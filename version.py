#!/usr/bin/env python3
"""Read the X Neighbours version, and run the Monday update check.

The number is the single line in VERSION, next to this file. Code and docs
read that file. Do not copy the number into another module.

The Monday check compares versions/latest.json with that number for every
bot. It asks before any upgrade and never runs git. Community mode is not
required. The global list stays in community.py.

  python3 version.py
  python3 version.py --plan --repo .
  python3 version.py --check --latest FILE --state PATH --now ISO [--force]
  python3 version.py --decide no --version X --state PATH --now ISO
  python3 version.py --notes OLD NEW
  python3 version.py --notes VERSION
  python3 version.py --bridge --state PATH
  python3 version.py --ack --state PATH
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import rules


ROOT = os.path.dirname(os.path.abspath(__file__))
SEMVER_NOTE = "version must be major.minor.patch"

UPGRADE_STEPS = [
    "git pull --ff-only",
    "python3 version.py",
    "python3 version.py --notes <old> <new>",
    "Show those bullets to the owner.",
    "python3 version.py --ack --state <state path>",
    "Keep config.json, data/, good_neighbours.json, state.json, community.json, and global_neighbours.neighbours.",
]
PAUSED_ROUTINES = (
    "If the owner has paused their scheduled routines, keep those routines paused. "
    "Do not unpause them, and do not add a new scheduled Monday check without asking."
)
PIP_STEP = "python3 -m pip install -r requirements.txt"
PIP_WHEN_CHANGED = "If requirements.txt changed, run python3 -m pip install -r requirements.txt."
OWNER_LINE = "I removed the daily update and added a Monday check that asks before upgrading."
SUMMARY_LIMIT = 3


def version(path=None):
    if path is None:
        path = os.path.join(ROOT, "VERSION")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = text[:-1] if text.endswith("\n") else text
    if not body or "\n" in body or body != body.strip() or not _semver_text(body):
        raise ValueError("VERSION must be a single major.minor.patch line")
    return body


def _semver_text(text):
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", text or ""))


def parse_semver(text):
    """major.minor.patch as a tuple. A leading v, or any other text, is refused."""
    body = (text or "").strip()
    if not _semver_text(body):
        raise ValueError(SEMVER_NOTE)
    return tuple(int(part) for part in body.split("."))


def is_newer(remote, local):
    """True when the remote version is a higher major.minor.patch than local."""
    return parse_semver(remote) > parse_semver(local)


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def on_monday(now=None):
    """True when now is a Monday in UTC. Blank now uses the current UTC time."""
    when = datetime.now(timezone.utc) if not now else rules.parse_time(now)
    return when.weekday() == 0


def week_key(value):
    when = value if isinstance(value, datetime) else rules.parse_time(value)
    iso = when.isocalendar()
    return (iso[0], iso[1])


def load_state(path):
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError("state file must be an object")
    return doc


def save_state(path, doc):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return doc


def update_plan(branch="main"):
    """Where to read versions/latest.json. Every bot. Never the global list."""
    chosen = rules.safe_branch(branch) or "main"
    return {
        "branch": chosen,
        "fetch_versions": True,
        "fetch_global": False,
        "versions_url": rules.raw_file_url(chosen, rules.LATEST_REL),
        "pull": False,
        "upgrade": False,
    }


def summary_lines(latest, limit=SUMMARY_LIMIT):
    """Up to three short lines for the yes/no card. Notes win over the changelog."""
    lines = []
    notes = latest.get("release_notes") if isinstance(latest, dict) else None
    if isinstance(notes, list):
        for item in notes:
            text = str(item).strip()
            if text:
                lines.append(text)
    if not lines and isinstance(latest, dict):
        changelog = str(latest.get("changelog") or "").strip()
        if changelog:
            lines.append(changelog)
    return lines[:limit]


def _quiet(reason):
    return {
        "ok": reason != "not Monday",
        "check": False,
        "ask": False,
        "upgrade": False,
        "pull": False,
        "executed": False,
        "read_versions": False,
        "newer": False,
        "declined": False,
        "behind_minimum": False,
        "summary": [],
        "message": "",
        "reason": reason,
    }


def check_weekly(local_version, latest, declined_version=None, declined_on=None, now=None, force=False):
    """Compare a versions/latest.json object with the local version.

    Community mode is not consulted. upgrade and pull stay false until the
    owner agrees. On a UTC day other than Monday the latest object is not read,
    unless force is set (the owner asked to check today).
    """
    if not force and not on_monday(now):
        refused = _quiet("not Monday")
        refused["ok"] = False
        return refused
    if not isinstance(latest, dict) or not latest.get("version"):
        return {
            "ok": False,
            "check": True,
            "ask": False,
            "upgrade": False,
            "pull": False,
            "executed": False,
            "read_versions": True,
            "error": "versions/latest.json has no version",
        }
    remote = str(latest["version"])
    minimum = str(latest.get("min_compatible_version") or remote)
    try:
        remote_parts = parse_semver(remote)
        local_parts = parse_semver(local_version)
        minimum_parts = parse_semver(minimum)
    except ValueError as exc:
        return {
            "ok": False,
            "check": True,
            "read_versions": True,
            "ask": False,
            "upgrade": False,
            "pull": False,
            "executed": False,
            "error": str(exc),
        }
    newer = remote_parts > local_parts
    behind = minimum_parts > local_parts
    same_offer = declined_version and str(declined_version) == remote
    declined = False
    when = now or datetime.now(timezone.utc)
    if same_offer and not force and declined_on:
        declined = week_key(declined_on) == week_key(when)
    ask = bool(newer and not declined)
    summary = []
    message = ""
    if ask:
        if behind:
            summary.append(
                f"This bot is below the minimum compatible version {minimum}."
            )
        room = SUMMARY_LIMIT - len(summary)
        if room > 0:
            summary.extend(summary_lines(latest, limit=room))
        message = "\n".join(
            [f"Version {remote} is out.", *summary, "Upgrade?"]
        )
    elif newer and same_offer and not force:
        message = (
            f"You already said no to version {remote} this week. "
            "I will ask again next week."
        )
        declined = True
    return {
        "ok": True,
        "check": True,
        "read_versions": True,
        "ask": ask,
        "upgrade": False,
        "pull": False,
        "executed": False,
        "remote_version": remote,
        "local_version": local_version,
        "newer": newer,
        "declined": bool(declined),
        "behind_minimum": behind,
        "summary": summary,
        "changelog": latest.get("changelog") or "",
        "message": message,
        "reason": "",
    }


def apply_check(latest, path=None, now=None, force=False, local_version=None):
    state = load_state(path) if path else {}
    local = local_version or version()
    return check_weekly(
        local,
        latest,
        declined_version=state.get("declined_version"),
        declined_on=state.get("declined_on"),
        now=now,
        force=force,
    )


def upgrade_steps(requirements_changed=None):
    """Pull steps. pip install is included only when requirements.txt changed.

    None leaves a conditional line, for a caller that has not looked yet.
    This never runs the commands.
    """
    steps = list(UPGRADE_STEPS)
    if requirements_changed is True:
        steps.insert(1, PIP_STEP)
    elif requirements_changed is None:
        steps.insert(1, PIP_WHEN_CHANGED)
    return steps


def decide_upgrade(answer, remote_version, requirements_changed=None):
    """Record the owner's answer. This never runs git."""
    agreed = str(answer or "").strip().lower() in ("yes", "y", "upgrade")
    if not agreed:
        return {
            "ok": True,
            "upgrade": False,
            "pull": False,
            "executed": False,
            "declined_version": remote_version,
            "ask_again": "next week",
        }
    return {
        "ok": True,
        "upgrade": True,
        "pull": True,
        "executed": False,
        "version": remote_version,
        "steps": upgrade_steps(requirements_changed),
    }


def apply_decision(path, answer, remote_version, now=None, requirements_changed=None):
    result = decide_upgrade(answer, remote_version, requirements_changed)
    state = load_state(path)
    if result.get("declined_version"):
        state["declined_version"] = result["declined_version"]
        when = now or datetime.now(timezone.utc)
        state["declined_on"] = rules.iso(when)
    elif result.get("upgrade"):
        state["declined_version"] = None
        state["declined_on"] = None
    save_state(path, state)
    return result


def note_lines(doc):
    lines = []
    notes = doc.get("release_notes") if isinstance(doc, dict) else None
    if isinstance(notes, list):
        for item in notes:
            text = str(item).strip()
            if text:
                lines.append(text)
    if lines:
        return lines
    changelog = str(doc.get("changelog") or "").strip() if isinstance(doc, dict) else ""
    return [changelog] if changelog else []


def load_catalog(repo=None):
    """The single release file, versions/latest.json. Older copies are not read."""
    path = os.path.join(repo or ROOT, "versions", "latest.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        return []
    try:
        parse_semver(str(doc.get("version") or ""))
    except ValueError:
        return []
    return [doc]


def notes_between(catalog, old, new):
    """Release notes for versions after old, up to and including new.

    old None means only new. The result is (version, lines) pairs, oldest first.
    """
    new_parts = parse_semver(new)
    old_parts = parse_semver(old) if old else None
    groups = []
    for doc in catalog:
        number = str(doc.get("version") or "")
        try:
            parts = parse_semver(number)
        except ValueError:
            continue
        if parts > new_parts:
            continue
        if old_parts is None:
            if parts != new_parts:
                continue
        elif not (old_parts < parts <= new_parts):
            continue
        lines = note_lines(doc)
        if lines:
            groups.append((number, lines))
    return groups


def format_notes(groups):
    blocks = []
    for number, lines in groups:
        body = "\n".join("- " + line for line in lines)
        blocks.append(number + "\n" + body if body else number)
    return "\n\n".join(blocks)


def format_range(repo, old, new):
    groups = notes_between(load_catalog(repo), old, new)
    return format_notes(groups), groups


def needs_routine_update(recorded, had_report, current):
    """True when this bot still has the v2 daily pull layout."""
    if not recorded and had_report:
        return True
    if not recorded:
        return False
    try:
        return parse_semver(recorded)[0] < parse_semver(current)[0]
    except ValueError:
        return False


def evaluate_bridge(state, current, catalog):
    """Decide whether this run should show release notes once.

    A new bot has no report clock and no recorded version. A v2 bot has a
    report clock and no bot_version. Notes already shown for current stay hidden.
    """
    state = state or {}
    recorded = str(state.get("bot_version") or "").strip() or None
    shown = str(state.get("notes_shown_for") or "").strip() or None
    had_report = bool(state.get("last_report_at"))
    result = {
        "ok": True,
        "show": False,
        "update_routines": False,
        "owner_line": "",
        "notes": [],
        "text": "",
        "from_version": recorded or "",
        "bot_version": current,
        "reason": "",
        "paused_routines": PAUSED_ROUTINES,
    }
    if shown == current:
        result["reason"] = "already shown"
        return result
    if recorded == current:
        result["reason"] = "already on this version"
        return result
    if not recorded and not had_report:
        result["reason"] = "new bot"
        result["write"] = {"bot_version": current, "notes_shown_for": current}
        return result
    if recorded:
        try:
            if not (parse_semver(recorded) < parse_semver(current)):
                result["reason"] = "not an upgrade"
                return result
        except ValueError:
            result["reason"] = "bad recorded version"
            return result
    groups = notes_between(catalog, recorded, current) if recorded else notes_between(catalog, None, current)
    notes = [line for _number, lines in groups for line in lines]
    update = needs_routine_update(recorded, had_report, current)
    result.update({
        "show": True,
        "update_routines": update,
        "owner_line": OWNER_LINE if update else "",
        "notes": notes,
        "text": format_notes(groups),
        "reason": "upgraded",
        "write": {"bot_version": current, "notes_shown_for": current},
    })
    return result


def apply_bridge(path, current=None, repo=None):
    current = current or version()
    state = load_state(path)
    result = evaluate_bridge(state, current, load_catalog(repo or ROOT))
    write = result.pop("write", None)
    if write:
        state.update(write)
        save_state(path, state)
    return result


def ack(path, current=None):
    """Remember that the owner has seen the notes for the running version."""
    current = current or version()
    state = load_state(path)
    state["bot_version"] = current
    state["notes_shown_for"] = current
    save_state(path, state)
    return {"ok": True, "show": False, "bot_version": current, "notes_shown_for": current}


def _local_version(path):
    if path and os.path.isfile(path):
        return version(path)
    if path:
        text = str(path).strip()
        parse_semver(text)
        return text
    return version()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the version, or run the Monday update check.")
    parser.add_argument("--notes", nargs="+", metavar="VERSION", help="print release notes for one version, or from old to new")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--latest", help="path to a downloaded versions/latest.json")
    parser.add_argument("--state", help="path to state.json in the bot store")
    parser.add_argument("--now", default="", help="UTC time for the Monday guard")
    parser.add_argument("--force", action="store_true", help="check on a day other than Monday")
    parser.add_argument("--local", help="version string or path to a VERSION file")
    parser.add_argument("--decide", default="", help="yes or no")
    parser.add_argument(
        "--version", nargs="?", const="", default="",
        help="remote version for --decide; alone, print the local version",
    )
    parser.add_argument("--requirements-changed", choices=("yes", "no", "auto"), default="auto")
    parser.add_argument("--bridge", action="store_true")
    parser.add_argument("--ack", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--repo", default="")
    parser.add_argument("--base", default="", help="branch for the versions URL")
    parser.add_argument("--config", default="", help="config.json; share_branch overrides the checkout")
    args = parser.parse_args(argv)
    actions = [bool(args.notes), args.check, bool(args.decide), args.bridge, args.ack, args.plan]
    if sum(actions) > 1:
        emit({"ok": False, "error": "pass one of --notes, --check, --decide, --bridge, --ack, --plan"})
        return 1
    if not any(actions):
        if args.version:
            emit({"ok": False, "error": "pass --decide with --version"})
            return 1
        try:
            print(version())
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    try:
        return _run(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


def _run(args):
    repo = args.repo or ROOT
    now = args.now or None
    if args.plan:
        branch = rules.resolve_branch(
            args.base, rules.share_branch_from_config(args.config), args.repo or ".")
        emit({"ok": True, **update_plan(branch)})
        return 0
    if args.notes is not None:
        if len(args.notes) == 1:
            old, new = None, args.notes[0]
        elif len(args.notes) == 2:
            old, new = args.notes
        else:
            emit({"ok": False, "error": "--notes takes one version, or an old version and a new one"})
            return 1
        text, _groups = format_range(repo, old, new)
        if text:
            print(text)
        return 0
    if args.bridge:
        if not args.state:
            emit({"ok": False, "error": "pass --state"})
            return 1
        emit(apply_bridge(args.state, repo=repo))
        return 0
    if args.ack:
        if not args.state:
            emit({"ok": False, "error": "pass --state"})
            return 1
        emit(ack(args.state))
        return 0
    if args.decide:
        if not args.version or not args.state:
            emit({"ok": False, "error": "pass --version and --state"})
            return 1
        requirements = {"yes": True, "no": False}.get(args.requirements_changed)
        emit(apply_decision(
            args.state, args.decide, args.version, now=now, requirements_changed=requirements))
        return 0
    if not args.force and not on_monday(now):
        emit(_quiet("not Monday"))
        return 1
    if not args.latest:
        emit({"ok": False, "error": "pass --latest"})
        return 1
    with open(args.latest, encoding="utf-8") as fh:
        latest = json.load(fh)
    local = _local_version(args.local) if args.local else None
    result = apply_check(latest, path=args.state, now=now, force=args.force, local_version=local)
    emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
