#!/usr/bin/env python3
"""Follow-up fixes from the v3 end-to-end test bot.

Accounts here are fictional. Each test pins one hole: the target branch,
the founding waiver on a normal submission, community-only prepare,
the 7-day clock, and the Monday guard.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import community
import global_build
import rules
import share_submission as share


NOW = "2026-11-25T17:00:00Z"
MONDAY = "2026-11-30T14:00:00Z"
WEDNESDAY = "2026-11-25T14:00:00Z"


def person(user_id="201", handle="ex_neighbour"):
    return {
        "user_id": user_id,
        "handle": handle,
        "replies": 2,
        "quotes": 0,
        "reposts": 0,
        "likes": 44,
        "first_seen": "2026-09-01T00:00:00Z",
        "last_seen": "2026-11-20T00:00:00Z",
    }


def namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


def joined_community(folder):
    path = os.path.join(folder, "community.json")
    community.join(path, NOW)
    return path


class BranchTargetTest(unittest.TestCase):
    def test_urls_follow_the_branch_and_default_to_main(self):
        main_plan = community.weekly_plan(True, "main")
        self.assertIn("/main/versions/latest.json", main_plan["versions_url"])
        self.assertIn("/main/global/neighbours.global.neighbours", main_plan["global_url"])
        v3_plan = community.weekly_plan(True, "v3")
        self.assertEqual(v3_plan["branch"], "v3")
        self.assertIn("/v3/versions/latest.json", v3_plan["versions_url"])
        self.assertNotIn("/main/", v3_plan["versions_url"])
        self.assertNotIn("/main/", v3_plan["global_url"])
        quiet = community.weekly_plan(False, "v3")
        self.assertFalse(quiet["fetch_versions"])
        self.assertFalse(quiet["fetch_global"])
        self.assertNotIn("versions_url", quiet)

    def test_resolve_order_is_flag_then_config_then_checkout_then_main(self):
        folder = tempfile.mkdtemp()
        try:
            self.assertEqual(rules.resolve_branch("", "", folder), "main")
            self.assertEqual(rules.resolve_branch("v3", "main", folder), "v3")
            config = os.path.join(folder, "config.json")
            with open(config, "w", encoding="utf-8") as fh:
                json.dump({"share_branch": "v3"}, fh)
            self.assertEqual(rules.share_branch_from_config(config), "v3")
            self.assertEqual(rules.resolve_branch("", "v3", folder), "v3")
            self.assertEqual(rules.safe_branch("../v3"), "")
            self.assertEqual(rules.safe_branch("v3"), "v3")
            checkout = os.path.join(folder, "checkout")
            os.makedirs(os.path.join(checkout, ".git"))
            with open(os.path.join(checkout, ".git", "HEAD"), "w", encoding="utf-8") as fh:
                fh.write("ref: refs/heads/v3\n")
            self.assertEqual(rules.checked_out_branch(checkout), "v3")
            self.assertEqual(rules.resolve_branch("", "", checkout), "v3")
            with open(os.path.join(checkout, ".git", "HEAD"), "w", encoding="utf-8") as fh:
                fh.write("abc123\n")
            self.assertEqual(rules.checked_out_branch(checkout), "")
            self.assertEqual(rules.resolve_branch("", "", checkout), "main")
        finally:
            shutil.rmtree(folder)

    def test_open_pr_can_target_v3(self):
        seen = []

        def transport(method, url, payload, headers):
            seen.append((method, url, payload))
            if url.endswith("/git/ref/heads/v3"):
                return 200, {"object": {"sha": "abc"}}
            if "/git/commits/abc" in url and method == "GET":
                return 200, {"tree": {"sha": "tree"}}
            if url.endswith("/git/blobs"):
                return 201, {"sha": "blob"}
            if url.endswith("/git/trees"):
                return 201, {"sha": "newtree"}
            if url.endswith("/git/commits"):
                return 201, {"sha": "commit"}
            if url.endswith("/git/refs"):
                return 201, {}
            if url.endswith("/pulls"):
                self.assertEqual(payload["base"], "v3")
                return 201, {"html_url": "https://github.com/Skybatan/x-neighbours/pull/9", "number": 9}
            raise AssertionError(url)

        result = share.create_pull_request(
            "secret-token", "submissions/100/2026-11-25T170000Z.neighbours", "{}\n",
            "Share neighbours from example_owner", "body", transport=transport, base="v3")
        self.assertTrue(result["opened"])
        self.assertEqual(result["base"], "v3")
        self.assertTrue(any(url.endswith("/git/ref/heads/v3") for _method, url, _payload in seen))
        self.assertFalse(any(url.endswith("/repos/Skybatan/x-neighbours") for _method, url, _payload in seen))


class FoundingWaiverFileTest(unittest.TestCase):
    def test_a_normal_submission_can_be_the_waiver_and_keeps_its_owner(self):
        repo = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(repo, "global"))
            document, _dropped, relpath = share.build_document(
                [person()], "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
            share.write_json(os.path.join(repo, relpath), document)
            share.write_json(os.path.join(repo, "global", "build.json"), {
                "min_recommendations": 2,
                "founding_waiver": {
                    "submission": relpath,
                    "owner_id": "founding",
                    "owner_handle": "founding-submission",
                },
            })
            report = share.validate_file(os.path.join(repo, relpath), repo, relpath, now="2026-11-25T18:00:00Z")
            self.assertTrue(report.ok, report.errors)
            self.assertFalse(any(item["code"] == "waiver" for item in report.errors))
            built, _summary = global_build.build(repo, "abc", "2026-11-25T18:00:00Z")
            row = built["neighbours"]["201"]
            self.assertEqual(row["source"], "founding")
            credit = row["recommended_by"][0]
            self.assertEqual(credit["owner_id"], "founding")
            self.assertEqual(credit["owner_handle"], "founding-submission")
            self.assertEqual(credit["submission"], relpath)
            self.assertNotIn("example_owner", json.dumps(row))
        finally:
            shutil.rmtree(repo)


class ShareGuardTest(unittest.TestCase):
    def test_prepare_refuses_individual_mode_and_reuses_a_code(self):
        folder = tempfile.mkdtemp()
        try:
            counts = os.path.join(folder, "counts.json")
            out = os.path.join(folder, "share-draft.neighbours")
            with open(counts, "w", encoding="utf-8") as fh:
                json.dump([person()], fh)
            with self.assertRaises(ValueError):
                share.run(namespace(
                    cmd="prepare", counts=counts, owner_id="100", owner_handle="example_owner",
                    owner_name="", now=NOW, days=90, drop=[], note=[], tag=[], exclude=[],
                    code="", community_file="", out=out, repo=folder))
            self.assertFalse(os.path.exists(out))
            community_path = os.path.join(folder, "community.json")
            community.save(community_path, community.blank())
            with self.assertRaises(ValueError):
                share.run(namespace(
                    cmd="prepare", counts=counts, owner_id="100", owner_handle="example_owner",
                    owner_name="", now=NOW, days=90, drop=[], note=[], tag=[], exclude=[],
                    code="XN-ABCD2345", community_file=community_path, out=out, repo=folder))
            self.assertFalse(os.path.exists(out))
            community.join(community_path, NOW)
            with redirect_stdout(io.StringIO()):
                code = share.run(namespace(
                    cmd="prepare", counts=counts, owner_id="100", owner_handle="example_owner",
                    owner_name="", now=NOW, days=90, drop=[], note=[], tag=[], exclude=[],
                    code="XN-KEEP1234", community_file=community_path, out=out, repo=folder))
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["verification"]["code"], "XN-KEEP1234")
        finally:
            shutil.rmtree(folder)

    def test_from_data_keeps_the_code_it_is_given(self):
        folder = tempfile.mkdtemp()
        try:
            out = os.path.join(folder, "share-draft.neighbours")
            community_path = joined_community(folder)
            with redirect_stdout(io.StringIO()):
                code = share.run(namespace(
                    cmd="from-data", data=os.path.join(ROOT, "tests", "fixtures", "offline"),
                    owner_id="100", owner_handle="example_owner", owner_name="",
                    now="2026-11-16T12:00:00Z", days=7, drop=[], exclude=[],
                    code="XN-KEEP1234", community_file=community_path, out=out, repo=folder))
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["verification"]["code"], "XN-KEEP1234")
            self.assertNotIn("100", {row["user_id"] for row in saved["neighbours"]})
        finally:
            shutil.rmtree(folder)

    def test_draft_validates_on_content_until_it_is_placed_under_submissions(self):
        repo = tempfile.mkdtemp()
        store = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(repo, "global"))
            share.write_json(
                os.path.join(repo, "global", "build.json"),
                {"founding_waiver": {"submission": ""}})
            document, _dropped, relpath = share.build_document(
                [person()], "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
            clock = "2026-11-25T18:00:00Z"
            draft = os.path.join(store, "share-draft.neighbours")
            share.write_json(draft, document)
            outside = share.validate_file(draft, repo, now=clock)
            self.assertTrue(outside.ok, outside.errors)
            self.assertFalse(any(item["code"] == "path" for item in outside.errors))

            working = os.path.join(repo, "share-draft.neighbours")
            share.write_json(working, document)
            in_repo = share.validate_file(working, repo, now=clock)
            self.assertTrue(in_repo.ok, in_repo.errors)
            self.assertFalse(any(item["code"] == "path" for item in in_repo.errors))

            missing = json.loads(json.dumps(document))
            missing["verification"]["proof_post_id"] = ""
            share.write_json(draft, missing)
            bad = share.validate_file(draft, repo, now=clock)
            self.assertFalse(bad.ok)
            self.assertTrue(any(item["code"] == "proof" for item in bad.errors))
            self.assertFalse(any(item["code"] == "path" for item in bad.errors))

            share.write_json(draft, document)
            with redirect_stdout(io.StringIO()) as buf:
                code = share.run(namespace(cmd="validate-file", path=draft, repo=repo))
            self.assertEqual(code, 0, buf.getvalue())
            self.assertTrue(json.loads(buf.getvalue())["ok"])

            share.write_json(os.path.join(repo, relpath), document)
            placed = share.validate_file(os.path.join(repo, relpath), repo, now=clock)
            self.assertTrue(placed.ok, placed.errors)

            wrong = os.path.join(repo, "submissions", "100", "not-a-stamp.neighbours")
            os.makedirs(os.path.dirname(wrong), exist_ok=True)
            share.write_json(wrong, document)
            path_report = share.validate_file(wrong, repo, now=clock)
            self.assertTrue(any(item["code"] == "path" for item in path_report.errors))
        finally:
            shutil.rmtree(repo)
            shutil.rmtree(store)

    def test_dropped_output_is_a_summary(self):
        rows = [{"user_id": str(i), "handle": f"h{i}", "reason": "score"} for i in range(20)]
        rows.append({"user_id": "x", "handle": "y", "reason": "conversation"})
        summary = share.summarize_dropped(rows)
        self.assertEqual(summary["count"], 21)
        self.assertEqual(summary["by_reason"]["score"], 20)
        self.assertEqual(len(summary["examples"]), 8)

    def test_uncommitted_draft_does_not_start_the_seven_day_clock(self):
        repo = tempfile.mkdtemp()
        try:
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=repo, check=True)
            os.makedirs(os.path.join(repo, "global"))
            share.write_json(os.path.join(repo, "global", "build.json"), {"founding_waiver": {"submission": ""}})
            first, doc = _write(repo, "100", "2026-11-01T12:00:00Z")
            subprocess.run(["git", "add", first], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "first share"], cwd=repo, check=True, capture_output=True)
            _write(repo, "100", "2026-11-02T12:00:00Z")
            self.assertEqual(share.previous_submission_at(repo, "100"), "2026-11-01T12:00:00Z")
            later, _doc = _write(repo, "100", "2026-11-08T12:00:00Z")
            report = share.validate_file(
                os.path.join(repo, later), repo, later, now="2026-11-25T18:00:00Z")
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(doc["owner"]["user_id"], "100")
        finally:
            shutil.rmtree(repo)


class MondayAndUpgradeTest(unittest.TestCase):
    def test_check_and_save_refuse_a_wednesday_unless_forced(self):
        folder = tempfile.mkdtemp()
        try:
            path = joined_community(folder)
            latest = os.path.join(folder, "latest.json")
            with open(latest, "w", encoding="utf-8") as fh:
                json.dump({"version": "9.9.9", "min_compatible_version": "9.9.9"}, fh)
            with redirect_stdout(io.StringIO()) as buf:
                code = community.run(namespace(
                    file=path, cmd="check-update", latest=latest, local=None,
                    now=WEDNESDAY, force=False))
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(buf.getvalue())["reason"], "not Monday")
            self.assertFalse(json.loads(buf.getvalue())["pull"])
            with redirect_stdout(io.StringIO()) as buf:
                code = community.run(namespace(
                    file=path, cmd="check-update", latest=latest, local=None,
                    now=MONDAY, force=False))
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(buf.getvalue())["check"])
            dest = os.path.join(folder, "global_neighbours.neighbours")
            src = os.path.join(folder, "remote.neighbours")
            with open(src, "w", encoding="utf-8") as fh:
                json.dump({"source_commit": "abc", "neighbours": {}}, fh)
            with redirect_stdout(io.StringIO()) as buf:
                code = community.run(namespace(
                    file=path, cmd="save-global", src=src, dest=dest, weekly=True,
                    now=WEDNESDAY, force=False))
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(dest))
            with redirect_stdout(io.StringIO()) as buf:
                code = community.run(namespace(
                    file=path, cmd="save-global", src=src, dest=dest, weekly=True,
                    now=MONDAY, force=False))
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(buf.getvalue())["saved"])
        finally:
            shutil.rmtree(folder)

    def test_pip_install_is_listed_only_when_requirements_changed(self):
        unknown = community.decide_upgrade("yes", "9.9.9")
        self.assertIn(community.PIP_WHEN_CHANGED, unknown["steps"])
        self.assertNotIn(community.PIP_STEP, unknown["steps"])
        changed = community.decide_upgrade("yes", "9.9.9", requirements_changed=True)
        self.assertIn(community.PIP_STEP, changed["steps"])
        same = community.decide_upgrade("yes", "9.9.9", requirements_changed=False)
        self.assertNotIn(community.PIP_STEP, same["steps"])
        self.assertNotIn("pip install", " ".join(same["steps"]))
        self.assertFalse(same["executed"])


class DocsAndIgnoreTest(unittest.TestCase):
    def test_config_example_has_share_branch_and_not_a_community_flag(self):
        with open(os.path.join(ROOT, "config.example.json"), encoding="utf-8") as fh:
            config = json.load(fh)
        self.assertNotIn("community", config)
        self.assertEqual(config["share_branch"], "")
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            ignored = fh.read()
        self.assertIn("test-state/", ignored)

    def test_runbooks_name_the_branch_the_draft_and_the_waiver(self):
        share_skill = _read("skills/x-neighbours-share/SKILL.md")
        community_skill = _read("skills/x-neighbours-community/SKILL.md")
        founding = _read("founding/README.md")
        self.assertNotIn("git fetch origin main", share_skill)
        self.assertIn("--base", share_skill)
        self.assertIn("share-draft.neighbours", share_skill)
        self.assertIn("submissions/<user id>/<timestamp>.neighbours", share_skill)
        self.assertIn("--code", share_skill)
        self.assertIn("--community-file", share_skill)
        self.assertIn("draft's contents", share_skill)
        self.assertIn("Where the draft is saved", share_skill)
        self.assertIn("path rule is enforced only when the file is placed", share_skill)
        self.assertIn("not Monday", community_skill)
        self.assertIn("--base v3", community_skill)
        self.assertIn("requirements.txt` changed", community_skill)
        self.assertIn("submissions/<x user id>/<UTC timestamp>.neighbours", founding)
        self.assertIn("founding-submission", founding)
        self.assertIn("submissions/founding/2026-11-26T000000Z.neighbours", founding)
        self.assertIn("Do not add another pre-made list", founding)


def _write(repo, owner, when):
    document, _dropped, relpath = share.build_document(
        [person()], owner, "example_owner", when, 90, "XN-ABCD2345", "555001")
    share.write_json(os.path.join(repo, relpath), document)
    return relpath, document


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    unittest.main()
