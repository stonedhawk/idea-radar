# idea-radar: AUDIT (draft)

Repo: `stonedhawk/idea-radar`
Commit audited: draft against branch `feat/m4-audit-readme`, based on main at f8c1678. Re-run on the commit on main that goes public.
Audited on: 2026-10-15
Auditor: Claude Code (Opus 5.5), for Rahul M Shah

<!-- Draft. It moves to Drive 05_Audit/idea-radar/AUDIT.md once the open rows are closed, and leaves the repo then. README.md:N references are line numbers in README.md on this branch; re-check every one against the commit audited at the final audit. -->

## Verdict

**BLOCKED** on checks 8, 9, 10 and 11, and on the About line and topic rows of check 1. Every row that can pass before the repo goes public passes. What is left is listed under "Fixes before ship".

## Checks

| # | Check | Pass condition | Result | Evidence |
|---|---|---|---|---|
| 1 | Claims | Every claim in README, About line and topics traces to a file. Recorded as a claim, evidence, action table. No unmeasured outcomes, no superlatives. | open | README rows all keep (see check 1 table). About line and topics are not set yet; proposed values are in the table and are set after this audit. |
| 2 | Numbers | Any maths is checked by an independent script against 3 or more worked examples. | pass | `python scripts/check_maths.py`: 16 of 16 hand-worked examples match (8 velocity, 4 measured and 4 estimated; 5 score totals; 3 lens caps). `tests/test_check_maths.py` runs it in CI and shows it fails when a weight or the velocity window changes. |
| 3 | Data flows | Every place data leaves the user's machine is listed, and the docs match the code. | pass | See check 3 table. Every row is in README "What leaves your machine" (README.md:37-45). |
| 4 | Defaults | Local servers bind to localhost. Third-party telemetry is off. | n/a | No server: nothing in `collectors/` or `scripts/` opens a listening socket. No analytics or telemetry SDK: `requirements.txt` is PyYAML and jsonschema only, and the only HTTP client is `urllib.request` in `collectors/common.py:50,76`. |
| 5 | LLM data terms | If the tool sends user data to an LLM API, the README says what is sent and warns about free-tier data use where it applies. | pass | No LLM API is called from the code and no key is stored. The weekly task sends public source text and the ideas written from it to Claude through the owner's account. README.md:44 says what is sent and that on a consumer plan training use follows the account's privacy setting. |
| 6 | Prompt tools | A required-rules test and a length test (7,500 characters or less, so it pastes into ChatGPT). Minimal input runs without halting. Tested at least 3 times each in the Claude and ChatGPT apps, graded by the repo's checker. Pass rate recorded; misses go under Known limitations. | pass | See check 6 table. Required rules and length: `tests/test_prompts.py` for all five prompts. Minimal input and chat-app runs are n/a: these prompts run inside the weekly Claude task and Claude Code on the week's scan files, never pasted into a chat app by a user with their own input. |
| 7 | Packages | The README never documents an unpublished version. Trusted publishing, a tag-equals-version check, and publish before the GitHub release. | n/a | Not published to any package index. The quickstart installs from `requirements.txt` in a clone. |
| 8 | Demo | Loads with no console errors. GitHub Pages URL set in the repo's Website field when one exists. | open | No web demo and no Pages site, so the console and Website parts are n/a. SPEC 15 M4 needs a GIF of a real weekly digest at `docs/demo.gif`; README.md:5 is a placeholder until the 2026-10-19 digest is recorded. |
| 9 | Copy | No em or en dashes. LICENSE names "Rahul M Shah". About line 200 characters or less. Topics include `liveops-tools` when the tool is for producers. | open | Dashes and LICENSE pass: `tests/test_copy.py` checks every text file we wrote (all of them except `data/scans/`, which keeps third-party titles as published; 2026-W42.json has 82 dashes and 2026-W42.selected.json has 1, all in source titles and descriptions). LICENSE:3 is "Copyright (c) 2026 Rahul M Shah". About line and topics are not set yet. |
| 10 | Secrets | No keys in the repo or its history. `.env` gitignored. | open | `gitleaks git --log-opts="--all" --redact` (gitleaks 8.30.1, 2026-10-15): 11 commits scanned, no leaks found. `.gitignore:5` is `.env` and `git check-ignore -v .env` confirms it. Open: four commits on main (f7e7a6b, 0ee2418, ad2fbb1, f8c1678) are authored with a personal email address rather than the GitHub noreply address; that address becomes public with the history. History is left alone; the owner decides. |
| 11 | Portfolio | The card in `stonedhawk/rahul-m-shah-portfolio`, `content/tools/`, is written from the README on main after the audit PR merges, with `inspiredBy` crediting the source. | open | Written after this PR merges, from README.md on main. |

## Check 1: claims

| Claim | Evidence | Action |
|---|---|---|
| Hook: "Every Monday: what is gaining traction in developer and AI tools, turned into tool ideas for game and AI product teams." (README.md:3) | `.github/workflows/scan.yml:5` cron Monday 01:30 UTC; SPEC 8 weekly task on Monday; `prompts/brainstorm.md:3` names the target users. | keep |
| Quickstart: three commands fork, install into a venv and scan (README.md:13-17) | Fresh `git clone` in a scratch directory on 2026-10-15, then lines 2 and 3 exactly as written: "scan 2026-W42: 676 items (github 529, show_hn 47, hf_space 100)". `gh repo fork --clone` was replaced by `git clone`, since forking is the reader's step. | keep |
| The scan writes `data/scans/<week>.json` and adds star counts to `data/stars.csv` (README.md:19) | `scripts/scan.py:1-8` docstring, `write_star_rows` at scripts/scan.py:110; the run above modified both files. | keep |
| `select.py --week <week>` picks the 20 items (README.md:19) | Same run: "selected 2026-W42: 20 items {'github': 12, 'show_hn': 5, 'hf_space': 3}". | keep |
| Forks need Actions enabled before workflows run (README.md:21) | GitHub's behaviour for forked repos, not this repo's code. | keep |
| Collect: GitHub by configured topics, Show HN from the last 7 days, HF trending Spaces (README.md:25) | `collectors/github.py:26-38` builds `topic:` queries from `config/sources.yaml`; `config/sources.yaml` `show_hn.window_days: 7`; `collectors/hf.py:12-20`. | keep |
| Velocity measured from a 5 to 10 day snapshot, otherwise estimated from lifetime stars over age (README.md:25, 49) | `scripts/scan.py:68-91`; `config/sources.yaml` `velocity`; `tests/test_velocity.py`; check 2. | keep |
| Select drops forks, archived, no README, lists and tutorials, HF terms, repeats from two weeks; fills 12, 5, 3 with at most 3 per primary topic; the workflow commits both files (README.md:26) | `scripts/select.py:80-97` (exclusions), `:48-56` (repeats), `:106-163` (quotas, cap, README check); `config/sources.yaml` `select` and `exclude`; `tests/test_select.py`; `.github/workflows/scan.yml:36-47`. | keep |
| Brief, brainstorm, originality, score in a weekly Claude task, Monday 03:15 UTC; 70 or more makes the shortlist, at most 3 (README.md:27) | `prompts/brief.md`, `brainstorm.md`, `originality.md`, `score.md`; `config/rubric.yaml:14-16`; `scripts/validate.py:287`. The 03:15 schedule lives in the owner's Claude account (SPEC 8), not in the repo. | keep |
| validate.py checks schemas and rubric and recomputes every total; render.py writes nothing unless validation passes (README.md:28) | `scripts/validate.py:234-250` (`check_score`), `:320` (`validate_run`); `scripts/render.py:326-329`; `tests/test_validate.py`, `tests/test_render.py`. | keep |
| Spec prompt, 11-check audit gate, track.py star checks (README.md:29) | `prompts/spec.md`, `templates/`, SPEC 11, `scripts/track.py:68` (`due_checks`), `tests/test_track.py`. | keep |
| pytest runs with the network blocked, covering the listed areas (README.md:33) | `tests/conftest.py:16-21` (`no_network`, autouse); `tests/test_velocity.py`, `test_select.py`, `test_validate.py`, `test_render.py`, `test_track.py`, `test_prompts.py`. | keep |
| check_maths.py checks 16 hand-worked examples and exits 1 on a mismatch (README.md:34) | `scripts/check_maths.py`; `tests/test_check_maths.py`. | keep |
| validate.py gates every weekly run before Drive (README.md:35) | SPEC Appendix A step 7; `scripts/render.py:326-329`. | keep |
| What leaves your machine (README.md:39-45) | Check 3 table. | keep |
| Limitations (README.md:49-54) | Velocity: `scripts/scan.py:88-91`. Product Hunt: SPEC 6.1 and 17.1. Claude account with Drive and Sheets: SPEC 5 and Appendix A step 8. Topics only: `collectors/github.py:31-37`. validate.py scope: `scripts/validate.py` checks schema, rubric and dashes only. Prompts not graded across runs: check 6. | keep |
| Credits: data sources; no code was copied (README.md:58) | `collectors/github.py:14`, `collectors/hn.py:10`, `collectors/hf.py:12`. Repo history from 4675264 contains only this project's own code. | keep |
| License: MIT, Rahul M Shah (README.md:62) | LICENSE:1-3. | keep |
| About line (not set). Proposed, 165 characters: "Weekly radar of what is gaining traction in developer and AI tools, turned into tool ideas for game and AI product teams. Scan in GitHub Actions, judgment in Claude." | Same claims as the README hook and stages 1 to 3. | set after audit |
| Topics (not set). Proposed: `liveops-tools`, `game-development`, `product-management`, `github-actions`, `hacker-news`, `huggingface`, `claude`, `trend-analysis` | `liveops-tools`, `game-development`, `product-management`: `prompts/brainstorm.md:3`. `github-actions`: `.github/workflows/`. `hacker-news`: `collectors/hn.py`. `huggingface`: `collectors/hf.py`. `claude`: SPEC 8 weekly task. `trend-analysis`: velocity and traction ranking, `scripts/scan.py:68`, `scripts/select.py:100`. | set after audit |

## Check 2: worked examples

Script: `scripts/check_maths.py`. Command: `python scripts/check_maths.py`. Expected values were worked by hand from SPEC 6.3 (velocity) and SPEC 8.4 (totals and caps); the working is written next to each input in the script and in the tables below. Tool output comes from `scripts.scan.velocity_7d`, `scripts.validate.compute_total`, `scripts.validate.check_score` and `scripts.validate.lens_cap`, and the caps are also compared with `config/rubric.yaml` `lens_caps`. Output on 2026-10-15:

#### Velocity (SPEC 6.3)

| Example | Input | Expected | Tool output | Match |
|---|---|---|---|---|
| measured, 7-day snapshot | 700 stars, created 2026-01-01, snapshots 2026-10-08: 400 | 300 measured ((700 - 400) / 7 x 7 = 300) | 300 measured | yes |
| measured, 5-day edge | 200 stars, created 2026-01-01, snapshots 2026-10-10: 100 | 140 measured ((200 - 100) / 5 x 7 = 140) | 140 measured | yes |
| measured, 10-day edge | 250 stars, created 2026-01-01, snapshots 2026-10-05: 150 | 70 measured ((250 - 150) / 10 x 7 = 70) | 70 measured | yes |
| measured, closest to 7 days wins | 590 stars, created 2026-01-01, snapshots 2026-10-09: 500, 2026-10-05: 400 | 105 measured (6-day snapshot beats 10-day: (590 - 500) / 6 x 7 = 105) | 105 measured | yes |
| estimated, no snapshot | 600 stars, created 2026-09-15, snapshots none | 140 estimated (30 days old: 600 / 30 x 7 = 140) | 140 estimated | yes |
| estimated, snapshot 11 days old | 300 stars, created 2026-08-16, snapshots 2026-10-04: 250 | 35 estimated (snapshot outside 5 to 10 days; 60 days old: 300 / 60 x 7 = 35) | 35 estimated | yes |
| estimated, snapshot 4 days old | 1000 stars, created 2026-07-07, snapshots 2026-10-11: 990 | 70 estimated (snapshot outside 5 to 10 days; 100 days old: 1000 / 100 x 7 = 70) | 70 estimated | yes |
| estimated, created today | 70 stars, created 2026-10-15, snapshots none | 490 estimated (age floor of 1 day: 70 / 1 x 7 = 490) | 490 estimated | yes |

#### Score totals (SPEC 8.4)

| Example | Input | Expected | Tool output | Match |
|---|---|---|---|---|
| score.md example | gaming_x_ai_pm, scores [5, 4, 4, 4, 5, 3] | 86 (25 + 16 + 12 + 12 + 15 + 6 = 86) | 86; validator accepts 86: True, rejects 87: True | yes |
| gaming, below threshold | gaming_only, scores [4, 3, 5, 2, 4, 1] | 67 (20 + 12 + 15 + 6 + 12 + 2 = 67) | 67; validator accepts 67: True, rejects 68: True | yes |
| AI PM, perfect elsewhere | ai_pm_only, scores [2, 5, 5, 5, 5, 5] | 85 (10 + 20 + 15 + 15 + 15 + 10 = 85) | 85; validator accepts 85: True, rejects 86: True | yes |
| gaming, weak | gaming_only, scores [4, 1, 2, 3, 3, 2] | 52 (20 + 4 + 6 + 9 + 9 + 4 = 52) | 52; validator accepts 52: True, rejects 53: True | yes |
| neither, dropped | neither, scores [0, 2, 0, 1, 2, 0] | 17 (0 + 8 + 0 + 3 + 6 + 0 = 17) | 17; validator accepts 17: True, rejects 18: True | yes |

#### Lens caps (SPEC 8.4)

| Example | Input | Expected | Tool output | Match |
|---|---|---|---|---|
| gaming_x_ai_pm | lens_fit 5, every other criterion 5 | 100 (25 + 20 + 15 + 15 + 15 + 10 = 100) | lens_cap() 100, rubric.yaml 100, rejects 101: True | yes |
| gaming_only | lens_fit 4, every other criterion 5 | 95 (20 + 20 + 15 + 15 + 15 + 10 = 95) | lens_cap() 95, rubric.yaml 95, rejects 96: True | yes |
| ai_pm_only | lens_fit 2, every other criterion 5 | 85 (10 + 20 + 15 + 15 + 15 + 10 = 85) | lens_cap() 85, rubric.yaml 85, rejects 86: True | yes |

16 of 16 worked examples match.

## Check 3: data flows

Found by searching `collectors/` and `scripts/` for HTTP clients, sockets and subprocesses (only `urllib.request` in `collectors/common.py`), and by reading the workflows and prompts.

| Where in the code | What is sent | To whom | In README |
|---|---|---|---|
| `collectors/github.py:26-43`, called from `scripts/scan.py:142` | Repository search queries built from `config/sources.yaml` topics and thresholds; `GITHUB_TOKEN` in the `Authorization` header (`collectors/github.py:18-23`) | GitHub, `api.github.com` | README.md:39 |
| `collectors/github.py:93-98`, called from `scripts/select.py:188` | One README request per candidate repo name; the token | GitHub, `api.github.com` | README.md:39 |
| `collectors/hn.py:16-24`, called from `scripts/scan.py:143` | A Show HN search with a time window and minimum points | Algolia, `hn.algolia.com` | README.md:40 |
| `collectors/hf.py:17-20`, called from `scripts/scan.py:144` | A request for the trending Spaces list | Hugging Face, `huggingface.co` | README.md:41 |
| `collectors/common.py:14,32` | User-Agent `idea-radar (+https://github.com/stonedhawk/idea-radar)` on every request above | All three APIs | README.md:42 |
| `.github/workflows/scan.yml:28-47` | The same reads, run in Actions with the built-in token; then `git add data/` and `git push` of scan files and `data/stars.csv` | GitHub, the repo itself (public once the repo is) | README.md:43 |
| SPEC Appendix A step 1; `prompts/brief.md:9-11` | Clone of the repo; README reads with `gh api`, HN item and linked page reads, HF Space API and README reads | GitHub, Algolia, the linked sites, Hugging Face | README.md:44 |
| `prompts/originality.md:12,17` | Two `gh search repos` queries and two web searches per idea | GitHub, the web search provider of the Claude task | README.md:44 |
| The weekly task itself (SPEC 5, 8) | Public source text, the briefs, ideas and scores written from it | Anthropic (Claude), through the owner's account | README.md:44 |
| SPEC Appendix A step 8; `prompts/spec.md:86-92` | Digest, briefs, backlog rows, archive, specs; reads of the backlog sheet | The owner's Google Drive and Sheets, through connectors | README.md:44 |
| `scripts/validate.py`, `scripts/render.py`, `scripts/track.py` | Nothing: local reads and writes under the run directory | n/a | README.md:45 |
| `tests/conftest.py:16-21` | Nothing: socket connects raise in every test | n/a | README.md:33 |

## Check 6: prompt tests and chat-app runs

| Prompt | Characters (limit 7,500) | Required-rules test | Length test |
|---|---|---|---|
| `prompts/brief.md` | 4,026 | pass | pass |
| `prompts/brainstorm.md` | 3,014 | pass | pass |
| `prompts/originality.md` | 3,147 | pass | pass |
| `prompts/score.md` | 3,329 | pass | pass |
| `prompts/spec.md` | 7,046 | pass | pass |

Tests: `tests/test_prompts.py::test_prompt_states_its_required_rules` and `::test_prompt_fits_in_a_chat_app`, parametrised over all five prompts, plus `::test_score_prompt_weights_match_the_rubric`. Removing one rule from a prompt (for example changing "At most 15 ideas per week" to 16 in `prompts/brainstorm.md`) fails the required-rules test.

| App | Runs | Passed | Pass rate | Misses |
|---|---|---|---|---|
| Claude | n/a | n/a | n/a | These prompts run inside the weekly Claude task and in Claude Code on the week's scan files, not pasted into a chat app with a user's own input, so there is no chat-app run to grade. |
| ChatGPT | n/a | n/a | n/a | Same reason. |

The end-to-end evidence that the four weekly prompts run without halting is the 2026-W42 run: `_digest.md` in Drive `02_Briefs/2026-W42/`, created 2026-10-15 08:49 UTC, produced only after `scripts/validate.py` passed. README.md:54 states that the prompts have not been graded across repeated runs.

## Fixes before ship

- Check 8: record `docs/demo.gif` from the real Monday 2026-10-19 digest and commit it; keep the alt text in README.md:5 true to what the GIF shows.
- Check 1 and 9: after merge, set the About line and topics proposed above (About line is 165 characters; topics include `liveops-tools`), then mark their rows keep.
- Check 10: decide on the four main commits authored with a personal email address (f7e7a6b, 0ee2418, ad2fbb1, f8c1678). Either accept that the address becomes public, or rewrite history before the repo goes public. Gitleaks is clean either way.
- Check 11: write the portfolio card from README.md on main after this PR merges, in `stonedhawk/rahul-m-shah-portfolio`, `content/tools/`.
- Then: re-run `gitleaks git --log-opts="--all"`, `python scripts/check_maths.py` and `pytest` on the main commit, fill in "Commit audited", move this file to Drive `05_Audit/idea-radar/AUDIT.md`, and make the repo public.
