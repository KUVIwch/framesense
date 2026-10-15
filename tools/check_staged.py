"""Check staged paths and common credential signatures without printing secrets."""

from pathlib import PurePosixPath
import re
import subprocess
import sys

paths = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
    text=True,
    encoding="utf-8",
).splitlines()
problems = []
patterns = [
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----$"),
]
for path in paths:
    parts = PurePosixPath(path).parts
    if (
        any(
            p in ("data", "work", "outputs", "dist", ".codex-remote-attachments")
            for p in parts
        )
        or path == ".env"
        or path.endswith((".db", ".sqlite", ".arw", ".docx"))
    ):
        problems.append((path, "private/generated path"))
        continue
    content = subprocess.check_output(["git", "show", ":" + path])
    if len(content) > 2 * 1024 * 1024:
        problems.append((path, "large blob"))
    if any(p.search(content) for p in patterns):
        problems.append((path, "credential signature"))
if problems:
    for path, reason in problems:
        print(reason + ": " + path)
    sys.exit(1)
print(
    f"Staged check passed: {len(paths)} source/document/brand files; no private paths or common credential signatures."
)
