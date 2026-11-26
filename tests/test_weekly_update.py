#!/usr/bin/env python3
"""Monday update check for every bot, release notes, and the v2 bridge.

The version number is not written into this file. Tests read VERSION.
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

import report_state
import version as version_mod
import versions_release


MONDAY = "2026-11-30T14:00:00Z"
NEXT_MONDAY = "2026-12-07T14:00:00Z"
WEDNESDAY = "2026-11-25T14:00:00Z"


def read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0]


def release_notes():
    path = os.path.join(ROOT, "versions", "latest.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["release_notes"]


class WeeklyCheckTest(unittest.TestCase):
    def test_weekly_check_runs_with_community_off(self):
        import inspect
        self.assertNotIn("community", inspect.signature(version_mod.check_weekly).parameters)
        notes = ["one line", "two line", "three line", "four line"]
        latest = {
            "version": "9.9.9",
            "min_compatible_version": "1.0.0",
            "changelog": "A changelog line that should not lead.",
            "release_notes": notes,
        }
        folder = tempfile.mkdtemp()
        try:
            state = os.path.join(folder, "state.json")
            asked = version_mod.apply_check(latest, path=state, now=MONDAY, local_version="1.0.0")
            self.assertTrue(asked["ask"])
            self.assertTrue(asked["check"])
            self.assertTrue(asked["read_versions"])
            self.assertFalse(asked["pull"])
            self.assertFalse(asked["upgrade"])
            self.assertFalse(asked["executed"])
            self.assertEqual(asked["summary"], notes[:3])
            self.assertNotIn("four line", asked["message"])
            self.assertIn("9.9.9", asked["message"])
            self.assertTrue(asked["message"].endswith("Upgrade?"))
            self.assertFalse(os.path.exists(os.path.join(folder, "community.json")))
            skipped = version_mod.check_weekly("1.0.0", latest, now=WEDNESDAY)
            self.assertEqual(skipped["reason"], "not Monday")
            self.assertFalse(skipped["ask"])
            self.assertFalse(skipped["pull"])
            self.assertFalse(skipped["read_versions"])
        finally:
            shutil.rmtree(folder)

        skill = read("skills/x-neighbours/SKILL.md")
        update = section(skill, "### Monday update check", "## Good Neighbours Newsletter")
        self.assertIn("with community mode off", update)
        self.assertIn("version.py --check", update)
        self.assertIn("git pull --ff-only", update)
        first = read("skills/x-neighbours/FIRST_RUN.md")
        on_request = section(first, "**Only when I ask.**", "Do not create both")
        self.assertIn("Monday update check", on_request)
        self.assertIn("no report routine", on_request)

    def test_a_non_monday_does_not_open_the_version_file(self):
        class Boom:
            def get(self, *_args, **_kwargs):
                raise AssertionError("the Wednesday check read versions/latest.json")

        result = version_mod.check_weekly("1.0.0", Boom(), now=WEDNESDAY)
        self.assertFalse(result["read_versions"])
        self.assertFalse(result["ask"])
        self.assertFalse(result["pull"])
        forced = version_mod.check_weekly(
            "1.0.0",
            {"version": "9.9.9", "min_compatible_version": "1.0.0", "changelog": "Now."},
            now=WEDNESDAY,
            force=True,
        )
        self.assertTrue(forced["ask"])
        self.assertFalse(forced["pull"])

    def test_a_no_is_asked_again_next_week_and_never_pulls_itself(self):
        folder = tempfile.mkdtemp()
        try:
            state = os.path.join(folder, "state.json")
            latest = {
                "version": "9.9.9",
                "min_compatible_version": "9.0.0",
                "changelog": "One line.",
            }
            version_mod.apply_decision(state, "no", "9.9.9", now=MONDAY)
            same_week = version_mod.apply_check(latest, path=state, now=MONDAY, local_version="1.0.0")
            self.assertFalse(same_week["ask"])
            self.assertFalse(same_week["pull"])
            self.assertTrue(same_week["declined"])
            forced = version_mod.apply_check(
                latest, path=state, now=MONDAY, local_version="1.0.0", force=True)
            self.assertTrue(forced["ask"])
            self.assertFalse(forced["executed"])
            next_week = version_mod.apply_check(
                latest, path=state, now=NEXT_MONDAY, local_version="1.0.0")
            self.assertTrue(next_week["ask"])
            self.assertFalse(next_week["pull"])
            yes = version_mod.apply_decision(state, "yes", "9.9.9", requirements_changed=False)
            self.assertTrue(yes["pull"])
            self.assertFalse(yes["executed"])
            self.assertIn("git pull --ff-only", yes["steps"])
            self.assertIn("python3 version.py --notes <old> <new>", yes["steps"])
            self.assertNotIn("pip install", " ".join(yes["steps"]))
            with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as fh:
                source = fh.read()
            self.assertNotIn("subprocess", source)
            self.assertNotIn("os.system", source)
            with open(state, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertIsNone(saved["declined_version"])
        finally:
            shutil.rmtree(folder)

    def test_plan_fetches_versions_and_never_the_global_list(self):
        plan = version_mod.update_plan("v3")
        self.assertTrue(plan["fetch_versions"])
        self.assertFalse(plan["fetch_global"])
        self.assertFalse(plan["pull"])
        self.assertIn("/v3/versions/latest.json", plan["versions_url"])
        self.assertNotIn("global", plan["versions_url"])


class DailyPullTest(unittest.TestCase):
    def test_the_daily_routine_does_not_pull(self):
        skill = read("skills/x-neighbours/SKILL.md")
        day = section(skill, "### Every day", "### Monday, after")
        self.assertIn("Do not `git pull`", day)
        self.assertNotIn("git pull --ff-only", day)
        self.assertNotIn("check-update", day)
        report = section(skill, "### Monday, after", "### Monday update check")
        self.assertNotIn("git pull --ff-only", report)
        self.assertNotIn("check-update", report)


class ReleaseNotesTest(unittest.TestCase):
    def test_current_release_notes_cover_the_owner_facing_changes(self):
        notes = release_notes()
        self.assertGreaterEqual(len(notes), 3)
        self.assertLessEqual(len(notes), 6)
        blob = " ".join(notes).lower()
        self.assertIn("welcome tour", blob)
        self.assertIn("5 latest", blob)
        self.assertIn("page", blob)
        self.assertIn("notifies you", blob)
        self.assertIn("direct reply", blob)
        self.assertIn("likes on your own replies", blob)
        self.assertIn("opt in", blob)
        self.assertIn("asks before", blob)
        with open(os.path.join(ROOT, "versions", "latest.json"), encoding="utf-8") as fh:
            latest = json.load(fh)
        self.assertEqual(latest["release_notes"], notes)

    def test_notes_print_from_latest_json_only(self):
        catalog = [
            {"version": "1.0.0", "release_notes": ["old only", "old two", "old three"]},
            {"version": "1.1.0", "release_notes": ["middle one", "middle two", "middle three"]},
            {"version": "1.2.0", "release_notes": ["new one", "new two", "new three"]},
        ]
        groups = version_mod.notes_between(catalog, "1.0.0", "1.2.0")
        self.assertEqual([number for number, _lines in groups], ["1.1.0", "1.2.0"])
        repo = tempfile.mkdtemp()
        try:
            folder = os.path.join(repo, "versions")
            os.makedirs(folder)
            with open(os.path.join(folder, "1.1.0.json"), "w", encoding="utf-8") as fh:
                json.dump({"version": "1.1.0", "release_notes": ["middle one", "middle two", "middle three"]}, fh)
            with open(os.path.join(folder, "latest.json"), "w", encoding="utf-8") as fh:
                json.dump({"version": "1.2.0", "release_notes": ["new one", "new two", "new three"]}, fh)
            text, found = version_mod.format_range(repo, "1.0.0", "1.2.0")
            self.assertEqual([number for number, _lines in found], ["1.2.0"])
            self.assertIn("- new one", text)
            self.assertNotIn("middle one", text)
            script = os.path.join(ROOT, "version.py")
            result = subprocess.run(
                [sys.executable, script, "--notes", "1.0.0", "1.2.0", "--repo", repo],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), text)
            current = subprocess.run(
                [sys.executable, script, "--notes", version_mod.version()],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(current.returncode, 0, current.stderr)
            self.assertIn("- " + release_notes()[0], current.stdout)
            self.assertIn(version_mod.version(), current.stdout)
        finally:
            shutil.rmtree(repo)

    def test_release_writer_keeps_notes_and_refuses_a_short_list(self):
        repo = tempfile.mkdtemp()
        try:
            with open(os.path.join(repo, "VERSION"), "w", encoding="utf-8") as fh:
                fh.write("1.2.3\n")
            notes = "First line | Second line | Third line"
            document = versions_release.write_release(
                repo, MONDAY, "A Monday line.", "abc", release_notes=notes)
            self.assertEqual(document["release_notes"], ["First line", "Second line", "Third line"])
            again = versions_release.write_release(repo, MONDAY, "A Monday line.", "def")
            self.assertEqual(again["release_notes"], document["release_notes"])
            self.assertEqual(again["source_commit"], "def")
            with self.assertRaises(ValueError):
                versions_release.write_release(
                    repo, MONDAY, "A Monday line.", "abc", release_notes="Only one | And two")
            with open(os.path.join(repo, "versions", "latest.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["source_commit"], "def")
            self.assertFalse(os.path.exists(os.path.join(repo, "versions", "1.2.3.json")))
        finally:
            shutil.rmtree(repo)


class BridgeTest(unittest.TestCase):
    def v2_state(self, folder):
        path = os.path.join(folder, "state.json")
        doc = {
            "version": 1,
            "last_report_at": "2026-11-25T09:00:00Z",
            "since": "2026-11-24T09:00:00Z",
            "until": "2026-11-25T09:00:00Z",
            "replies": 4,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        neighbours = os.path.join(folder, "good_neighbours.json")
        with open(neighbours, "w", encoding="utf-8") as fh:
            fh.write('{"version":1,"neighbours":[{"id":"1","username":"ada"}]}\n')
        return path, neighbours

    def test_v2_bridge_shows_notes_once_and_leaves_user_data(self):
        folder = tempfile.mkdtemp()
        try:
            path, neighbours = self.v2_state(folder)
            with open(neighbours, encoding="utf-8") as fh:
                before = fh.read()
            report_state.record(
                path, at="2026-11-25T09:00:00Z", since="2026-11-24T09:00:00Z",
                until="2026-11-25T09:00:00Z", replies=4, quotes=0, likes=0, reposts=0)
            with open(path, encoding="utf-8") as fh:
                after_report = json.load(fh)
            self.assertNotIn("bot_version", after_report)
            self.assertEqual(after_report["replies"], 4)
            first = version_mod.apply_bridge(path, repo=ROOT)
            self.assertTrue(first["show"])
            self.assertTrue(first["update_routines"])
            self.assertEqual(first["notes"], release_notes())
            self.assertIn("- " + release_notes()[0], first["text"])
            self.assertNotIn("\n", first["owner_line"])
            self.assertIn("Monday check", first["owner_line"])
            self.assertIn("paused", first["paused_routines"].lower())
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["last_report_at"], "2026-11-25T09:00:00Z")
            self.assertEqual(saved["replies"], 4)
            self.assertEqual(saved["bot_version"], version_mod.version())
            self.assertEqual(saved["notes_shown_for"], version_mod.version())
            second = version_mod.apply_bridge(path, repo=ROOT)
            self.assertFalse(second["show"])
            self.assertFalse(second["update_routines"])
            self.assertEqual(second["notes"], [])
            self.assertEqual(second["owner_line"], "")
            with open(neighbours, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)
        finally:
            shutil.rmtree(folder)

    def test_an_explicit_older_major_shows_once(self):
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "state.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "version": 1,
                    "last_report_at": "2026-11-20T09:00:00Z",
                    "bot_version": "2.4.1",
                }, fh)
            first = version_mod.apply_bridge(path, repo=ROOT)
            self.assertTrue(first["show"])
            self.assertTrue(first["update_routines"])
            self.assertEqual(first["from_version"], "2.4.1")
            self.assertEqual(first["notes"], release_notes())
            second = version_mod.apply_bridge(path, repo=ROOT)
            self.assertFalse(second["show"])
        finally:
            shutil.rmtree(folder)

    def test_a_new_bot_does_not_show_the_upgrade_note(self):
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "state.json")
            fresh = version_mod.apply_bridge(path, repo=ROOT)
            self.assertFalse(fresh["show"])
            self.assertFalse(fresh["update_routines"])
            self.assertEqual(fresh["reason"], "new bot")
            again = version_mod.apply_bridge(path, repo=ROOT)
            self.assertFalse(again["show"])
            recorded = report_state.record(
                os.path.join(folder, "created.json"),
                at=MONDAY, since=WEDNESDAY, until=MONDAY,
                replies=1, quotes=0, likes=0, reposts=0)
            self.assertEqual(recorded["bot_version"], version_mod.version())
            self.assertFalse(version_mod.apply_bridge(
                os.path.join(folder, "created.json"), repo=ROOT)["show"])
        finally:
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
