"""Selection rules (SPEC 7): exclusions, quota fill, diversity cap, repeats."""
from __future__ import annotations

import copy
import json
from collections import Counter

import pytest

from scripts.select import (
    exclusion_reason,
    matches_term,
    previous_weeks,
    rank_key,
    recently_selected,
    select_items,
)
from tests.conftest import load_fixture

NO_README = {"acme/no-docs"}


@pytest.fixture
def items():
    return load_fixture("select_scan.json")["items"]


def by_id(items, item_id):
    return next(it for it in items if it["id"] == item_id)


def has_readme(full_name):
    return full_name not in NO_README


def run(items, config, recent=frozenset()):
    return select_items(items, config, recent=set(recent), has_readme=has_readme)


# Exclusions


@pytest.mark.parametrize(
    "item_id, reason",
    [
        ("acme/fork-repo", "fork"),
        ("acme/old-repo", "archived"),
        ("acme/awesome-mcp", "excluded_term"),  # name
        ("acme/mcp-tools", "excluded_term"),  # topic "awesome-list"
        ("acme/llm-course", "excluded_term"),
        ("acme/prompt-tutorials", "excluded_term"),  # plural
        ("acme/playlist-sync", None),  # "list" only as part of a word
        ("acme/agent-1", None),
        ("Pepe104/MiniMax-H3-Turbo-Lora-UNCENSORED", "excluded_term"),
        ("someone/nsfw-detector", "excluded_term"),
        ("multimodalart/jev-decision-index", None),
        ("9003", None),  # Show HN titles are not term-filtered
    ],
)
def test_exclusion_reason(items, config, item_id, reason):
    assert exclusion_reason(by_id(items, item_id), config["exclude"]) == reason


def test_every_configured_term_excludes_a_github_repo(items, config):
    base = by_id(items, "acme/agent-1")
    for term in config["exclude"]["terms"]:
        repo = {**base, "title": f"my-{term}-repo"}
        assert exclusion_reason(repo, config["exclude"]) == "excluded_term", term


def test_every_hf_term_excludes_a_space(items, config):
    base = by_id(items, "org/level-designer")
    for term in config["exclude"]["hf_terms"]:
        space = {**base, "id": f"org/{term}-demo", "title": "Demo"}
        assert exclusion_reason(space, config["exclude"]) == "excluded_term", term


def test_hf_title_is_checked_as_well_as_id(items, config):
    space = {**by_id(items, "org/level-designer"), "title": "Deepfake studio"}
    assert exclusion_reason(space, config["exclude"]) == "excluded_term"


@pytest.mark.parametrize(
    "space_id, title",
    [
        ("hugging-apps/bfs-best-face-swap", "BFS Best Face Swap"),  # selected in 2026-W42
        ("org/FaceSwapLab", "Face Swap Lab"),
        ("org/faceswap-v2", "Demo"),
        ("org/face-swaps", "Demo"),
    ],
)
def test_face_swap_spaces_are_excluded(items, config, space_id, title):
    space = {**by_id(items, "org/level-designer"), "id": space_id, "title": title}
    assert exclusion_reason(space, config["exclude"]) == "excluded_term"


def test_face_terms_do_not_catch_unrelated_spaces(items, config):
    space = {**by_id(items, "org/level-designer"), "id": "org/face-landmarks", "title": "Swap tiles puzzle"}
    assert exclusion_reason(space, config["exclude"]) is None


@pytest.mark.parametrize(
    "text, term, expected",
    [
        ("awesome-mcp", "awesome", True),
        ("playlist-sync", "list", False),
        ("checklists", "list", False),
        ("prompt-tutorials", "tutorial", True),
        ("Python Cheat Sheet", "cheat-sheet", True),
        ("cheatsheet", "cheat-sheet", False),
        ("", "list", False),
    ],
)
def test_matches_term(text, term, expected):
    assert matches_term(text, term) is expected


def test_no_readme_is_skipped(items, config):
    selected, skipped = run(items, config)
    assert "acme/no-docs" not in {it["id"] for it in selected}
    assert skipped["no_readme"] == 1


def test_readme_is_only_checked_for_repos_about_to_be_picked(items, config):
    checked = []

    def spy(full_name):
        checked.append(full_name)
        return has_readme(full_name)

    select_items(items, config, recent=set(), has_readme=spy)
    assert "acme/fork-repo" not in checked
    assert "acme/playlist-sync" not in checked  # ranked below the quota
    assert len(checked) == 15  # 14 picked plus acme/no-docs


# Quotas


def test_default_quotas_with_show_hn_shortfall(items, config):
    # 3 Show HN items for 5 slots: GitHub gets 12 + 2.
    selected, _ = run(items, config)
    assert Counter(it["source"] for it in selected) == {"github": 14, "show_hn": 3, "hf_space": 3}
    assert len(selected) == 20


def test_output_is_grouped_in_quota_order(items, config):
    selected, _ = run(items, config)
    sources = [it["source"] for it in selected]
    assert sources == ["github"] * 14 + ["show_hn"] * 3 + ["hf_space"] * 3


def test_quotas_fill_exactly_when_every_source_has_enough(items, config):
    cfg = copy.deepcopy(config)
    cfg["select"]["quotas"] = {"github": 2, "show_hn": 2, "hf_space": 2}
    selected, _ = run(items, cfg)
    assert Counter(it["source"] for it in selected) == {"github": 2, "show_hn": 2, "hf_space": 2}


def test_hf_shortfall_also_goes_to_github(items, config):
    cfg = copy.deepcopy(config)
    cfg["select"]["quotas"] = {"github": 2, "show_hn": 1, "hf_space": 10}
    selected, _ = run(items, cfg)
    counts = Counter(it["source"] for it in selected)
    assert counts["hf_space"] == 4  # four eligible Spaces
    assert counts["github"] == 2 + 6


def test_picks_highest_traction_first(items, config):
    selected, _ = run(items, config)
    hf_ids = [it["id"] for it in selected if it["source"] == "hf_space"]
    assert hf_ids == ["multimodalart/jev-decision-index", "org/level-designer", "org/npc-voice"]


def test_measured_beats_estimated_on_a_tie(items):
    tied = [by_id(items, "acme/tie-estimated"), by_id(items, "acme/tie-measured")]
    assert [it["id"] for it in sorted(tied, key=rank_key)] == ["acme/tie-measured", "acme/tie-estimated"]


def test_tie_break_applies_inside_selection(items, config):
    cfg = copy.deepcopy(config)
    # 15 eligible repos rank above the tied pair, so slot 16 decides the tie.
    cfg["select"]["quotas"] = {"github": 16, "show_hn": 0, "hf_space": 0}
    selected, _ = run(items, cfg)
    assert selected[-1]["id"] == "acme/tie-measured"


# Diversity cap


def test_diversity_cap(items, config):
    selected, skipped = run(items, config)
    per_topic = Counter(it["primary_topic"] for it in selected if it.get("primary_topic"))
    assert max(per_topic.values()) == 3
    assert "acme/agent-4" not in {it["id"] for it in selected}
    assert skipped["diversity_cap"] >= 1


def test_items_without_primary_topic_are_not_capped(items, config):
    cfg = copy.deepcopy(config)
    cfg["select"]["diversity_cap"] = 1
    cfg["select"]["quotas"] = {"github": 0, "show_hn": 3, "hf_space": 0}
    selected, _ = run(items, cfg)
    assert len(selected) == 3


# Two-week repeat rule


def write_selected(scans_dir, week, ids):
    payload = {"week": week, "items": [{"source": source, "id": item_id} for source, item_id in ids]}
    (scans_dir / f"{week}.selected.json").write_text(json.dumps(payload))


def test_previous_weeks():
    assert previous_weeks("2026-W42", 2) == ["2026-W41", "2026-W40"]


def test_previous_weeks_across_a_53_week_year():
    assert previous_weeks("2027-W01", 2) == ["2026-W53", "2026-W52"]


def test_repeat_rule_covers_exactly_two_previous_weeks(tmp_path, items, config):
    write_selected(tmp_path, "2026-W41", [("github", "acme/repeat-repo")])
    write_selected(tmp_path, "2026-W40", [("hf_space", "multimodalart/jev-decision-index")])
    write_selected(tmp_path, "2026-W39", [("github", "acme/agent-1")])  # three weeks back: allowed

    recent = recently_selected(tmp_path, "2026-W42", config["select"]["repeat_weeks"])
    assert recent == {("github", "acme/repeat-repo"), ("hf_space", "multimodalart/jev-decision-index")}

    selected, skipped = run(items, config, recent)
    ids = {it["id"] for it in selected}
    assert "acme/repeat-repo" not in ids
    assert "multimodalart/jev-decision-index" not in ids
    assert "acme/agent-1" in ids
    assert skipped["recent"] == 2


def test_repeat_rule_matches_source_and_id(tmp_path, items, config):
    # Same id from a different source is not a repeat.
    write_selected(tmp_path, "2026-W41", [("show_hn", "acme/repeat-repo")])
    recent = recently_selected(tmp_path, "2026-W42", 2)
    selected, _ = run(items, config, recent)
    assert "acme/repeat-repo" in {it["id"] for it in selected}


def test_missing_previous_weeks_are_fine(tmp_path):
    assert recently_selected(tmp_path, "2026-W42", 2) == set()


# One id per selection (briefs and ideas key items by id alone)


def test_an_id_already_picked_from_another_source_is_skipped(items, config):
    space = by_id(items, "multimodalart/jev-decision-index")
    twin = copy.deepcopy(by_id(items, "acme/agent-1"))
    twin.update(id=space["id"], url=f"https://github.com/{space['id']}", title="jev-decision-index", traction=10.0**6)
    selected, skipped = run([*items, twin], config)
    assert [(it["source"], it["id"]) for it in selected if it["id"] == space["id"]] == [("hf_space", space["id"])]
    assert skipped["duplicate_id"] == 1
    assert len(selected) == sum(config["select"]["quotas"].values())
