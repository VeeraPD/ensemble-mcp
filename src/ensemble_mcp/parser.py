"""Parse the strict file-block format sub-agents reply in."""
import re

FILE_RE = re.compile(r"^=== FILE: (.+?) ===\n(.*?)\n=== END FILE ===", re.S | re.M)
FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\n(.*?)\n```\s*$", re.S)

OUTPUT_RULES = (
    "\n\nOUTPUT FORMAT (strict). For every file you create or replace, emit exactly:\n"
    "=== FILE: relative/path.ext ===\n<full file contents, no markdown fences>\n=== END FILE ===\n"
    "Only create files inside your owned paths. Never truncate a file."
)


def parse_reply(text):
    """Return [(path, content), ...]. Strips a stray markdown fence around contents."""
    files = []
    for m in FILE_RE.finditer(text):
        content = m.group(2)
        fence = FENCE_RE.match(content.strip())
        if fence:
            content = fence.group(1)
        files.append((m.group(1).strip(), content))
    return files
