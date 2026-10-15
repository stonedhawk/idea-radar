#!/usr/bin/env python3
"""Pick this week's 20 items from a scan (SPEC section 7).

Usage: GITHUB_TOKEN=... python scripts/select.py --week 2026-W42

Reads data/scans/<week>.json and writes data/scans/<week>.selected.json.
README checks hit the GitHub API, but only for repos about to be picked.
The scan is checked against schemas/scan.json before it is read and the
output against schemas/selected.json before it is written; on a failed
check or request nothing is written and the exit code is 1.
"""
from __future__ import annotations

import os
import sys

# This file is named select.py, which shadows the stdlib "select" module
# (socket imports it) while this directory is on the import path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from collections import Counter  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Callable  # noqa: E402

import yaml  # noqa: E402

from collectors import github  # noqa: E402
from collectors.common import FetchError  # noqa: E402
from scripts.contracts import ContractError, load, require  # noqa: E402

ROOT = Path(_ROOT)


def previous_weeks(week: str, n: int) -> list[str]:
    """The n ISO weeks before week, most recent first."""
    year, num = week.split("-W")
    monday = date.fromisocalendar(int(year), int(num), 1)
    weeks = []
    for k in range(1, n + 1):
        y, w, _ = (monday - timedelta(weeks=k)).isocalendar()
        weeks.append(f"{y}-W{w:02d}")
    return weeks


def recently_selected(scans_dir: Path, week: str, n: int) -> set[tuple[str, str]]:
    """(source, id) of every item selected in the n weeks before week."""
    seen: set[tuple[str, str]] = set()
    for prev in previous_weeks(week, n):
        path = scans_dir / f"{prev}.selected.json"
        if path.exists():
            for item in json.loads(path.read_text())["items"]:
                seen.add((item["source"], item["id"]))
    return seen


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w]


def matches_term(text: str, term: str) -> bool:
    """True if term appears in text as whole words; the last may take an "s".

    "awesome-mcp" matches "awesome"; "playlist-sync" does not match "list";
    "prompt-tutorials" matches "tutorial"; "Cheat Sheet" matches "cheat-sheet".
    """
    words, needle = _words(text), _words(term)
    if not needle:
        return False
    head, last = needle[:-1], needle[-1]
    for i in range(len(words) - len(needle) + 1):
        window = words[i : i + len(needle)]
        if window[:-1] == head and window[-1] in (last, last + "s"):
            return True
    return False


def exclusion_reason(item: dict, cfg: dict) -> str | None:
    """Why a scan item can never be selected, or None. README is checked later."""
    source = item["source"]
    if source == "github":
        if item.get("fork"):
            return "fork"
        if item.get("archived"):
            return "archived"
        fields = [item["title"], *item["topics"]]
        terms = cfg["terms"]
    elif source == "hf_space":
        fields = [item["id"], item["title"]]
        terms = [*cfg["terms"], *cfg["hf_terms"]]
    else:
        return None
    if any(matches_term(field, term) for field in fields for term in terms):
        return "excluded_term"
    return None


def rank_key(item: dict) -> tuple:
    """Highest traction first; on a tie, measured velocity beats estimated."""
    measured = item["traction_kind"] == "velocity_7d_measured"
    return (-item["traction"], 0 if measured else 1, item["id"])


def select_items(
    items: list[dict],
    cfg: dict,
    *,
    recent: set[tuple[str, str]],
    has_readme: Callable[[str], bool],
) -> tuple[list[dict], dict[str, int]]:
    """Return (selected items in quota order, skip counts by reason).

    Non-GitHub sources fill first; any quota they cannot fill goes to GitHub.
    """
    quotas: dict[str, int] = cfg["select"]["quotas"]
    cap: int = cfg["select"]["diversity_cap"]
    skipped: Counter = Counter()

    pools: dict[str, list[dict]] = {source: [] for source in quotas}
    for item in items:
        if item["source"] not in pools:
            continue
        reason = exclusion_reason(item, cfg["exclude"])
        if reason is None and (item["source"], item["id"]) in recent:
            reason = "recent"
        if reason:
            skipped[reason] += 1
            continue
        pools[item["source"]].append(item)
    for pool in pools.values():
        pool.sort(key=rank_key)

    per_topic: Counter = Counter()

    def fill(source: str, n: int) -> list[dict]:
        picked: list[dict] = []
        for item in pools[source]:
            if len(picked) >= n:
                break
            topic = item.get("primary_topic")
            if topic and per_topic[topic] >= cap:
                skipped["diversity_cap"] += 1
                continue
            if source == "github" and not has_readme(item["id"]):
                skipped["no_readme"] += 1
                continue
            picked.append(item)
            if topic:
                per_topic[topic] += 1
        return picked

    chosen: dict[str, list[dict]] = {}
    shortfall = 0
    for source, quota in quotas.items():
        if source != "github":
            chosen[source] = fill(source, quota)
            shortfall += quota - len(chosen[source])
    chosen["github"] = fill("github", quotas.get("github", 0) + shortfall)

    selected = [item for source in quotas for item in chosen[source]]
    return selected, dict(sorted(skipped.items()))


def run(
    cfg: dict,
    *,
    week: str,
    data_dir: Path,
    has_readme: Callable[[str], bool],
    now: datetime | None = None,
) -> dict:
    """Select from data/scans/<week>.json and write <week>.selected.json.

    Raises ContractError, before writing anything, if the scan or the output
    does not meet its schema.
    """
    scans_dir = data_dir / "scans"
    scan_path = scans_dir / f"{week}.json"
    if not scan_path.exists():
        raise ContractError([f"{scan_path}: missing; run scripts/scan.py first"])
    scan = load(scan_path, "scan")
    if scan["week"] != week:
        raise ContractError([f"{scan_path.name}/week: {scan['week']} is not {week}"])

    selected, skipped = select_items(
        scan["items"],
        cfg,
        recent=recently_selected(scans_dir, week, cfg["select"]["repeat_weeks"]),
        has_readme=has_readme,
    )
    now = now or datetime.now(timezone.utc)
    out = {
        "week": week,
        "generated_at": now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "scan": scan_path.name,
        "quotas": cfg["select"]["quotas"],
        "skipped": skipped,
        "items": selected,
    }
    out_path = scans_dir / f"{week}.selected.json"
    require(out, "selected", out_path.name)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week", required=True, help="ISO week, e.g. 2026-W42")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "sources.yaml")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        parser.error("set GITHUB_TOKEN; it is needed for README checks")

    cfg = yaml.safe_load(args.config.read_text())
    try:
        out = run(cfg, week=args.week, data_dir=args.data_dir, has_readme=github.readme_checker(token))
    except (ContractError, FetchError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [str(exc)]
        print(f"FAILED: {len(errors)} error(s); nothing written", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    counts = Counter(item["source"] for item in out["items"])
    print(f"selected {args.week}: {len(out['items'])} items {dict(counts)}; skipped {out['skipped']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
