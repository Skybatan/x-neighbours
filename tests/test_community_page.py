#!/usr/bin/env python3
"""The Community Honor Roll lists recommended accounts. Opt-in stays in the chat.

Handles here are fictional.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import community_page as community

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = "const page: CommunityPage = "


def component_tags(source):
    return set(re.findall(r"<([A-Z][A-Za-z0-9]*)\b", source))


def parse_canvas(source):
    start = source.index(MARKER) + len(MARKER)
    payload, _end = json.JSONDecoder().raw_decode(source[start:])
    return payload


def global_doc(neighbours):
    return {
        "format": "x-neighbours-global",
        "version": 1,
        "neighbours": neighbours,
    }


class TemplateTest(unittest.TestCase):
    def test_kit_blocks_sit_directly_in_page_and_section(self):
        with open(community.TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
        self.assertEqual(template.count("from "), 1)
        self.assertIn('from "grok/canvas"', template)
        self.assertNotIn("fetch(", template)
        self.assertEqual(component_tags(template), {"Page", "Section", "Text", "TextLink"})
        self.assertIn("{sectionNodes(block)}", template)


class PageTest(unittest.TestCase):
    def test_handles_link_to_profiles_and_counts_are_shown(self):
        rows = [
            {"user_id": "9001", "handle": "bea_glen", "recommendation_count": 1},
            {"user_id": "9002", "handle": "ada_brook", "recommendation_count": 3},
        ]
        folder = tempfile.mkdtemp(prefix="xn-community-")
        path = os.path.join(folder, "global.neighbours")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(global_doc({row["user_id"]: row for row in rows}), fh)
        loaded = community.load_entries(path)
        self.assertEqual([row["handle"] for row in loaded], ["ada_brook", "bea_glen"])
        source = community.render_canvas(community.build_model(loaded))
        payload = parse_canvas(source)
        self.assertEqual(payload["title"], "Community Honor Roll")
        self.assertIn("A recommendation is not a follow.", payload["intro"])
        blob = json.dumps(payload)
        self.assertIn("https://x.com/ada_brook", blob)
        self.assertIn("https://x.com/bea_glen", blob)
        self.assertIn("@ada_brook", blob)
        self.assertIn("3 recommendations", blob)
        self.assertIn("1 recommendation", blob)
        self.assertNotIn("9001", blob)
        self.assertNotIn("9002", blob)
        self.assertNotIn("Join the community", blob)
        self.assertNotRegex(source, r"(?<!\\)\\u[0-9a-fA-F]{4}")
        self.assertEqual(component_tags(source), {"Page", "Section", "Text", "TextLink"})

    def test_cli_refuses_an_empty_list_and_a_missing_file(self):
        folder = tempfile.mkdtemp(prefix="xn-community-empty-")
        empty = os.path.join(folder, "empty.neighbours")
        with open(empty, "w", encoding="utf-8") as fh:
            json.dump(global_doc({}), fh)
        out = os.path.join(folder, "out")
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "community_page.py"),
             "--global", empty, "--out", out],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["send"])
        self.assertIn("empty", payload["reason"].lower())
        missing = subprocess.run(
            [sys.executable, os.path.join(ROOT, "community_page.py"),
             "--global", os.path.join(folder, "missing.neighbours"), "--out", out],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertFalse(json.loads(missing.stdout)["send"])
        self.assertFalse(os.path.exists(os.path.join(out, "community.canvas.tsx")))


if __name__ == "__main__":
    unittest.main()
