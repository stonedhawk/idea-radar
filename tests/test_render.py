"""Rendering validated output for Drive (SPEC 8, 13)."""
from __future__ import annotations

import json
import re

import pytest

from scripts.render import BACKLOG_COLUMNS, main, render_run
from scripts.validate import DASHES, load_rubric
from tests.conftest import FIXTURES, ROOT

RUN = FIXTURES / "run"


@pytest.fixture
def selected():
    return json.loads((RUN / "selected.json").read_text())


@pytest.fixture
def out(tmp_path, selected):
    out = tmp_path / "drive"
    assert render_run(RUN, selected, load_rubric(), out) == []
    return out


def test_backlog_columns_match_spec_13_1():
    spec = (ROOT / "SPEC.md").read_text()
    section = spec.split("### 13.1 Backlog sheet columns", 1)[1]
    line = re.search(r"`([^`]+)`", section).group(1)
    assert BACKLOG_COLUMNS == [c.strip() for c in line.split(",")]


def test_writes_every_file(out):
    names = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert names == [
        "_digest.md",
        "archive.md",
        "backlog_rows.json",
        "briefs/acme-agent-1.md",
        "briefs/hf-org-level-designer.md",
        "briefs/hn-9003.md",
        "scan_rows.json",
    ]


def test_digest_shortlist_has_verdicts_and_evidence(out):
    digest = (out / "_digest.md").read_text()
    shortlist = digest.split("## Shortlist", 1)[1].split("## Other ideas", 1)[0]
    headings = re.findall(r"^### (\d)\. (.+) \((\d+(?:\.\d+)?)\)$", shortlist, re.M)
    assert headings == [("1", "LiveOps incident filer", "86"), ("2", "Experiment ticket planner", "85")]
    assert shortlist.count("- **Originality:** ") == 2
    assert "- **Originality:** differentiated. Existing planners order" in shortlist
    assert shortlist.count("- **Evidence:** https://") == 2


def test_digest_lists_killed_dropped_and_skipped(out):
    digest = (out / "_digest.md").read_text()
    assert "- 2026-W42-03 Anti-planner: example/anti-todo" in digest
    assert "## Dropped (outside the lens)\n\n- 2026-W42-05 Weekly plan for anyone" in digest
    assert "- org/face-swap-demo: Matches the face-swap exclusion" in digest
    other = digest.split("## Other ideas", 1)[1].split("## Killed", 1)[0]
    assert "2026-W42-04" in other and "2026-W42-05" not in other


def test_digest_with_no_shortlist(tmp_path, selected):
    run = tmp_path / "run"
    run.mkdir()
    for name in ("briefs", "ideas"):
        (run / f"{name}.json").write_text((RUN / f"{name}.json").read_text())
    scores = json.loads((RUN / "scores.json").read_text())
    scores["scores"] = [s for s in scores["scores"] if s["total"] < 70 or s["lens"] == "neither"]
    ideas = json.loads((RUN / "ideas.json").read_text())
    ideas["ideas"] = [i for i in ideas["ideas"] if i["idea_id"] in {"2026-W42-03", "2026-W42-04", "2026-W42-05"}]
    (run / "ideas.json").write_text(json.dumps(ideas))
    (run / "scores.json").write_text(json.dumps(scores))
    assert render_run(run, selected, load_rubric(), tmp_path / "drive") == []
    assert "No idea reached 70 this week." in (tmp_path / "drive" / "_digest.md").read_text()


def test_no_dashes_in_any_output(out):
    for path in out.rglob("*"):
        if path.is_file():
            assert not DASHES.search(path.read_text()), path
    # The source title carried an en dash; it is rendered as a hyphen.
    assert "# Show HN: A to-do list - plans your week" in (out / "briefs" / "hn-9003.md").read_text()


def test_backlog_rows(out):
    rows = json.loads((out / "backlog_rows.json").read_text())
    assert all(len(r) == len(BACKLOG_COLUMNS) for r in rows)
    col = {name: i for i, name in enumerate(BACKLOG_COLUMNS)}
    assert [(r[col["idea_id"]], r[col["total"]], r[col["status"]]) for r in rows] == [
        ("2026-W42-01", 86, "shortlisted"),
        ("2026-W42-02", 85, "shortlisted"),
        ("2026-W42-04", 60, "new"),
    ]
    planner = rows[1]
    assert planner[col["source_urls"]] == "https://github.com/acme/agent-1 ; https://news.ycombinator.com/item?id=9003"
    assert planner[col["originality"]] == "differentiated"
    assert planner[col["lens"]] == 2
    assert planner[col["notes"]] == "lens: ai_pm_only"


def test_archive_has_one_line_per_killed_or_dropped_idea(out):
    lines = [l for l in (out / "archive.md").read_text().splitlines() if l.startswith("- ")]
    assert len(lines) == 2
    assert lines[0].startswith("- 2026-W42-03 Anti-planner: killed.")
    assert "Evidence: https://github.com/example/anti-todo" in lines[0]
    assert lines[1].startswith("- 2026-W42-05 Weekly plan for anyone: dropped, outside the lens.")


def test_scan_rows(out, selected):
    rows = json.loads((out / "scan_rows.json").read_text())
    assert rows[0][:3] == ["week", "source", "id"]
    assert len(rows) == len(selected["items"]) + 1
    assert rows[1][:3] == ["2026-W42", "github", "acme/agent-1"]
    assert rows[1][6] == "ai-agents"


def test_invalid_run_writes_nothing(tmp_path, selected):
    run = tmp_path / "run"
    run.mkdir()
    for name in ("briefs", "ideas", "scores"):
        (run / f"{name}.json").write_text((RUN / f"{name}.json").read_text())
    scores = json.loads((run / "scores.json").read_text())
    scores["scores"][0]["criteria"]["demo"].pop("reason")
    (run / "scores.json").write_text(json.dumps(scores))
    out = tmp_path / "drive"
    errors = render_run(run, selected, load_rubric(), out)
    assert errors and "reason" in errors[0]
    assert not out.exists()


def test_cli(tmp_path, capsys):
    assert main([str(RUN), "--selected", str(RUN / "selected.json"), "--out", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "_digest.md").exists()
