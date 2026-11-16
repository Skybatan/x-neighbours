# Changelog

What changed in X Neighbours, newest first. The version number is the single line in [`VERSION`](VERSION). `version.py` reads that file. Docs point at it and do not keep a second copy.

```bash
python3 version.py
```

## Unreleased

- The house-framed thank-you picture shows each neighbour's display name, with @username on the line below. A missing name stays @username alone. ([#38](https://github.com/Skybatan/x-neighbours/issues/38))
- What's new shows each good neighbour's newest original post. A quote of their own counts. A reply or a plain repost does not. The age is that post's `created_at` against the current UTC time, not the report window. ([#36](https://github.com/Skybatan/x-neighbours/issues/36))

## 2026-11-16

- Contributor bots follow [`skills/x-neighbours-maintain/SKILL.md`](skills/x-neighbours-maintain/SKILL.md): open an issue, branch, one change per pull request, run the tests, update the docs and this changelog, and bump `VERSION` when releasing. An installed bot upgrades in place. The upgrade steps live in [`skills/x-neighbours/SKILL.md`](skills/x-neighbours/SKILL.md). ([#28](https://github.com/Skybatan/x-neighbours/issues/28))
- [`skills/x-neighbours/SKILL.md`](skills/x-neighbours/SKILL.md) is the only runbook. [`BOT.md`](BOT.md) only points there. ([#32](https://github.com/Skybatan/x-neighbours/pull/32))
- GitHub Actions runs the unit tests and an offline report on every pull request and on pushes to `main`. ([#30](https://github.com/Skybatan/x-neighbours/pull/30))
- The Contributors section sits at the top of the README, with a welcome. ([#25](https://github.com/Skybatan/x-neighbours/pull/25), [#35](https://github.com/Skybatan/x-neighbours/pull/35))
- The README thanks [RonySpark](https://github.com/RonySpark) for the first contribution. ([#23](https://github.com/Skybatan/x-neighbours/pull/23))
- A week report no longer crashes when What's new has more than five people and `created_at` is still an ISO string. Waiting is one row per person, and only when their latest message in that thread has no reply. The loader prefers `referenced_tweets` and falls back to `referenced_posts`. Posts, mentions, and likers pass `max_results` 100, and mentions keep paging until there is no `next_token`. ([#19](https://github.com/Skybatan/x-neighbours/pull/19))

## 2026-11-05

- Shorter report header. Suggestion options use the person's name. ([#18](https://github.com/Skybatan/x-neighbours/pull/18))
- The chat report reads on a phone: short sections, and the picture sits in the thank-you message. ([#16](https://github.com/Skybatan/x-neighbours/pull/16))
- Catch up hides a post the owner already liked, replied to, reposted, or quoted. ([#14](https://github.com/Skybatan/x-neighbours/pull/14))
- The owner can file feedback from chat. The bot drafts a link and does not post the issue. ([#12](https://github.com/Skybatan/x-neighbours/pull/12))
- Report sections renamed. A stale report offers a fresh one. ([#11](https://github.com/Skybatan/x-neighbours/pull/11))
- A good neighbours list, and a thank-you on every report. ([#10](https://github.com/Skybatan/x-neighbours/pull/10))

## 2026-11-04

- Catch up keeps original posts. A quote of their own counts. A reply or a plain repost does not. ([#9](https://github.com/Skybatan/x-neighbours/pull/9))
- The README shows the short fictional sample report. ([#8](https://github.com/Skybatan/x-neighbours/pull/8))
- Likes and Reposts drop the Total column. ([#7](https://github.com/Skybatan/x-neighbours/pull/7))
- The first run covers a short window and stays a short report. ([#6](https://github.com/Skybatan/x-neighbours/pull/6))
- Report redesign, with house frames on the neighbours picture. ([#5](https://github.com/Skybatan/x-neighbours/pull/5))
- Three rings, and both the daily and the Monday routine. ([#3](https://github.com/Skybatan/x-neighbours/pull/3))
- A simpler first run, and optional likes-only, replies-only, per-post, and per-day reports. ([#2](https://github.com/Skybatan/x-neighbours/pull/2))
- First published version of X Neighbours.
