#!/usr/bin/env python3
"""Rebuild global/neighbours.global.neighbours from every submission.

Every file under submissions/<user id>/ counts. When the same owner
recommends the same account in more than one file, that owner counts once.
An older file is not dropped when a later file leaves someone out. The one
path named by global/build.json founding_waiver.submission is also loaded.
Accounts in that file enter with one recommendation and source "founding".
Every other account needs min_recommendations (2). Opt-outs and banned
owners are applied after that.

This script does not read or write versions/. A mid-week rebuild must not
look like a Monday release.

  python3 global_build.py --repo . --out global/neighbours.global.neighbours \\
      --source-commit SHA --now 2026-11-25T00:00:00Z
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import rules
import share_submission as share


def load_doc(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_doc(path, doc):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def iter_submissions(repo):
    root = os.path.join(repo, "submissions")
    if not os.path.isdir(root):
        return
    for owner in sorted(os.listdir(root)):
        folder = os.path.join(root, owner)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".neighbours"):
                continue
            relpath = f"submissions/{owner}/{name}"
            yield relpath, os.path.join(folder, name)


def submissions_by_owner(repo):
    """Every valid file for each owner, oldest first.

    The folder name has to be that owner's numeric id. A founding seed under
    submissions/founding/ is not an owner folder; the waiver loader reads it.
    """
    grouped = defaultdict(list)
    for relpath, path in iter_submissions(repo):
        try:
            doc = load_doc(path)
            when = rules.parse_time(doc.get("submitted_at"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        owner = ""
        if isinstance(doc, dict) and isinstance(doc.get("owner"), dict):
            owner = rules.canonical_user_id(doc["owner"].get("user_id"))
        folder_owner = rules.canonical_user_id(relpath.split("/")[1])
        if not folder_owner or owner != folder_owner:
            continue
        grouped[folder_owner].append((when, relpath, doc))
    for rows in grouped.values():
        rows.sort(key=lambda item: (item[0], item[1]))
    return grouped


def user_sort_key(user_id):
    text = str(user_id)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def at_least(value, floor):
    """Integer at least `floor`. Missing or lower values use the floor."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return floor
    if number < floor:
        return floor
    return number


def contained_relpath(repo, path):
    """Clean relative path that stays inside repo after symlinks resolve.

    Empty when the path is unsafe or resolves outside the repository.
    """
    rel = rules.clean_relpath(path)
    if not rel:
        return ""
    root = os.path.realpath(repo)
    target = os.path.realpath(os.path.join(root, *rel.split("/")))
    try:
        inside = os.path.commonpath([root, target]) == root
    except ValueError:
        return ""
    if not inside:
        return ""
    return rel


def tag_list(tags):
    """Tags as written. A string must not be split into letters."""
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str) and tag]


def recommendation(owner_id, owner_handle, when, relpath, handle, tags):
    return {
        "owner_id": str(owner_id),
        "owner_handle": str(owner_handle).lstrip("@"),
        "recommended_at": rules.iso(when),
        "submission": relpath,
        "handle": str(handle).lstrip("@"),
        "tags": tag_list(tags),
    }


def rows_from_submission(doc, relpath, owner_id, owner_handle, when):
    """Eligible neighbour rows. Ineligible rows are left out."""
    period = doc.get("period") if isinstance(doc, dict) else None
    file_owner = ""
    file_handle = ""
    if isinstance(doc, dict) and isinstance(doc.get("owner"), dict):
        file_owner = str(doc["owner"].get("user_id") or "")
        file_handle = str(doc["owner"].get("handle") or "").lstrip("@")
    blocked_ids = {item for item in (str(owner_id), file_owner) if item}
    blocked_handles = {item.lower() for item in (str(owner_handle), file_handle) if item}
    try:
        days = rules.period_days(period.get("from"), period.get("to"))
    except (AttributeError, TypeError, ValueError):
        return []
    found = []
    for row in doc.get("neighbours") or []:
        if not isinstance(row, dict):
            continue
        user_id = rules.canonical_user_id(row.get("user_id"))
        handle = str(row.get("handle") or "").lstrip("@")
        if not user_id or user_id in blocked_ids or handle.lower() in blocked_handles:
            continue
        try:
            ok, _reason = rules.eligibility(row.get("interactions"), days)
        except ValueError:
            continue
        if not ok:
            continue
        found.append(recommendation(
            owner_id, owner_handle, when, relpath, handle, row.get("tags")))
        found[-1]["user_id"] = user_id
    return found


def build(repo, source_commit, generated_at):
    build_doc = share.load_build(repo)
    minimum = at_least(build_doc.get("min_recommendations"), rules.MIN_RECOMMENDATIONS)
    waiver = build_doc.get("founding_waiver") if isinstance(build_doc.get("founding_waiver"), dict) else {}
    raw_waiver = str(waiver.get("submission") or "").strip()
    waiver_rel = contained_relpath(repo, raw_waiver)
    waiver_owner = str(waiver.get("owner_id") or rules.FOUNDING_OWNER_ID)
    waiver_handle = str(waiver.get("owner_handle") or rules.FOUNDING_OWNER_HANDLE).lstrip("@")
    opted = set(share.opted_out_ids(repo))
    banned = set(share.banned_owner_ids(repo))

    by_owner = submissions_by_owner(repo)
    latest = {owner: rows[-1] for owner, rows in by_owner.items()}
    grouped = defaultdict(list)
    founding_ids = set()
    warnings = []
    if raw_waiver and not waiver_rel:
        warnings.append("founding waiver path is not a safe exact path inside the repository")

    for owner, rows in by_owner.items():
        if owner in banned:
            continue
        for when, relpath, doc in rows:
            file_handle = ""
            if isinstance(doc.get("owner"), dict):
                file_handle = str(doc["owner"].get("handle") or "")
            if rules.clean_relpath(relpath) == waiver_rel:
                continue
            for rec in rows_from_submission(doc, relpath, owner, file_handle, when):
                if rec["user_id"] in opted:
                    continue
                grouped[rec["user_id"]].append(rec)

    if waiver_rel:
        waiver_file = os.path.join(repo, waiver_rel)
        if not os.path.isfile(waiver_file):
            warnings.append(f"founding waiver path is set but the file is missing: {waiver_rel}")
        else:
            try:
                waiver_doc = load_doc(waiver_file)
                when = rules.parse_time(waiver_doc.get("submitted_at"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise SystemExit(f"founding waiver file cannot be read: {exc}") from exc
            # Credit the neutral identity from build.json, never the file's own
            # owner, so a test bot's handle does not become the founding credit.
            for rec in rows_from_submission(
                    waiver_doc, waiver_rel, waiver_owner, waiver_handle, when):
                if rec["user_id"] in opted:
                    continue
                founding_ids.add(rec["user_id"])
                grouped[rec["user_id"]].append(rec)

    neighbours = {}
    for user_id, recs in grouped.items():
        # One owner, one credit, even when several of their files name this account.
        # The newest of those files supplies the handle, time, and path.
        once = {}
        for rec in recs:
            current = once.get(rec["owner_id"])
            if current is None or (rec["recommended_at"], rec["submission"]) >= (
                    current["recommended_at"], current["submission"]):
                once[rec["owner_id"]] = rec
        unique = sorted(
            once.values(),
            key=lambda rec: (rec["recommended_at"], user_sort_key(rec["owner_id"])),
        )
        count = len(unique)
        founding = user_id in founding_ids
        if not founding and count < minimum:
            continue
        def handle_key(rec):
            prefer_newer_owner = 0 if rec["owner_id"] == waiver_owner else 1
            return (rec["recommended_at"], prefer_newer_owner)
        handle = max(unique, key=handle_key)["handle"]
        tags = defaultdict(int)
        recommended_by = []
        for rec in unique:
            recommended_by.append({
                "owner_id": rec["owner_id"],
                "owner_handle": rec["owner_handle"],
                "recommended_at": rec["recommended_at"],
                "submission": rec["submission"],
            })
            for tag in rec["tags"]:
                if isinstance(tag, str) and tag:
                    tags[tag] += 1
        neighbours[user_id] = {
            "user_id": user_id,
            "handle": handle,
            "source": "founding" if founding else "community",
            "recommendation_count": count,
            "recommended_by": recommended_by,
            "first_recommended": unique[0]["recommended_at"],
            "last_recommended": unique[-1]["recommended_at"],
            "tags": dict(sorted(tags.items())),
        }

    owners = {}
    for owner, (when, relpath, doc) in sorted(latest.items(), key=lambda item: user_sort_key(item[0])):
        handle = ""
        if isinstance(doc.get("owner"), dict):
            handle = str(doc["owner"].get("handle") or "").lstrip("@")
        owners[owner] = {
            "handle": handle,
            "last_submitted_at": rules.iso(when),
            "status": "banned" if owner in banned else "active",
            "latest_submission": relpath,
        }

    ordered = {key: neighbours[key] for key in sorted(neighbours, key=user_sort_key)}
    document = {
        "format": rules.FORMAT_GLOBAL,
        "version": rules.GLOBAL_VERSION,
        "generated_at": rules.iso(generated_at),
        "source_commit": str(source_commit or ""),
        "rules_version": str(build_doc.get("rules_version") or rules.RULES_VERSION),
        "min_recommendations": minimum,
        "neighbours": ordered,
        "owners": owners,
        "opted_out": sorted(opted),
        "banned_owners": sorted(banned),
    }
    summary = {
        "ok": True,
        "neighbours": len(ordered),
        "founding": sum(1 for row in ordered.values() if row["source"] == "founding"),
        "owners": len(owners),
        "warnings": warnings,
        "waiver": waiver_rel,
    }
    return document, summary


def main():
    parser = argparse.ArgumentParser(description="Rebuild the global neighbours file.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--now", required=True)
    args = parser.parse_args()
    out = args.out or os.path.join(args.repo, rules.GLOBAL_REL)
    document, summary = build(args.repo, args.source_commit, args.now)
    write_doc(out, document)
    summary["out"] = out
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
