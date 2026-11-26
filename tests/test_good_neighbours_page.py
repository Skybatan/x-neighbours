#!/usr/bin/env python3
"""The Good Neighbours Newsletter is separate from the Period Report.

Handles and names here are fictional.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import good_neighbours_page as gn
import report_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = "const page: NeighboursPage = "


def component_tags(source):
    return set(re.findall(r"<([A-Z][A-Za-z0-9]*)\b", source))


def parse_canvas(source):
    start = source.index(MARKER) + len(MARKER)
    payload, _end = json.JSONDecoder().raw_decode(source[start:])
    return payload


class TemplateTest(unittest.TestCase):
    def test_kit_blocks_sit_directly_in_page_and_section(self):
        with open(gn.TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
        self.assertEqual(template.count("from "), 1)
        self.assertIn('from "grok/canvas"', template)
        self.assertNotIn("fetch(", template)
        self.assertEqual(component_tags(template), {"Page", "Section", "Text", "TextLink"})
        self.assertIn("{sectionNodes(block)}", template)
        self.assertNotIn("function SectionBody", template)


class ModelTest(unittest.TestCase):
    def test_latest_posts_and_the_full_list_keep_their_links(self):
        neighbours = [
            {"id": "1", "username": "ada_brook", "name": "Ada Brook"},
            {"id": "2", "username": "bea_glen", "name": "Bea Glen"},
        ]
        catch = [{
            "name": "Ada Brook",
            "username": "ada_brook",
            "latest": {"text": "Kept the window light on.", "created_at": "2026-11-04T16:00:00Z"},
            "latest_url": "https://x.com/ada_brook/status/9",
        }]
        model = gn.build_model(neighbours, catch)
        source = gn.render_canvas(model)
        payload = parse_canvas(source)
        self.assertEqual(payload["title"], "Good Neighbours Newsletter")
        self.assertEqual([block["heading"] for block in payload["sections"]], ["Latest posts", "Your list"])
        self.assertIn("Latest posts", json.dumps(payload))
        blob = json.dumps(payload)
        self.assertIn("https://x.com/ada_brook/status/9", blob)
        self.assertIn("https://x.com/ada_brook", blob)
        self.assertIn("https://x.com/bea_glen", blob)
        self.assertIn("Ada Brook", blob)
        self.assertIn("Bea Glen (@bea_glen)", blob)
        self.assertNotIn("Add to good neighbours", blob)
        self.assertNotRegex(source, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertIn(gn.LATEST_EXPLAINER, blob)

    def test_an_empty_catch_up_still_lists_everyone(self):
        neighbours = [{"id": "1", "username": "ada_brook", "name": "Ada Brook"}]
        payload = parse_canvas(gn.render_canvas(gn.build_model(neighbours, [])))
        self.assertEqual(payload["sections"][0]["preface"], gn.CAUGHT_UP)
        self.assertEqual(payload["sections"][0]["items"], [])
        self.assertIn("https://x.com/ada_brook", json.dumps(payload["sections"][1]))

    def test_cli_skips_the_page_when_the_list_is_empty(self):
        folder = tempfile.mkdtemp(prefix="xn-gn-empty-")
        data = os.path.join(folder, "data")
        os.makedirs(data)
        path = os.path.join(folder, "good_neighbours.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "neighbours": []}, fh)
        out = os.path.join(folder, "out")
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "good_neighbours_page.py"),
             "--data", data, "--user-id", "100", "--good-neighbours", path, "--out", out],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["send"])
        self.assertNotIn("page_canvas", payload)
        self.assertFalse(os.path.exists(os.path.join(out, "good_neighbours.canvas.tsx")))

    def test_report_command_attaches_the_page_only_when_the_list_is_used(self):
        out = tempfile.mkdtemp(prefix="xn-gn-report-")
        cmd = [
            sys.executable, os.path.join(ROOT, "x_neighbours.py"),
            "--config", os.path.join(ROOT, "config.example.json"),
            "--handle", "fewcreator",
            "--user-id", "800001",
            "--data", os.path.join(ROOT, "examples", "few"),
            "--good-neighbours", os.path.join(ROOT, "examples", "few", "good_neighbours.json"),
            "--out", out,
            "--now", "2026-11-04T18:00:00Z",
            "--windows", "day",
            "--no-picture",
        ]
        result = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        day = json.loads(result.stdout)["day"]
        self.assertTrue(day["good_neighbours_page"]["send"])
        self.assertEqual(day["good_neighbours_page"]["page_title"], "Good Neighbours Newsletter")
        self.assertTrue(day["good_neighbours_page"]["add_reminder"])
        with open(day["good_neighbours_page"]["page_canvas"], encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("https://x.com/ada_brook", source)
        self.assertEqual(component_tags(source), {"Page", "Section", "Text", "TextLink"})
        self.assertNotIn(report_page.PLACEHOLDER, source)


if __name__ == "__main__":
    unittest.main()
