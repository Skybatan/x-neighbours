#!/usr/bin/env python3
"""Save an MCP tool result as data/<name>.json.

Accepts a file that is raw JSON, or text that wraps a single JSON object
(for example a tool log that quotes the response). Writes next to this script.

Usage:
  python3 save_raw.py <tool-result-file> <name>
"""
import json
import os
import sys


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
    with open(src, encoding="utf-8") as fh:
        data = parse_result(fh.read(), src)
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
