#!/usr/bin/env python3
"""List shipped ideas that are due a 7-day or 30-day star check (SPEC 12).

Usage: python scripts/track.py backlog.json [--today 2026-10-19] [--json]

backlog.json is the backlog sheet's values, header row first, as the Sheets
connector returns them (a list of lists), or a list of objects keyed by the
SPEC 13.1 column names. A check is due once the ship date is at least 7 or 30
days back and that row's stars_7d or stars_30d cell is still empty, so a
missed weekly run is caught up on the next one. Exit code 1 if any shipped
row cannot be checked (no repo_url, bad shipped_on).
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
from datetime import date, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

from scripts.render import BACKLOG_COLUMNS  # noqa: E402

CHECKS = {7: "stars_7d", 30: "stars_30d"}


def slugify(title: str) -> str:
    """Folder name under 04_Specs, 05_Audit and 06_Shipped (SPEC 13)."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def as_dicts(rows: list) -> list[dict]:
    """Sheet values (header row first) or dicts, as dicts with every column.

    The Sheets API drops trailing empty cells, so short rows are padded.
    """
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [{col: row.get(col, "") for col in BACKLOG_COLUMNS} for row in rows]
    header = [str(c).strip() for c in rows[0]]
    missing = [c for c in BACKLOG_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"backlog header is missing column(s): {', '.join(missing)}")
    out = []
    for row in rows[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        cells = list(row) + [""] * (len(header) - len(row))
        out.append({col: cells[header.index(col)] for col in BACKLOG_COLUMNS})
    return out


def blank(value) -> bool:
    return value is None or str(value).strip() == ""


def due_checks(rows: list, today: date) -> tuple[list[dict], list[str]]:
    """The star checks due today, oldest due date first, and any row errors."""
    due, errors = [], []
    for row in as_dicts(rows):
        if str(row["status"]).strip().lower() != "shipped":
            continue
        label = f"{row['idea_id'] or '?'} {row['title']}".strip()
        try:
            shipped_on = date.fromisoformat(str(row["shipped_on"]).strip())
        except ValueError:
            errors.append(f"{label}: shipped_on {row['shipped_on']!r} is not a YYYY-MM-DD date")
            continue
        if shipped_on > today:
            errors.append(f"{label}: shipped_on {shipped_on} is after today {today}")
            continue
        if blank(row["repo_url"]):
            errors.append(f"{label}: shipped with no repo_url")
            continue
        age = (today - shipped_on).days
        for days, column in CHECKS.items():
            if age < days or not blank(row[column]):
                continue
            due_on = shipped_on + timedelta(days=days)
            due.append(
                {
                    "idea_id": row["idea_id"],
                    "title": row["title"],
                    "slug": slugify(row["title"]),
                    "repo_url": str(row["repo_url"]).strip(),
                    "shipped_on": shipped_on.isoformat(),
                    "check": days,
                    "column": column,
                    "due_on": due_on.isoformat(),
                    "days_since_ship": age,
                    "late_by": (today - due_on).days,
                }
            )
    due.sort(key=lambda d: (d["due_on"], d["idea_id"], d["check"]))
    return due, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backlog", type=Path, help="backlog sheet values as JSON")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD (default: today)")
    parser.add_argument("--json", action="store_true", help="print the due checks as JSON")
    args = parser.parse_args(argv)

    due, errors = due_checks(json.loads(args.backlog.read_text()), args.today)
    for err in errors:
        print(f"error: {err}", file=sys.stderr)
    if args.json:
        print(json.dumps(due, indent=2, ensure_ascii=False))
    elif not due:
        print("no star checks due")
    else:
        for d in due:
            late = f", {d['late_by']} day(s) late" if d["late_by"] else ""
            print(
                f"{d['check']}d  {d['idea_id']}  {d['title']}  {d['repo_url']}  "
                f"-> 06_Shipped/{d['slug']}/results.md, {d['column']} (due {d['due_on']}{late})"
            )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
