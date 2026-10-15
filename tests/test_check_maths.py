"""The independent maths check (audit check 2) passes, and fails when the maths changes."""
from __future__ import annotations

import subprocess
import sys

import yaml

from scripts import check_maths
from tests.conftest import ROOT


def test_runs_from_the_command_line_and_every_example_matches():
    result = subprocess.run(
        [sys.executable, "scripts/check_maths.py"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "| NO |" not in result.stdout
    assert "16 of 16 worked examples match." in result.stdout


def test_at_least_three_worked_examples_per_area():
    assert sum(kind.endswith("measured") for *_, kind, _ in check_maths.VELOCITY) >= 3
    assert sum(kind.endswith("estimated") for *_, kind, _ in check_maths.VELOCITY) >= 3
    assert len(check_maths.TOTALS) >= 3
    assert len(check_maths.CAPS) >= 3


def test_fails_when_a_weight_changes(tmp_path, capsys):
    rubric = yaml.safe_load((ROOT / "config" / "rubric.yaml").read_text())
    rubric["weights"]["distribution"] = 11
    path = tmp_path / "rubric.yaml"
    path.write_text(yaml.safe_dump(rubric))

    assert check_maths.main(["--rubric", str(path)]) == 1
    assert "Mismatch:" in capsys.readouterr().out


def test_fails_when_the_velocity_window_changes(tmp_path, capsys):
    sources = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())
    sources["velocity"]["max_days"] = 11
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(sources))

    assert check_maths.main(["--sources", str(path)]) == 1
    assert "snapshot 11 days old" in capsys.readouterr().out.split("Mismatch:")[1]
