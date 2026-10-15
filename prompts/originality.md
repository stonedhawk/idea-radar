# Originality gate (SPEC 8.3)

For every idea in `runs/{week}/ideas.json`, check whether it already exists, then add an `originality` block to the idea, as defined in `schemas/idea.json` (`$defs/originality`). Do this before scoring; killed ideas are not scored.

## Searches

Run all four for every idea:

1. Two GitHub searches with different keyword sets, sorted by stars:

   ```
   gh search repos "<keywords>" --sort stars --limit 10 --json fullName,description,stargazersCount,pushedAt,url
   ```

   One set describes the mechanism in plain words ("kpi anomaly ticket"). The other uses the target user's vocabulary ("liveops event monitoring").

2. Two web searches: one for the tool ("liveops anomaly alert tool"), one for the job the user is doing ("how to catch a broken liveops event early").

Record the exact queries in `searches.github` and `searches.web`.

## Verdict

| Verdict | When |
|---|---|
| `clear` | Nothing comparable found. |
| `differentiated` | Something comparable exists. `differentiator` states, in one line, what this idea does that the closest match does not. |
| `killed` | A maintained project does the same thing and no one-line difference holds. Maintained means a commit in the last 6 months and 100 or more stars. `kill_reason` names it with its stars and last push. |

A comparable project that is unmaintained (no commit in 6 months) or tiny (under 100 stars) does not kill an idea; it makes it `differentiated` at most, and the differentiator can be "maintained" or "packaged for producers" only if that is genuinely the gap.

A differentiator must be about what the tool does or who it serves, not about quality ("better", "simpler", "AI-powered").

## Output

Add to each idea:

```json
"originality": {
  "verdict": "differentiated",
  "searches": {
    "github": ["kpi anomaly ticket", "liveops event monitoring"],
    "web": ["liveops anomaly alert tool", "catch broken liveops event early"]
  },
  "evidence_urls": [
    "https://github.com/example/kpi-watch",
    "https://github.com/search?q=liveops+event+monitoring&type=repositories"
  ],
  "differentiator": "kpi-watch alerts on any metric; this ties each alert to the live event and player segment that caused it.",
  "kill_reason": ""
}
```

- `evidence_urls` is required for every verdict, `https://` only. For `clear`, list the search result pages (`https://github.com/search?q=...&type=repositories`) and the closest non-matches you looked at, so the claim can be checked.
- `differentiator` is an empty string unless the verdict is `differentiated`.
- `kill_reason` is an empty string unless the verdict is `killed`.
- No em dashes or en dashes.

Killed ideas stay in `ideas.json` with their verdict. The render step sends them to `99_Archive` with the reason.
