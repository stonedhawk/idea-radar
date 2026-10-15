# Spec (SPEC 9)

Rahul picks an idea by setting `status = picked` in the backlog sheet, then asks: "Write the spec for {idea title}." You turn that idea into three files a coding agent can build from without asking a question: `SPEC.md`, `README.target.md` and `LAUNCH.md`, from the templates in `templates/`.

This runs on request, in Cowork or Claude Code. It is not part of the weekly task.

## 1. Find the idea

Read the `backlog` tab of `Build Lab/03_Backlog/idea-backlog`. Columns are in SPEC 13.1.

- Use the row whose `title` matches the request and whose `status` is `picked`.
- If that row's status is not `picked`, stop and say so. Do not change a status to pick an idea for Rahul.
- If its `originality` is `not checked` or empty (the seed row), run `prompts/originality.md` for it first and report the verdict. A `killed` verdict stops here.

## 2. Gather the inputs

Read everything before writing anything:

| Input | Where |
|---|---|
| The backlog row | The sheet: `idea_id`, `title`, `one_liner`, `target_user`, `source_urls`, `originality`, `differentiator`, `evidence_urls`, `total`, `picked_on`, `notes` |
| The full idea | `runs/{week}/ideas.json` if it is on this machine, otherwise `02_Briefs/{week}/_digest.md` in Drive: `smallest_version`, `demo`, `verifiable_by`, `rahul_edge` |
| The source briefs | `runs/{week}/briefs.json` or `02_Briefs/{week}/{brief}.md`: the `mechanism` of each source, which is the pattern to credit |
| The score reasons | `runs/{week}/scores.json` or the score table in the digest; the `distribution` reason names the channel |
| The sources | Every URL in `source_urls` and `evidence_urls`. Open the closest competitor so the non-goals and the differentiator are concrete |

If `smallest_version`, `demo` or `verifiable_by` cannot be found (the seed row has none), ask Rahul for them in one message before writing. Do not invent them.

## 3. Fill the templates

The slug names the Drive folders for this idea from now on (`04_Specs`, `05_Audit`, `06_Shipped`). Compute it, do not type it:

```bash
python -c 'from scripts.track import slugify; print(slugify("Shop offer teardown"))'
```

Copy `templates/SPEC.template.md`, `templates/README.template.md` and `templates/LAUNCH.template.md`. Replace every placeholder and every `<!-- ... -->` instruction comment with real content; the comments say what each section needs. `templates/AUDIT.template.md` is filled later, at the audit gate, into `05_Audit/{slug}/AUDIT.md`; do not write it now.

| Placeholder | Value |
|---|---|
| `{{title}}` | Backlog `title` |
| `{{slug}}` | From `slugify`, above |
| `{{idea_id}}` | Backlog `idea_id` |
| `{{one_liner}}` | Backlog `one_liner` |
| `{{target_user}}` | Backlog `target_user` |
| `{{picked_on}}` | Backlog `picked_on`; if empty, today, and write it back to the sheet |
| `{{total}}` | Backlog `total`; "not scored" for the seed row until it is scored |
| `{{originality}}` | Backlog `originality`: `clear` or `differentiated` |
| `{{differentiator}}` | Backlog `differentiator`; for `clear`, "Nothing comparable found" and the two searches |
| `{{smallest_version}}` | The idea's `smallest_version` |
| `{{demo}}` | The idea's `demo` |
| `{{verifiable_by}}` | The idea's `verifiable_by` |
| `{{rahul_edge}}` | The idea's `rahul_edge`, rewritten as one plain sentence about the design decision it changes |
| `{{source_pattern}}` | The source brief's `mechanism`, plus the source repo, post or Space name |
| `{{source_urls}}` | Backlog `source_urls`, as Markdown links |
| `{{distribution}}` | The `distribution` score reason |
| `{{repo_name}}` | The slug, unless Rahul names the repo |
| `{{hook}}` | One line for the top of the README: the user's problem and what the tool does about it, under 120 characters |
| `{{quickstart}}` | The commands to install and run it, 3 or fewer, as they will work once built |
| `{{about_line}}` | GitHub About line, 200 characters or less, no claims the README does not make |
| `{{topics}}` | 5 to 10 GitHub topics; include `liveops-tools` when the tool is for producers |
| `{{date}}` | Today, YYYY-MM-DD |
| `{{year}}` | This year, for the LICENSE line |
| `{{commit}}`, `{{auditor}}`, `{{verdict}}` | Audit time only, in `AUDIT.template.md` |

What each file must hold (SPEC 9):

- `SPEC.md`: problem, user, scope, non-goals, requirements with acceptance criteria, a test plan built on `verifiable_by`, milestones. Tool-agnostic: no instruction may depend on a particular coding agent. The scope must fit in two weekends; if it does not, cut it and move the rest to non-goals.
- `README.target.md`: the README the repo should have at launch. One-line hook, demo GIF placeholder, quickstart of 3 commands or fewer, honest limitations, credit to the source pattern. Write it as the build will be, not as a pitch: every claim in it becomes a row in the audit's claim, evidence, action table, so each one must map to a requirement in `SPEC.md`.
- `LAUNCH.md`: channels, post drafts, timing, and what gets measured at 7 and 30 days.

## 4. Check before writing

Every item must hold. Fix and re-check; do not write a file that fails one.

- No `{{` and no `<!--` left in any of the three files.
- No em dashes or en dashes anywhere (audit check 9).
- Every README claim in "What it does" maps to a requirement number in `SPEC.md`.
- Every requirement has an acceptance criterion someone can run or look at.
- The quickstart is 3 commands or fewer.
- The README has at least two specific limitations and credits the source pattern with a link.
- The About line is 200 characters or less.
- No superlatives and no outcomes nobody has measured ("saves hours", "the best", "10x").
- No source code was copied from the source repo; the credit says so.

## 5. Write to Drive

In `Build Lab/04_Specs/`, create the folder `{slug}` if it does not exist and write the three files into it as plain Markdown (`text/markdown`, no conversion to Google Docs): `SPEC.md`, `README.target.md`, `LAUNCH.md`. If the folder already has them, ask Rahul before overwriting.

Then set the backlog row's `status` to `specced`. Do not share any file or folder.

Finish with: the Drive folder link, the requirement count, the milestones, and anything you had to cut to fit two weekends.

When the repo is created, these files move into it and the Drive copies become read-only history (SPEC 9).

## Rules

- Only facts from the inputs above. No invented numbers, users or quotes.
- No em dashes or en dashes anywhere you write. Use commas, colons or full stops.
- Plain sentences. No superlatives you cannot back with a number from the inputs.
