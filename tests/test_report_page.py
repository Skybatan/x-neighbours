#!/usr/bin/env python3
"""The report Page keeps the chat report's words and links.

Handles, names, and post text here are fictional.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import report_page
import x_neighbours as xn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")
MARKER = "const report: Report = "
NOW = xn.ts("2026-11-04T18:00:00Z")
SINCE = xn.ts("2026-11-03T18:00:00Z")
THANKS = {
    "text": "My X neighbours circle, November 4! Thank you all for being here.",
    "intent": "https://x.com/intent/post?text=Hello%20neighbours",
    "link_label": "Post your thank-you",
    "note": xn.THANK_YOU_NOTE,
}


def parse_canvas(source):
    start = source.index(MARKER) + len(MARKER)
    payload, end = json.JSONDecoder().raw_decode(source[start:])
    if not source[start + end:].lstrip().startswith(";"):
        raise AssertionError("page data is not a single expression")
    return payload


def code_without_data(source):
    head, tail = source.split(MARKER, 1)
    _payload, end = json.JSONDecoder().raw_decode(tail)
    return head + tail[end:]


def hrefs(value, found=None):
    if found is None:
        found = []
    if isinstance(value, dict):
        if value.get("href"):
            found.append(value["href"])
        for item in value.values():
            hrefs(item, found)
    elif isinstance(value, list):
        for item in value:
            hrefs(item, found)
    return found


def strings(value, found=None):
    if found is None:
        found = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            strings(item, found)
    elif isinstance(value, list):
        for item in value:
            strings(item, found)
    return found


def empty_activity(**flags):
    activity = {
        "totals": {"replies": 0, "quotes": 0, "likes": 0, "reposts": 0},
        "threads": [],
        "interactions": [],
        "catch_up": [],
        "has_good_neighbours": False,
        "catch_hint": True,
        "all_caught_up": False,
    }
    activity.update(flags)
    return activity


class TemplateTest(unittest.TestCase):
    def test_template_imports_only_the_page_kit(self):
        with open(report_page.TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
        self.assertEqual(template.count(report_page.PLACEHOLDER), 1)
        self.assertEqual(template.count("from "), 1)
        self.assertIn('from "grok/canvas"', template)
        self.assertNotIn("fetch(", template)
        self.assertNotIn("cursor/canvas", template)


class FewPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="xn-page-")
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
        with open(cls.output["page_canvas"], encoding="utf-8") as fh:
            cls.canvas = fh.read()
        cls.payload = parse_canvas(cls.canvas)

    def test_page_source_keeps_emoji_as_characters(self):
        self.assertNotRegex(self.canvas, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertIn("💐", self.canvas)
        self.assertIn("💬", self.canvas)
        self.assertIn("❤️", self.canvas)
        self.assertNotIn("\\ud83d", self.canvas)
        self.assertNotIn("\\u2014", self.canvas)

    def test_canvas_is_one_page_module(self):
        code = code_without_data(self.canvas)
        self.assertEqual(code.count("from "), 1)
        self.assertIn('from "grok/canvas"', code)
        self.assertIn("export default function XNeighboursReport", code)
        self.assertIn("<Page", code)
        self.assertNotIn("fetch(", code)
        self.assertNotIn(report_page.PLACEHOLDER, self.canvas)
        self.assertEqual(self.payload["title"], "Last 24 hours")
        self.assertEqual(self.output["page_title"], "Last 24 hours")
        self.assertEqual(self.output["messages"][0]["part"], "page")
        self.assertEqual(self.output["messages"][0]["text"], self.output["headline"])
        self.assertEqual(len(self.output["fallback_messages"]), 2)

    def test_every_markdown_link_is_on_the_page(self):
        md_urls = set(MD_LINK.findall(self.report)) | set(MD_LINK.findall(self.thanks))
        self.assertTrue(md_urls)
        self.assertEqual(md_urls, set(hrefs(self.payload)))
        self.assertIn("https://x.com/ada_brook", hrefs(self.payload))
        self.assertIn(self.output["thank_you"]["intent"], hrefs(self.payload))

    def test_section_order_and_hidden_rows_stay_hidden(self):
        headings = [block["heading"] for block in self.payload["blocks"] if block["kind"] == "section"]
        self.assertEqual(headings, ["💐 Flowers", "🏡 What's new", "👋 Replies"])
        self.assertEqual(self.payload["blocks"][-1]["kind"], "thanks")
        self.assertEqual(self.payload["blocks"][-1]["linkLabel"], "Post your thank-you")
        for row in self.more["greetings_answered"]:
            self.assertNotIn(row["url"], hrefs(self.payload))
            self.assertNotIn(row["text"], json.dumps(self.payload["blocks"]))
        self.assertIn("already answered. Ask to see them.", json.dumps(self.payload))

    def test_headline_counts_replies_that_need_an_answer(self):
        lines = [line.strip() for line in self.report.splitlines() if line.strip()]
        self.assertTrue(self.output["headline"].startswith(lines[0] + " · " + lines[1]))
        waiting = self.report.count("Not replied yet") + len(self.more["greetings_unanswered"])
        self.assertIn(
            xn.counted(waiting, "reply to answer", "replies to answer"),
            self.output["headline"],
        )
        self.assertNotIn(self.output["headline"], self.canvas.split(MARKER, 1)[0])


class UnicodeSourceTest(unittest.TestCase):
    def test_emoji_and_em_dash_are_characters_not_escapes(self):
        activity = {
            "totals": {"replies": 1, "quotes": 0, "likes": 0, "reposts": 0},
            "interactions": [{
                "name": "Ada\u0007 — Brook",
                "username": "ada_brook",
                "good": False,
                "stranger": False,
                "replies": 1,
                "likes": 0,
                "reposts": 0,
            }],
            "catch_up": [{
                "name": "Bea Glen",
                "username": "bea_glen",
                "good": False,
                "stranger": False,
                "latest": {"text": "Kept the window — light on.", "created_at": "2026-11-04T16:00:00Z"},
                "latest_url": "https://x.com/bea_glen/status/1",
            }],
            "threads": [],
            "has_good_neighbours": False,
            "catch_hint": True,
            "all_caught_up": False,
        }
        clock = xn.ts("2026-11-04T18:00:00Z")
        with patch.object(xn, "utc_now", return_value=clock):
            model = report_page.build_page_model(
                activity, SINCE, NOW, "Last 24 hours", window="day", thanks=THANKS)
            source = report_page.render_report_canvas(model)
        self.assertNotRegex(source, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertIn("💐", source)
        self.assertIn("💬", source)
        self.assertIn("—", source)
        self.assertNotIn("\\u2014", source)
        self.assertNotIn("\\ud83d", source)
        self.assertNotIn("\\u0007", source)
        payload = parse_canvas(source)
        found = strings(payload)
        self.assertIn("Ada  — Brook", found)
        self.assertTrue(any("window — light" in text for text in found))
        self.assertEqual(payload["blocks"][0]["heading"], "💐 Flowers")


class EmptySectionTest(unittest.TestCase):
    def test_empty_sections_are_omitted_and_the_sentences_match(self):
        activity = empty_activity()
        folder = tempfile.mkdtemp(prefix="xn-empty-page-")
        path = os.path.join(folder, "report.md")
        xn.write_chat_report(activity, path, "demo", SINCE, NOW, "Last 24 hours", window="day")
        with open(path, encoding="utf-8") as fh:
            report = fh.read()
        model = report_page.build_page_model(
            activity, SINCE, NOW, "Last 24 hours", window="day", thanks=THANKS)
        source = report_page.render_report_canvas(model)
        payload = parse_canvas(source)
        headings = [block.get("heading") for block in payload["blocks"]]
        for heading in ("💐 Flowers", "🏡 What's new", "👋 Replies"):
            self.assertNotIn(heading, headings)
            self.assertNotIn(heading, source)
        for sentence in (report_page.NO_FLOWERS, report_page.NO_CATCH, report_page.CATCH_HINT, report_page.NO_REPLIES):
            self.assertIn(sentence, report)
            self.assertIn(sentence, source)
        self.assertEqual(
            model["headline"],
            "Last 24 hours · 💬 0 · 🔁💬 0 · ❤️ 0 · 🔁 0",
        )
        self.assertNotIn("to answer", model["headline"])

    def test_caught_up_has_no_whats_new_heading(self):
        activity = empty_activity(has_good_neighbours=True, catch_hint=False, all_caught_up=True)
        model = report_page.build_page_model(activity, SINCE, NOW, "Last 24 hours", window="day")
        source = report_page.render_report_canvas(model)
        self.assertIn(report_page.CAUGHT_UP, source)
        self.assertNotIn("🏡 What's new", source)
        self.assertNotIn(report_page.NO_ORIGINALS, source)

    def test_trial_keeps_the_intro_and_skips_the_list_hint(self):
        activity = empty_activity()
        intro = xn.trial_intro(5)
        model = report_page.build_page_model(
            activity, SINCE, NOW, "First report", window="first", intro=intro, thanks=THANKS)
        payload = parse_canvas(report_page.render_report_canvas(model))
        self.assertEqual(payload["title"], "First report")
        self.assertEqual(payload["intro"], intro)
        self.assertIn("Community sharing can wait until later.", payload["intro"])
        texts = [block.get("text") for block in payload["blocks"]]
        self.assertIn(report_page.NO_CATCH, texts)
        self.assertNotIn(report_page.CATCH_HINT, texts)

    def test_renderer_drops_a_section_that_has_no_rows(self):
        model = {
            "title": "Last 24 hours",
            "summary": "💬 0 · 🔁💬 0 · ❤️ 0 · 🔁 0",
            "legend": None,
            "intro": None,
            "headline": "Last 24 hours · 💬 0 · 🔁💬 0 · ❤️ 0 · 🔁 0",
            "blocks": [
                {
                    "kind": "section",
                    "heading": "💐 Flowers",
                    "preface": None,
                    "items": [],
                    "footers": [],
                },
                {"kind": "note", "text": report_page.NO_FLOWERS},
            ],
        }
        source = report_page.render_report_canvas(model)
        self.assertNotIn("💐 Flowers", source)
        self.assertEqual(parse_canvas(source)["blocks"][0]["text"], report_page.NO_FLOWERS)
        again = report_page.render_report_canvas(model)
        self.assertEqual(source, again)


class EscapingTest(unittest.TestCase):
    def test_user_text_and_handles_cannot_break_the_page(self):
        nasty_name = 'Ada <script>alert("x")</script>'
        nasty_handle = 'a"b<c>'
        nasty_post = "line\nwith ${foo} and </Text> & </Page>"
        activity = {
            "totals": {"replies": 1, "quotes": 0, "likes": 1, "reposts": 0},
            "interactions": [{
                "name": nasty_name,
                "username": nasty_handle,
                "good": True,
                "stranger": False,
                "replies": 1,
                "likes": 0,
                "reposts": 0,
            }],
            "catch_up": [{
                "name": "Bob & Co",
                "username": "bob_co",
                "good": False,
                "stranger": True,
                "latest": {"text": nasty_post, "created_at": "2026-11-04T16:00:00Z"},
                "latest_url": "https://x.com/bob_co/status/1",
            }],
            "threads": [{
                "name": "Cleo\u2028Dawn",
                "username": "cleo_dawn",
                "good": False,
                "stranger": False,
                "items": [{
                    "kind": "reply",
                    "text": "hi <b>",
                    "url": "https://x.com/cleo_dawn/status/2",
                    "on_text": 'on "quote"',
                    "created_at": "2026-11-04T16:00:00Z",
                    "replied": False,
                }],
            }],
            "has_good_neighbours": True,
            "catch_hint": False,
            "all_caught_up": False,
        }
        clock = xn.ts("2026-11-04T18:00:00Z")
        with patch.object(xn, "utc_now", return_value=clock):
            model = report_page.build_page_model(
                activity, SINCE, NOW, "Last 24 hours", window="day", thanks=THANKS)
            source = report_page.render_report_canvas(model)
        payload = parse_canvas(source)
        self.assertNotRegex(source, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertNotIn("\u2028", source)
        self.assertIn("Bob & Co", source)
        self.assertNotIn("\\u0026", source)
        found = strings(payload)
        self.assertIn(nasty_name, found)
        self.assertTrue(any(xn.snippet(nasty_post) in text for text in found))
        self.assertIn("</Text>", xn.snippet(nasty_post))
        self.assertIn("Cleo\nDawn", found)
        self.assertIn("Bob & Co", found)
        self.assertIn(f"https://x.com/{nasty_handle}", hrefs(payload))
        self.assertIn("https://x.com/cleo_dawn/status/2", hrefs(payload))
        self.assertIn("https://x.com/bob_co/status/1", hrefs(payload))


class OverrideTest(unittest.TestCase):
    def test_picture_tag_rewrites_the_thank_you_and_ignores_a_web_picture(self):
        activity = empty_activity()
        model = report_page.build_page_model(
            activity, SINCE, NOW, "Last 24 hours", window="day", thanks=THANKS)
        tagged = report_page.apply_overrides(
            model,
            thank_intent="https://x.com/intent/post?text=tagged",
            thanks_extra="Add @SkyXFunNext when you post the picture.",
            picture_asset_name="https://x.com/pic.png",
        )
        payload = report_page.page_payload(tagged)
        thanks = payload["blocks"][-1]
        self.assertEqual(thanks["href"], "https://x.com/intent/post?text=tagged")
        self.assertIn("@SkyXFunNext", thanks["extra"])
        self.assertIsNone(thanks["picture"])
        shown = report_page.apply_overrides(model, picture_asset_name="asset:neighbours")
        self.assertEqual(report_page.page_payload(shown)["blocks"][-1]["picture"], "asset:neighbours")

    def test_cli_writes_the_canvas_from_the_model(self):
        folder = tempfile.mkdtemp(prefix="xn-page-cli-")
        model = report_page.build_page_model(
            empty_activity(), SINCE, NOW, "Last 7 days", window="week", thanks=THANKS)
        model_path = os.path.join(folder, "report_week_page.json")
        with open(model_path, "w", encoding="utf-8") as fh:
            json.dump(model, fh)
        extra = "Reminder <for> the picture."
        result = subprocess.run(
            [
                sys.executable, os.path.join(ROOT, "report_page.py"),
                "--model", model_path,
                "--thank-intent", "https://x.com/intent/post?text=week",
                "--thanks-extra", extra,
            ],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        out = json.loads(result.stdout)
        self.assertTrue(out["page_canvas"].endswith("report_week.canvas.tsx"))
        with open(out["page_canvas"], encoding="utf-8") as fh:
            source = fh.read()
        payload = parse_canvas(source)
        self.assertEqual(payload["title"], "Last 7 days")
        self.assertEqual(payload["blocks"][-1]["href"], "https://x.com/intent/post?text=week")
        self.assertEqual(payload["blocks"][-1]["extra"], extra)
        self.assertIn("<for>", source)
        self.assertNotRegex(source, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertIn("💬", source)

    def test_extra_post_section_keeps_its_link_ahead_of_thanks(self):
        text = (
            "### Per post\n\n"
            "- 2026-11-04 12:00 UTC — Hello — 1 likes, 0 reposts — "
            "https://x.com/ada/status/9\n"
        )
        extra = report_page.blocks_from_extra_markdown(text)
        self.assertEqual(extra[0]["heading"], "Per post")
        self.assertIn("https://x.com/ada/status/9", hrefs(extra))
        merged = report_page.insert_before_thanks(
            [{"kind": "note", "text": report_page.NO_FLOWERS},
             {"kind": "thanks", "text": "Thanks", "href": "https://x.com/intent/post?text=1",
              "linkLabel": "Post your thank-you", "note": None, "extra": None, "picture": None}],
            extra,
        )
        self.assertEqual(merged[-1]["kind"], "thanks")
        self.assertEqual(merged[-2]["heading"], "Per post")


class RunbookTest(unittest.TestCase):
    def test_the_bot_sends_a_page_and_keeps_the_fallback(self):
        with open(os.path.join(ROOT, "skills", "x-neighbours", "SKILL.md"), encoding="utf-8") as fh:
            skill = fh.read()
        with open(os.path.join(ROOT, "skills", "x-neighbours", "FIRST_RUN.md"), encoding="utf-8") as fh:
            first = fh.read()
        for text in (skill, first):
            self.assertIn("WriteCanvas", text)
            self.assertIn("headline", text)
            self.assertIn("page_canvas", text)
        self.assertIn("Do not pass a canvas id", skill)
        self.assertIn("fallback_messages", skill)
        self.assertIn("add_question", skill)
        self.assertIn("don't need to wait", skill)
        self.assertIn("report_page.py", skill)
        self.assertNotIn("Send exactly two chat messages", skill)
        self.assertIn("Do not send a good-neighbours card", first)
        self.assertIn("community", first.lower())
        self.assertIn("don't need to wait", first)


if __name__ == "__main__":
    unittest.main()
