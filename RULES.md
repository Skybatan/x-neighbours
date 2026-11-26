# Share rules

A shared good neighbours list is a recommendation. It is not a follow exchange. The bot does not follow anyone, does not ask for a follow back, and does not reward following. The owner taps Follow themselves. See [X’s platform manipulation and spam policy](https://help.x.com/en/rules-and-policies/platform-manipulation).

The numbers in [`rules.py`](rules.py) and [`rules.json`](rules.json) are the copy the checker runs. This page is the explanation. `rules_version` in those files is the version an owner agrees to.

## Who can share

Community mode is opt-in and off by default. An individual bot does not open a share pull request. An owner may submit whenever they want, including after a report that used a different period. There is no waiting period between files.

A rejected pull request can be fixed and sent again. A merged file stays. A later file does not replace it.

## What gets listed

The bot builds the list from the same interaction counts as the neighbours picture, over the period in the file. The default period is the last 90 days. An owner may shorten it, down to 7 days, or use up to 93 days (the length of the first 3-month picture). They may remove names before the pull request. They cannot type in accounts the counts did not produce.

The saved catch-up list (at most 20 people) is not the share list.

Score, using the same quiet weights as the picture (`like_weight` 1, `reply_weight` 3):

```text
score = likes + reposts + 3 × (replies + quotes)
min_score = max(8, ceil(50 × period_days / 90))
```

`replies` in that formula are first-level only. A reply counts when its direct parent (`referenced_tweets` or `referenced_posts`, type `replied_to`) is the owner's original post or quote, the post that starts the conversation. Owner posts P, someone replies (A1), the owner replies, and that person replies again (A2): only A1 counts. A2 does not count as a reply and does not count toward `replies + quotes` of at least 2. `conversation_id` and `in_reply_to_user_id` do not by themselves make a reply first-level. `likes` are likes on those original posts and quotes. The bot does not fetch likers for the owner's replies, and a missing liker file for a reply does not change the score.

| Period | min_score |
|---|---|
| 90 days | 50 |
| 7 days | 8 |

Every listed account also needs `replies + quotes` of at least 2 in the period. Likes alone are not enough. After that filter the list is capped at 100, highest score first, then replies plus quotes.

Also left out: the owner, opted-out accounts, suspended or missing accounts, and anyone the owner removes. A note is optional, at most 140 characters, with no link, no @mention, and no promise of a follow. At most 3 tags.

## The file

Path: `submissions/<x_user_id>/<UTC timestamp>.neighbours`

The timestamp has no colons, for example `2026-11-25T170000Z.neighbours`. The contents are JSON. Older files stay. A pull request adds one new file and does not edit history.

The owner proves the account by posting a one-time `XN-` code from their own X account and giving the bot that post’s id. The bot does not post the code. Neighbour Dog checks the post before a merge.

## The global list

[`global/neighbours.global.neighbours`](global/neighbours.global.neighbours) is rebuilt from every submission file. The same owner counts once per account, even when more than one of their files names that account. An older recommendation stays when a later file leaves someone out. An account appears when two or more owners recommend it. Each entry records `recommended_by` (owner id, handle, time, and submission path). Opt-outs and banned owners are applied after that. The rebuild opens a pull request for that file. It does not push the file onto `main` by itself.

The one exception is the founding waiver in [`global/build.json`](global/build.json). It names a single file path. Accounts in that file enter with one recommendation and `source` set to `founding`. No other file gets the waiver. How to point the waiver at a file, once it exists, is in [`founding/README.md`](founding/README.md). The displayed credit for that file is the neutral identity in the build config (`founding` / `founding-submission`), not a personal handle. A founding entry stays until the person opts out. A later recommendation appends to `recommended_by` and the source stays `founding`.

## Releases

`versions/latest.json` is the only release file. It changes on Monday (UTC) only. A mid-week rebuild of the global list does not bump it. Every bot compares that file with the local `VERSION` once a week and asks before upgrading. `python3 version.py --notes` reads the release notes on that file. Community bots also save a local copy of the global list on that Monday. Individual bots do not download the list.
