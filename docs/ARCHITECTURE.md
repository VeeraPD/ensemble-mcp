# Architecture

## Layers

1. **Human** sets the goal and verifies anything only they can (real hardware, production).
2. **Lead** (Claude Code) plans, writes the *contracts* (shared interfaces and value types, in a directory no sub-agent may write), writes self-contained task prompts, reviews every returned file, runs the build and tests, and decides when to retry or escalate.
3. **Role sub-agents** (cheap model) each implement one slice against the contracts. A role is a name, a set of owned paths, and a prompt. Roles with disjoint paths run in parallel.
4. **Escalation tier** (optional): a stronger model listed in `provider.models`, used by the lead only after the default model fails on a step.

Why it works: the lead's context stays small (it reads diffs, not drafts), the contracts make parallel work composable, and ownership makes parallel work safe.

## One delegation, step by step

1. The lead calls `delegate_task` (or `delegate_parallel`) over MCP stdio.
2. **System prompt** = each `shared_context` file → the role's `instructions_file` → inline `instructions` → the role's `context` files → "You are the X agent. You own: …" → strict output-format rules.
3. **User prompt** = the task + the `context_files` the lead chose (capped by `max_context_bytes`).
4. One `POST {base_url}/chat/completions` with retry/backoff on 429/5xx and network errors.
5. The reply is parsed for blocks:
   ```
   === FILE: relative/path.ext ===
   <full contents>
   === END FILE ===
   NOTES: questions, assumptions, contract problems
   ```
   A stray markdown fence around contents is stripped. `NOTES:` is only read after the last file block.
6. Each path goes through the write policy. Allowed files are written; the rest are reported as REJECTED.
7. A summary returns to the lead; a line is appended to `.ensemble/log.jsonl`.

## Path policy ([paths.py](../src/ensemble_mcp/paths.py))

Write a file only if all of these hold:
- the path is relative, normalised and does not use `..`;
- it resolves (through symlinks) inside the project root;
- **both** the spelled path and the resolved path are under one of the role's `owns` (exact file or directory prefix; `src` does not match `srcx/`);
- neither is a secret (`.env*`, `*.pem`, `*.key`, SSH keys, `credentials*`), under `.git/` or `.ensemble/`, nor the config file.

Context reads use the same secret/protected rules and must stay inside the root.

## Protocol

Newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP stdio transport): `initialize`, `tools/list`, `tools/call`, `ping`; notifications are ignored. The server echoes the client's protocol version. Logs go to stderr only, never stdout. Tool failures return `isError: true` with a message rather than crashing the server.

## Design choices

- **File blocks instead of function calling.** Works with every chat model, needs no tool-use support, and the full file is explicit, so partial edits cannot silently corrupt a file.
- **JSON config.** Keeps the package dependency-free.
- **No execution.** The server writes files; the lead decides what to build and run.
- **Truncation is loud.** If `finish_reason == "length"`, the summary says so (an unterminated file block is never written).

## Limits

- Whole-file replacement only; for big files, split them or give the role a smaller target.
- Sub-agents do not see the repo unless the lead passes files, by design.
- Serial MCP request handling: one `delegate_parallel` call runs its tasks concurrently, but separate tool calls do not overlap.
