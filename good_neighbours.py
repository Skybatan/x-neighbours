#!/usr/bin/env python3
"""Add, remove, and list good neighbours in the bot's store JSON.

The file stays outside the repo. A missing file is an empty list. The list
holds at most 20 people. Adding someone who is already there changes nothing.

  python3 good_neighbours.py --file PATH add <handle|id> [--id ID] [--name NAME]
  python3 good_neighbours.py --file PATH remove <handle>
  python3 good_neighbours.py --file PATH list
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone


CAP = 20


def load(path):
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc.get("neighbours") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return []
    people = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("id") or not item.get("username"):
            continue
        people.append({
            "id": str(item["id"]),
            "username": str(item["username"]).lstrip("@"),
            "name": item.get("name") or str(item["username"]).lstrip("@"),
            "added": item.get("added") or "",
        })
        if len(people) >= CAP:
            break
    return people


def save(path, people):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    doc = {"version": 1, "neighbours": people[:CAP]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return doc


def same_person(person, user_id, username):
    if user_id and person["id"] == str(user_id):
        return True
    if username and person["username"].lower() == username.lower():
        return True
    return False


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def cmd_list(path):
    people = load(path)
    emit({"ok": True, "version": 1, "neighbours": people})
    return 0


def cmd_add(path, who, user_id, name):
    token = (who or "").strip().lstrip("@")
    if not token:
        emit({"ok": False, "error": "Pass a username or a numeric id."})
        return 1
    if user_id:
        username = token
        user_id = str(user_id)
    elif token.isdigit():
        username = None
        user_id = token
    else:
        username = token
        user_id = None
    people = load(path)
    found = next((person for person in people if same_person(person, user_id, username)), None)
    if found:
        emit({"ok": True, "already": True, "neighbour": found, "neighbours": people})
        return 0
    if not username or not user_id:
        emit({
            "ok": False,
            "error": "Need both a username and an id. Look the handle up, then pass --id.",
        })
        return 1
    if len(people) >= CAP:
        emit({"ok": False, "error": "The list is full (20). Remove someone first."})
        return 2
    person = {
        "id": str(user_id),
        "username": username,
        "name": name or username,
        "added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    people.append(person)
    save(path, people)
    emit({"ok": True, "already": False, "neighbour": person, "neighbours": people})
    return 0


def cmd_remove(path, handle):
    token = (handle or "").strip().lstrip("@")
    if not token:
        emit({"ok": False, "error": "Pass a username."})
        return 1
    people = load(path)
    kept = [person for person in people if not same_person(person, token if token.isdigit() else None, token)]
    removed = len(kept) != len(people)
    if removed:
        save(path, kept)
    emit({"ok": True, "removed": removed, "neighbours": kept})
    return 0


def main():
    parser = argparse.ArgumentParser(description="Edit the good neighbours list.")
    parser.add_argument("--file", required=True, help="path to good_neighbours.json")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add a person, or do nothing if they are already listed")
    add.add_argument("who", help="username, or a numeric id")
    add.add_argument("--id", help="numeric user id, when who is a username")
    add.add_argument("--name", help="display name")
    remove = sub.add_parser("remove", help="remove a person by username or id")
    remove.add_argument("handle")
    sub.add_parser("list", help="print the list")
    args = parser.parse_args()
    try:
        if args.cmd == "list":
            code = cmd_list(args.file)
        elif args.cmd == "add":
            code = cmd_add(args.file, args.who, args.id, args.name)
        else:
            code = cmd_remove(args.file, args.handle)
    except json.JSONDecodeError as exc:
        emit({"ok": False, "error": f"{args.file} is not JSON ({exc})"})
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
