---
name: x-neighbours
description: >-
  Rank who liked and replied to the owner on X over the last day and week,
  tag each person, suggest follow-backs, and draw an X Neighbours picture.
  Use when the owner asks for neighbours, top likers, top repliers, or their
  weekly X audience picture.
---

# X Neighbours — bot runbook

You run this for the owner of this bot. It ranks who liked and replied to them on X over the last day and the last week, tags each person, suggests follow-backs, and draws a picture: their avatar in the centre, their closest neighbours in rings.

You do the X reads. `x_neighbours.py` only reads JSON you saved. Follow every rule in this file on every run. The same text is in `BOT.md` at the root of the repo.

## Rules

- Stay within about **1,000 X reads a day** and **30 a minute**. Send about 12 calls, then pause. Count as you go. If the next batch would pass 1,000, stop, render what you have, and tell the owner which posts you skipped.
- Refresh follower and following lists **at most once a week**. Reuse `data/followers_*.json` and `data/following_*.json` when they are under 7 days old.
- This run is **read-only**. Never follow, unfollow, like, unlike, repost, bookmark, post, reply, or DM. Follow-back suggestions are text for the owner. If they ask you to follow those people or to post the picture, say this run stays read-only and they can do that in the X app.
- Leave bot accounts out. `@grok` is already in `exclude`. Ask once if they want other handles on that list.
- Never commit user data. Do not commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, or `x_neighbours_*.png`. Do not open a pull request with those files. Do not run `git add .`. For a normal run, commit nothing. `git pull` is fine: those paths are gitignored.
- Stay on this task. Do not read their DMs, bookmarks, home timeline, or other people's accounts to fill out the picture.
- If the X tools are missing, ask the owner to connect X in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in.

Weights are a quiet setting. The meaning of `like_weight` and `reply_weight` lives only in the config section of [README.md](../../README.md). Ask for them at setup, write the answer into `config.json`, and do not repeat the numbers on the picture, in report headings, or in the summary you send.

## First run

Ask these in one message. Accept a default whenever they skip a question.

1. **Handle.** Call `get_users_me` with `user.fields=id,name,username,description,public_metrics,profile_image_url`. Show them that handle and id. This run is for the connected account, because followers and following come from that login. If it is the wrong account, they reconnect X. Do not point the script at a different user id.
2. **Weights.** Ask if they want to keep the weights in `config.example.json`. If they name different numbers, write those into `config.json` and nowhere else.
3. **Theme.** `midnight` (default), `light`, or `sunset`.
4. **Rings.** 1 to 4, default 3. The rings hold 8 people, then 14, then 20, then 26.
5. **Windows.** `day`, `week`, or both. Default is both.

`@grok` is excluded unless they ask for that handle to be removed. They can name other handles to exclude.

Then:

```bash
git clone https://github.com/Skybatan/x-neighbours.git
cd x-neighbours
python3 -m pip install -r requirements.txt
cp config.example.json config.json
```

If the repo is already there, `git status` first. Unstage anything under `data/` or named `config.json` if it was staged. Then `git pull --ff-only`. Do not commit local files to make the pull succeed.

Write their answers into `config.json`. Store `user_id` as a string. Check the install with the fictional sample (do not send this picture to the owner as if it were theirs):

```bash
python3 x_neighbours.py --help
python3 x_neighbours.py \
  --config config.example.json \
  --handle samplecreator \
  --user-id 900001 \
  --data examples/sample \
  --out /tmp/x-neighbours-sample \
  --now 2026-11-04T18:00:00Z
```

You should get a PNG. The inner ring of the week picture starts with `@nova_lane`. Those accounts are made up.

## Each run

Work in the clone. Pick a UTC timestamp `T` when you start fetching, such as `2026-11-04T18:00:00Z`. You will pass `T` as `--now`.

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

Save as `posts_1`, `posts_2`, and so on.

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

### 4. Followers and following

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

It reads `config.json` and `data/`. It writes `report_day.md`, `report_week.md`, `x_neighbours_day.png`, and `x_neighbours_week.png` for the windows in config. Stdout is JSON:

```json
{
  "week": {
    "likes": [["@handle", 8]],
    "replies": [["@handle", 4]],
    "follow_back": ["@handle"],
    "inner": [["@handle", 17]]
  }
}
```

`likes` and `replies` are raw counts. `follow_back` is people they do not follow. `inner` is the picture order. Do not quote `inner`'s point totals to the owner. Relationship tags (`mutual`, `follows-you`, `you-follow`, `neither`) are in the report tables and the follow-back lines.

Flags, when you need them: `--handle`, `--user-id`, `--data`, `--out`, `--rings`, `--top`, `--theme`, `--windows day,week`, `--show-names`, `--hide-names`, `--exclude`, `--no-image`, `--config`. Weight flags exist. Keep those values in config only.

## What you send the owner

Send the PNG for each window they asked for, week picture first. Then a short note in your own words:

- who liked them most, with the like counts
- who replied most, with the reply counts
- up to five follow-back suggestions, each with its relationship tag
- one line if Notes says liker lists were missing or short

A note shaped like the fictional sample reads: "@pixel_otter liked you the most this week (8) and @nova_lane replied the most (4). Often here, and you don't follow them yet: @pixel_otter (follows you), @moss_radio (neither), @cedar_loop (neither), @drift_paper (follows you), @paper_kite (follows you)."

Use the real names from this run. Do not include the weight settings. Do not post the picture, like anything, or DM anyone. Offer to change theme, rings, or windows next time.

## Weekly schedule

Suggest one run a week, Monday morning in the owner's timezone. Offer to remember that time. The run is:

1. `git pull --ff-only` in the clone. Leave `config.json` and `data/` uncommitted.
2. Refresh followers and following. This is the weekly refresh.
3. Fetch posts, mentions, and likers for the last 7 days, using the liker rule above.
4. Run `python3 x_neighbours.py --now <T>`.
5. Send `x_neighbours_week.png` and the short summary. Include the day picture when `windows` contains `day`.

A daily picture is optional, and only if they ask. On the other days: posts and mentions for 24 hours, likers for that day's liked posts, reuse follower files, `--windows day`. Skip the daily run when it would push the day past about 1,000 reads.
