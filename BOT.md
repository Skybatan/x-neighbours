# X Neighbours — bot runbook

You run this for the owner of this bot. It shows who replied, quoted, liked, and reposted, then who to catch up with. Every report ends with a house-framed neighbours picture and a thank-you link.

You do the X reads. `x_neighbours.py` only reads JSON you saved. Follow every rule in this file on every run.

## Rules

- Stay within about **1,000 X reads a day** and **30 a minute**. Send about 12 calls, then pause. Count as you go. If the next batch would pass 1,000, stop, render what you have, and tell the owner which posts you skipped.
- Refresh follower and following lists **at most once a week**. Reuse `data/followers_*.json` and `data/following_*.json` when they are under 7 days old.
- This run is **read-only**. Never follow, unfollow, like, unlike, repost, bookmark, post, reply, or DM. Never open a GitHub issue yourself. If they ask you to follow someone or to post the picture, say this run stays read-only and they can do that in the X app.
- Leave bot accounts out. `@grok` is already in `exclude`. They can name other handles to skip anytime.
- Never commit user data. Do not commit or push `config.json`, `data/`, `.avatar_cache/`, `report_*.md`, `report_*.png`, `x_neighbours_*.png`, `good_neighbours.json`, or `state.json`. Do not open a pull request with those files. Do not run `git add .`. For a normal run, commit nothing. `git pull` is fine: those paths are gitignored. The good neighbours list and the report clock live in this bot's own store, outside the repo.
- Stay on this task. Do not read their DMs, bookmarks, home timeline, or other people's accounts to fill out the picture.
- If the X tools are missing, ask the owner to connect X in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in.

Weights are a quiet setting. The meaning of `like_weight` and `reply_weight` lives only in the config section of [README.md](README.md). Do not ask about them before the first picture. Do not repeat the numbers on the picture, in report headings, or in the summary you send.

## First run

The only step is to make sure **one** X account is connected. If the X tools are missing, ask them to tap **Connect** on the X card in this chat. Do not ask for a password, API key, or bearer token, and do not open x.com to log them in. Stop until that one account is connected.

Then do the rest with the defaults. Do not ask setup questions.

1. `get_users_me` with `user.fields=id,name,username,description,profile_image_url`. That is the account. Write `handle` and `user_id` into `config.json` copied from `config.example.json`. If you know their timezone, set `timezone` to an IANA name such as `Europe/Stockholm`. Leave `fresh_hours` unset unless they ask for a fixed interval. Leave every other key as in the example.
2. Clone or `git pull --ff-only` this repo, install Pillow, and fetch only the last `first_run_days` from config (default **2 days**, 48 hours). Use the tool calls below with that `START`. Do not fetch a full week on the first run. Never commit `config.json` or `data/`.
3. Run `python3 x_neighbours.py --now <T> --first-run --good-neighbours <path> --state <state path>`. Send the report as two messages, exactly as in “How to send a report”. Do not post the thank-you yourself. If stdout has `add_question`, send that one card after those two messages. Do not ask again in prose.
4. Create both routines with no question: every day at 9:00 AM (last 24 hours, picture included), and Mondays at 9:00 AM (last 7 days, reusing daily files, picture included). Use their timezone, or UTC if you don't know it.
5. Close with one line: daily and Monday reports are set; anything can be changed by asking (time, period, top N, likes only, replies only, per post, per day); say 'add @someone to my good neighbours' to keep up with them here.

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

Read the good neighbours file first (see Good neighbours). If it lists people, fetch a latest page for each of them, at most 20, and do not also fetch the ranked ten. If the file is missing or the list is empty, pick at most 10 people with the highest quiet score in config (replies and quotes use `reply_weight`, likes use `like_weight`; do not tell the owner the numbers). For each person, one call:

`get_users_posts` — `id` their user id, `max_results` 10, `exclude=replies,retweets`, `post.fields=created_at,text,author_id,in_reply_to_user_id,referenced_tweets`, `expansions=author_id`, `user.fields=username,name,profile_image_url`.

Save the whole page as `latest_<userid>`. Catch up uses the newest original post in that page. A quote of their own counts. A reply (`in_reply_to_user_id` or `referenced_tweets` type `replied_to`) and a plain repost (`retweeted`, or text starting `RT @`) do not. If the page has no original post, the script skips that person. With an empty list it fills the ten from the next person. With a list it does not fill from anyone else. Skip a file saved earlier today.

### 6. Followers and following

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

`<path>` is `good_neighbours.json` in the store. `<state path>` is `state.json` beside it. The script reads `config.json` and `data/`. For each window it writes `report_<window>.md` (sections 1–3) and `report_<window>_thanks.md` (section 4), plus `x_neighbours_<window>.png`, the house-framed picture. The report card PNG is off unless you pass `--report-card`. Stdout is JSON with totals, `catch_up`, `picture`, `thank_you`, and `messages`. `thank_you.text` is the thank-you sentence. It names no one. `thank_you.intent` is the post link. A day window, a first run, and a fresh on-demand report include `suggest_good_neighbours` and `add_question` when someone in Flowers is not on the list yet. A week window does not. `--first-run` uses `first_run_days` (default 2). A missing good neighbours file is an empty list. `--no-picture` skips the image; the default is to draw it every time. `--since <ISO>` is a report that starts at that time.

A custom period is `--days 14` (writes `report_custom`). Likes only, replies only, per post, and per day are `--report likes`, `--report replies`, `--per-post`, and `--per-day`. They re-read `data/` and do not need more X calls. Weight flags exist. Keep those values in config only, and never print them.

## How to send a report

Send exactly two chat messages, in this order. Then, only if `add_question` is present, one question card. Do not post, like, or DM anyone. Do not send a report card unless they asked.

**Message 1 — sections 1 to 3.** Send the text of `report_<window>.md` and nothing else. The `images` field of this message is empty. Do not attach the picture here.

The sections, in order, are:

1. **💐 Flowers from your neighbours** — User, Replies, Likes, Reposts. Replies means replies plus quote posts. Top 10, biggest supporters first. No Total column.
2. **Catch up with your good neighbours**
3. **👋 Greetings from your neighbours**

⭐ next to a name means they are on the good neighbours list. The legend “⭐ = good neighbour” appears only when that list is non-empty. 👤? means the owner does not follow that person. Do not add a followed/unfollowed split, a follow-back list, or impressions.

**Message 2 — section 4, one message, picture included.** This is a single chat message. Put the house-framed PNG in that message's `images` field. The path is `messages[1].images[0]`, the same file as `picture`. The text of the same message is `thank_you.text`, then a blank line, then the link `thank_you.intent` with the label “Post your thank-you”.

The picture belongs inside this message. Do not send the picture as its own message. Do not send the picture as a later attachment. Do not send the text first and the picture second. If the owner cannot see the picture in the same bubble as the thank-you sentence, the send was wrong.

Do not post the thank-you yourself.

**Then the ⭐ Add card, or nothing.** If `add_question` is absent, stop. If it is present, send one multi-select question card after message 2. The short label is **⭐ Add**. The prompt is “Add to good neighbours?”. The options are the `label` values (`⭐ @handle`), in Flowers order, at most five, and only people who are not on the list. There is one free-text option (“Or name anyone else”). Do not also paste that list into message 1 or message 2. Do not look anyone else up on X to invent suggestions. Do not send the card on the Monday report. When they pick someone, add them with `good_neighbours.py`. Use the id and name already in `suggest_good_neighbours`. Call `get_users_by_username` only for a handle that is not in that list.

## Routines

Create both during the first run. Do not ask first. Tell the owner afterwards that they can change the time or turn either one off by asking.

Both run at 9:00 AM in the owner's timezone. Count every X call from both toward the same cap: about 30 a minute and 1,000 a day. On Monday, run the daily job first, then the weekly job, and do not fetch the last 24 hours twice.

### Every day

1. `git pull --ff-only`. Leave `config.json` and `data/` uncommitted.
2. Do not refresh followers or following.
3. Pick `T`. `START` is `T` minus 24 hours.
4. Fetch posts and mentions from `START`. Save them as `posts_day_1`, `posts_day_2`, … and `mentions_day_1`, ….
5. Fetch likers, reposters, and quote posts for that day with the budget rule above. Skip files you already have.
6. Fetch latest posts (`latest_<userid>.json`) for each good neighbour, or for the ranked ten when the list is empty.
7. Run `python3 x_neighbours.py --now <T> --windows day --good-neighbours <path> --state <state path>`.
8. Send the report with “How to send a report”: message 1 is `report_day.md` with no image, message 2 is the thank-you text and link with `x_neighbours_day.png` in that message's `images` field. Then the ⭐ Add card if `add_question` is present. If they pick someone, add them with `good_neighbours.py`.

Leave the files in place. Later reports filter them by time.

### Monday, after that day's daily run

If today's `posts_day_1.json` is missing, do the daily run first.

1. Refresh followers and following. This is the only day that does.
2. Reuse today's posts, mentions, likes, reposts, quotes, and latest-post files. Do not request the last 24 hours again.
3. If saved posts already cover `T` minus 7 days through `T` minus 24 hours, do not page posts or mentions for that span. Fetch only missing liker, reposter, and quote files for older posts whose count is 3 or more.
4. If that span is missing, fetch it once: `get_users_posts` and `get_users_mentions` with `start_time` of `T` minus 7 days and `end_time` of `T` minus 24 hours. Save as `posts_week_1`, … and `mentions_week_1`, …. Then the same 3-or-more rule for likes, reposts, and quotes. Refresh `latest_<userid>.json` for each good neighbour, or for the catch-up ten when the list is empty, and only if today's file is missing.
5. Run `python3 x_neighbours.py --now <T> --windows week --good-neighbours <path> --state <state path>`. Do not send the ⭐ Add card on this report.
6. Send the report with “How to send a report”: message 1 is `report_week.md` with no image, message 2 is the thank-you text and link with `x_neighbours_week.png` in that message's `images` field. Do not post it. Do not send a report card unless they asked for `--report-card`. After those two messages, add one line and nothing else: “Anything you'd change about X Neighbours? Tell me and I'll turn it into a feedback link.” That line is `feedback_line` in the script output. Do not fetch anything for it.

If the Monday calls would pass about 1,000 for the day, send the day picture you already have, fetch the older posts and mentions, and stop the liker lists when the cap is close. Tell the owner which older posts were left out.

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

To remove someone, run `remove`. To show the list, run `list` and send the names and @handles. That needs no X call.

Adding someone does not follow them. This run stays read-only on X.

When the list is non-empty, Catch up with your good neighbours shows only those people, each one's latest original post, and skips anyone with no recent original post. They are not inserted into the other sections just because they are on the list. When the list is empty, Catch up stays the top 10 from the period and the report adds: “Add people to your good neighbours list to keep up with them here.”

After a daily report, a first run, and a fresh on-demand report, the script lists up to five people from Flowers who are not on the list yet, in that table's order. They are in `suggest_good_neighbours`. If nobody is left, `add_question` is absent and you skip the card. Send one multi-select card, short label **⭐ Add**, option labels `⭐ @handle`, plus a free-text option. A weekly report does not ask. The first-run closing line mentions the list once, besides that card.

## When they just say hello

If the owner opens the chat or sends a greeting with no specific request (no report, no picture, no list change, no settings), check freshness and do nothing else until they answer.

```bash
python3 report_state.py --file <state path> check
```

If `config.json` has `fresh_hours`, add `--hours` after `check`. Otherwise leave it off and the script estimates from the last report.

If `ask` is false, reply with one line that the last report is still fresh (`age_label`) and stop. Do not fetch.

If `ask` is true, send one yes/no question card with `question` and stop. Do not fetch, and do not send a report, until they answer. The usual question is “Your last report was 2 hours ago. Want a fresh one?”

If they say no, stop. If they say yes, run a fresh report. `START` is `fetch_since` from that check (the end of the last report, or 24 hours ago when there is no report, and never more than 7 days). Pass it as `--since`. Use the same read budget as a daily run when the gap is under 24 hours, and the days-2-to-7 budget when it is longer. Then send the report with “How to send a report” and pass `--state` so the clock updates.

```bash
python3 x_neighbours.py --now <T> --since <fetch_since> --good-neighbours <path> --state <state path>
```

The estimate, unless `fresh_hours` is set: 60 or more replies, quote posts, likes, and reposts per 24 hours is a big account (ask after 1 hour); 15 to 59 is medium (ask after 3 hours); under 15 is small (ask after 8 hours).

## Feedback

Offer this for any concern the owner mentions: a complaint, a wish, a nit, or a “what if”. Stay light. One offer per topic in this conversation, never a follow-up push. The Monday report already asks once, in a single line; if they answer that line, treat it as the concern and offer the link the same way.

1. Answer the point in a sentence or two.
2. Ask once, as a yes/no card: “Want to report this so it gets fixed?”
3. If they say no, drop it. Do not ask again about that same point in this conversation.
4. If they say yes, draft a short issue and show it before any link. Title is one line. Body has what they expected, what happened, the report type (daily, weekly, first, fresh, or other), and the version from `git rev-parse --short HEAD`.
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
- Version: abc1234
EOF
)"
```

The script prints JSON. `url` is `https://github.com/Skybatan/x-neighbours/issues/new?title=...&body=...&labels=feedback`, URL-encoded, and kept under 7500 characters. Send that URL. The owner taps it and submits the issue themselves. You never call the GitHub API, never run `gh issue create`, and never submit the form.

If the script says the draft contains a handle or a secret, rewrite the draft without that and run it again. If `shortened` is true, tell them the draft was shortened to fit the link.
