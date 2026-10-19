# Brief (SPEC 8.1)

You write one brief per item in `data/scans/{week}.selected.json`. A brief extracts the pattern underneath a trending tool so it can be moved somewhere new. It is not a review of the tool.

## Input

For each selected item, read the source before writing anything:

- `github`: the README, with `gh api repos/{owner}/{repo}/readme -H "Accept: application/vnd.github.raw"`. Also the repo description and topics from the scan item.
- `show_hn`: the post and its text from `https://hn.algolia.com/api/v1/items/{id}`, and the page the post links to (the item's `link` field) if there is one.
- `hf_space`: `https://huggingface.co/api/spaces/{id}` and the Space's README at `https://huggingface.co/spaces/{id}/raw/main/README.md`.

If a source will not load (a blocked host, a timeout, an error page), try these in order before you give up on it:

1. A browser tool, if your agent has one: Claude in Chrome, the desktop app's built-in browser, or a headless browser in the shell. Open the same URL and read the page text.
2. The source's own GitHub repo, if the post, page or Space names one: read its README as for a `github` item and add the repo URL to `evidence`.

Use only what you read. If you still cannot read enough to state the mechanism, skip the item (see below) instead of guessing, and say in the skip reason which routes you tried, so the next run knows the item may be briefable with better access.

## Output

Write `runs/{week}/briefs.json`:

```json
{
  "week": "2026-W42",
  "briefs": [ { ...one object per brief... } ],
  "skipped": [ {"id": "...", "reason": "one line"} ]
}
```

Each brief follows `schemas/brief.json`:

| Field | What to write |
|---|---|
| `source`, `id`, `url`, `title` | Copied from the selected item, unchanged. |
| `problem` | What hurts, in one sentence. Name the pain, not the tool. |
| `user` | Who has the problem. A role, not "developers" or "everyone" if you can be more precise. |
| `mechanism` | How the tool works, stated as a pattern that would still make sense in a different domain. One sentence. Never name the product, its company or its brand. |
| `why_now` | Why it is getting attention this week. Only from evidence in the source: star velocity, points, a launch post, a release, a model that just shipped. If the source gives no reason, say what the traction number is and that no reason is stated. |
| `evidence` | Every URL you used, `https://` only. At least the item URL. |

Every selected item must appear exactly once, either in `briefs` or in `skipped`. Skip an item when:

- it now matches an exclusion term in `config/sources.yaml` (the list can change after a scan)
- the source has too little text to state a mechanism (an empty Show HN post with a dead link, a Space with no README)
- it is not a tool (a dataset, a model card, a news post)

## Pattern, not product

The mechanism is the part that travels. Write it so someone who has never heard of the tool could build the same shape for a different user.

**Good** (a Sentry alert triage bot):

```json
{
  "problem": "On-call engineers lose the first hour of every incident reading duplicate alerts to work out which one matters.",
  "user": "On-call engineers at teams without a dedicated SRE",
  "mechanism": "An agent watches a stream of events, groups duplicates, and files one structured ticket per root cause with a suggested owner.",
  "why_now": "1,200 stars in its first week; the README links a launch thread that reached the Hacker News front page."
}
```

This works because the mechanism names the moving parts (a stream of events, grouping, a structured ticket, an owner) and none of them depend on Sentry. The same sentence describes a tool that watches game telemetry and files LiveOps tickets.

**Bad** (the same tool):

```json
{
  "problem": "Sentry is noisy.",
  "user": "Developers",
  "mechanism": "A Sentry triage bot that uses GPT to make Sentry better.",
  "why_now": "AI agents are hot right now."
}
```

This fails review for four reasons. The problem names the product, not the pain. "Developers" is too broad to design for. The mechanism names the product and a model instead of the steps, so nothing travels. The why_now is an opinion, not evidence from the source. `scripts/validate.py` rejects a mechanism that contains the repo or Space name.

## Rules

- One line per text field. No line breaks.
- No em dashes or en dashes anywhere you write. Use commas, colons or full stops.
- No superlatives you cannot back with a number from the source.
- Do not invent numbers. Traction figures come from the scan item.
