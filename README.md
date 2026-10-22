# ensemble-mcp

Let one strong AI **lead** (Claude Code) plan the work and hand the typing to cheaper, **role-scoped sub-agents** (DeepSeek by default, any OpenAI-compatible model works) over [MCP](https://modelcontextprotocol.io). Each sub-agent can only write inside the paths its role owns, so five of them can work in parallel without stepping on each other.

- **Zero dependencies.** One small Python package, stdlib only (Python 3.9+).
- **Enforced ownership.** Writes outside a role's paths are rejected, symlinks included. Secrets and `.git` are never touched.
- **Provider-agnostic.** DeepSeek, OpenAI, OpenRouter, Ollama, anything that speaks `/chat/completions`.
- **Config, not code.** Roles, prompts, shared rules and models live in one `ensemble.json`.
- **Battle-tested workflow.** Built for and used on a real multi-role Swift app. See [examples/swift-ios](examples/swift-ios).

## How it works

```
        you
         │
   ┌─────▼─────┐  1. writes contracts (interfaces, types) and task prompts
   │   LEAD    │  4. reviews every file, runs build + tests, fixes or re-delegates
   │ (Claude)  │
   └─────┬─────┘
         │ MCP: delegate_task / delegate_parallel
   ┌─────▼──────────────────────────────┐
   │ ensemble-mcp                       │  builds prompt = shared rules + role prompt
   │  • role → owned paths              │            + task + context files
   │  • path policy (symlink-safe)      │  calls the model, parses file blocks,
   │  • audit log                       │  writes only what the role owns
   └─────┬───────┬───────┬──────────────┘
         ▼       ▼       ▼
     backend   web     tests      sub-agents, each confined to its own paths
```

Layers: **you → lead → role sub-agents → (optionally) a stronger model for retries.** The lead owns the contracts (the shared interfaces) and is the only reviewer; sub-agents never see each other's work except through files the lead passes as context. Full design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

```bash
pip install git+https://github.com/VeeraPD/ensemble-mcp      # or: pip install -e . from a clone
cd your-project
ensemble-mcp init                                          # writes ensemble.json + docs/CONVENTIONS.md
export DEEPSEEK_API_KEY=sk-...                             # or put it in ./.env (git-ignored!)
ensemble-mcp check                                         # validates config, key, prompts
```

Register it with Claude Code. Either run

```bash
claude mcp add ensemble -- ensemble-mcp --config /absolute/path/to/your-project/ensemble.json serve
```

or put this in the project's `.mcp.json`:

```json
{
  "mcpServers": {
    "ensemble": {
      "command": "ensemble-mcp",
      "args": ["--config", "/absolute/path/to/your-project/ensemble.json", "serve"]
    }
  }
}
```

Without installing, `"command": "python3", "args": ["-m", "ensemble_mcp", "--config", "...", "serve"]` with `PYTHONPATH=/path/to/ensemble-mcp/src` also works.

Then copy [templates/CLAUDE.md](templates/CLAUDE.md) into your project so the lead knows the workflow, and ask Claude to build something.

## Configuration

`ensemble.json` (paths are relative to this file):

```json
{
  "provider": {
    "base_url": "https://api.deepseek.com",
    "api_key_env": "DEEPSEEK_API_KEY",
    "models": ["deepseek-chat", "deepseek-reasoner"],
    "default_model": "deepseek-chat",
    "timeout": 900,
    "max_retries": 3,
    "max_tokens": 0
  },
  "shared_context": ["docs/CONVENTIONS.md"],
  "max_context_bytes": 120000,
  "max_parallel": 5,
  "audit_log": true,
  "roles": {
    "backend": {
      "owns": ["src/"],
      "instructions_file": "docs/agents/backend.md",
      "context": [],
      "description": "server code"
    }
  }
}
```

| Key | Meaning |
|---|---|
| `provider.base_url` | Any OpenAI-compatible base URL (`/chat/completions` is appended). Ollama: `http://localhost:11434/v1` with `"api_key_env": ""`. |
| `provider.models` / `default_model` | Allowed model names. The lead uses the default and escalates to a stronger one only after failures. Check your provider for current names. |
| `shared_context` | Files prepended to every role's system prompt (coding rules, product brief). |
| `roles.<name>.owns` | Files or directories the role may write. Everything else is rejected. |
| `roles.<name>.instructions_file` / `instructions` | Role prompt, from a file and/or inline. |
| `roles.<name>.context` | Extra files always added to this role's system prompt. |
| `max_parallel` | Cap for `delegate_parallel` (1–16). |
| `audit_log` | Append every run to `.ensemble/log.jsonl`. |

Config is found via `--config`, `$ENSEMBLE_CONFIG`, or by searching upward from the current directory.

## MCP tools

| Tool | Purpose |
|---|---|
| `delegate_task` | One role, one task. Args: `role`, `task`, `context_files`, `model`, `dry_run`. |
| `delegate_parallel` | Up to `max_parallel` tasks with **distinct** roles, run concurrently. One failure does not sink the others. |
| `list_roles` | Roles, owned paths and models. |

Each call returns a summary: files written, files **REJECTED** (outside ownership), a truncation warning if the model hit its token limit, and the sub-agent's `NOTES:` (questions or contract problems it hit). Treat NOTES as claims to verify, not facts.

## CLI

```
ensemble-mcp init [dir]                  scaffold ensemble.json
ensemble-mcp check                       validate setup
ensemble-mcp run ROLE "task" -f file     one task without MCP (add --dry-run to preview)
ensemble-mcp serve                       MCP server on stdio (the default)
```

## Safety

Sub-agent output is untrusted text written to your disk. Ownership, symlink resolution, protected secrets and no code execution limit the blast radius; they do not replace review. Use git and read every diff. Details and what is *not* covered in [SECURITY.md](SECURITY.md). Everything you pass as context is sent to your model provider.

## More docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, prompt assembly, path policy, protocol
- [docs/WRITING_TASKS.md](docs/WRITING_TASKS.md) — how to write prompts that sub-agents get right the first time
- [templates/CLAUDE.md](templates/CLAUDE.md) — drop-in lead workflow for your project
- [examples/](examples) — Swift/iPadOS and Python configs

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE). Not affiliated with Anthropic or DeepSeek.
