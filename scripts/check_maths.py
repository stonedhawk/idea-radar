#!/usr/bin/env python3
"""Check the pipeline's maths against hand-worked examples (audit check 2).

Usage: python scripts/check_maths.py

Every expected value below was worked out by hand from SPEC 6.3 and 8.4 and
is written out in full next to its inputs; none of it is computed by the code
under test. The script runs the real functions on the same inputs and prints
one Markdown table per area (velocity, score totals, lens caps), in the shape
of the check 2 table in templates/AUDIT.template.md. Exit code 1 on any
mismatch.
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
from dataclasses import dataclass  # noqa: E402
from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from scripts.scan import velocity_7d  # noqa: E402
from scripts.validate import check_score, compute_total, lens_cap, load_rubric  # noqa: E402

ROOT = Path(_ROOT)
TOLERANCE = 0.01
TODAY = date(2026, 10, 15)
CRITERIA = ["lens_fit", "rahul_edge", "build_size", "demo", "verifiable", "distribution"]


@dataclass
class Row:
    example: str
    inputs: str
    expected: str
    output: str
    match: bool


# Velocity (SPEC 6.3). Today is 2026-10-15 and a snapshot counts when it is
# 5 to 10 days old. Each case: (name, stars_now, created_on, snapshots,
# expected value, expected flag, working).
VELOCITY = [
    (
        "measured, 7-day snapshot",
        700, date(2026, 1, 1), [(date(2026, 10, 8), 400)],
        300.0, "velocity_7d_measured",
        "(700 - 400) / 7 x 7 = 300",
    ),
    (
        "measured, 5-day edge",
        200, date(2026, 1, 1), [(date(2026, 10, 10), 100)],
        140.0, "velocity_7d_measured",
        "(200 - 100) / 5 x 7 = 140",
    ),
    (
        "measured, 10-day edge",
        250, date(2026, 1, 1), [(date(2026, 10, 5), 150)],
        70.0, "velocity_7d_measured",
        "(250 - 150) / 10 x 7 = 70",
    ),
    (
        "measured, closest to 7 days wins",
        590, date(2026, 1, 1), [(date(2026, 10, 9), 500), (date(2026, 10, 5), 400)],
        105.0, "velocity_7d_measured",
        "6-day snapshot beats 10-day: (590 - 500) / 6 x 7 = 105",
    ),
    (
        "estimated, no snapshot",
        600, date(2026, 9, 15), [],
        140.0, "velocity_7d_estimated",
        "30 days old: 600 / 30 x 7 = 140",
    ),
    (
        "estimated, snapshot 11 days old",
        300, date(2026, 8, 16), [(date(2026, 10, 4), 250)],
        35.0, "velocity_7d_estimated",
        "snapshot outside 5 to 10 days; 60 days old: 300 / 60 x 7 = 35",
    ),
    (
        "estimated, snapshot 4 days old",
        1000, date(2026, 7, 7), [(date(2026, 10, 11), 990)],
        70.0, "velocity_7d_estimated",
        "snapshot outside 5 to 10 days; 100 days old: 1000 / 100 x 7 = 70",
    ),
    (
        "estimated, created today",
        70, TODAY, [],
        490.0, "velocity_7d_estimated",
        "age floor of 1 day: 70 / 1 x 7 = 490",
    ),
]

# Score totals (SPEC 8.4): total = sum(weight x score) / 5. Weights are
# lens_fit 25, rahul_edge 20, build_size 15, demo 15, verifiable 15,
# distribution 10, so each point is worth 5, 4, 3, 3, 3 and 2.
TOTALS = [
    ("score.md example", "gaming_x_ai_pm", [5, 4, 4, 4, 5, 3], 86.0, "25 + 16 + 12 + 12 + 15 + 6 = 86"),
    ("gaming, below threshold", "gaming_only", [4, 3, 5, 2, 4, 1], 67.0, "20 + 12 + 15 + 6 + 12 + 2 = 67"),
    ("AI PM, perfect elsewhere", "ai_pm_only", [2, 5, 5, 5, 5, 5], 85.0, "10 + 20 + 15 + 15 + 15 + 10 = 85"),
    ("gaming, weak", "gaming_only", [4, 1, 2, 3, 3, 2], 52.0, "20 + 4 + 6 + 9 + 9 + 4 = 52"),
    ("neither, dropped", "neither", [0, 2, 0, 1, 2, 0], 17.0, "0 + 8 + 0 + 3 + 6 + 0 = 17"),
]

# Lens caps (SPEC 8.4): lens_fit fixed by the lens, every other criterion 5.
CAPS = [
    ("gaming_x_ai_pm", 100.0, "25 + 20 + 15 + 15 + 15 + 10 = 100"),
    ("gaming_only", 95.0, "20 + 20 + 15 + 15 + 15 + 10 = 95"),
    ("ai_pm_only", 85.0, "10 + 20 + 15 + 15 + 15 + 10 = 85"),
]


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


def check_velocity(window: dict) -> list[Row]:
    rows = []
    for name, now, created, snaps, want, want_kind, working in VELOCITY:
        got, kind = velocity_7d(
            now, TODAY, created, snaps, min_days=window["min_days"], max_days=window["max_days"]
        )
        snap_text = ", ".join(f"{d.isoformat()}: {s}" for d, s in snaps) or "none"
        rows.append(
            Row(
                name,
                f"{now} stars, created {created.isoformat()}, snapshots {snap_text}",
                f"{want:g} {want_kind.removeprefix('velocity_7d_')} ({working})",
                f"{got:g} {kind.removeprefix('velocity_7d_')}",
                close(got, want) and kind == want_kind,
            )
        )
    return rows


def criteria_for(scores: list[int]) -> dict:
    return {name: {"score": s, "reason": "worked example"} for name, s in zip(CRITERIA, scores)}


def check_totals(rubric: dict) -> list[Row]:
    rows = []
    for name, lens, scores, want, working in TOTALS:
        criteria = criteria_for(scores)
        got = compute_total(criteria, rubric)
        # The validator must accept the hand total and reject one point off it.
        accepts = not check_score({"lens": lens, "criteria": criteria, "total": want}, rubric, "x")
        rejects = bool(check_score({"lens": lens, "criteria": criteria, "total": want + 1}, rubric, "x"))
        rows.append(
            Row(
                name,
                f"{lens}, scores {scores}",
                f"{want:g} ({working})",
                f"{got:g}; validator accepts {want:g}: {accepts}, rejects {want + 1:g}: {rejects}",
                close(got, want) and accepts and rejects,
            )
        )
    return rows


def check_caps(rubric: dict) -> list[Row]:
    rows = []
    for lens, want, working in CAPS:
        got = lens_cap(lens, rubric)
        configured = rubric["lens_caps"][lens]
        # A total one point over the cap must fail validation even if the
        # criteria were somehow made to add up to it.
        over = {"lens": lens, "criteria": criteria_for([rubric["lens"][lens], 5, 5, 5, 5, 5]), "total": want + 1}
        rejects = any("cap" in e for e in check_score(over, rubric, "x"))
        rows.append(
            Row(
                lens,
                f"lens_fit {rubric['lens'][lens]}, every other criterion 5",
                f"{want:g} ({working})",
                f"lens_cap() {got:g}, rubric.yaml {configured:g}, rejects {want + 1:g}: {rejects}",
                close(got, want) and close(configured, want) and rejects,
            )
        )
    return rows


def table(title: str, rows: list[Row]) -> str:
    lines = [
        f"### {title}",
        "",
        "| Example | Input | Expected | Tool output | Match |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row.example} | {row.inputs} | {row.expected} | {row.output} | {'yes' if row.match else 'NO'} |")
    return "\n".join(lines)


def run(rubric: dict, window: dict) -> dict[str, list[Row]]:
    return {
        "Velocity (SPEC 6.3)": check_velocity(window),
        "Score totals (SPEC 8.4)": check_totals(rubric),
        "Lens caps (SPEC 8.4)": check_caps(rubric),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rubric", type=Path, default=ROOT / "config" / "rubric.yaml")
    parser.add_argument("--sources", type=Path, default=ROOT / "config" / "sources.yaml")
    args = parser.parse_args(argv)

    rubric = load_rubric(args.rubric)
    window = yaml.safe_load(args.sources.read_text())["velocity"]
    results = run(rubric, window)

    print("\n\n".join(table(title, rows) for title, rows in results.items()))
    failed = [row.example for rows in results.values() for row in rows if not row.match]
    total = sum(len(rows) for rows in results.values())
    print(f"\n{total - len(failed)} of {total} worked examples match.")
    if failed:
        print("Mismatch: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
