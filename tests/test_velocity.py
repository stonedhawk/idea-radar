"""Velocity maths, both flags (SPEC 6.3)."""
from __future__ import annotations

import shutil
from datetime import date

import pytest

from scripts.scan import read_star_rows, star_history, velocity_7d, write_star_rows
from tests.conftest import FIXTURES

TODAY = date(2026, 10, 15)
WEEK = "2026-W42"


@pytest.fixture
def history():
    return star_history(read_star_rows(FIXTURES / "stars.csv"), exclude_week=WEEK)


def v(stars_now, repo, history, created=date(2026, 1, 1)):
    return velocity_7d(stars_now, TODAY, created, history.get(repo, []), min_days=5, max_days=10)


def test_measured_from_snapshot_seven_days_old(history):
    # 400 stars on 2026-10-08, 700 now: 300 in 7 days. The 14-day-old row is ignored.
    assert v(700, "acme/agent-kit", history) == (300.0, "velocity_7d_measured")


def test_current_week_rows_are_not_history(history):
    # The fixture has a 2026-W42 row for agent-kit; it must not be the baseline.
    assert all(day != TODAY for day, _ in history["acme/agent-kit"])


def test_measured_picks_snapshot_closest_to_seven_days(history):
    # Snapshots 6 days (500) and 10 days (400) old: use the 6-day one.
    value, kind = v(590, "acme/two-snapshots", history)
    assert kind == "velocity_7d_measured"
    assert value == pytest.approx((590 - 500) / 6 * 7)


@pytest.mark.parametrize(
    "repo, kind",
    [
        ("acme/edge-5", "velocity_7d_measured"),
        ("acme/edge-10", "velocity_7d_measured"),
        ("acme/too-recent", "velocity_7d_estimated"),
        ("acme/edge-11", "velocity_7d_estimated"),
    ],
)
def test_window_is_5_to_10_days_inclusive(history, repo, kind):
    assert v(200, repo, history)[1] == kind


def test_measured_uses_days_between(history):
    # 5 days old, +100 stars: 100 / 5 * 7 = 140.
    assert v(200, "acme/edge-5", history) == (pytest.approx(140.0), "velocity_7d_measured")


def test_estimated_without_any_snapshot(history):
    # Created 2026-09-15, 30 days old, 600 stars: 600 / 30 * 7 = 140.
    value, kind = v(600, "acme/unknown", history, created=date(2026, 9, 15))
    assert kind == "velocity_7d_estimated"
    assert value == pytest.approx(140.0)


def test_estimated_when_only_stale_snapshot(history):
    value, kind = v(300, "acme/stale", history, created=date(2026, 8, 16))
    assert kind == "velocity_7d_estimated"
    assert value == pytest.approx(300 / 60 * 7)


def test_estimated_age_floor_is_one_day(history):
    # Created today: age is treated as 1 day, not 0.
    assert v(70, "acme/new", history, created=TODAY) == (pytest.approx(490.0), "velocity_7d_estimated")


def test_measured_can_be_negative(history):
    assert v(300, "acme/agent-kit", history) == (pytest.approx(-100.0), "velocity_7d_measured")


def test_rerunning_a_week_replaces_its_rows(tmp_path):
    path = tmp_path / "stars.csv"
    shutil.copy(FIXTURES / "stars.csv", path)
    items = [{"source": "github", "id": "acme/agent-kit", "stars": 710}, {"source": "show_hn", "id": "1"}]

    for _ in range(2):
        write_star_rows(path, read_star_rows(path), WEEK, TODAY, items)

    rows = read_star_rows(path)
    this_week = [r for r in rows if r["week"] == WEEK]
    assert this_week == [{"week": WEEK, "date": "2026-10-15", "repo": "acme/agent-kit", "stars": "710"}]
    assert len(rows) == 10  # 9 earlier rows kept, 1 row for this week
