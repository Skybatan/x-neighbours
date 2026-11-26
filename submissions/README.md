# Submissions

Each community owner may add a file here whenever they want:

```text
submissions/<x_user_id>/<UTC timestamp>.neighbours
```

Example: `submissions/100/2026-11-25T170000Z.neighbours`

The contents are JSON. The shape is [`schemas/submission.schema.json`](../schemas/submission.schema.json). The rules are in [`RULES.md`](../RULES.md). Older files stay as history and are never overwritten. The global list reads every file. The same owner counts once per account.

These files are public recommendations. They are not follows. Do not put post text, tokens, or a personal note that names a private conversation.
