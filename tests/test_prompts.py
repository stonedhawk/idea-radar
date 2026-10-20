"""Prompt files (SPEC 8.1 to 8.4, 9): required rules and length (audit check 6), copy rules (audit check 9)."""
from __future__ import annotations

import re

import pytest
import yaml

from scripts.validate import DASHES
from tests.conftest import ROOT

PROMPTS = ["brief", "brainstorm", "originality", "score"]
ALL_PROMPTS = [*PROMPTS, "spec"]

# Audit check 6: a prompt must paste into a chat app, so 7,500 characters or less.
MAX_CHARS = 7500

# Audit check 6: the rules each prompt must state, taken from the SPEC section
# it implements. Matched case-sensitively after collapsing whitespace.
REQUIRED_RULES = {
    "brief": [
        "schemas/brief.json",
        "`problem`", "`user`", "`mechanism`", "`why_now`", "`evidence`",
        "Never name the product",
        "Only from evidence in the source",
        "Every selected item must appear exactly once",
        "Do not invent numbers",
        "No em dashes or en dashes",
    ],
    "brainstorm": [
        "schemas/idea.json",
        "**Same mechanism, new user.**",
        "**Same user, earlier moment.**",
        "**Combine two patterns.**",
        "**Invert.**",
        "At most 2 ideas per brief",
        "At most 15 ideas per week",
        "2 weekends or less",
        "`smallest_version`", "`demo`", "`verifiable_by`", "`rahul_edge`",
        "Do not port or clone the source's code",
        "No em dashes or en dashes",
    ],
    "originality": [
        "schemas/idea.json",
        "Two GitHub searches",
        "Two web searches",
        "`clear`", "`differentiated`", "`killed`",
        "a commit in the last 6 months and 100 or more stars",
        "`evidence_urls` is required for every verdict",
        "killed ideas are not scored",
        "No em dashes or en dashes",
    ],
    "score": [
        "config/rubric.yaml",
        "A score without a reason fails validation",
        "`gaming_x_ai_pm`", "`gaming_only`", "`ai_pm_only`", "`neither`",
        "total = sum(weight x score) / 5",
        "totals of 70 or more, highest first, at most 3",
        "No em dashes or en dashes",
    ],
    "spec": [
        "templates/SPEC.template.md", "templates/README.template.md", "templates/LAUNCH.template.md",
        "If that row's status is not `picked`, stop and say so",
        "Do not invent them",
        "No `{{` and no `<!--` left in any of the three files",
        "The quickstart is 3 commands or fewer",
        "at least two specific limitations",
        "The About line is 200 characters or less",
        "No source code was copied from the source repo",
        "Do not share any file or folder",
        "keeps the RTK and `HANDOFF.md` requirements from the template, unchanged",
        "No em dashes or en dashes",
    ],
}


def prompt_text(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text()


def test_every_prompt_has_rules():
    assert sorted(REQUIRED_RULES) == sorted(ALL_PROMPTS)
    assert sorted(p.stem for p in (ROOT / "prompts").glob("*.md")) == sorted(ALL_PROMPTS)


@pytest.mark.parametrize("name", ALL_PROMPTS)
def test_prompt_states_its_required_rules(name):
    text = re.sub(r"\s+", " ", prompt_text(name))
    missing = [rule for rule in REQUIRED_RULES[name] if rule not in text]
    assert missing == []


@pytest.mark.parametrize("name", ALL_PROMPTS)
def test_prompt_fits_in_a_chat_app(name):
    assert len(prompt_text(name)) <= MAX_CHARS


def test_score_prompt_weights_match_the_rubric():
    rubric = yaml.safe_load((ROOT / "config" / "rubric.yaml").read_text())
    text = prompt_text("score")
    for key, weight in rubric["weights"].items():
        assert re.search(rf"\| `{key}` \| {weight} \|", text), key
    for lens, cap in rubric["lens_caps"].items():
        assert re.search(rf"\| `{lens}` \| {rubric['lens'][lens]} \| {cap} \|", text), lens


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
    [f"prompts/{n}.md" for n in ALL_PROMPTS]
    + ["schemas/brief.json", "schemas/idea.json", "schemas/score.json", "config/rubric.yaml"],
)
def test_no_en_or_em_dashes(path):
    assert not DASHES.search((ROOT / path).read_text())
