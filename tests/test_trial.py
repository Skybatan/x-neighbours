#!/usr/bin/env python3
"""Welcome tour: five originals or quotes, no stranger marks, a time estimate.

Handles, names, and ids here are fictional. Nothing in this file is a real account.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_neighbours as xn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = "2026-11-16T12:00:00Z"


def starter(pid, created, likes=1, reposts=1, quotes=1, replies=0):
    return {
        "id": pid,
        "created_at": created,
        "conversation_id": pid,
        "text": f"Original {pid}",
        "public_metrics": {
            "like_count": likes,
            "repost_count": reposts,
            "quote_count": quotes,
            "reply_count": replies,
        },
    }


def owner_reply(pid, created):
    return {
        "id": pid,
        "created_at": created,
        "conversation_id": "s1",
        "text": "A reply, even with many likes.",
        "referenced_tweets": [{"type": "replied_to", "id": "s1"}],
        "public_metrics": {"like_count": 20, "repost_count": 4, "quote_count": 2},
    }


class TrialPlanTest(unittest.TestCase):
    def _posts(self):
        rows = []
        for index in range(1, 9):
            hour = 8 + index
            rows.append(starter(f"s{index}", f"2026-11-16T{hour:02d}:00:00Z"))
        rows.append(owner_reply("r9", "2026-11-16T18:30:00Z"))
        rows.append({
            "id": "q1",
            "created_at": "2026-11-16T19:00:00Z",
            "conversation_id": "quoted-other",
            "text": "A quote.",
            "referenced_tweets": [{"type": "quoted", "id": "quoted-other"}],
            "public_metrics": {"like_count": 1, "repost_count": 0, "quote_count": 0},
        })
        return rows

    def test_plan_keeps_originals_and_quotes_and_caps_at_five(self):
        self.assertEqual(xn.TRIAL_POST_COUNT, 5)
        self.assertEqual(xn.TRIAL_READ_BUDGET, 15)
        chosen = xn.select_trial_posts(self._posts(), limit=5)
        ids = [post["id"] for post in chosen]
        self.assertEqual(ids[0], "q1")
        self.assertNotIn("r9", ids)
        self.assertEqual(len(ids), 5)
        self.assertEqual(ids[1:], ["s8", "s7", "s6", "s5"])
        short = xn.select_trial_posts(self._posts(), limit=3)
        self.assertEqual([post["id"] for post in short], ["q1", "s8", "s7"])

    def test_full_engagement_stays_inside_the_read_budget(self):
        rows = [row for row in self._posts() if row["id"] != "q1"]
        plan = xn.trial_plan(rows, limit=5, budget=15)
        self.assertEqual(len(plan["posts"]), 5)
        self.assertEqual(plan["reply_pages"], 0)
        self.assertLessEqual(plan["read_count"], 15)
        self.assertEqual(plan["read_count"], 15)
        self.assertFalse(plan["within_budget"])
        tools = [row["tool"] for row in plan["reads"]]
        self.assertEqual(tools[0], "get_users_posts")
        self.assertNotIn("search_posts_all", tools)
        self.assertEqual(tools.count("get_posts_liking_users"), 5)
        self.assertNotIn("r9", [row.get("id") for row in plan["reads"]])
        skipped_ids = [row.get("id") for row in plan["skipped"]]
        self.assertTrue(skipped_ids)
        self.assertTrue(all(row["tool"] == "get_posts_quoted_posts" for row in plan["skipped"]))

    def test_reply_pages_follow_reply_volume_and_slow_the_estimate(self):
        posts = []
        for index in range(5):
            posts.append(starter(
                f"p{index}",
                f"2026-11-16T{10 + index:02d}:00:00Z",
                likes=1,
                reposts=1 if index == 0 else 0,
                quotes=0,
                replies=15,
            ))
        plan = xn.trial_plan(posts, limit=5, budget=15)
        self.assertEqual(plan["reply_count"], 75)
        self.assertEqual(plan["reply_page_size"], 25)
        self.assertEqual(plan["reply_pages_needed"], 3)
        self.assertEqual(plan["reply_pages"], 3)
        search = [row for row in plan["reads"] if row["tool"] == "search_posts_all"]
        self.assertEqual(len(search), 1)
        self.assertEqual(search[0]["count"], 3)
        self.assertIn("25", search[0]["paging"])
        self.assertIn("first-level", search[0]["paging"])
        self.assertIn("Do not stop after one extra page", search[0]["paging"])
        self.assertEqual(plan["read_count"], 10)
        self.assertEqual(plan["estimate_minutes"], 3)
        self.assertIn("about 3 minutes", plan["estimate_message"])
        self.assertIn("I'll let you know when it's ready.", plan["estimate_message"])
        self.assertEqual(xn.estimate_minutes(10, sequential_seconds=180), 3)
        self.assertEqual(xn.estimate_minutes(15), 1)

    def test_reply_pages_stop_when_the_budget_ends(self):
        posts = [
            starter(
                f"p{index}",
                f"2026-11-16T{10 + index:02d}:00:00Z",
                likes=1,
                reposts=0,
                quotes=0,
                replies=100,
            )
            for index in range(5)
        ]
        plan = xn.trial_plan(posts, limit=5, budget=15)
        self.assertEqual(plan["reply_pages_needed"], 20)
        self.assertEqual(plan["reply_pages"], 14)
        self.assertEqual(plan["read_count"], 15)
        self.assertFalse(plan["within_budget"])
        tools = [row["tool"] for row in plan["reads"]]
        self.assertNotIn("get_posts_liking_users", tools)
        self.assertEqual(plan["estimate_minutes"], 14)

    def test_estimate_uses_reads_time_and_parallelism(self):
        self.assertEqual(xn.estimate_minutes(0), 0)
        self.assertEqual(xn.estimate_minutes(15), 1)
        self.assertEqual(xn.estimate_minutes(111), 4)
        self.assertEqual(xn.estimate_minutes(360), 12)
        self.assertEqual(xn.estimate_minutes(15, parallelism=100), 1)
        message = xn.estimate_message(15)
        self.assertIn("about 1 minute", message)
        self.assertIn("don't need to wait", message)
        self.assertIn("notify you when it's ready", message)


class StrangerMarkTest(unittest.TestCase):
    def _write(self, folder, with_following):
        me = "100"
        posts = {
            "data": [{
                "id": "7001",
                "author_id": me,
                "created_at": "2026-11-16T08:00:00Z",
                "text": "Window light.",
                "conversation_id": "7001",
                "public_metrics": {"like_count": 1},
            }],
            "includes": {"users": [{"id": me, "username": "demo_owner", "name": "Demo Owner"}]},
        }
        mentions = {
            "data": [{
                "id": "7101",
                "author_id": "201",
                "created_at": "2026-11-16T09:00:00Z",
                "text": "Saw the light.",
                "in_reply_to_user_id": me,
                "conversation_id": "7001",
                "referenced_tweets": [{"type": "replied_to", "id": "7001"}],
            }],
            "includes": {"users": [{"id": "201", "username": "ada_brook", "name": "Ada Brook"}]},
        }
        with open(os.path.join(folder, "posts_1.json"), "w", encoding="utf-8") as fh:
            json.dump(posts, fh)
        with open(os.path.join(folder, "mentions_1.json"), "w", encoding="utf-8") as fh:
            json.dump(mentions, fh)
        if with_following:
            with open(os.path.join(folder, "following_1.json"), "w", encoding="utf-8") as fh:
                json.dump({"data": []}, fh)
        return me

    def test_no_stranger_marks_without_a_following_file(self):
        folder = tempfile.mkdtemp(prefix="xn-nofollow-")
        me = self._write(folder, with_following=False)
        data = xn.Data(folder, me)
        self.assertFalse(data.following_known)
        since = xn.ts("2026-11-01T00:00:00Z")
        until = xn.ts(NOW)
        activity = xn.build_activity(
            data, since, until, 10, 1, 3, "both", until,
        )
        self.assertTrue(activity["interactions"])
        self.assertFalse(any(row["stranger"] for row in activity["interactions"]))
        path = os.path.join(folder, "report.md")
        xn.write_chat_report(activity, path, "demo_owner", since, until, "Last 7 days", window="week")
        with open(path, encoding="utf-8") as fh:
            report = fh.read()
        self.assertNotIn("👤?", report)
        self.assertNotIn("you don't follow", report)

    def test_marks_return_when_the_following_list_is_loaded(self):
        folder = tempfile.mkdtemp(prefix="xn-follow-")
        me = self._write(folder, with_following=True)
        data = xn.Data(folder, me)
        self.assertTrue(data.following_known)
        since = xn.ts("2026-11-01T00:00:00Z")
        until = xn.ts(NOW)
        activity = xn.build_activity(
            data, since, until, 10, 1, 3, "both", until,
        )
        self.assertTrue(any(row["stranger"] for row in activity["interactions"]))
        path = os.path.join(folder, "report.md")
        xn.write_chat_report(activity, path, "demo_owner", since, until, "Last 7 days", window="week")
        with open(path, encoding="utf-8") as fh:
            report = fh.read()
        self.assertIn("👤?", report)


class TrialReportCommandTest(unittest.TestCase):
    def test_first_run_header_and_next_steps_skip_the_sixth_post(self):
        folder = tempfile.mkdtemp(prefix="xn-trial-")
        out = tempfile.mkdtemp(prefix="xn-trial-out-")
        me = "100"
        posts = []
        for index in range(1, 7):
            posts.append({
                "id": f"800{index}",
                "author_id": me,
                "created_at": f"2026-11-0{index}T08:00:00Z",
                "text": f"Post {index}",
                "conversation_id": f"800{index}",
                "public_metrics": {"like_count": 1, "repost_count": 0, "quote_count": 0},
            })
        posts.append({
            "id": "8901",
            "author_id": me,
            "created_at": "2026-11-16T11:00:00Z",
            "text": "Owner reply, not a trial post.",
            "conversation_id": "8006",
            "referenced_tweets": [{"type": "replied_to", "id": "1"}],
            "public_metrics": {"like_count": 8},
        })
        with open(os.path.join(folder, "posts_1.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "data": posts,
                "includes": {"users": [{"id": me, "username": "demo_owner", "name": "Demo"}]},
            }, fh)
        with open(os.path.join(folder, "likes_8001.json"), "w", encoding="utf-8") as fh:
            json.dump({"data": [{"id": "301", "username": "old_fan", "name": "Old Fan"}]}, fh)
        with open(os.path.join(folder, "likes_8006.json"), "w", encoding="utf-8") as fh:
            json.dump({"data": [{"id": "302", "username": "new_fan", "name": "New Fan"}]}, fh)
        cmd = [
            sys.executable, os.path.join(ROOT, "x_neighbours.py"),
            "--handle", "demo_owner",
            "--user-id", me,
            "--data", folder,
            "--out", out,
            "--now", "2026-11-16T12:00:00Z",
            "--first-run",
            "--no-picture",
            "--good-neighbours", os.path.join(ROOT, "examples", "few", "good_neighbours.json"),
            "--config", os.path.join(ROOT, "config.example.json"),
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)["first"]
        self.assertEqual(payload["trial"]["post_count"], 5)
        self.assertNotIn("8001", payload["trial"]["posts"])
        self.assertIn("8006", payload["trial"]["posts"])
        self.assertEqual(
            payload["next_steps"]["options"],
            ["Daily report", "Weekly report", "Only when I ask"],
        )
        with open(payload["report_md"], encoding="utf-8") as fh:
            report = fh.read()
        self.assertTrue(report.startswith("Welcome tour"))
        self.assertNotIn("Old Fan", report)
        self.assertIn("New Fan", report)
        self.assertNotIn("👤?", report)
        self.assertNotIn("add_question", payload)
        self.assertNotIn("suggest_good_neighbours", payload)
        self.assertNotIn("good_neighbours_page", payload)
        self.assertFalse(payload["community_offer"])
        self.assertFalse(payload["share_offer"])
        self.assertTrue(payload["intro"].startswith("Hi @demo_owner! 👋"))
        self.assertNotIn("Hi Demo", payload["intro"])
        intro_lines = [line for line in payload["intro"].splitlines() if line.strip()]
        self.assertEqual(len(intro_lines), 3)
        self.assertEqual(payload["intro"].count("Hi @demo_owner! 👋"), 1)
        self.assertIn("keep up with and grow the connections", payload["intro"])
        self.assertNotIn("good neighbours", payload["intro"].lower())
        self.assertNotIn("community list", payload["intro"].lower())
        self.assertEqual(
            payload["headline"],
            "Here's a quick welcome tour of your 5 latest posts.",
        )
        self.assertEqual(payload["messages"][0]["text"], payload["headline"])
        self.assertNotIn("Hi ", payload["headline"])
        self.assertIn(payload["intro"], report)
        self.assertEqual(report.count("Hi @demo_owner! 👋"), 1)
        self.assertIn(xn.TOUR_FLOWERS, report)
        self.assertNotIn("Add to good neighbours", report)
        self.assertNotIn("Join the community", report)
        self.assertNotIn("share", payload["intro"].lower())
        with open(payload["thanks_md"], encoding="utf-8") as fh:
            thanks = fh.read()
        self.assertIn(xn.TOUR_THANKS, thanks)
        self.assertIn(xn.TOUR_NEXT_HEADING, thanks)
        self.assertIn("daily, weekly, or only when you ask", thanks)
        self.assertIn(xn.TOUR_NEXT_LATER, thanks)

        plan = subprocess.run(
            [sys.executable, os.path.join(ROOT, "x_neighbours.py"),
             "--trial-plan", "--data", folder, "--config", os.path.join(ROOT, "config.example.json")],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        planned = json.loads(plan.stdout)
        self.assertEqual(planned["trial_post_count"], 5)
        self.assertEqual(len(planned["posts"]), 5)
        self.assertNotIn("8901", [row["id"] for row in planned["posts"]])
        self.assertLessEqual(planned["read_count"], 15)
        self.assertTrue(planned["estimate_message"].startswith("Hi @your_handle! 👋 "))
        self.assertEqual(planned["estimate_message"].count("Hi @your_handle! 👋"), 1)
        self.assertIn("I'll let you know when it's ready.", planned["estimate_message"])
        self.assertNotIn(planned["estimate_message"], payload["headline"])

        estimate = subprocess.run(
            [sys.executable, os.path.join(ROOT, "x_neighbours.py"), "--estimate-reads", "15"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        estimated = json.loads(estimate.stdout)
        self.assertEqual(estimated["estimate_minutes"], 1)
        self.assertIn("don't need to wait", estimated["message"])
        self.assertNotIn("Hi ", estimated["message"])


class GreetingTest(unittest.TestCase):
    def test_greeting_uses_the_display_name(self):
        intro = xn.trial_intro(5, name="Ada Brook", handle="ada_brook")
        self.assertEqual(
            intro,
            "Hi Ada Brook! 👋\n"
            "X Neighbours helps you keep up with and grow the connections around your posts "
            "(the people who reply, like, quote and repost).\n"
            "Here's a quick welcome tour of your 5 latest posts.",
        )
        self.assertNotIn("@ada_brook", intro)
        estimate = xn.tour_estimate_message(
            10, name="Ada Brook", handle="ada_brook", post_count=5, sequential_seconds=180)
        self.assertEqual(
            estimate,
            "Hi Ada Brook! 👋 X Neighbours helps you keep up with the people around your posts. "
            "I'm putting together a quick welcome tour of your 5 latest posts, about 3 minutes; "
            "I'll let you know when it's ready.",
        )
        self.assertNotIn("@ada_brook", estimate)
        self.assertNotIn("quote and repost", estimate)
        collapsed = xn.trial_intro(5, name="Ada\nBrook", handle="ada_brook")
        self.assertTrue(collapsed.startswith("Hi Ada Brook! 👋\n"))
        self.assertEqual(collapsed.count("Hi Ada Brook! 👋"), 1)

    def test_greeting_falls_back_to_the_handle(self):
        for blank in ("", "   ", None, "\n\t"):
            intro = xn.trial_intro(5, name=blank, handle="@ada_brook")
            self.assertTrue(intro.startswith("Hi @ada_brook! 👋\n"), repr(blank))
            estimate = xn.tour_estimate_message(
                15, name=blank, handle="ada_brook", post_count=5)
            self.assertTrue(estimate.startswith("Hi @ada_brook! 👋 "))
            self.assertIn("about 1 minute;", estimate)
            self.assertEqual(estimate.count("Hi @ada_brook! 👋"), 1)
        one = xn.trial_intro(1, name="", handle="ada_brook")
        self.assertTrue(one.endswith("Here's a quick welcome tour of your latest post."))
        self.assertNotIn("1 latest", one)

    def test_greeting_appears_once_in_chat_and_once_on_the_page(self):
        hello = "Hi Ada Brook! 👋"
        intro = xn.trial_intro(5, name="Ada Brook", handle="ada_brook")
        delivery = xn.tour_delivery_line(5)
        estimate = xn.tour_estimate_message(
            10, name="Ada Brook", handle="ada_brook", post_count=5, sequential_seconds=180)
        self.assertEqual(intro.count(hello), 1)
        self.assertEqual(estimate.count(hello), 1)
        self.assertNotIn(hello, delivery)
        self.assertNotIn("Hi ", delivery)
        self.assertEqual((estimate + "\n" + delivery).count(hello), 1)
        posts = [starter("p1", "2026-11-16T10:00:00Z", likes=0, reposts=0, quotes=0, replies=0)]
        named = xn.trial_plan(posts, name="Ada Brook", handle="ada_brook")
        blank = xn.trial_plan(posts, name="   ", handle="@ada_brook")
        self.assertEqual(named["estimate_message"].count(hello), 1)
        self.assertIn("your latest post", named["estimate_message"])
        self.assertNotIn("@ada_brook", named["estimate_message"])
        self.assertTrue(blank["estimate_message"].startswith("Hi @ada_brook! 👋"))
        self.assertNotIn("Ada Brook", blank["estimate_message"])
        self.assertEqual(blank["estimate_message"].count("Hi @ada_brook! 👋"), 1)

    def test_first_run_greets_from_config_and_not_again_on_delivery(self):
        folder = tempfile.mkdtemp(prefix="xn-greet-")
        out = tempfile.mkdtemp(prefix="xn-greet-out-")
        me = "100"
        with open(os.path.join(folder, "posts_1.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "data": [{
                    "id": "1",
                    "author_id": me,
                    "created_at": "2026-11-16T08:00:00Z",
                    "text": "Hello",
                    "conversation_id": "1",
                    "public_metrics": {
                        "like_count": 0, "repost_count": 0, "quote_count": 0, "reply_count": 0,
                    },
                }],
                "includes": {"users": [{
                    "id": me, "username": "demo_owner", "name": "Saved Name",
                }]},
            }, fh)
        config_path = os.path.join(folder, "config.json")
        with open(os.path.join(ROOT, "config.example.json"), encoding="utf-8") as fh:
            config = json.load(fh)
        config.update({"handle": "demo_owner", "user_id": me, "name": "Ada Brook"})
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        cmd = [
            sys.executable, os.path.join(ROOT, "x_neighbours.py"),
            "--config", config_path,
            "--data", folder,
            "--out", out,
            "--now", "2026-11-16T12:00:00Z",
            "--first-run",
            "--no-picture",
            "--good-neighbours", os.path.join(ROOT, "examples", "few", "good_neighbours.json"),
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)["first"]
        hello = "Hi Ada Brook! 👋"
        self.assertEqual(payload["intro"].count(hello), 1)
        self.assertTrue(payload["intro"].startswith(hello))
        self.assertNotIn("Saved Name", payload["intro"])
        self.assertNotIn("@demo_owner", payload["intro"])
        self.assertEqual(payload["headline"], "Here's a quick welcome tour of your latest post.")
        self.assertEqual(payload["messages"][0]["text"], payload["headline"])
        self.assertNotIn("Hi ", payload["headline"])
        with open(payload["page_canvas"], encoding="utf-8") as fh:
            source = fh.read()
        marker = "const report: Report = "
        start = source.index(marker) + len(marker)
        page, _end = json.JSONDecoder().raw_decode(source[start:])
        self.assertEqual(page["intro"].count(hello), 1)
        self.assertEqual(page["intro"].splitlines()[0], hello)

        plan = subprocess.run(
            [sys.executable, os.path.join(ROOT, "x_neighbours.py"),
             "--trial-plan", "--data", folder, "--config", config_path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        message = json.loads(plan.stdout)["estimate_message"]
        self.assertEqual(
            message,
            "Hi Ada Brook! 👋 X Neighbours helps you keep up with the people around your posts. "
            "I'm putting together a quick welcome tour of your latest post, about 1 minute; "
            "I'll let you know when it's ready.",
        )
        self.assertEqual(message.count(hello), 1)
        self.assertNotIn(hello, payload["headline"])

        config["name"] = "   "
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        fallback = subprocess.run(
            [sys.executable, os.path.join(ROOT, "x_neighbours.py"),
             "--trial-plan", "--data", folder, "--config", config_path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        fallback_message = json.loads(fallback.stdout)["estimate_message"]
        self.assertTrue(fallback_message.startswith("Hi @demo_owner! 👋 "))
        self.assertNotIn("Saved Name", fallback_message)
        self.assertNotIn("Ada Brook", fallback_message)
        self.assertEqual(fallback_message.count("Hi @demo_owner! 👋"), 1)


if __name__ == "__main__":
    unittest.main()
