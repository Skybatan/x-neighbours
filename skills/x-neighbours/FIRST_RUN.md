# Welcome tour

The welcome tour is a short guided demo of how X Neighbours works. You run it yourself in this chat. Do not hand it to a subagent. Do not read the full [SKILL.md](SKILL.md) to produce it. Later reports use that file, after the owner picks a routine.

This run is read-only. Do not follow, like, post, reply, or DM. Do not commit `config.json` or `data/`.

`trial_post_count` in config is how many original posts and quotes to use. Default **5**. There is no day window. Replies are not in that set. The flag stays `--first-run`. The files stay `report_first.*`.

The hard budget is about **15** X reads. Stay under 30 a minute. Send independent reads in parallel batches of up to 12. Prefer `max_results` 100. Do not omit it. Recent search still returns **25** posts a page when `max_results` is 100, so the reply search is often more than one read.

The tour uses real posts. It is not a sample. It shows the same report Page a later report uses, with one plain line under each part the first time it appears.

## Time

The posts page is one read. After it is saved, run `--trial-plan` and send `estimate_message` before the reply search and the other reads. That message is the first thing they see. It already greets them by name, says what X Neighbours helps with, and says you are putting the tour together, how many minutes it should take, and that you will let them know when it is ready. Send that text as it is. Do not add another greeting in front of it.

Do not tell them the tour is one minute unless that message says so. Reply pages are one after another, about a minute each. The plan counts them from the five posts' `reply_count` totals, 25 replies a page. Three reply pages is about three minutes. `--estimate-reads 15` hides those pages. Do not use it as the tour's time.

## Steps

1. One X account must be connected. If the tools are missing, ask them to tap **Connect**. Do not ask for a password, an API key, or a token. Do not open x.com to log them in.
2. `get_users_me` with `user.fields=id,name,username,description,profile_image_url`. Copy `config.example.json` to `config.json`. Set `handle` and `user_id`. Set `name` to the display `name` from that call. When `name` is missing or blank, leave it blank: the greeting uses `@handle`. Set `timezone` to an IANA name when you know it. Leave `trial_post_count` at 5 unless they ask for another number.
3. `get_users_posts` once. `id` is the owner. `max_results` 100. `exclude` replies and retweets. No `start_time`. `post.fields=created_at,public_metrics,conversation_id,referenced_tweets,in_reply_to_user_id`. `expansions=author_id,referenced_posts`. `user.fields=username,name,profile_image_url`. Save with `python3 save_raw.py <file> posts_1`. One page. Fetch `posts_2` only when you still have fewer than `trial_post_count` originals or quotes, `meta.next_token` is set, and the 15-read budget still has room.
4. Plan the rest from the saved posts, then send `estimate_message`:

```bash
python3 x_neighbours.py --trial-plan --data data --user-id <id>
```

`posts` are the originals and quotes, newest first, at most `trial_post_count`. A quote counts even when `conversation_id` is the quoted post. A reply does not. `reply_count` is the total of those posts' reply metrics. `reply_pages` is how many search pages fit in the budget (`reply_pages_needed` is the full count, 25 replies a page). Do the reads in `reads` that you have not already done. Skip `skipped`. Do not pass `budget`.

`estimate_message` is the whole first chat message. It greets them once. Do not write your own hello, and do not send it again when the Page is ready.

5. Replies to those posts: `search_posts_all` (recent search) using the plan's `query` (`conversation_id:` joined with `OR`), `max_results` 100, `post.fields=created_at,author_id,text,in_reply_to_user_id,referenced_tweets,conversation_id`, `expansions=author_id,referenced_posts`. Save each page as `mentions_1`, `mentions_2`, and so on. Recent search returns 25 posts a page even when `max_results` is 100. Keep paging while `next_token` is set, the first-level replies you have saved are still fewer than the posts' `reply_count` total, and the read budget still has room. Stop when that first-level count matches the posts' reply metrics or the budget ends. Do not stop after one extra page. If search is missing, page `get_users_mentions` the same way and stop at the same line. Do not page through the whole account past the budget.

A reply counts only when its direct `replied_to` parent is one of the posts in this welcome tour. `conversation_id` is the thread root and is not enough. `in_reply_to_user_id` equal to the owner is not enough. Owner posts P, A replies (A1), the owner replies, A replies again (A2): only A1 counts. A2 is not an unanswered reply.

6. Likers, reposters, and quote posts: only the ids the plan lists, and only when that count is greater than 0. Never fetch likers for a reply. `max_results` 100. `user.fields=username,name,description,public_metrics,profile_image_url`. Save `likes_<id>`, `reposts_<id>`, and `quotes_<id>`. A missing liker file is normal. The report still runs.

7. Do not fetch followers or following. Do not fetch latest-post pages or the owner's likes. With no following file the report leaves off the 👤? marks and that legend. Those lists load on the first daily, weekly, or on-request report.

8. Render. `<T>` is the UTC time you started (`date -u +%Y-%m-%dT%H:%M:%SZ`). The store paths are `good_neighbours.json` and `state.json` in this bot's store.

```bash
python3 x_neighbours.py --now <T> --first-run --good-neighbours <store>/good_neighbours.json --state <store>/state.json
```

9. Send the report as a Page. `page_canvas` is `report_first.canvas.tsx` and `page_title` is `Welcome tour`. Pass the whole file to WriteCanvas. Do not pass a canvas id. Do not write the Page by hand.

The Page opens with `intro`, three short lines. The first line greets them: `Hi <name>! 👋`. `<name>` is the display name from `get_users_me`, or `@handle` when that name is blank. The second line says X Neighbours helps them keep up with and grow the connections around their posts (the people who reply, like, quote and repost). The third line is `Here's a quick welcome tour of your N latest posts.` The name is part of `intro` and is escaped with the rest of the Page data. Do not write the greeting by hand, and do not add a second introduction.

Each section has a one-line explainer the first time it appears (what Flowers are, what What's new is, what Replies waiting means, what the thank-you picture is for). The page ends with What's next: daily, weekly, or only when they ask. The choice itself stays a chat question after the Page link. One line says good neighbours, a picture on its own, and the community list come after this tour.

The house-framed picture is inside the Page. When a picture was drawn, the canvas already points at `picture_asset` (`asset:` plus the file name) and `picture_alt`.

1. Pass the whole canvas file to WriteCanvas. The title is `page_title`. Do not pass a canvas id.
2. WriteCanvas returns a url and a canvas id. If it fails or returns no url, use the fallback below. Do not invent a link.
3. If it succeeded and `picture` is set, call WriteCanvasAsset with that canvas id, the file name (the part of `picture_asset` after `asset:`), and the path `picture`.
4. The upload returns width and height. Ratio is `width/height`. Run:

```bash
python3 report_page.py --model <page_model> --picture-ratio "<width>/<height>"
```

`<page_model>` is `report_first_page.json`. WriteCanvas again with the same canvas id and the updated file. The Image uses `asset:<file name>`, the alt, and that ratio. A tag before the upload shows its alt until the picture is uploaded.

The delivery chat message is `headline`, then the Page link labelled `Welcome tour`. On this tour `headline` is the short line `Here's a quick welcome tour of your N latest posts.` It does not greet them again. The greeting was `estimate_message`, and it is the opening of the Page. Do not put `x_neighbours_first.png` in that message. Do not paste `report_first.md`, `intro`, or the thank-you sentence into the chat. Those words are on the Page. Do not post the picture.

If WriteCanvas fails or returns no url, send two messages and no Page link. Message 1 is the text of `report_first.md` and no image. Message 2 is `thank_you.text`, a blank line, the link `thank_you.intent` labelled “Post your thank-you”, a blank line, and `thank_you.note`, with the PNG in `images`. That picture-on-chat path is only the fallback.

Do not send a good-neighbours card. Do not send the Good neighbours Page. `add_question` is absent on the welcome tour. Do not ask them to build the list. Do not run `community.py offer`. Do not send a community or share card. `community_offer` and `share_offer` are false. The tour is the five-post report, the greeting, the one-line explainers, and What's next.

10. Then ask what comes next, with `next_steps` from the script. One question. The options are Daily report, Weekly report, and Only when I ask.

- **Daily report.** Every day at 9:00 in their timezone, or UTC if you don't know it. Last 24 hours. Read the “Every day” steps in [SKILL.md](SKILL.md) and create that routine. Do not also create the Monday report routine. Do create the Monday update check.
- **Weekly report.** Mondays at 9:00. Last 7 days. Read the Monday report steps in [SKILL.md](SKILL.md) and create that routine. Also create the Monday update check.
- **Only when I ask.** Create no report routine. Do create the Monday update check.

Do not create both report routines. Every choice still gets the Monday update check. Followers and following load on the first regular report, if those files are still missing. That same report is the first time you may send the ⭐ Add card, when `add_question` is present, and the first time you may send the Good neighbours Page, when the list is not empty. Offer community mode once with or after that first regular report, using the community skill. Not before.
