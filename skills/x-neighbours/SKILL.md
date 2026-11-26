---
name: x-neighbours
description: >-
  Show who replied, quoted, liked, and reposted the owner, plus who to catch
  up with. Use when the owner asks for X Neighbours, a daily or weekly
  report, the neighbours picture, their good neighbours list, or the Monday
  update check.
---

# X Neighbours — bot runbook

You run this for the owner of this bot. X Neighbours does four things. Keep them separate.

1. **Report.** One Page per report: Flowers, What's new, Replies, and the thank-you. The house-framed picture is inside that Page. The chat message is the headline and the Page link, with no picture. “How to send a report” is the steps. The welcome tour is the first of these Pages. It follows [FIRST_RUN.md](FIRST_RUN.md).
2. **Good neighbours.** Its own Page, titled `Good neighbours`, not a section of the report. It shows the latest post to catch up with for each person on the list, with a link, then the full list with a profile link each. Send it alongside a daily, weekly, or on-request report when the list is not empty, and when they ask to see their good neighbours. The welcome tour does not send it. After that Page link, remind them they can add more. The selector stays in the chat, because a Page cannot take input.
3. **Neighbours picture.** They can ask anytime (“make my neighbours picture”). That picture is not only part of a report. Run `--picture-only` and send the PNG in chat with the thank-you link. Do not post it. The same picture also sits inside each report Page. On the weekly report, add `picture_nudge` after the Page link.
4. **Community.** Its own Page, titled `Community`, from the saved global list: each recommended @handle links to that profile, with the recommendation count. Send it when they ask, and after the Monday save when the file has people. Joining, leaving, and sharing stay in the chat. Do not offer it on the welcome tour. Individual mode does not send it.

You do the X reads. `x_neighbours.py` only reads JSON you saved. Follow every rule in this file on every run. This file is the only copy of these instructions. The root `BOT.md` only points here.

## Rules

- Stay within about **1,000 X reads a day** and **30 a minute**. Send independent reads in parallel batches of up to 12, and stay under 30 a minute. Do not start the next batch until the current one has returned. Count as you go. If the next batch would pass 1,000, stop, render what you have, and tell the owner which posts you skipped.
- For posts, mentions, and likers, always pass `max_results` **100**. Do not omit it (the tool then pages at 25). Keep paging mentions until `meta.next_token` is absent.
- Refresh follower and following lists **at most once a week**. Reuse `data/followers_*.json` and `data/following_*.json` when they are under 7 days old.
- This run is **read-only**. Never follow, unfollow, like, unlike, repost, bookmark, post, reply, or DM. Never open a GitHub issue yourself. If they ask you to follow someone or to post the picture, say this run stays read-only and they can do that in the X app.
- Leave bot accounts out. `@grok` is already in `exclude`. They can name other handles to skip anytime.
- Never commit user data. Do not commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, `report_*.png`, `report_*.canvas.tsx`, `report_*_page.json`, `x_neighbours_*.png`, `good_neighbours.json`, `state.json`, `community.json`, or `global_neighbours.neighbours`. Do not open a pull request with those files. Do not run `git add .`. For a normal run, commit nothing. `git pull` is fine when the owner asked to upgrade: those paths are gitignored. The good neighbours list, the report clock, and community mode live in this bot's own store, outside the repo.
- Community mode is off until the owner opts in. The steps are in [skills/x-neighbours-community/SKILL.md](../x-neighbours-community/SKILL.md). Individual mode does not download the global list, does not share, and does not mention `@SkyXFunNext`. Every bot runs the Monday update check, community mode on or off.
- A community share is the only time you open a GitHub pull request, and only for one submission file, and only by [skills/x-neighbours-share/SKILL.md](../x-neighbours-share/SKILL.md). You still never open a GitHub issue yourself. You still never post, follow, or repost on X.
- Stay on this task. Do not read their DMs, bookmarks, home timeline, or other people's accounts to fill out the picture.
- If the X tools are missing, ask the owner to connect X in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in.

Weights are a quiet setting. The meaning of `like_weight` and `reply_weight` lives only in the config section of [README.md](../../README.md). Do not ask about them before the first picture. Do not repeat the numbers on the picture, in report headings, or in the summary you send.

## Upgrading

An already-installed bot updates the clone it already has. Leave `config.json`, `data/`, and the bot store as they are. Do not pull on a daily schedule. The only scheduled upgrade is the Monday update check, and it pulls only after the owner says yes on that check.

User data stays put: `config.json`, `data/`, the good neighbours file, the report clock in `state.json`, `community.json`, and `global_neighbours.neighbours`.

### Bridge from an older bot

Do this at the start of every run, before any X read and before any pull. Bots installed before this layout pull the clone from their old daily step. The first run on the new code has to notice.

```bash
python3 version.py --bridge --state <state path>
```

The recorded version lives in `state.json` as `bot_version`. An older bot has a report clock and no `bot_version`.

- If `show` is false, say nothing about the version and continue the run.
- If `show` is true, send `text` once. That is the release note: the bullets for the versions this bot moved across. Do not send it again on a later run. The command records that it was shown.
- If `update_routines` is true, change the routines to this runbook. Remove the daily `git pull` step. Add the Monday update check below. An on-request owner still gets that check, and still gets no report routine. Then send `owner_line` and nothing else about the change. That line is one sentence.

A new bot has no report clock yet. The bridge does not show notes and does not rewrite routines. The first report records the running version so a later run does not treat that bot as an upgrade.

### When the owner asks to update now

Skip the Monday wait only when they asked. Still do not pull on your own.

1. From the clone, run `python3 version.py` and keep the line.
2. `git pull --ff-only`. When `requirements.txt` changed, run `python3 -m pip install -r requirements.txt`.
3. Run `python3 version.py` again. When the line changed, run `python3 version.py --notes <old> <new>`, send those bullets, then `python3 version.py --ack --state <state path>` so the bridge does not show them again. The longer history is in `CHANGELOG.md`. The owner sees the short bullets.
4. Leave the good neighbours file, `state.json`, `community.json`, and `global_neighbours.neighbours` in the bot store. The next report uses the updated scripts. Connect X again only when the X tools are missing.

## Welcome tour

The welcome tour is a short demo. Read [FIRST_RUN.md](FIRST_RUN.md) and follow that file only. Do not read the rest of this runbook to produce it. The getting-started skill points at the same file. You run the welcome tour yourself. Do not hand it to a subagent.

The first chat message is `estimate_message` from `--trial-plan`. It greets the owner by the display name in config (`name`, from `get_users_me`), or by `@handle` when that name is blank. The Page opens with `intro`, which starts with that same hello. When the tour is ready, send `headline` and the Page link. That line does not greet them again. Send those fields as they are. Do not write a second hello.

After the owner picks a daily report, a weekly report, or on-request only, later reports follow this file. Create the Monday update check with that choice, including on-request. Do not create both report routines during the welcome tour. Do not offer community mode during the welcome tour. Do not send the Good neighbours Page during the welcome tour.

## Each run

Before the first X read of any report (daily, weekly, or on request), run the bridge under Upgrading. Then count the reads you plan to make and run `python3 x_neighbours.py --estimate-reads <N>`. Send the `message` field to the owner. It says how many minutes the report should take, that they don't need to wait in the chat, and that they will get a notification when it is ready. Then fetch. Deliver the report when it is done, as “How to send a report” says: a Page, then one short chat message. The estimate is the only message you send before the fetches.

A manual run can fetch one window in a single pass. The daily and Monday routines below split the work so Monday reuses that morning's files. Work in the clone. Pick a UTC timestamp `T` when you start fetching. `T` is the actual current UTC time (`date -u +%Y-%m-%dT%H:%M:%SZ`). Pass that as `--now`. Do not reuse a timestamp from an earlier run, from `state.json`, or from a sample such as `2026-11-04T18:00:00Z` (that value is only a shape example). What's new does not age posts from `--now`; a stale `--now` still shifts the Flowers and Replies window.

One fetch covers every window in config. When `week` is on, `START` is `T` minus 7 days. When the config is day-only, `START` is `T` minus 24 hours. The script cuts the 24-hour window out of the same files, so do not fetch twice.

Save each result from the repo directory:

```bash
python3 save_raw.py <tool-result-file> <name>
```

That writes `data/<name>.json`. Raw JSON and text wrapped around one JSON object both work. If you already have the JSON object, you may write `data/<name>.json` yourself.

Call the tools by these names on the owner's X connection. Always pass `max_results` 100 for posts, mentions, and likers; do not omit it (the tool then pages at 25). Page with `pagination_token` set to the previous response's `meta.next_token`. Keep paging while `meta.next_token` is present — a short page is not the end of the list. For mentions, keep calling until there is no `next_token`.

`{ID}` is the owner's user id from config.

### 1. Posts

`get_users_posts`

- `id`: `{ID}`
- `start_time`: `START`
- `exclude`: `retweets`
- `max_results`: `100`
- `post.fields`: `created_at,public_metrics,in_reply_to_user_id,referenced_tweets,conversation_id`
- `expansions`: `author_id,referenced_posts`
- `user.fields`: `username,name,profile_image_url,public_metrics`

Save as `posts_1`, `posts_2`, and so on. On a scheduled run, use `posts_day_*` or `posts_week_*` as the Routines section says. The script loads every `posts_*.json`. Do not pass `exclude=replies`. The owner's own replies have to be in these pages so Replies can tell an original post from a reply, and can see which replies the owner already answered.

`referenced_posts` is how these X tools expand the parent post. Some payloads call that list `referenced_tweets`. Pass both names, and save the whole response, including `includes`. The script reads either name. `conversation_id` is the thread root: it matches the post id on an original post and differs on a reply.

### 2. Mentions

`get_users_mentions`

- `id`: `{ID}`
- `start_time`: `START`
- `max_results`: `100`
- `post.fields`: `created_at,author_id,text,in_reply_to_user_id,referenced_tweets,conversation_id`
- `expansions`: `author_id,referenced_posts`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Save as `mentions_1`, `mentions_2`, and so on, including `includes`. If `meta.next_token` is present, fetch the next page.

`expansions=referenced_posts` puts each mention's direct parent in `includes.posts` or `includes.tweets`. The mention itself still needs `referenced_tweets` or `referenced_posts` with `type` `replied_to` and that parent's id. Without the parent id, the script cannot tell a top-level reply from a later one in the thread.

A reply counts only when it is first-level. The same count is used everywhere: the emoji total, Flowers, the Replies list, unanswered replies, the picture score (`likes + reposts + 3 × (replies + quotes)`), and the share check that replies plus quotes must be at least 2. Do not tell the owner those weights.

Owner posts P. User A replies to P (A1). The owner replies to A1. A replies again (A2). Only A1 counts as A's reply. A2 is not a new reply and it is not an unanswered reply. Once the owner has replied to someone, that person's later replies further down the same thread do not count.

How to see that in the saved JSON:

- The direct parent is `referenced_tweets` (or `referenced_posts`) with `type` `replied_to` and that parent's id. A1's parent is P. A2's parent is the owner's reply, not P.
- That parent must be an owner post or quote that starts the conversation. A starter is an original post (`conversation_id` missing or equal to the post id, no `replied_to`, no `in_reply_to_user_id`) or a quote (`type` `quoted`, and the quote is not itself a reply). Some quotes set `conversation_id` to the quoted post. That quote is still a starter. A reply to it counts.
- `conversation_id` alone is the thread root. A1 and A2 share it. It does not make A2 first-level.
- `in_reply_to_user_id` equal to `{ID}` is not enough. A2 has that too, because A2 is under the owner's reply.

A quote of the owner's post still counts, when the quote is not itself a reply to something else. Never list the owner's own posts or replies, even when they show up in mentions.

### 3. Likers

Do not fetch likers for the owner's replies. A reply is never sent to `get_posts_liking_users`, no matter the `like_count`. The report, the picture score, and a community share still run when those files are absent. Do not fetch them later to fill a gap.

Fetch likers only for original posts and quotes (the posts that start a conversation, same test as in Replies above). For each of those in the fetched window:

- Last 24 hours and `like_count` greater than 0: fetch likers.
- Days 2–7 and `like_count` at least 3: fetch likers.
- Otherwise skip the post.

The same rule is `should_fetch_likers` in `x_neighbours.py`. A reply returns false. The welcome tour uses a different scope (the latest originals and quotes, no day window) and its own read budget. That scope is in [FIRST_RUN.md](FIRST_RUN.md).

`get_posts_liking_users`

- `id`: the post id
- `max_results`: `100`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Save as `likes_<postid>`. If `meta.next_token` is present and the day's budget allows, save the next page as `likes_<postid>_p2`, and so on. One page covers almost every post.

Skip a post you already saved likers for earlier the same day.

### 4. Reposts and quote posts

Same count rule as likes, using `repost_count` and `quote_count`, and this one still includes the owner's replies. Last 24 hours: every post with that count above 0. Days 2–7: only counts of 3 or more. Skip a file you already saved. The reply skip is for likers only.

`get_posts_reposted_by` — `id` the post id, `max_results` 100 (the tool maximum; do not lower it), `user.fields=username,name,description,public_metrics,profile_image_url`. Save as `reposts_<postid>`.

`get_posts_quoted_posts` — `id` the post id, `max_results` 100 (the tool maximum is 100 and the minimum is 10), `post.fields=created_at,author_id,text,referenced_tweets,conversation_id`, `expansions=author_id`, `user.fields=username,name,description,profile_image_url`. Save as `quotes_<postid>`.

### 5. Posts the owner already engaged with

Do this once per run, before the catch-up pages, and only if today's files are missing. At most three calls. If a call fails or the tool is missing, skip it and continue. Do not mention the failure.

`get_users_liked_posts` — `id` `{ID}`, `max_results` 20, `post.fields=id,created_at,author_id`. Save as `my_likes_1`. If `meta.next_token` is present, save one more page as `my_likes_2`, then stop.

`get_users_posts` — `id` `{ID}`, `max_results` 20, no `exclude` (replies and reposts have to be in the page), `post.fields=created_at,text,author_id,in_reply_to_user_id,referenced_tweets,conversation_id`, `expansions=author_id,referenced_posts`. Save as `my_posts_1`. One page only.

Those files, plus replies already in `posts_*.json`, are how Catch up hides a post the owner liked, replied to, reposted, or quoted. A reply's `referenced_tweets` (or `referenced_posts`) id of type `replied_to`, its `conversation_id`, a quote's `quoted` id, and a repost's `retweeted` id all count. The same owner replies tell Replies which mentions are already answered: answered means the owner's reply's `replied_to` id is that mention's id. A page that drops replies, or drops `referenced_posts`, leaves an answered reply marked as not replied.

### 6. Latest post for the catch-up list

Read the good neighbours file first (see Good neighbours). If it lists people, fetch a latest page for each of them, at most 20, and do not also fetch the ranked ten. If the file is missing or the list is empty, pick at most 10 people with the highest quiet score in config (replies and quotes use `reply_weight`, likes use `like_weight`; do not tell the owner the numbers). For each person:

`get_users_posts`

- `id`: their user id
- `max_results`: `100` (the tool maximum). `10` is not enough once posts the owner already liked, reposted, or replied to are skipped
- `exclude`: `replies` and `retweets`. Pass the two values. `exclude=replies,retweets` is the same pair
- `post.fields`: `created_at,text,conversation_id`
- `expansions`: `author_id,in_reply_to_user_id,referenced_posts`
- `user.fields`: `username,name,profile_image_url`

Do not put `author_id`, `in_reply_to_user_id`, or `referenced_tweets` in `post.fields`. On this API those are expansions (`referenced_posts`, not `referenced_tweets`). An unknown post field can fail the call, and the saved page then has no real `created_at`.

Save the whole page as `latest_<userid>`. Copy each post's `created_at` from the tool result. Do not replace it with the fetch time, the report time, or `--now`. If every original post on that page is one the owner already liked, reposted, or replied to, and `meta.next_token` is present, fetch one more page and save it as `latest_<userid>_p2`. Then stop. The script merges those pages.

The script walks the saved posts newest first and keeps one post per neighbour: the newest of their own writing that the owner has not liked, reposted, or replied to. A quote by the owner counts as engaged. A quote post of their own counts as their writing (it is their text). A quote that is also a reply does not. A reply does not (`in_reply_to_user_id`, a `replied_to` reference on `referenced_tweets` or `referenced_posts`, or a `conversation_id` that is not the post's own id). A plain repost does not (`retweeted`, or text starting `RT @`). If that page has no such post, the script skips that person. If nobody is left, the section is one line: “You're all caught up with your good neighbours 🎉”. With an empty list it fills the ten from the next person who still has an unengaged original post. With a list it does not fill from anyone else.

The age on each line is that post's `created_at` against the actual current UTC time when the script runs. It is not `--now`, the report window, or the time the file was saved. Skip a `latest_<userid>` file saved earlier today. A file from a previous day is stale and must be fetched again. Do not skip section 5: those likes, reposts, and replies are what hides a post the owner already engaged with.

### 7. Followers and following

Do this only when `data/followers_1.json` or `data/following_1.json` is missing or older than 7 days, and on the weekly run below.

`get_users_me_followers` and `get_users_me_following`

- `max_results`: `1000`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Page to the end. Save as `followers_1`, `followers_2`, … and `following_1`, `following_2`, …

Overwrite those names as you go. Do not delete the previous files until the new list has reached its last page. If the refresh fails halfway, keep what was already there and tell the owner the relationship tags are from the earlier list.

## Run the script

```bash
python3 x_neighbours.py --now <T> --good-neighbours <path> --state <state path>
```

`<path>` is `good_neighbours.json` in the store. `<state path>` is `state.json` beside it. The script reads `config.json` and `data/`. For each window it writes `report_<window>.md` (sections 1–3), `report_<window>_thanks.md` (section 4), `report_<window>.canvas.tsx` (the Page), and `report_<window>_page.json` (the data that filled the Page), plus `x_neighbours_<window>.png`, the house-framed picture. Each neighbour on that picture is labelled with their display name and, on the line below, their @username. The name is the X user `name` field. Keep `name` in every `user.fields` list in this runbook. When an account has no name, the label is the @username alone. The report card PNG is off unless you pass `--report-card`. Stdout is JSON with totals, `catch_up`, `picture`, `thank_you`, `page_title`, `headline`, `page_canvas`, `page_model`, `messages`, and `fallback_messages`. `thank_you.text` is the thank-you sentence. It names no one. `thank_you.intent` is the post link. `headline` is the one line for the chat. A day window and a fresh on-demand report include `suggest_good_neighbours` and `add_question` when someone in Flowers is not on the list yet. A week window does not. The welcome tour does not: no good-neighbours card, no Good neighbours Page, and `community_offer` is false. It includes `intro` instead. On the welcome tour, `intro` opens with the greeting and `headline` is the short delivery line, not a second greeting. When the list is not empty, a daily, weekly, or on-request report also writes `good_neighbours_page` (`good_neighbours.canvas.tsx`). `--picture-only` draws `x_neighbours_picture.png` and skips the report. `--first-run` uses `trial_post_count` (default 5), not a day window. A missing good neighbours file is an empty list. `--no-picture` skips the image; the default is to draw it every time. `--since <ISO>` is a report that starts at that time. `picture` is the PNG path. `picture_asset` is `asset:` plus that file name. `picture_alt` is the alt text. The success `messages[0].images` list is empty. The picture is on the Page. `fallback_messages` still carries the PNG when the Page fails.

A custom period is `--days 14` (writes `report_custom`). Likes only, replies only, per post, and per day are `--report likes`, `--report replies`, `--per-post`, and `--per-day`. They re-read `data/` and do not need more X calls. Weight flags exist. Keep those values in config only, and never print them.

## How to send a report

The report is a Page. The chat does not get the report body. Do not post, like, or DM anyone. Do not send a report card unless they asked.

The sections, in order, stay as they are. They are written for a phone. Do not turn them into a wide table. Do not add a date range such as Nov 5 – Nov 5.

The Page title is the period. The line under the title is the emoji counts. Those are the first two lines of `report_<window>.md`.

1. The interval. A fresh report is `Since your last report · 30 min ago`, using the real time since the previous report (`min`, `hr`, `day`). A daily report is `Last 24 hours`. A Monday report is `Last 7 days`. The welcome tour is `Welcome tour`.
2. Emoji counts only, including zeros: `💬 3 · 🔁💬 0 · ❤️ 0 · 🔁 0`. No words beside those numbers.

Then the sections. The headings are short:

1. **💐 Flowers** — one person per block. The name is the only link. Counts sit on the next line (`2 replies · 4 likes · 1 repost`). Replies means replies plus quote posts. Biggest supporters first. No Total column and no second @handle.
2. **🏡 What's new** — the post preview is the link. No @handle and no separate “Read post” link. Same people as Catch up: good neighbours when the list has anyone, otherwise the top people from the period. One post per person: their newest original (a quote of their own counts; a reply or a plain repost does not) that the owner has not liked, reposted, or replied to. The age is that post's `created_at` against the actual current UTC time, not `--now`.
3. **👋 Replies** — first-level replies and quote posts only, unanswered first, newest first inside the unanswered group and inside the answered group, one block each, no nested bullets. The preview text is a link to that reply or quote (`url`), so the owner can open it and answer. A reply counts only when its direct `replied_to` parent is an owner post or quote that starts the conversation. A later reply in the thread, under the owner's reply, does not count, and the owner's own posts are never listed. Replies the owner already answered directly are left out. The report says how many, and they can ask to see them. Shown answered text says `Replied`, never `Not replied yet`. The “ago” time is that post's `created_at` against the actual current UTC time, not the report window end.

On the Page, a name and the line under it are separate lines, with the same words as the markdown. The name link and the post link are link components. A legend line, when there is one, sits under the counts. An empty section is left out. The sentence the markdown uses for an empty stretch stays, without a heading.

Each section shows at most five entries. A last line says how many are left (`+3 more in Flowers. Ask to see them.`). Those entries are in `more_json` (`report_<window>_more.json`): `flowers`, `catch_up`, `greetings_unanswered`, and `greetings_answered`. If they ask for more, or for the answered greetings, send each greeting's `markdown` field in the chat. That text already links the preview to `url` and says `Replied` when `replied` is true, or `Not replied yet` when it is false. Do not relabel an answered greeting as not replied. Do not fetch X again. Do not paste the whole file. That file is this report only, not an older history.

⭐ next to a name means they are on the good neighbours list. The legend “⭐ = good neighbour” appears only when that list is non-empty. 👤? means the owner does not follow that person. It is shown only when a following list was loaded. The welcome tour does not fetch that list, so it does not show 👤? or that legend. Do not add a followed/unfollowed split, a follow-back list, or impressions.

When per-post or per-day is on, those extra sections are on the Page too, after Replies and before the thank-you.

The thank-you block on the Page is `thank_you.text`, then the link `thank_you.intent` with the label “Post your thank-you”, then `thank_you.note`: “Save the picture and attach it in X before posting.” The house-framed picture is in that same block. The link only opens a composer with the words. It does not attach the picture. Never say that tapping the link posts the image. Do not post the thank-you yourself. On the welcome tour, What's next follows the thank-you.

**The Page.** `page_canvas` is `report_<window>.canvas.tsx`. The script fills it from `templates/report.canvas.tsx`. Do not write that file by hand.

In community mode, before WriteCanvas, run picture-tag from the community skill. When `remind` is true, rewrite the Page so the thank-you link is `intent` and `text` follows the note:

```bash
python3 report_page.py --model <page_model> --thank-intent "<intent>" --thanks-extra "<text>"
```

`<page_model>` is `report_<window>_page.json`, the same path as `page_model`. When `remind` is false, skip that command. The welcome tour does not run picture-tag. When the posting account is already `@SkyXFunNext`, picture-tag says `remind` false. That reminder is the only @handle, and you still do not post the picture. Keep `--picture-asset` on that rewrite when `picture_asset` is set, so the picture stays on the Page:

```bash
python3 report_page.py --model <page_model> --thank-intent "<intent>" --thanks-extra "<text>" --picture-asset "<picture_asset>"
```

Pass the whole canvas file to WriteCanvas. The title is `page_title`. Do not pass a canvas id on this first write. Each report gets its own Page, including a routine run and a run that says the same thing as the last one. `report_<window>.md` is overwritten every time and is not a history of past reports, so reusing one Page would change the report an older chat link still opens.

WriteCanvas returns a url and a canvas id. If it fails or returns no url, use the plain-text fallback below. Do not invent a link.

When `picture` is set, upload it onto that Page. Call WriteCanvasAsset with the canvas id, the file name (the part of `picture_asset` after `asset:`), and the path `picture`. The upload returns width and height. Set the ratio with:

```bash
python3 report_page.py --model <page_model> --picture-ratio "<width>/<height>"
```

Pass the same thank-intent and thanks-extra when picture-tag rewrote the link. WriteCanvas again with the same canvas id. The Image `src` is `asset:<file name>`, `alt` is `picture_alt`, and `ratio` is width/height from the upload. A tag before the upload shows its alt until the picture is there.

**The chat message.** One message, after the Page exists. The text is `headline`, then the Page link. `headline` is the period, the emoji counts, and, when replies are waiting, how many (`2 replies to answer`). On the welcome tour, `headline` is a short line (`Here's a quick welcome tour of your N latest posts.`), not the counts and not a second hello. The greeting was the earlier `estimate_message`, and it opens the Page. Label the link with `page_title`. The host shows that link as a card. Do not paste the sections, `report_<window>.md`, or `thank_you.text` into the chat. Do not put the PNG in that message. `messages[0].images` is empty on purpose. In individual mode the chat message has no @handle.

**Good neighbours Page.** If `good_neighbours_page` is present, send it after the report message. It is a second Page. Pass `good_neighbours.canvas.tsx` to WriteCanvas. Do not pass a canvas id. The title is `Good neighbours`. The chat line is `good_neighbours_page.headline` and that Page link. No picture on that message. Then remind them they can add more: if `add_question` is present, send that card and do not also send `add_reminder`. If `add_question` is absent, send `add_reminder` as one line. Do not send this Page on the welcome tour.

**Neighbours picture on its own.** When they ask to make a neighbours picture and they did not ask for a report, run:

```bash
python3 x_neighbours.py --now <T> --picture-only --good-neighbours <path>
```

That uses the last 7 days of saved data, or `--days` when they name a length. Send one chat message: `headline`, the thank-you link, and the PNG in `images`. Do not post it. Do not also send a report Page unless they asked for a report. The picture inside a report Page is separate and still happens on every report.

**Then the chat widgets, or nothing.** A Page cannot record a choice, so these stay in the chat, after the Page link.

If `add_question` is absent, do not send the ⭐ Add card. If it is present, send one multi-select question card. The short label is **⭐ Add**. The prompt is “Add to good neighbours?”. Use each option's `label` exactly. It is `Display Name (@username)`, with a ⭐ in front only when that person is already a good neighbour. Do not shorten it to `@handle`. There is one free-text option (“Or name anyone else”). Do not also paste that list into the Page or the chat message. Do not look anyone else up on X to invent suggestions. Do not send the card on the Monday report or the welcome tour. When they pick someone, add them with `good_neighbours.py`. Use the id and name already in `suggest_good_neighbours`. Call `get_users_by_username` only for a handle that is not in that list.

On the Monday report, after the report Page message, add `picture_nudge` and then `feedback_line`. Do not fetch anything for them. Do not send the ⭐ Add card. The Good neighbours Page, when `good_neighbours_page` is present, is its own message as above.

The welcome tour does not send the ⭐ Add card, the Good neighbours Page, a community offer, or a share card. The greeting is already the first chat message and the opening of the Page. Do not add a second greeting or a second introduction. Then ask `next_steps` in the chat.

**Plain-text fallback.** If WriteCanvas fails or returns no url, send two chat messages and no Page link. Message 1 is the text of `report_<window>.md` and no image. Message 2 is `thank_you.text`, a blank line, the link `thank_you.intent` with the label “Post your thank-you”, a blank line, and `thank_you.note`, with the PNG in that message's `images`. Those two messages are `fallback_messages`. Then the same widgets as above. In community mode, when picture-tag says `remind`, use its `intent` for that fallback link and add its `text` after the note.

Profile photos are not drawn beside names. A Page does not fetch a web image, and a chat gallery cannot line a small photo up with each person. Each person in `more_json` has an `avatar` field when the saved user data includes `profile_image_url`. Leave those URLs unused. Do not invent a screenshot of the list.

## Routines

Create a report routine only after the welcome tour, and only the one the owner picks. Daily is every day at 9:00. Weekly is Mondays at 9:00. On-request creates no report routine. Every choice also creates the Monday update check. They can add the other report later by asking. Tell them the time can be changed.

Both report routines run at 9:00 AM in the owner's timezone. Count every X call from both toward the same cap: about 30 a minute and 1,000 a day. On Monday, run the daily job first, then the weekly job, and do not fetch the last 24 hours twice. The Monday update check runs after those reports and does not fetch X.

### Every day

1. Do not `git pull`. Do not download `versions/`. The Monday update check is the only scheduled upgrade, and it runs with community mode off or on. Leave `config.json` and `data/` uncommitted. The bridge under Upgrading already ran at the start of this run.
2. Do not refresh followers or following.
3. Pick `T`. `START` is `T` minus 24 hours.
4. Fetch posts and mentions from `START`. Save them as `posts_day_1`, `posts_day_2`, … and `mentions_day_1`, ….
5. Fetch likers only for original posts and quotes (never the owner's replies), and fetch reposters and quote posts, with the budget rule above. Skip files you already have. Before the first read, send the estimate from `--estimate-reads`.
6. If today's `my_likes_1.json` or `my_posts_1.json` is missing, fetch those small pages (section 5). Then fetch latest posts (`latest_<userid>.json`) for each good neighbour, or for the ranked ten when the list is empty.
7. Run `python3 x_neighbours.py --now <T> --windows day --good-neighbours <path> --state <state path>`.
8. Send the report with “How to send a report”: one Page titled with the period, then a short chat message (`headline` and the Page link, no picture). The picture is inside the Page. Then the Good neighbours Page when `good_neighbours_page` is present, then the ⭐ Add card if `add_question` is present. If they pick someone, add them with `good_neighbours.py`.

Leave the files in place. Later reports filter them by time.

### Monday, after that day's daily run

If today's `posts_day_1.json` is missing, do the daily run first.

1. Refresh followers and following. This is the only day that does.
2. Reuse today's posts, mentions, likes, reposts, quotes, `my_likes_*.json`, `my_posts_1.json`, and latest-post files. Do not request the last 24 hours again.
3. If saved posts already cover `T` minus 7 days through `T` minus 24 hours, do not page posts or mentions for that span. Fetch only missing liker, reposter, and quote files for older original posts and quotes whose count is 3 or more. Do not fetch likers for the owner's replies.
4. If that span is missing, fetch it once: `get_users_posts` and `get_users_mentions` with `start_time` of `T` minus 7 days and `end_time` of `T` minus 24 hours. Save as `posts_week_1`, … and `mentions_week_1`, …. Then the same 3-or-more rule for likes, reposts, and quotes. Refresh `latest_<userid>.json` for each good neighbour, or for the catch-up ten when the list is empty, and only if today's file is missing.
5. Run `python3 x_neighbours.py --now <T> --windows week --good-neighbours <path> --state <state path>`. Do not send the ⭐ Add card on this report.
6. Send the report with “How to send a report”: one Page titled with the period, then a short chat message (`headline` and the Page link, no picture). Do not post it. Do not send a report card unless they asked for `--report-card`. Do not send the ⭐ Add card. If `good_neighbours_page` is present, send that Page and then `add_reminder` as one line. After the report message, add `picture_nudge` (they can ask anytime for a neighbours picture to post) and `feedback_line`: “Anything you'd change about X Neighbours? Tell me and I'll turn it into a feedback link.” Do not fetch anything for those lines.
7. Do not check versions here and do not download the global list here. That is the Monday update check, which runs after this report.

If the Monday calls would pass about 1,000 for the day, send the day picture you already have, fetch the older posts and mentions, and stop the liker lists when the cap is close. Tell the owner which older posts were left out.

### Monday update check

Create this routine for every owner after the welcome tour, when they pick a daily report, a weekly report, or on-request only. It is its own routine. On-request owners get this check and no report routine. Daily owners do not also get the Monday report routine. Weekly owners get both the Monday report and this check.

Mondays at 9:00 in the owner's timezone, or UTC if you don't know it. It does not fetch X. If a report routine is also running that morning, send the report first, then run this.

Run it with community mode off, and run it when community mode is on. Do not skip it because they have not joined. Do not use `community.py plan` to decide. That plan leaves `fetch_versions` false when community mode is off. This routine uses `version.py --plan`, which always fetches the version file and never fetches the global list.

1. Run the bridge under Upgrading if this session has not already.
2. Do not `git pull` yet.
3. Run `python3 version.py --plan --repo . --config config.json`. Download `versions_url` to a temp file. Do not commit it. `fetch_global` is false. Do not open the global URL.
4. Run:

```bash
python3 version.py --check --latest <temp file> --state <state path> --now <T>
```

`<T>` is the current UTC time. On any UTC day other than Monday the command returns `reason` `not Monday` and does not compare versions. Stop. Do not pull and do not save the global list. If they ask to check on another day, add `--force`. Still ask before pulling. Do not save the global list on that extra check.

5. If `ask` is true, send `message` as one yes/no card. It names the version and a 1–3 line summary. Do not `git pull` yet.
6. If they say no:

```bash
python3 version.py --decide no --version <remote_version> --state <state path> --now <T>
```

Stay on the current version. Ask again next week. Do not pull.
7. If they say yes:

```bash
python3 version.py --decide yes --version <remote_version> --state <state path>
```

`executed` is false. `pull` is true only so you know they agreed. You run the `steps` yourself. `git pull --ff-only` only. Run `python3 -m pip install -r requirements.txt` only when a step says to, which is when `requirements.txt` changed. Keep the `local_version` from the check and pass it as `<old>`. Pass `remote_version` as `<new>`.

```bash
python3 version.py --notes <old> <new>
```

Send those bullets. That is the release note, 3 to 6 short lines. Then:

```bash
python3 version.py --ack --state <state path>
```

so the bridge does not show the same note again. Keep `config.json`, `data/`, the good neighbours file, `state.json`, `community.json`, and `global_neighbours.neighbours`.
8. If `ask` is false, do not pull and do not send a card.
9. If community mode is on, save the global list with the community skill, including when there was no new version. If community mode is off, do not download the global file.

## Good neighbours

The list is personal. Keep it outside the repo, in this bot's own persistent store, next to the report clock:

`/cursor/stores/<store-id>/x-neighbours/good_neighbours.json`

`/cursor/stores/<store-id>/x-neighbours/state.json`

`<store-id>` is this bot's store, the directory under `/cursor/stores/` that belongs to this bot. Create `x-neighbours` when you add the first person. Pass that path as `--good-neighbours` on every run. A missing file is an empty list. Never commit the file.

```json
{"version":1,"neighbours":[{"id":"123","username":"ada","name":"Ada Brook","added":"2026-11-04"}]}
```

Each person has `id`, `username`, `name`, and `added` as `YYYY-MM-DD`. No other fields. At most 20 people.

The owner manages it in chat:

- “add @handle” or “add @handle to my good neighbours”
- “remove @handle”
- “show my good neighbours”

Edit the file with `good_neighbours.py`. Do not hand-edit it.

```bash
python3 good_neighbours.py --file <path> add <handle> --id <id> --name "<name>"
python3 good_neighbours.py --file <path> remove <handle>
python3 good_neighbours.py --file <path> list
```

`add` is idempotent: someone already on the list stays as they are. The script refuses a 21st person. `remove` of someone who is not listed is a no-op.

To add someone:

1. If the list already has 20 people, say it is full and ask who to remove. Do not add.
2. If this report's `suggest_good_neighbours` already has their id and name, use those. Otherwise look the handle up with the X plugin `get_users_by_username` (`usernames` set to that handle, `user.fields=id,name,username`). If there is no user, say so. Do not invent an id.
3. Run `add` with the username, `--id`, and `--name`.
4. Confirm with their name and @handle.

To remove someone, run `remove`. To show the list, render the Good neighbours Page. That needs no X call when `latest_<userid>.json` is already saved. If those files are missing, say the latest posts are not loaded yet and still show the names from `list`.

```bash
python3 good_neighbours_page.py --data data --user-id <id> --good-neighbours <path> --out <dir>
```

If `send` is false, the list is empty. Say so in one line and ask who to add. Do not invent a Page. If `send` is true, WriteCanvas the canvas file. The title is `Good neighbours`. The chat message is `headline` and the Page link, then `add_reminder` (or the ⭐ Add card when a report's `add_question` is in hand). Do not put a selector on the Page.

Adding someone does not follow them. This run stays read-only on X.

When the list is non-empty, Catch up with your good neighbours shows only those people, each one's latest original post the owner has not already liked, replied to, reposted, or quoted, and skips anyone with no such post. A quote of their own counts as that original post; a reply or a plain repost does not. The age is the post's `created_at` against the current UTC time. They are not inserted into the other sections just because they are on the list. When the list is empty, Catch up stays the top 10 from the period, with the same skip, and the report adds: “Add people to your good neighbours list to keep up with them here.” If nothing is left to show, the section is “You're all caught up with your good neighbours 🎉”.

After a daily report and a fresh on-demand report, the script lists up to five people from Flowers who are not on the list yet, in Flowers order. They are in `suggest_good_neighbours`. If nobody is left, `add_question` is absent and you skip the card. Send one multi-select card, short label **⭐ Add**. Each option label is `Display Name (@username)` from the `label` field. Do not rewrite it to the handle alone. Add a free-text option (“Or name anyone else”). A weekly report does not ask with the card. It sends `add_reminder` only when the Good neighbours Page went out. The welcome tour does not ask either. The first daily, weekly, or on-request report after it is the first time you send that card.

## Community and sharing

Community mode, the Sunday reminder, the Monday global-list save, the Community Page, and the picture-tag line are in [skills/x-neighbours-community/SKILL.md](../x-neighbours-community/SKILL.md). Sharing a list is in [skills/x-neighbours-share/SKILL.md](../x-neighbours-share/SKILL.md). Both stay off until `community.json` says they joined. The Monday update check does not. Recommendations are not follows. You never post the picture or the proof code. Opt-in and the share flow stay in the chat. The Community Page only shows the saved global list.

## When they just say hello

If the owner opens the chat or sends a greeting with no specific request (no report, no picture, no list change, no settings), check freshness and do nothing else until they answer.

```bash
python3 report_state.py --file <state path> check
```

If `config.json` has `fresh_hours`, add `--hours` after `check`. Otherwise leave it off and the script estimates from the last report.

If `ask` is false, reply with one line that the last report is still fresh (`age_label`) and stop. Do not fetch.

If `ask` is true, send one yes/no question card with `question` and stop. Do not fetch, and do not send a report, until they answer. The usual question is “Your last report was 2 hours ago. Want a fresh one?”

If they say no, stop. If they say yes, run a fresh report. Before the first X read, send the estimate from `--estimate-reads`. `START` is `fetch_since` from that check (the end of the last report, or 24 hours ago when there is no report, and never more than 7 days). Pass it as `--since`. Use the same read budget as a daily run when the gap is under 24 hours, and the days-2-to-7 budget when it is longer. Then send the report with “How to send a report” and pass `--state` so the clock updates.

```bash
python3 x_neighbours.py --now <T> --since <fetch_since> --good-neighbours <path> --state <state path>
```

The estimate, unless `fresh_hours` is set: 60 or more replies, quote posts, likes, and reposts per 24 hours is a big account (ask after 1 hour); 15 to 59 is medium (ask after 3 hours); under 15 is small (ask after 8 hours).

## Feedback

Offer this for any concern the owner mentions: a complaint, a wish, a nit, or a “what if”. Stay light. One offer per topic in this conversation, never a follow-up push. The Monday report already asks once, in a single line; if they answer that line, treat it as the concern and offer the link the same way.

1. Answer the point in a sentence or two.
2. Ask once, as a yes/no card: “Want to report this so it gets fixed?”
3. If they say no, drop it. Do not ask again about that same point in this conversation.
4. If they say yes, draft a short issue and show it before any link. Title is one line. Body has what they expected, what happened, the report type (daily, weekly, first, fresh, or other), the version from `python3 version.py` (the line in `VERSION`), and the short git SHA from `git rev-parse --short HEAD`.
5. Leave out every personal detail: handles, names, post text, the good neighbours list, avatars, ids, and tokens. Describe the behaviour, not the people.
6. When they accept the draft, build the link. Do not post it.

```bash
python3 feedback_link.py --title "Catch up hid an original post" --body "$(cat <<'EOF'
What I expected
Catch up should keep an original post.

What happened
A quote of their own post was left out of Catch up.

Report
- Type: daily
- Version: (paste `python3 version.py`) (abc1234)
EOF
)"
```

The script prints JSON. `url` is `https://github.com/Skybatan/x-neighbours/issues/new?title=...&body=...&labels=feedback`, URL-encoded, and kept under 7500 characters. Send that URL. The owner taps it and submits the issue themselves. You never call the GitHub API, never run `gh issue create`, and never submit the form.

If the script says the draft contains a handle or a secret, rewrite the draft without that and run it again. If `shortened` is true, tell them the draft was shortened to fit the link.
