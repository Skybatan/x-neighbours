# Changelog

What changed in X Neighbours, newest first. The version number is the single line in [`VERSION`](VERSION). `version.py` reads that file. Docs point at it and do not keep a second copy.

```bash
python3 version.py
```

## Unreleased

- The four functions are Period Report, Good Neighbours Newsletter, Neighbours Picture Day, and Community Honor Roll. Page titles use those names. The welcome tour stays titled Welcome tour. File names, flags, and JSON keys are unchanged.
- The founding seed is `submissions/founding/2026-11-26T000000Z.neighbours`. Those accounts enter the global list with source `founding` and one recommendation, credited to `founding` / `founding-submission`.
- `versions/latest.json` is the only release file. `version.py --notes` reads it. The Monday workflow does not write a second copy.
- An owner may share again whenever they want. The global rebuild reads every submission and counts each owner once per account. It opens a pull request for `global/neighbours.global.neighbours` instead of pushing that file onto main.
- `save_raw.py` follows a truncated tool wrapper that names the full payload on a `Full text:` line. Post reads ask for `author_id`, `in_reply_to_user_id`, and `referenced_posts` as expansions. An upgrade that finds paused routines leaves them paused.
- The welcome tour greets the owner first. The first chat message uses their X display name (or @handle when they have no name), says that X Neighbours helps them keep up with the people around their posts, and says how long the tour should take. The Page opens with a short hello. The message that carries the Page link is one line and does not greet them again.
- The welcome tour replaces the “First report” title. The Page opens with how X Neighbours works, a one-line explainer the first time each section appears, and a short What's next (daily, weekly, or only when you ask). Good neighbours and community stay out of the tour. The house-framed picture is inside every report Page; the chat is the headline and the Page link, and the picture is attached in chat only if the Page fails. Reply search plans pages from the posts' `reply_count` (25 a page) and the time estimate counts those pages one after another. The bot is documented as four functions: the report Page, a separate Good neighbours Page, a neighbours picture you can ask for anytime (with a weekly nudge), and a Community Page of recommended accounts. (`trial_post_count`, `--first-run`, and `report_first.*` are unchanged.)
- Every bot checks for an update on Monday and asks before upgrading. There is no daily `git pull`. The check runs with community mode off. After a yes, the bot shows the short release notes for the versions it crossed. Those notes live in `release_notes` on the version file. `python3 version.py --notes` prints them. A bot that arrives from an older daily pull shows the notes once, drops that daily pull, and adds the Monday check.
- A report is delivered as a Page. `report_page.py` fills `templates/report.canvas.tsx` with the same sections, order, and links as the chat report. The canvas file is UTF-8: emoji and punctuation are the characters themselves. The chat message is a short headline and the Page link. The markdown files stay as the plain-text fallback. The good-neighbours card and the community offer stay in the chat.
- The welcome tour is a short demo. It uses the `trial_post_count` latest original posts and quotes (default 5), stays around 15 X reads, and does not fetch followers or following. The header is `Welcome tour`, with a short intro and no good-neighbours card, community opt-in, or share offer. Those wait until the first regular report. 👤? is hidden until a following list is loaded. Before each report the bot says how long it should take and that the owner need not wait. The steps are in [`skills/x-neighbours/FIRST_RUN.md`](skills/x-neighbours/FIRST_RUN.md).
- Likers are fetched only for the owner's original posts and quotes. Replies are skipped even when they have likes. The report still builds when those liker files are absent.
- Reply counts are first-level only. A reply counts when it replies directly to an owner post or quote. After the owner replies in a thread, later replies further down that thread do not count, including unanswered replies, the picture score, and the share check that replies plus quotes are at least 2.
- X reads go out in parallel batches of up to 12, still under 30 a minute.
- A share pull request and the Monday raw URLs use a configurable branch. The default is the checked-out branch, then `main`. Set `share_branch` or pass `--base` (for example `v3`). The founding waiver points at one normal `submissions/<user id>/` file and still credits `founding` / `founding-submission`. Preparing a list requires community mode. The 7-day clock uses committed files only. `pip install` is listed only when `requirements.txt` changed, and the Monday save refuses any other UTC weekday unless `--force`.
- Share checks reject a period that is not 7 to 93 full days, a timestamp in the future, a user id with a leading zero, and a note that hides a link or an @mention. The global rebuild will not follow a waiver path outside the repo, will not drop the two-recommendation rule when the build file asks for fewer, and will not count one owner twice. A broken or pre-release version is not an upgrade. Neighbour Dog flags a closed boost ring, including one with three or more lists.
- Community mode is opt-in and off by default. Individual bots do not check for updates or use the shared list. Community bots get a Sunday share reminder, a Monday check that asks before upgrading, a local copy of the global recommendations, and a reminder to tag @SkyXFunNext when posting the neighbours picture. The bot still does not post. ([#44](https://github.com/Skybatan/x-neighbours/issues/44), [#46](https://github.com/Skybatan/x-neighbours/issues/46))
- A community owner can share an eligible neighbours list as `submissions/<user id>/<timestamp>.neighbours`. The score matches the picture, with a conversation floor, a 100-person cap, and one submission every 7 days. ([#43](https://github.com/Skybatan/x-neighbours/issues/43))
- The global list is rebuilt from each owner's latest submission. An account needs two recommendations, unless it is in the one founding file named by `global/build.json`. That waiver is empty until the maintainer points it at a file. The credit on that file is a neutral founding identity. ([#45](https://github.com/Skybatan/x-neighbours/issues/45))
- Neighbour Dog's runbook reviews share pull requests. GitHub Actions check the file shape and rebuild the global list. Neighbour Dog's token and GitHub account are for the maintainer to configure. ([#47](https://github.com/Skybatan/x-neighbours/issues/47))
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
