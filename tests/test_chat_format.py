#!/usr/bin/env python3
"""Chat report stays readable on a phone and still hides engaged posts."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_neighbours as xn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISIBLE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")


def visible(line):
    text = VISIBLE_LINK.sub(r"\1", line)
    text = URL.sub("", text)
    return text.strip()


class ChatFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="xn-chat-")
        cmd = [
            sys.executable, os.path.join(ROOT, "x_neighbours.py"),
            "--config", os.path.join(ROOT, "config.example.json"),
            "--handle", "fewcreator",
            "--user-id", "800001",
            "--data", os.path.join(ROOT, "examples", "few"),
            "--good-neighbours", os.path.join(ROOT, "examples", "few", "good_neighbours.json"),
            "--out", cls.tmp,
            "--now", "2026-11-04T18:00:00Z",
            "--windows", "day",
            "--no-picture",
        ]
        result = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        cls.output = json.loads(result.stdout)["day"]
        with open(cls.output["report_md"], encoding="utf-8") as fh:
            cls.report = fh.read()
        with open(cls.output["thanks_md"], encoding="utf-8") as fh:
            cls.thanks = fh.read()
        with open(cls.output["more_json"], encoding="utf-8") as fh:
            cls.more = json.load(fh)

    def test_section_order_and_no_table(self):
        flowers = self.report.index("Flowers from your neighbours")
        catch = self.report.index("Catch up with your good neighbours")
        greet = self.report.index("Greetings from your neighbours")
        self.assertLess(flowers, catch)
        self.assertLess(catch, greet)
        self.assertNotIn("|---", self.report)
        self.assertNotIn("| User |", self.report)

    def test_flowers_are_stacked_and_capped(self):
        block = self.report.split("### Catch up")[0]
        self.assertNotIn("@ada_brook", block)
        self.assertIn("[Ada Brook](https://x.com/ada_brook)", block)
        self.assertIn("1 reply · 1 like", block)
        self.assertIn("more in Flowers. Ask to see them.", block)
        self.assertGreaterEqual(len(self.more["flowers"]), 1)
        self.assertLessEqual(block.count("https://x.com/"), 5)

    def test_catch_up_preview_has_one_link(self):
        block = self.report.split("### Catch up")[1].split("### ")[0]
        self.assertIn("Kept the window light on.", block)
        self.assertNotIn("Quoting my own note", block)
        self.assertNotIn("Read post", block)
        self.assertNotIn("@ada_brook", block)
        self.assertNotIn("@fay_glen", block)
        self.assertIn("](https://x.com/ada_brook/status/83101)", block)
        self.assertNotIn("more to catch up", block)
        self.assertEqual(self.more["catch_up"], [])

    def test_greeting_preview_links_to_the_post(self):
        block = self.report.split("### 👋 Greetings")[1]
        self.assertRegex(block, r"\]\(https://x\.com/[A-Za-z0-9_]+/status/\w+\)")
        self.assertIn("Not replied yet", block)
        for row in self.more["greetings_answered"]:
            self.assertTrue(row["replied"])
            self.assertEqual(row["status"], "Replied")
            self.assertIn(f"]({row['url']})", row["markdown"])
            self.assertIn("· Replied", row["markdown"])
            self.assertNotIn("Not replied yet", row["markdown"])

    def test_answered_greeting_lines_say_replied(self):
        now = xn.ts("2026-11-04T18:00:00Z")
        row = {
            "name": "Ada Brook",
            "username": "ada_brook",
            "kind": "reply",
            "text": "I could see it from the corner.",
            "url": "https://x.com/ada_brook/status/71001",
            "on_text": "Left a light on in the window.",
            "created_at": "2026-11-04T10:00:00Z",
            "replied": True,
        }
        text = "\n".join(xn.greeting_lines(row, now))
        self.assertIn("[“I could see it from the corner.”](https://x.com/ada_brook/status/71001)", text)
        self.assertIn("· Replied", text)
        self.assertNotIn("Not replied yet", text)
        waiting = dict(row, replied=False)
        waiting_text = "\n".join(xn.greeting_lines(waiting, now))
        self.assertIn("· Not replied yet", waiting_text)
        self.assertNotIn("· Replied", waiting_text)

    def test_markdown_hard_breaks_separate_name_and_detail(self):
        self.assertRegex(
            self.report,
            r"\*\*\[Ada Brook\]\(https://x.com/ada_brook\)\*\* ⭐  \n1 reply · 1 like",
        )
        self.assertRegex(
            self.report,
            r"\*\*Ada Brook\*\* ⭐  \n\[“Kept the window light on\.”\]",
        )
        greet = self.report.split("### 👋 Greetings")[1]
        self.assertIn("  \n", greet)

    def test_greetings_skip_answered_by_default(self):
        block = self.report.split("### 👋 Greetings")[1]
        self.assertIn("Not replied yet", block)
        self.assertNotIn("already replied", block.lower())
        self.assertNotRegex(block, r"^\s+- ", )
        self.assertIn("already answered. Ask to see them.", block)
        self.assertTrue(any(row["replied"] for row in self.more["greetings_answered"]))
        self.assertNotIn("    - ", block)

    def test_lines_wrap_without_a_long_unbroken_token(self):
        for line in self.report.splitlines():
            shown = visible(line)
            for token in shown.split():
                self.assertLessEqual(len(token), 40, token)

    def test_thanks_note_does_not_claim_the_link_attaches_the_picture(self):
        self.assertIn("Save the picture and attach it in X before posting.", self.thanks)
        self.assertIn(self.thanks.splitlines()[0], self.output["thank_you"]["text"])
        self.assertNotIn("@", self.output["thank_you"]["text"])
        self.assertEqual(
            self.output["thank_you"]["note"],
            "Save the picture and attach it in X before posting.",
        )
        self.assertNotIn("###", self.thanks)


if __name__ == "__main__":
    unittest.main()
