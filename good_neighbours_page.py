#!/usr/bin/env python3
"""Render the Good Neighbours Newsletter.

This page is separate from the report. It shows the latest post to catch up
with for each person on the list, then the full list with profile links.
The add selector stays in the chat. A Page cannot record a choice.

  python3 good_neighbours_page.py --data data --user-id ID --good-neighbours PATH --out DIR
"""
import argparse
import json
import os
from datetime import datetime, timezone

import report_page
import x_neighbours as xn

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "templates", "good_neighbours.canvas.tsx")
PLACEHOLDER = "/*__PAGE_JSON__*/ null as unknown as NeighboursPage"

TITLE = xn.GOOD_NEIGHBOURS_NEWSLETTER
ADD_REMINDER = "Name someone to add to good neighbours, or say who to remove."
CAUGHT_UP = "You're all caught up with your good neighbours."
LATEST_EXPLAINER = (
    "A post from someone on your list that you have not liked, replied to, or reposted yet."
)
LIST_EXPLAINER = "Everyone you asked to keep up with. A name opens their profile."
INTRO = "Latest posts to catch up with, then everyone on your list."


def part(text, href=None):
    return {"text": text or "", "href": href or None}


def profile_url(username):
    username = (username or "").lstrip("@")
    if not username:
        return None
    return f"https://x.com/{username}"


def _people(neighbours):
    people = []
    for person in neighbours or []:
        if not isinstance(person, dict) or not person.get("username"):
            continue
        username = str(person["username"]).lstrip("@")
        if not username:
            continue
        people.append({
            "id": str(person.get("id") or ""),
            "username": username,
            "name": person.get("name") or username,
        })
    return people


def _age(created_at):
    if not created_at:
        return ""
    return " · " + xn.ago(xn.ts(created_at), xn.utc_now())


def build_model(neighbours, catch_up):
    """Page model. `catch_up` is the report's good-neighbour catch-up rows."""
    people = _people(neighbours)
    posts = []
    for person in catch_up or []:
        latest = person.get("latest") or {}
        username = (person.get("username") or "").lstrip("@")
        name = person.get("name") or username
        text = xn.snippet(latest.get("text")) or "Post"
        url = (person.get("latest_url") or "").strip() or None
        posts.append({
            "lines": [
                {"parts": [part(name, profile_url(username))]},
                {"parts": [part(f"“{text}”{_age(latest.get('created_at'))}", url)]},
            ],
        })
    listed = []
    for person in people:
        label = f"{person['name']} (@{person['username']})"
        listed.append({
            "lines": [{"parts": [part(label, profile_url(person["username"]))]}],
        })
    summary = (
        xn.counted(len(people), "person", "people")
        + " · "
        + xn.counted(len(posts), "post to catch up with", "posts to catch up with")
    )
    return {
        "title": TITLE,
        "summary": summary,
        "intro": INTRO,
        "headline": f"{TITLE} · {summary}",
        "sections": [
            {
                "heading": "Latest posts",
                "explainer": LATEST_EXPLAINER,
                "preface": None if posts else CAUGHT_UP,
                "items": posts,
                "footers": [],
            },
            {
                "heading": "Your list",
                "explainer": LIST_EXPLAINER,
                "preface": None,
                "items": listed,
                "footers": [],
            },
        ],
    }


def render_canvas(model, template=None):
    if template is None:
        with open(TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("good neighbours template must contain the data placeholder once")
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


def page_output(model, canvas_path, model_path):
    return {
        "send": True,
        "page_title": model["title"],
        "headline": model["headline"],
        "page_canvas": canvas_path,
        "page_model": model_path,
        "add_reminder": ADD_REMINDER,
    }


def catch_up_for(data, neighbours, now):
    """Latest unengaged original for each person on the list, in list order."""
    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    activity = xn.build_activity(
        data, since, now, 10, 1, 3, "both", now, good_neighbours=neighbours,
    )
    return activity["catch_up"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fill the Good Neighbours Newsletter.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--good-neighbours", required=True, dest="good_neighbours")
    parser.add_argument("--out", required=True)
    parser.add_argument("--now", help="UTC ISO time (default: now)")
    args = parser.parse_args(argv)
    neighbours = xn.load_good_neighbours(args.good_neighbours)
    if not neighbours:
        print(json.dumps({
            "send": False,
            "reason": "Your good neighbours list is empty.",
        }, ensure_ascii=False))
        return
    if not os.path.isdir(args.data):
        parser.error(f"data folder not found: {args.data}")
    now = xn.ts(args.now) if args.now else xn.utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    data = xn.Data(args.data, str(args.user_id))
    model = build_model(neighbours, catch_up_for(data, neighbours, now))
    os.makedirs(args.out, exist_ok=True)
    canvas_path = os.path.join(args.out, "good_neighbours.canvas.tsx")
    model_path = os.path.join(args.out, "good_neighbours_page.json")
    write_page(model, canvas_path, model_path)
    print(json.dumps(page_output(model, canvas_path, model_path), ensure_ascii=False))


if __name__ == "__main__":
    main()
