#!/usr/bin/env python3
"""Render a validated week into the files the weekly task writes to Drive.

Usage: python scripts/render.py runs/2026-W42 [--selected PATH] [--out DIR]

Runs scripts/validate.py first and writes nothing if it fails. Output, in
--out (default <run_dir>/drive):

  briefs/<slug>.md      one brief per item       -> 02_Briefs/<week>/
  _digest.md            the week's digest        -> 02_Briefs/<week>/
  archive.md            killed and dropped ideas -> 99_Archive/<week>-archive.md
  backlog_rows.json     rows in SPEC 13.1 order  -> 03_Backlog/idea-backlog
  scan_rows.json        header plus 20 rows      -> 01_Scan/repo-scan, tab <week>
"""
from __future__ import annotations

import os
import sys

# scripts/select.py shadows the stdlib "select" module (socket imports it)
# while this directory is on the import path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

from scripts.validate import (  # noqa: E402
    DASHES,
    RUBRIC,
    load_rubric,
    resolve_selected,
    validate_run,
)

BACKLOG_COLUMNS = [
    "week", "idea_id", "title", "one_liner", "target_user", "move", "source_urls",
    "originality", "differentiator", "evidence_urls", "lens", "edge", "build", "demo",
    "verifiable", "distribution", "total", "status", "picked_on", "repo_url",
    "shipped_on", "stars_7d", "stars_30d", "notes",
]
SCAN_COLUMNS = [
    "week", "source", "id", "url", "title", "description", "topics", "language",
    "license", "traction", "traction_kind", "created_at", "fetched_at",
]
CRITERIA = [
    ("lens_fit", "Lens fit"),
    ("rahul_edge", "Rahul's edge"),
    ("build_size", "Build size"),
    ("demo", "10-second demo"),
    ("verifiable", "Verifiable"),
    ("distribution", "Distribution"),
]
MOVES = {
    1: "same mechanism, new user",
    2: "same user, earlier moment",
    3: "combine two patterns",
    4: "invert",
}
JOIN = " ; "


def clean(text) -> str:
    """Source titles can carry en or em dashes; our copy never does."""
    text = "" if text is None else str(text)
    return DASHES.sub("-", text)


def sheet_cell(value):
    """Keep text from being read as a formula when written to Sheets as user input.

    Scan text and model output are untrusted; a leading apostrophe makes Sheets
    store the cell as plain text and is not shown.
    """
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def one_line(text) -> str:
    return " ".join(clean(text).split())


def slug(brief: dict) -> str:
    prefix = {"github": "", "show_hn": "hn-", "hf_space": "hf-"}[brief["source"]]
    body = re.sub(r"[^a-z0-9]+", "-", brief["id"].lower()).strip("-")
    return prefix + body


def fmt_total(total: float) -> str:
    return f"{total:g}"


def quoted(queries: list[str]) -> str:
    return ", ".join(f'"{one_line(q)}"' for q in queries)


def key_evidence(orig: dict) -> str:
    """The most specific evidence URL: the first that is not a search results page."""
    urls = orig["evidence_urls"]
    return next((u for u in urls if "/search?" not in u), urls[0])


def dropped_ids(data: dict, rubric: dict) -> set[str]:
    """Ideas whose lens is outside the rubric (SPEC 8.4: scored 0 and dropped)."""
    return {s["idea_id"] for s in data["scores"]["scores"] if s["lens"] in rubric["dropped_lenses"]}


# Markdown


def render_brief(brief: dict, item: dict | None, ideas: list[dict], scores: dict) -> str:
    lines = [f"# {one_line(brief['title'])}", ""]
    meta = f"Source: {brief['source']}, {brief['url']}"
    if item is not None:
        meta += f", traction {item['traction']:g} ({item['traction_kind']})"
    lines += [meta, ""]
    lines += [
        f"**Problem:** {one_line(brief['problem'])}",
        "",
        f"**User:** {one_line(brief['user'])}",
        "",
        f"**Mechanism:** {one_line(brief['mechanism'])}",
        "",
        f"**Why now:** {one_line(brief['why_now'])}",
        "",
        "## Evidence",
        "",
    ]
    lines += [f"- {url}" for url in brief["evidence"]]
    mine = [i for i in ideas if brief["id"] in i["source_ids"]]
    if mine:
        lines += ["", "## Ideas from this brief", ""]
        for idea in mine:
            verdict = idea["originality"]["verdict"]
            score = scores.get(idea["idea_id"])
            total = f", total {fmt_total(score['total'])}" if score else ""
            lines.append(f"- {idea['idea_id']} {one_line(idea['title'])} ({verdict}{total})")
    return "\n".join(lines) + "\n"


def score_table(score: dict, rubric: dict) -> list[str]:
    lines = ["| Criterion | Weight | Score | Points | Reason |", "|---|---|---|---|---|"]
    for key, label in CRITERIA:
        c = score["criteria"][key]
        weight = rubric["weights"][key]
        points = weight * c["score"] / rubric["max_score"]
        lines.append(f"| {label} | {weight} | {c['score']} | {points:g} | {one_line(c['reason'])} |")
    lines.append(f"| **Total** | 100 | | **{fmt_total(score['total'])}** | lens: {score['lens']} |")
    return lines


def sources_line(idea: dict, briefs: dict) -> str:
    parts = []
    for sid in idea["source_ids"]:
        b = briefs[sid]
        parts.append(f"[{one_line(b['title'])}]({b['url']})")
    return ", ".join(parts)


def render_digest(week: str, data: dict, selected: dict | None, rubric: dict) -> str:
    briefs = {b["id"]: b for b in data["briefs"]["briefs"]}
    ideas = data["ideas"]["ideas"]
    scores = {s["idea_id"]: s for s in data["scores"]["scores"]}
    killed = [i for i in ideas if i["originality"]["verdict"] == "killed"]
    threshold = rubric["shortlist"]["threshold"]
    short = data["shortlist"]

    lines = [f"# idea-radar digest, {week}", ""]
    n_items = len(selected["items"]) if selected else len(briefs) + len(data["briefs"].get("skipped", []))
    lines.append(
        f"{n_items} selected items, {len(briefs)} briefs, {len(ideas)} ideas, "
        f"{len(killed)} killed by the originality gate. Shortlist threshold: {threshold}."
    )
    lines += ["", "## Shortlist", ""]
    if not short:
        lines += [f"No idea reached {threshold} this week.", ""]
    for rank, entry in enumerate(short, 1):
        idea, score = entry["idea"], entry["score"]
        orig = idea["originality"]
        lines += [f"### {rank}. {one_line(idea['title'])} ({fmt_total(score['total'])})", ""]
        lines += [one_line(idea["one_liner"]), ""]
        lines.append(f"- **Idea id:** {idea['idea_id']}")
        lines.append(f"- **Target user:** {one_line(idea['target_user'])}")
        lines.append(f"- **Move {idea['move']}** ({MOVES[idea['move']]}) from {sources_line(idea, briefs)}")
        verdict = f"- **Originality:** {orig['verdict']}"
        if orig["verdict"] == "differentiated":
            verdict += f". {one_line(orig['differentiator'])}"
        lines.append(verdict)
        lines.append(f"- **Searched:** GitHub {quoted(orig['searches']['github'])}; web {quoted(orig['searches']['web'])}")
        lines.append("- **Evidence:** " + ", ".join(orig["evidence_urls"]))
        lines.append(f"- **Smallest version:** {one_line(idea['smallest_version'])}")
        lines.append(f"- **Demo:** {one_line(idea['demo'])}")
        lines.append(f"- **Verifiable by:** {one_line(idea['verifiable_by'])}")
        lines.append(f"- **Rahul's edge:** {one_line(idea['rahul_edge']) or 'none'}")
        lines += [""] + score_table(score, rubric) + [""]

    short_ids = {e["idea"]["idea_id"] for e in short}
    dropped = dropped_ids(data, rubric)
    rest = [
        i
        for i in ideas
        if i["idea_id"] not in short_ids | dropped and i["originality"]["verdict"] != "killed"
    ]
    rest.sort(key=lambda i: (-scores[i["idea_id"]]["total"], i["idea_id"]))
    lines += ["## Other ideas", ""]
    if rest:
        lines += ["| Idea | Title | Total | Lens | Originality |", "|---|---|---|---|---|"]
        for idea in rest:
            s = scores[idea["idea_id"]]
            lines.append(
                f"| {idea['idea_id']} | {one_line(idea['title'])} | {fmt_total(s['total'])} "
                f"| {s['lens']} | {idea['originality']['verdict']} |"
            )
    else:
        lines.append("None.")
    lines += ["", "## Killed", ""]
    if killed:
        for idea in killed:
            orig = idea["originality"]
            lines.append(f"- {idea['idea_id']} {one_line(idea['title'])}: {one_line(orig['kill_reason'])} ({key_evidence(orig)})")
    else:
        lines.append("None.")
    if dropped:
        lines += ["", "## Dropped (outside the lens)", ""]
        for idea in ideas:
            if idea["idea_id"] in dropped:
                lines.append(f"- {idea['idea_id']} {one_line(idea['title'])}: {one_line(scores[idea['idea_id']]['criteria']['lens_fit']['reason'])}")
    lines += ["", "## Briefs", ""]
    for brief in data["briefs"]["briefs"]:
        lines.append(f"- [{one_line(brief['title'])}]({brief['url']}): {one_line(brief['mechanism'])}")
    skipped = data["briefs"].get("skipped", [])
    if skipped:
        lines += ["", "## Skipped items", ""]
        lines += [f"- {s['id']}: {one_line(s['reason'])}" for s in skipped]
    return "\n".join(lines) + "\n"


def render_archive(week: str, data: dict, rubric: dict) -> str:
    """Killed and dropped ideas, one line each on why."""
    scores = {s["idea_id"]: s for s in data["scores"]["scores"]}
    dropped = dropped_ids(data, rubric)
    lines = [f"# Killed and dropped ideas, {week}", ""]
    for idea in data["ideas"]["ideas"]:
        orig = idea["originality"]
        if orig["verdict"] == "killed":
            lines.append(
                f"- {idea['idea_id']} {one_line(idea['title'])}: killed. {one_line(orig['kill_reason'])} "
                f"Evidence: {', '.join(orig['evidence_urls'])}"
            )
        elif idea["idea_id"] in dropped:
            reason = one_line(scores[idea["idea_id"]]["criteria"]["lens_fit"]["reason"])
            lines.append(f"- {idea['idea_id']} {one_line(idea['title'])}: dropped, outside the lens. {reason}")
    if len(lines) == 2:
        lines.append("None.")
    return "\n".join(lines) + "\n"


# Sheet rows


def backlog_rows(week: str, data: dict, rubric: dict) -> list[list]:
    """One row per surviving idea, in SPEC 13.1 column order.

    Killed and dropped ideas go to the archive instead.
    """
    dropped = dropped_ids(data, rubric)
    briefs = {b["id"]: b for b in data["briefs"]["briefs"]}
    scores = {s["idea_id"]: s for s in data["scores"]["scores"]}
    short_ids = {e["idea"]["idea_id"] for e in data["shortlist"]}
    rows = []
    for idea in data["ideas"]["ideas"]:
        orig = idea["originality"]
        if orig["verdict"] == "killed" or idea["idea_id"] in dropped:
            continue
        s = scores[idea["idea_id"]]
        c = s["criteria"]
        row = {
            "week": week,
            "idea_id": idea["idea_id"],
            "title": one_line(idea["title"]),
            "one_liner": one_line(idea["one_liner"]),
            "target_user": one_line(idea["target_user"]),
            "move": idea["move"],
            "source_urls": JOIN.join(briefs[sid]["url"] for sid in idea["source_ids"]),
            "originality": orig["verdict"],
            "differentiator": one_line(orig["differentiator"]),
            "evidence_urls": JOIN.join(orig["evidence_urls"]),
            "lens": c["lens_fit"]["score"],
            "edge": c["rahul_edge"]["score"],
            "build": c["build_size"]["score"],
            "demo": c["demo"]["score"],
            "verifiable": c["verifiable"]["score"],
            "distribution": c["distribution"]["score"],
            "total": s["total"],
            "status": "shortlisted" if idea["idea_id"] in short_ids else "new",
            "picked_on": "",
            "repo_url": "",
            "shipped_on": "",
            "stars_7d": "",
            "stars_30d": "",
            "notes": f"lens: {s['lens']}",
        }
        rows.append([sheet_cell(row[col]) for col in BACKLOG_COLUMNS])
    total, idea_id = BACKLOG_COLUMNS.index("total"), BACKLOG_COLUMNS.index("idea_id")
    rows.sort(key=lambda r: (-r[total], r[idea_id]))
    return rows


def scan_rows(selected: dict) -> list[list]:
    rows = [SCAN_COLUMNS]
    for item in selected["items"]:
        row = {**item, "week": selected["week"], "topics": ", ".join(item.get("topics", []))}
        cells = ["" if row.get(col) is None else row[col] for col in SCAN_COLUMNS]
        rows.append([sheet_cell(clean(c)) if isinstance(c, str) else c for c in cells])
    return rows


def render_run(run_dir: Path, selected: dict | None, rubric: dict, out: Path) -> list[str]:
    """Validate, then write every output file. Returns the errors (empty on success)."""
    errors, data = validate_run(run_dir, selected, rubric)
    if errors:
        return errors
    week = data["briefs"]["week"]
    items = {i["id"]: i for i in selected["items"]} if selected else {}
    scores = {s["idea_id"]: s for s in data["scores"]["scores"]}
    ideas = data["ideas"]["ideas"]

    files: dict[str, str] = {}
    for brief in data["briefs"]["briefs"]:
        name, n = slug(brief), 1
        while f"briefs/{name}.md" in files:  # distinct ids can share a slug
            n += 1
            name = f"{slug(brief)}-{n}"
        files[f"briefs/{name}.md"] = render_brief(brief, items.get(brief["id"]), ideas, scores)
    files["_digest.md"] = render_digest(week, data, selected, rubric)
    files["archive.md"] = render_archive(week, data, rubric)
    files["backlog_rows.json"] = json.dumps(backlog_rows(week, data, rubric), indent=2, ensure_ascii=False) + "\n"
    if selected:
        files["scan_rows.json"] = json.dumps(scan_rows(selected), indent=2, ensure_ascii=False) + "\n"

    leaked = [name for name, text in files.items() if DASHES.search(text)]
    if leaked:
        return [f"{name}: rendered text contains an en or em dash" for name in leaked]
    # Clear what an earlier render wrote, so a brief that has since been
    # dropped or renamed is not uploaded again.
    shutil.rmtree(out / "briefs", ignore_errors=True)
    for name, text in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--selected", type=Path, help="the week's .selected.json (default: from the week)")
    parser.add_argument("--rubric", type=Path, default=RUBRIC)
    parser.add_argument("--no-selected", action="store_true", help="skip the check against the selected items")
    parser.add_argument("--out", type=Path, help="output directory (default: <run_dir>/drive)")
    args = parser.parse_args(argv)

    selected, problem = resolve_selected(args.run_dir, args.selected, args.no_selected)
    if problem:
        print(f"FAILED: {problem}; nothing written", file=sys.stderr)
        return 1
    out = args.out or args.run_dir / "drive"
    errors = render_run(args.run_dir, selected, load_rubric(args.rubric), out)
    if errors:
        print(f"FAILED: {len(errors)} error(s); nothing written", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
