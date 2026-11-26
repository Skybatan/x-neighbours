#!/usr/bin/env python3
"""Render the Community Honor Roll from the saved global list.

The page lists recommended accounts: each @handle links to that profile,
with the recommendation count when the file has one. Joining, leaving, and
sharing stay in the chat. This script does not follow anyone.

  python3 community_page.py --global PATH --out DIR
"""
import argparse
import json
import os

import report_page
import x_neighbours as xn

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "templates", "community.canvas.tsx")
PLACEHOLDER = "/*__PAGE_JSON__*/ null as unknown as CommunityPage"

TITLE = xn.COMMUNITY_HONOR_ROLL
INTRO = "Accounts other owners recommended. A recommendation is not a follow."
EXPLAINER = "The count is how many owners listed that account."


def part(text, href=None):
    return {"text": text or "", "href": href or None}


def profile_url(handle):
    handle = (handle or "").lstrip("@")
    if not handle:
        return None
    return f"https://x.com/{handle}"


def load_entries(path):
    """Recommended accounts, most recommendations first.

    Returns None when the file is missing. An empty list means the file
    has no accounts to show.
    """
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    raw = doc.get("neighbours") if isinstance(doc, dict) else None
    if not isinstance(raw, dict):
        return []
    rows = []
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        handle = str(entry.get("handle") or "").lstrip("@")
        if not handle:
            continue
        count = entry.get("recommendation_count")
        has_count = isinstance(count, int) and not isinstance(count, bool)
        rows.append({
            "handle": handle,
            "count": int(count) if has_count else 0,
            "has_count": has_count,
            "user_id": str(entry.get("user_id") or key),
        })
    rows.sort(key=lambda row: (-row["count"], row["handle"].lower()))
    return rows


def build_model(entries):
    items = []
    for row in entries:
        lines = [{"parts": [part("@" + row["handle"], profile_url(row["handle"]))]}]
        if row.get("has_count"):
            lines.append({
                "parts": [part(xn.counted(row["count"], "recommendation", "recommendations"))],
            })
        items.append({"lines": lines})
    summary = xn.counted(len(entries), "recommended account", "recommended accounts")
    return {
        "title": TITLE,
        "summary": summary,
        "intro": INTRO,
        "headline": f"{TITLE} · {summary}",
        "sections": [
            {
                "heading": "Recommended",
                "explainer": EXPLAINER,
                "preface": None,
                "items": items,
                "footers": [],
            },
        ],
    }


def render_canvas(model, template=None):
    if template is None:
        with open(TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("community template must contain the data placeholder once")
    return template.replace(PLACEHOLDER, report_page.embed_json(model), 1)


def write_page(model, canvas_path, model_path=None):
    source = render_canvas(model)
    if not source.endswith("\n"):
        source += "\n"
    folder = os.path.dirname(canvas_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(canvas_path, "w", encoding="utf-8") as fh:
        fh.write(source)
    if model_path:
        model_folder = os.path.dirname(model_path)
        if model_folder:
            os.makedirs(model_folder, exist_ok=True)
        with open(model_path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    return source


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fill the Community Honor Roll from the global list.")
    parser.add_argument("--global", dest="global_path", required=True, help="global_neighbours.neighbours")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    entries = load_entries(args.global_path)
    if entries is None:
        print(json.dumps({
            "send": False,
            "reason": "No community list is saved yet.",
        }, ensure_ascii=False))
        return
    if not entries:
        print(json.dumps({
            "send": False,
            "reason": "The community list is empty.",
        }, ensure_ascii=False))
        return
    model = build_model(entries)
    os.makedirs(args.out, exist_ok=True)
    canvas_path = os.path.join(args.out, "community.canvas.tsx")
    model_path = os.path.join(args.out, "community_page.json")
    write_page(model, canvas_path, model_path)
    print(json.dumps({
        "send": True,
        "page_title": model["title"],
        "headline": model["headline"],
        "page_canvas": canvas_path,
        "page_model": model_path,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
