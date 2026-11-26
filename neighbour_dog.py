#!/usr/bin/env python3
"""Decide whether Neighbour Dog merges, rejects, or flags a share pull request.

The GitHub Action runs the mechanical checks. This module judges the result
and the content hints the reviewer bot gathered (account age, boost rings,
follow-for-follow wording). It does not follow anyone on X.

  python3 neighbour_dog.py decide --validation FILE [--context FILE]
  python3 neighbour_dog.py act --validation FILE --pr N [--context FILE]

act comments and, on a clean pass, merges only when NEIGHBOUR_DOG_TOKEN is
set. The token comes from the environment, never from an argument. With no
token the decision is still printed and a reject still fails the process.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import rules


def _id_set(group):
    found = set()
    for item in group or []:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            found.add(text)
    return found


def detect_boost_ring(lists):
    """True when accounts mostly appear on each other's lists and almost nowhere else.

    Each list is one owner's recommended user ids. A pair is a ring when both
    lists have at least three accounts, at least 80 percent of the smaller
    list is shared, and none of those shared accounts appear on a list outside
    that pair. A larger closed group is also a ring: every list in the group
    has at least three accounts, and at least 80 percent of each list also
    appears on the other lists in the group. One sighting is a flag, not a reject.
    Lists shorter than three accounts are not flagged.
    """
    cleaned = []
    for group in lists or []:
        ids = _id_set(group)
        if ids:
            cleaned.append(ids)
    count = len(cleaned)
    if count < 2:
        return False

    def pair_is_ring(left, right):
        first, second = cleaned[left], cleaned[right]
        if len(first) < 3 or len(second) < 3:
            return False
        shared = first & second
        if not shared or len(shared) / min(len(first), len(second)) < 0.8:
            return False
        elsewhere = set()
        for index, group in enumerate(cleaned):
            if index in (left, right):
                continue
            elsewhere |= group
        return shared.isdisjoint(elsewhere)

    for left in range(count):
        for right in range(left + 1, count):
            if pair_is_ring(left, right):
                return True

    parent = list(range(count))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left in range(count):
        for right in range(left + 1, count):
            if cleaned[left] & cleaned[right]:
                union(left, right)

    groups = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)

    for members in groups.values():
        if len(members) < 2 or any(len(cleaned[index]) < 3 for index in members):
            continue
        closed = True
        for index in members:
            others = set()
            for other in members:
                if other != index:
                    others |= cleaned[other]
            overlap = cleaned[index] & others
            if len(overlap) / len(cleaned[index]) < 0.8:
                closed = False
                break
        if closed:
            return True
    return False


def decide(validation, context=None):
    """Return decision merge, reject, or flag, plus short reasons."""
    context = context or {}
    validation = validation or {}
    if validation.get("ok") and validation.get("share") is False:
        return {
            "decision": "skip",
            "reasons": ["Not a share pull request."],
            "merge": False,
        }
    errors = validation.get("errors") or []
    if errors or not validation.get("ok", False):
        reasons = [item.get("message") or item.get("code") or "validation failed" for item in errors]
        return {"decision": "reject", "reasons": reasons or ["validation failed"], "merge": False}

    if rules.follow_bargain(context.get("pr_body") or "") or rules.follow_bargain(context.get("notes") or ""):
        return {
            "decision": "reject",
            "reasons": ["This list promises a follow or asks for one. Recommendations are not a follow exchange."],
            "merge": False,
        }
    if context.get("other_open"):
        return {
            "decision": "reject",
            "reasons": ["This owner already has an open share pull request."],
            "merge": False,
        }

    flags = []
    neighbours = int(validation.get("neighbours") or 0)
    if "prior_count" not in context or int(context.get("prior_count") or 0) == 0:
        flags.append("First-time owner. A person should look before the first list is merged.")
    if neighbours >= rules.LARGE_LIST:
        flags.append("Unusually large list.")
    previous = context.get("previous_count")
    if previous is not None:
        previous = int(previous)
        if neighbours >= previous + 40 and neighbours >= previous * 2:
            flags.append("Sudden spike compared with the previous list.")
    age = context.get("owner_age_days")
    if age is not None and int(age) < rules.OWNER_MIN_AGE_DAYS:
        flags.append("Owner account is newer than 90 days.")
    posts = context.get("recent_original_posts")
    if posts is not None and int(posts) < 1:
        flags.append("Owner account has no recent original posts.")
    if context.get("boost_ring"):
        flags.append("Possible boost ring. The same accounts mostly recommend each other.")
    if context.get("suspicious"):
        flags.append("Some accounts look suspicious.")
    if context.get("action_green") is False:
        flags.append("The automatic check is not green yet.")

    if flags:
        return {"decision": "flag", "reasons": flags, "merge": False}
    return {
        "decision": "merge",
        "reasons": ["The automatic check is green and nothing looks borderline."],
        "merge": True,
    }


def _transport(method, url, payload, headers):
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


def comment_body(result):
    decision = result["decision"]
    lines = [f"Neighbour Dog: {decision}.", ""]
    for reason in result.get("reasons") or []:
        lines.append(f"- {reason}")
    lines.append("")
    if decision == "flag":
        lines.append("Flag for maintainer. This pull request was not merged.")
    elif decision == "reject":
        lines.append("Not merged.")
    else:
        lines.append("Merged. The rebuild opens a pull request for the global list. Each owner counts once per account. Neighbour Dog does not edit that file by hand.")
    lines.append("")
    lines.append("Recommendations are discovery only. They are not a follow exchange.")
    return "\n".join(lines)


def act(result, token, pr_number, repo=rules.REPO_SLUG, transport=None):
    """Comment, and merge only on a clean pass when a token is configured."""
    outcome = {
        "ok": True,
        "decision": result.get("decision"),
        "posted": False,
        "merged": False,
        "labeled": False,
    }
    if result.get("decision") == "skip":
        outcome["reason"] = "not a share pull request"
        return outcome
    if not token:
        outcome["reason"] = "NEIGHBOUR_DOG_TOKEN is not set"
        return outcome
    if not pr_number:
        outcome["ok"] = False
        outcome["reason"] = "pull request number is missing"
        return outcome
    transport = transport or _transport
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "neighbour-dog",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api = f"https://api.github.com/repos/{repo}"

    def call(method, url, payload=None):
        status, parsed = transport(method, url, payload, headers)
        if status >= 400:
            message = parsed.get("message") if isinstance(parsed, dict) else ""
            raise RuntimeError(f"GitHub returned {status}" + (f": {message}" if message else ""))
        return parsed

    try:
        call("POST", f"{api}/issues/{pr_number}/comments", {"body": comment_body(result)})
        outcome["posted"] = True
        if result.get("decision") == "flag":
            try:
                call("POST", f"{api}/issues/{pr_number}/labels", {"labels": ["needs-maintainer"]})
                outcome["labeled"] = True
            except RuntimeError as exc:
                outcome["label_error"] = str(exc)
        elif result.get("decision") == "merge":
            call("PUT", f"{api}/pulls/{pr_number}/merge", {"merge_method": "merge"})
            outcome["merged"] = True
    except RuntimeError as exc:
        outcome["ok"] = False
        outcome["reason"] = str(exc)
    return outcome


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    parser = argparse.ArgumentParser(description="Neighbour Dog review decision.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--validation", required=True)
    decide_cmd.add_argument("--context", default="")
    act_cmd = sub.add_parser("act")
    act_cmd.add_argument("--validation", required=True)
    act_cmd.add_argument("--context", default="")
    act_cmd.add_argument("--pr", default=os.environ.get("PR_NUMBER", ""))
    act_cmd.add_argument("--repo-slug", default=rules.REPO_SLUG)
    args = parser.parse_args()
    validation = load_json(args.validation)
    context = load_json(args.context) if args.context else {}
    result = decide(validation, context)
    if args.cmd == "decide":
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["decision"] != "reject" else 1
    token = os.environ.get("NEIGHBOUR_DOG_TOKEN") or ""
    outcome = act(result, token, args.pr, repo=args.repo_slug)
    print(json.dumps({"decision": result, "act": outcome}, ensure_ascii=False))
    if result["decision"] == "reject" or not outcome.get("ok", True):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
