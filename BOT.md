# X Neighbours — bot runbook

You run this for the owner of this bot. It shows who replied, quoted, liked, and reposted, then who to catch up with. The ring picture is separate, with a house frame around every avatar, and only some Mondays include it.

You do the X reads. `x_neighbours.py` only reads JSON you saved. Follow every rule in this file on every run.

## Rules

- Stay within about **1,000 X reads a day** and **30 a minute**. Send about 12 calls, then pause. Count as you go. If the next batch would pass 1,000, stop, render what you have, and tell the owner which posts you skipped.
- Refresh follower and following lists **at most once a week**. Reuse `data/followers_*.json` and `data/following_*.json` when they are under 7 days old.
- This run is **read-only**. Never follow, unfollow, like, unlike, repost, bookmark, post, reply, or DM. If they ask you to follow someone or to post the picture, say this run stays read-only and they can do that in the X app.
- Leave bot accounts out. `@grok` is already in `exclude`. They can name other handles to skip anytime.
- Never commit user data. Do not commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, `report_*.png`, or `x_neighbours_*.png`. Do not open a pull request with those files. Do not run `git add .`. For a normal run, commit nothing. `git pull` is fine: those paths are gitignored.
- Stay on this task. Do not read their DMs, bookmarks, home timeline, or other people's accounts to fill out the picture.
- If the X tools are missing, ask the owner to connect X in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in.

Weights are a quiet setting. The meaning of `like_weight` and `reply_weight` lives only in the config section of [README.md](README.md). Do not ask about them before the first picture. Do not repeat the numbers on the picture, in report headings, or in the summary you send.

## First run

The only step is to make sure **one** X account is connected. If the X tools are missing, ask them to tap **Connect** on the X card in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in. Stop until that one account is connected.

Then do the rest with the defaults. Do not ask setup questions.

1. `get_users_me` with `user.fields=id,name,username,description,profile_image_url`. That is the account. Write `handle` and `user_id` into `config.json` copied from `config.example.json`. Leave every other key as in the example.
2. Clone or `git pull --ff-only` this repo, install Pillow, and fetch only the last `first_run_days` from config (default **2 days**, 48 hours). Use the tool calls below with that `START`. Do not fetch a full week on the first run. Never commit `config.json` or `data/`.
3. Run `python3 x_neighbours.py --now <T> --first-run`. Send the chat markdown (`report_first.md`). Also send the house-framed picture and the thank-you link, framed as: here's a picture you can post to thank your neighbours. Do not post it yourself.
4. Create both routines with no question: every day at 9:00 AM (last 24 hours, text only), and Mondays at 9:00 AM (last 7 days, reusing daily files, picture only on the random weeks). Use their timezone, or UTC if you don't know it.
5. Close with one line: daily and Monday reports are set; anything can be changed by asking (time, period, top N, likes only, replies only, per post, per day, picture).

Do not send a settings list.

## Each run

A manual run can fetch one window in a single pass. The daily and Monday routines below split the work so Monday reuses that morning's files. Work in the clone. Pick a UTC timestamp `T` when you start fetching, such as `2026-11-04T18:00:00Z`. You will pass `T` as `--now`.

One fetch covers every window in config. When `week` is on, `START` is `T` minus 7 days. When the config is day-only, `START` is `T` minus 24 hours. The script cuts the 24-hour window out of the same files, so do not fetch twice.

Save each result from the repo directory:

```bash
python3 save_raw.py <tool-result-file> <name>
```

That writes `data/<name>.json`. Raw JSON and text wrapped around one JSON object both work. If you already have the JSON object, you may write `data/<name>.json` yourself.

Call the tools by these names on the owner's X connection. Page with `pagination_token` set to the previous response's `meta.next_token`. Stop when there is no next token. A page can be shorter than `max_results`.

`{ID}` is the owner's user id from config.

### 1. Posts

`get_users_posts`

- `id`: `{ID}`
- `start_time`: `START`
- `exclude`: `retweets`
- `max_results`: `100`
- `post.fields`: `created_at,public_metrics,in_reply_to_user_id,referenced_tweets`
- `expansions`: `author_id`
- `user.fields`: `username,name,profile_image_url,public_metrics`

Save as `posts_1`, `posts_2`, and so on. On a scheduled run, use `posts_day_*` or `posts_week_*` as the Routines section says. The script loads every `posts_*.json`.

Also request `conversation_id` in `post.fields` so a later reply from the owner can be matched to the item.

### 2. Mentions

`get_users_mentions`

- `id`: `{ID}`
- `start_time`: `START`
- `max_results`: `100`
- `post.fields`: `created_at,author_id,in_reply_to_user_id,referenced_tweets,conversation_id`
- `expansions`: `author_id`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Save as `mentions_1`, `mentions_2`, and so on.

A reply is a mention with `in_reply_to_user_id` equal to `{ID}`, or a `replied_to` reference whose id is one of the owner's posts. Ignore the owner's own posts.

### 3. Likers

For each of the owner's posts in the fetched window:

- Last 24 hours and `like_count` greater than 0: fetch likers.
- Days 2–7 and `like_count` at least 3: fetch likers.
- Otherwise skip the post. Most skips are short replies with one or two likes.

`get_posts_liking_users`

- `id`: the post id
- `max_results`: `100`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Save as `likes_<postid>`. If `meta.next_token` is present and the day's budget allows, save the next page as `likes_<postid>_p2`, and so on. One page covers almost every post.

Skip a post you already saved likers for earlier the same day.

### 4. Reposts and quote posts

Same budget rule as likes, using `repost_count` and `quote_count` from the post's `public_metrics`. Last 24 hours: every post with that count above 0. Days 2–7: only counts of 3 or more. Skip a file you already saved.

`get_posts_reposted_by` — `id` the post id, `max_results` 100, `user.fields=username,name,description,public_metrics,profile_image_url`. Save as `reposts_<postid>`.

`get_posts_quoted_posts` — `id` the post id, `max_results` 100, `post.fields=created_at,author_id,text,referenced_tweets,conversation_id`, `expansions=author_id`, `user.fields=username,name,description,profile_image_url`. Save as `quotes_<postid>`.

### 5. Latest post for the catch-up list

After the files above are saved, pick at most 10 people with the highest quiet score in config (replies and quotes use `reply_weight`, likes use `like_weight`; do not tell the owner the numbers). For each, one call:

`get_users_posts` — `id` their user id, `max_results` 10, `exclude=replies,retweets`, `post.fields=created_at,text,author_id,in_reply_to_user_id,referenced_tweets`, `expansions=author_id`, `user.fields=username,name,profile_image_url`.

Save the whole page as `latest_<userid>`. Catch up uses the newest original post in that page. A quote of their own counts. A reply (`in_reply_to_user_id` or `referenced_tweets` type `replied_to`) and a plain repost (`retweeted`, or text starting `RT @`) do not. If the page has no original post, the script skips that person and fills the ten from the next person. Skip a file saved earlier today. Never more than 10 of these calls.

### 6. Followers and following

Do this only when `data/followers_1.json` or `data/following_1.json` is missing or older than 7 days, and on the weekly run below.

`get_users_me_followers` and `get_users_me_following`

- `max_results`: `1000`
- `user.fields`: `username,name,description,public_metrics,profile_image_url`

Page to the end. Save as `followers_1`, `followers_2`, … and `following_1`, `following_2`, …

Overwrite those names as you go. Do not delete the previous files until the new list has reached its last page. If the refresh fails halfway, keep what was already there and tell the owner the relationship tags are from the earlier list.

## Run the script

```bash
python3 x_neighbours.py --now <T>
```

It reads `config.json` and `data/`. For each window it writes `report_<window>.md`, the chat report, with `[@handle](https://x.com/handle)` links. The report card PNG is off unless you pass `--report-card`. It draws the ring picture on `--first-run`, on about one Monday in three, or when you pass `--picture`. Stdout is JSON with totals and `catch_up`. When the picture is included, stdout also has `picture` and `thank_you` (`text` under 280 characters, and `intent` as `https://x.com/intent/post?text=...`). `--first-run` uses `first_run_days` (default 2) and always draws the picture.

A custom period is `--days 14` (writes `report_custom`). Likes only, replies only, per post, and per day are `--report likes`, `--report replies`, `--per-post`, and `--per-day`. They re-read `data/` and do not need more X calls. Weight flags exist. Keep those values in config only, and never print them.

## What you send the owner

Send the chat markdown. That is the report. On a run that wrote the picture, also send the PNG and the thank-you link, as something they can post. Do not post it yourself. Do not send a report card unless they asked.

The markdown is the summary: header totals, replies and quote posts with Replied / Not replied yet, the likes and reposts table (user, likes, and reposts), and Catch up with a Read post link. 👤? means the owner does not follow that person. Do not add a followed/unfollowed split, a follow-back list, or impressions.

Use the names from this run. Do not post, like, or DM anyone.

## Routines

Create both during the first run. Do not ask first. Tell the owner afterwards that they can change the time or turn either one off by asking.

Both run at 9:00 AM in the owner's timezone. Count every X call from both toward the same cap: about 30 a minute and 1,000 a day. On Monday, run the daily job first, then the weekly job, and do not fetch the last 24 hours twice.

### Every day

1. `git pull --ff-only`. Leave `config.json` and `data/` uncommitted.
2. Do not refresh followers or following.
3. Pick `T`. `START` is `T` minus 24 hours.
4. Fetch posts and mentions from `START`. Save them as `posts_day_1`, `posts_day_2`, … and `mentions_day_1`, ….
5. Fetch likers, reposters, and quote posts for that day with the budget rule above. Skip files you already have.
6. Fetch at most 10 latest posts (`latest_<userid>.json`).
7. Run `python3 x_neighbours.py --now <T> --windows day --no-picture`.
8. Send `report_day.md`. The report is the markdown. Do not send a report card, and do not include the ring picture.

Leave the files in place. Later reports filter them by time.

### Monday, after that day's daily run

If today's `posts_day_1.json` is missing, do the daily run first.

1. Refresh followers and following. This is the only day that does.
2. Reuse today's posts, mentions, likes, reposts, quotes, and latest-post files. Do not request the last 24 hours again.
3. If saved posts already cover `T` minus 7 days through `T` minus 24 hours, do not page posts or mentions for that span. Fetch only missing liker, reposter, and quote files for older posts whose count is 3 or more.
4. If that span is missing, fetch it once: `get_users_posts` and `get_users_mentions` with `start_time` of `T` minus 7 days and `end_time` of `T` minus 24 hours. Save as `posts_week_1`, … and `mentions_week_1`, …. Then the same 3-or-more rule for likes, reposts, and quotes. Refresh `latest_<userid>.json` only for the catch-up ten, and only if today's file is missing.
5. Run `python3 x_neighbours.py --now <T> --windows week`. About one week in three (`picture_every_n_weeks` in config) it also writes the house-framed picture and a thank-you intent link. Pass `--picture` when the owner asks, any day.
6. Send `report_week.md`. When the picture was written, send that PNG and the thank-you link too, as something they can post. Do not post it. Do not send a report card unless they asked for `--report-card`.

If the Monday calls would pass about 1,000 for the day, send the day picture you already have, fetch the older posts and mentions, and stop the liker lists when the cap is close. Tell the owner which older posts were left out.
