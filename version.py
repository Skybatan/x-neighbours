#!/usr/bin/env python3
"""Read the X Neighbours version.

The number is the single line in VERSION, next to this file. Code and docs
read that file. Do not copy the number into another module.
"""
import os
import re
import sys

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def version(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = text[:-1] if text.endswith("\n") else text
    if not body or "\n" in body or body != body.strip() or not SEMVER.fullmatch(body):
        raise ValueError("VERSION must be a single major.minor.patch line")
    return body


def main():
    try:
        print(version())
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
