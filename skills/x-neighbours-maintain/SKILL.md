---
name: x-neighbours-maintain
description: >-
  Update the X Neighbours repo the same way every time. Use when a
  contributor's bot changes X Neighbours, opens a pull request, edits the
  runbook, or releases a version.
---

# X Neighbours — maintainer runbook

You change this repo for a contributor. Follow every rule in this file. The owner reviews and merges. You never merge.

## Before you edit

1. Start from an issue. When the change has no issue, open one first. One issue is one change.
2. Update `main`, then branch from it. Commit on that branch.
3. Leave other open issues on their own branches. Add `CONTRIBUTING.md` or a pull request template only when that is the issue you are closing. Add another GitHub Actions workflow only when that is the issue. [`skills/x-neighbours/SKILL.md`](../x-neighbours/SKILL.md) is the only runbook. `BOT.md` only points there. Do not paste the runbook back into `BOT.md`.

## One change

One change per branch and per pull request. When you find a second problem, open another issue and stop.

- Add or update tests for the behavior you changed.
- Run `python3 -m unittest discover -s tests -v`. Open the pull request only after it passes.
- Update the docs the change touches:
  - [`README.md`](../../README.md)
  - [`skills/x-neighbours/SKILL.md`](../x-neighbours/SKILL.md), the bot instructions, and the only copy. `BOT.md` only points at that file. Edit the skill. Do not paste runbook text into `BOT.md`.
  - [`CHANGELOG.md`](../../CHANGELOG.md). Add a dated section at the top for what changed, and link the issue or the pull request.
- When you release, bump the version. The number is the single line in [`VERSION`](../../VERSION). Replace that line. A fix bumps the last number. A feature bumps the middle number and sets the last number to 0. `version.py` reads `VERSION`. Check with `python3 version.py`. The README, the runbook, this skill, and the changelog do not copy the number.

## Pull request

Open a pull request against `main`. The body includes a line `Closes #N`, where N is the issue number.

Never merge. Never enable auto-merge. Never run a merge command. The owner reviews and merges.

## Personal data

Never commit personal data. Never commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, `report_*.png`, `x_neighbours_*.png`, `good_neighbours.json`, or `state.json`. Never commit real handles, real names, user ids, post text, avatars, or tokens. The fictional samples under `examples/` are the only account-shaped data that belongs in git. Never run `git add .`.
