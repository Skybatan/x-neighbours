#!/usr/bin/env python3
"""House-framed picture labels use the account display name and @username."""
import os
import sys
import tempfile
import unittest
from collections import Counter
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x_neighbours as xn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "offline")


class PictureLineTest(unittest.TestCase):
    def test_display_name_sits_above_the_handle(self):
        self.assertEqual(
            xn.picture_lines({"username": "ada_brook", "name": "Ada Brook"}),
            ("Ada Brook", "@ada_brook"),
        )

    def test_blank_name_falls_back_to_the_handle(self):
        for name in (None, "", "   ", "\n"):
            self.assertEqual(
                xn.picture_lines({"username": "ada_brook", "name": name}),
                ("@ada_brook",),
                name,
            )

    def test_missing_username_keeps_the_display_name(self):
        self.assertEqual(xn.picture_lines({"name": "Ada Brook"}), ("Ada Brook",))
        self.assertEqual(xn.picture_lines({}), ())

    def test_newlines_in_a_name_stay_on_one_line(self):
        self.assertEqual(
            xn.picture_lines({"username": "ada_brook", "name": "Ada\nBrook"}),
            ("Ada Brook", "@ada_brook"),
        )

    def test_saved_json_keeps_the_display_name_for_the_picture(self):
        data = xn.Data(FIXTURES, "100")
        self.assertEqual(xn.picture_lines(data.users["201"]), ("Pat Wait", "@waitalot"))
        self.assertEqual(xn.picture_lines(data.users["202"]), ("Quinn Posts", "@postsonly"))


class LabelFitTest(unittest.TestCase):
    def test_long_latin_name_truncates_with_an_ellipsis(self):
        face = xn.LabelFace(28, bold=True)
        text = "North Window Ledger And Paper Kite Society"
        limit = 140
        self.assertGreater(face.width(text), limit)
        fitted = face.fit(text, limit)
        self.assertTrue(fitted.endswith("…"))
        self.assertLessEqual(face.width(fitted), limit)
        self.assertLess(len(fitted), len(text))

    def test_short_name_is_not_truncated(self):
        face = xn.LabelFace(28, bold=True)
        self.assertEqual(face.fit("Ada Brook", 400), "Ada Brook")

    def test_hangul_and_cjk_use_a_covering_font(self):
        face = xn.LabelFace(32, bold=True)
        if face.cjk is None or not xn._font_covers(face.cjk, "한"):
            self.skipTest("no Hangul font installed")
        self.assertEqual(face.kind("한"), "cjk")
        self.assertEqual(face.kind("你"), "cjk")
        self.assertEqual(face.kind("あ"), "cjk")
        self.assertEqual(face.kind("A"), "primary")
        text = "김하늘과푸른바다"
        limit = 90
        self.assertGreater(face.width(text), limit)
        fitted = face.fit(text, limit)
        self.assertTrue(fitted.endswith("…"))
        self.assertLessEqual(face.width(fitted), limit)
        self.assertNotIn("\ufffd", fitted)

    def test_hangul_pixels_are_not_the_latin_font_boxes(self):
        from PIL import Image, ImageDraw
        face = xn.LabelFace(40, bold=True)
        if face.kind("한") != "cjk":
            self.skipTest("no Hangul font installed")
        mixed = Image.new("L", (280, 80), 0)
        ImageDraw.Draw(mixed)
        face.draw(ImageDraw.Draw(mixed), mixed, "한글", 4, 8, 255)
        primary = Image.new("L", (280, 80), 0)
        ImageDraw.Draw(primary).text((4, 8), "한글", font=face.primary, fill=255)
        self.assertGreater(sum(mixed.tobytes()), 80)
        self.assertNotEqual(mixed.tobytes(), primary.tobytes())

    def test_emoji_stays_whole_and_uses_the_emoji_font(self):
        face = xn.LabelFace(28, bold=True)
        family = "👨‍👩‍👧‍👦"
        self.assertEqual(xn.text_clusters(family), [family])
        self.assertEqual(xn.text_clusters("Ada 🙂"), ["A", "d", "a", " ", "🙂"])
        if face.emoji is None:
            self.skipTest("no color emoji font installed")
        self.assertEqual(face.kind("🙂"), "emoji")
        self.assertEqual(face.kind(family), "emoji")
        self.assertEqual(face.kind("❤️"), "emoji")
        limit = face.width("Hi") + 2
        fitted = face.fit("Hi " + family, limit)
        self.assertNotIn("\u200d", fitted)
        self.assertNotIn("👨", fitted)
        kept = face.fit("Nova 🙂 Lane", 10000)
        self.assertIn("🙂", kept)

    def test_unrenderable_name_falls_back_to_the_handle(self):
        name_face = xn.LabelFace(28, bold=True)
        handle_face = xn.LabelFace(20, bold=False)
        lines = xn.picture_lines({"username": "ada_brook", "name": "\ue000\ue001"})
        self.assertEqual(lines[1], "@ada_brook")
        drawn = xn.fitted_picture_lines(lines, name_face, handle_face, 400)
        self.assertEqual(drawn, ["@ada_brook"])

    def test_emoji_name_still_draws(self):
        from PIL import Image, ImageDraw
        face = xn.LabelFace(32, bold=True)
        if face.kind("🙂") != "emoji":
            self.skipTest("no color emoji font installed")
        image = Image.new("RGBA", (180, 80), (10, 14, 39, 255))
        draw = ImageDraw.Draw(image)
        face.draw(draw, image, "Ada 🙂", 4, 8, (255, 255, 255, 255))
        colors = image.getcolors(maxcolors=50000) or []
        colorful = [count for count, rgba in colors if rgba[0] > 180 and rgba[1] > 140 and rgba[2] < 80]
        self.assertTrue(colorful)


class PictureRenderTest(unittest.TestCase):
    def _users(self):
        return {
            "1": {"id": "1", "username": "fewcreator", "name": "Few Creator"},
            "2": {"id": "2", "username": "ada_brook", "name": "Ada Brook"},
            "3": {"id": "3", "username": "no_name"},
            "4": {"id": "4", "username": "kim_haneul", "name": "김하늘 🙂"},
            "5": {"id": "5", "username": "long_paper", "name": "A Very Long Paper Neighbourhood Display Name"},
            "6": {"id": "6", "username": "yamada_hana", "name": "山田 花"},
        }

    def _draw(self, users, path):
        scores = Counter({"2": 5, "4": 4, "5": 3, "6": 2, "3": 1})
        xn.draw_circle(
            SimpleNamespace(me="1", users=users), users["1"], scores, path,
            rings=1, show_names=True, width=640,
            subtitle="Top neighbours of the last 2 days")

    def test_display_names_change_the_rendered_picture(self):
        users = self._users()
        self.assertEqual(xn.picture_lines(users["2"]), ("Ada Brook", "@ada_brook"))
        self.assertEqual(xn.picture_lines(users["3"]), ("@no_name",))
        self.assertEqual(xn.picture_lines(users["4"])[0], "김하늘 🙂")
        folder = tempfile.mkdtemp(prefix="xn-labels-")
        named = os.path.join(folder, "named.png")
        handles = os.path.join(folder, "handles.png")
        self._draw(users, named)
        blank = {uid: {k: v for k, v in user.items() if k != "name"} for uid, user in users.items()}
        self._draw(blank, handles)
        self.assertGreater(os.path.getsize(named), 1000)
        with open(named, "rb") as fh:
            named_bytes = fh.read()
        with open(handles, "rb") as fh:
            handle_bytes = fh.read()
        self.assertNotEqual(named_bytes, handle_bytes)


if __name__ == "__main__":
    unittest.main()
