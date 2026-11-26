---
name: x-neighbours-community
description: >-
  Opt-in community mode for X Neighbours. Use when the owner joins or leaves
  the community, on the Sunday share reminder, on the Monday global-list
  save, or when sending the neighbours picture in community mode.
---

# X Neighbours — community mode

Community mode is off until the owner opts in. Individual mode is a private bot: local reports, the picture, and the good neighbours list. It does not download the global list, does not share, and does not mention a tag. The Monday update check runs either way. It lives in the main runbook, not here.

Read [`skills/x-neighbours/SKILL.md`](../x-neighbours/SKILL.md) for the report itself. This file is the community gate. The store file is `community.json` next to `good_neighbours.json`. Never commit it.

```text
/cursor/stores/<store-id>/x-neighbours/community.json
/cursor/stores/<store-id>/x-neighbours/global_neighbours.neighbours
```

## Join and leave

Do not offer community mode during the welcome tour. That tour follows [FIRST_RUN.md](../x-neighbours/FIRST_RUN.md) and stops at the five-post demo plus a short intro. After the owner has picked a daily, weekly, or on-request routine, offer community once, with or after their first regular report. If they ask to join before that, wait until that report. Then run:

```bash
python3 community.py --file <community path> offer
```

If `offer` is true, send one yes/no card with `prompt`. Do not add a second explanation. If they say yes:

```bash
python3 community.py --file <community path> join --now <T>
```

Then create the Sunday routine below. If they say no, stop. `offer` records that you asked. Do not ask again on later runs. They can still say “join the community” later, and you run `join`.

To leave:

```bash
python3 community.py --file <community path> leave --now <T>
```

Leaving stops the Sunday reminder, global-list downloads, sharing, and the picture-tag reminder. The Monday update check keeps running. Local reports keep working. A list already merged on GitHub stays until they file an opt-out. Tell them that in one sentence.

Before any community behaviour, run `status`. If `community` is false, do not fetch `versions/`, do not fetch the global file, and do not open a share pull request.

```bash
python3 community.py --file <community path> status
python3 community.py --file <community path> plan --repo .
```

`plan` says what a community Monday may touch. `branch` is the git branch in `versions_url` and `global_url`. It is `share_branch` from `config.json` when that is set, otherwise the checked-out branch, otherwise `main`. Pass `--base v3` when this clone should read `v3` and the checkout is something else. In individual mode `fetch_versions` and `fetch_global` are false. Obey that for this command. Do not open the global URL anyway. The version check does not use this plan. The main runbook uses `version.py --plan`, which fetches the version file with community mode off and never fetches the global file.

## Picture tag

When community mode is on, run this before WriteCanvas, as the main runbook says:

```bash
python3 community.py --file <community path> picture-tag --handle <config handle> --text "<thank_you.text>"
```

If `remind` is false, leave the Page as the report script wrote it. No @handle in the chat message.

If `remind` is true, rewrite the Page with `report_page.py` so the “Post your thank-you” link is `intent` (the composer includes `@SkyXFunNext`) and `text` follows the note. That reminder is the only @handle, and it stays on the Page. The owner still attaches the picture and posts it. You do not post or repost.

The reminder is skipped when the posting account is already `@SkyXFunNext`. If WriteCanvas fails, the plain-text fallback in the main runbook uses the same `intent` and adds `text` after the note. When you rewrite the Page, keep `--picture-asset` so the house picture stays inside the Page. The main runbook has the WriteCanvasAsset step.

## Community Honor Roll

This is the list of recommended accounts. It is not the opt-in card and not the share flow. Those stay in the chat.

Send the Page when the owner asks to see the community list, and after the Monday `save-global` when the file has people. Do not send it on the welcome tour. Do not send it in individual mode. Do not follow anyone on it.

```bash
python3 community_page.py --global <store>/global_neighbours.neighbours --out <dir>
```

If `send` is false, say `reason` in one line. Do not invent a Page. If `send` is true, pass the canvas file to WriteCanvas. Do not pass a canvas id. The title is `Community Honor Roll`. The chat message is `headline` and the Page link. Each @handle on the Page links to that profile. The count is how many owners recommended them. A recommendation is not a follow.

## Sunday reminder

Create this when they join. Sundays at 9:00 AM in the owner’s timezone (the same `timezone` as reports, or UTC). It does not fetch X.

```bash
python3 community.py --file <community path> sunday --now <T> --timezone <IANA name>
```

If `remind` is false, send nothing. If it is true, send `text` and nothing else. The line invites them to share. There is no waiting period between shares. It also says a feature release may land on Monday.

## Monday global list

The version check is the Monday update check in the main runbook. It runs with community mode off. Do not run `check-update` or `decide-upgrade` from this file. Pip install still happens only when `requirements.txt` changed, and that step is in the main runbook. The report itself is still a Page.

After that check, and only when community mode is on, download `global_url` from `plan` and save it:

```bash
python3 community.py --file <community path> save-global --src <downloaded file> --weekly --now <T>
```

Do this even when there is no new bot version. `--now` is the same UTC time. The command refuses with `reason` `not Monday` on any other UTC weekday, even if `--weekly` is passed. Do not add `--force` for a mid-week download. Recommendations you show later come from this local file. The owner chooses who to follow. You do not follow anyone.

If community mode is off, do not download the global file. An owner who asks to update on another day uses the main runbook. Still ask before pulling. Do not download the global file mid-week.
