---
name: x-neighbours-community
description: >-
  Opt-in community mode for X Neighbours. Use when the owner joins or leaves
  the community, on the Sunday share reminder, on the Monday version check,
  or when sending the neighbours picture in community mode.
---

# X Neighbours — community mode

Community mode is off until the owner opts in. Individual mode is a private bot: local reports, the picture, and the good neighbours list. It does not check for updates, does not download the global list, does not share, and does not mention a tag.

Read [`skills/x-neighbours/SKILL.md`](../x-neighbours/SKILL.md) for the report itself. This file is the community gate. The store file is `community.json` next to `good_neighbours.json`. Never commit it.

```text
/cursor/stores/<store-id>/x-neighbours/community.json
/cursor/stores/<store-id>/x-neighbours/global_neighbours.neighbours
```

## Join and leave

Do not offer community mode during the first report. That report follows [FIRST_RUN.md](../x-neighbours/FIRST_RUN.md) and stops at the five-post demo plus a short intro. After the owner has picked a daily, weekly, or on-request routine, offer community once, with or after their first regular report. If they ask to join before that, wait until that report. Then run:

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

Leaving stops the update check, the Sunday reminder, global-list downloads, sharing, and the picture-tag reminder. Local reports keep working. A list already merged on GitHub stays until they file an opt-out. Tell them that in one sentence.

Before any community behaviour, run `status`. If `community` is false, do not fetch `versions/`, do not fetch the global file, and do not open a share pull request.

```bash
python3 community.py --file <community path> status
python3 community.py --file <community path> plan --repo .
```

`plan` says what a Monday check may touch. `branch` is the git branch in `versions_url` and `global_url`. It is `share_branch` from `config.json` when that is set, otherwise the checked-out branch, otherwise `main`. Pass `--base v3` when this clone should read `v3` and the checkout is something else. In individual mode `fetch_versions` and `fetch_global` are false. Obey that. Do not open those URLs anyway.

## Picture tag

When community mode is on, run this before WriteCanvas, as the main runbook says:

```bash
python3 community.py --file <community path> picture-tag --handle <config handle> --text "<thank_you.text>"
```

If `remind` is false, leave the Page as the report script wrote it. No @handle in the chat message.

If `remind` is true, rewrite the Page with `report_page.py` so the “Post your thank-you” link is `intent` (the composer includes `@SkyXFunNext`) and `text` follows the note. That reminder is the only @handle, and it stays on the Page. The owner still attaches the picture and posts it. You do not post or repost.

The reminder is skipped when the posting account is already `@SkyXFunNext`. If WriteCanvas fails, the plain-text fallback in the main runbook uses the same `intent` and adds `text` after the note.

## Sunday reminder

Create this when they join. Sundays at 9:00 AM in the owner’s timezone (the same `timezone` as reports, or UTC). It does not fetch X.

```bash
python3 community.py --file <community path> sunday --now <T> --timezone <IANA name>
```

If `remind` is false, send nothing. If it is true, send `text` and nothing else. When they can share, the line invites them. When they cannot, it names the day they can share again. It also says a feature release may land on Monday.

## Monday check

On the Monday report, after the Page message, and only when `plan` says to fetch:

1. Download `versions_url` from `plan` to a temp file. Do not commit it.
2. Run:

```bash
python3 community.py --file <community path> check-update --latest <temp file> --now <T>
```

`<T>` is the current UTC time. On any UTC day other than Monday the command returns `reason` `not Monday` and does not compare versions. Do not pull. If they ask to check on another day, add `--force`. Still ask before pulling.

3. If `ask` is true, send `message` as one yes/no card. Do not `git pull` yet.
4. If they say no:

```bash
python3 community.py --file <community path> decide-upgrade --answer no --version <remote_version>
```

Stay on the current version. Do not ask again until the next Monday, unless they ask you to check.

5. If they say yes:

```bash
python3 community.py --file <community path> decide-upgrade --answer yes --version <remote_version>
```

`executed` is false. You run the `steps` yourself. `git pull --ff-only` only. Run `python3 -m pip install -r requirements.txt` only when a step says to, which is when `requirements.txt` changed. If you already know, pass `--requirements-changed yes` or `no` so the step list matches. Then `python3 version.py`, read `CHANGELOG.md`, and tell them the new version in one line. Keep `config.json`, `data/`, the good neighbours file, `state.json`, `community.json`, and `global_neighbours.neighbours`.

6. On the same check, download `global_url` from `plan` and save it:

```bash
python3 community.py --file <community path> save-global --src <downloaded file> --weekly --now <T>
```

Do this even when there is no new bot version. `--now` is the same UTC time. The command refuses with `reason` `not Monday` on any other UTC weekday, even if `--weekly` is passed. Do not add `--force` for a mid-week download. Recommendations you show later come from this local file. The owner chooses who to follow. You do not follow anyone.

If they ask “check for updates” on another day, you may run the check with `--force` on `check-update`. Still ask before pulling. Do not download the global file mid-week.

Individual owners who ask to update follow the Upgrading section of the main runbook. They do not get this check on their own.
