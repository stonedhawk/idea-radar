# Brainstorm (SPEC 8.2)

You turn this week's briefs into tool ideas for game producers, LiveOps teams, monetization designers and AI product managers. Read `runs/{week}/briefs.json` first. Work from each brief's `mechanism`, not from the product.

## The four moves

Apply these to each brief's mechanism:

1. **Same mechanism, new user.** Keep the pattern and hand it to a game producer, a LiveOps team, a monetization designer or an AI product manager. Ask what their version of the event stream, the document, the queue or the review is.
2. **Same user, earlier moment.** Keep the source's user and catch the problem before it happens. If the source cleans up after an incident, what would have warned about it a day earlier?
3. **Combine two patterns.** Join this brief's mechanism with another brief from this week. Both ids go in `source_ids`.
4. **Invert.** Do the opposite of what the source does: remove instead of add, slow down instead of speed up, show the human what the agent would do instead of doing it.

Not every brief yields an idea. A brief whose mechanism has no plausible landing in gaming or AI product work gets none; do not force it.

## Limits

- At most 2 ideas per brief, counted by the first id in `source_ids` (the primary source).
- At most 15 ideas per week. Fewer, better ideas beat a full list.
- Each idea must be buildable by one person in 2 weekends or less.

## Output

Write `runs/{week}/ideas.json`:

```json
{
  "week": "2026-W42",
  "ideas": [ { ...one object per idea... } ]
}
```

Each idea follows `schemas/idea.json`:

| Field | What to write |
|---|---|
| `idea_id` | `{week}-{nn}`, numbered from 01 in the order you write them. |
| `title` | A short working name, 80 characters or less. |
| `one_liner` | What it does for whom, one line, 200 characters or less. |
| `target_user` | The specific role, e.g. "LiveOps producers running weekly events". |
| `move` | 1, 2, 3 or 4. |
| `source_ids` | Brief ids, primary first. Two or more for move 3. |
| `smallest_version` | What ships in 2 weekends or less. Name the input, the output and the interface (CLI, web page, Claude skill, sheet add-on). |
| `demo` | The 10-second GIF in one sentence: what is on screen at the start and what changes. |
| `verifiable_by` | How every claim and number will be tested: a script with worked examples, a golden set with expected values, or a protocol of chat-app runs with a pass rate. |
| `rahul_edge` | What 16 years of F2P and LiveOps adds that a generic builder lacks, and how it changes the design. An empty string if nothing. Decoration does not count. |
| `originality` | Leave this for the originality gate (`prompts/originality.md`). It is required before validation. |

## Rules

- One line per text field except `smallest_version` and `verifiable_by`.
- No em dashes or en dashes.
- Do not port or clone the source's code. The source is inspiration and gets credited.
- Do not promise outcomes you cannot measure ("saves 10 hours a week"). Describe what the tool does.
