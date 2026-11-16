#!/usr/bin/env python3
"""Replies lists only top-level replies to the owner's original posts.

Handles, names, and ids here are fictional. Nothing in this file is a real account.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_neighbours as xn

ME = "900"
CLOCK = "2026-11-16T12:00:00Z"
STALE_NOW = "2026-11-09T12:05:00Z"


def dump(folder, name, doc):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def user(uid, username, name):
    return {"id": uid, "username": username, "name": name}


def mention(pid, author, created, text, parent=None, quoted=None, parent_type="replied_to"):
    row = {
        "id": pid,
        "author_id": author,
        "created_at": created,
        "text": text,
        "in_reply_to_user_id": ME,
    }
    refs = []
    if parent:
        refs.append({"type": parent_type, "id": parent})
    if quoted:
        refs.append({"type": "quoted", "id": quoted})
    if refs:
        row["referenced_tweets"] = refs
    return row


class TopLevelRepliesTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="xn-replies-")
        posts = {
            "data": [
                {
                    "id": "1001",
                    "author_id": ME,
                    "created_at": "2026-11-08T12:00:00Z",
                    "text": "Morning light on the step.",
                    "conversation_id": "1001",
                },
                {
                    "id": "1002",
                    "author_id": ME,
                    "created_at": "2026-11-15T13:00:00Z",
                    "text": "Glad you saw it.",
                    "conversation_id": "1001",
                    "referenced_tweets": [{"type": "replied_to", "id": "702"}],
                },
            ],
            "includes": {"users": [user(ME, "demo_owner", "Demo Owner")]},
        }
        mentions = {
            "data": [
                mention("701", "901", "2026-11-09T12:00:00Z",
                        "Lane saw the step.", parent="1001"),
                mention("702", "902", "2026-11-15T12:00:00Z",
                        "Moss saw the morning light.", parent="1001"),
                mention("703", "902", "2026-11-15T14:00:00Z",
                        "Later reply under the owner's reply.", parent="1002"),
                mention("704", "904", "2026-11-16T08:00:00Z",
                        "Wren stopped by.", parent="1001"),
                mention("705", "905", "2026-11-16T11:00:00Z",
                        "Nia found the older original.", parent="1000"),
                mention("706", "906", "2026-11-16T11:30:00Z",
                        "Back under the reply.", parent="1009"),
                mention("707", "903", "2026-11-16T10:00:00Z",
                        "Brook quoted the morning.", quoted="1001"),
                mention("708", "907", "2026-11-16T09:00:00Z",
                        "Only the user id, no parent."),
                mention("1002", ME, "2026-11-15T13:00:00Z",
                        "Glad you saw it.", parent="702"),
            ],
            "includes": {
                "users": [
                    user("901", "lane_quill", "Lane Quill"),
                    user("902", "moss_harper", "Moss Harper"),
                    user("903", "brook_vale", "Brook Vale"),
                    user("904", "wren_pond", "Wren Pond"),
                    user("905", "nia_keel", "Nia Keel"),
                    user("906", "kit_olm", "Kit Olm"),
                    user("907", "no_parent", "No Parent"),
                ],
                "posts": [
                    {
                        "id": "1000",
                        "author_id": ME,
                        "created_at": "2026-10-20T12:00:00Z",
                        "text": "An older original.",
                        "conversation_id": "1000",
                    },
                    {
                        "id": "1009",
                        "author_id": ME,
                        "created_at": "2026-10-21T12:00:00Z",
                        "text": "A reply under that original.",
                        "conversation_id": "1000",
                        "referenced_posts": [{"type": "replied_to", "id": "1000"}],
                    },
                ],
            },
        }
        my_posts = {
            "data": [
                {
                    "id": "1003",
                    "author_id": ME,
                    "created_at": "2026-11-16T09:00:00Z",
                    "text": "Thanks Wren.",
                    "conversation_id": "1001",
                    "referenced_posts": [{"type": "replied_to", "id": "704"}],
                }
            ]
        }
        dump(self.folder, "posts_1.json", posts)
        dump(self.folder, "mentions_1.json", mentions)
        dump(self.folder, "my_posts_1.json", my_posts)
        self.data = xn.Data(self.folder, ME)
        self.clock = xn.ts(CLOCK)

    def _activity(self, now):
        since = xn.ts("2026-11-01T00:00:00Z")
        return xn.build_activity(
            self.data, since, xn.ts(now), top=10,
            like_weight=1, reply_weight=3, mode="both", now=xn.ts(now),
        )

    def _report(self, now):
        activity = self._activity(now)
        path = os.path.join(self.folder, "report.md")
        with patch.object(xn, "utc_now", return_value=self.clock):
            more = xn.write_chat_report(
                activity, path, "demo_owner",
                xn.ts("2026-11-01T00:00:00Z"), xn.ts(now), "Last 7 days",
                window="week",
            )
        with open(path, encoding="utf-8") as fh:
            report = fh.read()
        return report, more

    def test_only_top_level_replies_and_quotes_are_listed(self):
        report, more = self._report(CLOCK)
        block = report.split("### 👋 Replies")[1]
        self.assertIn("Nia found the older original.", block)
        self.assertIn("Brook quoted the morning.", block)
        self.assertIn("Lane saw the step.", block)
        self.assertNotIn("Later reply under the owner's reply.", report)
        self.assertNotIn("Back under the reply.", report)
        self.assertNotIn("Only the user id, no parent.", report)
        self.assertNotIn("Glad you saw it.", report)
        self.assertNotIn("Moss saw the morning light.", block)
        self.assertNotIn("Wren stopped by.", block)
        self.assertIn("2 already answered.", block)
        for row in more["greetings_answered"]:
            self.assertTrue(row["replied"])
            self.assertEqual(row["status"], "Replied")
            self.assertIn("· Replied", row["markdown"])
            self.assertNotIn("Not replied yet", row["markdown"])
        answered_names = [row["username"] for row in more["greetings_answered"]]
        self.assertEqual(answered_names, ["wren_pond", "moss_harper"])
        self.assertNotIn("demo_owner", answered_names)
        self.assertNotIn("kit_olm", answered_names)

    def test_unanswered_are_newest_first(self):
        report, _more = self._report(CLOCK)
        block = report.split("### 👋 Replies")[1]
        nia = block.index("Nia Keel")
        brook = block.index("Brook Vale")
        lane = block.index("Lane Quill")
        self.assertLess(nia, brook)
        self.assertLess(brook, lane)
        self.assertIn("Quote", block)
        self.assertEqual(block.count("Not replied yet"), 3)

    def test_age_uses_current_utc_not_a_stale_report_clock(self):
        report, _more = self._report(STALE_NOW)
        block = report.split("### 👋 Replies")[1]
        self.assertIn("Lane saw the step.", block)
        self.assertIn("7d ago", block)
        self.assertNotIn("m ago", block)
        self.assertNotIn("Moss saw the morning light.", report)
        self.assertNotIn("Nia found the older original.", report)

    def test_direct_reply_in_my_posts_marks_answered(self):
        self.assertIn("704", self.data.owner_replied_to)
        self.assertIn("702", self.data.owner_replied_to)
        self.assertIn("1001", self.data.owner_original_ids)
        self.assertIn("1000", self.data.owner_original_ids)
        self.assertNotIn("1002", self.data.owner_original_ids)
        self.assertNotIn("1009", self.data.owner_original_ids)
        self.assertIn("1009", self.data.owner_reply_ids)


if __name__ == "__main__":
    unittest.main()
