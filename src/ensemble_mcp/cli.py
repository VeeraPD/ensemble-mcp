"""Command line: serve (MCP), check (validate setup), run (one task without MCP), init (scaffold)."""
import argparse
import json
import os
import sys

from . import __version__
from .client import ApiError, load_api_key
from .config import ConfigError, find_config, load_config
from .server import serve
from .tasks import run_task

STARTER = {
    "provider": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    "shared_context": ["docs/CONVENTIONS.md"],
    "roles": {
        "backend": {"owns": ["src/"], "instructions": "Role: backend. Implement server-side logic.", "description": "server code"},
        "tests": {"owns": ["tests/"], "instructions": "Role: tests. Write tests; never edit sources.", "description": "test code"},
    },
}


def cmd_init(a):
    target = os.path.abspath(a.dir)
    cfg_path = os.path.join(target, "ensemble.json")
    if os.path.exists(cfg_path) and not a.force:
        sys.exit(f"{cfg_path} exists (use --force to overwrite)")
    os.makedirs(os.path.join(target, "docs"), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(STARTER, fh, indent=2)
        fh.write("\n")
    conv = os.path.join(target, "docs", "CONVENTIONS.md")
    if not os.path.exists(conv):
        with open(conv, "w", encoding="utf-8") as fh:
            fh.write("Shared rules for every sub-agent.\n\n- Implement exactly the task. No extra features.\n")
    print(f"created {cfg_path}\nNext: export DEEPSEEK_API_KEY=..., edit roles, run `ensemble-mcp check`.")


def cmd_check(cfg, _a):
    ok = True
    print(f"config: {cfg.path}\nroot:   {cfg.root}\nmodel:  {cfg.provider.default_model} @ {cfg.provider.chat_url}")
    try:
        load_api_key(cfg)
        print(f"key:    {cfg.provider.api_key_env} found")
    except ApiError as e:
        ok = False
        print(f"key:    MISSING - {e}")
    from .tasks import build_system
    for name, role in cfg.roles.items():
        try:
            build_system(cfg, name)
            print(f"role {name}: ok, owns {role.owns}")
        except Exception as e:
            ok = False
            print(f"role {name}: ERROR {e}")
    sys.exit(0 if ok else 1)


def cmd_run(cfg, a):
    task = sys.stdin.read() if a.task == "-" else a.task
    spec = {"role": a.role, "task": task, "context_files": a.file, "model": a.model, "dry_run": a.dry_run}
    print(run_task(cfg, spec))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ensemble-mcp", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("-c", "--config", help="path to ensemble.json (default: search upward, or $ENSEMBLE_CONFIG)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="run the MCP server on stdio (default)")
    sub.add_parser("check", help="validate config, key and role prompts")
    r = sub.add_parser("run", help="run one task from the shell")
    r.add_argument("role")
    r.add_argument("task", help="task text, or - for stdin")
    r.add_argument("-f", "--file", action="append", default=[], help="context file (repeatable)")
    r.add_argument("--model")
    r.add_argument("--dry-run", action="store_true")
    i = sub.add_parser("init", help="write a starter ensemble.json")
    i.add_argument("dir", nargs="?", default=".")
    i.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "init":
        return cmd_init(a)
    try:
        cfg = load_config(a.config or find_config())
    except ConfigError as e:
        sys.exit(f"config error: {e}")
    if a.cmd == "check":
        return cmd_check(cfg, a)
    if a.cmd == "run":
        try:
            return cmd_run(cfg, a)
        except (ApiError, ValueError, OSError) as e:
            sys.exit(f"error: {e}")
    serve(cfg)


if __name__ == "__main__":
    main()
