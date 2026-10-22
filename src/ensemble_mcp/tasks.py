"""Run one delegated task: build prompts, call the model, write only permitted files."""
import json
import os
import sys
import threading
import time

from . import client
from .parser import OUTPUT_RULES, parse_reply
from .paths import PathError, resolve_read, resolve_write

_log_lock = threading.Lock()


def log(msg):
    with _log_lock:
        print(msg, file=sys.stderr, flush=True)


def _read(cfg, rel):
    _, full = resolve_read(cfg, rel)
    with open(full, encoding="utf-8") as fh:
        return fh.read()


def build_system(cfg, role):
    r = cfg.roles[role]
    parts = []
    for name in cfg.shared_context:
        parts.append(f"# {name}\n{_read(cfg, name)}")
    if r.instructions_file:
        parts.append(f"# {r.instructions_file}\n{_read(cfg, r.instructions_file)}")
    if r.instructions:
        parts.append(r.instructions)
    for name in r.context:
        parts.append(f"# {name}\n{_read(cfg, name)}")
    parts.append(f"You are the '{role}' agent. You own: {', '.join(r.owns)}")
    return "\n\n".join(parts) + OUTPUT_RULES


def build_user(cfg, spec):
    ctx, total = "", 0
    for path in spec.get("context_files") or []:
        text = _read(cfg, path)
        total += len(text.encode())
        if total > cfg.max_context_bytes:
            raise ValueError(f"context_files exceed {cfg.max_context_bytes} bytes; pass fewer or smaller files")
        ctx += f"\n--- {path} ---\n{text}\n"
    return spec["task"] + (f"\n\nCONTEXT FILES:{ctx}" if ctx else "")


def _audit(cfg, entry):
    if not cfg.audit_log:
        return
    d = os.path.join(cfg.root, ".ensemble")
    os.makedirs(d, exist_ok=True)
    with _log_lock, open(os.path.join(d, "log.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def run_task(cfg, spec):
    role = spec.get("role")
    if role not in cfg.roles:
        raise ValueError(f"unknown role '{role}'; valid: {list(cfg.roles)}")
    if not spec.get("task"):
        raise ValueError("'task' is required")
    model = spec.get("model") or cfg.provider.default_model
    if model not in cfg.provider.models:
        raise ValueError(f"unknown model '{model}'; valid: {cfg.provider.models}")
    dry = bool(spec.get("dry_run"))

    system, user = build_system(cfg, role), build_user(cfg, spec)
    log(f"[{role}] start model={model}{' (dry run)' if dry else ''}")
    t0 = time.time()
    text, finish, usage = client.chat(cfg, system, user, model)

    files = parse_reply(text)
    written, rejected = [], []
    for rel_in, content in files:
        try:
            rel, full = resolve_write(cfg, role, rel_in)
        except PathError as e:
            rejected.append(f"{rel_in}: {e}")
            continue
        if not dry:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content.rstrip("\n") + "\n")
        written.append(rel)

    secs = round(time.time() - t0)
    log(f"[{role}] done {secs}s files={len(written)}")
    _audit(cfg, {"ts": int(t0), "role": role, "model": model, "dry_run": dry, "written": written,
                 "rejected": rejected, "finish": finish, "usage": usage})

    lines = [f"## {role} ({model}, {secs}s, {usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out)"]
    lines.append(("Would write: " if dry else "Written: ") + (", ".join(written) if written else "none"))
    if rejected:
        lines.append("REJECTED: " + "; ".join(rejected))
    if finish == "length":
        lines.append("WARNING: reply hit the token limit; the last file may be missing or cut. Split the task.")
    if not files:
        lines.append("Raw reply (no file blocks found):\n" + text[:4000])
    return "\n".join(lines)
