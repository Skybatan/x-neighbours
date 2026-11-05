#!/usr/bin/env python3
"""Read and update the last-report clock in the bot's store.

The file lives next to good_neighbours.json, outside the repo. The bot uses
`check` before an idle greeting, and `x_neighbours.py --state` writes it
after a report. Do not hand-edit the JSON.

  python3 report_state.py --file PATH check [--now ISO] [--hours N]
  python3 report_state.py --file PATH show
  python3 report_state.py --file PATH record --at ISO --since ISO --until ISO \
      --replies N --quotes N --likes N --reposts N [--hours N]

Freshness, from replies + quote posts + likes + reposts scaled to 24 hours:

  60 or more   big account      ask again after 1 hour
  15 to 59     medium account   ask again after 3 hours
  under 15     small account    ask again after 8 hours

`--hours` or config `fresh_hours` replaces that estimate.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone


BIG_PER_DAY = 60
MEDIUM_PER_DAY = 15
BIG_HOURS = 1
MEDIUM_HOURS = 3
SMALL_HOURS = 8
MAX_FRESH_SPAN = timedelta(days=7)


def parse_time(value):
    when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def iso(when):
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def activity_per_day(replies, quotes, likes, reposts, hours):
    span = max(float(hours), 1 / 60)
    return (replies + quotes + likes + reposts) * 24 / span


def hours_for(per_day, override=None):
    if override not in (None, "", 0):
        hours = float(override)
        if hours <= 0:
            raise SystemExit("fresh hours must be greater than 0")
        return hours
    if per_day >= BIG_PER_DAY:
        return BIG_HOURS
    if per_day >= MEDIUM_PER_DAY:
        return MEDIUM_HOURS
    return SMALL_HOURS


def load(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or not doc.get("last_report_at"):
        return None
    return doc


def save(path, doc):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def age_label(hours):
    if hours < 1:
        minutes = max(1, int(round(hours * 60)))
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    if hours < 48:
        rounded = max(1, int(round(hours)))
        unit = "hour" if rounded == 1 else "hours"
        return f"{rounded} {unit} ago"
    days = max(2, int(round(hours / 24)))
    return f"{days} days ago"


def record(path, at, since, until, replies, quotes, likes, reposts, override=None):
    at = at if isinstance(at, datetime) else parse_time(at)
    since = since if isinstance(since, datetime) else parse_time(since)
    until = until if isinstance(until, datetime) else parse_time(until)
    span_hours = max((until - since).total_seconds() / 3600, 1 / 60)
    per_day = activity_per_day(replies, quotes, likes, reposts, span_hours)
    fresh = hours_for(per_day, override)
    doc = {
        "version": 1,
        "last_report_at": iso(at),
        "since": iso(since),
        "until": iso(until),
        "replies": int(replies),
        "quotes": int(quotes),
        "likes": int(likes),
        "reposts": int(reposts),
        "activity_per_day": round(per_day, 1),
        "fresh_hours": fresh,
    }
    save(path, doc)
    return doc


def check(path, now=None, override=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        now = parse_time(now)
    doc = load(path)
    if not doc:
        since = now - timedelta(hours=24)
        return {
            "ok": True,
            "ask": True,
            "has_report": False,
            "question": "No report yet. Want one for the last 24 hours?",
            "yes_no": True,
            "fetch_since": iso(since),
            "clamped_to_7d": False,
            "fresh_hours": hours_for(0, override),
        }
    at = parse_time(doc["last_report_at"])
    age = max(0, (now - at).total_seconds() / 3600)
    per_day = float(doc.get("activity_per_day") or 0)
    fresh = hours_for(per_day, override if override not in (None, "") else None)
    until = parse_time(doc.get("until") or doc["last_report_at"])
    earliest = now - MAX_FRESH_SPAN
    clamped = until < earliest
    fetch_since = earliest if clamped else until
    label = age_label(age)
    ask = age >= fresh
    question = f"Your last report was {label}. Want a fresh one?" if ask else None
    return {
        "ok": True,
        "ask": ask,
        "has_report": True,
        "age_hours": round(age, 2),
        "age_label": label,
        "activity_per_day": per_day,
        "fresh_hours": fresh,
        "question": question,
        "yes_no": True,
        "fetch_since": iso(fetch_since),
        "clamped_to_7d": clamped,
        "last_report_at": doc["last_report_at"],
    }


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Read or update the report freshness clock.")
    parser.add_argument("--file", required=True, help="path to state.json in the bot store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check_cmd = sub.add_parser("check", help="say whether to offer a fresh report")
    check_cmd.add_argument("--now", help="UTC ISO time (default: now)")
    check_cmd.add_argument("--hours", type=float, help="owner override for the freshness interval")
    sub.add_parser("show", help="print the saved state")
    rec = sub.add_parser("record", help="save a report that just finished")
    rec.add_argument("--at", required=True)
    rec.add_argument("--since", required=True)
    rec.add_argument("--until", required=True)
    rec.add_argument("--replies", type=int, default=0)
    rec.add_argument("--quotes", type=int, default=0)
    rec.add_argument("--likes", type=int, default=0)
    rec.add_argument("--reposts", type=int, default=0)
    rec.add_argument("--hours", type=float, help="owner override for the freshness interval")
    args = parser.parse_args()
    try:
        if args.cmd == "show":
            doc = load(args.file) or {"version": 1}
            emit(doc)
            return 0
        if args.cmd == "check":
            emit(check(args.file, now=args.now, override=args.hours))
            return 0
        doc = record(
            args.file, at=args.at, since=args.since, until=args.until,
            replies=args.replies, quotes=args.quotes, likes=args.likes,
            reposts=args.reposts, override=args.hours)
        emit(doc)
        return 0
    except json.JSONDecodeError as exc:
        emit({"ok": False, "error": f"{args.file} is not JSON ({exc})"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
