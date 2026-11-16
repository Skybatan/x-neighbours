#!/usr/bin/env python3
"""The version number lives only in VERSION, and the maintainer skill is present."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import version as version_mod

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".avatar_cache"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class VersionTest(unittest.TestCase):
    def test_version_file_is_one_semver_line(self):
        text = read(os.path.join(ROOT, "VERSION"))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(version_mod.version(), text.strip())
        self.assertRegex(version_mod.version(), r"^\d+\.\d+\.\d+$")

    def test_rejects_a_second_line_or_a_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = os.path.join(folder, "VERSION")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write(version_mod.version() + "\nextra\n")
            with self.assertRaises(ValueError):
                version_mod.version(bad)
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("v" + version_mod.version() + "\n")
            with self.assertRaises(ValueError):
                version_mod.version(bad)

    def test_cli_prints_the_version_file(self):
        number = version_mod.version()
        for args in (
            [sys.executable, os.path.join(ROOT, "version.py")],
            [sys.executable, os.path.join(ROOT, "x_neighbours.py"), "--version"],
        ):
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), number)

    def test_version_string_appears_only_in_VERSION(self):
        number = version_mod.version()
        hits = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            for name in filenames:
                if os.path.splitext(name)[1].lower() in SKIP_EXT:
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, ROOT)
                if rel == "VERSION":
                    continue
                try:
                    text = read(path)
                except (UnicodeDecodeError, OSError):
                    continue
                if number in text:
                    hits.append(rel)
        self.assertEqual(hits, [])


class ReleaseNotesTest(unittest.TestCase):
    def test_changelog_seeds_recent_merged_prs(self):
        text = read(os.path.join(ROOT, "CHANGELOG.md"))
        self.assertIn("https://github.com/Skybatan/x-neighbours/pull/19", text)
        self.assertIn("https://github.com/Skybatan/x-neighbours/pull/23", text)
        self.assertIn("https://github.com/Skybatan/x-neighbours/issues/28", text)
        self.assertIn("VERSION", text)

    def test_maintainer_skill_matches_frontmatter_and_rules(self):
        path = os.path.join(ROOT, "skills", "x-neighbours-maintain", "SKILL.md")
        text = read(path)
        self.assertTrue(text.startswith("---\nname: x-neighbours-maintain\ndescription: >-\n"))
        for phrase in (
            "open one first",
            "branch from it",
            "One change per branch",
            "python3 -m unittest discover -s tests -v",
            "README.md",
            "skills/x-neighbours/SKILL.md",
            "CHANGELOG.md",
            "VERSION",
            "bump the version",
            "Closes #N",
            "Never merge",
            "Never commit personal data",
        ):
            self.assertIn(phrase, text, phrase)

    def test_readme_and_runbook_explain_upgrade(self):
        readme = read(os.path.join(ROOT, "README.md"))
        skill = read(os.path.join(ROOT, "skills", "x-neighbours", "SKILL.md"))
        bot = read(os.path.join(ROOT, "BOT.md"))
        for text in (readme, skill):
            self.assertIn("python3 version.py", text)
            self.assertIn("CHANGELOG.md", text)
            self.assertIn("git pull --ff-only", text)
        self.assertIn("## Upgrading an installed bot", readme)
        self.assertIn("## Upgrading", skill)
        self.assertIn("skills/x-neighbours-maintain/SKILL.md", readme)
        self.assertNotIn("## Upgrading", bot)
        self.assertNotIn("## Rules", bot)
        self.assertIn("skills/x-neighbours/SKILL.md", bot)
        self.assertIn("This file only points there.", bot)
        welcome = "A big thank you to everyone who has helped make X Neighbours better"
        self.assertIn(welcome, readme)
        self.assertEqual(readme.count("## Contributors"), 1)
        self.assertLess(readme.index("## Contributors"), readme.index("## Setup"))
