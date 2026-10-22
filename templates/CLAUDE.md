# <Project> — lead developer workflow

Copy into your project root and edit the bracketed parts.

You (Claude) are the lead: you plan, write contracts, write task prompts, delegate coding to sub-agents through the `ensemble` MCP server, then review and integrate. Read docs/PRD.md [or your product brief] first.

## Layout
- [contracts dir]/ — shared interfaces and types. Yours alone; no role may write here.
- docs/agents/<role>.md — role prompts. docs/CONVENTIONS.md — rules sent to every sub-agent.
- ensemble.json — roles and owned paths. Call `list_roles` to see them.

## Loop
1. Write or update contracts first. Sub-agents code against them.
2. Write each task prompt self-contained: goal, exact file paths, API signatures, acceptance criteria. Pass contracts and related code as `context_files`.
3. Run roles with disjoint paths via `delegate_parallel`; otherwise `delegate_task`.
4. Review every returned file by reading it. Run [build and test command]. Fix small issues yourself; send a precise follow-up for larger ones. Use the stronger model only after the default fails.
5. Treat REJECTED paths as a signal: the task or the role's `owns` is wrong. Fix the contracts or config and re-delegate.

## Rules
- Do not commit or push unless asked. Never read or print .env.
- Anything needing real hardware or production is verified by the user; list those checks explicitly.
