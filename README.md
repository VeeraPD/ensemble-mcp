# ensemble-mcp

Let a strong AI **master** (Claude Code) hand coding work to cheaper **sub-agents** over [MCP](https://modelcontextprotocol.io). Each sub-agent can only change the paths its role owns, so several can work in parallel without colliding.

- Zero dependencies (Python 3.9+, stdlib only)
- Any OpenAI-compatible model: DeepSeek (default), OpenAI, OpenRouter, Ollama
- Roles, prompts and models live in one `ensemble.json`
- Ownership is enforced, including through symlinks. Secrets and `.git` are never touched

## How it works

```
┌──────────────────────────────┐
│ MASTER  (Claude Code)        │  plans, defines contracts, reviews, runs tests
└──────────────┬───────────────┘
               │ MCP: delegate_task / delegate_parallel
┌──────────────▼───────────────┐
│ ensemble-mcp                 │  builds prompt, calls model, checks paths
└───────┬──────────┬───────────┘
        │          │          │
┌───────▼───┐ ┌────▼──────┐ ┌─▼─────────┐
│ backend   │ │ web       │ │ tests     │   sub-agents (cheap model)
│ src/      │ │ web/      │ │ tests/    │   each limited to its own paths
└───────────┘ └───────────┘ └───────────┘
```

The master owns the shared interfaces (contracts) that no sub-agent may change, and reviews everything that comes back.

## Quick start

```bash
pip install git+https://github.com/VeeraPD/ensemble-mcp
cd your-project
ensemble-mcp init                  # creates ensemble.json
export DEEPSEEK_API_KEY=sk-...     # or put it in ./.env (git-ignored)
ensemble-mcp check                 # verifies config, key and prompts
claude mcp add ensemble -- ensemble-mcp -c "$PWD/ensemble.json" serve
```

Copy [templates/CLAUDE.md](templates/CLAUDE.md) into your project so the master knows the workflow, then ask Claude to build something.

## Multi-level agents

For large projects, add a middle level: one **area lead** per part of the codebase. Each area lead is a Claude Code subagent with its own `ensemble.json` and MCP server.

```
┌────────────────────────────────────────────┐
│ LEVEL 1  MASTER                            │  cross-area contracts, final review
└───────────────┬────────────────┬───────────┘
                │                │
      ┌─────────▼──────┐  ┌──────▼─────────┐
      │ LEVEL 2        │  │ LEVEL 2        │
      │ mobile lead    │  │ web lead       │  Claude Code subagents,
      │ (subagent)     │  │ (subagent)     │  one per area
      └───┬───────┬────┘  └───┬────────┬───┘
          │       │           │        │
       ┌──▼──┐ ┌──▼───┐    ┌──▼──┐  ┌──▼───┐
       │ ui  │ │store │    │ api │  │front │   LEVEL 3  workers
       └─────┘ └──────┘    └─────┘  └──────┘   (cheap models, owned paths)
```

```bash
claude mcp add ensemble-mobile -- ensemble-mcp -c /abs/mobile/ensemble.json serve
claude mcp add ensemble-web    -- ensemble-mcp -c /abs/web/ensemble.json serve
```

Rules:
- Cross-area contracts live in a folder only the master edits.
- Owned paths must not overlap between configs.
- Each area lead reports a short summary upward; the master does not re-read every file.
- Add this level only when one lead can no longer hold the whole codebase. Otherwise the single-level setup above is simpler and cheaper.

## Configuration

`ensemble.json`, paths relative to the file:

```json
{
  "provider": {
    "base_url": "https://api.deepseek.com",
    "api_key_env": "DEEPSEEK_API_KEY",
    "models": ["deepseek-chat", "deepseek-reasoner"],
    "default_model": "deepseek-chat"
  },
  "shared_context": ["docs/CONVENTIONS.md"],
  "roles": {
    "backend": { "owns": ["src/"], "instructions_file": "docs/agents/backend.md" },
    "tests":   { "owns": ["tests/"], "instructions": "Test through public APIs only." }
  }
}
```

| Key | Meaning |
|---|---|
| `provider.base_url` | Any OpenAI-compatible base URL. Ollama: `http://localhost:11434/v1` with `"api_key_env": ""` |
| `provider.models`, `default_model` | Allowed models. Use the default first, a stronger one only for steps that fail |
| `shared_context` | Files added to every role's prompt (coding rules) |
| `roles.<name>.owns` | Files or folders the role may change |
| `roles.<name>.instructions_file` / `instructions` | The role's prompt |
| `max_parallel` | Cap for parallel tasks (default 5) |

Optional: `roles.<name>.context`, `max_context_bytes`, `provider.timeout`, `provider.max_retries`, `provider.max_tokens`, `audit_log`.

## MCP tools

| Tool | Purpose |
|---|---|
| `delegate_task` | One role, one task: `role`, `task`, `context_files`, `model`, `dry_run` |
| `delegate_parallel` | Several tasks with distinct roles, run concurrently |
| `list_roles` | Roles, owned paths, models |

A good task states the goal, the exact file paths, the interfaces to match and how to check the result, and passes the relevant contracts as `context_files`. Each call returns the files changed and any paths that were rejected for being outside the role.

## CLI

```
ensemble-mcp init [dir]               create ensemble.json
ensemble-mcp check                    validate setup
ensemble-mcp run ROLE "task" -f file  run one task without MCP (--dry-run to preview)
ensemble-mcp serve                    MCP server on stdio (default)
```

## Safety

Model output is untrusted. A file is only saved if its path is inside the project, not a secret or `.git`, and under the role's `owns` (checked before and after following symlinks). Nothing the model returns is ever executed. Review every diff, and note that context files are sent to your model provider. See [SECURITY.md](SECURITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

[MIT](LICENSE). Not affiliated with Anthropic or DeepSeek.
