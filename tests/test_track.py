"""Star-check tracking (SPEC 12)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from scripts.render import BACKLOG_COLUMNS
from scripts.track import as_dicts, due_checks, main, slugify

TODAY = date(2026, 11, 16)  # a Monday, when the weekly task runs


def row(**cells) -> list:
    """A sheet row in SPEC 13.1 order, trailing empty cells dropped like the Sheets API does."""
    values = [cells.get(col, "") for col in BACKLOG_COLUMNS]
    while values and values[-1] == "":
        values.pop()
    return values


def shipped(idea_id: str, title: str, shipped_on: str, **cells) -> list:
    base = {"idea_id": idea_id, "title": title, "status": "shipped", "shipped_on": shipped_on,
            "repo_url": f"https://github.com/stonedhawk/{slugify(title)}"}
    return row(**{**base, **cells})


def sheet(*rows) -> list:
    return [BACKLOG_COLUMNS, *rows]


def checks(rows, today=TODAY) -> list[tuple[str, int]]:
    due, errors = due_checks(rows, today)
    assert errors == []
    return [(d["idea_id"], d["check"]) for d in due]


def test_slugify_matches_drive_folder_names():
    assert slugify("Shop offer teardown") == "shop-offer-teardown"
    assert slugify("  LiveOps model bench!  ") == "liveops-model-bench"
    assert slugify("Economy table extractor (v2)") == "economy-table-extractor-v2"


def test_only_shipped_rows_are_checked():
    rows = sheet(
        shipped("A", "Alpha", "2026-11-09"),
        row(idea_id="B", title="Beta", status="building", shipped_on="2026-11-09",
            repo_url="https://github.com/stonedhawk/beta"),
        row(idea_id="C", title="Gamma", status="shortlisted"),
    )
    assert checks(rows) == [("A", 7)]


@pytest.mark.parametrize(
    "shipped_on, expected",
    [
        ("2026-11-10", []),                        # day 6: nothing due yet
        ("2026-11-09", [("A", 7)]),                # day 7 exactly
        ("2026-11-03", [("A", 7)]),                # day 13: weekly run missed day 7, catch up
        ("2026-10-18", [("A", 7)]),                # day 29: 30-day check not yet due
        ("2026-10-17", [("A", 7), ("A", 30)]),     # day 30 with the 7-day check never recorded
    ],
)
def test_due_boundaries(shipped_on, expected):
    assert checks(sheet(shipped("A", "Alpha", shipped_on))) == expected


def test_recorded_checks_are_not_due_again():
    rows = sheet(
        shipped("A", "Alpha", "2026-10-17", stars_7d="4"),
        shipped("B", "Beta", "2026-10-01", stars_7d="9", stars_30d="31"),
        shipped("C", "Gamma", "2026-11-09", stars_7d="0"),  # zero is a recorded value
    )
    assert checks(rows) == [("A", 30)]


def test_due_entry_fields_and_order():
    rows = sheet(
        shipped("2026-W44-01", "Shop offer teardown", "2026-11-09", notes="first ship"),
        shipped("2026-W42-02", "LiveOps model bench", "2026-10-12"),
    )
    due, errors = due_checks(rows, TODAY)
    assert errors == []
    assert [(d["idea_id"], d["check"], d["due_on"]) for d in due] == [
        ("2026-W42-02", 7, "2026-10-19"),
        ("2026-W42-02", 30, "2026-11-11"),
        ("2026-W44-01", 7, "2026-11-16"),
    ]
    assert due[0] == {
        "idea_id": "2026-W42-02",
        "title": "LiveOps model bench",
        "slug": "liveops-model-bench",
        "repo_url": "https://github.com/stonedhawk/liveops-model-bench",
        "shipped_on": "2026-10-12",
        "check": 7,
        "column": "stars_7d",
        "due_on": "2026-10-19",
        "days_since_ship": 35,
        "late_by": 28,
    }
    assert due[2]["late_by"] == 0


def test_bad_rows_are_reported_not_skipped_silently():
    rows = sheet(
        shipped("A", "Alpha", "16/11/2026"),
        shipped("B", "Beta", ""),
        shipped("C", "Gamma", "2026-11-20"),
        shipped("D", "Delta", "2026-11-09", repo_url=""),
        shipped("E", "Epsilon", "2026-11-09"),
    )
    due, errors = due_checks(rows, TODAY)
    assert [d["idea_id"] for d in due] == ["E"]
    assert len(errors) == 4
    assert errors[0].startswith("A Alpha: shipped_on '16/11/2026'")
    assert "after today" in errors[2]
    assert errors[3] == "D Delta: shipped with no repo_url"


def test_status_and_cells_tolerate_sheet_formatting():
    rows = sheet(shipped("A", "Alpha", " 2026-11-09 ", status="Shipped ", stars_30d=" "))
    assert checks(rows) == [("A", 7)]


def test_accepts_dicts_and_skips_blank_rows():
    dicts = [{"idea_id": "A", "title": "Alpha", "status": "shipped", "shipped_on": "2026-11-09",
              "repo_url": "https://github.com/stonedhawk/alpha"}]
    assert checks(dicts) == [("A", 7)]
    assert as_dicts([BACKLOG_COLUMNS, [], ["", ""]]) == []
    assert as_dicts([]) == []


def test_header_must_have_every_column():
    with pytest.raises(ValueError, match="stars_30d"):
        as_dicts([[c for c in BACKLOG_COLUMNS if c != "stars_30d"]])


def test_reordered_header_columns_are_read_by_name():
    header = list(reversed(BACKLOG_COLUMNS))
    values = dict(zip(BACKLOG_COLUMNS, row(idea_id="A", title="Alpha", status="shipped",
                                            shipped_on="2026-11-09",
                                            repo_url="https://github.com/stonedhawk/alpha")))
    assert checks([header, [values.get(c, "") for c in header]]) == [("A", 7)]


def test_cli(tmp_path, capsys):
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps(sheet(shipped("A", "Alpha", "2026-11-03"))))
    assert main([str(path), "--today", "2026-11-16"]) == 0
    out = capsys.readouterr().out
    assert "7d  A  Alpha" in out
    assert "06_Shipped/alpha/results.md, stars_7d (due 2026-11-10, 6 day(s) late)" in out

    assert main([str(path), "--today", "2026-11-16", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["column"] == "stars_7d"

    assert main([str(path), "--today", "2026-11-05"]) == 0
    assert capsys.readouterr().out.strip() == "no star checks due"


def test_cli_exits_1_on_row_errors(tmp_path, capsys):
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps(sheet(shipped("A", "Alpha", "2026-11-09", repo_url=""))))
    assert main([str(path), "--today", "2026-11-16"]) == 1
    assert "no repo_url" in capsys.readouterr().err
