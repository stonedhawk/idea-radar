"""Prompt files (SPEC 8.1 to 8.4) and copy rules (audit check 9)."""
from __future__ import annotations

import pytest

from scripts.validate import DASHES
from tests.conftest import ROOT

PROMPTS = ["brief", "brainstorm", "originality", "score"]


@pytest.mark.parametrize("name", PROMPTS)
def test_prompt_exists_and_names_its_schema_or_rubric(name):
    text = (ROOT / "prompts" / f"{name}.md").read_text()
    assert f"SPEC 8." in text.splitlines()[0]
    assert "schemas/" in text or "config/rubric.yaml" in text


def test_brief_prompt_has_one_good_and_one_bad_example():
    text = (ROOT / "prompts" / "brief.md").read_text()
    assert text.count("**Good**") == 1
    assert text.count("**Bad**") == 1


@pytest.mark.parametrize(
    "path",
    [f"prompts/{n}.md" for n in PROMPTS]
    + ["schemas/brief.json", "schemas/idea.json", "schemas/score.json", "config/rubric.yaml"],
)
def test_no_en_or_em_dashes(path):
    assert not DASHES.search((ROOT / path).read_text())
