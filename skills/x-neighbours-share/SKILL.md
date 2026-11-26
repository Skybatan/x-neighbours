---
name: x-neighbours-share
description: >-
  Share an eligible good neighbours list to the X Neighbours repo. Use when a
  community owner asks to share their neighbours. Never use it in individual
  mode, and never follow or post on X.
---

# X Neighbours — share a list

You help a community owner publish neighbours who already talk with them. Recommendations are discovery only. You do not follow anyone, you do not promise a follow back, and you do not post the proof code or the picture. The owner does those in X.

Rules: [`RULES.md`](../../RULES.md). Checker: `share_submission.py`. Community flag: [`skills/x-neighbours-community/SKILL.md`](../x-neighbours-community/SKILL.md).

## Before you build anything

1. `python3 community.py --file <community path> status`. If `community` is false, say sharing is part of community mode and offer to join. Do not build a file.
2. If `pending_pr` is set, tell them that pull request is still open. Do not open another. If they say it was rejected, run `python3 community.py --file <community path> share-result --state rejected` and continue.
3. Fetch the target branch, not a hardcoded `main`. Run `python3 community.py --file <community path> plan --repo .` and read `branch`. That is `share_branch` from `config.json` when set, otherwise the checked-out branch, otherwise `main`. Pass the same name as `--base` when you open the pull request. To force `v3`, set `share_branch` to `v3` or pass `--base v3`.

```bash
git fetch origin <branch>
```

There is no waiting period. A previous share does not block the next one. They may share again after a report that covered a different period.

## Build the list

Use the saved JSON in `data/`, the same counts as the picture. A reply counts only when it replies directly to an owner post or quote. A later reply in that thread does not. Likes are likes on those posts and quotes, not on the owner's replies. Default period is 90 days. If they ask for a shorter window, `--days` may be from 7 to 93. Do not invent accounts. Do not use only the 20-person catch-up list.

The draft is a private file in the bot store. It is not the file that gets committed. `open-pr` reads the draft and opens a pull request that adds `submissions/<user id>/<timestamp>.neighbours`. Do not copy the draft into `submissions/` yourself, and do not commit `share-draft.neighbours`.

```bash
python3 share_submission.py from-data \
  --data data \
  --owner-id <id> \
  --owner-handle <handle> \
  --now <T> \
  --days 90 \
  --community-file <community path> \
  --out <store>/share-draft.neighbours
```

`from-data` and `prepare` refuse when community mode is off. Show the kept handles and counts from the draft. `dropped` is a count by reason plus a few examples, not every excluded account. They may remove names. If you build again, pass `--code` with the code already in the draft so the proof post does not change. `from-data` accepts `--code` the same way `prepare` does.

```bash
python3 share_submission.py from-data \
  --data data \
  --owner-id <id> \
  --owner-handle <handle> \
  --now <T> \
  --days 90 \
  --community-file <community path> \
  --code <code from the draft> \
  --drop <id> \
  --out <store>/share-draft.neighbours
```

A note, when they ask for one, is `--note <id>=<text>` on `prepare` (140 characters, no link, no @mention, no follow bargain). Tags are `--tag <id>=<word>`, at most three.

The draft’s `post_text` is what they post from their own account:

```text
Verifying my X Neighbours list. Code: XN-________
```

Tell them to post that text themselves and send you the post id. You do not post it. You do not open x.com to log them in.

When they send the post id:

```bash
python3 share_submission.py finalize --draft <store>/share-draft.neighbours --proof-post <id>
python3 share_submission.py validate-file <store>/share-draft.neighbours --repo .
```

`finalize` prints `path`. That is `submissions/<user id>/<timestamp>.neighbours`, the file `open-pr` will add. The draft stays in the store. `validate-file` checks the draft's contents and returns `ok` and `errors`. Where the draft is saved does not matter: a file in the bot store is checked on content. The path rule is enforced only when the file is placed at `submissions/<user id>/<timestamp>.neighbours` for the pull request. If validation fails, explain the `errors` in plain language and stop. Do not open a pull request.

## Open the pull request

The pull request adds one new file at `submissions/<user id>/<timestamp>.neighbours`. It does not change `global/build.json`, `versions/`, or older submissions. The draft file is the `--file` argument. It is not the path in the pull request.

```bash
python3 share_submission.py open-pr --file <store>/share-draft.neighbours --repo . --base <branch>
```

`--base` defaults to `share_branch`, then the checked-out branch, then `main`. Pass `v3` while this work is on `v3`. The token is `X_NEIGHBOURS_GITHUB_TOKEN` in the environment, not an argument. Without that token the command does not call GitHub.

If `opened` is false, do not pretend the pull request exists. Give them the draft path and the share issue template only if they want to file it themselves. If `opened` is true, tell them the `url` and the `base` branch in one line and record it:

```bash
python3 community.py --file <community path> record-share --at <submitted_at> --pending-url <url>
```

Say that Neighbour Dog reviews it, and that one owner is not enough for the global list unless the maintainer later points the founding waiver at this exact file. You do not set that waiver.

When they say a pull request merged, run `share-result --state merged`.
