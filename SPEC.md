# idea-radar: SPEC

Owner: Rahul M Shah (stonedhawk)
Status: Ready to build
Last updated: 2026-10-15

## 1. What this is

idea-radar finds patterns that are gaining traction in developer and AI product tools, turns them into tool ideas for game producers, LiveOps teams and AI product managers, and carries a picked idea through spec, audit and launch.

It is not a cloner. It reads what is trending to extract the pattern underneath, then asks where that pattern lands in a place nobody has built for yet.

The repo itself is the first thing the pipeline ships, so it has to pass its own audit gate (section 11) before it goes public.

## 2. Why

Two problems, measured on stonedhawk's own repos in October 2026:

1. Idea supply is not the bottleneck. Distribution is. Eight public tool repos had 0 to 2 stars each.
2. AI-assisted builds shipped claims the code did not support: Alexa skills that were prompts, privacy statements the code contradicted, wrong odds in a gacha auditor's own README. Every one was caught only by a manual audit.

So the pipeline optimises for fewer, better launches: a pattern that is gaining attention, an idea that is demonstrably original, a build small enough to finish, and a gate that blocks anything whose claims are not verified.

## 3. Goals

1. Every Monday, produce a ranked shortlist of at most 3 ideas, each with an originality verdict and evidence links.
2. Turn a picked idea into SPEC.md, a target README and LAUNCH.md that a coding agent can build from without further questions.
3. Block any ship that fails the audit gate.
4. Record stars at 7 and 30 days for every ship and feed results back into the scoring weights.

## 4. Non-goals

- Building the picked idea automatically. Building stays human-driven in Claude Code, Codex or Antigravity.
- Posting to LinkedIn or any channel automatically.
- Scraping HTML pages. Public APIs only.
- Cloning or porting a source repo's code. Sources are inspiration and get credited.

## 5. Architecture

Two runtimes, split by what each does well.

| Part | Runs in | Why |
|---|---|---|
| Collect and select | GitHub Actions, weekly | Full network access, free, deterministic. Uses the built-in GITHUB_TOKEN; no other secrets. |
| Brief, brainstorm, originality, score, digest | A weekly scheduled Claude task | Judgment work. No LLM API key stored anywhere. Writes to Google Drive through the account's connectors. |
| Spec generation | Claude (Cowork or Claude Code), on request | Runs when Rahul picks an idea. |
| Build | Claude Code, Codex or Antigravity | Human-driven. |
| Audit, ship, track | Claude Code plus the tracking step of the weekly task | Gate and feedback loop. |

Deterministic steps are Python scripts with tests. Judgment steps are versioned prompt files with JSON outputs validated against schemas. Nothing the LLM writes reaches Drive without passing validation.

### 5.1 Repo layout

```
idea-radar/
├── README.md
├── SPEC.md
├── CLAUDE.md, AGENTS.md, GEMINI.md   one line each: "Read SPEC.md first."
├── LICENSE                            MIT, "Copyright (c) 2026 Rahul M Shah"
├── config/
│   ├── sources.yaml                   topics, queries, quotas, exclusions
│   └── rubric.yaml                    scoring weights and thresholds
├── collectors/
│   ├── common.py                      shared item model, HTTP with retry
│   ├── github.py
│   ├── hn.py
│   └── hf.py
├── scripts/
│   ├── scan.py                        runs collectors, writes data/scans/<week>.json
│   ├── select.py                      velocity, exclusions, quotas, diversity
│   └── validate.py                    validates LLM output files against schemas
├── prompts/
│   ├── brief.md
│   ├── brainstorm.md
│   ├── originality.md
│   ├── score.md
│   └── spec.md
├── schemas/
│   ├── scan_item.json
│   ├── brief.json
│   ├── idea.json
│   └── score.json
├── templates/
│   ├── SPEC.template.md
│   ├── README.template.md
│   ├── LAUNCH.template.md
│   └── AUDIT.template.md
├── data/
│   ├── scans/                         one JSON file per ISO week, committed
│   └── stars.csv                      weekly star snapshots for velocity
├── tests/
└── .github/workflows/
    ├── scan.yml                       weekly, Monday 01:30 UTC
    └── test.yml                       on every push and PR
```

## 6. Stage 1: Collect (GitHub Actions)

Schedule: Monday 01:30 UTC (07:00 IST). Also runnable with workflow_dispatch.

### 6.1 Sources

| Source | Endpoint | What counts as traction |
|---|---|---|
| GitHub | REST search, `/search/repositories` | Stars gained per 7 days |
| Show HN | `https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&numericFilters=created_at_i>{t},points>{min}` | Points within the last 7 days |
| Hugging Face Spaces | `https://huggingface.co/api/spaces?sort=trendingScore&limit=100` | `trendingScore` |

Both public endpoints were confirmed working on 2026-10-15. Product Hunt needs an OAuth token and is out of scope for v1.

### 6.2 GitHub queries

For each topic in `config/sources.yaml`:

- New repos: `topic:{t} created:>{today-30d} stars:>{new_min}` sorted by stars, top 30.
- Established repos with recent activity: `topic:{t} pushed:>{today-7d} stars:>{est_min}` sorted by stars, top 30.

Default topics: `ai-agents, mcp, claude-code, llm-evals, llm, rag, prompt-engineering, agents, product-management, analytics, ab-testing, developer-tools, gamedev, game-development, godot, unity`.

Default thresholds: `new_min: 30`, `est_min: 500`. All values live in `sources.yaml`, not code.

Respect the search API rate limit (30 requests per minute authenticated). Sleep between calls; fail the job if a query errors twice.

### 6.3 Velocity

GitHub has no star-history API, so velocity comes from snapshots.

- Every scan appends `{week, repo, stars}` rows to `data/stars.csv` for every GitHub repo it saw.
- If a snapshot for the repo exists from 5 to 10 days earlier: `velocity_7d = (stars_now - stars_prev) / days_between * 7`, flagged `measured`.
- Otherwise: `velocity_7d = stars_now / max(age_days, 1) * 7`, flagged `estimated`.
- The first two weeks will be mostly estimated. That is expected; selection prefers `measured` when scores tie.

### 6.4 Item model

Every source normalises to one shape (`schemas/scan_item.json`):

```json
{
  "source": "github | show_hn | hf_space",
  "id": "owner/repo | hn id | space id",
  "url": "https://...",
  "title": "string",
  "description": "string",
  "topics": ["string"],
  "language": "string | null",
  "license": "string | null",
  "traction": 123.4,
  "traction_kind": "velocity_7d_measured | velocity_7d_estimated | hn_points | hf_trending",
  "created_at": "ISO date",
  "fetched_at": "ISO datetime"
}
```

### 6.5 Output

`data/scans/{YYYY}-W{ww}.json`, committed by the workflow with message `scan: {YYYY}-W{ww}`. The scan is public data and the file history doubles as a dataset.

## 7. Stage 2: Select (GitHub Actions)

`scripts/select.py --week {YYYY}-W{ww}` writes `data/scans/{YYYY}-W{ww}.selected.json` with 20 items.

Exclude:

- forks and archived repos
- names or topics matching `awesome`, `list`, `course`, `tutorial`, `interview`, `roadmap`, `cheatsheet`
- repos with no README
- HF Spaces whose id or title matches the exclusion terms in `sources.yaml` (default includes `uncensored`, `nsfw`, `lora`, `deepfake`); the trending feed is noisy
- anything selected in either of the previous two weeks

Rank within each source by `traction`, then fill quotas: 12 GitHub, 5 Show HN, 3 HF Spaces. Diversity cap: at most 3 items sharing a primary topic. If a source returns too few items, give its quota to GitHub.

Tests must cover velocity maths (both flags), every exclusion rule, quota fill, diversity cap and the two-week repeat rule, using fixture files, with no network.

## 8. Stage 3: Brief, brainstorm, originality, score (weekly Claude task)

Runs Monday 03:15 UTC (08:45 IST), after the scan workflow. The full task prompt is in Appendix A.

All outputs are JSON first, validated with `python scripts/validate.py`, then rendered to Drive. On a validation failure the task fixes the file and retries once; a second failure is reported, not written.

### 8.1 Brief (`prompts/brief.md`)

Input: the selected item plus its README (via `gh api`) or the HN post and linked page.

Output per item (`schemas/brief.json`):

- `problem`: what hurts, in one sentence
- `user`: who has the problem
- `mechanism`: how the tool works, stated as a pattern that is independent of its domain. Example: "an agent watches a stream of events and files structured tickets". Not: "a Sentry triage bot".
- `why_now`: why it is getting attention this week, only from evidence in the source
- `evidence`: URLs used

A brief that describes the product instead of the pattern fails review. The prompt includes one good and one bad example.

### 8.2 Brainstorm (`prompts/brainstorm.md`)

Apply four moves to each brief's mechanism:

1. Same mechanism, new user: game producers, LiveOps, monetization designers or AI product managers.
2. Same user, earlier moment: catch the problem before it happens.
3. Combine two patterns from this week's briefs.
4. Invert: do the opposite of what the source does.

Keep at most 2 ideas per brief and 15 per week. Each idea (`schemas/idea.json`) has:

- `title`, `one_liner`
- `target_user`
- `move` (1 to 4) and `source_ids`
- `smallest_version`: what ships in 2 weekends or less
- `demo`: the 10-second GIF, described in one sentence
- `verifiable_by`: how claims or maths will be tested (script, golden set, chat-app runs)
- `rahul_edge`: what 16 years of F2P and LiveOps adds that a generic builder lacks; empty if nothing

### 8.3 Originality gate (`prompts/originality.md`)

For each idea:

1. `gh search repos` with 2 keyword sets, sorted by stars.
2. Two web searches.
3. Verdict:
   - `clear`: nothing comparable found
   - `differentiated`: something comparable exists; one line states the difference
   - `killed`: a maintained project (commit in the last 6 months, 100 or more stars) does the same thing and no one-line difference holds

Evidence URLs are required for every verdict, including `clear` (list what was searched). Killed ideas go to the archive with the reason.

### 8.4 Score (`prompts/score.md`, `config/rubric.yaml`)

Each criterion scored 0 to 5 with a one-line reason. A score without a reason fails validation.

| Criterion | Weight | 5 means |
|---|---|---|
| Lens fit | 25 | Gaming crossed with AI product work. Gaming or LiveOps only scores 4. AI PM only scores 2. Neither scores 0 and the idea is dropped. |
| Rahul's edge | 20 | Domain insight that changes the design, not decoration |
| Build size | 15 | One weekend. Two weekends scores 4, three scores 2, more scores 0. |
| 10-second demo | 15 | The value is visible in a GIF without narration |
| Verifiable | 15 | Every claim and number can be tested by a script or a golden set |
| Distribution | 10 | A named channel where the target users already gather |

Total = sum of weight × score / 5, out of 100. Shortlist threshold: 70. The digest shows at most 3 shortlisted ideas, highest first.

An AI-PM-only idea can total at most 85, and a gaming-only idea at most 95, so ideas outside the core lens need near-perfect scores elsewhere to make the shortlist. That is intended.

## 9. Stage 4: Pick and spec (on request)

Rahul picks by setting `status = picked` in the backlog sheet.

Then, in Cowork or Claude Code: "Write the spec for {idea title}." The agent uses `prompts/spec.md` and the templates to write three files into `04_Specs/{slug}/` in Drive:

- `SPEC.md`: problem, user, scope, non-goals, requirements with acceptance criteria, test plan with the verification method from the idea, milestones. Tool-agnostic.
- `README.target.md`: the README the repo should have at launch. One-line hook, demo GIF placeholder, quickstart of 3 commands or fewer, honest limitations, credit to the source pattern.
- `LAUNCH.md`: channels, post drafts, timing, and what gets measured at 7 and 30 days.

When the repo is created, these move into it and the Drive copies become read-only history. The repo copy is the source of truth from then on.

## 10. Stage 5: Build

Out of scope for automation. The repo gets `CLAUDE.md`, `AGENTS.md` and `GEMINI.md`, each a single line pointing to `SPEC.md`, so any agent starts from the same spec.

## 11. Stage 6: Audit gate (required)

Nothing ships until every applicable check passes. Each check came from a defect found in a stonedhawk repo in October 2026. The record lives in `05_Audit/{slug}/AUDIT.md`, built from `templates/AUDIT.template.md`.

| # | Check | Pass condition |
|---|---|---|
| 1 | Claims | Every claim in README, About line and topics traces to a file. Recorded as a claim, evidence, action table. No unmeasured outcomes, no superlatives. |
| 2 | Numbers | Any maths is checked by an independent script against 3 or more worked examples. |
| 3 | Data flows | Every place data leaves the user's machine is listed, and the docs match the code. |
| 4 | Defaults | Local servers bind to localhost. Third-party telemetry is off. |
| 5 | LLM data terms | If the tool sends user data to an LLM API, the README says what is sent and warns about free-tier data use where it applies. |
| 6 | Prompt tools | A required-rules test and a length test (7,500 characters or less, so it pastes into ChatGPT). Minimal input runs without halting. Tested at least 3 times each in the Claude and ChatGPT apps, graded by the repo's checker. Pass rate recorded; misses go under Known limitations. |
| 7 | Packages | The README never documents an unpublished version. Trusted publishing, a tag-equals-version check, and publish before the GitHub release. |
| 8 | Demo | Loads with no console errors. GitHub Pages URL set in the repo's Website field when one exists. |
| 9 | Copy | No em or en dashes. LICENSE names "Rahul M Shah". About line 200 characters or less. Topics include `liveops-tools` when the tool is for producers. |
| 10 | Secrets | No keys in the repo or its history. `.env` gitignored. |
| 11 | Portfolio | The card in `stonedhawk/rahul-m-shah-portfolio`, `content/tools/`, is written from the README on main after the audit PR merges, with `inspiredBy` crediting the source. |

## 12. Stage 7: Ship and track

Ship means: the repo is public, About and topics are set, the portfolio card PR is merged, and the LinkedIn post is drafted with the `my-writing-style` skill for Rahul to publish himself.

Tracking runs inside the weekly Claude task:

- For each row in the backlog sheet with `status = shipped`, record stars on the 7th and 30th day after the ship date into `06_Shipped/{slug}/results.md`.
- LinkedIn reach and inbound messages are entered by hand.
- After every 5 ships, the task writes a comparison of scores against 30-day stars and proposes weight changes as a PR to `config/rubric.yaml`. Rahul approves or rejects it.

## 13. Google Drive layout

```
Build Lab/
├── 00_README          Google Doc: how the pipeline works, rubric, repo links
├── 01_Scan/
│   └── repo-scan      Sheet: one tab per week, the 20 selected items
├── 02_Briefs/
│   └── {YYYY}-W{ww}/  One .md brief per item, plus _digest.md
├── 03_Backlog/
│   └── idea-backlog   Sheet: the index for everything
├── 04_Specs/{slug}/   Draft SPEC, target README, LAUNCH until the repo exists
├── 05_Audit/{slug}/   AUDIT.md, maths checks, chat-app transcripts
├── 06_Shipped/{slug}/ assets/, linkedin-post.md, results.md
└── 99_Archive/        Killed and rejected ideas, one line each on why
```

The backlog sheet is the index. Status lives in the sheet, never in folder names.

### 13.1 Backlog sheet columns

`week, idea_id, title, one_liner, target_user, move, source_urls, originality, differentiator, evidence_urls, lens, edge, build, demo, verifiable, distribution, total, status, picked_on, repo_url, shipped_on, stars_7d, stars_30d, notes`

Status values: `new, shortlisted, picked, specced, building, audit, shipped, killed, parked`.

## 14. Success metrics

Pipeline health:

- The weekly run completes 9 weeks out of 10.
- At least 3 ideas per week pass the originality gate.
- Time from pick to ship: 3 weekends or less.

Outcome:

- The first pipeline-sourced tool reaches 25 stars within 30 days of launch. That is the point where the portfolio starts showing a star count.
- idea-radar itself reaches 25 stars within 30 days of its own launch.

## 15. Milestones

| # | Scope | Done when |
|---|---|---|
| M1 | Collectors, scan workflow, select.py, stars.csv, tests | Two consecutive weekly scans committed; all tests pass with no network |
| M2 | Prompts, schemas, validate.py, the weekly Claude task writing to Drive | One full Monday run produces a validated digest in Drive |
| M3 | Spec, README, LAUNCH and AUDIT templates; tracking | One idea goes from pick to SPEC.md in Drive |
| M4 | Launch idea-radar | Audit gate passed on idea-radar; README has a GIF of a real weekly digest; repo public |

The repo stays private until M4.

## 16. Seed backlog

Add as the first `shortlisted` row, sourced from this month's audit rather than a scan:

**Skill evals for prompt tools.** Golden-set tests for LLM system prompts: expected values per test case, a checker that grades saved outputs, required-rules and length tests, and a protocol for chat-app runs with pass rates. Extracted from `scripts/check_output.py` in gacha-odds-pity-auditor and `scripts/check_calendar.py` in liveops-event-calendar-skill. Source pattern: eval harnesses for LLM apps.

## 17. Open questions

1. Product Hunt as a fourth source in v2 needs an OAuth token stored as a repo secret.
2. Whether briefs should also be published in the repo as a weekly public digest. Default: no, they stay in Drive.

## Appendix A: weekly Claude task prompt

```
Weekly idea-radar run. Follow SPEC.md sections 8 and 12 exactly.

1. Clone stonedhawk/idea-radar. Read SPEC.md.
2. Find this ISO week's data/scans/{YYYY}-W{ww}.selected.json. If it is
   missing, check the scan workflow's latest run with gh, report the
   failure, and stop.
3. For each of the 20 items, write a brief per prompts/brief.md.
4. Brainstorm per prompts/brainstorm.md.
5. Run the originality gate per prompts/originality.md.
6. Score per prompts/score.md and config/rubric.yaml.
7. Validate every JSON output with python scripts/validate.py. Fix and
   retry once on failure. Never write unvalidated output to Drive.
8. In Google Drive, Build Lab/:
   - add this week's tab to 01_Scan/repo-scan
   - write briefs and _digest.md to 02_Briefs/{YYYY}-W{ww}/
   - append ideas to 03_Backlog/idea-backlog with status new or
     shortlisted; killed ideas go to 99_Archive with the reason
9. Tracking: for every shipped row whose ship date was 7 or 30 days ago,
   record stars into 06_Shipped/{slug}/results.md and the sheet.
10. Finish with a summary: the shortlisted ideas with totals, their
    originality verdicts, and any step that failed.
```
