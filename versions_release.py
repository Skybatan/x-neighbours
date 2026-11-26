#!/usr/bin/env python3
"""Write versions/latest.json on a Monday release.

The version number is read from VERSION. This script refuses to run on any
other UTC weekday, and it is the only writer of versions/latest.json.
It does not write a second versions/<version>.json file.
global_build.py must not call it. A mid-week global rebuild leaves this
folder alone.

  python3 versions_release.py --repo . --now ISO --changelog "text" \\
    --source-commit SHA --notes "line | line | line"

It does not create the git tag or the GitHub Release. The Monday workflow
does that after this script succeeds.
"""
import argparse
import json
import os
import sys

import rules
import version as version_mod


def assert_monday(when):
    parsed = rules.parse_time(when)
    if parsed.weekday() != 0:
        raise ValueError("versions/latest.json may only change on Monday (UTC)")
    return parsed


def split_notes(text):
    """A list, or one string with lines separated by |. Blank means none."""
    if text is None:
        return None
    if isinstance(text, list):
        parts = [str(item).strip() for item in text]
    else:
        raw = str(text).strip()
        if not raw:
            return None
        parts = [part.strip() for part in raw.split("|")]
    parts = [part for part in parts if part]
    return parts or None


def validate_notes(notes):
    if notes is None:
        return None
    if not isinstance(notes, list) or not 3 <= len(notes) <= 6:
        raise ValueError("release_notes needs 3 to 6 short lines")
    clean = []
    for item in notes:
        text = str(item).strip()
        if not text or "\n" in text or len(text) > 180:
            raise ValueError("each release note is one short line")
        clean.append(text)
    return clean


def existing_notes(repo, number):
    """Notes already stored on versions/latest.json for this same version."""
    path = os.path.join(repo, "versions", "latest.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict) or str(doc.get("version") or "") != number:
        return None
    if not doc.get("release_notes"):
        return None
    return validate_notes(doc.get("release_notes"))


def release_document(repo, when, changelog, source_commit, min_compatible=None, release_notes=None):
    parsed = assert_monday(when)
    number = version_mod.version(os.path.join(repo, "VERSION"))
    minimum = min_compatible or number
    if version_mod.parse_semver(minimum) > version_mod.parse_semver(number):
        raise ValueError("min_compatible_version cannot be newer than the release")
    if not str(changelog or "").strip():
        raise ValueError("a Monday release needs a changelog line")
    if release_notes in (None, ""):
        notes = existing_notes(repo, number)
    else:
        notes = validate_notes(split_notes(release_notes) or [])
    document = {
        "version": number,
        "released_at": rules.iso(parsed),
        "min_compatible_version": minimum,
        "repo": rules.REPO_URL,
        "global_path": rules.GLOBAL_REL,
        "source_commit": str(source_commit or ""),
        "changelog": str(changelog).strip(),
    }
    if notes:
        document["release_notes"] = notes
    return document


def write_release(repo, when, changelog, source_commit, min_compatible=None, release_notes=None):
    document = release_document(
        repo, when, changelog, source_commit, min_compatible, release_notes=release_notes)
    folder = os.path.join(repo, "versions")
    os.makedirs(folder, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    with open(os.path.join(folder, "latest.json"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return document


def main():
    parser = argparse.ArgumentParser(description="Publish versions/latest.json on Monday.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--now", required=True)
    parser.add_argument("--changelog", required=True)
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--min-compatible", default="")
    parser.add_argument("--notes", default="", help="3 to 6 short lines, separated by |")
    args = parser.parse_args()
    try:
        document = write_release(
            args.repo, args.now, args.changelog, args.source_commit,
            min_compatible=args.min_compatible or None, release_notes=args.notes)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "version": document["version"], "released_at": document["released_at"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
