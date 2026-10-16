# {{title}}: SPEC

Owner: Rahul M Shah (stonedhawk)
Status: Ready to build
Last updated: {{date}}
Idea: {{idea_id}}, picked on {{picked_on}}, score {{total}} of 100
Originality: {{originality}}. {{differentiator}}

<!-- Tool-agnostic: no section may assume Claude Code, Codex or Antigravity. A coding agent must be able to build from this file without asking a question. -->

## 1. What this is

{{one_liner}}

## 2. Problem

<!-- What hurts, for whom, and what they do today instead. Two to four sentences. Only facts from the brief, the originality evidence or Rahul's notes; no market sizes, no invented numbers. -->

## 3. User

{{target_user}}

<!-- One paragraph: the moment in their week when they reach for this tool, and what they have open at the time (a spreadsheet, a build, a store page). -->

Why Rahul: {{rahul_edge}}

## 4. Scope

The smallest version, buildable in two weekends or less:

{{smallest_version}}

<!-- Turn the smallest version into a numbered list of what ships. Each item must map to at least one requirement in section 6. -->

## 5. Non-goals

<!-- At least three. Include anything the source tool does that this one deliberately does not, and anything that would push the build past two weekends. -->

## 6. Requirements

<!-- One row per requirement. R1, R2, ... Every acceptance criterion is observable: a command and its expected output, a file that exists, a test that passes. No "fast", "accurate" or "easy" without a number and a way to measure it. -->

| # | Requirement | Acceptance criteria |
|---|---|---|
| R1 | | |

## 7. Data flows and defaults

<!-- Audit checks 3, 4, 5 and 10 are designed in here, not discovered later. List every place data leaves the user's machine (API calls, uploads, telemetry) or write "None: everything runs locally." Local servers bind to 127.0.0.1. Third-party telemetry is off. If user data goes to an LLM API, say what is sent. Secrets come from environment variables and .env is gitignored. -->

## 8. Test plan

Verification method from the idea: {{verifiable_by}}

<!-- Turn the verification method into concrete tests: the golden set (size, where the expected values come from), the script that grades it, and any maths checked against 3 or more worked examples by an independent script (audit check 2). For a prompt tool, add the required-rules test, the 7,500 character length test and the chat-app run protocol (audit check 6). Map each test to the requirements it covers. -->

| Test | Covers | How it runs |
|---|---|---|
| | | |

## 9. Demo

{{demo}}

<!-- The 10-second GIF: the input on screen, the action, the result. It must read without narration. -->

## 10. Milestones

<!-- Two to four milestones, each ending in something runnable. The last one is "audit gate passed" (templates/AUDIT.template.md in idea-radar). -->

| # | Scope | Done when |
|---|---|---|
| M1 | | |

## 11. Repo setup

- `CLAUDE.md`, `AGENTS.md` and `GEMINI.md`: one line each, "Read SPEC.md first."
- RTK is required for every agent session in this repo. `AGENTS.md` says so in its working rules: install it with `brew install rtk` (other platforms: https://github.com/rtk-ai/rtk#installation), set up the hook once per machine with `rtk init` and the flag for your agent (`rtk init -g` for Claude Code, `rtk init -g --codex` for Codex, `rtk init -g --gemini` for Gemini CLI, `rtk init -g --agent antigravity` for Antigravity), and check it with `rtk gain`. Where no hook is active, prefix shell commands with `rtk` (`rtk pytest`, `rtk git status`). RTK is a development tool only: it is not a runtime dependency and CI does not use it.
- `LICENSE`: MIT, "Copyright (c) {{year}} Rahul M Shah"
- `README.md`: starts from `README.target.md` and is corrected to match what was built before launch.
- Repo name: `{{repo_name}}`

## 12. Credits

Source pattern: {{source_pattern}}
Sources: {{source_urls}}

This tool takes the pattern, not the code. No source code is copied or ported.
