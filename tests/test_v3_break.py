#!/usr/bin/env python3
"""Adversarial tests for the v3 share list, global build, and Monday check.

Every account here is fictional. The cases sit next to the happy-path tests
and try the boundaries the rules name: exact scores, bad files, the 7-day
gap, the founding waiver, abuse, and version checks.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import community
import global_build
import neighbour_dog
import rules
import share_submission as share
import versions_release


NOW = "2026-11-25T17:00:00Z"
CLOCK = "2026-11-25T18:00:00Z"


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


def interactions(replies=2, quotes=0, reposts=0, likes=44):
    return {"replies": replies, "quotes": quotes, "reposts": reposts, "likes": likes}


def codes(report):
    return [item["code"] for item in report.errors]


def write_build(repo, waiver="", minimum=2):
    os.makedirs(os.path.join(repo, "global"), exist_ok=True)
    share.write_json(os.path.join(repo, "global", "build.json"), {
        "min_recommendations": minimum,
        "rules_version": "1",
        "founding_waiver": {
            "submission": waiver,
            "owner_id": "founding",
            "owner_handle": "founding-submission",
        },
    })


def write_submission(repo, owner_id, handle, when, rows, days=90, proof="555001"):
    document, _dropped, relpath = share.build_document(
        rows, owner_id, handle, when, days, "XN-ABCD2345", proof,
        owner_name="Example Owner")
    share.write_json(os.path.join(repo, relpath), document)
    return relpath, document


def check(doc, relpath, repo=None, previous=None, now=CLOCK):
    del previous
    report = share.Report()
    share.validate_document(
        doc, relpath, report, now=now,
        waiver=share.waiver_path(share.load_build(repo)) if repo else "",
    )
    return report


class EligibilityBreakTest(unittest.TestCase):
    def test_score_is_likes_plus_reposts_plus_three_times_replies_and_quotes(self):
        samples = (
            (0, 0, 0, 0, 0),
            (1, 0, 0, 0, 1),
            (0, 4, 0, 0, 4),
            (10, 2, 3, 1, 10 + 2 + 3 * (3 + 1)),
            (44, 0, 2, 0, 50),
            (43, 0, 2, 0, 49),
            (0, 0, 1, 1, 6),
            (100, 20, 0, 2, 126),
        )
        for likes, reposts, replies, quotes, expected in samples:
            self.assertEqual(
                rules.interaction_score(likes, reposts, replies, quotes), expected,
                (likes, reposts, replies, quotes))

    def test_forty_nine_fails_and_fifty_passes_at_ninety_days(self):
        self.assertEqual(rules.min_score(90), 50)
        low = interactions(replies=2, likes=43)
        high = interactions(replies=2, likes=44)
        self.assertEqual(rules.score_of(low), 49)
        self.assertEqual(rules.score_of(high), 50)
        self.assertEqual(rules.eligibility(low, 90), (False, "score"))
        self.assertEqual(rules.eligibility(high, 90), (True, ""))
        # Reposts weigh the same as likes. 43 likes + 1 repost is the passing 50.
        self.assertEqual(
            rules.eligibility(interactions(replies=2, likes=43, reposts=1), 90),
            (True, ""))
        self.assertEqual(
            rules.eligibility(interactions(replies=2, likes=42, reposts=1), 90),
            (False, "score"))

    def test_scaled_periods_use_the_exact_minimum(self):
        expected = {
            7: 8, 14: 8, 15: 9, 30: 17, 45: 25,
            89: 50, 90: 50, 91: 51, 92: 52, 93: 52,
        }
        for days, minimum in expected.items():
            self.assertEqual(rules.min_score(days), minimum, days)
        for days in range(rules.MIN_PERIOD_DAYS, rules.MAX_PERIOD_DAYS + 1):
            minimum = rules.min_score(days)
            # Two replies contribute 6, so the rest has to come from likes.
            self.assertGreaterEqual(minimum, 8)
            passing = interactions(replies=2, likes=minimum - 6)
            failing = interactions(replies=2, likes=minimum - 7)
            self.assertEqual(rules.score_of(passing), minimum, days)
            self.assertEqual(rules.score_of(failing), minimum - 1, days)
            self.assertEqual(rules.eligibility(passing, days), (True, ""), days)
            self.assertEqual(rules.eligibility(failing, days), (False, "score"), days)

    def test_one_reply_or_quote_fails_and_two_passes(self):
        for days in (7, 15, 90, 93):
            one_reply = interactions(replies=1, quotes=0, likes=1000, reposts=1000)
            one_quote = interactions(replies=0, quotes=1, likes=1000)
            self.assertEqual(rules.eligibility(one_reply, days), (False, "conversation"), days)
            self.assertEqual(rules.eligibility(one_quote, days), (False, "conversation"), days)
        # 1 + 1 is the floor. Quotes count the same as replies.
        self.assertEqual(rules.eligibility(interactions(replies=1, quotes=1, likes=2), 7), (True, ""))
        self.assertEqual(rules.eligibility(interactions(replies=0, quotes=2, likes=2), 7), (True, ""))
        self.assertEqual(rules.eligibility(interactions(replies=2, quotes=0, likes=2), 7), (True, ""))
        # Two replies with nothing else are score 6, under the 7-day floor of 8.
        self.assertEqual(rules.eligibility(interactions(replies=2, likes=1), 7), (False, "score"))
        self.assertEqual(rules.eligibility(interactions(replies=2, likes=2), 7), (True, ""))
        self.assertEqual(rules.eligibility(interactions(replies=3, likes=0), 7), (True, ""))

    def test_zeros_fail_the_conversation_floor_before_the_score(self):
        zeros = interactions(replies=0, quotes=0, reposts=0, likes=0)
        self.assertEqual(rules.score_of(zeros), 0)
        self.assertEqual(rules.eligibility(zeros, 7), (False, "conversation"))
        self.assertEqual(rules.eligibility(zeros, 90), (False, "conversation"))
        kept, dropped = rules.select_neighbours(
            [person(201, "ex_neighbour", replies=0, quotes=0, reposts=0, likes=0)],
            90, "100")
        self.assertEqual(kept, [])
        self.assertEqual(dropped[0]["reason"], "conversation")

    def test_missing_and_negative_counts_are_not_eligible(self):
        for bad in (
            {},
            {"replies": 2, "quotes": 0, "reposts": 0},
            {"replies": 2, "quotes": 0, "reposts": 0, "likes": None},
            {"replies": -1, "quotes": 2, "reposts": 0, "likes": 10},
            {"replies": 2, "quotes": 0, "reposts": -5, "likes": 100},
            {"replies": True, "quotes": 0, "reposts": 0, "likes": 100},
            {"replies": 2.5, "quotes": 0, "reposts": 0, "likes": 100},
            {"replies": "2", "quotes": 0, "reposts": 0, "likes": 100},
        ):
            with self.assertRaises(ValueError):
                rules.counts_of(bad)
            with self.assertRaises(ValueError):
                rules.eligibility(bad, 90)
        rows = [
            person(201, "negative_likes", likes=-10),
            person(202, "negative_replies", replies=-3, likes=100),
            person(203, "float_replies", replies=2.9, likes=100),
            person(204, "true_replies", replies=True, likes=100),
            person(205, "text_likes", likes="100"),
            person(206, "null_likes", likes=None, replies=20),
            {**person(207, "missing_likes", replies=2, likes=0), "likes": None},
        ]
        del rows[-1]["likes"]
        kept, dropped = rules.select_neighbours(rows, 90, "100")
        self.assertEqual(kept, [])
        self.assertEqual({item["user_id"] for item in dropped}, {str(n) for n in range(201, 208)})
        self.assertTrue(all(item["reason"] == "counts" for item in dropped))

    def test_period_bounds_are_seven_and_ninety_three_full_days(self):
        end = rules.parse_time("2026-11-25T00:00:00Z")
        for days, ok in ((6, False), (7, True), (90, True), (93, True), (94, False)):
            start = end - timedelta(days=days)
            self.assertEqual(rules.period_within_bounds(start, end), ok, days)
            self.assertEqual(rules.period_days(start, end), days)
        almost = end - (timedelta(days=7) - timedelta(seconds=1))
        self.assertFalse(rules.period_within_bounds(almost, end))
        self.assertEqual(
            rules.period_span(end - timedelta(hours=6 * 24 + 23), end),
            timedelta(days=6, hours=23))
        self.assertFalse(rules.period_within_bounds(
            end - timedelta(days=6, hours=23), end))
        self.assertFalse(rules.period_within_bounds(
            end - (timedelta(days=93) + timedelta(seconds=1)), end))
        with self.assertRaises(ValueError):
            rules.period_within_bounds(end, end)
        with self.assertRaises(ValueError):
            rules.min_score(0)

    def test_ties_at_the_cap_keep_the_higher_conversation_then_lower_id(self):
        tied = [
            person(user_id, f"n{user_id}", replies=2, likes=54)
            for user_id in range(1, 102)
        ]
        kept, dropped = rules.select_neighbours(tied, 90, "1000")
        self.assertEqual(len(kept), 100)
        self.assertEqual([row["user_id"] for row in kept], [str(n) for n in range(1, 101)])
        self.assertEqual(dropped[0]["user_id"], "101")
        self.assertEqual(dropped[0]["reason"], "cap")

        # Same score, but one person talked more, and one id would win a text sort.
        rows = [
            person(99, "shorter_id", replies=2, likes=54),
            person(100, "longer_id", replies=2, likes=54),
            person(50, "spoke_more", replies=10, likes=30),
            person(1, "higher_score", replies=4, likes=80),
        ]
        self.assertEqual(rules.score_of(interactions(replies=2, likes=54)), 60)
        self.assertEqual(rules.score_of(interactions(replies=10, likes=30)), 60)
        kept, dropped = rules.select_neighbours(rows, 90, "1000", cap=2)
        self.assertEqual([row["user_id"] for row in kept], ["1", "50"])
        self.assertEqual({item["user_id"] for item in dropped}, {"99", "100"})

        kept, _dropped = rules.select_neighbours(
            [person(100, "a", replies=2, likes=54), person(99, "b", replies=2, likes=54)],
            90, "1000", cap=1)
        self.assertEqual(kept[0]["user_id"], "99")

    def test_duplicates_do_not_take_two_cap_slots(self):
        rows = [person(user_id, f"n{user_id}", replies=2, likes=54) for user_id in range(1, 101)]
        rows.append(person(1, "again", replies=9, likes=100))
        kept, dropped = rules.select_neighbours(rows, 90, "1000")
        self.assertEqual(len(kept), 100)
        self.assertEqual(sum(1 for item in dropped if item["reason"] == "cap"), 0)
        self.assertEqual(sum(1 for item in dropped if item["reason"] == "duplicate"), 1)
        self.assertEqual(kept[0]["user_id"], "1")
        self.assertEqual(kept[0]["replies"], 2)

    def test_builder_rejects_a_period_outside_seven_to_ninety_three(self):
        for days in (6, 0, 94, 180):
            with self.assertRaises(ValueError):
                share.build_document(
                    [person(201, "ex_neighbour")], "100", "example_owner",
                    NOW, days, "XN-ABCD2345", "555001")
        for days in (7, 93):
            doc, _dropped, _path = share.build_document(
                [person(201, "ex_neighbour", likes=80, replies=4)],
                "100", "example_owner", NOW, days, "XN-ABCD2345", "555001")
            self.assertTrue(rules.period_within_bounds(doc["period"]["from"], doc["period"]["to"]))


class SubmissionBreakTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        write_build(self.repo)
        self.relpath, self.doc = write_submission(
            self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])

    def tearDown(self):
        shutil.rmtree(self.repo)

    def test_schema_errors(self):
        report = check([], self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        report = check("not-json", self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        missing = json.loads(json.dumps(self.doc))
        del missing["consent"]
        report = check(missing, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        self.assertTrue(any("consent" in item["message"] for item in report.errors))
        extra = json.loads(json.dumps(self.doc))
        extra["surprise"] = True
        report = check(extra, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        bad_format = json.loads(json.dumps(self.doc))
        bad_format["format"] = "neighbours"
        bad_format["version"] = "1"
        report = check(bad_format, self.relpath, now=CLOCK)
        self.assertGreaterEqual(codes(report).count("schema"), 2)
        not_list = json.loads(json.dumps(self.doc))
        not_list["neighbours"] = {"user_id": "201"}
        report = check(not_list, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        extra_count = json.loads(json.dumps(self.doc))
        extra_count["neighbours"][0]["interactions"]["shares"] = 4
        report = check(extra_count, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))

    def test_wrong_extension_is_not_a_submission(self):
        wrong = "submissions/100/2026-11-25T170000Z.json"
        os.makedirs(os.path.join(self.repo, "submissions", "100"), exist_ok=True)
        share.write_json(os.path.join(self.repo, wrong), self.doc)
        report = share.validate_file(os.path.join(self.repo, wrong), self.repo, wrong, now=CLOCK)
        self.assertIn("path", codes(report))
        upper = "submissions/100/2026-11-25T170000Z.NEIGHBOURS"
        report = check(self.doc, upper, now=CLOCK)
        self.assertIn("path", codes(report))
        payload = share.validate_changes(self.repo, [
            {"status": "A", "path": self.relpath},
            {"status": "A", "path": wrong},
        ])
        self.assertFalse(payload["ok"])
        self.assertTrue(any(item["code"] == "files" for item in payload["errors"]))

    def test_bad_user_ids(self):
        for owner_id in ("", "abc", "12.3", "100 ", "+100", "1" * 26, "-1", "0100", "٠٠١"):
            doc = json.loads(json.dumps(self.doc))
            doc["owner"]["user_id"] = owner_id
            report = check(doc, self.relpath, now=CLOCK)
            self.assertTrue(report.errors, owner_id)
            self.assertTrue(
                any(item["code"] in ("schema", "path") for item in report.errors), owner_id)
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["user_id"] = "0201"
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        self.assertEqual(rules.canonical_user_id("100"), "100")
        self.assertEqual(rules.canonical_user_id("0100"), "")
        self.assertEqual(rules.canonical_user_id("0"), "0")

    def test_owner_cannot_list_themselves_by_id_or_handle(self):
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"].append({
            "user_id": "100",
            "handle": "someone_else",
            "interactions": interactions(replies=4, likes=80),
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        })
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("self", codes(report))
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["user_id"] = "999"
        doc["neighbours"][0]["handle"] = "Example_Owner"
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("self", codes(report))
        doc["neighbours"][0]["handle"] = "@example_owner"
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("self", codes(report))

    def test_duplicate_neighbours(self):
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"].append(json.loads(json.dumps(doc["neighbours"][0])))
        doc["neighbours"][1]["handle"] = "other_name"
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        self.assertTrue(any("repeats" in item["message"] for item in report.errors))

    def test_notes_over_140_and_links_and_mentions(self):
        path = os.path.join(self.repo, self.relpath)
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["note"] = "a" * 140
        share.write_json(path, doc)
        self.assertTrue(share.validate_file(path, self.repo, self.relpath, now=CLOCK).ok)
        doc["neighbours"][0]["note"] = "é" * 140
        share.write_json(path, doc)
        self.assertTrue(share.validate_file(path, self.repo, self.relpath, now=CLOCK).ok)
        doc["neighbours"][0]["note"] = "a" * 141
        share.write_json(path, doc)
        self.assertIn("note", codes(share.validate_file(path, self.repo, self.relpath, now=CLOCK)))
        for note in (
            "see https://example.com",
            "see HTTP://example.com/a",
            "see www.example.com",
            "see WWW.Example.com/a",
            "pic t.co/abc",
            "pic T.CO/abc",
            "on x.com/example",
            "on X.COM/example",
            "on twitter.com/example",
            "hello @ex_neighbour",
            "hello @A",
            "hello \uff20ex_neighbour",
            "name@example.com",
            "  padded",
            "",
            "follow for follow",
        ):
            doc["neighbours"][0]["note"] = note
            share.write_json(path, doc)
            report = share.validate_file(path, self.repo, self.relpath, now=CLOCK)
            self.assertIn("note", codes(report), note)
        doc["neighbours"][0]["note"] = "a neighbour who replies"
        share.write_json(path, doc)
        self.assertTrue(share.validate_file(path, self.repo, self.relpath, now=CLOCK).ok)

    def test_more_than_three_tags(self):
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["tags"] = ["one", "two", "three"]
        self.assertNotIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["one", "two", "three", "four"]
        self.assertIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["one", "one"]
        self.assertIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["One"]
        self.assertIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["a" * 24]
        self.assertNotIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["a" * 25]
        self.assertIn("tag", codes(check(doc, self.relpath, now=CLOCK)))
        doc["neighbours"][0]["tags"] = ["ok-tag", "@nope", ""]
        self.assertIn("tag", codes(check(doc, self.relpath, now=CLOCK)))

    def test_path_must_match_the_owner_user_id(self):
        doc = json.loads(json.dumps(self.doc))
        doc["owner"]["user_id"] = "200"
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("path", codes(report))
        report = share.validate_file(
            os.path.join(self.repo, self.relpath), self.repo, self.relpath, now=CLOCK)
        # The file on disk still has owner 100, matching the folder.
        self.assertTrue(report.ok, report.errors)
        mismatched = json.loads(json.dumps(self.doc))
        mismatched["owner"]["user_id"] = "200"
        share.write_json(os.path.join(self.repo, self.relpath), mismatched)
        report = share.validate_file(
            os.path.join(self.repo, self.relpath), self.repo, self.relpath, now=CLOCK)
        self.assertIn("path", codes(report))

    def test_timestamps_in_the_future_fail(self):
        future = "2026-11-25T17:00:01Z"
        doc = json.loads(json.dumps(self.doc))
        doc["submitted_at"] = future
        relpath = rules.submission_relpath("100", future)
        report = check(doc, relpath, now=NOW)
        self.assertIn("future", codes(report))
        self.assertTrue(any("submitted_at" in item["message"] for item in report.errors))
        # The same instant is allowed. One second earlier is allowed.
        doc["submitted_at"] = NOW
        report = check(doc, self.relpath, now=NOW)
        self.assertNotIn("future", codes(report))
        report = check(self.doc, self.relpath, now="2026-11-25T17:00:01Z")
        self.assertNotIn("future", codes(report))

        later_period = json.loads(json.dumps(self.doc))
        end = rules.parse_time(later_period["period"]["to"]) + timedelta(seconds=1)
        later_period["period"]["to"] = rules.iso(end)
        report = check(later_period, self.relpath, now=NOW)
        self.assertIn("future", codes(report))

        ahead = json.loads(json.dumps(self.doc))
        ahead["neighbours"][0]["first_seen"] = "2099-01-01T00:00:00Z"
        report = check(ahead, self.relpath, now=CLOCK)
        self.assertIn("future", codes(report))
        self.assertTrue(any("first_seen" in item["message"] for item in report.errors))
        ahead["neighbours"][0]["first_seen"] = "2026-09-01T00:00:00Z"
        ahead["neighbours"][0]["last_seen"] = "2099-01-01T00:00:00Z"
        report = check(ahead, self.relpath, now=CLOCK)
        self.assertIn("future", codes(report))
        self.assertTrue(any("last_seen" in item["message"] for item in report.errors))

    def test_period_shorter_than_seven_or_longer_than_ninety_three_fails(self):
        end = rules.parse_time(self.doc["period"]["to"])
        for delta, ok in (
            (timedelta(days=7), True),
            (timedelta(days=7) - timedelta(seconds=1), False),
            (timedelta(days=6, hours=23), False),
            (timedelta(days=6), False),
            (timedelta(days=93), True),
            (timedelta(days=93) + timedelta(seconds=1), False),
            (timedelta(days=94), False),
        ):
            doc = json.loads(json.dumps(self.doc))
            doc["period"]["from"] = rules.iso(end - delta)
            doc["period"]["to"] = rules.iso(end)
            # Keep the neighbour eligible at the stricter 93-day bar too.
            doc["neighbours"][0]["interactions"] = interactions(replies=4, likes=80)
            report = check(doc, self.relpath, now=CLOCK)
            if ok:
                self.assertNotIn("schema", codes(report), delta)
                self.assertTrue(report.ok, report.errors)
            else:
                self.assertIn("schema", codes(report), delta)
                self.assertTrue(any("period must cover" in item["message"] for item in report.errors))

    def test_score_49_and_50_are_checked_again_on_the_file(self):
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["interactions"] = interactions(replies=2, likes=43)
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("eligibility", codes(report))
        doc["neighbours"][0]["interactions"] = interactions(replies=2, likes=44)
        report = check(doc, self.relpath, now=CLOCK)
        self.assertTrue(report.ok, report.errors)
        doc["neighbours"][0]["interactions"] = interactions(replies=1, quotes=0, likes=100)
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("eligibility", codes(report))
        doc["neighbours"][0]["interactions"] = interactions(replies=1, quotes=1, likes=44)
        report = check(doc, self.relpath, now=CLOCK)
        self.assertTrue(report.ok, report.errors)

    def test_negative_counts_in_the_file_fail_schema(self):
        doc = json.loads(json.dumps(self.doc))
        doc["neighbours"][0]["interactions"]["likes"] = -1
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))
        doc["neighbours"][0]["interactions"] = {"replies": 2, "quotes": 0, "reposts": 0}
        report = check(doc, self.relpath, now=CLOCK)
        self.assertIn("schema", codes(report))

    def test_edits_and_deletes_of_neighbours_files_are_rejected(self):
        for status, path in (
            ("M", self.relpath),
            ("D", self.relpath),
            ("R", "submissions/100/2026-11-26T170000Z.neighbours"),
            ("C", "founding/other.neighbours"),
            ("M", "founding/2026-11-25T000000Z.neighbours"),
        ):
            payload = share.validate_changes(self.repo, [{"status": status, "path": path}])
            self.assertFalse(payload["ok"], status)
            self.assertTrue(any(item["code"] == "history" for item in payload["errors"]), status)
            self.assertFalse(payload["share"])
        added = share.validate_changes(self.repo, [{"status": "A", "path": self.relpath}])
        self.assertTrue(added["ok"], added["errors"])
        self.assertTrue(added["share"])
        replaced = share.validate_changes(self.repo, [
            {"status": "D", "path": "submissions/100/2026-11-01T000000Z.neighbours"},
            {"status": "A", "path": self.relpath},
        ])
        self.assertFalse(replaced["ok"])
        self.assertTrue(any(item["code"] == "history" for item in replaced["errors"]))
        self.assertFalse(replaced["share"])


class IntervalBreakTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        write_build(self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo)

    def file_at(self, when, owner="100", handle="example_owner"):
        return write_submission(
            self.repo, owner, handle, when, [person(201, "ex_neighbour")])

    def test_a_second_file_does_not_have_to_wait(self):
        self.file_at("2026-03-01T12:00:00Z")
        relpath, _doc = self.file_at("2026-03-01T13:00:00Z")
        report = share.validate_file(
            os.path.join(self.repo, relpath), self.repo, relpath, now=CLOCK)
        self.assertTrue(report.ok, report.errors)
        self.assertNotIn("interval", codes(report))

    def test_multiple_files_in_one_pull_request_fail(self):
        first, _doc = self.file_at("2026-03-01T12:00:00Z", owner="100")
        second, _doc = write_submission(
            self.repo, "200", "second_owner", "2026-03-01T12:00:00Z",
            [person(202, "other_neighbour")])
        third, _doc = write_submission(
            self.repo, "300", "third_owner", "2026-03-08T12:00:00Z",
            [person(203, "third_neighbour")])
        payload = share.validate_changes(self.repo, [
            {"status": "A", "path": first},
            {"status": "A", "path": second},
        ])
        self.assertFalse(payload["ok"])
        self.assertTrue(any(item["code"] == "files" for item in payload["errors"]))
        self.assertEqual(len(payload["added"]), 2)
        payload = share.validate_changes(self.repo, [
            {"status": "A", "path": first},
            {"status": "A", "path": second},
            {"status": "A", "path": third},
        ])
        self.assertFalse(payload["ok"])
        self.assertGreaterEqual(
            sum(1 for item in payload["errors"] if item["code"] == "files"), 1)
        # Same owner, a week apart, still one file per pull request.
        later, _doc = self.file_at("2026-03-08T12:00:00Z", owner="100")
        payload = share.validate_changes(self.repo, [
            {"status": "A", "path": first},
            {"status": "A", "path": later},
        ])
        self.assertFalse(payload["ok"])
        self.assertTrue(any(item["code"] == "files" for item in payload["errors"]))

    def test_file_stamp_uses_utc(self):
        previous = "2026-03-01T12:00:00Z"
        exact_local = "2026-03-08T13:00:00+01:00"
        self.assertEqual(rules.iso(exact_local), "2026-03-08T12:00:00Z")
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", previous, [person(201, "ex_neighbour")])
        doc["submitted_at"] = exact_local
        matched = rules.submission_relpath("100", exact_local)
        self.assertTrue(matched.endswith("2026-03-08T120000Z.neighbours"))
        report = check(doc, matched, repo=self.repo, now=CLOCK)
        self.assertTrue(report.ok, report.errors)
        report = check(doc, relpath, repo=self.repo, now=CLOCK)
        self.assertIn("path", codes(report))


class GlobalBuildBreakTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        write_build(self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo)

    def rebuild(self):
        return global_build.build(self.repo, "abc123", "2026-11-25T18:00:00Z")

    def set_waiver(self, path):
        doc = share.read_json(os.path.join(self.repo, "global", "build.json"))
        doc["founding_waiver"]["submission"] = path
        share.write_json(os.path.join(self.repo, "global", "build.json"), doc)

    def test_two_distinct_owners_are_required_and_one_owner_is_not_counted_twice(self):
        write_submission(self.repo, "100", "example_owner", "2026-11-01T12:00:00Z", [
            person(201, "old_name", likes=44),
            person(202, "only_old"),
        ])
        write_submission(self.repo, "100", "renamed_owner", "2026-11-20T12:00:00Z", [
            person(201, "mid_name", likes=70),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.assertEqual(document["owners"]["100"]["handle"], "renamed_owner")
        self.assertEqual(
            document["owners"]["100"]["latest_submission"],
            rules.submission_relpath("100", "2026-11-20T12:00:00Z"))
        write_submission(self.repo, "200", "second_owner", "2026-11-21T12:00:00Z", [
            person(201, "new_name", likes=80),
            person(202, "only_old"),
        ])
        document, _summary = self.rebuild()
        self.assertIn("202", document["neighbours"])
        dropped = document["neighbours"]["202"]
        self.assertEqual(dropped["recommendation_count"], 2)
        self.assertEqual(
            [item["owner_id"] for item in dropped["recommended_by"]], ["100", "200"])
        row = document["neighbours"]["201"]
        self.assertEqual(row["recommendation_count"], 2)
        self.assertEqual(row["handle"], "new_name")
        owners = [item["owner_id"] for item in row["recommended_by"]]
        self.assertEqual(owners, ["100", "200"])
        by_owner = {item["owner_id"]: item for item in row["recommended_by"]}
        self.assertEqual(by_owner["100"]["owner_handle"], "renamed_owner")
        self.assertEqual(by_owner["100"]["recommended_at"], "2026-11-20T12:00:00Z")
        self.assertEqual(
            by_owner["100"]["submission"],
            rules.submission_relpath("100", "2026-11-20T12:00:00Z"))
        self.assertEqual(by_owner["200"]["owner_handle"], "second_owner")
        self.assertEqual(by_owner["200"]["recommended_at"], "2026-11-21T12:00:00Z")
        self.assertEqual(row["first_recommended"], "2026-11-20T12:00:00Z")
        self.assertEqual(row["last_recommended"], "2026-11-21T12:00:00Z")
        self.assertEqual(row["source"], "community")

    def test_removing_someone_from_the_latest_file_drops_them(self):
        write_submission(self.repo, "100", "example_owner", "2026-11-01T12:00:00Z", [
            person(201, "kept"), person(202, "dropped_later"),
        ])
        write_submission(self.repo, "200", "second_owner", "2026-11-02T12:00:00Z", [
            person(201, "kept"), person(202, "dropped_later"),
        ])
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertIn("202", document["neighbours"])
        write_submission(self.repo, "100", "example_owner", "2026-11-20T12:00:00Z", [
            person(201, "kept"),
        ])
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertEqual(document["neighbours"]["201"]["recommendation_count"], 2)
        self.assertIn("202", document["neighbours"])
        self.assertEqual(document["neighbours"]["202"]["recommendation_count"], 2)

    def test_handle_changes_stay_under_the_same_user_id(self):
        write_submission(self.repo, "100", "old_owner", "2026-11-01T12:00:00Z", [
            person(201, "old_handle"),
        ])
        write_submission(self.repo, "200", "second_owner", "2026-11-10T12:00:00Z", [
            person(201, "new_handle", likes=80),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(list(document["neighbours"]), ["201"])
        self.assertEqual(document["neighbours"]["201"]["handle"], "new_handle")
        self.assertNotIn("old_handle", json.dumps(document["neighbours"]))
        write_submission(self.repo, "100", "new_owner", "2026-11-20T12:00:00Z", [
            person(201, "newer_handle", likes=90),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(document["owners"]["100"]["handle"], "new_owner")
        self.assertEqual(list(document["owners"]), ["100", "200"])
        self.assertEqual(document["neighbours"]["201"]["handle"], "newer_handle")
        self.assertEqual(document["neighbours"]["201"]["recommendation_count"], 2)

    def test_opt_outs_and_banned_owners(self):
        write_submission(self.repo, "100", "example_owner", NOW, [
            person(201, "opted"), person(202, "stays"),
        ])
        write_submission(self.repo, "200", "second_owner", NOW, [
            person(201, "opted"), person(202, "stays"),
        ])
        write_submission(self.repo, "300", "banned_owner", NOW, [
            person(203, "from_banned"), person(202, "stays", likes=90),
        ])
        os.makedirs(os.path.join(self.repo, "opted-out"), exist_ok=True)
        os.makedirs(os.path.join(self.repo, "banned"), exist_ok=True)
        share.write_json(os.path.join(self.repo, "opted-out", "accounts.json"), {"accounts": ["201"]})
        share.write_json(os.path.join(self.repo, "banned", "owners.json"), {"owners": ["300"]})
        document, _summary = self.rebuild()
        self.assertNotIn("201", document["neighbours"])
        self.assertNotIn("203", document["neighbours"])
        self.assertIn("202", document["neighbours"])
        owners = {item["owner_id"] for item in document["neighbours"]["202"]["recommended_by"]}
        self.assertEqual(owners, {"100", "200"})
        self.assertEqual(document["neighbours"]["202"]["recommendation_count"], 2)
        self.assertIn("201", document["opted_out"])
        self.assertEqual(document["owners"]["300"]["status"], "banned")
        self.assertEqual(document["banned_owners"], ["300"])

    def test_founding_waiver_is_only_the_exact_path_and_the_credit_is_neutral(self):
        waiver = "founding/one.neighbours"
        doc, _dropped, _relpath = share.build_document(
            [person(201, "ex_neighbour"), person(100, "example_owner", replies=4, likes=80)],
            "100", "example_owner", "2026-11-01T12:00:00Z", 90, "XN-ABCD2345", "555001")
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, waiver), doc)
        other = json.loads(json.dumps(doc))
        other["neighbours"] = [{
            "user_id": "404",
            "handle": "not_waived",
            "interactions": interactions(replies=4, likes=80),
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        }]
        share.write_json(os.path.join(self.repo, "founding", "another.neighbours"), other)
        self.set_waiver("")
        document, summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.assertEqual(summary["waiver"], "")
        self.set_waiver("   ")
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.set_waiver(waiver)
        document, summary = self.rebuild()
        self.assertEqual(summary["founding"], 1)
        self.assertEqual(list(document["neighbours"]), ["201"])
        row = document["neighbours"]["201"]
        self.assertEqual(row["source"], "founding")
        self.assertEqual(row["recommendation_count"], 1)
        credit = row["recommended_by"][0]
        self.assertEqual(credit, {
            "owner_id": "founding",
            "owner_handle": "founding-submission",
            "recommended_at": "2026-11-01T12:00:00Z",
            "submission": waiver,
        })
        self.assertNotIn("example_owner", json.dumps(row))
        self.assertNotIn("100", json.dumps(row))
        self.assertNotIn("404", document["neighbours"])

    def test_empty_waiver_ignores_a_decoy_and_a_second_file_is_not_waived(self):
        first = "founding/one.neighbours"
        doc, _dropped, _path = share.build_document(
            [person(201, "ex_neighbour")],
            "100", "example_owner", "2026-11-01T12:00:00Z", 90, "XN-ABCD2345", "555001")
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, first), doc)
        self.set_waiver("")
        write_submission(self.repo, "100", "example_owner", "2026-11-20T12:00:00Z", [
            person(404, "only_on_second"),
            person(201, "ex_neighbour"),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.set_waiver(first)
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertNotIn("404", document["neighbours"])
        self.assertEqual(document["neighbours"]["201"]["source"], "founding")
        credits = document["neighbours"]["201"]["recommended_by"]
        self.assertEqual([item["owner_id"] for item in credits], ["founding", "100"])
        self.assertEqual(credits[0]["owner_handle"], "founding-submission")
        self.assertEqual(credits[0]["submission"], first)
        self.assertNotEqual(credits[1]["owner_handle"], "founding-submission")

    def test_later_owners_append_to_a_founding_account(self):
        waiver = "founding/one.neighbours"
        doc, _dropped, _path = share.build_document(
            [person(201, "old_handle")],
            "100", "example_owner", "2026-11-10T12:00:00Z", 90, "XN-ABCD2345", "555001")
        os.makedirs(os.path.join(self.repo, "founding"))
        share.write_json(os.path.join(self.repo, waiver), doc)
        self.set_waiver(waiver)
        # An earlier owner still appends, ordered by time, and does not replace founding.
        write_submission(self.repo, "200", "early_owner", "2026-11-01T12:00:00Z", [
            person(201, "early_handle", likes=60),
        ])
        write_submission(self.repo, "300", "later_owner", "2026-11-20T12:00:00Z", [
            person(201, "new_handle", likes=90),
        ])
        document, _summary = self.rebuild()
        row = document["neighbours"]["201"]
        self.assertEqual(row["source"], "founding")
        self.assertEqual(row["recommendation_count"], 3)
        self.assertEqual(row["handle"], "new_handle")
        self.assertEqual(
            [item["owner_id"] for item in row["recommended_by"]],
            ["200", "founding", "300"])
        self.assertEqual(row["recommended_by"][1]["owner_handle"], "founding-submission")
        self.assertEqual(row["recommended_by"][1]["submission"], waiver)
        self.assertEqual(row["recommended_by"][1]["recommended_at"], "2026-11-10T12:00:00Z")
        self.assertEqual(row["recommended_by"][0]["recommended_at"], "2026-11-01T12:00:00Z")
        self.assertEqual(row["recommended_by"][2]["owner_handle"], "later_owner")
        self.assertEqual(row["recommended_by"][2]["recommended_at"], "2026-11-20T12:00:00Z")
        self.assertEqual(row["first_recommended"], "2026-11-01T12:00:00Z")
        self.assertEqual(row["last_recommended"], "2026-11-20T12:00:00Z")
        self.assertNotIn("example_owner", json.dumps(row["recommended_by"]))

    def test_output_is_deterministic(self):
        write_submission(self.repo, "200", "second_owner", "2026-11-02T12:00:00Z", [
            person(301, "b_person"), person(201, "a_person", likes=70),
        ])
        write_submission(self.repo, "100", "example_owner", "2026-11-01T12:00:00Z", [
            person(201, "a_person"), person(301, "b_person", likes=80),
        ])
        first, summary_one = self.rebuild()
        second, summary_two = self.rebuild()
        self.assertEqual(first, second)
        self.assertEqual(summary_one, summary_two)
        self.assertEqual(list(first["neighbours"]), ["201", "301"])
        self.assertEqual(list(first["owners"]), ["100", "200"])
        text_one = json.dumps(first, ensure_ascii=False, indent=2)
        text_two = json.dumps(second, ensure_ascii=False, indent=2)
        self.assertEqual(text_one, text_two)
        again, _summary = global_build.build(self.repo, "abc123", "2026-11-25T18:00:00Z")
        self.assertEqual(again, first)

    def test_ineligible_rows_do_not_enter_even_when_two_owners_agree(self):
        weak = person(201, "likes_only", replies=0, quotes=0, likes=500)
        write_submission(self.repo, "100", "example_owner", NOW, [person(202, "real")])
        # build_document drops the likes-only row, so put it back by hand.
        relpath = rules.submission_relpath("100", NOW)
        doc = share.read_json(os.path.join(self.repo, relpath))
        doc["neighbours"].append({
            "user_id": "201",
            "handle": "likes_only",
            "interactions": interactions(replies=0, quotes=0, likes=500),
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-11-20T00:00:00Z",
        })
        share.write_json(os.path.join(self.repo, relpath), doc)
        write_submission(self.repo, "200", "second_owner", NOW, [weak, person(202, "real")])
        other = rules.submission_relpath("200", NOW)
        second = share.read_json(os.path.join(self.repo, other))
        second["neighbours"].insert(0, json.loads(json.dumps(doc["neighbours"][-1])))
        share.write_json(os.path.join(self.repo, other), second)
        document, _summary = self.rebuild()
        self.assertNotIn("201", document["neighbours"])
        self.assertIn("202", document["neighbours"])


class AbuseBreakTest(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp()
        self.repo = os.path.join(self.parent, "repo")
        os.makedirs(self.repo)
        write_build(self.repo)

    def tearDown(self):
        shutil.rmtree(self.parent)

    def rebuild(self):
        return global_build.build(self.repo, "abc123", "2026-11-25T18:00:00Z")

    def test_many_tiny_owners_do_not_fill_the_list_unless_two_agree(self):
        early = "2026-11-01T12:00:00Z"
        for owner in range(1000, 1040):
            write_submission(
                self.repo, str(owner), f"owner{owner}", early,
                [person(5000 + owner, f"solo{owner}")])
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.assertEqual(len(document["owners"]), 40)
        write_submission(self.repo, "1000", "owner1000", "2026-11-20T12:00:00Z", [
            person(900, "shared_person"),
        ])
        write_submission(self.repo, "1001", "owner1001", "2026-11-21T12:00:00Z", [
            person(900, "shared_person"),
        ])
        document, _summary = self.rebuild()
        self.assertEqual(list(document["neighbours"]), ["900"])
        self.assertEqual(document["neighbours"]["900"]["recommendation_count"], 2)

    def test_a_lower_minimum_in_build_json_cannot_make_one_owner_enough(self):
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        for minimum in (0, 1, -3, "1", "nope", None):
            doc = share.read_json(os.path.join(self.repo, "global", "build.json"))
            doc["min_recommendations"] = minimum
            share.write_json(os.path.join(self.repo, "global", "build.json"), doc)
            document, _summary = self.rebuild()
            self.assertEqual(document["neighbours"], {}, minimum)
            self.assertGreaterEqual(document["min_recommendations"], 2)
            self.assertNotIn("submission_interval_days", document)
            self.assertNotIn("next_allowed_at", document["owners"]["100"])

    def test_leading_zero_ids_are_not_a_second_owner(self):
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        relpath, doc = write_submission(
            self.repo, "100", "example_owner", "2026-11-01T12:00:00Z", [person(201, "ex_neighbour")])
        alias = json.loads(json.dumps(doc))
        alias["owner"]["user_id"] = "0100"
        alias["submitted_at"] = "2026-11-02T12:00:00Z"
        folder = os.path.join(self.repo, "submissions", "0100")
        os.makedirs(folder)
        share.write_json(os.path.join(folder, "2026-11-02T120000Z.neighbours"), alias)
        # A second real owner is still required. The aliased folder must not supply it.
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"], {})
        self.assertNotIn("0100", document["owners"])
        write_submission(self.repo, "200", "second_owner", NOW, [
            person(201, "ex_neighbour"),
            person("0201", "alias_neighbour", replies=4, likes=80),
        ])
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertNotIn("0201", document["neighbours"])
        self.assertEqual(document["neighbours"]["201"]["recommendation_count"], 2)

    def test_a_string_of_tags_is_not_split_into_letters(self):
        write_submission(self.repo, "100", "example_owner", NOW, [person(201, "ex_neighbour")])
        write_submission(self.repo, "200", "second_owner", NOW, [person(201, "ex_neighbour")])
        for owner in ("100", "200"):
            path = os.path.join(self.repo, rules.submission_relpath(owner, NOW))
            doc = share.read_json(path)
            doc["neighbours"][0]["tags"] = "art"
            share.write_json(path, doc)
        document, _summary = self.rebuild()
        self.assertEqual(document["neighbours"]["201"]["tags"], {})

    def test_waiver_traversal_does_not_read_outside_the_repo(self):
        outside = os.path.join(self.parent, "secret.neighbours")
        secret, _dropped, _path = share.build_document(
            [person(777001, "outside_person", replies=4, likes=80)],
            "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
        share.write_json(outside, secret)
        planted = os.path.join(self.repo, "secret.neighbours")
        planted_doc = json.loads(json.dumps(secret))
        planted_doc["neighbours"][0]["user_id"] = "777002"
        planted_doc["neighbours"][0]["handle"] = "planted_person"
        share.write_json(planted, planted_doc)
        os.makedirs(os.path.join(self.repo, "founding"))
        real, _dropped, _path = share.build_document(
            [person(201, "ex_neighbour")],
            "100", "example_owner", NOW, 90, "XN-ABCD2345", "555001")
        share.write_json(os.path.join(self.repo, "founding", "one.neighbours"), real)
        os.symlink(outside, os.path.join(self.repo, "founding", "link.neighbours"))
        attacks = (
            "../secret.neighbours",
            "..\\secret.neighbours",
            "founding/../../secret.neighbours",
            "founding/../../../etc/passwd",
            "....//founding/one.neighbours",
            "founding/../founding/one.neighbours",
            "founding/./one.neighbours",
            "/etc/passwd",
            "founding/one.neighbours\x00.neighbours",
            "founding/link.neighbours",
        )
        build_path = os.path.join(self.repo, "global", "build.json")
        for attack in attacks:
            doc = share.read_json(build_path)
            doc["founding_waiver"]["submission"] = attack
            share.write_json(build_path, doc)
            document, summary = self.rebuild()
            self.assertNotIn("777001", document["neighbours"], attack)
            self.assertNotIn("777002", document["neighbours"], attack)
            self.assertNotIn("201", document["neighbours"], attack)
            self.assertEqual(summary["waiver"], "", attack)
            self.assertTrue(summary["warnings"], attack)
        doc = share.read_json(build_path)
        doc["founding_waiver"]["submission"] = "./founding/one.neighbours"
        share.write_json(build_path, doc)
        document, summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertEqual(summary["waiver"], "founding/one.neighbours")
        self.assertEqual(
            document["neighbours"]["201"]["recommended_by"][0]["owner_handle"],
            "founding-submission")
        doc["founding_waiver"]["submission"] = "founding/one.neighbours"
        share.write_json(build_path, doc)
        document, _summary = self.rebuild()
        self.assertIn("201", document["neighbours"])
        self.assertNotIn("777001", document["neighbours"])

    def test_boost_rings_of_closed_lists_are_flagged_and_not_rejected(self):
        self.assertFalse(neighbour_dog.detect_boost_ring([]))
        self.assertFalse(neighbour_dog.detect_boost_ring([["1", "2", "3"]]))
        # Two accounts that only list each other are below the size of 3.
        self.assertFalse(neighbour_dog.detect_boost_ring([["20"], ["10"]]))
        self.assertFalse(neighbour_dog.detect_boost_ring([["1", "2"], ["1", "2"], ["1", "2"]]))
        # Exactly 80 percent, and those accounts appear on no other list.
        self.assertTrue(neighbour_dog.detect_boost_ring([
            ["1", "2", "3", "4", "5"],
            ["1", "2", "3", "4", "9"],
        ]))
        self.assertFalse(neighbour_dog.detect_boost_ring([
            ["1", "2", "3", "4", "5"],
            ["1", "2", "3", "8", "9"],
        ]))
        # A third list that shares the overlap is not an outside audience.
        self.assertFalse(neighbour_dog.detect_boost_ring([
            ["1", "2", "3", "4", "5"],
            ["1", "2", "3", "4", "9"],
            ["1", "8", "7"],
        ]))
        # Three identical lists used to hide, because each pair's overlap
        # also appears on the third list.
        self.assertTrue(neighbour_dog.detect_boost_ring([
            ["1", "2", "3", "4"],
            ["1", "2", "3", "4"],
            ["1", "2", "3", "4"],
        ]))
        # Each list is the other members of the ring and nobody else.
        self.assertTrue(neighbour_dog.detect_boost_ring([
            ["2", "3", "4"],
            ["1", "3", "4"],
            ["1", "2", "4"],
            ["1", "2", "3"],
        ]))
        # The same ring stops being closed once an outside list shares someone.
        self.assertFalse(neighbour_dog.detect_boost_ring([
            ["2", "3", "4"],
            ["1", "3", "4"],
            ["1", "2", "4"],
            ["1", "2", "3"],
            ["1", "8", "9"],
        ]))
        validation = {
            "ok": True, "errors": [], "neighbours": 4, "share": True,
        }
        context = {
            "prior_count": 2, "owner_age_days": 200, "recent_original_posts": 3,
            "action_green": True, "boost_ring": True,
        }
        result = neighbour_dog.decide(validation, context)
        self.assertEqual(result["decision"], "flag")
        self.assertFalse(result["merge"])


class VersionBreakTest(unittest.TestCase):
    def test_semver_orders_3_0_0_and_3_0_10_as_numbers(self):
        self.assertTrue(rules.SEMVER_RE.fullmatch("3.0.10"))
        import version as version_mod
        self.assertTrue(version_mod.is_newer("3.0.10", "3.0.9"))
        self.assertTrue(version_mod.is_newer("3.0.10", "3.0.2"))
        self.assertFalse(version_mod.is_newer("3.0.2", "3.0.10"))
        self.assertTrue(version_mod.is_newer("3.1.0", "3.0.10"))
        self.assertTrue(version_mod.is_newer("10.0.0", "9.9.9"))
        same = release(3, 0, 0)
        patch = release(3, 0, 10)
        self.assertFalse(version_mod.is_newer(same, same))
        self.assertFalse(version_mod.is_newer(same, patch))
        self.assertEqual(version_mod.parse_semver("3.0.10"), (3, 0, 10))
        padded = "0" + release(3, 0, 10)
        self.assertEqual(version_mod.parse_semver(padded), (3, 0, 10))
        self.assertFalse(version_mod.is_newer(padded, release(3, 0, 10)))
        for bad in ("3.0.10-rc.1", "3.0.10-alpha", "v3.0.10", "3.0", "3", "", "3.0.10+meta", None):
            with self.assertRaises(ValueError):
                version_mod.parse_semver(bad)

    def test_a_bad_version_does_not_upgrade_and_minimum_is_reported(self):
        import version as version_mod
        base = release(3, 0, 0)
        patch = release(3, 0, 10)
        remote = {
            "version": patch,
            "min_compatible_version": base,
            "changelog": "Patch ten.",
            "source_commit": "abc",
        }
        asked = community.check_update(True, base, remote)
        self.assertTrue(asked["ask"])
        self.assertFalse(asked["behind_minimum"])
        self.assertFalse(asked["upgrade"])
        self.assertFalse(asked["pull"])
        self.assertFalse(asked["executed"])
        higher_min = dict(remote, min_compatible_version=patch)
        behind = community.check_update(True, base, higher_min)
        self.assertTrue(behind["ask"])
        self.assertTrue(behind["behind_minimum"])
        self.assertIn(patch, behind["message"])
        self.assertFalse(behind["pull"])
        same = community.check_update(True, patch, remote)
        self.assertFalse(same["ask"])
        self.assertFalse(same["newer"])
        self.assertFalse(same["pull"])
        older_remote = dict(remote, version=base, min_compatible_version=base)
        no_downgrade = community.check_update(True, patch, older_remote)
        self.assertFalse(no_downgrade["ask"])
        self.assertFalse(no_downgrade["pull"])
        met = community.check_update(
            True, release(3, 0, 9), dict(remote, min_compatible_version=base))
        self.assertTrue(met["ask"])
        self.assertFalse(met["behind_minimum"])
        for bad_remote in (
            release(3, 0, 10, "-rc.1"),
            "v" + patch,
            "3.0",
            release(3, 0, 10, "+meta"),
        ):
            result = community.check_update(True, base, dict(remote, version=bad_remote))
            self.assertFalse(result["ok"], bad_remote)
            self.assertFalse(result["ask"], bad_remote)
            self.assertFalse(result["pull"], bad_remote)
            self.assertFalse(result["upgrade"], bad_remote)
        bad_min = community.check_update(
            True, base, dict(remote, min_compatible_version=release(3, 0, 10, "-rc.1")))
        self.assertFalse(bad_min["ok"])
        self.assertFalse(bad_min["pull"])
        bad_local = community.check_update(True, "v" + base, remote)
        self.assertFalse(bad_local["ok"])
        self.assertFalse(bad_local["pull"])
        declined = community.check_update(True, base, remote, declined_version=patch)
        self.assertFalse(declined["ask"])
        self.assertFalse(declined["pull"])
        for answer in ("no", "later", "YES please", "", None, "true"):
            decision = community.decide_upgrade(answer, "3.0.10")
            self.assertFalse(decision["pull"], answer)
            self.assertFalse(decision["executed"], answer)
        agreed = community.decide_upgrade("yes", "3.0.10")
        self.assertTrue(agreed["pull"])
        self.assertFalse(agreed["executed"])
        self.assertNotIn("git", json.dumps({k: v for k, v in agreed.items() if k != "steps"}))

    def test_individual_mode_never_checks_even_when_forced(self):
        class Boom:
            def get(self, *_args, **_kwargs):
                raise AssertionError("individual mode read versions/latest.json")

        result = community.check_update(False, release(3, 0, 0), Boom(), force=True)
        self.assertFalse(result["check"])
        self.assertFalse(result["read_versions"])
        self.assertFalse(result["ask"])
        self.assertFalse(result["pull"])
        plan = community.weekly_plan(False)
        self.assertFalse(plan["fetch_versions"])
        self.assertFalse(plan["fetch_global"])
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "community.json")
            missing = os.path.join(folder, "missing-latest.json")
            with redirect_stdout(io.StringIO()):
                code = community.run(argparse_namespace(
                    file=path, cmd="check-update", latest=missing, local=None, force=True))
            self.assertEqual(code, 0)
            self.assertFalse(os.path.exists(missing))
        finally:
            shutil.rmtree(folder)

    def test_monday_release_guard_uses_utc(self):
        monday = datetime(2026, 11, 30, 12, 0, tzinfo=timezone.utc)
        for offset in range(7):
            when = monday + timedelta(days=offset)
            if offset == 0:
                self.assertEqual(versions_release.assert_monday(when), when.astimezone(timezone.utc))
            else:
                with self.assertRaises(ValueError):
                    versions_release.assert_monday(when)
        with self.assertRaises(ValueError):
            versions_release.assert_monday("2026-11-29T23:59:59Z")
        versions_release.assert_monday("2026-11-30T00:00:00Z")
        versions_release.assert_monday("2026-11-30T23:59:59Z")
        with self.assertRaises(ValueError):
            versions_release.assert_monday("2026-12-01T00:00:00Z")
        # Monday evening in New York is already Tuesday in UTC.
        with self.assertRaises(ValueError):
            versions_release.assert_monday("2026-11-30T20:00:00-05:00")
        # Sunday evening in New York is already Monday in UTC.
        versions_release.assert_monday("2026-11-29T20:00:00-05:00")
        # Monday 00:30 in UTC+1 is still Sunday in UTC.
        with self.assertRaises(ValueError):
            versions_release.assert_monday("2026-11-30T00:30:00+01:00")

        repo = tempfile.mkdtemp()
        try:
            with open(os.path.join(repo, "VERSION"), "w", encoding="utf-8") as fh:
                fh.write("1.2.3\n")
            with self.assertRaises(ValueError):
                versions_release.write_release(repo, "2026-11-25T14:00:00Z", "notes", "abc")
            self.assertFalse(os.path.exists(os.path.join(repo, "versions", "latest.json")))
            with self.assertRaises(ValueError):
                versions_release.write_release(
                    repo, "2026-11-30T14:00:00Z", "notes", "abc", min_compatible="9.0.0")
            self.assertFalse(os.path.exists(os.path.join(repo, "versions", "latest.json")))
            with self.assertRaises(ValueError):
                versions_release.write_release(
                    repo, "2026-11-30T14:00:00Z", "notes", "abc", min_compatible="1.2.3-rc.1")
            document = versions_release.write_release(
                repo, "2026-11-30T14:00:00Z", "notes", "abc", min_compatible="1.2.0")
            self.assertEqual(document["min_compatible_version"], "1.2.0")
            self.assertEqual(document["version"], "1.2.3")
            with open(os.path.join(repo, "versions", "latest.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["min_compatible_version"], "1.2.0")
        finally:
            shutil.rmtree(repo)

        with open(os.path.join(ROOT, ".github", "workflows", "monday-release.yml"), encoding="utf-8") as fh:
            workflow = fh.read()
        self.assertIn("versions_release.py", workflow)
        self.assertIn("date -u", workflow)
        self.assertNotIn("2026-11-30", workflow)
        with open(os.path.join(ROOT, ".github", "workflows", "rebuild-global.yml"), encoding="utf-8") as fh:
            rebuild = fh.read()
        self.assertNotIn("versions_release", rebuild)
        self.assertNotIn("versions/latest.json", rebuild)


def release(major, minor, patch, extra=""):
    """Build a version string without writing the repo's current number into this file."""
    return f"{major}.{minor}.{patch}{extra}"


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


if __name__ == "__main__":
    unittest.main()
