# Contributing

- Zero runtime dependencies is a goal; please keep it (stdlib only).
- Run the tests: `PYTHONPATH=src python3 -m unittest discover -s tests`
- Any change to `paths.py` needs a test that tries to escape (symlinks, `..`, secrets).
- Keep the MCP surface small. New tools need a clear reason.
- Be kind and constructive; harassment is not tolerated. Maintainers may remove comments or contributors that break this.
- Contributions are licensed under the MIT License.
