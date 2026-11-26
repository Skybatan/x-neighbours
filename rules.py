#!/usr/bin/env python3
"""Eligibility rules for a shared good neighbours list.

RULES.md is the explanation. This module is the copy the checker, the global
builder, and the tests run. Change a number here and in RULES.md together.
"""
import json
import math
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone


RULES_VERSION = "1"
FORMAT_SUBMISSION = "x-neighbours-submission"
FORMAT_GLOBAL = "x-neighbours-global"
SUBMISSION_VERSION = 1
GLOBAL_VERSION = 1

LIKE_WEIGHT = 1
REPLY_WEIGHT = 3
CONVERSATION_FLOOR = 2
SCORE_NUMERATOR = 50
SCORE_WINDOW_DAYS = 90
SCORE_FLOOR = 8

DEFAULT_PERIOD_DAYS = 90
MIN_PERIOD_DAYS = 7
# The first 3-month picture covered 93 days. A share may use that window.
# Longer than that is refused. A longer window raises the minimum score.
MAX_PERIOD_DAYS = 93

LIST_CAP = 100
NOTE_MAX = 140
TAGS_MAX = 3
TAG_MAX_LEN = 24
MIN_RECOMMENDATIONS = 2
MAX_FILE_BYTES = 256 * 1024

FOUNDING_OWNER_ID = "founding"
FOUNDING_OWNER_HANDLE = "founding-submission"
PICTURE_TAG = "SkyXFunNext"

REPO_SLUG = "Skybatan/x-neighbours"
REPO_URL = "https://github.com/Skybatan/x-neighbours"
GLOBAL_REL = "global/neighbours.global.neighbours"
BUILD_REL = "global/build.json"
OPTED_OUT_REL = "opted-out/accounts.json"
BANNED_REL = "banned/owners.json"
LATEST_REL = "versions/latest.json"
LOCAL_GLOBAL_NAME = "global_neighbours.neighbours"

LARGE_LIST = 80
OWNER_MIN_AGE_DAYS = 90
MAINTAINER_WAIVER_LABEL = "maintainer-waiver"

HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
# No leading zeros. "100" and "0100" must not count as two owners.
USER_ID_RE = re.compile(r"^(?:0|[1-9][0-9]{0,24})$")
CODE_RE = re.compile(r"^XN-[A-Z0-9]{8}$")
PROOF_RE = re.compile(r"^[0-9]{1,25}$")
TAG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,23})$")
SUBMISSION_RE = re.compile(
    r"^submissions/([0-9]{1,25})/(\d{4}-\d{2}-\d{2}T\d{6}Z)\.neighbours$"
)
# The one founding seed. Its folder is the neutral id, not a numeric X id.
FOUNDING_SUBMISSION_RE = re.compile(
    r"^submissions/founding/(\d{4}-\d{2}-\d{2}T\d{6}Z)\.neighbours$"
)
STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})Z$")
LINK_RE = re.compile(
    r"(https?://|www\.|t\.co/|(?:x|twitter)\.com/)",
    re.IGNORECASE,
)
# Fullwidth ＠ is the usual way to sneak a mention past a plain "@" check.
MENTION_RE = re.compile(r"[@＠][A-Za-z0-9_]")
FOLLOW_BARGAIN_RE = re.compile(
    r"follow[\s-]*for[\s-]*follow|\bf4f\b|follow[\s-]*back|followback"
    r"|i(?:'ll| will) follow|follow me",
    re.IGNORECASE,
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Unambiguous alphabet for a code the owner posts. The checker accepts any
# XN- code of eight letters or digits, so a hand-typed code still validates.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def as_dict():
    """The machine-readable rule card. rules.json mirrors this."""
    return {
        "rules_version": RULES_VERSION,
        "score": "likes + reposts + 3 * (replies + quotes)",
        "like_weight": LIKE_WEIGHT,
        "reply_weight": REPLY_WEIGHT,
        "min_score": "max(8, ceil(50 * period_days / 90))",
        "conversation_floor": CONVERSATION_FLOOR,
        "default_period_days": DEFAULT_PERIOD_DAYS,
        "min_period_days": MIN_PERIOD_DAYS,
        "max_period_days": MAX_PERIOD_DAYS,
        "cap": LIST_CAP,
        "min_recommendations": MIN_RECOMMENDATIONS,
        "note_max_chars": NOTE_MAX,
        "max_tags": TAGS_MAX,
        "max_file_bytes": MAX_FILE_BYTES,
        "founding_owner_id": FOUNDING_OWNER_ID,
        "founding_owner_handle": FOUNDING_OWNER_HANDLE,
        "picture_tag": PICTURE_TAG,
    }


def parse_time(value):
    if isinstance(value, datetime):
        when = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        when = datetime.fromisoformat(text)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def iso(when):
    return parse_time(when).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_stamp(when):
    """UTC timestamp safe in a file name. Colons are removed."""
    return parse_time(when).strftime("%Y-%m-%dT%H%M%SZ")


def stamp_to_iso(stamp):
    match = STAMP_RE.fullmatch(stamp or "")
    if not match:
        raise ValueError("file stamp must look like 2026-11-25T170000Z")
    day, hour, minute, second = match.groups()
    return f"{day}T{hour}:{minute}:{second}Z"


def submission_relpath(user_id, when):
    return f"submissions/{user_id}/{file_stamp(when)}.neighbours"


def period_span(start, end):
    """UTC length of a period. The end must be strictly later than the start."""
    delta = parse_time(end) - parse_time(start)
    if delta <= timedelta(0):
        raise ValueError("period ends before it starts")
    return delta


def period_within_bounds(start, end):
    """True when the period spans 7 to 93 full days, inclusive.

    A partial day does not round up into the minimum. Six days and 23 hours
    is shorter than 7 days, and 93 days plus one second is longer than 93.
    """
    delta = period_span(start, end)
    return timedelta(days=MIN_PERIOD_DAYS) <= delta <= timedelta(days=MAX_PERIOD_DAYS)


def period_days(start, end):
    """Whole days covered by the period. An exact multiple stays exact.

    Used to scale min_score. The share checker uses period_within_bounds for
    the 7-day and 93-day limits, so a short window cannot pass by rounding up.
    """
    seconds = period_span(start, end).total_seconds()
    return int(math.ceil(seconds / 86400 - 1e-9))


def canonical_user_id(value):
    """Numeric X id with no leading zeros, or "" when the id is not usable."""
    text = str(value or "").strip()
    if not USER_ID_RE.fullmatch(text):
        return ""
    return text


def safe_branch(name):
    """A git branch name safe to put in a URL or a ref. Empty when it is not."""
    text = str(name or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", text):
        return ""
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return ""
    return text


def checked_out_branch(repo="."):
    """The branch named by .git/HEAD, or "" when HEAD is detached or missing."""
    git_path = os.path.join(repo, ".git")
    if os.path.isfile(git_path):
        try:
            with open(git_path, encoding="utf-8") as fh:
                line = fh.read().strip()
        except OSError:
            return ""
        if not line.startswith("gitdir:"):
            return ""
        git_path = line.split(":", 1)[1].strip()
        if not os.path.isabs(git_path):
            git_path = os.path.normpath(os.path.join(repo, git_path))
    head = os.path.join(git_path, "HEAD")
    try:
        with open(head, encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError:
        return ""
    prefix = "ref: refs/heads/"
    if not text.startswith(prefix):
        return ""
    return safe_branch(text[len(prefix):])


def share_branch_from_config(path):
    """share_branch from a bot config.json. Blank when the file or key is absent."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(doc, dict):
        return ""
    return str(doc.get("share_branch") or "").strip()


def resolve_branch(explicit="", config_branch="", repo="."):
    """Branch for raw URLs and share pull requests.

    An explicit --base wins, then share_branch in config, then the checked-out
    branch. main is the fallback when none of those is a usable name.
    """
    for candidate in (explicit, config_branch, checked_out_branch(repo)):
        safe = safe_branch(candidate)
        if safe:
            return safe
    return "main"


def raw_file_url(branch, relpath):
    """raw.githubusercontent.com URL for one file on a branch."""
    chosen = safe_branch(branch) or "main"
    root = REPO_URL.replace("https://github.com", "https://raw.githubusercontent.com")
    quoted = urllib.parse.quote(chosen, safe="/")
    return f"{root}/{quoted}/{relpath}"


def clean_relpath(path):
    """Repo-relative path with no traversal.

    A leading ./ is removed. Absolute paths, NUL bytes, empty segments, and
    any "." or ".." segment return "" so they cannot match or be opened.
    """
    text = str(path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text.startswith("/") or "\x00" in text:
        return ""
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return ""
    return "/".join(parts)


def min_score(days):
    """max(8, ceil(50 * period_days / 90))."""
    days = int(days)
    if days < 1:
        raise ValueError("period_days must be at least 1")
    scaled = int(math.ceil(SCORE_NUMERATOR * days / SCORE_WINDOW_DAYS))
    return max(SCORE_FLOOR, scaled)


def interaction_score(likes, reposts, replies, quotes, like_weight=LIKE_WEIGHT,
                      reply_weight=REPLY_WEIGHT):
    return (int(likes) + int(reposts)) * like_weight + (int(replies) + int(quotes)) * reply_weight


def counts_of(interactions):
    if not isinstance(interactions, dict):
        raise ValueError("interactions must be an object")
    out = {}
    for key in ("replies", "quotes", "reposts", "likes"):
        value = interactions.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        out[key] = value
    return out


def eligibility(interactions, days):
    """Return (ok, reason). reason is empty when the row passes.

    `replies` are first-level replies only: a direct reply to an owner post
    or quote. A later reply under the owner's own reply does not count
    toward the conversation floor or the score. `likes` are likes on those
    original posts and quotes. Likes on the owner's replies are not included.
    The counts are already filtered before they reach this function.
    """
    counts = counts_of(interactions)
    conversation = counts["replies"] + counts["quotes"]
    if conversation < CONVERSATION_FLOOR:
        return False, "conversation"
    score = interaction_score(
        counts["likes"], counts["reposts"], counts["replies"], counts["quotes"])
    needed = min_score(days)
    if score < needed:
        return False, "score"
    return True, ""


def score_of(interactions):
    counts = counts_of(interactions)
    return interaction_score(
        counts["likes"], counts["reposts"], counts["replies"], counts["quotes"])


def conversation_of(interactions):
    counts = counts_of(interactions)
    return counts["replies"] + counts["quotes"]


def note_problem(note):
    """Empty string when a note is allowed. None means the note is absent."""
    if note is None:
        return ""
    if not isinstance(note, str):
        return "note must be text"
    if note != note.strip() or not note:
        return "note must be non-empty text without surrounding spaces"
    if len(note) > NOTE_MAX:
        return f"note is longer than {NOTE_MAX} characters"
    if LINK_RE.search(note):
        return "note must not contain a link"
    if MENTION_RE.search(note):
        return "note must not contain an @mention"
    if FOLLOW_BARGAIN_RE.search(note):
        return "note must not promise a follow or ask for one"
    return ""


def tags_problem(tags):
    if tags is None:
        return ""
    if not isinstance(tags, list):
        return "tags must be a list"
    if len(tags) > TAGS_MAX:
        return f"at most {TAGS_MAX} tags"
    seen = set()
    for tag in tags:
        if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
            return "a tag must be a short lowercase word"
        if tag in seen:
            return "tags must not repeat"
        seen.add(tag)
    return ""


def follow_bargain(text):
    return bool(FOLLOW_BARGAIN_RE.search(text or ""))


def rank_key(row):
    """Highest score, then replies plus quotes, then numeric user id.

    User ids are numbers. "99" stays ahead of "100"; a text sort would not.
    """
    conversation = int(row["replies"]) + int(row["quotes"])
    user_id = str(row["user_id"])
    try:
        numeric = (0, int(user_id))
    except ValueError:
        numeric = (1, user_id)
    return (-int(row["score"]), -conversation, numeric)


def select_neighbours(rows, days, owner_id, owner_handle="", drop_ids=None,
                      exclude_ids=None, cap=LIST_CAP):
    """Keep eligible people, highest score first, at most `cap`.

    rows are dicts with user_id, handle, replies, quotes, reposts, likes.
    The owner is always dropped. drop_ids are people the owner removed.
    exclude_ids are opted-out or otherwise barred user ids.
    """
    owner = str(owner_id)
    owner_name = str(owner_handle or "").lstrip("@").lower()
    dropped_by_owner = {str(item) for item in (drop_ids or [])}
    barred = {str(item) for item in (exclude_ids or [])}
    seen = set()
    kept = []
    dropped = []

    def reject(row, reason):
        dropped.append({
            "user_id": str(row.get("user_id") or ""),
            "handle": str(row.get("handle") or "").lstrip("@"),
            "reason": reason,
        })

    for row in rows:
        user_id = str(row.get("user_id") or "")
        handle = str(row.get("handle") or "").lstrip("@")
        if not user_id:
            reject(row, "missing id")
            continue
        if user_id == owner or (owner_name and handle.lower() == owner_name):
            reject(row, "self")
            continue
        if user_id in dropped_by_owner:
            reject(row, "removed")
            continue
        if user_id in barred:
            reject(row, "excluded")
            continue
        if user_id in seen:
            reject(row, "duplicate")
            continue
        seen.add(user_id)

        def one_count(key):
            if key not in row or row[key] is None:
                raise ValueError(key)
            return row[key]

        try:
            counts = counts_of({
                "replies": one_count("replies"),
                "quotes": one_count("quotes"),
                "reposts": one_count("reposts"),
                "likes": one_count("likes"),
            })
        except ValueError:
            reject(row, "counts")
            continue
        interactions = counts
        ok, reason = eligibility(interactions, days)
        if not ok:
            reject(row, reason)
            continue
        kept.append({
            **row,
            "user_id": user_id,
            "handle": handle,
            "replies": interactions["replies"],
            "quotes": interactions["quotes"],
            "reposts": interactions["reposts"],
            "likes": interactions["likes"],
            "score": interaction_score(
                interactions["likes"], interactions["reposts"],
                interactions["replies"], interactions["quotes"]),
        })
    kept.sort(key=rank_key)
    overflow = kept[cap:]
    for row in overflow:
        reject(row, "cap")
    return kept[:cap], dropped
