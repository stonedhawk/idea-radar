"""Spec prompt and templates (SPEC 9, 11) and copy rules (audit check 9)."""
from __future__ import annotations

import re

import pytest

from scripts.validate import DASHES
from tests.conftest import ROOT

TEMPLATES = ["SPEC", "README", "LAUNCH", "AUDIT"]
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def template(name: str) -> str:
    return (ROOT / "templates" / f"{name}.template.md").read_text()


def headings(text: str) -> list[str]:
    return re.findall(r"^#{2,3} (.+)$", text, re.M)


def table_rows(text: str) -> list[list[str]]:
    """Body rows of every Markdown table in text, as stripped cells."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or re.match(r"^\|[-| ]+\|$", line):
            continue
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def spec_audit_checks() -> list[list[str]]:
    section = (ROOT / "SPEC.md").read_text().split("## 11. Stage 6", 1)[1].split("\n## ", 1)[0]
    return [r for r in table_rows(section) if r[0].isdigit()]


def test_spec_prompt_names_its_section_and_templates():
    text = (ROOT / "prompts" / "spec.md").read_text()
    assert "SPEC 9" in text.splitlines()[0]
    for name in ["SPEC", "README", "LAUNCH"]:
        assert f"templates/{name}.template.md" in text
    for out in ["`SPEC.md`", "`README.target.md`", "`LAUNCH.md`", "04_Specs"]:
        assert out in text


@pytest.mark.parametrize("name", TEMPLATES)
def test_every_placeholder_is_documented_in_the_spec_prompt(name):
    prompt = (ROOT / "prompts" / "spec.md").read_text()
    used = set(PLACEHOLDER.findall(template(name)))
    assert used, f"{name} template has no placeholders"
    missing = sorted(p for p in used if f"{{{{{p}}}}}" not in prompt)
    assert missing == []


def test_spec_prompt_documents_no_unused_placeholders():
    prompt = (ROOT / "prompts" / "spec.md").read_text()
    used = set().union(*(PLACEHOLDER.findall(template(n)) for n in TEMPLATES))
    assert set(PLACEHOLDER.findall(prompt)) == used


def test_spec_template_has_the_sections_spec_9_requires():
    found = " | ".join(headings(template("SPEC"))).lower()
    for section in ["problem", "user", "scope", "non-goals", "requirements", "test plan", "milestones"]:
        assert section in found
    text = template("SPEC")
    assert "| # | Requirement | Acceptance criteria |" in text
    assert "{{verifiable_by}}" in text.split("## 8. Test plan", 1)[1]


def test_spec_template_sets_up_the_repo_like_spec_10():
    text = template("SPEC")
    assert "`CLAUDE.md`, `AGENTS.md` and `GEMINI.md`: one line each, \"Read SPEC.md first.\"" in text
    assert "Rahul M Shah" in text


def test_readme_template_has_what_spec_9_requires():
    text = template("README")
    assert text.splitlines()[2] == "{{hook}}"
    assert re.search(r"!\[[^\]]*\]\([^)]+\.gif\)", text), "demo GIF placeholder"
    found = [h.lower() for h in headings(text)]
    for section in ["quickstart", "limitations", "credits", "what leaves your machine"]:
        assert section in found
    assert "{{source_pattern}}" in text.split("## Credits", 1)[1]
    assert "Three commands or fewer" in text.split("## Quickstart", 1)[1]


def test_launch_template_has_what_spec_9_requires():
    text = template("LAUNCH")
    found = [h.lower() for h in headings(text)]
    for section in ["channels", "post drafts", "timing", "measured at 7 and 30 days"]:
        assert section in found
    measured = text.split("## Measured at 7 and 30 days", 1)[1]
    assert "| Measure | Day 7 | Day 30 | Recorded by |" in measured
    assert "scripts/track.py" in measured
    assert "my-writing-style" in text


def test_audit_template_has_all_11_checks_from_spec_11():
    section = template("AUDIT").split("## Checks", 1)[1].split("\n## ", 1)[0]
    checks = [r for r in table_rows(section) if r[0].isdigit()]
    assert [r[:3] for r in checks] == [r[:3] for r in spec_audit_checks()]
    assert [int(r[0]) for r in checks] == list(range(1, 12))


def test_audit_template_has_a_claim_evidence_action_table_for_check_1():
    section = template("AUDIT").split("## Check 1: claims", 1)[1].split("\n## ", 1)[0]
    assert "| Claim | Evidence | Action |" in section


def test_audit_template_has_three_worked_examples_for_check_2():
    section = template("AUDIT").split("## Check 2: worked examples", 1)[1].split("\n## ", 1)[0]
    assert [r[0] for r in table_rows(section)][1:] == ["1", "2", "3"]


@pytest.mark.parametrize(
    "path", ["prompts/spec.md"] + [f"templates/{n}.template.md" for n in TEMPLATES]
)
def test_no_en_or_em_dashes(path):
    assert not DASHES.search((ROOT / path).read_text())
