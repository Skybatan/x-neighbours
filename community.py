#!/usr/bin/env python3
"""Opt-in community mode for one owner's bot.

The flag lives in the bot store, next to good_neighbours.json. It is never
committed. Individual mode is the default: no global list, no share, no
picture-tag reminder. The Monday version check for every bot lives in
version.py. check-update here still does nothing unless community mode is on.

  python3 community.py --file PATH status
  python3 community.py --file PATH offer
  python3 community.py --file PATH join --now ISO
  python3 community.py --file PATH leave --now ISO
  python3 community.py --file PATH picture-tag --handle HANDLE --text "thank-you sentence"
  python3 community.py --file PATH sunday --now ISO [--last-share ISO] [--timezone NAME]
  python3 community.py --file PATH check-update --latest FILE [--force]
  python3 community.py --file PATH decide-upgrade --answer yes|no --version X
  python3 community.py --file PATH save-global --src FILE [--weekly]
  python3 community.py --file PATH plan

check-update and save-global do nothing in individual mode, and they do not
open versions/ or the global file in that mode. decide-upgrade never runs
git pull. The bot runs the steps only after the owner says yes.
"""
import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone

import rules
import version as version_mod


JOIN_PROMPT = (
    "Community mode is optional. If you join, this bot can download a public "
    "recommendations list and can help you share neighbours who already "
    "talk with you. It still does not post or follow anyone. Your private "
    "reports stay on this bot either way. The Monday update check already "
    "runs either way. Join the community?"
)
PICTURE_REMINDER = (
    f"When you post this picture, include @{rules.PICTURE_TAG} so it can be "
    "reposted. This bot does not post it for you."
)
UPGRADE_STEPS = [
    "git pull --ff-only",
    "python3 version.py",
    "Read CHANGELOG.md when the version line changed.",
    "Keep config.json, data/, good_neighbours.json, state.json, community.json, and global_neighbours.neighbours.",
]
PIP_STEP = "python3 -m pip install -r requirements.txt"
PIP_WHEN_CHANGED = "If requirements.txt changed, run python3 -m pip install -r requirements.txt."


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def blank():
    return {
        "community": False,
        "offered": False,
        "joined_at": None,
        "left_at": None,
        "declined_version": None,
        "pending_pr": None,
        "last_submitted_at": None,
        "share_state": None,
        "global_source_commit": None,
    }


def load(path):
    state = blank()
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if isinstance(doc, dict):
            state.update({key: doc.get(key, state[key]) for key in state})
    state["community"] = bool(state.get("community"))
    state["offered"] = bool(state.get("offered"))
    return state


def save(path, state):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return state


def iso_now(value=None):
    if value:
        return rules.iso(value)
    return rules.iso(datetime.now(timezone.utc))


def offer(path):
    state = load(path)
    if state["community"]:
        return {"ok": True, "offer": False, "reason": "already joined", "community": True}
    if state["offered"]:
        return {"ok": True, "offer": False, "reason": "already offered", "community": False}
    state["offered"] = True
    save(path, state)
    return {"ok": True, "offer": True, "community": False, "prompt": JOIN_PROMPT}


def join(path, now):
    state = load(path)
    state["community"] = True
    state["offered"] = True
    state["joined_at"] = iso_now(now)
    state["left_at"] = None
    save(path, state)
    return {"ok": True, "community": True, "joined_at": state["joined_at"]}


def leave(path, now):
    state = load(path)
    state["community"] = False
    state["left_at"] = iso_now(now)
    save(path, state)
    return {
        "ok": True,
        "community": False,
        "left_at": state["left_at"],
        "shared_lists": "stay until an opt-out",
    }


def posting_is_tag_account(handle):
    return str(handle or "").lstrip("@").lower() == rules.PICTURE_TAG.lower()


def picture_tag(community_on, handle, thank_you_text=""):
    """Reminder and optional composer prefill. Individual mode stays silent."""
    if not community_on or posting_is_tag_account(handle):
        reason = "individual" if not community_on else "posting account"
        return {
            "remind": False,
            "text": "",
            "prefill": None,
            "intent": None,
            "reason": reason,
        }
    intent = None
    if thank_you_text:
        composed = thank_you_text.rstrip() + f" @{rules.PICTURE_TAG}"
        intent = "https://x.com/intent/post?text=" + urllib.parse.quote(composed)
    return {
        "remind": True,
        "text": PICTURE_REMINDER,
        "prefill": f"@{rules.PICTURE_TAG}",
        "intent": intent,
        "reason": "",
    }


def sunday_message(community_on, now, last_submitted_at=None, zone_name=""):
    """Sunday invite. Sharing has no cooldown, so a recent file does not delay it.

    `now`, `last_submitted_at`, and `zone_name` stay in the signature so an
    older caller can still pass them. They do not block the invite.
    """
    _ = (now, last_submitted_at, zone_name)
    if not community_on:
        return {"ok": True, "remind": False, "reason": "individual"}
    release = "A feature release may land on Monday."
    text = (
        "You can share your eligible neighbours whenever you want. "
        + release
        + " Say if you want to share."
    )
    return {
        "ok": True,
        "remind": True,
        "can_share": True,
        "next_allowed_at": None,
        "text": text,
    }


def weekly_plan(community_on, branch="main"):
    """What a Monday check may touch. Individual mode fetches nothing.

    branch is the git branch for the raw file URLs. main is the default.
    Pass v3, or the name from resolve_branch, when this clone is not on main.
    """
    chosen = rules.safe_branch(branch) or "main"
    if not community_on:
        return {
            "mode": "individual",
            "branch": chosen,
            "fetch_versions": False,
            "fetch_global": False,
            "ask": False,
            "upgrade": False,
            "pull": False,
            "save_global": False,
        }
    return {
        "mode": "community",
        "branch": chosen,
        "fetch_versions": True,
        "fetch_global": True,
        "versions_url": rules.raw_file_url(chosen, rules.LATEST_REL),
        "global_url": rules.raw_file_url(chosen, rules.GLOBAL_REL),
        "ask": False,
        "upgrade": False,
        "pull": False,
        "save_global": False,
    }


def on_monday(now=None):
    """True when now is a Monday in UTC. Blank now uses the current UTC time."""
    when = datetime.now(timezone.utc) if not now else rules.parse_time(now)
    return when.weekday() == 0


def check_update(community_on, local_version, latest, declined_version=None, force=False):
    """Compare a versions/latest.json object with the local version.

    latest is ignored in individual mode, so the caller need not read the file.
    upgrade and pull stay false until the owner agrees.
    """
    if not community_on:
        return {
            "ok": True,
            "mode": "individual",
            "check": False,
            "ask": False,
            "upgrade": False,
            "pull": False,
            "read_versions": False,
        }
    if not isinstance(latest, dict) or not latest.get("version"):
        return {"ok": False, "check": True, "ask": False, "upgrade": False, "pull": False,
                "error": "versions/latest.json has no version"}
    remote = str(latest["version"])
    minimum = str(latest.get("min_compatible_version") or remote)
    try:
        remote_parts = version_mod.parse_semver(remote)
        local_parts = version_mod.parse_semver(local_version)
        minimum_parts = version_mod.parse_semver(minimum)
    except ValueError as exc:
        return {
            "ok": False,
            "mode": "community",
            "check": True,
            "read_versions": True,
            "ask": False,
            "upgrade": False,
            "pull": False,
            "executed": False,
            "error": str(exc),
        }
    newer = remote_parts > local_parts
    declined = (not force) and declined_version and str(declined_version) == remote
    ask = bool(newer and not declined)
    behind = minimum_parts > local_parts
    message = ""
    if ask:
        message = f"Version {remote} is out. {latest.get('changelog') or ''} Upgrade?"
        if behind:
            message = (
                f"Version {remote} is out and this bot is below the minimum compatible "
                f"version {minimum}. {latest.get('changelog') or ''} Upgrade?"
            )
    elif newer and declined:
        message = "You already declined this version. I will ask again next week, or if you ask."
    return {
        "ok": True,
        "mode": "community",
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
        "changelog": latest.get("changelog") or "",
        "source_commit": latest.get("source_commit") or "",
        "message": " ".join(message.split()),
    }


def upgrade_steps(requirements_changed=None):
    """Pull steps. pip install is included only when requirements.txt changed.

    None leaves a conditional line, for a caller that has not looked yet.
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
            "ask_again": "next weekly check",
        }
    return {
        "ok": True,
        "upgrade": True,
        "pull": True,
        "executed": False,
        "version": remote_version,
        "steps": upgrade_steps(requirements_changed),
    }


def save_global(community_on, weekly, remote_doc, dest, previous_commit=None):
    """Write the global list into the bot store on the weekly community check."""
    if not community_on:
        return {"ok": True, "saved": False, "reason": "individual", "read_global": False}
    if not weekly:
        return {"ok": True, "saved": False, "reason": "mid-week", "read_global": False}
    if not isinstance(remote_doc, dict):
        return {"ok": False, "saved": False, "error": "global file is not an object"}
    remote_commit = str(remote_doc.get("source_commit") or "")
    if previous_commit is not None and remote_commit and previous_commit == remote_commit:
        if os.path.isfile(dest):
            return {
                "ok": True,
                "saved": False,
                "reason": "same commit",
                "source_commit": remote_commit,
                "path": dest,
            }
    write_needed = True
    if os.path.isfile(dest) and remote_commit:
        try:
            with open(dest, encoding="utf-8") as fh:
                local = json.load(fh)
        except (OSError, json.JSONDecodeError):
            local = {}
        if isinstance(local, dict) and str(local.get("source_commit") or "") == remote_commit:
            write_needed = False
    if not write_needed:
        return {
            "ok": True,
            "saved": False,
            "reason": "same commit",
            "source_commit": remote_commit,
            "path": dest,
        }
    folder = os.path.dirname(os.path.abspath(dest))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(remote_doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return {
        "ok": True,
        "saved": True,
        "path": dest,
        "source_commit": remote_commit,
        "read_global": True,
    }


def record_share(path, submitted_at, pending_url=""):
    state = load(path)
    state["last_submitted_at"] = rules.iso(submitted_at)
    state["share_state"] = "open" if pending_url else "prepared"
    state["pending_pr"] = pending_url or None
    save(path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description="Community mode for this bot.")
    parser.add_argument("--file", required=True, help="path to community.json in the bot store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("offer")
    planned = sub.add_parser("plan")
    planned.add_argument("--base", default="", help="branch for the raw URLs; default is the checkout, then main")
    planned.add_argument("--config", default="", help="config.json; share_branch overrides the checkout")
    planned.add_argument("--repo", default=".")
    joined = sub.add_parser("join")
    joined.add_argument("--now")
    left = sub.add_parser("leave")
    left.add_argument("--now")
    tag = sub.add_parser("picture-tag")
    tag.add_argument("--handle", default="")
    tag.add_argument("--text", default="")
    sunday = sub.add_parser("sunday")
    sunday.add_argument("--now", required=True)
    sunday.add_argument("--last-share", default="")
    sunday.add_argument("--timezone", default="")
    check = sub.add_parser("check-update")
    check.add_argument("--latest", help="path to versions/latest.json")
    check.add_argument("--local", help="defaults to the VERSION file")
    check.add_argument("--now", default="", help="UTC time for the Monday guard")
    check.add_argument("--force", action="store_true", help="run the check on a day other than Monday")
    decide = sub.add_parser("decide-upgrade")
    decide.add_argument("--answer", required=True)
    decide.add_argument("--version", required=True)
    decide.add_argument(
        "--requirements-changed", choices=("yes", "no", "auto"), default="auto",
        help="include pip install only when requirements.txt changed",
    )
    save_cmd = sub.add_parser("save-global")
    save_cmd.add_argument("--src", required=True)
    save_cmd.add_argument("--dest", default="")
    save_cmd.add_argument("--weekly", action="store_true")
    save_cmd.add_argument("--now", default="", help="UTC time for the Monday guard")
    save_cmd.add_argument("--force", action="store_true", help="save on a day other than Monday")
    share_cmd = sub.add_parser("record-share")
    share_cmd.add_argument("--at", required=True)
    share_cmd.add_argument("--pending-url", default="")
    result_cmd = sub.add_parser("share-result")
    result_cmd.add_argument("--state", required=True, choices=("open", "merged", "rejected"))
    result_cmd.add_argument("--pending-url", default="")
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


def run(args):
    state = load(args.file) if args.cmd != "offer" else None
    if args.cmd == "status":
        emit({"ok": True, **load(args.file)})
        return 0
    if args.cmd == "offer":
        emit(offer(args.file))
        return 0
    if args.cmd == "plan":
        branch = rules.resolve_branch(
            args.base, rules.share_branch_from_config(args.config), args.repo)
        emit({"ok": True, **weekly_plan(load(args.file)["community"], branch)})
        return 0
    if args.cmd == "join":
        emit(join(args.file, args.now))
        return 0
    if args.cmd == "leave":
        emit(leave(args.file, args.now))
        return 0
    if args.cmd == "picture-tag":
        current = load(args.file)
        emit({"ok": True, **picture_tag(current["community"], args.handle, args.text)})
        return 0
    if args.cmd == "sunday":
        current = load(args.file)
        last = args.last_share or current.get("last_submitted_at")
        if current.get("share_state") == "rejected":
            last = None
        emit(sunday_message(current["community"], args.now, last, args.timezone))
        return 0
    if args.cmd == "check-update":
        current = load(args.file)
        if not current["community"]:
            emit(check_update(False, version_mod.version(), None))
            return 0
        if not args.force and not on_monday(args.now):
            emit({
                "ok": False,
                "check": False,
                "ask": False,
                "upgrade": False,
                "pull": False,
                "read_versions": False,
                "reason": "not Monday",
            })
            return 1
        if not args.latest:
            emit({"ok": False, "error": "pass --latest"})
            return 1
        with open(args.latest, encoding="utf-8") as fh:
            latest = json.load(fh)
        local = args.local or version_mod.version()
        if args.local and os.path.isfile(args.local):
            local = version_mod.version(args.local)
        result = check_update(
            True, local, latest, declined_version=current.get("declined_version"),
            force=args.force)
        emit(result)
        return 0 if result.get("ok") else 1
    if args.cmd == "decide-upgrade":
        requirements = {"yes": True, "no": False}.get(args.requirements_changed)
        result = decide_upgrade(args.answer, args.version, requirements_changed=requirements)
        if result.get("declined_version"):
            current = load(args.file)
            current["declined_version"] = result["declined_version"]
            save(args.file, current)
        elif result.get("upgrade"):
            current = load(args.file)
            current["declined_version"] = None
            save(args.file, current)
        emit(result)
        return 0
    if args.cmd == "save-global":
        current = load(args.file)
        dest = args.dest or os.path.join(os.path.dirname(os.path.abspath(args.file)), rules.LOCAL_GLOBAL_NAME)
        if current["community"] and args.weekly and not args.force and not on_monday(args.now):
            emit({
                "ok": False,
                "saved": False,
                "reason": "not Monday",
                "read_global": False,
            })
            return 1
        if not current["community"] or not args.weekly:
            emit(save_global(current["community"], args.weekly, None, dest))
            return 0
        with open(args.src, encoding="utf-8") as fh:
            remote = json.load(fh)
        result = save_global(
            True, True, remote, dest, previous_commit=current.get("global_source_commit"))
        if result.get("saved"):
            current["global_source_commit"] = result.get("source_commit")
            save(args.file, current)
        emit(result)
        return 0 if result.get("ok", True) else 1
    if args.cmd == "record-share":
        state = record_share(args.file, args.at, args.pending_url)
        emit({"ok": True, "last_submitted_at": state["last_submitted_at"], "pending_pr": state["pending_pr"]})
        return 0
    if args.cmd == "share-result":
        current = load(args.file)
        current["share_state"] = args.state
        if args.state == "rejected":
            current["pending_pr"] = None
            current["last_submitted_at"] = None
        elif args.pending_url:
            current["pending_pr"] = args.pending_url
        elif args.state == "merged":
            current["pending_pr"] = None
        save(args.file, current)
        emit({"ok": True, "share_state": current["share_state"], "pending_pr": current["pending_pr"]})
        return 0
    raise ValueError(f"unknown command {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
