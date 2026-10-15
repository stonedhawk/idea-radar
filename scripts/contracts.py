#!/usr/bin/env python3
"""Check the files the deterministic steps hand to each other (AGENTS.md, step contracts).

Usage: python scripts/contracts.py data/scans/2026-W42.json [more files] [--kind scan|selected]

A scan file (data/scans/<week>.json) must match schemas/scan.json, and a
selected file (data/scans/<week>.selected.json) schemas/selected.json; every
item in either must match schemas/scan_item.json. The kind comes from the file
name (selected.json or *.selected.json is a selected file) unless --kind is
given. Every error is printed and the exit code is 1.

scripts/scan.py and scripts/select.py call these checks before they write, and
scripts/validate.py and scripts/render.py before they read a selected file.
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
from collections import Counter  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

from jsonschema import Draft202012Validator  # noqa: E402

ROOT = Path(_ROOT)
SCHEMAS = ROOT / "schemas"
KINDS = ("scan", "selected")


class ContractError(ValueError):
    """A file does not meet its contract. errors holds every problem found."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / f"{name}.json").read_text()))


def schema_errors(instance, name: str, where: str) -> list[str]:
    errors = sorted(validator_for(name).iter_errors(instance), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path)
        out.append(f"{where}{'/' + path if path else ''}: {err.message}")
    return out


def item_errors(items: list, where: str) -> list[str]:
    errors = []
    seen: Counter = Counter()
    for i, item in enumerate(items):
        found = schema_errors(item, "scan_item", f"{where}/items/{i}")
        errors += found
        if not found:
            seen[(item["source"], item["id"])] += 1
    errors += [f"{where}: {s} item {k} appears {n} times" for (s, k), n in seen.items() if n > 1]
    return errors


def check_scan(doc, where: str = "scan") -> list[str]:
    """Errors in a scan file, empty if it meets schemas/scan.json."""
    errors = schema_errors(doc, "scan", where)
    if errors:
        return errors
    errors = item_errors(doc["items"], where)
    if errors:
        return errors
    actual = Counter(item["source"] for item in doc["items"])
    for source, n in doc["counts"].items():
        if actual[source] != n:
            errors.append(f"{where}/counts/{source}: says {n} but the file has {actual[source]} {source} items")
    return errors


def check_selected(doc, where: str = "selected") -> list[str]:
    """Errors in a selected file, empty if it meets schemas/selected.json."""
    errors = schema_errors(doc, "selected", where)
    if errors:
        return errors
    errors = item_errors(doc["items"], where)
    if doc["scan"] != f"{doc['week']}.json":
        errors.append(f"{where}/scan: {doc['scan']} is not the scan for {doc['week']}")
    unknown = sorted({item["source"] for item in doc["items"]} - set(doc["quotas"]))
    if unknown:
        errors.append(f"{where}/items: source(s) with no quota: {', '.join(unknown)}")
    return errors


CHECKS = {"scan": check_scan, "selected": check_selected}


def kind_of(path: Path) -> str:
    return "selected" if path.name == "selected.json" or path.name.endswith(".selected.json") else "scan"


def require(doc, kind: str, where: str) -> None:
    """Raise ContractError unless doc meets the contract for kind."""
    errors = CHECKS[kind](doc, where)
    if errors:
        raise ContractError(errors)


def load(path: Path, kind: str | None = None) -> dict:
    """Read and check a scan or selected file. Raises ContractError on any problem."""
    path = Path(path)
    kind = kind or kind_of(path)
    if not path.exists():
        raise ContractError([f"{path}: missing"])
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ContractError([f"{path}: not valid JSON ({exc})"]) from exc
    require(doc, kind, path.name)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", type=Path, nargs="+", help="scan or selected files")
    parser.add_argument("--kind", choices=KINDS, help="default: selected for *.selected.json, else scan")
    args = parser.parse_args(argv)

    failed = 0
    for path in args.paths:
        try:
            doc = load(path, args.kind)
        except ContractError as exc:
            failed += 1
            print(f"FAILED: {path}: {len(exc.errors)} error(s)", file=sys.stderr)
            for err in exc.errors:
                print(f"  {err}", file=sys.stderr)
            continue
        print(f"ok: {path} ({args.kind or kind_of(path)}, {len(doc['items'])} items)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
