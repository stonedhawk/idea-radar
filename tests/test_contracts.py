"""Step contracts: scan and selected files against their schemas, and the steps that enforce them."""
from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime, timezone

import pytest

from collectors import hf
from scripts import select as select_step
from scripts.contracts import ContractError, check_scan, check_selected, kind_of, load, main
from scripts.scan import run as scan_run
from scripts.validate import main as validate_main
from tests.conftest import FIXTURES, ROOT

WEEK = "2026-W42"
NOW = datetime(2026, 10, 15, 1, 30, tzinfo=timezone.utc)
SCANS = ROOT / "data" / "scans"


@pytest.fixture
def scan():
    return json.loads((FIXTURES / "select_scan.json").read_text())


@pytest.fixture
def selected():
    return json.loads((FIXTURES / "run" / "selected.json").read_text())


# The files the pipeline has already committed and the fixtures meet the contract.


@pytest.mark.parametrize("path", sorted(SCANS.glob("*.json")), ids=lambda p: p.name)
def test_committed_scan_files_meet_the_contract(path):
    assert load(path)["week"] == path.name[:8]


def test_fixtures_meet_the_contract(scan, selected):
    assert check_scan(scan) == []
    assert check_selected(selected) == []


def test_kind_comes_from_the_file_name(tmp_path):
    assert kind_of(tmp_path / "2026-W42.json") == "scan"
    assert kind_of(tmp_path / "2026-W42.selected.json") == "selected"
    assert kind_of(tmp_path / "selected.json") == "selected"


# Scan files


def test_scan_needs_counts(scan):
    del scan["counts"]
    assert check_scan(scan, "s") == ["s: 'counts' is a required property"]


def test_scan_counts_must_match_the_items(scan):
    scan["counts"]["show_hn"] += 1
    errors = check_scan(scan, "s")
    assert len(errors) == 1 and errors[0].startswith("s/counts/show_hn: says")


def test_scan_week_must_be_an_iso_week(scan):
    scan["week"] = "2026-42"
    assert any(e.startswith("s/week:") for e in check_scan(scan, "s"))


def test_every_item_is_checked_against_scan_item(scan):
    scan["items"][3]["traction_kind"] = "vibes"
    del scan["items"][5]["url"]
    errors = check_scan(scan, "s")
    assert any(e.startswith("s/items/3/traction_kind:") for e in errors)
    assert "s/items/5: 'url' is a required property" in errors


def test_duplicate_items_fail(scan):
    scan["items"].append(copy.deepcopy(scan["items"][0]))
    scan["counts"][scan["items"][0]["source"]] += 1
    assert any("appears 2 times" in e for e in check_scan(scan, "s"))


# Selected files


def test_selected_must_name_its_own_scan(selected):
    selected["scan"] = "2026-W41.json"
    assert check_selected(selected, "x") == ["x/scan: 2026-W41.json is not the scan for 2026-W42"]


def test_selected_items_need_a_quota(selected):
    del selected["quotas"]["hf_space"]
    assert check_selected(selected, "x") == ["x/items: source(s) with no quota: hf_space"]


def test_selected_needs_items(selected):
    selected["items"] = []
    assert any(e.startswith("x/items:") for e in check_selected(selected, "x"))


# Loading and the CLI


def test_load_reports_a_missing_file_and_bad_json(tmp_path):
    with pytest.raises(ContractError, match="missing"):
        load(tmp_path / "2026-W42.json")
    bad = tmp_path / "2026-W42.json"
    bad.write_text("{")
    with pytest.raises(ContractError, match="not valid JSON"):
        load(bad)


def test_cli_passes_good_files_and_fails_bad_ones(tmp_path, scan, capsys):
    good = tmp_path / "2026-W42.json"
    good.write_text(json.dumps(scan))
    assert main([str(good)]) == 0
    assert "ok:" in capsys.readouterr().out

    del scan["counts"]
    bad = tmp_path / "2026-W43.json"
    bad.write_text(json.dumps(scan))
    assert main([str(good), str(bad)]) == 1
    assert "'counts' is a required property" in capsys.readouterr().err


def test_cli_kind_flag_overrides_the_name(tmp_path, selected):
    path = tmp_path / "anything.json"
    path.write_text(json.dumps(selected))
    assert main([str(path)]) == 1
    assert main([str(path), "--kind", "selected"]) == 0


# The steps refuse to write a file that breaks the contract.


def test_scan_writes_nothing_when_an_item_breaks_the_contract(config, tmp_path, fake_fetch, monkeypatch):
    cfg = copy.deepcopy(config)
    cfg["github"]["topics"] = ["ai-agents"]
    real = hf.collect

    def broken(*args, **kwargs):
        items = real(*args, **kwargs)
        items[0]["url"] = "http://not-https.example"
        return items

    monkeypatch.setattr(hf, "collect", broken)
    with pytest.raises(ContractError, match="does not match"):
        scan_run(cfg, week=WEEK, now=NOW, data_dir=tmp_path, token="t", fetch=fake_fetch, sleep=lambda s: None)
    assert not (tmp_path / "scans").exists()
    assert not (tmp_path / "stars.csv").exists()


def test_select_refuses_a_scan_that_breaks_the_contract(config, tmp_path, scan):
    (tmp_path / "scans").mkdir()
    del scan["counts"]
    (tmp_path / "scans" / f"{WEEK}.json").write_text(json.dumps(scan))
    with pytest.raises(ContractError, match="counts"):
        select_step.run(config, week=WEEK, data_dir=tmp_path, has_readme=lambda name: True, now=NOW)
    assert not (tmp_path / "scans" / f"{WEEK}.selected.json").exists()


def test_select_refuses_a_scan_for_another_week(config, tmp_path):
    (tmp_path / "scans").mkdir()
    shutil.copy(FIXTURES / "select_scan.json", tmp_path / "scans" / "2026-W43.json")
    with pytest.raises(ContractError, match="is not 2026-W43"):
        select_step.run(config, week="2026-W43", data_dir=tmp_path, has_readme=lambda name: True, now=NOW)


def test_select_output_meets_the_contract(config, tmp_path):
    (tmp_path / "scans").mkdir()
    shutil.copy(FIXTURES / "select_scan.json", tmp_path / "scans" / f"{WEEK}.json")
    out = select_step.run(config, week=WEEK, data_dir=tmp_path, has_readme=lambda name: True, now=NOW)
    assert load(tmp_path / "scans" / f"{WEEK}.selected.json") == out
    assert out["generated_at"] == "2026-10-15T01:30:00Z"


def test_validate_refuses_a_selected_file_that_breaks_the_contract(tmp_path, selected, capsys):
    run = tmp_path / "run"
    shutil.copytree(FIXTURES / "run", run)
    del selected["quotas"]
    (run / "selected.json").write_text(json.dumps(selected))
    assert validate_main([str(run), "--selected", str(run / "selected.json")]) == 1
    assert "does not meet schemas/selected.json" in capsys.readouterr().err
