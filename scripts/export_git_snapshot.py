"""Export committed UTF-8 source files for publishing through the GitHub connector.

Only the explicitly supplied Git commit is read; ignored data and credentials
are never included. Used when local Git transport is not authenticated.
"""
import json
import subprocess
import sys

revision = sys.argv[1]
paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", revision]).decode("utf-8").split("\0")
elements = []
for path in filter(None, paths):
    if path == ".env" or path.startswith(("data/", ".venv/", ".tmp/")):
        raise SystemExit("Refusing to export sensitive/generated runtime files")
    data = subprocess.check_output(["git", "show", revision + ":" + path])
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Screenshots are delivered locally; source snapshots remain text-only.
        continue
    elements.append({"path": path, "mode": "100644", "type": "blob", "content": content})
if not any(item["path"] == ".gitattributes" for item in elements):
    elements.append({"path": ".gitattributes", "mode": "100644", "type": "blob", "content": "* text=auto eol=lf\n*.png binary\n*.jpg binary\n*.webp binary\n"})
print(json.dumps(elements, ensure_ascii=True))
