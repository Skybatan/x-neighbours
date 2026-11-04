# X Neighbours — bot runbook

You run this for the owner of this bot. It ranks who liked and replied to them on X over the last day and the last week, tags each person, suggests follow-backs, and draws a picture: their avatar in the centre, their closest neighbours in rings.

You do the X reads. `x_neighbours.py` only reads JSON you saved. Follow every rule in this file on every run.

## Rules

- Stay within about **1,000 X reads a day** and **30 a minute**. Send about 12 calls, then pause. Count as you go. If the next batch would pass 1,000, stop, render what you have, and tell the owner which posts you skipped.
- Refresh follower and following lists **at most once a week**. Reuse `data/followers_*.json` and `data/following_*.json` when they are under 7 days old.
- This run is **read-only**. Never follow, unfollow, like, unlike, repost, bookmark, post, reply, or DM. Follow-back suggestions are text for the owner. If they ask you to follow those people or to post the picture, say this run stays read-only and they can do that in the X app.
- Leave bot accounts out. `@grok` is already in `exclude`. After the first picture, they can name other handles to skip.
- Never commit user data. Do not commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, or `x_neighbours_*.png`. Do not open a pull request with those files. Do not run `git add .`. For a normal run, commit nothing. `git pull` is fine: those paths are gitignored.
- Stay on this task. Do not read their DMs, bookmarks, home timeline, or other people's accounts to fill out the picture.
- If the X tools are missing, ask the owner to connect X in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in.

Weights are a quiet setting. The meaning of `like_weight` and `reply_weight` lives only in the config section of [README.md](README.md). Do not ask about them before the first picture. Do not repeat the numbers on the picture, in report headings, or in the summary you send.

## First run

Ask **only** whether X is connected. If the X tools are missing, ask them to tap **Connect** on the X card in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in. Stop until X is connected.

Then generate the report immediately with the defaults. Do not ask about theme, rings, windows, weights, or who to exclude.

1. Call `get_users_me` with `user.fields=id,name,username,description,public_metrics,profile_image_url`. That handle and id are the account this run is for, because followers and following come from that login. Do not point the script at a different user id. Do not wait for them to confirm it.
2. Clone or update the repo, install Pillow, and copy the example config. Write only `handle` and `user_id`. Leave every other key as it is in `config.example.json`.

```bash
git clone https://github.com/Skybatan/x-neighbours.git
cd x-neighbours
python3 -m pip install -r requirements.txt
cp config.example.json config.json
```

If the repo is already there, `git status` first. Unstage anything under `data/` or named `config.json` if it was staged. Then `git pull --ff-only`. Do not commit local files to make the pull succeed.

Defaults you are keeping: rings 4, theme `midnight`, names on, window `week`, exclude `grok`, top 10, report `both`, per-post off, per-day off. Store `user_id` as a string.

3. Fetch the last 7 days (the tool calls below) and run:

```bash
python3 x_neighbours.py --now <T>
```

4. Send `x_neighbours_week.png` and the short summary. The picture goes out before any settings question.
5. After that, in **one** message, list every setting below with its current default. Say they can change any of them just by asking. In the same message, list the extra reports and offer a Monday-morning routine. Do not send these as separate questions, and do not block the picture on an answer.

Use this shape, in your own words, with these defaults:

- Theme: midnight. Also light or sunset.
- Rings: 4 (1 to 4; the rings hold 8, then 14, then 20, then 26).
- Names on the picture: on.
- Window: the last 7 days. The last 24 hours, or both, when they ask.
- Leave out: @grok. They can name other handles.
- Table length: 10.
- Scoring weights: a quiet setting, kept off the picture and out of the summary. They can ask to change it. Do not print the numbers.
- More reports, only when they ask: likes only, replies only, per post (who liked or replied to each post), per day, and the last 24 hours as well as the week.
- Offer a weekly routine, Monday morning in their time zone. If they say nothing, don't schedule it.

To check the install on the fictional sample, without sending that picture as if it were theirs:

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

You should get a four-ring PNG. The inner ring starts with `@nova_lane`. Those accounts are made up.

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

Flags, when the owner asks: `--handle`, `--user-id`, `--data`, `--out`, `--rings`, `--top`, `--theme`, `--windows day` or `--windows day,week`, `--report likes`, `--report replies`, `--per-post`, `--per-day`, `--show-names`, `--hide-names`, `--exclude`, `--no-image`, `--config`. A plain run stays on the defaults: both rankings, no per-post, no per-day, week window. These modes re-read `data/` and do not need more X calls. Weight flags exist. Keep those values in config only.

## What you send the owner

Send the PNG for each window they asked for, week picture first. Then a short note in your own words:

- who liked them most, with the like counts
- who replied most, with the reply counts
- up to five follow-back suggestions, each with its relationship tag
- one line if Notes says liker lists were missing or short

A note shaped like the fictional sample reads: "@pixel_otter liked you the most this week (8) and @nova_lane replied the most (4). Often here, and you don't follow them yet: @pixel_otter (follows you), @moss_radio (neither), @cedar_loop (neither), @drift_paper (follows you), @paper_kite (follows you)."

Use the real names from this run. Do not include the weight settings. Do not post the picture, like anything, or DM anyone.

On the first run, the settings message from the First run section follows this note. On later runs, send the picture and the summary. Repeat the full settings list only when they ask what they can change.

## Weekly schedule

After the first report, offer one run a week, Monday morning in the owner's timezone. Don't block the picture on that offer. If they want it, the run is:

1. `git pull --ff-only` in the clone. Leave `config.json` and `data/` uncommitted.
2. Refresh followers and following. This is the weekly refresh.
3. Fetch posts, mentions, and likers for the last 7 days, using the liker rule above.
4. Run `python3 x_neighbours.py --now <T>`.
5. Send `x_neighbours_week.png` and the short summary. Include the day picture when `windows` contains `day`.

A daily picture is optional, and only if they ask. On the other days: posts and mentions for 24 hours, likers for that day's liked posts, reuse follower files, `--windows day`. Skip the daily run when it would push the day past about 1,000 reads.
