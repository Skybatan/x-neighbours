# First report

The first X Neighbours report is a short demo. You run it yourself in this chat. Do not hand it to a subagent. Do not read the full [SKILL.md](SKILL.md) to produce it. Later reports use that file, after the owner picks a routine.

This run is read-only. Do not follow, like, post, reply, or DM. Do not commit `config.json` or `data/`.

`trial_post_count` in config is how many original posts and quotes to use. Default **5**. There is no day window. Replies are not in that set.

The hard budget is about **15** X reads. Stay under 30 a minute. Send independent reads in parallel batches of up to 12. Prefer `max_results` 100. Do not omit it.

## Before any X read

Count the reads you plan (use 15 until the plan says a smaller number) and run:

```bash
python3 x_neighbours.py --estimate-reads 15
```

Send the `message` field before you fetch. It says the report is about one minute, that they don't need to wait in the chat, and that you will notify them when it is ready. Deliver the report as a Page when it is done. The chat message is the short headline and the Page link.

## Steps

1. One X account must be connected. If the tools are missing, ask them to tap **Connect**. Do not ask for a password, an API key, or a token. Do not open x.com to log them in.
2. `get_users_me` with `user.fields=id,name,username,description,profile_image_url`. Copy `config.example.json` to `config.json`. Set `handle` and `user_id`. Set `timezone` to an IANA name when you know it. Leave `trial_post_count` at 5 unless they ask for another number.
3. `get_users_posts` once. `id` is the owner. `max_results` 100. `exclude` replies and retweets. No `start_time`. `post.fields=created_at,public_metrics,conversation_id,referenced_tweets,in_reply_to_user_id`. `expansions=author_id,referenced_posts`. `user.fields=username,name,profile_image_url`. Save with `python3 save_raw.py <file> posts_1`. One page. Fetch `posts_2` only when you still have fewer than `trial_post_count` originals or quotes, `meta.next_token` is set, and the 15-read budget still has room.
4. Plan the rest from the saved posts:

```bash
python3 x_neighbours.py --trial-plan --data data --user-id <id>
```

`posts` are the originals and quotes, newest first, at most `trial_post_count`. A quote counts even when `conversation_id` is the quoted post. A reply does not. Do the reads in `reads` that you have not already done. Skip `skipped`. Do not pass `budget`.

5. Replies to those posts: one `search_posts_all` (recent search) using the plan's `query` (`conversation_id:` joined with `OR`), `max_results` 100, `post.fields=created_at,author_id,text,in_reply_to_user_id,referenced_tweets,conversation_id`, `expansions=author_id,referenced_posts`. Save as `mentions_1`. A second page only when `next_token` is set and the budget allows. If search is missing, one `get_users_mentions` page with the same fields and stop. Do not page through the whole account.

A reply counts only when its direct `replied_to` parent is one of the posts in this first report. `conversation_id` is the thread root and is not enough. `in_reply_to_user_id` equal to the owner is not enough. Owner posts P, A replies (A1), the owner replies, A replies again (A2): only A1 counts. A2 is not an unanswered reply.

6. Likers, reposters, and quote posts: only the ids the plan lists, and only when that count is greater than 0. Never fetch likers for a reply. `max_results` 100. `user.fields=username,name,description,public_metrics,profile_image_url`. Save `likes_<id>`, `reposts_<id>`, and `quotes_<id>`. A missing liker file is normal. The report still runs.

7. Do not fetch followers or following. Do not fetch latest-post pages or the owner's likes. With no following file the report leaves off the 👤? marks and that legend. Those lists load on the first daily, weekly, or on-request report.

8. Render. `<T>` is the UTC time you started (`date -u +%Y-%m-%dT%H:%M:%SZ`). The store paths are `good_neighbours.json` and `state.json` in this bot's store.

```bash
python3 x_neighbours.py --now <T> --first-run --good-neighbours <store>/good_neighbours.json --state <store>/state.json
```

9. Send the report as a Page. `page_canvas` is `report_first.canvas.tsx` and `page_title` is `First report`. Pass the whole file to WriteCanvas. Do not pass a canvas id. Do not write the Page by hand. The Page already starts with `First report` and the short `intro` (what this is, what the sections show, and an invitation to thank someone, ask anytime, or pick daily or weekly). One line in that intro says community sharing can wait. Do not add a second introduction.

The chat message is `headline`, then the Page link labelled `First report`. Put `x_neighbours_first.png` in that message's `images`. Do not paste `report_first.md` or the thank-you sentence into the chat. Those words are on the Page. Do not post the picture.

If WriteCanvas fails or returns no url, send two messages and no Page link. Message 1 is the text of `report_first.md` and no image. Message 2 is `thank_you.text`, a blank line, the link `thank_you.intent` labelled “Post your thank-you”, a blank line, and `thank_you.note`, with the PNG in `images`.

Do not send a good-neighbours card. `add_question` is absent on the first report. Do not ask them to build the list. Do not run `community.py offer`. Do not send a community or share card. `community_offer` and `share_offer` are false. The first experience is the five-post report plus that intro.

10. Then ask what comes next, with `next_steps` from the script. One question. The options are Daily report, Weekly report, and Only when I ask.

- **Daily report.** Every day at 9:00 in their timezone, or UTC if you don't know it. Last 24 hours. Read the “Every day” steps in [SKILL.md](SKILL.md) and create that routine. Do not also create the Monday routine.
- **Weekly report.** Mondays at 9:00. Last 7 days. Read the Monday steps in [SKILL.md](SKILL.md) and create that routine only.
- **Only when I ask.** Create no routine.

Do not create both. Followers and following load on the first regular report, if those files are still missing. That same report is the first time you may send the ⭐ Add card, when `add_question` is present. Offer community mode once with or after that first regular report, using the community skill. Not before.
