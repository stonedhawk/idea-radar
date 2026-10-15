"""Publishing a rendered week (SPEC 13, config/publish.yaml)."""
from __future__ import annotations

import csv
import json
import shutil

import pytest

from scripts.publish import ENV_DIR, load_config, main, plan, write_local
from scripts.render import BACKLOG_COLUMNS, render_run
from scripts.validate import load_rubric
from tests.conftest import FIXTURES

RUN = FIXTURES / "run"
WEEK = "2026-W42"


@pytest.fixture
def rendered(tmp_path):
    out = tmp_path / "drive"
    selected = json.loads((RUN / "selected.json").read_text())
    assert render_run(RUN, selected, load_rubric(), out) == []
    return out


def make_plan(rendered):
    return plan(RUN, rendered, load_config(), load_rubric())


def read_csv(path):
    with path.open(newline="") as fh:
        return list(csv.reader(fh))


def test_config_covers_every_file_render_writes(rendered):
    steps, errors = make_plan(rendered)
    assert errors == []
    sources = {str(p) for p in rendered.rglob("*") if p.is_file()}
    assert {s["source"] for s in steps} == sources


def test_plan_puts_each_file_in_the_build_lab_layout(rendered):
    steps, _ = make_plan(rendered)
    by_name = {s["source"].rsplit("/", 1)[1]: s for s in steps}
    assert by_name["_digest.md"] == {
        "action": "upload",
        "source": str(rendered / "_digest.md"),
        "dest": f"Build Lab/02_Briefs/{WEEK}/_digest.md",
        "mime_type": "text/markdown",
    }
    assert by_name["archive.md"]["dest"] == f"Build Lab/99_Archive/{WEEK}-archive.md"
    assert by_name["hn-9003.md"]["dest"] == f"Build Lab/02_Briefs/{WEEK}/hn-9003.md"
    scan = by_name["scan_rows.json"]
    assert (scan["action"], scan["dest"], scan["tab"], scan["rows"]) == (
        "new_sheet_tab", "Build Lab/01_Scan/repo-scan", WEEK, 5,
    )
    backlog = by_name["backlog_rows.json"]
    assert (backlog["action"], backlog["dest"], backlog["tab"]) == (
        "append_rows", "Build Lab/03_Backlog/idea-backlog", "backlog",
    )


def test_plan_needs_a_render(tmp_path):
    steps, errors = make_plan(tmp_path / "nothing")
    assert steps == []
    assert any("missing; run scripts/render.py first" in e for e in errors)


def test_plan_needs_a_valid_run(tmp_path, rendered):
    run = tmp_path / "run"
    shutil.copytree(RUN, run)
    (run / "scores.json").write_text("{")
    steps, errors = plan(run, rendered, load_config(), load_rubric())
    assert steps == []
    assert len(errors) == 1 and errors[0].startswith("scores.json: not valid JSON")


def test_plan_refuses_stale_backlog_rows(rendered):
    path = rendered / "backlog_rows.json"
    rows = json.loads(path.read_text())
    path.write_text(json.dumps(rows[:-1]))
    _, errors = make_plan(rendered)
    assert errors == ["backlog_rows.json: does not match the run; re-run scripts/render.py"]


def test_plan_refuses_scan_rows_without_the_header(rendered):
    path = rendered / "scan_rows.json"
    rows = json.loads(path.read_text())
    path.write_text(json.dumps(rows[1:]))
    _, errors = make_plan(rendered)
    assert len(errors) == 1 and errors[0].startswith("scan_rows.json: first row must be the header")


def test_plan_refuses_scan_rows_for_another_week(rendered):
    path = rendered / "scan_rows.json"
    rows = json.loads(path.read_text())
    rows[1][0] = "2026-W41"
    path.write_text(json.dumps(rows))
    _, errors = make_plan(rendered)
    assert errors == ["scan_rows.json: rows are for ['2026-W41', '2026-W42'], not 2026-W42"]


def test_write_local_builds_the_layout(tmp_path, rendered):
    steps, _ = make_plan(rendered)
    base = tmp_path / "out"
    assert write_local(steps, base) == []
    lab = base / "Build Lab"
    assert (lab / "02_Briefs" / WEEK / "_digest.md").read_text() == (rendered / "_digest.md").read_text()
    assert (lab / "99_Archive" / f"{WEEK}-archive.md").exists()
    scan = read_csv(lab / "01_Scan" / "repo-scan" / f"{WEEK}.csv")
    assert scan[0][0] == "week" and len(scan) == 5
    backlog = read_csv(lab / "03_Backlog" / "idea-backlog" / "backlog.csv")
    assert backlog[0] == BACKLOG_COLUMNS
    assert [row[1] for row in backlog[1:]] == [row[1] for row in json.loads((rendered / "backlog_rows.json").read_text())]


def test_write_local_appends_backlog_rows_under_the_existing_header(tmp_path, rendered):
    steps, _ = make_plan(rendered)
    sheet = tmp_path / "out" / "Build Lab" / "03_Backlog" / "idea-backlog" / "backlog.csv"
    sheet.parent.mkdir(parents=True)
    sheet.write_text(",".join(BACKLOG_COLUMNS) + "\n" + ",".join(["2026-W41", "2026-W41-01"] + [""] * 22) + "\n")
    assert write_local(steps, tmp_path / "out") == []
    rows = read_csv(sheet)
    assert rows.count(BACKLOG_COLUMNS) == 1
    assert rows[1][1] == "2026-W41-01" and rows[2][0] == WEEK


def test_write_local_refuses_a_week_already_published(tmp_path, rendered):
    steps, _ = make_plan(rendered)
    base = tmp_path / "out"
    assert write_local(steps, base) == []
    sheet = base / "Build Lab" / "03_Backlog" / "idea-backlog" / "backlog.csv"
    before = sheet.read_text()
    errors = write_local(steps, base)
    assert errors and all("already exists" in e for e in errors)
    assert sheet.read_text() == before  # no duplicate rows


def test_cli_prints_the_plan_without_writing(tmp_path, rendered, capsys, monkeypatch):
    monkeypatch.delenv(ENV_DIR, raising=False)
    assert main([str(RUN), "--rendered", str(rendered), "--json"]) == 0
    steps = json.loads(capsys.readouterr().out)
    assert len(steps) == 7
    assert not list(tmp_path.glob("**/Build Lab"))


def test_cli_writes_locally_from_the_env_var(tmp_path, rendered, capsys, monkeypatch):
    monkeypatch.setenv(ENV_DIR, str(tmp_path / "pub"))
    assert main([str(RUN), "--rendered", str(rendered)]) == 0
    assert "wrote 7 step(s)" in capsys.readouterr().out
    assert (tmp_path / "pub" / "Build Lab" / "02_Briefs" / WEEK / "_digest.md").exists()
    assert main([str(RUN), "--rendered", str(rendered)]) == 1
    assert "nothing published" in capsys.readouterr().err


def test_config_rejects_an_unknown_action(tmp_path):
    bad = tmp_path / "publish.yaml"
    bad.write_text("root: Build Lab\noutputs:\n  - {source: a.md, action: email, dest: x}\n")
    with pytest.raises(ValueError, match="each action one of"):
        load_config(bad)
