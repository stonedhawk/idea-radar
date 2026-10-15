# {{title}}: AUDIT

Repo: `stonedhawk/{{repo_name}}`
Commit audited: {{commit}}
Audited on: {{date}}
Auditor: {{auditor}}

<!-- Nothing ships until every applicable check passes (SPEC 11). Audit the commit on main that will go public, not a branch. Result is pass, fail or n/a; n/a needs a one-line reason in Evidence. Evidence is a file path with line numbers, a command and its output, or a link to a file in 05_Audit/{{slug}}/. A fail keeps the row and adds a fix to "Fixes before ship". -->

## Verdict

**{{verdict}}**

<!-- PASS only when every row below is pass or n/a. Otherwise BLOCKED, with the failing check numbers. -->

## Checks

| # | Check | Pass condition | Result | Evidence |
|---|---|---|---|---|
| 1 | Claims | Every claim in README, About line and topics traces to a file. Recorded as a claim, evidence, action table. No unmeasured outcomes, no superlatives. | | See check 1 table |
| 2 | Numbers | Any maths is checked by an independent script against 3 or more worked examples. | | |
| 3 | Data flows | Every place data leaves the user's machine is listed, and the docs match the code. | | |
| 4 | Defaults | Local servers bind to localhost. Third-party telemetry is off. | | |
| 5 | LLM data terms | If the tool sends user data to an LLM API, the README says what is sent and warns about free-tier data use where it applies. | | |
| 6 | Prompt tools | A required-rules test and a length test (7,500 characters or less, so it pastes into ChatGPT). Minimal input runs without halting. Tested at least 3 times each in the Claude and ChatGPT apps, graded by the repo's checker. Pass rate recorded; misses go under Known limitations. | | |
| 7 | Packages | The README never documents an unpublished version. Trusted publishing, a tag-equals-version check, and publish before the GitHub release. | | |
| 8 | Demo | Loads with no console errors. GitHub Pages URL set in the repo's Website field when one exists. | | |
| 9 | Copy | No em or en dashes. LICENSE names "Rahul M Shah". About line 200 characters or less. Topics include `liveops-tools` when the tool is for producers. | | |
| 10 | Secrets | No keys in the repo or its history. `.env` gitignored. | | |
| 11 | Portfolio | The card in `stonedhawk/rahul-m-shah-portfolio`, `content/tools/`, is written from the README on main after the audit PR merges, with `inspiredBy` crediting the source. | | |

## Check 1: claims

<!-- One row per claim: every sentence in the README that says what the tool does or how well, the About line, and each topic. Evidence is the file and lines that make the claim true, or the test that proves it. Action is "keep" when the evidence holds, otherwise "reword" or "remove" with the new wording. A claim with no evidence can never be "keep". -->

| Claim | Evidence | Action |
|---|---|---|
| | | |

## Check 2: worked examples

<!-- The independent script, the command that runs it, and at least 3 worked examples with inputs, expected values and where the expected values came from. n/a only if the tool does no maths. -->

| Example | Input | Expected | Tool output | Match |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## Check 3: data flows

<!-- Every network call, upload or file write outside the working directory, found by reading the code (search for HTTP clients, fetch, sockets, analytics SDKs). Then confirm the README section "What leaves your machine" says the same. -->

| Where in the code | What is sent | To whom | In README |
|---|---|---|---|
| | | | |

## Check 6: chat-app runs

<!-- Prompt tools only. At least 3 runs in each app, graded by the repo's checker. Transcripts go in 05_Audit/{{slug}}/. Misses are listed under Limitations in the README. -->

| App | Runs | Passed | Pass rate | Misses |
|---|---|---|---|---|
| Claude | | | | |
| ChatGPT | | | | |

## Fixes before ship

<!-- One line per failing check: what changes, in which file. Re-run the check after the fix and update its row. -->
