#!/usr/bin/env python3
"""Save an MCP tool result as data/<name>.json.

Accepts a file that is raw JSON, or text that wraps a single JSON object
(for example a tool log that quotes the response). A truncated write_to_file
display that names the full payload on a `Full text: /path/to/file.txt` line
is followed to that file. Writes next to this script.

Usage:
  python3 save_raw.py <tool-result-file> <name>
"""
import json
import os
import re
import sys


_FULL_TEXT = re.compile(r"(?m)^Full text:\s+(\S+)\s*$")


def resolve_wrapper(raw, src, seen=None):
    """Return payload text, following one Full text: path when this file is not JSON.

    Valid JSON is left alone, so a payload that happens to mention a path is
    not opened. A missing path is left for the JSON parser to reject.
    """
    text = raw.strip()
    try:
        json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        return text
    seen = set() if seen is None else seen
    match = _FULL_TEXT.search(raw)
    if not match:
        return raw
    path = match.group(1)
    if path in seen or os.path.abspath(path) == os.path.abspath(src):
        return raw
    if not os.path.isfile(path):
        return raw
    seen.add(path)
    with open(path, encoding="utf-8") as fh:
        followed = fh.read()
    return resolve_wrapper(followed, path, seen)


def load_result(src):
    with open(src, encoding="utf-8") as fh:
        raw = fh.read()
    return parse_result(resolve_wrapper(raw, src), src)


def parse_result(raw, src):
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        sys.exit(f"no JSON object found in {src}")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        sys.exit(f"could not parse JSON in {src} ({exc})")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python3 save_raw.py <tool-result-file> <name>")
    src, name = sys.argv[1], sys.argv[2]
    stem = name[:-5] if name.endswith(".json") else name
    if not stem or any(c in stem for c in "/\\") or stem.startswith("."):
        sys.exit("name must be a file stem such as posts_1 or likes_123")
    data = load_result(src)
    if not isinstance(data, dict):
        sys.exit(f"expected a JSON object in {src}")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, stem + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    rows = data.get("data") or []
    created = [row.get("created_at") for row in rows if isinstance(row, dict)]
    print(stem, data.get("meta"), len(rows), created[-1] if created else None)


if __name__ == "__main__":
    main()
