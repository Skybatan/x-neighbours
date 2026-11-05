#!/usr/bin/env python3
"""Build a prefilled GitHub issue link. It does not create the issue.

  python3 feedback_link.py --title "Catch up skipped a post" --body "..."

The owner opens the URL and submits it. Keep the draft free of handles,
names, post text, the good neighbours list, and tokens. The full URL stays
under 7500 characters, which fits GitHub and common browsers.
"""
import argparse
import json
import re
import sys
import urllib.parse


REPO = "https://github.com/Skybatan/x-neighbours/issues/new"
MAX_URL = 7500
MAX_TITLE = 120
HANDLE = re.compile(r"@[A-Za-z0-9_]{1,15}\b")
SECRET = re.compile(
    r"(?i)\b(bearer|api[_-]?key|access[_-]?token|password|secret)\b\s*[:=]\s*\S+"
    r"|\b(ghp_|github_pat_|xox[baprs]-|sk-)[A-Za-z0-9_\-]{8,}"
)


def looks_personal(text):
    if HANDLE.search(text or ""):
        return "a handle (@name)"
    if SECRET.search(text or ""):
        return "a token or secret"
    return None


def clip(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    return text[: limit - 1].rstrip() + "…", True


def build_url(title, body):
    title, title_cut = clip(title, MAX_TITLE)
    note = "\n\n(shortened to fit the link)"

    def link(current):
        query = urllib.parse.urlencode(
            {"title": title, "body": current, "labels": "feedback"},
            quote_via=urllib.parse.quote,
        )
        return f"{REPO}?{query}"

    shortened = title_cut
    current = body.strip()
    url = link(current)
    if len(url) > MAX_URL:
        shortened = True
        lo, hi = 0, len(current)
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            trial = current[:mid].rstrip() + note
            if len(link(trial)) <= MAX_URL:
                best = trial
                lo = mid + 1
            else:
                hi = mid - 1
        current = best or note.strip()
        url = link(current)
    return {
        "ok": True,
        "url": url,
        "title": title,
        "body": current,
        "shortened": shortened,
        "chars": len(url),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Print a prefilled GitHub new-issue URL. Does not post the issue."
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    args = parser.parse_args()
    title = args.title.strip()
    body = args.body.strip()
    if not title or not body:
        print(json.dumps({"ok": False, "error": "Title and body are both required."}))
        return 1
    problem = looks_personal(title) or looks_personal(body)
    if problem:
        print(json.dumps({
            "ok": False,
            "error": f"The draft looks like it contains {problem}. "
                     "Rewrite it with no handles, names, post text, lists, or tokens.",
        }))
        return 1
    print(json.dumps(build_url(title, body), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
