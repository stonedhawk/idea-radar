"""scripts/scan.py end to end against fixtures, plus the CLI entry points."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import jsonschema
import pytest

from scripts.scan import iso_week, read_star_rows, run
from tests.conftest import FIXTURES, ROOT

NOW = datetime(2026, 10, 15, 1, 30, tzinfo=timezone.utc)
WEEK = "2026-W42"


@pytest.fixture
def scan_cfg(config):
    cfg = json.loads(json.dumps(config))
    cfg["github"]["topics"] = ["ai-agents", "mcp"]
    return cfg


@pytest.fixture
def data_dir(tmp_path):
    shutil.copy(FIXTURES / "stars.csv", tmp_path / "stars.csv")
    return tmp_path


def do_scan(cfg, data_dir, fetch):
    return run(cfg, week=WEEK, now=NOW, data_dir=data_dir, token="t", fetch=fetch, sleep=lambda s: None)


def test_iso_week():
    assert iso_week(NOW.date()) == "2026-W42"
    assert iso_week(datetime(2027, 1, 1).date()) == "2026-W53"


def test_scan_writes_schema_valid_items(scan_cfg, data_dir, fake_fetch, schema):
    scan = do_scan(scan_cfg, data_dir, fake_fetch)
    written = json.loads((data_dir / "scans" / f"{WEEK}.json").read_text())
    assert written == scan
    assert written["counts"] == {"github": 4, "show_hn": 2, "hf_space": 3}
    validator = jsonschema.Draft202012Validator(schema)
    for item in written["items"]:
        validator.validate(item)


def test_scan_applies_velocity(scan_cfg, data_dir, fake_fetch):
    items = {it["id"]: it for it in do_scan(scan_cfg, data_dir, fake_fetch)["items"]}
    # 400 stars on 2026-10-08 in stars.csv, 700 now.
    assert items["acme/agent-kit"]["traction"] == 300.0
    assert items["acme/agent-kit"]["traction_kind"] == "velocity_7d_measured"
    # Created 2026-10-15, no history: 70 stars over a 1-day floor.
    assert items["acme/brand-new"]["traction"] == 490.0
    assert items["acme/brand-new"]["traction_kind"] == "velocity_7d_estimated"


def test_scan_items_are_ordered_by_source_then_traction(scan_cfg, data_dir, fake_fetch):
    items = do_scan(scan_cfg, data_dir, fake_fetch)["items"]
    sources = [it["source"] for it in items]
    assert sources == sorted(sources, key=["github", "show_hn", "hf_space"].index)
    github = [it["traction"] for it in items if it["source"] == "github"]
    assert github == sorted(github, reverse=True)


def test_scan_appends_star_history_once_per_week(scan_cfg, data_dir, fake_fetch):
    do_scan(scan_cfg, data_dir, fake_fetch)
    do_scan(scan_cfg, data_dir, fake_fetch)
    rows = [r for r in read_star_rows(data_dir / "stars.csv") if r["week"] == WEEK]
    assert sorted(r["repo"] for r in rows) == [
        "acme/agent-kit",
        "acme/brand-new",
        "bigco/orchestrator",
        "someone/mcp-server-fork",
    ]
    assert {r["date"] for r in rows} == {"2026-10-15"}


def test_rerun_does_not_measure_against_its_own_week(scan_cfg, data_dir, fake_fetch):
    do_scan(scan_cfg, data_dir, fake_fetch)
    items = {it["id"]: it for it in do_scan(scan_cfg, data_dir, fake_fetch)["items"]}
    assert items["acme/agent-kit"]["traction"] == 300.0


@pytest.mark.parametrize("script", ["scan.py", "select.py"])
def test_scripts_run_directly_without_shadowing_stdlib_select(script):
    # Running scripts/select.py puts scripts/ on sys.path, where select.py
    # would replace the stdlib module that socket imports.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout


def test_select_cli_end_to_end(tmp_path):
    scans = tmp_path / "scans"
    scans.mkdir()
    shutil.copy(FIXTURES / "select_scan.json", scans / f"{WEEK}.json")
    # Every fixture repo has a README except acme/no-docs, but the CLI asks the
    # real API, so swap the checker in a wrapper instead of hitting the network.
    wrapper = tmp_path / "run_select.py"
    wrapper.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import collectors.github as gh\n"
        "gh.readme_checker = lambda token: (lambda name: name != 'acme/no-docs')\n"
        "from scripts import select\n"
        "sys.exit(select.main(sys.argv[1:]))\n"
    )
    result = subprocess.run(
        [sys.executable, str(wrapper), "--week", WEEK, "--data-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"GITHUB_TOKEN": "t", "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    out = json.loads((scans / f"{WEEK}.selected.json").read_text())
    assert len(out["items"]) == 20
    assert out["skipped"]["no_readme"] == 1
