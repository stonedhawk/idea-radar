"""Copy rules for the repo's own text (audit check 9).

data/scans holds third-party titles and descriptions exactly as the APIs
return them, so it is out of scope; everything else we wrote is in.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validate import DASHES
from tests.conftest import ROOT

THIRD_PARTY = Path("data/scans")


def own_text_files() -> list[Path]:
    """Every tracked text file except third-party scan data: what the repo publishes."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    files = []
    for name in filter(None, tracked):
        rel = Path(name)
        if rel.is_relative_to(THIRD_PARTY) or not (ROOT / rel).is_file():
            continue
        try:
            (ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # images and other binaries
        files.append(rel)
    return files


def test_scope_includes_the_files_people_read():
    files = set(own_text_files())
    for must in ["README.md", "SPEC.md", "LICENSE", "prompts/spec.md", "templates/README.template.md"]:
        assert Path(must) in files
    assert not any(f.is_relative_to(THIRD_PARTY) for f in files)


def test_no_en_or_em_dashes_in_our_own_copy():
    offenders = [str(rel) for rel in own_text_files() if DASHES.search((ROOT / rel).read_text(encoding="utf-8"))]
    assert offenders == []


def test_license_names_rahul_m_shah():
    assert "Copyright (c) 2026 Rahul M Shah" in (ROOT / "LICENSE").read_text()


def test_agent_files_are_one_line():
    for name in ["CLAUDE.md", "AGENTS.md", "GEMINI.md"]:
        assert (ROOT / name).read_text().strip() == "Read SPEC.md first."
