#!/usr/bin/env python3
"""Run every collector and write data/scans/<week>.json (SPEC section 6).

Usage: GITHUB_TOKEN=... python scripts/scan.py [--week 2026-W42] [--allow-other-week]

Also appends this scan's GitHub star counts to data/stars.csv. Re-running a
week replaces that week's rows instead of adding duplicates. The APIs only
return today's data, so --week must be this ISO week (UTC): for any other
week the rows would carry today's date and replace that week's real
snapshots, which skews later velocity. --allow-other-week overrides this,
for a deliberate backfill only. The scan is
checked against schemas/scan.json before anything is written; on a failed
request or a failed check nothing is written and the exit code is 1.
"""
from __future__ import annotations

import os
import sys

# scripts/select.py would shadow the stdlib "select" module, which socket
# imports, so take this directory off the import path before anything loads.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from datetime import date, datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from collectors import github, hf, hn  # noqa: E402
from collectors.common import SOURCES, FetchError, get_json  # noqa: E402
from scripts.contracts import ContractError, require  # noqa: E402

ROOT = Path(_ROOT)
STARS_FIELDS = ("week", "date", "repo", "stars")


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def parse_day(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def read_star_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def star_history(rows: list[dict], *, exclude_week: str) -> dict[str, list[tuple[date, int]]]:
    """Snapshots per repo from earlier weeks, as (date, stars) pairs."""
    history: dict[str, list[tuple[date, int]]] = {}
    for row in rows:
        if row["week"] == exclude_week:
            continue
        history.setdefault(row["repo"], []).append((date.fromisoformat(row["date"]), int(row["stars"])))
    return history


def velocity_7d(
    stars_now: int,
    today: date,
    created_on: date,
    snapshots: list[tuple[date, int]],
    *,
    min_days: int,
    max_days: int,
) -> tuple[float, str]:
    """Stars gained per 7 days (SPEC 6.3).

    Measured from the snapshot closest to 7 days old, if one is min_days to
    max_days old. Otherwise estimated as lifetime stars over age.
    """
    in_window = [
        ((today - day).days, stars)
        for day, stars in snapshots
        if min_days <= (today - day).days <= max_days
    ]
    if in_window:
        days, stars_prev = min(in_window, key=lambda pair: (abs(pair[0] - 7), pair[0]))
        return (stars_now - stars_prev) / days * 7, "velocity_7d_measured"
    age_days = max((today - created_on).days, 1)
    return stars_now / age_days * 7, "velocity_7d_estimated"


def apply_velocity(items: list[dict], history: dict, today: date, cfg: dict) -> None:
    for item in items:
        if item["source"] != "github":
            continue
        value, kind = velocity_7d(
            item["stars"],
            today,
            parse_day(item["created_at"]),
            history.get(item["id"], []),
            min_days=cfg["min_days"],
            max_days=cfg["max_days"],
        )
        item["traction"] = round(value, 2)
        item["traction_kind"] = kind


def write_star_rows(path: Path, rows: list[dict], week: str, today: date, items: list[dict]) -> None:
    """Replace this week's rows with the current scan's GitHub star counts."""
    kept = [row for row in rows if row["week"] != week]
    fresh = sorted(
        (
            {"week": week, "date": today.isoformat(), "repo": item["id"], "stars": str(item["stars"])}
            for item in items
            if item["source"] == "github"
        ),
        key=lambda row: row["repo"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=STARS_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept + fresh)


def run(
    cfg: dict,
    *,
    week: str,
    now: datetime,
    data_dir: Path,
    token: str,
    fetch=get_json,
    sleep=time.sleep,
) -> dict:
    """Collect, score velocity, and write the scan file and star history."""
    today = now.date()
    fetched_at = now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    items = github.collect(cfg["github"], token=token, today=today, fetched_at=fetched_at, fetch=fetch, sleep=sleep)
    items += hn.collect(cfg["show_hn"], now_ts=int(now.timestamp()), fetched_at=fetched_at, fetch=fetch)
    items += hf.collect(cfg["hf_spaces"], fetched_at=fetched_at, fetch=fetch)

    stars_path = data_dir / "stars.csv"
    rows = read_star_rows(stars_path)
    apply_velocity(items, star_history(rows, exclude_week=week), today, cfg["velocity"])
    items.sort(key=lambda it: (SOURCES.index(it["source"]), -it["traction"], it["id"]))

    scan = {
        "week": week,
        "generated_at": fetched_at,
        "counts": {source: sum(1 for it in items if it["source"] == source) for source in SOURCES},
        "items": items,
    }
    out = data_dir / "scans" / f"{week}.json"
    require(scan, "scan", out.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scan, indent=2, ensure_ascii=False) + "\n")
    write_star_rows(stars_path, rows, week, today, items)
    return scan


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(timezone.utc)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week", default=iso_week(now.date()), help="ISO week, e.g. 2026-W42 (default: this week, UTC)")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "sources.yaml")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--allow-other-week",
        action="store_true",
        help="scan for a week other than this one; its star rows get today's date and replace that week's",
    )
    args = parser.parse_args(argv)

    this_week = iso_week(now.date())
    if args.week != this_week and not args.allow_other_week:
        parser.error(
            f"--week {args.week} is not this week ({this_week}); today's data would replace that week's "
            "star snapshots. Pass --allow-other-week to do it anyway"
        )

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        parser.error("set GITHUB_TOKEN; unauthenticated search allows only 10 requests per minute")

    try:
        scan = run(load_config(args.config), week=args.week, now=now, data_dir=args.data_dir, token=token)
    except (ContractError, FetchError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [str(exc)]
        print(f"FAILED: {len(errors)} error(s); nothing written", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    counts = ", ".join(f"{k} {v}" for k, v in scan["counts"].items())
    print(f"scan {args.week}: {len(scan['items'])} items ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
