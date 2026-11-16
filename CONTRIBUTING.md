# Contributing

Thanks for helping with X Neighbours. People and bots follow one short process.

## 1. Open an issue first

One issue per change. Say what you want to change and why. A bug, a doc fix, and a new behaviour each get their own issue.

## 2. One change per pull request

Keep the pull request to that one issue. In the description, write `Closes #N` with the issue number. GitHub starts from the checklist in [`.github/pull_request_template.md`](.github/pull_request_template.md).

## 3. Tests

Add or update tests for the behaviour you changed. From the repo directory:

```bash
python3 -m unittest discover -s tests -v
```

Run that before you open the pull request. CI will also run it.

## 4. Docs the change touches

Update the docs your change affects:

- [README.md](README.md), when setup, flags, or what a report does has changed.
- [`skills/x-neighbours/SKILL.md`](skills/x-neighbours/SKILL.md), when the bot's instructions change. That file is becoming the single source of bot instructions ([#29](https://github.com/Skybatan/x-neighbours/issues/29)).
- `CHANGELOG.md`, when someone upgrading should know what changed ([#28](https://github.com/Skybatan/x-neighbours/issues/28)).

Leave a file alone when the change does not touch it.

## 5. No personal data

Keep real handles, user ids, and tokens out of code, fixtures, and docs. The samples in `examples/` and `tests/fixtures/` are fictional. `config.json`, `data/`, reports, and pictures stay on your machine.

## 6. Review

The owner reviews and merges.
