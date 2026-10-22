"""Dependency-free MCP (stdio, newline-delimited JSON-RPC) server."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from . import __version__
from .tasks import run_task


def build_tools(cfg):
    role_names = list(cfg.roles)
    role_help = "; ".join(f"{n} owns {', '.join(r.owns)}" for n, r in cfg.roles.items())
    props = {
        "role": {"type": "string", "enum": role_names, "description": f"Sub-agent role. {role_help}"},
        "task": {"type": "string", "description": "Self-contained task prompt: goal, exact file paths, API signatures, acceptance criteria."},
        "context_files": {"type": "array", "items": {"type": "string"},
                          "description": "Project-relative files to include (contracts, related code)."},
        "model": {"type": "string", "enum": cfg.provider.models,
                  "description": f"Default {cfg.provider.default_model}. Escalate to a stronger model only after the default fails."},
        "dry_run": {"type": "boolean", "description": "Parse and validate the reply but write nothing."},
    }
    n = cfg.max_parallel
    return [
        {"name": "delegate_task",
         "description": "Delegate one implementation task to a sub-agent. It writes files into the role's owned paths and returns a summary. Review the files afterwards.",
         "inputSchema": {"type": "object", "properties": props, "required": ["role", "task"]}},
        {"name": "delegate_parallel",
         "description": f"Run up to {n} sub-agent tasks concurrently, each with a distinct role. Use only when tasks touch different owned paths.",
         "inputSchema": {"type": "object", "required": ["tasks"], "properties": {
             "tasks": {"type": "array", "minItems": 1, "maxItems": n,
                       "items": {"type": "object", "properties": props, "required": ["role", "task"]}}}}},
        {"name": "list_roles",
         "description": "List configured roles, the paths each owns, and the available models.",
         "inputSchema": {"type": "object", "properties": {}}},
    ]


def call_tool(cfg, name, args):
    if name == "delegate_task":
        return run_task(cfg, args)
    if name == "delegate_parallel":
        tasks = args["tasks"]
        if len(tasks) > cfg.max_parallel:
            raise ValueError(f"at most {cfg.max_parallel} parallel tasks")
        roles = [t.get("role") for t in tasks]
        if len(set(roles)) != len(roles):
            raise ValueError("parallel tasks must have distinct roles")

        def safe(t):
            try:
                return run_task(cfg, t)
            except Exception as e:
                return f"## {t.get('role')} FAILED: {e}"

        with ThreadPoolExecutor(max_workers=cfg.max_parallel) as pool:
            return "\n\n".join(pool.map(safe, tasks))
    if name == "list_roles":
        lines = [f"models: {cfg.provider.models} (default {cfg.provider.default_model})"]
        for n, r in cfg.roles.items():
            lines.append(f"- {n}: owns {r.owns}" + (f" — {r.description}" if r.description else ""))
        return "\n".join(lines)
    raise ValueError(f"unknown tool {name}")


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def handle(cfg, msg):
    """Return a response dict for a request, or None for notifications."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        ver = (msg.get("params") or {}).get("protocolVersion", "2024-11-05")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": ver, "capabilities": {"tools": {}},
            "serverInfo": {"name": "ensemble-mcp", "version": __version__}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": build_tools(cfg)}}
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            out, err = call_tool(cfg, p.get("name"), p.get("arguments") or {}), False
        except Exception as e:
            out, err = f"Error: {e}", True
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": out}], "isError": err}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}


def serve(cfg):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(cfg, msg)
        if resp is not None:
            _send(resp)
