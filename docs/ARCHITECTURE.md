# Architecture

## One delegation

```
master ──delegate_task──► ensemble-mcp ──► model API
                               │
        1. prompt = shared rules + role prompt + task + context files
        2. model replies with file blocks:
             === FILE: path ===
             <contents>
             === END FILE ===
        3. each path is checked against the role's owned paths
        4. allowed files are saved, others reported as REJECTED
        5. summary returns to the master; run is logged to .ensemble/log.jsonl
```

## Path rules

A file is saved only if all hold:
- the path is relative and has no `..`
- it resolves, through symlinks, inside the project root
- both the written path and the resolved path are under one of the role's `owns`
- it is not a secret (`.env*`, `*.pem`, `*.key`, SSH keys), `.git/`, `.ensemble/` or the config file

Context files follow the same secret and root rules.

## Protocol

MCP over stdio (newline-delimited JSON-RPC 2.0): `initialize`, `tools/list`, `tools/call`, `ping`. Logs go to stderr. A failed tool call returns `isError: true`; it never stops the server.

## Limits

- Each reply replaces whole files, so keep tasks small. A reply that hits the token limit is flagged.
- Sub-agents see only the files the master passes in.
