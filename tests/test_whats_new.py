#!/usr/bin/env python3
"""What's new: newest original post, and ages against the real UTC clock.

Every handle, name, and id in here is fictional. Nothing is a real X account.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_neighbours as xn

CLOCK = datetime(2026, 11, 16, 16, 0, tzinfo=timezone.utc)
OWNER = "900"


_ids = 8000


def flake(_when=None):
    """Fictional post id. Not a snowflake and not a real post."""
    global _ids
    _ids += 1
    return str(_ids)


def iso(when):
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump(folder, name, doc):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def user(uid, username, name):
    return {"id": uid, "username": username, "name": name}


def post(pid, author, when, text, **extra):
    row = {
        "id": pid,
        "author_id": author,
        "created_at": iso(when) if isinstance(when, datetime) else when,
        "text": text,
    }
    row.update(extra)
    return row


class OriginalPostRulesTest(unittest.TestCase):
    def test_quote_counts_reply_and_repost_do_not(self):
        self.assertTrue(xn.is_original_post({
            "id": "10",
            "text": "A quote of my own.",
            "conversation_id": "999",
            "referenced_posts": [{"type": "quoted", "id": "999"}],
        }))
        self.assertFalse(xn.is_original_post({
            "id": "11",
            "text": "Replying without the old fields.",
            "conversation_id": "10",
        }))
        self.assertFalse(xn.is_original_post({
            "id": "12",
            "text": "A quote that is also a reply.",
            "conversation_id": "10",
            "referenced_posts": [
                {"type": "replied_to", "id": "10"},
                {"type": "quoted", "id": "8"},
            ],
        }))
        self.assertFalse(xn.is_original_post({
            "id": "13",
            "text": "RT @someone: not mine",
        }))
        self.assertTrue(xn.is_original_post({
            "id": "14",
            "text": "Just my own note.",
            "conversation_id": "14",
        }))

    def test_small_ids_use_created_at_against_the_clock(self):
        person = {
            "name": "Lane Post",
            "username": "lane_post",
            "latest": {
                "id": "42",
                "text": "Short id, two hours old.",
                "created_at": "2026-11-16T14:00:00Z",
            },
            "latest_url": "https://x.com/lane_post/status/42",
        }
        stale = CLOCK - timedelta(days=6)
        with patch.object(xn, "utc_now", return_value=CLOCK):
            text = "\n".join(xn.catch_lines(person, stale))
        self.assertIn("2h ago", text)
        self.assertNotIn("6d ago", text)
        self.assertNotIn("7d ago", text)


class WhatsNewSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clock = CLOCK
        cls.patch = patch.object(xn, "utc_now", return_value=cls.clock)
        cls.patch.start()
        cls.folder = tempfile.mkdtemp(prefix="xn-whats-new-")
        hour = timedelta(hours=1)
        day = timedelta(days=1)
        minute = timedelta(minutes=1)

        lane_quote_at = cls.clock - 3 * hour - 10 * minute
        lane_quote = flake(lane_quote_at)
        river_liked_at = cls.clock - 2 * hour - 20 * minute
        river_liked = flake(river_liked_at)
        river_keep_at = cls.clock - day - 15 * minute
        river_keep = flake(river_keep_at)
        pine_real = cls.clock - 7 * day - 5 * minute
        pine_id = flake(pine_real)
        cedar_real = cls.clock - 7 * day - 25 * minute
        cedar_id = flake(cedar_real)
        page_old_at = cls.clock - 3 * day - 40 * minute
        page_old = flake(page_old_at)
        page_new_at = cls.clock - 2 * hour - 7 * minute
        page_new = flake(page_new_at)
        hide_reply_new_at = cls.clock - hour - 17 * minute
        hide_reply_new = flake(hide_reply_new_at)
        hide_reply_old_at = cls.clock - 2 * day - 35 * minute
        hide_reply_old = flake(hide_reply_old_at)
        hide_repost_new_at = cls.clock - hour - 41 * minute
        hide_repost_new = flake(hide_repost_new_at)
        hide_repost_old_at = cls.clock - 2 * day - 55 * minute
        hide_repost_old = flake(hide_repost_old_at)

        dump(cls.folder, "latest_501.json", {
            "data": [
                post(flake(cls.clock - 30 * minute), "501",
                     cls.clock - 30 * minute, "Quote reply no.",
                     conversation_id="1",
                     referenced_posts=[
                         {"type": "replied_to", "id": "1"},
                         {"type": "quoted", "id": "2"},
                     ]),
                post(flake(cls.clock - 70 * minute), "501", cls.clock - 70 * minute,
                     "A reply that must not show.", conversation_id="1"),
                post(flake(cls.clock - 130 * minute), "501", cls.clock - 130 * minute,
                     "RT @someone: a plain repost",
                     referenced_tweets=[{"type": "retweeted", "id": "3"}]),
                post(flake(cls.clock - 100 * minute), "999",
                     cls.clock - 100 * minute, "Not their post."),
                post(lane_quote, "501", lane_quote_at,
                     "A quote that should show.",
                     conversation_id="777",
                     referenced_posts=[{"type": "quoted", "id": "777"}]),
                post(flake(cls.clock - 5 * day - 10 * minute), "501",
                     cls.clock - 5 * day - 10 * minute,
                     "Older original that should not win.",
                     conversation_id=flake(cls.clock - 5 * day - 10 * minute)),
            ],
            "includes": {"users": [user("501", "lane_post", "Lane Post")]},
        })
        dump(cls.folder, "latest_502.json", {
            "data": [
                post(river_liked, "502", river_liked_at, "Already liked.",
                     conversation_id=river_liked),
                post(flake(cls.clock - 4 * hour - 12 * minute), "502",
                     cls.clock - 4 * hour - 12 * minute,
                     "Replying, not posting.",
                     referenced_posts=[{"type": "replied_to", "id": "4"}]),
                post(river_keep, "502", river_keep_at, "The unengaged original.",
                     conversation_id=river_keep),
            ],
            "includes": {"users": [user("502", "river_note", "River Note")]},
        })
        dump(cls.folder, "latest_503.json", {
            "data": [
                post(flake(cls.clock - hour), "503", cls.clock - hour,
                     "Only a reply.", conversation_id="8"),
            ],
            "includes": {"users": [user("503", "moss_yard", "Moss Yard")]},
        })
        dump(cls.folder, "latest_504.json", {
            "data": [
                post(pine_id, "504", pine_real, "Week old note.",
                     conversation_id=pine_id),
            ],
            "includes": {"users": [user("504", "pine_hill", "Pine Hill")]},
        })
        dump(cls.folder, "latest_505.json", {
            "data": [
                post(cedar_id, "505", cedar_real, "True week old.",
                     conversation_id=cedar_id),
            ],
            "includes": {"users": [user("505", "cedar_row", "Cedar Row")]},
        })
        dump(cls.folder, "latest_506.json", {
            "data": [
                post(page_old, "506", page_old_at, "Page one note.",
                     conversation_id=page_old),
            ],
            "includes": {"users": [user("506", "page_two", "Page Two")]},
        })
        dump(cls.folder, "latest_506_p2.json", {
            "data": [
                post(page_new, "506", page_new_at, "Page two note.",
                     conversation_id=page_new),
            ],
            "includes": {"users": [user("506", "page_two", "Page Two")]},
        })
        dump(cls.folder, "latest_507.json", {
            "data": [
                post(hide_reply_new, "507", hide_reply_new_at, "Answered already.",
                     conversation_id=hide_reply_new),
                post(hide_reply_old, "507", hide_reply_old_at, "Still open.",
                     conversation_id=hide_reply_old),
            ],
            "includes": {"users": [user("507", "reply_hide", "Reply Hide")]},
        })
        dump(cls.folder, "latest_508.json", {
            "data": [
                post(hide_repost_new, "508", hide_repost_new_at, "Reposted already.",
                     conversation_id=hide_repost_new),
                post(hide_repost_old, "508", hide_repost_old_at, "Still fresh.",
                     conversation_id=hide_repost_old),
            ],
            "includes": {"users": [user("508", "repost_hide", "Repost Hide")]},
        })
        dump(cls.folder, "my_likes_1.json", {
            "data": [{"id": river_liked, "created_at": iso(cls.clock - hour)}],
        })
        dump(cls.folder, "my_posts_1.json", {
            "data": [
                {
                    "id": flake(cls.clock - 12 * minute),
                    "author_id": OWNER,
                    "created_at": iso(cls.clock - 12 * minute),
                    "text": "I replied.",
                    "referenced_tweets": [{"type": "replied_to", "id": hide_reply_new}],
                },
                {
                    "id": flake(cls.clock - 18 * minute),
                    "author_id": OWNER,
                    "created_at": iso(cls.clock - 18 * minute),
                    "text": "RT @repost_hide: Reposted already.",
                    "referenced_tweets": [{"type": "retweeted", "id": hide_repost_new}],
                },
            ],
        })
        cls.neighbours = [
            {"id": "501", "username": "lane_post", "name": "Lane Post"},
            {"id": "502", "username": "river_note", "name": "River Note"},
            {"id": "503", "username": "moss_yard", "name": "Moss Yard"},
            {"id": "504", "username": "pine_hill", "name": "Pine Hill"},
            {"id": "505", "username": "cedar_row", "name": "Cedar Row"},
            {"id": "506", "username": "page_two", "name": "Page Two"},
            {"id": "507", "username": "reply_hide", "name": "Reply Hide"},
            {"id": "508", "username": "repost_hide", "name": "Repost Hide"},
        ]
        data = xn.Data(cls.folder, OWNER)
        # Stale report clock: 8 hours after the week-old posts. The old bug
        # rendered those as "8h ago".
        cls.stale_now = cedar_real + timedelta(hours=8)
        cls.activity = xn.build_activity(
            data, cls.stale_now - day, cls.stale_now, 10, 1, 3, "both", cls.stale_now,
            good_neighbours=cls.neighbours,
        )
        cls.out = os.path.join(cls.folder, "report.md")
        xn.write_chat_report(
            cls.activity, cls.out, "testowner", cls.stale_now - day, cls.stale_now,
            "Last 24 hours", window="day", show=10,
        )
        with open(cls.out, encoding="utf-8") as fh:
            cls.report = fh.read()
        parts = cls.report.split("### 🏡 What's new")
        cls.block = parts[1].split("### ")[0] if len(parts) > 1 else ""

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()

    def test_shows_newest_original_not_a_reply_or_repost(self):
        self.assertIn("A quote that should show.", self.block)
        self.assertIn("3h ago", self.block)
        self.assertNotIn("Quote reply no.", self.block)
        self.assertNotIn("A reply that must not show.", self.block)
        self.assertNotIn("a plain repost", self.block)
        self.assertNotIn("Not their post.", self.block)
        self.assertNotIn("Older original that should not win.", self.block)
        self.assertNotIn("Moss Yard", self.block)
        self.assertNotIn("Only a reply.", self.block)

    def test_skips_posts_the_owner_liked_replied_or_reposted(self):
        self.assertIn("The unengaged original.", self.block)
        self.assertIn("1d ago", self.block)
        self.assertNotIn("Already liked.", self.block)
        self.assertNotIn("Replying, not posting.", self.block)
        self.assertIn("Still open.", self.block)
        self.assertNotIn("Answered already.", self.block)
        self.assertIn("Still fresh.", self.block)
        self.assertNotIn("Reposted already.", self.block)

    def test_second_page_can_hold_the_newer_post(self):
        self.assertIn("Page two note.", self.block)
        self.assertNotIn("Page one note.", self.block)

    def test_ages_use_the_real_clock_not_a_stale_report_now(self):
        self.assertRegex(self.block, r"Week old note\.”\]\([^)]+\) · 7d ago")
        self.assertRegex(self.block, r"True week old\.”\]\([^)]+\) · 7d ago")
        self.assertNotRegex(self.block, r"Week old note\.”\]\([^)]+\) · 8h ago")
        self.assertNotRegex(self.block, r"True week old\.”\]\([^)]+\) · 8h ago")
        self.assertNotIn("8h ago", self.block)

    def test_caught_up_when_nothing_qualifies(self):
        folder = tempfile.mkdtemp(prefix="xn-caught-")
        liked = flake(self.clock - timedelta(hours=3))
        dump(folder, "latest_601.json", {
            "data": [post(liked, "601", self.clock - timedelta(hours=3),
                          "Liked and done.", conversation_id=liked)],
            "includes": {"users": [user("601", "done_yard", "Done Yard")]},
        })
        dump(folder, "latest_602.json", {
            "data": [post(flake(self.clock - timedelta(hours=1)), "602",
                          self.clock - timedelta(hours=1), "Still just a reply.",
                          conversation_id="1")],
            "includes": {"users": [user("602", "only_reply", "Only Reply")]},
        })
        dump(folder, "my_likes_1.json", {"data": [{"id": liked}]})
        data = xn.Data(folder, OWNER)
        neighbours = [
            {"id": "601", "username": "done_yard", "name": "Done Yard"},
            {"id": "602", "username": "only_reply", "name": "Only Reply"},
        ]
        activity = xn.build_activity(
            data, self.clock - timedelta(days=1), self.stale_now, 10, 1, 3, "both",
            self.stale_now, good_neighbours=neighbours,
        )
        self.assertEqual(activity["catch_up"], [])
        self.assertTrue(activity["all_caught_up"])
        path = os.path.join(folder, "report.md")
        xn.write_chat_report(
            activity, path, "testowner", self.clock - timedelta(days=1), self.stale_now,
            "Last 24 hours", window="day",
        )
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("You're all caught up with your good neighbours 🎉", text)
        self.assertNotIn("### 🏡 What's new", text)
        self.assertNotIn("No recent original posts", text)

    def test_empty_list_does_not_use_the_caught_up_line(self):
        data = xn.Data(tempfile.mkdtemp(prefix="xn-empty-"), OWNER)
        activity = xn.build_activity(
            data, self.clock - timedelta(days=1), self.clock, 10, 1, 3, "both",
            self.clock, good_neighbours=[],
        )
        self.assertFalse(activity["all_caught_up"])
        self.assertTrue(activity["catch_hint"])
        self.assertEqual(activity["catch_up"], [])


if __name__ == "__main__":
    unittest.main()
