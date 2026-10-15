# Score (SPEC 8.4)

Score every idea in `runs/{week}/ideas.json` whose originality verdict is not `killed`. The weights, lens scores, caps and threshold live in `config/rubric.yaml`; read it, do not work from memory.

## Criteria

Each criterion is an integer from 0 to 5 with a one-line reason. A score without a reason fails validation. The reason must say why this idea earned this number, not restate the criterion.

| Criterion | Key | Weight | 5 means |
|---|---|---|---|
| Lens fit | `lens_fit` | 25 | Gaming crossed with AI product work. Fixed by the lens, see below. |
| Rahul's edge | `rahul_edge` | 20 | F2P and LiveOps insight that changes the design, not decoration. An idea with an empty `rahul_edge` scores 0 or 1. |
| Build size | `build_size` | 15 | One weekend. Two weekends scores 4, three scores 2, more scores 0. No other values. |
| 10-second demo | `demo` | 15 | The value is visible in a GIF without narration. |
| Verifiable | `verifiable` | 15 | Every claim and number can be tested by a script or a golden set. |
| Distribution | `distribution` | 10 | A named channel where the target users already gather. Name it in the reason. |

## Lens

Pick one lens per idea. The lens fixes the `lens_fit` score:

| Lens | `lens` value | `lens_fit` score | Highest possible total |
|---|---|---|---|
| Gaming crossed with AI product work | `gaming_x_ai_pm` | 5 | 100 |
| Gaming or LiveOps only | `gaming_only` | 4 | 95 |
| AI product management only | `ai_pm_only` | 2 | 85 |
| Neither | `neither` | 0 | dropped |

So an AI-PM-only idea needs near-perfect scores everywhere else to reach the 70 threshold. That is intended. An idea with lens `neither` is still scored, so the record is complete, but it is dropped: it never reaches the shortlist or the backlog and goes to the archive.

## Total

```
total = sum(weight x score) / 5
```

Out of 100. Work it out and write it; `scripts/validate.py` recomputes it and fails the file if yours differs. Example: lens_fit 5, rahul_edge 4, build_size 4, demo 4, verifiable 5, distribution 3 gives 25 + 16 + 12 + 12 + 15 + 6 = 86.

Shortlist: totals of 70 or more, highest first, at most 3. Ties break on `idea_id`. The validator computes the shortlist; you do not mark it.

## Output

Write `runs/{week}/scores.json`:

```json
{
  "week": "2026-W42",
  "scores": [
    {
      "idea_id": "2026-W42-01",
      "lens": "gaming_x_ai_pm",
      "criteria": {
        "lens_fit": {"score": 5, "reason": "An AI agent doing LiveOps monitoring work."},
        "rahul_edge": {"score": 4, "reason": "Knowing which event KPIs move during a sale decides the alert thresholds."},
        "build_size": {"score": 4, "reason": "Two weekends: CSV reader, detector, ticket writer."},
        "demo": {"score": 4, "reason": "A spike turning into a ticket reads without narration but needs one caption."},
        "verifiable": {"score": 5, "reason": "A golden set of KPI files with labelled anomalies checks every alert."},
        "distribution": {"score": 3, "reason": "The LiveOps and Game Economy Slack groups exist but are small."}
      },
      "total": 86
    }
  ]
}
```

## Rules

- Be harsh. A 5 is rare. Most ideas should land between 40 and 75.
- Score what the idea says, not what it could become.
- One line per reason, 10 characters or more. No em dashes or en dashes.
