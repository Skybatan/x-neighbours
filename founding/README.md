# Founding list

The global list starts from one seed file:

`submissions/founding/2026-11-26T000000Z.neighbours`

That path is `founding_waiver.submission` in [`global/build.json`](../global/build.json). The file's owner, and the credit on the global list, are the neutral identity. Do not put the repo owner's name, X handle, or X user id in this file.

```json
{
  "min_recommendations": 2,
  "rules_version": "1",
  "founding_waiver": {
    "submission": "submissions/founding/2026-11-26T000000Z.neighbours",
    "owner_id": "founding",
    "owner_handle": "founding-submission"
  }
}
```

`owner_id` and `owner_handle` are what the global list displays. Only that exact path bypasses the two-recommendation rule. A later file from a community owner does not.

The rebuild loads that file. Each account in it enters `global/neighbours.global.neighbours` with `source` set to `founding` and one `recommended_by` row for `founding` / `founding-submission`.

Opt-out still removes a founding entry. A banned owner's later submissions do not change this seed. A founding entry stays until opt-out. If another owner later recommends the same account, that row is appended and `source` stays `founding`. The same owner still counts once. The displayed handle of the neighbour refreshes from the newest recommendation.

Later shares use the normal path, `submissions/<x user id>/<UTC timestamp>.neighbours`. Those files keep that owner's real user id and handle. Do not add another pre-made list.

Changing the waiver path needs the label `maintainer-waiver`. Neighbour Dog must not merge that pull request. The maintainer merges it.
