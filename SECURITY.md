# Security

## Threat model
Sub-agent output is untrusted model text that gets written to your disk. ensemble-mcp limits the damage:

- **Write ownership.** A role may only write inside the paths it `owns`. Paths are normalised and resolved through symlinks; both the spelled and the real location must be owned.
- **Protected files.** `.env*`, `*.pem`, `*.key`, SSH keys, `.git/`, `.ensemble/` and the config file are never writable or readable as context, even if a role owns them.
- **Context allow-list.** `context_files` and prompt files must resolve inside the project root.
- **No code execution.** The server never runs anything the model returns. It only writes files. Review them before you run them.

## Not covered
- A role can still write bad or malicious code into its own paths. Always review diffs (use git).
- Everything in `context_files` and the prompts is sent to your configured provider. Do not include secrets or code you may not share.
- Prompt injection inside context files can steer a sub-agent within its owned paths.

## API keys
Keys come from the environment or a git-ignored `.env`. Never commit them. If a key leaks, revoke it at the provider.

## Reporting
Open a private security advisory on the repository, or email the maintainers listed there. Please do not file public issues for vulnerabilities.
