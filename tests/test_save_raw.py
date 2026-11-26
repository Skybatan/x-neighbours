#!/usr/bin/env python3
"""save_raw follows a truncated write_to_file wrapper to the full payload."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import save_raw


class SaveRawTest(unittest.TestCase):
    def test_full_text_wrapper_is_followed(self):
        folder = tempfile.mkdtemp()
        try:
            payload = {"data": [{"id": "1", "text": "hello"}], "meta": {"next_token": None}}
            full = os.path.join(folder, "full.txt")
            with open(full, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            wrapper = os.path.join(folder, "wrapper.txt")
            with open(wrapper, "w", encoding="utf-8") as fh:
                fh.write("truncated write_to_file display\n")
                fh.write(f"Full text: {full}\n")
                fh.write('{"data": [\x01')
            self.assertEqual(save_raw.load_result(wrapper), payload)
        finally:
            shutil.rmtree(folder)

    def test_plain_json_is_not_followed(self):
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "posts_1.json")
            body = {"data": [], "meta": {}}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(body, fh)
            self.assertEqual(save_raw.load_result(path), body)
        finally:
            shutil.rmtree(folder)
