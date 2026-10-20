#!/usr/bin/env python3
"""Validate a week's LLM output files against the schemas and rubric (SPEC 8).

Usage: python scripts/validate.py runs/2026-W42 [--selected PATH | --no-selected] [--json]

The run directory holds briefs.json, ideas.json and scores.json. --selected
defaults to data/scans/<week>.selected.json and must exist unless
--no-selected is given, and must meet schemas/selected.json. Every error is
printed and the exit code is 1; on success the shortlist is printed and the exit code is 0.
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
from collections import Counter  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

from scripts.contracts import ContractError  # noqa: E402
from scripts.contracts import load as load_contract  # noqa: E402

ROOT = Path(_ROOT)
SCHEMAS = ROOT / "schemas"
RUBRIC = ROOT / "config" / "rubric.yaml"
WEEK_RE = re.compile(r"^[0-9]{4}-W[0-9]{2}$")
DASHES = re.compile("[\u2013\u2014]")  # en and em dash (audit check 9)
TOTAL_TOLERANCE = 0.01

# Brief fields copied verbatim from the source, so exempt from the dash rule.
COPIED_FIELDS = {"title", "url", "evidence"}

# Repo names made only of these words describe a pattern, not a product, so a
# mechanism may use them (a repo called "browser-agent" does not ban "agent").
GENERIC_WORDS = {
    "agent", "agents", "ai", "app", "apps", "bench", "bot", "bots", "browser", "chat",
    "cli", "code", "coding", "data", "dev", "eval", "evals", "game", "games", "kit", "llm",
    "llms", "mcp", "prompt", "prompts", "rag", "server", "skill", "skills", "tool", "tools",
    "web",
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.json").read_text())


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


def load_rubric(path: Path = RUBRIC) -> dict:
    return yaml.safe_load(path.read_text())


# Rubric maths


def compute_total(criteria: dict, rubric: dict) -> float:
    """Sum of weight x score / max_score, out of 100."""
    weights = rubric["weights"]
    raw = sum(weights[name] * criteria[name]["score"] for name in weights)
    return round(raw / rubric["max_score"], 2)


def lens_cap(lens: str, rubric: dict) -> float:
    """The highest total an idea in this lens can reach."""
    top = rubric["max_score"]
    best = {name: {"score": top} for name in rubric["weights"]}
    best["lens_fit"] = {"score": rubric["lens"][lens]}
    return compute_total(best, rubric)


# Checks. Each returns a list of error strings prefixed with where they are.


def schema_errors(instance, name: str, where: str) -> list[str]:
    errors = sorted(validator_for(name).iter_errors(instance), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path)
        out.append(f"{where}{'/' + path if path else ''}: {err.message}")
    return out


def dash_errors(obj, where: str, skip: frozenset = frozenset()) -> list[str]:
    """En or em dashes anywhere in the strings of obj."""
    out = []
    if isinstance(obj, str):
        if DASHES.search(obj):
            out.append(f"{where}: contains an en or em dash")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key not in skip:
                out += dash_errors(value, f"{where}/{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            out += dash_errors(value, f"{where}/{i}")
    return out


def product_name(brief: dict) -> str | None:
    """The repo or space name a mechanism must not mention.

    None for Show HN posts, for names under 4 characters, and for names made
    only of generic words.
    """
    if brief["source"] not in ("github", "hf_space"):
        return None
    name = brief["id"].split("/")[-1]
    words = [w for w in re.split(r"[-_. ]+", name.lower()) if w]
    if len(name) < 4 or all(w in GENERIC_WORDS for w in words):
        return None
    return name


def names_product(mechanism: str, name: str) -> bool:
    """True if the name appears as whole words, with or without its separators."""
    text = mechanism.lower()
    for form in {name.lower(), re.sub(r"[-_.]+", " ", name.lower())}:
        if re.search(rf"(?<![a-z0-9]){re.escape(form)}(?![a-z0-9])", text):
            return True
    return False


def envelope_errors(doc, key: str, where: str) -> list[str]:
    if not isinstance(doc, dict):
        return [f"{where}: top level must be an object"]
    errors = []
    if not isinstance(doc.get("week"), str) or not WEEK_RE.match(doc["week"]):
        errors.append(f"{where}/week: must be an ISO week like 2026-W42")
    if not isinstance(doc.get(key), list):
        errors.append(f"{where}/{key}: must be a list")
    return errors


def check_briefs(doc: dict, selected: dict | None = None) -> list[str]:
    where = "briefs.json"
    errors = envelope_errors(doc, "briefs", where)
    if errors:
        return errors
    seen: Counter = Counter()
    for i, brief in enumerate(doc["briefs"]):
        at = f"{where}/briefs/{i}"
        found = schema_errors(brief, "brief", at)
        errors += found
        if found:
            continue
        seen[brief["id"]] += 1
        errors += dash_errors(brief, at, skip=COPIED_FIELDS)
        name = product_name(brief)
        if name and names_product(brief["mechanism"], name):
            errors.append(f"{at}/mechanism: names the product '{name}'; state the pattern instead")
    errors += [f"{where}: brief id {k} appears {n} times" for k, n in seen.items() if n > 1]

    skipped = doc.get("skipped", [])
    skipped_ids = set()
    if not isinstance(skipped, list):
        errors.append(f"{where}/skipped: must be a list")
        skipped = []
    for i, entry in enumerate(skipped):
        at = f"{where}/skipped/{i}"
        if not (isinstance(entry, dict) and entry.get("id") and str(entry.get("reason", "")).strip()):
            errors.append(f"{at}: needs an id and a reason")
            continue
        skipped_ids.add(entry["id"])
        errors += dash_errors(entry["reason"], f"{at}/reason")

    if selected is not None:
        if selected.get("week") != doc["week"]:
            errors.append(f"{where}/week: {doc['week']} does not match the selected file's {selected.get('week')}")
        items = {item["id"]: item for item in selected["items"]}
        for i, brief in enumerate(doc["briefs"]):
            if not isinstance(brief, dict):
                continue  # already reported by the schema check
            item = items.get(brief.get("id"))
            if item is None:
                errors.append(f"{where}/briefs/{i}: id {brief.get('id')} is not in the selected items")
            elif brief.get("url") != item["url"] or brief.get("source") != item["source"]:
                errors.append(f"{where}/briefs/{i}: source or url differs from the selected item")
        for item_id in items:
            if item_id not in seen and item_id not in skipped_ids:
                errors.append(f"{where}: selected item {item_id} has no brief and is not listed as skipped")
        for item_id in skipped_ids:
            if item_id not in items:
                errors.append(f"{where}: skipped id {item_id} is not in the selected items")
            if item_id in seen:
                errors.append(f"{where}: {item_id} is both briefed and skipped")
    return errors


def check_ideas(doc: dict, brief_ids: set[str], rubric: dict) -> list[str]:
    where = "ideas.json"
    errors = envelope_errors(doc, "ideas", where)
    if errors:
        return errors
    limits = rubric["brainstorm"]
    ids: Counter = Counter()
    per_brief: Counter = Counter()
    for i, idea in enumerate(doc["ideas"]):
        at = f"{where}/ideas/{i}"
        found = schema_errors(idea, "idea", at)
        errors += found
        if found:
            continue
        errors += dash_errors(idea, at)
        ids[idea["idea_id"]] += 1
        if not idea["idea_id"].startswith(doc["week"] + "-"):
            errors.append(f"{at}/idea_id: must start with {doc['week']}-")
        unknown = [s for s in idea["source_ids"] if s not in brief_ids]
        if unknown:
            errors.append(f"{at}/source_ids: no brief for {', '.join(unknown)}")
        per_brief[idea["source_ids"][0]] += 1
    errors += [f"{where}: idea_id {k} appears {n} times" for k, n in ids.items() if n > 1]
    if len(doc["ideas"]) > limits["max_per_week"]:
        errors.append(f"{where}: {len(doc['ideas'])} ideas; at most {limits['max_per_week']} per week")
    for source_id, n in per_brief.items():
        if n > limits["max_per_brief"]:
            errors.append(f"{where}: {n} ideas from brief {source_id}; at most {limits['max_per_brief']}")
    return errors


def check_score(score: dict, rubric: dict, at: str) -> list[str]:
    """Rubric rules for one schema-valid score."""
    errors = []
    lens = score["lens"]
    criteria = score["criteria"]
    expected_lens = rubric["lens"][lens]
    if criteria["lens_fit"]["score"] != expected_lens:
        errors.append(f"{at}/criteria/lens_fit/score: lens {lens} scores {expected_lens}")
    if criteria["build_size"]["score"] not in rubric["build_size_scores"]:
        errors.append(f"{at}/criteria/build_size/score: must be one of {rubric['build_size_scores']}")
    total = compute_total(criteria, rubric)
    if abs(score["total"] - total) > TOTAL_TOLERANCE:
        errors.append(f"{at}/total: {score['total']:g} but the criteria give {total:g}")
    if lens in rubric["lens_caps"] and score["total"] > rubric["lens_caps"][lens] + TOTAL_TOLERANCE:
        errors.append(f"{at}/total: {score['total']} is above the {lens} cap of {rubric['lens_caps'][lens]:g}")
    return errors


def check_scores(doc: dict, ideas: list[dict], rubric: dict) -> list[str]:
    where = "scores.json"
    errors = envelope_errors(doc, "scores", where)
    if errors:
        return errors
    verdicts = {
        idea["idea_id"]: (idea.get("originality") or {}).get("verdict")
        for idea in ideas
        if isinstance(idea, dict) and "idea_id" in idea
    }
    scored: Counter = Counter()
    for i, score in enumerate(doc["scores"]):
        at = f"{where}/scores/{i}"
        found = schema_errors(score, "score", at)
        errors += found
        if found:
            continue
        errors += dash_errors(score, at)
        idea_id = score["idea_id"]
        scored[idea_id] += 1
        if idea_id not in verdicts:
            errors.append(f"{at}/idea_id: no idea {idea_id}")
        elif verdicts[idea_id] == "killed":
            errors.append(f"{at}/idea_id: {idea_id} was killed by the originality gate; do not score it")
        errors += check_score(score, rubric, at)
    errors += [f"{where}: idea {k} is scored {n} times" for k, n in scored.items() if n > 1]
    for idea_id, verdict in verdicts.items():
        if verdict != "killed" and idea_id not in scored:
            errors.append(f"{where}: idea {idea_id} has no score")
    return errors


# Shortlist


def shortlist(ideas: list[dict], scores: list[dict], rubric: dict) -> list[dict]:
    """Ideas at or above the threshold, highest total first, capped at max_ideas.

    Killed ideas and dropped lenses never make it. Ties break on idea_id. The
    total is the one the criteria give, not the written one, which check_score
    lets differ by up to TOTAL_TOLERANCE.
    """
    by_id = {idea["idea_id"]: idea for idea in ideas}
    rule = rubric["shortlist"]
    total = {s["idea_id"]: compute_total(s["criteria"], rubric) for s in scores}
    eligible = [
        s
        for s in scores
        if s["idea_id"] in by_id
        and by_id[s["idea_id"]]["originality"]["verdict"] != "killed"
        and s["lens"] not in rubric["dropped_lenses"]
        and total[s["idea_id"]] >= rule["threshold"]
    ]
    eligible.sort(key=lambda s: (-total[s["idea_id"]], s["idea_id"]))
    return [{"idea": by_id[s["idea_id"]], "score": s} for s in eligible[: rule["max_ideas"]]]


# Run directory


def load_json(path: Path, errors: list[str]):
    if not path.exists():
        errors.append(f"{path.name}: missing")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: not valid JSON ({exc})")
        return None


def validate_run(run_dir: Path, selected: dict | None = None, rubric: dict | None = None):
    """Validate briefs.json, ideas.json and scores.json in run_dir.

    Returns (errors, data) where data holds the parsed files and the shortlist.
    In data, each score's total is the one its criteria give, so the shortlist,
    digest and backlog rows never use a written total that is slightly off.
    """
    rubric = rubric or load_rubric()
    errors: list[str] = []
    briefs = load_json(run_dir / "briefs.json", errors)
    ideas = load_json(run_dir / "ideas.json", errors)
    scores = load_json(run_dir / "scores.json", errors)
    if errors:
        return errors, None

    errors += check_briefs(briefs, selected)
    brief_list = briefs.get("briefs") if isinstance(briefs, dict) else None
    brief_ids = {b.get("id") for b in brief_list or [] if isinstance(b, dict)}
    errors += check_ideas(ideas, brief_ids, rubric)
    idea_list = ideas.get("ideas") if isinstance(ideas, dict) else None
    errors += check_scores(scores, idea_list if isinstance(idea_list, list) else [], rubric)
    weeks = {
        doc.get("week") for doc in (briefs, ideas, scores) if isinstance(doc, dict) and isinstance(doc.get("week"), str)
    }
    if len(weeks) > 1:
        errors.append(f"week differs across files: {sorted(map(str, weeks))}")
    if errors:
        return errors, None
    for score in scores["scores"]:
        score["total"] = compute_total(score["criteria"], rubric)
    data = {
        "briefs": briefs,
        "ideas": ideas,
        "scores": scores,
        "shortlist": shortlist(ideas["ideas"], scores["scores"], rubric),
    }
    return [], data


def default_selected(run_dir: Path) -> Path | None:
    """data/scans/<week>.selected.json for the week in briefs.json, whether or not it exists."""
    briefs = run_dir / "briefs.json"
    try:
        week = json.loads(briefs.read_text())["week"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(week, str) or not WEEK_RE.match(week):
        return None
    return ROOT / "data" / "scans" / f"{week}.selected.json"


def resolve_selected(run_dir: Path, given: Path | None, skip: bool) -> tuple[dict | None, str | None]:
    """Load the selected file, or say why it cannot be. Returns (selected, error)."""
    if skip:
        return None, None
    path = given or default_selected(run_dir)
    if path is None:
        return None, "cannot tell the week from briefs.json, so no selected file to check against"
    if not path.exists():
        return None, f"selected file {path} not found; pass --selected, or --no-selected to skip the check"
    try:
        return load_contract(path, "selected"), None
    except ContractError as exc:
        return None, f"selected file {path} does not meet schemas/selected.json: " + "; ".join(exc.errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="directory with briefs.json, ideas.json, scores.json")
    parser.add_argument("--selected", type=Path, help="the week's .selected.json (default: from the week)")
    parser.add_argument("--rubric", type=Path, default=RUBRIC)
    parser.add_argument("--no-selected", action="store_true", help="skip the check against the selected items")
    parser.add_argument("--json", action="store_true", help="print the shortlist as JSON")
    args = parser.parse_args(argv)

    selected, problem = resolve_selected(args.run_dir, args.selected, args.no_selected)
    if problem:
        print(f"FAILED: {problem}", file=sys.stderr)
        return 1
    errors, data = validate_run(args.run_dir, selected, load_rubric(args.rubric))
    if errors:
        print(f"FAILED: {len(errors)} error(s)", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data["shortlist"], indent=2, ensure_ascii=False))
        return 0
    ideas = data["ideas"]["ideas"]
    killed = sum(1 for i in ideas if i["originality"]["verdict"] == "killed")
    print(
        f"ok: {len(data['briefs']['briefs'])} briefs, {len(ideas)} ideas ({killed} killed), "
        f"{len(data['scores']['scores'])} scores"
        + ("" if selected else "; selected items not checked (--no-selected)")
    )
    if not data["shortlist"]:
        print("shortlist: none at or above the threshold")
    for entry in data["shortlist"]:
        idea, score = entry["idea"], entry["score"]
        print(f"  {score['total']:6.2f}  {idea['idea_id']}  {idea['title']}  ({idea['originality']['verdict']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
