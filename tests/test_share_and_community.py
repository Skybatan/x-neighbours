#!/usr/bin/env python3
"""Community mode, eligibility, submissions, the global list, and releases.

Every account in here is fictional. Nothing is a real X user.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import community
import global_build
import neighbour_dog
import rules
import share_submission as share
import version as version_mod
import versions_release


NOW = "2026-11-25T17:00:00Z"
EARLIER = "2026-11-10T17:00:00Z"


def person(user_id, handle, replies=2, quotes=0, reposts=0, likes=44, **extra):
    row = {
        "user_id": str(user_id),
        "handle": handle,
        "replies": replies,
        "quotes": quotes,
        "reposts": reposts,
        "likes": likes,
        "first_seen": "2026-09-01T00:00:00Z",
        "last_seen": "2026-11-20T00:00:00Z",
    }
    row.update(extra)
    return row


def write_submission(repo, owner_id, handle, when, rows, proof="555001"):
    document, _dropped, relpath = share.build_document(
        rows, owner_id, handle, when, 90, "XN-ABCD2345", proof,
        owner_name="Example Owner")
    path = os.path.join(repo, relpath)
    share.write_json(path, document)
    return relpath, document


class EligibilityTest(unittest.TestCase):
    def test_min_score_scales_and_floors_at_eight(self):
        self.assertEqual(rules.min_score(90), 50)
        self.assertEqual(rules.min_score(7), 8)
        self.assertEqual(rules.min_score(30), 17)
        self.assertEqual(rules.min_score(45), 25)
        self.assertEqual(rules.min_score(1), 8)
        self.assertEqual(rules.period_days("2026-08-27T00:00:00Z", "2026-11-25T00:00:00Z"), 90)
        self.assertEqual(rules.period_days("2026-08-23T00:00:00Z", "2026-11-24T00:00:00Z"), 93)

    def test_score_matches_the_picture_weights(self):
        self.assertEqual(rules.interaction_score(10, 2, 3, 1), 10 + 2 + 3 * (3 + 1))

    def test_conversation_floor_blocks_a_likes_only_account(self):
        ok, reason = rules.eligibility(
            {"replies": 0, "quotes": 0, "reposts": 0, "likes": 100}, 90)
        self.assertFalse(ok)
        self.assertEqual(reason, "conversation")

    def test_ninety_day_threshold(self):
        low = {"replies": 2, "quotes": 0, "reposts": 0, "likes": 43}
        high = {"replies": 2, "quotes": 0, "reposts": 0, "likes": 44}
        self.assertFalse(rules.eligibility(low, 90)[0])
        self.assertTrue(rules.eligibility(high, 90)[0])
        quotes = {"replies": 0, "quotes": 2, "reposts": 0, "likes": 44}
        self.assertTrue(rules.eligibility(quotes, 90)[0])

    def test_seven_day_threshold(self):
        self.assertFalse(rules.eligibility(
            {"replies": 2, "quotes": 0, "reposts": 0, "likes": 1}, 7)[0])
        self.assertTrue(rules.eligibility(
            {"replies": 2, "quotes": 0, "reposts": 0, "likes": 2}, 7)[0])
        self.assertTrue(rules.eligibility(
            {"replies": 3, "quotes": 0, "reposts": 0, "likes": 0}, 7)[0])

    def test_cap_self_and_order(self):
        rows = [person(100, "example_owner", likes=80)]
        rows.append(person(201, "low_neighbour", replies=2, likes=44))
        rows.append(person(202, "high_neighbour", replies=4, likes=80))
        for index in range(203, 310):
            rows.append(person(index, f"neighbour{index}", replies=2, likes=50))
        kept, dropped = rules.select_neighbours(rows, 90, "100", owner_handle="example_owner")
        self.assertEqual(len(kept), 100)
        self.assertTrue(any(item["reason"] == "self" for item in dropped))
        self.assertTrue(any(item["reason"] == "cap" for item in dropped))
        self.assertEqual(kept[0]["user_id"], "202")
        self.assertNotIn("100", {row["user_id"] for row in kept})

    def test_rules_json_matches_the_module(self):
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), rules.as_dict())


class SubmissionTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.repo)

    def test_valid_file_passes(self):
        relpath, _doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        report = share.validate_file(os.path.join(self.repo, relpath), self.repo, relpath)
        self.assertTrue(report.ok, report.errors)

    def test_owner_cannot_list_themselves(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        doc["neighbours"].append({
            "user_id": "100",
            "handle": "example_owner",
            "interactions": {"replies": 3, "quotes": 0, "reposts": 0, "likes": 40},
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        })
        share.write_json(os.path.join(self.repo, relpath), doc)
        report = share.validate_file(os.path.join(self.repo, relpath), self.repo, relpath)
        self.assertTrue(any(item["code"] == "self" for item in report.errors))

    def test_note_rejects_links_mentions_and_length(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        path = os.path.join(self.repo, relpath)
        doc["neighbours"][0]["note"] = "see https://example.com"
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "note" for item in share.validate_file(path, self.repo, relpath).errors))
        doc["neighbours"][0]["note"] = "hello @ex_neighbour"
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "note" for item in share.validate_file(path, self.repo, relpath).errors))
        doc["neighbours"][0]["note"] = "follow for follow"
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "note" for item in share.validate_file(path, self.repo, relpath).errors))
        doc["neighbours"][0]["note"] = "x" * 141
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "note" for item in share.validate_file(path, self.repo, relpath).errors))
        doc["neighbours"][0]["note"] = "x" * 140
        share.write_json(path, doc)
        self.assertTrue(share.validate_file(path, self.repo, relpath).ok)

    def test_too_many_tags_fail(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        doc["neighbours"][0]["tags"] = ["one", "two", "three", "four"]
        path = os.path.join(self.repo, relpath)
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "tag" for item in share.validate_file(path, self.repo, relpath).errors))

    def test_a_later_file_is_allowed_immediately(self):
        write_submission(
            self.repo, "100", "example_owner", EARLIER, [person(201, "ex_neighbour")])
        soon = "2026-11-11T17:00:00Z"
        relpath, _doc = write_submission(
            self.repo, "100", "example_owner", soon, [person(202, "other_neighbour")])
        report = share.validate_file(os.path.join(self.repo, relpath), self.repo, relpath)
        self.assertTrue(report.ok, report.errors)
        self.assertFalse(any(item["code"] == "interval" for item in report.errors))

    def test_cap_and_eligibility_are_checked_again(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour", replies=0, quotes=0, likes=80)])
        # prepare drops ineligible people, so force one back in
        doc["neighbours"] = [{
            "user_id": "201",
            "handle": "ex_neighbour",
            "interactions": {"replies": 0, "quotes": 0, "reposts": 0, "likes": 80},
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        }]
        path = os.path.join(self.repo, relpath)
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "eligibility" for item in share.validate_file(path, self.repo, relpath).errors))

    def test_missing_proof_fails(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        doc["verification"]["proof_post_id"] = ""
        path = os.path.join(self.repo, relpath)
        share.write_json(path, doc)
        self.assertTrue(any(item["code"] == "proof" for item in share.validate_file(path, self.repo, relpath).errors))

    def test_docs_under_share_folders_are_not_submission_history(self):
        changes = [
            {"status": "A", "path": "founding/README.md"},
            {"status": "A", "path": "submissions/README.md"},
            {"status": "A", "path": "global/build.json"},
            {"status": "M", "path": "README.md"},
        ]
        payload = share.validate_changes(
            self.repo, changes, labels=[], base_waiver="", head_waiver="")
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertFalse(payload["share"])

    def test_share_pr_cannot_change_the_waiver(self):
        relpath, _doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        changes = [
            {"status": "A", "path": relpath},
            {"status": "M", "path": "global/build.json"},
        ]
        payload = share.validate_changes(
            self.repo, changes, labels=[],
            base_waiver="", head_waiver="founding/one.neighbours")
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["waiver_changed"])
        self.assertTrue(any(item["code"] == "waiver" for item in payload["errors"]))
        allowed = share.validate_changes(
            self.repo, [{"status": "M", "path": "global/build.json"}],
            labels=[rules.MAINTAINER_WAIVER_LABEL],
            base_waiver="", head_waiver="founding/one.neighbours")
        self.assertFalse(any(item["code"] == "waiver" for item in allowed["errors"]))

    def test_from_data_never_lists_the_owner(self):
        rows = share.counts_from_data(
            os.path.join(ROOT, "tests", "fixtures", "offline"),
            "100", "2026-11-16T12:00:00Z", 7)
        self.assertNotIn("100", {row["user_id"] for row in rows})

    def test_open_pr_without_a_token_does_not_call_github(self):
        called = []

        def transport(*_args):
            called.append(True)
            return 500, {}

        result = share.create_pull_request("", "submissions/100/file.neighbours", "{}", "t", "b", transport=transport)
        self.assertFalse(result["opened"])
        self.assertFalse(result["pull"])
        self.assertEqual(called, [])

    def test_open_pr_uses_the_transport_and_hides_the_token(self):
        seen = []

        def transport(method, url, payload, headers):
            seen.append((method, url))
            self.assertNotIn("secret-token", json.dumps(payload or {}))
            if url.endswith("/repos/Skybatan/x-neighbours"):
                return 200, {"default_branch": "main"}
            if url.endswith("/git/ref/heads/main"):
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
                return 201, {"html_url": "https://github.com/Skybatan/x-neighbours/pull/1", "number": 1}
            raise AssertionError(url)

        result = share.create_pull_request(
            "secret-token", "submissions/100/2026-11-25T170000Z.neighbours", "{}\n",
            "Share neighbours from example_owner", "body", transport=transport)
        self.assertTrue(result["opened"])
        self.assertNotIn("secret-token", json.dumps(result))
        self.assertTrue(any(url.endswith("/pulls") for _method, url in seen))


class GlobalBuildTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.repo, "global"))
        share.write_json(os.path.join(self.repo, "global", "build.json"), {
            "min_recommendations": 2,
            "rules_version": "1",
            "founding_waiver": {
                "submission": "",
                "owner_id": "founding",
                "owner_handle": "founding-submission",
            },
        })
        os.makedirs(os.path.join(self.repo, "versions"))
        with open(os.path.join(self.repo, "versions", "latest.json"), "w", encoding="utf-8") as fh:
            fh.write('{"version":"9.9.9"}\n')

    def tearDown(self):
        shutil.rmtree(self.repo)

    def rebuild(self):
        return global_build.build(self.repo, "abc123", "2026-11-25T18:00:00Z")

    def set_waiver(self, path):
        doc = share.read_json(os.path.join(self.repo, "global", "build.json"))
        doc["founding_waiver"]["submission"] = path
        share.write_json(os.path.join(self.repo, "global", "build.json"), doc)

    def test_one_owner_does_not_populate_the_list(self):
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        document, summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.assertEqual(summary["neighbours"], 0)
        self.assertIn("100", document["owners"])

    def test_two_owners_add_an_account(self):
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        write_submission(self.repo, "200", "second_owner", NOW, [person(201, "ex_neighbour", likes=60)])
        document, _summary = self.rebuild()
        row = document["neighbours"]["201"]
        self.assertEqual(row["source"], "community")
        self.assertEqual(row["recommendation_count"], 2)
        owners = {item["owner_id"] for item in row["recommended_by"]}
        self.assertEqual(owners, {"100", "200"})
        self.assertIn("submission", row["recommended_by"][0])

    def test_one_owner_counts_once_across_files(self):
        write_submission(self.repo, "100", "example_owner", EARLIER, [person(201, "old_name")])
        write_submission(self.repo, "100", "example_owner", NOW, [person(202, "new_name")])
        write_submission(self.repo, "200", "second_owner", NOW, [
            person(201, "old_name"),
            person(202, "new_name"),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"]["201"]["recommendation_count"], 2)
        self.assertEqual(document["neighbours"]["202"]["recommendation_count"], 2)
        owners_for_old = {item["owner_id"] for item in document["neighbours"]["201"]["recommended_by"]}
        self.assertEqual(owners_for_old, {"100", "200"})

    def test_founding_waiver_populates_from_one_file_with_a_neutral_credit(self):
        doc, _dropped, _relpath = share.build_document(
            [person(201, "ex_neighbour"), person(202, "ex_neighbour2")],
            "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
        # The file may have been produced by a test bot. The global credit
        # still has to be the neutral identity, not example_owner.
        waiver = "founding/2026-11-25T170000Z.neighbours"
        self.set_waiver(waiver)
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, waiver), doc)
        document, summary = self.rebuild()
        self.assertEqual(summary["founding"], 2)
        row = document["neighbours"]["201"]
        self.assertEqual(row["source"], "founding")
        self.assertEqual(row["recommendation_count"], 1)
        credit = row["recommended_by"][0]
        self.assertEqual(credit["owner_id"], "founding")
        self.assertEqual(credit["owner_handle"], "founding-submission")
        self.assertEqual(credit["submission"], waiver)
        self.assertNotEqual(credit["owner_handle"], "example_owner")
        self.assertEqual(len(row["recommended_by"]), 1)

    def test_waiver_matches_the_configured_path_only(self):
        _relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        self.set_waiver("founding/the-one.neighbours")
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, "founding", "the-one.neighbours"), doc)
        other = json.loads(json.dumps(doc))
        other["neighbours"][0]["user_id"] = "404"
        other["neighbours"][0]["handle"] = "not_waived"
        share.write_json(os.path.join(self.repo, "founding", "another.neighbours"), other)
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertNotIn("404", document["neighbours"])

    def test_waiver_on_the_submission_path_hides_the_test_bot(self):
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        doc["neighbours"].append({
            "user_id": "100",
            "handle": "example_owner",
            "interactions": {"replies": 5, "quotes": 1, "reposts": 0, "likes": 80},
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        })
        share.write_json(os.path.join(self.repo, relpath), doc)
        self.set_waiver(relpath)
        document, summary = self.rebuild()
        self.assertEqual(summary["founding"], 1)
        credit = document["neighbours"]["201"]["recommended_by"][0]
        self.assertEqual(credit["owner_id"], "founding")
        self.assertEqual(credit["owner_handle"], "founding-submission")
        self.assertEqual(credit["submission"], relpath)
        self.assertEqual(document["neighbours"]["201"]["recommendation_count"], 1)
        self.assertNotIn("100", document["neighbours"])

    def test_ordinary_submission_cannot_borrow_the_waiver(self):
        write_submission(self.repo, "100", "founding-submission", NOW, [person(201, "ex_neighbour")])
        self.set_waiver("founding/the-one.neighbours")
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})

    def test_later_owner_appends_and_source_stays_founding(self):
        doc, _dropped, _relpath = share.build_document(
            [person(201, "old_handle")],
            "100", "example_owner", EARLIER, 90, "XN-ABCD2345", "555001")
        waiver = "founding/the-one.neighbours"
        self.set_waiver(waiver)
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, waiver), doc)
        write_submission(
            self.repo, "200", "second_owner", NOW, [person(201, "new_handle", likes=70)])
        document, _summary = self.rebuild()
        row = document["neighbours"]["201"]
        self.assertEqual(row["source"], "founding")
        self.assertEqual(row["recommendation_count"], 2)
        self.assertEqual(row["handle"], "new_handle")
        self.assertEqual(row["recommended_by"][0]["owner_id"], "founding")
        self.assertEqual(row["recommended_by"][1]["owner_id"], "200")

    def test_opt_out_removes_a_founding_entry_and_a_ban_ignores_later_submissions(self):
        doc, _dropped, _relpath = share.build_document(
            [person(201, "ex_neighbour")],
            "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
        waiver = "founding/the-one.neighbours"
        self.set_waiver(waiver)
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, waiver), doc)
        os.makedirs(os.path.join(self.repo, "opted-out"))
        share.write_json(os.path.join(self.repo, "opted-out", "accounts.json"), {"accounts": ["201"]})
        write_submission(self.repo, "300", "banned_owner", NOW, [person(202, "from_banned")])
        os.makedirs(os.path.join(self.repo, "banned"))
        share.write_json(os.path.join(self.repo, "banned", "owners.json"), {"owners": ["300"]})
        document, _summary = self.rebuild()
        self.assertNotIn("201", document["neighbours"])
        self.assertNotIn("202", document["neighbours"])
        self.assertIn("201", document["opted_out"])
        self.assertEqual(document["owners"]["300"]["status"], "banned")

    def test_rebuild_does_not_touch_versions(self):
        latest = os.path.join(self.repo, "versions", "latest.json")
        with open(latest, encoding="utf-8") as fh:
            before = fh.read()
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        out = os.path.join(self.repo, "global", "neighbours.global.neighbours")
        subprocess.run(
            [sys.executable, os.path.join(ROOT, "global_build.py"),
             "--repo", self.repo, "--out", out, "--now", NOW, "--source-commit", "abc"],
            check=True, cwd=ROOT,
        )
        with open(latest, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_committed_global_file_matches_an_empty_rebuild(self):
        """An empty submissions tree rebuilds to an empty global list.

        The rebuild runs in a temp repo with the build config and no share
        files, so a real file under submissions/ does not change the result.
        The committed global file is checked for shape only. A later rebuild
        may list owners, and a share pull request does not have to update it.
        """
        repo = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(repo, "global"))
            shutil.copy(
                os.path.join(ROOT, "global", "build.json"),
                os.path.join(repo, "global", "build.json"))
            document, summary = global_build.build(repo, "", "2026-11-25T00:00:00Z")
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["neighbours"], 0)
            self.assertEqual(summary["owners"], 0)
            self.assertEqual(document["neighbours"], {})
            self.assertEqual(document["owners"], {})
            self.assertEqual(document["opted_out"], [])
            self.assertEqual(document["banned_owners"], [])
            self.assertEqual(document["generated_at"], "2026-11-25T00:00:00Z")
            self.assertEqual(document["source_commit"], "")
            self.assertEqual(document["format"], rules.FORMAT_GLOBAL)
            with open(os.path.join(ROOT, rules.GLOBAL_REL), encoding="utf-8") as fh:
                committed = json.load(fh)
            # The seed file and a later rebuild share this shape. Owners and
            # neighbours depend on submissions, so this test does not require
            # the committed file to stay empty.
            self.assertEqual(committed["format"], document["format"])
            self.assertEqual(committed["rules_version"], document["rules_version"])
            self.assertEqual(committed["min_recommendations"], document["min_recommendations"])
            self.assertNotIn("submission_interval_days", document)
            self.assertNotIn("submission_interval_days", committed)
            self.assertIsInstance(committed["neighbours"], dict)
            self.assertIsInstance(committed["owners"], dict)
        finally:
            shutil.rmtree(repo)

    def test_committed_founding_seed_uses_the_neutral_credit(self):
        with open(os.path.join(ROOT, "global", "build.json"), encoding="utf-8") as fh:
            build = json.load(fh)
        rel = build["founding_waiver"]["submission"]
        self.assertEqual(rel, "submissions/founding/2026-11-26T000000Z.neighbours")
        self.assertEqual(build["founding_waiver"]["owner_id"], "founding")
        self.assertEqual(build["founding_waiver"]["owner_handle"], "founding-submission")
        path = os.path.join(ROOT, rel)
        report = share.validate_file(path, ROOT, rel, now="2026-11-26T18:00:00Z")
        self.assertTrue(report.ok, report.errors)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["owner"]["user_id"], "founding")
        self.assertEqual(doc["owner"]["handle"], "founding-submission")
        self.assertEqual(len(doc["neighbours"]), 42)
        with open(os.path.join(ROOT, rules.GLOBAL_REL), encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(set(committed["neighbours"]), {row["user_id"] for row in doc["neighbours"]})
        self.assertEqual(len(committed["neighbours"]), 42)
        for row in committed["neighbours"].values():
            self.assertEqual(row["source"], "founding")
            self.assertEqual(row["recommendation_count"], 1)
            credit = row["recommended_by"][0]
            self.assertEqual(credit["owner_id"], "founding")
            self.assertEqual(credit["owner_handle"], "founding-submission")
            self.assertEqual(credit["submission"], rel)


class CommunityModeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "community.json")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_default_is_off_and_join_then_leave(self):
        self.assertFalse(community.load(self.path)["community"])
        offered = community.offer(self.path)
        self.assertTrue(offered["offer"])
        self.assertIn("does not post or follow", offered["prompt"])
        again = community.offer(self.path)
        self.assertFalse(again["offer"])
        joined = community.join(self.path, NOW)
        self.assertTrue(joined["community"])
        left = community.leave(self.path, NOW)
        self.assertFalse(left["community"])
        self.assertIn("opt-out", left["shared_lists"])
        self.assertFalse(community.load(self.path)["community"])

    def test_individual_mode_does_not_read_versions_or_the_global_list(self):
        blocked = os.path.join(self.dir, "versions-dir")
        os.mkdir(blocked)
        plan = community.weekly_plan(False)
        self.assertFalse(plan["fetch_versions"])
        self.assertFalse(plan["fetch_global"])
        result = community.check_update(False, "0.1.0", {"version": "9.9.9"})
        self.assertFalse(result["check"])
        self.assertFalse(result["read_versions"])
        self.assertFalse(result["ask"])
        self.assertFalse(result["pull"])
        dest = os.path.join(self.dir, "global_neighbours.neighbours")
        saved = community.save_global(False, True, {"source_commit": "abc"}, dest)
        self.assertFalse(saved["saved"])
        self.assertFalse(saved["read_global"])
        self.assertFalse(os.path.isfile(dest))
        sunday = community.sunday_message(False, NOW, None)
        self.assertFalse(sunday["remind"])

    def test_picture_tag_reminder(self):
        quiet = community.picture_tag(False, "example_owner", "My X neighbours circle!")
        self.assertFalse(quiet["remind"])
        self.assertNotIn("@", quiet["text"])
        self.assertIsNone(quiet["intent"])
        loud = community.picture_tag(True, "example_owner", "My X neighbours circle!")
        self.assertTrue(loud["remind"])
        self.assertIn("@SkyXFunNext", loud["text"])
        self.assertIn("SkyXFunNext", urllib_unquote(loud["intent"]))
        skipped = community.picture_tag(True, "@SkyXFunNext", "My X neighbours circle!")
        self.assertFalse(skipped["remind"])
        self.assertEqual(skipped["text"], "")

    def test_sunday_reminder_names_the_next_day(self):
        ready = community.sunday_message(True, NOW, None, "Europe/Stockholm")
        self.assertTrue(ready["can_share"])
        self.assertIn("Monday", ready["text"])
        again = community.sunday_message(True, NOW, "2026-11-24T17:00:00Z", "Europe/Stockholm")
        self.assertTrue(again["can_share"])
        self.assertIsNone(again["next_allowed_at"])
        self.assertIn("whenever you want", again["text"])

    def test_update_check_asks_and_never_pulls_by_itself(self):
        latest = {
            "version": "9.9.9",
            "min_compatible_version": "9.0.0",
            "changelog": "A test release.",
            "source_commit": "abc",
        }
        result = community.check_update(True, "0.1.0", latest)
        self.assertTrue(result["ask"])
        self.assertFalse(result["upgrade"])
        self.assertFalse(result["pull"])
        self.assertFalse(result["executed"])
        self.assertTrue(result["behind_minimum"])
        same = community.check_update(True, version_mod.version(), {
            "version": version_mod.version(),
            "min_compatible_version": version_mod.version(),
            "changelog": "same",
        })
        self.assertFalse(same["ask"])
        declined = community.check_update(True, "0.1.0", latest, declined_version="9.9.9")
        self.assertFalse(declined["ask"])
        forced = community.check_update(True, "0.1.0", latest, declined_version="9.9.9", force=True)
        self.assertTrue(forced["ask"])
        no = community.decide_upgrade("no", "9.9.9")
        self.assertFalse(no["pull"])
        self.assertFalse(no["executed"])
        self.assertEqual(no["declined_version"], "9.9.9")
        yes = community.decide_upgrade("yes", "9.9.9")
        self.assertTrue(yes["pull"])
        self.assertFalse(yes["executed"])
        self.assertIn("git pull --ff-only", yes["steps"])
        with open(os.path.join(ROOT, "community.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)

    def test_global_list_is_saved_on_the_weekly_check_only(self):
        dest = os.path.join(self.dir, "global_neighbours.neighbours")
        remote = {"format": "x-neighbours-global", "source_commit": "abc", "neighbours": {}}
        mid = community.save_global(True, False, remote, dest)
        self.assertFalse(mid["saved"])
        self.assertFalse(os.path.isfile(dest))
        saved = community.save_global(True, True, remote, dest)
        self.assertTrue(saved["saved"])
        again = community.save_global(True, True, remote, dest)
        self.assertFalse(again["saved"])
        self.assertEqual(again["reason"], "same commit")
        newer = dict(remote, source_commit="def")
        saved = community.save_global(True, True, newer, dest)
        self.assertTrue(saved["saved"])
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["source_commit"], "def")


class VersionReleaseTest(unittest.TestCase):
    def test_is_newer_orders_major_minor_patch(self):
        self.assertFalse(version_mod.is_newer(version_mod.version(), version_mod.version()))
        self.assertTrue(version_mod.is_newer("9.9.9", version_mod.version()))
        self.assertFalse(version_mod.is_newer("0.1.0", version_mod.version()))

    def test_latest_json_is_the_only_release_file(self):
        folder = os.path.join(ROOT, "versions")
        self.assertEqual(os.listdir(folder), ["latest.json"])
        with open(os.path.join(folder, "latest.json"), encoding="utf-8") as fh:
            latest = json.load(fh)
        self.assertEqual(latest["version"], version_mod.version())
        self.assertEqual(latest["min_compatible_version"], version_mod.version())
        self.assertEqual(latest["released_at"], "2026-11-26T18:00:00Z")
        self.assertNotIn("Tentative", latest["changelog"])
        self.assertEqual(latest["repo"], rules.REPO_URL)

    def test_release_writer_refuses_a_wednesday_and_writes_on_monday(self):
        repo = tempfile.mkdtemp()
        try:
            with open(os.path.join(repo, "VERSION"), "w", encoding="utf-8") as fh:
                fh.write("1.2.3\n")
            with self.assertRaises(ValueError):
                versions_release.write_release(repo, "2026-11-25T14:00:00Z", "notes", "abc")
            document = versions_release.write_release(repo, "2026-11-30T14:00:00Z", "notes", "abc")
            self.assertEqual(document["version"], "1.2.3")
            with open(os.path.join(repo, "versions", "latest.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["source_commit"], "abc")
        finally:
            shutil.rmtree(repo)

    def test_real_repo_rebuild_leaves_latest_json_bytes_alone(self):
        path = os.path.join(ROOT, "versions", "latest.json")
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        out = tempfile.mkdtemp()
        try:
            subprocess.run(
                [sys.executable, os.path.join(ROOT, "global_build.py"),
                 "--repo", ROOT, "--out", os.path.join(out, "out.neighbours"),
                 "--now", "2026-11-25T00:00:00Z", "--source-commit", ""],
                check=True, cwd=ROOT,
            )
        finally:
            shutil.rmtree(out)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)


class NeighbourDogTest(unittest.TestCase):
    def clean(self, **extra):
        validation = {"ok": True, "errors": [], "neighbours": 4, "waiver_changed": False}
        context = {"prior_count": 2, "owner_age_days": 200, "recent_original_posts": 3, "action_green": True}
        context.update(extra)
        return validation, context

    def test_a_code_change_is_not_a_share_review(self):
        result = neighbour_dog.decide({"ok": True, "errors": [], "share": False, "neighbours": 0}, {})
        self.assertEqual(result["decision"], "skip")
        self.assertFalse(result["merge"])

    def test_clean_pass_merges(self):
        validation, context = self.clean()
        result = neighbour_dog.decide(validation, context)
        self.assertEqual(result["decision"], "merge")
        self.assertTrue(result["merge"])

    def test_interval_proof_opt_out_and_waiver_reject(self):
        for code, message in (
            ("interval", "next submission is allowed at 2026-12-01T00:00:00Z"),
            ("proof", "proof_post_id is missing"),
            ("opt_out", "ex_neighbour has opted out"),
            ("waiver", "changing the founding waiver path needs the maintainer-waiver label"),
            ("self", "the owner cannot list their own account"),
            ("eligibility", "ex_neighbour does not meet the score rule"),
        ):
            result = neighbour_dog.decide(
                {"ok": False, "errors": [{"code": code, "message": message}], "neighbours": 1},
                {"prior_count": 3})
            self.assertEqual(result["decision"], "reject", code)
            self.assertFalse(result["merge"])

    def test_spike_and_first_time_and_boost_ring_are_flags(self):
        validation, context = self.clean(previous_count=10)
        validation["neighbours"] = 55
        result = neighbour_dog.decide(validation, context)
        self.assertEqual(result["decision"], "flag")
        self.assertTrue(any("spike" in reason.lower() for reason in result["reasons"]))

        _validation, context = self.clean(prior_count=0)
        result = neighbour_dog.decide(_validation, context)
        self.assertEqual(result["decision"], "flag")
        self.assertTrue(any("first-time" in reason.lower() for reason in result["reasons"]))

        ring = neighbour_dog.detect_boost_ring([
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "9"},
            {"8", "7", "6"},
        ])
        self.assertTrue(ring)
        self.assertFalse(neighbour_dog.detect_boost_ring([
            {"1", "2", "3", "4", "5"},
            {"1", "2", "3", "4", "9"},
            {"1", "8", "7"},
        ]))
        validation, context = self.clean(boost_ring=True)
        result = neighbour_dog.decide(validation, context)
        self.assertEqual(result["decision"], "flag")

    def test_follow_bargain_rejects(self):
        validation, context = self.clean()
        context["pr_body"] = "Follow for follow if you want on the list."
        result = neighbour_dog.decide(validation, context)
        self.assertEqual(result["decision"], "reject")

    def test_act_without_a_token_does_not_merge(self):
        result = neighbour_dog.decide(*self.clean())
        called = []
        outcome = neighbour_dog.act(result, "", 12, transport=lambda *args: called.append(args))
        self.assertFalse(outcome["merged"])
        self.assertFalse(outcome["posted"])
        self.assertEqual(called, [])


class OneSubmissionCITest(unittest.TestCase):
    """A real share file must not turn the suite, the validator, or the rebuild red."""

    def test_one_valid_submission_keeps_checks_green(self):
        parent = tempfile.mkdtemp()
        try:
            dest = os.path.join(parent, "repo")
            shutil.copytree(
                ROOT, dest,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "venv", "*.pyc"))
            self._git(dest, "init", "-b", "v3")
            self._git(dest, "config", "user.email", "test@example.com")
            self._git(dest, "config", "user.name", "Test Bot")
            self._git(dest, "add", "-A")
            self._git(dest, "commit", "-m", "base")
            base = self._git(dest, "rev-parse", "HEAD").stdout.strip()

            relpath, _doc = write_submission(
                dest, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
            report = share.validate_file(
                os.path.join(dest, relpath), dest, now="2026-11-25T18:00:00Z")
            self.assertTrue(report.ok, report.errors)

            nested = subprocess.run(
                [sys.executable, "-m", "unittest",
                 "tests.test_version.VersionTest.test_version_string_appears_only_in_VERSION",
                 "tests.test_share_and_community.GlobalBuildTest.test_committed_global_file_matches_an_empty_rebuild"],
                cwd=dest, capture_output=True, text=True)
            self.assertEqual(nested.returncode, 0, nested.stderr)

            self._git(dest, "add", relpath)
            self._git(dest, "commit", "-m", "Share neighbours from example_owner")
            checked = subprocess.run(
                [sys.executable, os.path.join(dest, "share_submission.py"), "validate-pr",
                 "--repo", dest, "--base", base, "--labels", ""],
                cwd=dest, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            payload = json.loads(checked.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertTrue(payload["share"])
            self.assertEqual(payload["added"], [relpath])
            self.assertEqual(payload["errors"], [])

            latest = os.path.join(dest, "versions", "latest.json")
            with open(latest, encoding="utf-8") as fh:
                before = fh.read()
            out = os.path.join(dest, "global", "neighbours.global.neighbours")
            rebuilt = subprocess.run(
                [sys.executable, os.path.join(dest, "global_build.py"),
                 "--repo", dest, "--out", out,
                 "--now", "2026-11-26T00:00:00Z", "--source-commit", "abc123"],
                cwd=dest, capture_output=True, text=True)
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
            summary = json.loads(rebuilt.stdout)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["neighbours"], 42)
            self.assertEqual(summary["founding"], 42)
            self.assertEqual(summary["owners"], 1)
            with open(latest, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)
            with open(out, encoding="utf-8") as fh:
                document = json.load(fh)
            self.assertEqual(len(document["neighbours"]), 42)
            self.assertNotIn("201", document["neighbours"])
            self.assertTrue(all(row["source"] == "founding" for row in document["neighbours"].values()))
            self.assertIn("100", document["owners"])
            self.assertEqual(
                document["owners"]["100"]["latest_submission"], relpath)

            validate_workflow = self._workflow("validate.yml")
            tests_workflow = self._workflow("tests.yml")
            rebuild_workflow = self._workflow("rebuild-global.yml")
            self.assertIn("pull_request:", validate_workflow)
            self.assertIn("share_submission.py validate-pr", validate_workflow)
            self.assertIn("pull_request:", tests_workflow)
            self.assertIn("unittest discover -s tests", tests_workflow)
            self.assertIn('branches:\n      - main', rebuild_workflow)
            self.assertIn('"submissions/**"', rebuild_workflow)
            self.assertIn("global_build.py", rebuild_workflow)
            self.assertNotIn("pull_request:", rebuild_workflow)
            self.assertIn("gh pr create", rebuild_workflow)
            self.assertNotIn("versions/", rebuild_workflow)
        finally:
            shutil.rmtree(parent)

    def _git(self, dest, *args):
        result = subprocess.run(
            ["git", *args], cwd=dest, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def _workflow(self, name):
        with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as fh:
            return fh.read()


def urllib_unquote(value):
    import urllib.parse
    return urllib.parse.unquote(value or "")


if __name__ == "__main__":
    unittest.main()
