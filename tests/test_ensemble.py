import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ensemble_mcp import client
from ensemble_mcp.config import ConfigError, find_config, load_config
from ensemble_mcp.parser import parse_reply
from ensemble_mcp.paths import PathError, resolve_read, resolve_write
from ensemble_mcp.server import build_tools, call_tool, handle
from ensemble_mcp.tasks import run_task


def make_project(extra=None, base_url="http://127.0.0.1:1"):
    d = tempfile.mkdtemp()
    cfg = {
        "provider": {"base_url": base_url, "api_key_env": "ENSEMBLE_TEST_KEY", "max_retries": 1,
                     "models": ["m-small", "m-big"], "default_model": "m-small"},
        "shared_context": ["rules.md"],
        "roles": {
            "backend": {"owns": ["src/", "main.py"], "instructions": "backend role"},
            "tests": {"owns": ["tests/"], "instructions": "tests role"},
        },
    }
    cfg.update(extra or {})
    with open(os.path.join(d, "ensemble.json"), "w") as fh:
        json.dump(cfg, fh)
    with open(os.path.join(d, "rules.md"), "w") as fh:
        fh.write("be careful")
    os.makedirs(os.path.join(d, "src"))
    return d


class FakeApi(BaseHTTPRequestHandler):
    reply = ""
    finish_reason = "stop"
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeApi.seen.append({"body": body, "auth": self.headers.get("Authorization")})
        out = json.dumps({"choices": [{"message": {"content": FakeApi.reply}, "finish_reason": FakeApi.finish_reason}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 2}}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        os.environ["ENSEMBLE_TEST_KEY"] = "test-key"
        self.dir = make_project()
        self.cfg = load_config(os.path.join(self.dir, "ensemble.json"))


class ParserTests(unittest.TestCase):
    def test_files_fence_and_notes(self):
        text = "=== FILE: a.py ===\n```python\nx = 1  # NOTES: inline\n```\n=== END FILE ===\nNOTES: hello"
        files, notes = parse_reply(text)
        self.assertEqual(files, [("a.py", "x = 1  # NOTES: inline")])
        self.assertEqual(notes, "hello")

    def test_no_blocks(self):
        files, notes = parse_reply("just chatter")
        self.assertEqual(files, [])
        self.assertEqual(notes, "")


class ConfigTests(Base):
    def test_find_config_walks_up(self):
        sub = os.path.join(self.dir, "src")
        os.environ.pop("ENSEMBLE_CONFIG", None)
        self.assertEqual(os.path.realpath(find_config(sub)), os.path.realpath(os.path.join(self.dir, "ensemble.json")))

    def test_rejects_unsafe_owns(self):
        for bad in ("../x", "/etc", "."):
            d = make_project({"roles": {"r": {"owns": [bad]}}})
            with self.assertRaises(ConfigError):
                load_config(os.path.join(d, "ensemble.json"))

    def test_default_model_must_exist(self):
        d = make_project({"provider": {"models": ["a"], "default_model": "b"}})
        with self.assertRaises(ConfigError):
            load_config(os.path.join(d, "ensemble.json"))


class PathTests(Base):
    def test_write_inside_owned(self):
        rel, _ = resolve_write(self.cfg, "backend", "src/app/x.py")
        self.assertEqual(rel, os.path.join("src", "app", "x.py"))
        resolve_write(self.cfg, "backend", "main.py")

    def test_write_outside_owned(self):
        for bad in ("tests/x.py", "srcx/y.py", "main.pyc", "../escape.py", "/abs.py", "ensemble.json"):
            with self.assertRaises(PathError, msg=bad):
                resolve_write(self.cfg, "backend", bad)

    def test_protected_even_if_owned(self):
        cfg = load_config(os.path.join(make_project({"roles": {"r": {"owns": ["src"]}}}), "ensemble.json"))
        for bad in ("src/.env", "src/server.pem", "src/.env.local"):
            with self.assertRaises(PathError, msg=bad):
                resolve_write(cfg, "r", bad)

    def test_symlink_escape(self):
        outside = tempfile.mkdtemp()
        os.symlink(outside, os.path.join(self.dir, "src", "link"))
        with self.assertRaises(PathError):
            resolve_write(self.cfg, "backend", "src/link/evil.py")

    def test_symlink_into_unowned_project_dir(self):
        os.makedirs(os.path.join(self.dir, "tests"))
        os.symlink(os.path.join(self.dir, "tests"), os.path.join(self.dir, "src", "t"))
        with self.assertRaises(PathError):
            resolve_write(self.cfg, "backend", "src/t/x.py")

    def test_read_blocks_secrets_and_escape(self):
        with open(os.path.join(self.dir, ".env"), "w") as fh:
            fh.write("K=v")
        for bad in (".env", "../x", "/etc/passwd", ".git/config"):
            with self.assertRaises(PathError, msg=bad):
                resolve_read(self.cfg, bad)
        resolve_read(self.cfg, "rules.md")


class EndToEnd(Base):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeApi)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        os.environ["ENSEMBLE_TEST_KEY"] = "test-key"
        self.dir = make_project(base_url=f"http://127.0.0.1:{self.srv.server_port}")
        self.cfg = load_config(os.path.join(self.dir, "ensemble.json"))
        FakeApi.seen.clear()
        FakeApi.finish_reason = "stop"

    def test_writes_owned_rejects_others(self):
        FakeApi.reply = ("=== FILE: src/a.py ===\nprint(1)\n=== END FILE ===\n"
                         "=== FILE: tests/t.py ===\nx\n=== END FILE ===\nNOTES: check this")
        out = run_task(self.cfg, {"role": "backend", "task": "do it", "context_files": ["rules.md"]})
        self.assertTrue(os.path.exists(os.path.join(self.dir, "src", "a.py")))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "tests", "t.py")))
        self.assertIn("REJECTED", out)
        self.assertIn("NOTES: check this", out)
        seen = FakeApi.seen[0]
        self.assertEqual(seen["auth"], "Bearer test-key")
        self.assertEqual(seen["body"]["model"], "m-small")
        self.assertIn("be careful", seen["body"]["messages"][0]["content"])
        self.assertIn("backend role", seen["body"]["messages"][0]["content"])
        self.assertIn("--- rules.md ---", seen["body"]["messages"][1]["content"])
        with open(os.path.join(self.dir, ".ensemble", "log.jsonl")) as fh:
            log = fh.read()
        self.assertIn('"role": "backend"', log)

    def test_dry_run_writes_nothing(self):
        FakeApi.reply = "=== FILE: src/a.py ===\nprint(1)\n=== END FILE ==="
        out = run_task(self.cfg, {"role": "backend", "task": "t", "dry_run": True})
        self.assertIn("Would write: src", out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "src", "a.py")))

    def test_truncation_warning(self):
        FakeApi.reply, FakeApi.finish_reason = "=== FILE: src/a.py ===\nhalf", "length"
        out = run_task(self.cfg, {"role": "backend", "task": "t"})
        self.assertIn("WARNING", out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "src", "a.py")))

    def test_bad_role_and_model(self):
        with self.assertRaises(ValueError):
            run_task(self.cfg, {"role": "nope", "task": "t"})
        with self.assertRaises(ValueError):
            run_task(self.cfg, {"role": "backend", "task": "t", "model": "zzz"})

    def test_missing_key(self):
        del os.environ["ENSEMBLE_TEST_KEY"]
        with self.assertRaises(client.ApiError):
            run_task(self.cfg, {"role": "backend", "task": "t"})

    def test_parallel_requires_distinct_roles_and_isolates_failures(self):
        FakeApi.reply = "=== FILE: src/p.py ===\n1\n=== END FILE ==="
        with self.assertRaises(ValueError):
            call_tool(self.cfg, "delegate_parallel", {"tasks": [{"role": "backend", "task": "a"}, {"role": "backend", "task": "b"}]})
        out = call_tool(self.cfg, "delegate_parallel", {"tasks": [
            {"role": "backend", "task": "a"}, {"role": "tests", "task": "b", "context_files": [".env"]}]})
        self.assertIn("## backend", out)
        self.assertIn("tests FAILED", out)


class ProtocolTests(Base):
    def test_handshake_and_tools(self):
        init = handle(self.cfg, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        self.assertIsNone(handle(self.cfg, {"method": "notifications/initialized"}))
        tools = handle(self.cfg, {"id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["delegate_task", "delegate_parallel", "list_roles"])
        self.assertEqual(tools[0]["inputSchema"]["properties"]["role"]["enum"], ["backend", "tests"])

    def test_tool_error_is_reported_not_raised(self):
        r = handle(self.cfg, {"id": 3, "method": "tools/call", "params": {"name": "delegate_task", "arguments": {"role": "x", "task": "t"}}})
        self.assertTrue(r["result"]["isError"])

    def test_unknown_method(self):
        self.assertEqual(handle(self.cfg, {"id": 4, "method": "bogus"})["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
