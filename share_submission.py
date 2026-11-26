#!/usr/bin/env python3
"""Build and check a public good neighbours submission.

A submission is JSON with a .neighbours extension. The path is
submissions/<x_user_id>/<UTC timestamp>.neighbours. Older files stay.

  python3 share_submission.py code
  python3 share_submission.py next-allowed --owner-id ID --now ISO [--previous ISO]
  python3 share_submission.py prepare --counts FILE --owner-id ID --owner-handle HANDLE \\
      --now ISO [--days N] [--drop ID] [--out FILE]
  python3 share_submission.py finalize --draft FILE --proof-post ID [--out FILE]
  python3 share_submission.py from-data --data DIR --owner-id ID --owner-handle HANDLE \\
      --now ISO [--days N] [--out FILE]
  python3 share_submission.py validate-file PATH [--repo ROOT]
  python3 share_submission.py validate-pr --repo ROOT --base REF [--labels a,b]
  python3 share_submission.py open-pr --file PATH

validate-file checks a draft on its contents. The path rule
(submissions/<user id>/<timestamp>.neighbours) applies only when the
file is already under submissions/, which is where a share pull request
places it.

open-pr reads X_NEIGHBOURS_GITHUB_TOKEN from the environment. It never
prints the token and it never takes the token as an argument. With no
token it does not open a pull request.

Recommendations are discovery only. This script does not follow anyone
and it does not post on X.
"""
import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import community
import rules
import version as version_mod


GENERATOR_BOT = "x-neighbours"
INTERACTION_KEYS = ("replies", "quotes", "reposts", "likes")


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, doc):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def new_code():
    chars = rules.CODE_ALPHABET
    return "XN-" + "".join(secrets.choice(chars) for _ in range(8))


def load_id_list(path, key):
    if not path or not os.path.isfile(path):
        return []
    doc = read_json(path)
    rows = doc.get(key) if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return []
    found = []
    for item in rows:
        if isinstance(item, dict):
            item = item.get("user_id") or item.get("id") or ""
        if item is not None and str(item).strip():
            found.append(str(item).strip())
    return found


def opted_out_ids(repo):
    return load_id_list(os.path.join(repo, rules.OPTED_OUT_REL), "accounts")


def banned_owner_ids(repo):
    return load_id_list(os.path.join(repo, rules.BANNED_REL), "owners")


def load_build(repo):
    path = os.path.join(repo, rules.BUILD_REL)
    if not os.path.isfile(path):
        return {"min_recommendations": rules.MIN_RECOMMENDATIONS, "founding_waiver": {}}
    doc = read_json(path)
    return doc if isinstance(doc, dict) else {}


def waiver_raw(doc):
    """The waiver path as written in build.json, before it is checked."""
    waiver = doc.get("founding_waiver") if isinstance(doc, dict) else None
    if not isinstance(waiver, dict):
        return ""
    return str(waiver.get("submission") or "").strip()


def waiver_path(doc):
    """Exact safe waiver path. Unsafe or empty config matches nothing."""
    return rules.clean_relpath(waiver_raw(doc))


def period_bounds(now, days):
    end = rules.parse_time(now)
    start = end - timedelta(days=int(days))
    return rules.iso(start), rules.iso(end)


def neighbour_record(row):
    record = {
        "user_id": str(row["user_id"]),
        "handle": str(row["handle"]).lstrip("@"),
        "interactions": {
            "replies": int(row["replies"]),
            "quotes": int(row["quotes"]),
            "reposts": int(row["reposts"]),
            "likes": int(row["likes"]),
        },
        "first_seen": row.get("first_seen") or "",
        "last_seen": row.get("last_seen") or "",
    }
    note = row.get("note")
    if note:
        record["note"] = note
    tags = row.get("tags")
    if tags:
        record["tags"] = list(tags)
    return record


def build_document(rows, owner_id, owner_handle, now, days, code, proof_post_id,
                   owner_name="", drop_ids=None, exclude_ids=None, notes=None, tags=None):
    """Return (document, dropped, relpath). proof_post_id may be empty on a draft."""
    days = int(days)
    if days < rules.MIN_PERIOD_DAYS or days > rules.MAX_PERIOD_DAYS:
        raise ValueError(
            f"period must be from {rules.MIN_PERIOD_DAYS} to {rules.MAX_PERIOD_DAYS} days"
        )
    start, end = period_bounds(now, days)
    prepared = []
    notes = notes or {}
    tags = tags or {}
    for row in rows:
        item = dict(row)
        user_id = str(item.get("user_id") or "")
        if user_id in notes:
            item["note"] = notes[user_id]
        if user_id in tags:
            item["tags"] = tags[user_id]
        prepared.append(item)
    kept, dropped = rules.select_neighbours(
        prepared, days, owner_id, owner_handle=owner_handle,
        drop_ids=drop_ids, exclude_ids=exclude_ids, cap=rules.LIST_CAP)
    when = rules.parse_time(now)
    owner = {"user_id": str(owner_id), "handle": str(owner_handle).lstrip("@")}
    if owner_name:
        owner["name"] = owner_name
    neighbours = []
    for row in kept:
        problem = rules.note_problem(row.get("note"))
        if problem:
            raise ValueError(problem)
        problem = rules.tags_problem(row.get("tags"))
        if problem:
            raise ValueError(problem)
        if not row.get("first_seen"):
            row["first_seen"] = start
        if not row.get("last_seen"):
            row["last_seen"] = end
        neighbours.append(neighbour_record(row))
    document = {
        "format": rules.FORMAT_SUBMISSION,
        "version": rules.SUBMISSION_VERSION,
        "submitted_at": rules.iso(when),
        "owner": owner,
        "verification": {
            "code": code,
            "proof_post_id": str(proof_post_id or ""),
        },
        "consent": {
            "share_publicly": True,
            "agreed_rules_version": rules.RULES_VERSION,
        },
        "period": {"from": start, "to": end},
        "neighbours": neighbours,
        "generator": {
            "bot": GENERATOR_BOT,
            "template_version": version_mod.version(),
        },
    }
    return document, dropped, rules.submission_relpath(owner_id, when)


def normalize_counts(payload):
    if isinstance(payload, dict):
        payload = payload.get("neighbours") or payload.get("counts") or payload.get("share_counts") or []
    if not isinstance(payload, list):
        raise ValueError("counts must be a list of people")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        interactions = item.get("interactions") if isinstance(item.get("interactions"), dict) else item
        rows.append({
            "user_id": str(item.get("user_id") or item.get("id") or ""),
            "handle": str(item.get("handle") or item.get("username") or "").lstrip("@"),
            "name": item.get("name") or "",
        "replies": interactions.get("replies") if interactions.get("replies") is not None else 0,
        "quotes": interactions.get("quotes") if interactions.get("quotes") is not None else 0,
        "reposts": interactions.get("reposts") if interactions.get("reposts") is not None else 0,
        "likes": interactions.get("likes") if interactions.get("likes") is not None else 0,
            "first_seen": item.get("first_seen") or "",
            "last_seen": item.get("last_seen") or "",
            "note": item.get("note") or None,
            "tags": item.get("tags") or [],
        })
    return rows


def parse_assignments(values):
    """Turn ['id=text', ...] into a dict. The value may contain '='."""
    found = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"expected id=value, got {raw}")
        key, value = raw.split("=", 1)
        found[str(key).strip()] = value.strip()
    return found


def parse_tag_assignments(values):
    grouped = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"expected id=tag, got {raw}")
        key, value = raw.split("=", 1)
        grouped.setdefault(str(key).strip(), []).append(value.strip().lower())
    return grouped


class Report:
    def __init__(self):
        self.errors = []

    def add(self, code, message):
        self.errors.append({"code": code, "message": message})

    @property
    def ok(self):
        return not self.errors

    def as_dict(self):
        return {"ok": self.ok, "errors": list(self.errors)}


def _require_object(report, value, label):
    if not isinstance(value, dict):
        report.add("schema", f"{label} must be an object")
        return False
    return True


def path_rules_apply(relpath):
    """True when the file is already under submissions/.

    A draft in the bot store is checked on content. The folder name and the
    file stamp are checked only once the file sits at
    submissions/<user id>/<timestamp>.neighbours, which is where open-pr
    and a share pull request place it.
    """
    rel = str(relpath or "").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.startswith("submissions/")


def validate_document(doc, relpath, report, opted_out=None,
                      banned=None, waiver=None, now=None, check_path=True):
    """Append errors for one submission document. relpath is repo-relative.

    now is the clock for future timestamps. It defaults to the current UTC time.
    check_path is false for a draft that is not under submissions/. Content
    rules still run. The path rule runs when the file is placed for submit.
    There is no waiting period between files from the same owner.
    """
    opted_out = set(opted_out or [])
    banned = set(banned or [])
    clock = datetime.now(timezone.utc) if now is None else rules.parse_time(now)
    if not isinstance(doc, dict):
        report.add("schema", "submission must be a JSON object")
        return
    expected = {
        "format", "version", "submitted_at", "owner", "verification",
        "consent", "period", "neighbours", "generator",
    }
    extra = set(doc) - expected
    if extra:
        report.add("schema", "unexpected fields: " + ", ".join(sorted(extra)))
    missing = expected - set(doc)
    if missing:
        report.add("schema", "missing fields: " + ", ".join(sorted(missing)))
        return
    if doc.get("format") != rules.FORMAT_SUBMISSION:
        report.add("schema", "format is not a neighbours submission")
    if doc.get("version") != rules.SUBMISSION_VERSION:
        report.add("schema", "unsupported submission version")

    match = rules.SUBMISSION_RE.fullmatch(relpath or "") if check_path else None
    founding_match = rules.FOUNDING_SUBMISSION_RE.fullmatch(relpath or "") if check_path else None
    # A draft outside submissions/ skips the path rule. Submit places the file,
    # and the pull request check is what requires the path. The founding seed
    # lives at submissions/founding/<timestamp>.neighbours and is credited to
    # the neutral identity. global_build.py writes that credit from build.json.
    if check_path:
        waiver_rel = rules.clean_relpath(waiver)
        if founding_match:
            owner_from_path = rules.FOUNDING_OWNER_ID
            stamp = founding_match.group(1)
        elif match:
            owner_from_path, stamp = match.group(1), match.group(2)
        else:
            if waiver_rel and rules.clean_relpath(relpath) == waiver_rel:
                report.add(
                    "path",
                    "the founding waiver must be submissions/founding/<timestamp>.neighbours"
                    " or submissions/<user id>/<timestamp>.neighbours",
                )
            report.add("path", "path must be submissions/<user id>/<timestamp>.neighbours")
            owner_from_path = ""
            stamp = ""
    else:
        owner_from_path = ""
        stamp = ""

    try:
        submitted = rules.iso(doc.get("submitted_at"))
    except (TypeError, ValueError):
        report.add("schema", "submitted_at must be a UTC timestamp")
        submitted = ""
    if submitted and rules.parse_time(submitted) > clock:
        report.add("future", "submitted_at is in the future")
    if stamp and submitted:
        try:
            stamped = rules.stamp_to_iso(stamp)
        except ValueError:
            stamped = ""
        if stamped and stamped != submitted:
            report.add("path", "file name timestamp must match submitted_at")

    owner = doc.get("owner")
    if not _require_object(report, owner, "owner"):
        owner = {}
    owner_id = str(owner.get("user_id") or "")
    handle = str(owner.get("handle") or "").lstrip("@")
    owner_keys = set(owner) - {"user_id", "handle", "name"}
    if owner_keys:
        report.add("schema", "owner has unexpected fields")
    if founding_match:
        if handle != rules.FOUNDING_OWNER_HANDLE:
            report.add("schema", "founding file owner handle must be founding-submission")
    elif not rules.HANDLE_RE.fullmatch(handle):
        report.add("schema", "owner handle must be an X handle")
    if not founding_match and not rules.USER_ID_RE.fullmatch(owner_id):
        report.add("schema", "owner user_id must be the numeric X id")
    if owner_from_path and owner_id != owner_from_path:
        report.add("path", "folder name must be the owner user id")
    if owner_id in banned:
        report.add("banned_owner", "this owner is not allowed to submit")

    verification = doc.get("verification")
    if not _require_object(report, verification, "verification"):
        verification = {}
    code = str(verification.get("code") or "")
    proof = str(verification.get("proof_post_id") or "")
    if set(verification) - {"code", "proof_post_id"}:
        report.add("schema", "verification has unexpected fields")
    if not rules.CODE_RE.fullmatch(code):
        report.add("proof", "verification code must look like XN- and eight letters or digits")
    if not proof:
        report.add("proof", "proof_post_id is missing")
    elif not rules.PROOF_RE.fullmatch(proof):
        report.add("proof", "proof_post_id must be the numeric id of the owner's post")

    consent = doc.get("consent")
    if not _require_object(report, consent, "consent"):
        consent = {}
    if consent.get("share_publicly") is not True:
        report.add("schema", "share_publicly must be true")
    if consent.get("agreed_rules_version") != rules.RULES_VERSION:
        report.add("schema", "agreed_rules_version does not match the current rules")

    period = doc.get("period")
    if not _require_object(report, period, "period"):
        period = {}
    try:
        start_at = rules.parse_time(period.get("from"))
        end_at = rules.parse_time(period.get("to"))
        if end_at <= start_at:
            raise ValueError("period ends before it starts")
        days = rules.period_days(start_at, end_at)
    except (TypeError, ValueError):
        report.add("schema", "period from and to must be UTC timestamps")
        days = None
        start_at = None
        end_at = None
    if days is not None and not rules.period_within_bounds(start_at, end_at):
        report.add(
            "schema",
            f"period must cover {rules.MIN_PERIOD_DAYS} to {rules.MAX_PERIOD_DAYS} days",
        )
    if start_at is not None and (start_at > clock or end_at > clock):
        report.add("future", "period must not extend into the future")

    neighbours = doc.get("neighbours")
    if not isinstance(neighbours, list):
        report.add("schema", "neighbours must be a list")
        neighbours = []
    if len(neighbours) > rules.LIST_CAP:
        report.add("cap", f"a submission lists at most {rules.LIST_CAP} people")
    seen = set()
    for index, row in enumerate(neighbours):
        where = f"neighbours[{index}]"
        if not isinstance(row, dict):
            report.add("schema", f"{where} must be an object")
            continue
        allowed_keys = {
            "user_id", "handle", "interactions", "first_seen", "last_seen", "note", "tags",
        }
        extra_row = set(row) - allowed_keys
        if extra_row:
            report.add("schema", f"{where} has unexpected fields")
        user_id = str(row.get("user_id") or "")
        row_handle = str(row.get("handle") or "").lstrip("@")
        if not rules.USER_ID_RE.fullmatch(user_id):
            report.add("schema", f"{where} user_id must be numeric")
        if not rules.HANDLE_RE.fullmatch(row_handle):
            report.add("schema", f"{where} handle must be an X handle")
        if user_id and (user_id == owner_id or row_handle.lower() == handle.lower()):
            report.add("self", "the owner cannot list their own account")
        if user_id in seen:
            report.add("schema", f"{where} repeats a user id")
        seen.add(user_id)
        if user_id in opted_out:
            report.add("opt_out", f"{row_handle or user_id} has opted out")
        try:
            counts = rules.counts_of(row.get("interactions"))
        except ValueError as exc:
            report.add("schema", f"{where} {exc}")
            counts = None
        if counts is not None and set(row.get("interactions") or {}) - set(INTERACTION_KEYS):
            report.add("schema", f"{where} interactions has unexpected fields")
        if counts is not None and days is not None:
            ok, reason = rules.eligibility(counts, days)
            if not ok:
                report.add("eligibility", f"{row_handle or user_id} does not meet the {reason} rule")
        for field in ("first_seen", "last_seen"):
            try:
                seen_at = rules.parse_time(row.get(field))
            except (TypeError, ValueError):
                report.add("schema", f"{where} {field} must be a UTC timestamp")
            else:
                if seen_at > clock:
                    report.add("future", f"{where} {field} is in the future")
        problem = rules.note_problem(row["note"]) if "note" in row else ""
        if problem:
            report.add("note", f"{where} {problem}")
        problem = rules.tags_problem(row["tags"]) if "tags" in row else ""
        if problem:
            report.add("tag", f"{where} {problem}")

    generator = doc.get("generator")
    if not _require_object(report, generator, "generator"):
        generator = {}
    if generator.get("bot") != GENERATOR_BOT:
        report.add("schema", "generator.bot must be x-neighbours")
    if not rules.SEMVER_RE.fullmatch(str(generator.get("template_version") or "")):
        report.add("schema", "generator.template_version must be major.minor.patch")


def head_submission_names(repo, owner_id):
    """File names committed on HEAD for this owner.

    None when this directory is not a git checkout with a HEAD. An empty list
    means HEAD exists and this owner has no committed submission.
    """
    folder_rel = f"submissions/{owner_id}"
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", folder_rel],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    prefix = folder_rel + "/"
    names = []
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if path.startswith(prefix) and path.endswith(".neighbours"):
            names.append(path[len(prefix):])
    return names


def _latest_submitted(pairs):
    """pairs are (relpath, doc-or-None). Returns the latest ISO time, or None."""
    latest = None
    for relpath, doc in pairs:
        if not isinstance(doc, dict):
            continue
        try:
            when = rules.parse_time(doc.get("submitted_at"))
        except (TypeError, ValueError):
            continue
        if latest is None or when > latest:
            latest = when
    return rules.iso(latest) if latest else None


def previous_submission_at(repo, owner_id, ignore_relpath=""):
    """Latest committed submitted_at for this owner, ignoring one new file.

    In a git checkout only files on HEAD count. An uncommitted draft in the
    working tree is not part of that history. A directory that is not a
    git checkout falls back to the files on disk, which is what the tests use.
    """
    names = head_submission_names(repo, owner_id)
    if names is not None:
        pairs = []
        for name in names:
            relpath = f"submissions/{owner_id}/{name}"
            if relpath == ignore_relpath:
                continue
            pairs.append((relpath, git_show(repo, "HEAD", relpath)))
        return _latest_submitted(pairs)

    folder = os.path.join(repo, "submissions", str(owner_id))
    if not os.path.isdir(folder):
        return None
    pairs = []
    for name in os.listdir(folder):
        relpath = f"submissions/{owner_id}/{name}"
        if relpath == ignore_relpath or not name.endswith(".neighbours"):
            continue
        path = os.path.join(folder, name)
        try:
            doc = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        pairs.append((relpath, doc))
    return _latest_submitted(pairs)


def validate_file(path, repo, relpath=None, now=None):
    report = Report()
    if relpath is None:
        relpath = os.path.relpath(path, repo).replace(os.sep, "/")
    check_path = path_rules_apply(relpath)
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        report.add("schema", str(exc))
        return report
    if size > rules.MAX_FILE_BYTES:
        report.add("size", f"file is larger than {rules.MAX_FILE_BYTES} bytes")
        return report
    try:
        doc = read_json(path)
    except json.JSONDecodeError as exc:
        report.add("schema", f"not JSON ({exc})")
        return report
    build = load_build(repo)
    validate_document(
        doc, relpath, report,
        opted_out=opted_out_ids(repo), banned=banned_owner_ids(repo),
        waiver=waiver_path(build), now=now, check_path=check_path,
    )
    return report


def git_changes(repo, base):
    result = subprocess.run(
        ["git", "diff", "--name-status", f"{base}...HEAD"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    changes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        changes.append({"status": status[:1], "path": path.replace(os.sep, "/")})
    return changes


def git_show(repo, base, relpath):
    result = subprocess.run(
        ["git", "show", f"{base}:{relpath}"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def validate_changes(repo, changes, labels=None, base_waiver=None, head_waiver=None):
    """Check a pull request's file list. Does not merge or comment."""
    report = Report()
    labels = {item.strip() for item in (labels or []) if item and item.strip()}
    neighbours_changes = []
    other = []
    for change in changes:
        path = change.get("path") or ""
        # Docs such as founding/README.md are not submission history.
        # Only a .neighbours file under submissions/ or founding/ is.
        if path.endswith(".neighbours") and (
            path.startswith("submissions/") or path.startswith("founding/")
        ):
            neighbours_changes.append(change)
        else:
            other.append(change)

    if head_waiver is None:
        head_waiver = waiver_raw(load_build(repo))
    if base_waiver is None:
        base_waiver = head_waiver
    base_text = str(base_waiver or "").strip()
    head_text = str(head_waiver or "").strip()
    waiver_changed = base_text != head_text
    for raw in (base_text, head_text):
        if raw and not rules.clean_relpath(raw):
            report.add(
                "waiver",
                "founding waiver path must be an exact path inside the repository",
            )
            break
    if waiver_changed and rules.MAINTAINER_WAIVER_LABEL not in labels:
        report.add(
            "waiver",
            "changing the founding waiver path needs the maintainer-waiver label",
        )

    added_submissions = [
        change for change in neighbours_changes
        if change.get("status") == "A" and rules.SUBMISSION_RE.fullmatch(change.get("path") or "")
    ]
    # The founding seed may be added beside other maintainer files when the
    # waiver label is set and the path is the one named in build.json.
    head_rel = rules.clean_relpath(head_text)
    allowed_founding = []
    if rules.MAINTAINER_WAIVER_LABEL in labels and head_rel:
        for change in neighbours_changes:
            path = change.get("path") or ""
            if change.get("status") != "A":
                continue
            if not rules.FOUNDING_SUBMISSION_RE.fullmatch(path):
                continue
            if rules.clean_relpath(path) == head_rel:
                allowed_founding.append(change)
    bad_share = [
        change for change in neighbours_changes
        if change not in added_submissions and change not in allowed_founding
    ]
    for change in bad_share:
        report.add("history", f"submission files are append-only ({change.get('path')})")

    is_share = bool(added_submissions) and not other and not bad_share and not waiver_changed
    if added_submissions and (other or waiver_changed):
        report.add("files", "a share pull request may only add the one submission file")
    if len(added_submissions) > 1:
        report.add("files", "a share pull request adds one submission file")

    neighbour_count = 0
    if (added_submissions or allowed_founding) and not bad_share:
        for change in added_submissions + allowed_founding:
            path = os.path.join(repo, change["path"])
            file_report = validate_file(path, repo, relpath=change["path"])
            report.errors.extend(file_report.errors)
            try:
                doc = read_json(path)
                neighbour_count += len(doc.get("neighbours") or [])
            except (OSError, json.JSONDecodeError):
                pass

    payload = report.as_dict()
    payload.update({
        "share": is_share,
        "waiver_changed": waiver_changed,
        "files": changes,
        "neighbours": neighbour_count,
        "added": [change["path"] for change in added_submissions],
    })
    return payload


def counts_from_data(data_dir, owner_id, now, days, exclude=None):
    """Picture counts from saved JSON.

    Replies are first-level only. Likes on the owner's replies are omitted,
    so a report still scores when those liker files were never fetched.
    """
    import x_neighbours as xn
    end = rules.parse_time(now)
    start = end - timedelta(days=int(days))
    data = xn.Data(data_dir, str(owner_id))
    data.exclude = {str(item).lstrip("@").lower() for item in (exclude or [])}
    activity = xn.build_activity(
        data, start, end, top=10, like_weight=rules.LIKE_WEIGHT,
        reply_weight=rules.REPLY_WEIGHT, mode="both", now=end)
    return activity.get("share_counts") or []


def default_transport(method, url, payload, headers):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"message": raw[:300]}
        return exc.code, parsed


def create_pull_request(token, relpath, content, title, body, repo=rules.REPO_SLUG,
                        transport=None, base=""):
    """Open a pull request that adds one submission file. Does not follow or post.

    base is the branch the pull request merges into. Blank asks GitHub for
    the repository default, which is main for this repo. Pass v3 to target
    that branch instead. The token is never included in the result.
    """
    if not token:
        return {
            "ok": False,
            "opened": False,
            "pull": False,
            "reason": "X_NEIGHBOURS_GITHUB_TOKEN is not set",
            "path": relpath,
        }
    transport = transport or default_transport
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": GENERATOR_BOT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api = f"https://api.github.com/repos/{repo}"

    def call(method, url, payload=None):
        status, parsed = transport(method, url, payload, headers)
        if status >= 400:
            message = ""
            if isinstance(parsed, dict):
                message = parsed.get("message") or ""
            raise RuntimeError(f"GitHub returned {status}" + (f": {message}" if message else ""))
        return parsed

    try:
        branch = rules.safe_branch(base)
        if not branch:
            meta = call("GET", api)
            branch = rules.safe_branch(meta.get("default_branch")) or "main"
        ref = call("GET", f"{api}/git/ref/heads/{branch}")
        base_sha = ref["object"]["sha"]
        commit = call("GET", f"{api}/git/commits/{base_sha}")
        tree_sha = commit["tree"]["sha"]
        blob = call("POST", f"{api}/git/blobs", {
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "encoding": "base64",
        })
        tree = call("POST", f"{api}/git/trees", {
            "base_tree": tree_sha,
            "tree": [{
                "path": relpath,
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            }],
        })
        stamp = relpath.rsplit("/", 1)[-1].replace(".neighbours", "")
        owner = relpath.split("/")[1]
        head = f"share/{owner}/{stamp}"
        new_commit = call("POST", f"{api}/git/commits", {
            "message": title,
            "tree": tree["sha"],
            "parents": [base_sha],
        })
        call("POST", f"{api}/git/refs", {
            "ref": f"refs/heads/{head}",
            "sha": new_commit["sha"],
        })
        pull = call("POST", f"{api}/pulls", {
            "title": title,
            "body": body,
            "head": head,
            "base": branch,
        })
    except (KeyError, RuntimeError, TypeError) as exc:
        return {
            "ok": False,
            "opened": False,
            "pull": False,
            "reason": str(exc),
            "path": relpath,
        }
    return {
        "ok": True,
        "opened": True,
        "pull": True,
        "executed": True,
        "url": pull.get("html_url") or "",
        "number": pull.get("number"),
        "path": relpath,
        "base": branch,
    }


def community_required(path):
    """Sharing writes a public file. Individual mode cannot prepare one."""
    if not path:
        raise ValueError("pass --community-file; individual mode does not share")
    state = community.load(path)
    if not state.get("community"):
        raise ValueError("community mode is off; individual mode does not share")


def summarize_dropped(dropped, limit=8):
    """Counts by reason, plus a short sample. The full list is not printed."""
    rows = [item for item in (dropped or []) if isinstance(item, dict)]
    by_reason = {}
    for item in rows:
        reason = str(item.get("reason") or "other")
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "count": len(rows),
        "by_reason": by_reason,
        "examples": rows[:limit],
    }


def pull_body(handle):
    return (
        f"Share a good neighbours list from @{handle}.\n\n"
        "Recommendations are discovery only. This list does not follow anyone "
        "and it does not ask for a follow back.\n\n"
        "The rules are in RULES.md.\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Build or check a neighbours submission.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("code", help="print a one-time verification code")

    allowed = sub.add_parser("next-allowed", help="report the last submission; sharing has no waiting period")
    allowed.add_argument("--owner-id", required=True)
    allowed.add_argument("--now", required=True)
    allowed.add_argument("--previous", help="ISO time of the last submission")
    allowed.add_argument("--repo", default=".")

    prepare = sub.add_parser("prepare", help="build a draft from a counts file")
    prepare.add_argument("--counts", required=True)
    prepare.add_argument("--owner-id", required=True)
    prepare.add_argument("--owner-handle", required=True)
    prepare.add_argument("--owner-name", default="")
    prepare.add_argument("--now", required=True)
    prepare.add_argument("--days", type=int, default=rules.DEFAULT_PERIOD_DAYS)
    prepare.add_argument("--drop", action="append", default=[])
    prepare.add_argument("--note", action="append", default=[])
    prepare.add_argument("--tag", action="append", default=[])
    prepare.add_argument("--exclude", action="append", default=[])
    prepare.add_argument("--code", help="verification code; generated when omitted")
    prepare.add_argument("--community-file", required=True, help="community.json; sharing stays off until the owner joins")
    prepare.add_argument("--out", required=True)
    prepare.add_argument("--repo", default=".")

    finalize = sub.add_parser("finalize", help="add the proof post id to a draft")
    finalize.add_argument("--draft", required=True)
    finalize.add_argument("--proof-post", required=True)
    finalize.add_argument("--out", help="defaults to the draft path")

    from_data = sub.add_parser("from-data", help="count saved X JSON, then prepare a draft")
    from_data.add_argument("--data", required=True)
    from_data.add_argument("--owner-id", required=True)
    from_data.add_argument("--owner-handle", required=True)
    from_data.add_argument("--owner-name", default="")
    from_data.add_argument("--now", required=True)
    from_data.add_argument("--days", type=int, default=rules.DEFAULT_PERIOD_DAYS)
    from_data.add_argument("--drop", action="append", default=[])
    from_data.add_argument("--exclude", action="append", default=[])
    from_data.add_argument("--code", help="reuse this verification code instead of minting a new one")
    from_data.add_argument("--community-file", required=True, help="community.json; sharing stays off until the owner joins")
    from_data.add_argument("--out", required=True)
    from_data.add_argument("--repo", default=".")

    check = sub.add_parser(
        "validate-file",
        help="check a draft on content, or a file under submissions/ on content and path",
    )
    check.add_argument("path")
    check.add_argument("--repo", default=".")

    pull = sub.add_parser("validate-pr", help="check the files changed on a branch")
    pull.add_argument("--repo", default=".")
    pull.add_argument("--base", required=True)
    pull.add_argument("--labels", default="")

    opener = sub.add_parser("open-pr", help="open a pull request when a token is configured")
    opener.add_argument("--file", required=True)
    opener.add_argument("--repo-slug", default=rules.REPO_SLUG)
    opener.add_argument("--base", default="", help="branch the pull request targets; default is the checkout, then main")
    opener.add_argument("--config", default="", help="config.json; share_branch overrides the checkout")
    opener.add_argument("--repo", default=".")

    args = parser.parse_args()
    try:
        code = run(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1
    return code


def run(args):
    if args.cmd == "code":
        emit({"ok": True, "code": new_code()})
        return 0
    if args.cmd == "next-allowed":
        previous = args.previous or previous_submission_at(args.repo, args.owner_id)
        emit({
            "ok": True,
            "allowed": True,
            "last_submitted_at": previous,
            "next_allowed_at": None,
        })
        return 0
    if args.cmd in ("prepare", "from-data"):
        community_required(args.community_file)
        if args.cmd == "from-data":
            rows = counts_from_data(
                args.data, args.owner_id, args.now, args.days, exclude=args.exclude)
        else:
            rows = normalize_counts(read_json(args.counts))
        code = str(args.code or "").strip() or new_code()
        notes = parse_assignments(getattr(args, "note", None))
        tags = parse_tag_assignments(getattr(args, "tag", None))
        document, dropped, relpath = build_document(
            rows, args.owner_id, args.owner_handle, args.now, args.days, code, "",
            owner_name=args.owner_name, drop_ids=args.drop,
            exclude_ids=list(args.exclude) + opted_out_ids(args.repo),
            notes=notes, tags=tags)
        document["verification"]["proof_post_id"] = ""
        write_json(args.out, document)
        post = f"Verifying my X Neighbours list. Code: {code}"
        emit({
            "ok": True,
            "draft": True,
            "path": relpath,
            "file": args.out,
            "code": code,
            "post_text": post,
            "neighbours": len(document["neighbours"]),
            "dropped": summarize_dropped(dropped),
            "proof_post_id": "",
        })
        return 0
    if args.cmd == "finalize":
        document = read_json(args.draft)
        if not isinstance(document, dict):
            raise ValueError("draft must be a JSON object")
        verification = document.setdefault("verification", {})
        verification["proof_post_id"] = str(args.proof_post)
        out = args.out or args.draft
        write_json(out, document)
        owner = document.get("owner") or {}
        relpath = rules.submission_relpath(owner.get("user_id"), document.get("submitted_at"))
        emit({"ok": True, "draft": False, "file": out, "path": relpath})
        return 0
    if args.cmd == "validate-file":
        report = validate_file(args.path, args.repo)
        payload = report.as_dict()
        emit(payload)
        return 0 if report.ok else 1
    if args.cmd == "validate-pr":
        changes = git_changes(args.repo, args.base)
        base_doc = git_show(args.repo, args.base, rules.BUILD_REL) or {}
        head_doc = load_build(args.repo)
        payload = validate_changes(
            args.repo, changes, labels=args.labels.split(","),
            base_waiver=waiver_raw(base_doc), head_waiver=waiver_raw(head_doc),
        )
        emit(payload)
        return 0 if payload["ok"] else 1
    if args.cmd == "open-pr":
        document = read_json(args.file)
        owner = document.get("owner") or {}
        relpath = rules.submission_relpath(owner.get("user_id"), document.get("submitted_at"))
        handle = str(owner.get("handle") or "owner").lstrip("@")
        with open(args.file, encoding="utf-8") as fh:
            content = fh.read()
        token = os.environ.get("X_NEIGHBOURS_GITHUB_TOKEN") or ""
        base = rules.resolve_branch(
            args.base, rules.share_branch_from_config(args.config), args.repo)
        result = create_pull_request(
            token, relpath, content,
            title=f"Share neighbours from {handle}",
            body=pull_body(handle),
            repo=args.repo_slug,
            base=base,
        )
        emit(result)
        return 0 if result.get("opened") else 2
    raise ValueError(f"unknown command {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
