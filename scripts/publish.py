#!/usr/bin/env python3
"""Plan, or write locally, where a rendered week goes (SPEC 13, config/publish.yaml).

Usage: python scripts/publish.py runs/2026-W42 [--rendered DIR] [--local DIR] [--json]

Re-validates the run, checks that the rendered files in --rendered (default
<run_dir>/drive) are present, well formed and match the run, then prints the
plan: one step per file, with the action (upload, new_sheet_tab, append_rows)
and the destination under the Build Lab root. An agent with Google Drive and
Sheets tools carries the plan out with them.

With --local DIR, or IDEA_RADAR_PUBLISH_DIR set, it also writes the plan as
plain files under DIR: Markdown is copied, a sheet tab becomes <tab>.csv in a
folder named after the sheet, and appended rows go to the end of that CSV. A
destination that already exists stops the run before anything is written,
because it means the week was published before. Exit code 1 on any error.
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
import csv  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from scripts.render import BACKLOG_COLUMNS, SCAN_COLUMNS, backlog_rows  # noqa: E402
from scripts.validate import RUBRIC, load_rubric, validate_run  # noqa: E402

ROOT = Path(_ROOT)
CONFIG = ROOT / "config" / "publish.yaml"
ENV_DIR = "IDEA_RADAR_PUBLISH_DIR"
ACTIONS = ("upload", "new_sheet_tab", "append_rows")


def load_config(path: Path = CONFIG) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    bad = [o.get("action") for o in cfg.get("outputs", []) if o.get("action") not in ACTIONS]
    if not cfg.get("root") or not cfg.get("outputs") or bad:
        raise ValueError(f"{path}: needs root and outputs, each action one of {', '.join(ACTIONS)}")
    return cfg


def read_rows(path: Path, errors: list[str]) -> list | None:
    try:
        rows = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: not valid JSON ({exc})")
        return None
    if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        errors.append(f"{path.name}: must be a list of rows")
        return None
    return rows


def check_rows(name: str, rows: list, week: str, data: dict, rubric: dict) -> list[str]:
    """The sheet rows must have the SPEC 13.1 columns and match the validated run."""
    if name == "scan_rows.json":
        if not rows or rows[0] != SCAN_COLUMNS:
            return [f"{name}: first row must be the header {SCAN_COLUMNS}"]
        short = [i for i, r in enumerate(rows[1:], 1) if len(r) != len(SCAN_COLUMNS)]
        weeks = {r[0] for r in rows[1:] if r}
        errors = [f"{name}/{i}: has the wrong number of cells" for i in short]
        if weeks - {week}:
            errors.append(f"{name}: rows are for {sorted(weeks)}, not {week}")
        return errors
    if name == "backlog_rows.json":
        if rows != backlog_rows(week, data, rubric):
            return [f"{name}: does not match the run; re-run scripts/render.py"]
        return []
    return []


def plan(run_dir: Path, rendered: Path, cfg: dict, rubric: dict) -> tuple[list[dict], list[str]]:
    """The publish steps for a validated, rendered run, or the errors that stop it."""
    errors, data = validate_run(run_dir, None, rubric)
    if errors:
        return [], errors
    week = data["briefs"]["week"]
    root = cfg["root"]
    steps: list[dict] = []
    for out in cfg["outputs"]:
        dest = out["dest"].format(week=week)
        sources = sorted(rendered.glob(out["source"])) if "*" in out["source"] else [rendered / out["source"]]
        sources = [s for s in sources if s.is_file()]
        if not sources:
            errors.append(f"{rendered / out['source']}: missing; run scripts/render.py first")
            continue
        for src in sources:
            step = {"action": out["action"], "source": str(src)}
            if out["action"] == "upload":
                step["dest"] = f"{root}/{dest}{src.name}" if dest.endswith("/") else f"{root}/{dest}"
                step["mime_type"] = "text/markdown"
            else:
                rows = read_rows(src, errors)
                if rows is None:
                    continue
                errors += check_rows(src.name, rows, week, data, rubric)
                step["dest"] = f"{root}/{dest}"
                step["tab"] = out["tab"].format(week=week)
                step["rows"] = len(rows)
            steps.append(step)
    return (steps, []) if not errors else ([], errors)


def local_path(base: Path, step: dict) -> Path:
    if step["action"] == "upload":
        return base / step["dest"]
    return base / step["dest"] / f"{step['tab']}.csv"


def write_local(steps: list[dict], base: Path) -> list[str]:
    """Carry out the plan as plain files under base. Writes nothing on a conflict."""
    taken = [str(local_path(base, s)) for s in steps if s["action"] != "append_rows" and local_path(base, s).exists()]
    if taken:
        return [f"{p}: already exists; this week looks published already" for p in taken]
    for step in steps:
        path = local_path(base, step)
        path.parent.mkdir(parents=True, exist_ok=True)
        if step["action"] == "upload":
            shutil.copyfile(step["source"], path)
            continue
        rows = json.loads(Path(step["source"]).read_text())
        if step["action"] == "append_rows" and not path.exists():
            rows = [BACKLOG_COLUMNS, *rows]
        with path.open("a" if step["action"] == "append_rows" else "w", newline="") as fh:
            csv.writer(fh, lineterminator="\n").writerows(rows)
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--rendered", type=Path, help="render.py's output (default: <run_dir>/drive)")
    parser.add_argument("--local", type=Path, default=os.environ.get(ENV_DIR) or None,
                        help=f"write the plan under this folder (default: ${ENV_DIR}, else print only)")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--rubric", type=Path, default=RUBRIC)
    parser.add_argument("--json", action="store_true", help="print the plan as JSON")
    args = parser.parse_args(argv)

    steps, errors = plan(args.run_dir, args.rendered or args.run_dir / "drive",
                         load_config(args.config), load_rubric(args.rubric))
    if not errors and args.local:
        errors = write_local(steps, args.local)
    if errors:
        print(f"FAILED: {len(errors)} error(s); nothing published", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(steps, indent=2, ensure_ascii=False))
    else:
        for s in steps:
            extra = f" tab {s['tab']}, {s['rows']} rows" if "tab" in s else ""
            print(f"{s['action']:13s} {s['source']} -> {s['dest']}{extra}")
    if args.local:
        print(f"wrote {len(steps)} step(s) under {args.local}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
