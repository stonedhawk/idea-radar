"""LLM output validation (SPEC 8): schemas, rubric maths, lens caps, shortlist."""
from __future__ import annotations

import copy
import json
import shutil

import pytest
from jsonschema import Draft202012Validator

from scripts.validate import (
    check_briefs,
    check_ideas,
    check_scores,
    compute_total,
    lens_cap,
    load_rubric,
    load_schema,
    main,
    shortlist,
    validate_run,
)
from tests.conftest import FIXTURES, ROOT

RUN = FIXTURES / "run"
CRITERIA = ["lens_fit", "rahul_edge", "build_size", "demo", "verifiable", "distribution"]


@pytest.fixture
def rubric():
    return load_rubric()


@pytest.fixture
def run():
    return {name: json.loads((RUN / f"{name}.json").read_text()) for name in ("selected", "briefs", "ideas", "scores")}


@pytest.fixture
def run_dir(tmp_path, run):
    """A writable copy of the fixture run. Tests edit run[...] and call write()."""

    def write():
        for name in ("briefs", "ideas", "scores"):
            (tmp_path / f"{name}.json").write_text(json.dumps(run[name]))
        return tmp_path

    shutil.copy(RUN / "selected.json", tmp_path / "selected.json")
    return write


def criteria(**scores):
    return {name: {"score": scores.get(name, 0), "reason": f"Reason for {name}."} for name in CRITERIA}


def make_score(idea_id, lens, rubric, **scores):
    c = criteria(**scores)
    return {"idea_id": idea_id, "lens": lens, "criteria": c, "total": compute_total(c, rubric)}


def score_errors(score, rubric, ideas):
    """Errors for one score; the other fixture ideas are left unscored on purpose."""
    errors = check_scores({"week": "2026-W42", "scores": [score]}, ideas, rubric)
    return [e for e in errors if not e.endswith("has no score")]


# Schemas


@pytest.mark.parametrize("name", ["brief", "idea", "score", "scan_item"])
def test_schemas_are_valid_json_schema(name):
    Draft202012Validator.check_schema(load_schema(name))


def test_fixture_run_is_valid(run, rubric):
    errors, data = validate_run(RUN, run["selected"], rubric)
    assert errors == []
    assert [e["idea"]["idea_id"] for e in data["shortlist"]] == ["2026-W42-01", "2026-W42-02"]


# Rubric maths: total = sum of weight x score / 5


def test_weights_sum_to_100(rubric):
    assert sum(rubric["weights"].values()) == 100


@pytest.mark.parametrize(
    "scores, total",
    [
        ({name: 5 for name in CRITERIA}, 100),
        ({name: 0 for name in CRITERIA}, 0),
        # 25*5/5 + 20*4/5 + 15*4/5 + 15*4/5 + 15*5/5 + 10*3/5 = 25+16+12+12+15+6
        ({"lens_fit": 5, "rahul_edge": 4, "build_size": 4, "demo": 4, "verifiable": 5, "distribution": 3}, 86),
        # 25*4/5 + 20*3/5 + 15*2/5 + 15*3/5 + 15*3/5 + 10*2/5 = 20+12+6+9+9+4
        ({"lens_fit": 4, "rahul_edge": 3, "build_size": 2, "demo": 3, "verifiable": 3, "distribution": 2}, 60),
        # 25*2/5 + 20*1/5 + 15*0/5 + 15*1/5 + 15*2/5 + 10*1/5 = 10+4+0+3+6+2
        ({"lens_fit": 2, "rahul_edge": 1, "build_size": 0, "demo": 1, "verifiable": 2, "distribution": 1}, 25),
    ],
)
def test_compute_total_worked_examples(rubric, scores, total):
    assert compute_total(criteria(**scores), rubric) == total


@pytest.mark.parametrize("name", CRITERIA)
def test_one_point_on_a_criterion_is_worth_weight_over_five(rubric, name):
    assert compute_total(criteria(**{name: 1}), rubric) == rubric["weights"][name] / 5


# Lens caps: AI PM only tops out at 85, gaming only at 95


@pytest.mark.parametrize("lens, cap", [("gaming_x_ai_pm", 100), ("gaming_only", 95), ("ai_pm_only", 85)])
def test_lens_cap(rubric, lens, cap):
    assert lens_cap(lens, rubric) == cap
    assert rubric["lens_caps"][lens] == cap


def test_ai_pm_only_idea_with_every_other_score_maxed_totals_85(rubric, run):
    best = {name: 5 for name in CRITERIA} | {"lens_fit": 2}
    score = make_score("2026-W42-02", "ai_pm_only", rubric, **best)
    assert score["total"] == 85
    assert score_errors(score, rubric, run["ideas"]["ideas"]) == []


def test_gaming_only_idea_with_every_other_score_maxed_totals_95(rubric, run):
    best = {name: 5 for name in CRITERIA} | {"lens_fit": 4}
    score = make_score("2026-W42-04", "gaming_only", rubric, **best)
    assert score["total"] == 95
    assert score_errors(score, rubric, run["ideas"]["ideas"]) == []


@pytest.mark.parametrize("lens, claimed", [("ai_pm_only", 5), ("ai_pm_only", 4), ("gaming_only", 5), ("gaming_x_ai_pm", 4)])
def test_lens_fit_score_must_match_the_lens(rubric, run, lens, claimed):
    score = make_score("2026-W42-02", lens, rubric, **({name: 5 for name in CRITERIA} | {"lens_fit": claimed}))
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert any("lens_fit/score" in e for e in errors)


def test_ai_pm_only_cannot_claim_more_than_85(rubric, run):
    score = make_score("2026-W42-02", "ai_pm_only", rubric, **({name: 5 for name in CRITERIA} | {"lens_fit": 2}))
    score["total"] = 90
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert any("criteria give 85" in e for e in errors)
    assert any("above the ai_pm_only cap of 85" in e for e in errors)


def test_total_must_match_criteria(rubric, run):
    score = copy.deepcopy(run["scores"]["scores"][0])
    score["total"] = 87
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert errors == ["scores.json/scores/0/total: 87 but the criteria give 86"]


@pytest.mark.parametrize("build", [1, 3])
def test_build_size_only_takes_rubric_values(rubric, run, build):
    score = copy.deepcopy(run["scores"]["scores"][0])
    score["criteria"]["build_size"]["score"] = build
    score["total"] = compute_total(score["criteria"], rubric)
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert any("build_size/score: must be one of" in e for e in errors)


# A score without a one-line reason fails


@pytest.mark.parametrize(
    "reason",
    [None, "", "   ", "too short", "First line.\nSecond line."],
    ids=["missing", "empty", "blank", "under-10-chars", "two-lines"],
)
def test_score_without_a_one_line_reason_fails(rubric, run, reason):
    score = copy.deepcopy(run["scores"]["scores"][0])
    if reason is None:
        del score["criteria"]["demo"]["reason"]
    else:
        score["criteria"]["demo"]["reason"] = reason
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert errors and all("criteria/demo" in e for e in errors)


def test_score_missing_a_criterion_fails(rubric, run):
    score = copy.deepcopy(run["scores"]["scores"][0])
    del score["criteria"]["distribution"]
    assert any("'distribution' is a required property" in e for e in score_errors(score, rubric, run["ideas"]["ideas"]))


@pytest.mark.parametrize("value", [6, -1, 4.5])
def test_criterion_score_is_an_integer_from_0_to_5(rubric, run, value):
    score = copy.deepcopy(run["scores"]["scores"][0])
    score["criteria"]["demo"]["score"] = value
    assert any("criteria/demo/score" in e for e in score_errors(score, rubric, run["ideas"]["ideas"]))


def test_every_surviving_idea_needs_a_score(rubric, run):
    scores = {"week": "2026-W42", "scores": run["scores"]["scores"][1:]}
    errors = check_scores(scores, run["ideas"]["ideas"], rubric)
    assert errors == ["scores.json: idea 2026-W42-01 has no score"]


def test_killed_ideas_are_not_scored(rubric, run):
    score = make_score("2026-W42-03", "ai_pm_only", rubric, lens_fit=2)
    errors = score_errors(score, rubric, run["ideas"]["ideas"])
    assert any("was killed by the originality gate" in e for e in errors)


def test_score_for_unknown_idea_fails(rubric, run):
    score = make_score("2026-W42-99", "ai_pm_only", rubric, lens_fit=2)
    assert any("no idea 2026-W42-99" in e for e in score_errors(score, rubric, run["ideas"]["ideas"]))


# Ideas and the originality gate


def idea_errors(run, rubric, mutate):
    ideas = copy.deepcopy(run["ideas"])
    mutate(ideas["ideas"])
    brief_ids = {b["id"] for b in run["briefs"]["briefs"]}
    return check_ideas(ideas, brief_ids, rubric)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda i: i[1]["originality"].update(differentiator=""), "originality/differentiator"),
        (lambda i: i[2]["originality"].update(kill_reason=""), "originality/kill_reason"),
        (lambda i: i[0]["originality"].update(evidence_urls=[]), "originality/evidence_urls"),
        (lambda i: i[0]["originality"]["searches"].update(github=["only one"]), "searches/github"),
        (lambda i: i[0]["originality"]["searches"].update(web=["only one"]), "searches/web"),
        (lambda i: i[0]["originality"].update(verdict="maybe"), "originality/verdict"),
        (lambda i: i[0].pop("originality"), "'originality' is a required property"),
        (lambda i: i[0]["originality"].update(evidence_urls=["http://insecure.example"]), "evidence_urls/0"),
    ],
    ids=[
        "differentiated-needs-differentiator",
        "killed-needs-reason",
        "clear-needs-evidence",
        "two-github-searches",
        "two-web-searches",
        "bad-verdict",
        "no-originality",
        "https-only",
    ],
)
def test_originality_rules(rubric, run, mutate, expected):
    errors = idea_errors(run, rubric, mutate)
    assert any(expected in e for e in errors), errors


def test_combine_move_needs_two_sources(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[1].update(source_ids=["acme/agent-1"]))
    assert any("source_ids" in e for e in errors)


def test_move_must_be_1_to_4(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[0].update(move=5))
    assert any("/move" in e for e in errors)


def test_idea_source_must_be_a_brief(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[0].update(source_ids=["nobody/nothing"]))
    assert any("no brief for nobody/nothing" in e for e in errors)


def test_idea_id_must_carry_the_week(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[0].update(idea_id="2026-W41-01"))
    assert any("must start with 2026-W42-" in e for e in errors)


def test_at_most_two_ideas_per_brief(rubric, run):
    def third(ideas):
        extra = copy.deepcopy(ideas[0])
        extra["idea_id"] = "2026-W42-06"
        ideas.append(extra)
        ideas[1]["source_ids"] = ["acme/agent-1", "9003"]  # already primary on agent-1

    errors = idea_errors(run, rubric, third)
    assert "ideas.json: 3 ideas from brief acme/agent-1; at most 2" in errors


def test_at_most_fifteen_ideas_per_week(rubric, run):
    def flood(ideas):
        base = ideas[0]
        ideas.clear()
        for n in range(16):
            idea = copy.deepcopy(base)
            idea["idea_id"] = f"2026-W42-{n + 1:02d}"
            ideas.append(idea)

    rubric = copy.deepcopy(rubric)
    rubric["brainstorm"]["max_per_brief"] = 99
    errors = idea_errors(run, rubric, flood)
    assert "ideas.json: 16 ideas; at most 15 per week" in errors


def test_duplicate_idea_ids_fail(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[1].update(idea_id="2026-W42-01"))
    assert any("appears 2 times" in e for e in errors)


def test_em_dash_in_an_idea_fails(rubric, run):
    errors = idea_errors(run, rubric, lambda i: i[0].update(one_liner="Watches telemetry \u2014 files tickets for LiveOps."))
    assert errors == ["ideas.json/ideas/0/one_liner: contains an en or em dash"]


# Briefs


def test_en_dash_in_a_copied_source_title_is_allowed(run):
    assert "\u2013" in run["briefs"]["briefs"][1]["title"]
    assert check_briefs(run["briefs"], run["selected"]) == []


def test_mechanism_that_names_the_product_fails(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["briefs"][2]["mechanism"] = "Level Designer turns a short text description into a tile grid."
    errors = check_briefs(briefs, run["selected"])
    assert errors == ["briefs.json/briefs/2/mechanism: names the product 'level-designer'; state the pattern instead"]


@pytest.mark.parametrize("field", ["problem", "user", "mechanism", "why_now", "evidence"])
def test_brief_fields_are_required(run, field):
    briefs = copy.deepcopy(run["briefs"])
    del briefs["briefs"][0][field]
    assert any(f"'{field}' is a required property" in e for e in check_briefs(briefs))


def test_problem_is_one_sentence_on_one_line(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["briefs"][0]["problem"] = "Teams lose hours.\nEvery week."
    assert any("briefs/0/problem" in e for e in check_briefs(briefs))


def test_every_selected_item_is_briefed_or_skipped(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["skipped"] = []
    errors = check_briefs(briefs, run["selected"])
    assert errors == ["briefs.json: selected item org/face-swap-demo has no brief and is not listed as skipped"]


def test_skipped_item_needs_a_reason(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["skipped"][0]["reason"] = " "
    assert "briefs.json/skipped/0: needs an id and a reason" in check_briefs(briefs, run["selected"])


def test_brief_url_must_match_the_selected_item(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["briefs"][0]["url"] = "https://github.com/acme/other"
    assert "briefs.json/briefs/0: source or url differs from the selected item" in check_briefs(briefs, run["selected"])


def test_brief_for_an_item_that_was_not_selected_fails(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["briefs"][0]["id"] = "acme/not-selected"
    errors = check_briefs(briefs, run["selected"])
    assert "briefs.json/briefs/0: id acme/not-selected is not in the selected items" in errors


def test_week_must_match_the_selected_file(run):
    briefs = copy.deepcopy(run["briefs"])
    briefs["week"] = "2026-W43"
    assert any("does not match the selected file" in e for e in check_briefs(briefs, run["selected"]))


# Shortlist


def test_shortlist_threshold_is_inclusive(rubric, run):
    ideas = run["ideas"]["ideas"]
    # 25 + 20 + 15 + 0 + 0 + 10 = 70
    at = make_score("2026-W42-01", "gaming_x_ai_pm", rubric, lens_fit=5, rahul_edge=5, build_size=5, distribution=5)
    # 25 + 20 + 12 + 0 + 3 + 6 = 66
    below = make_score("2026-W42-04", "gaming_x_ai_pm", rubric, lens_fit=5, rahul_edge=5, build_size=4, verifiable=1, distribution=3)
    assert (at["total"], below["total"]) == (70, 66)
    assert [e["idea"]["idea_id"] for e in shortlist(ideas, [at, below], rubric)] == ["2026-W42-01"]


def test_shortlist_drops_neither_lens_and_killed_ideas(rubric, run):
    ideas = run["ideas"]["ideas"]
    neither = make_score("2026-W42-05", "neither", rubric, **({n: 5 for n in CRITERIA} | {"lens_fit": 0}))
    killed = make_score("2026-W42-03", "gaming_x_ai_pm", rubric, **{n: 5 for n in CRITERIA})
    assert neither["total"] == 75
    assert shortlist(ideas, [neither, killed], rubric) == []


def test_shortlist_keeps_at_most_three_highest_first(rubric, run):
    base = run["ideas"]["ideas"][0]
    ideas, scores = [], []
    for n, edge in enumerate([1, 5, 3, 4, 2], 1):
        idea = copy.deepcopy(base)
        idea["idea_id"] = f"2026-W42-{n:02d}"
        ideas.append(idea)
        scores.append(make_score(idea["idea_id"], "gaming_x_ai_pm", rubric, lens_fit=5, rahul_edge=edge, build_size=5, demo=5, verifiable=5))
    picked = shortlist(ideas, scores, rubric)
    # 25 + 4 x edge + 15 + 15 + 15 + 0
    assert [e["score"]["total"] for e in picked] == [90, 86, 82]
    assert [e["idea"]["idea_id"] for e in picked] == ["2026-W42-02", "2026-W42-04", "2026-W42-03"]


def test_shortlist_ties_break_on_idea_id(rubric, run):
    ideas = run["ideas"]["ideas"]
    a = make_score("2026-W42-04", "gaming_x_ai_pm", rubric, **{n: 5 for n in CRITERIA})
    b = make_score("2026-W42-01", "gaming_x_ai_pm", rubric, **{n: 5 for n in CRITERIA})
    assert [e["idea"]["idea_id"] for e in shortlist(ideas, [a, b], rubric)] == ["2026-W42-01", "2026-W42-04"]


# Run directory and CLI


def test_missing_file_is_reported(tmp_path):
    errors, data = validate_run(tmp_path)
    assert data is None
    assert errors == ["briefs.json: missing", "ideas.json: missing", "scores.json: missing"]


def test_invalid_json_is_reported(run_dir):
    path = run_dir()
    (path / "scores.json").write_text("{not json")
    errors, _ = validate_run(path)
    assert len(errors) == 1 and errors[0].startswith("scores.json: not valid JSON")


def test_idea_and_score_errors_are_reported_together(run, run_dir, rubric):
    run["ideas"]["ideas"][0]["originality"]["evidence_urls"] = []
    run["scores"]["scores"][1]["criteria"]["demo"]["reason"] = ""
    errors, _ = validate_run(run_dir(), run["selected"], rubric)
    assert any("ideas/0/originality/evidence_urls" in e for e in errors)
    assert any("scores/1/criteria/demo/reason" in e for e in errors)


def test_cli_passes_and_prints_shortlist(run_dir, capsys):
    path = run_dir()
    assert main([str(path), "--selected", str(path / "selected.json")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("ok: 3 briefs, 5 ideas (1 killed), 4 scores")
    assert "86.00  2026-W42-01  LiveOps incident filer  (clear)" in out


def test_cli_json_output(run_dir, capsys):
    path = run_dir()
    assert main([str(path), "--selected", str(path / "selected.json"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [e["score"]["total"] for e in data] == [86, 85]


def test_cli_fails_with_every_error(run, run_dir, capsys):
    run["scores"]["scores"][0]["total"] = 1
    run["scores"]["scores"][0]["criteria"]["demo"]["reason"] = ""
    path = run_dir()
    assert main([str(path), "--selected", str(path / "selected.json")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAILED:")
    assert "scores/0/criteria/demo/reason" in err


def test_rubric_file_is_what_the_spec_says():
    rubric = load_rubric(ROOT / "config" / "rubric.yaml")
    assert rubric["weights"] == {
        "lens_fit": 25,
        "rahul_edge": 20,
        "build_size": 15,
        "demo": 15,
        "verifiable": 15,
        "distribution": 10,
    }
    assert rubric["shortlist"] == {"threshold": 70, "max_ideas": 3}
    assert rubric["lens"] == {"gaming_x_ai_pm": 5, "gaming_only": 4, "ai_pm_only": 2, "neither": 0}


# Review fixes: malformed input, product names, the selected file


def test_validator_is_built_once_per_schema():
    from scripts.validate import validator_for

    assert validator_for("idea") is validator_for("idea")


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda b: b.update(skipped=None), "briefs.json/skipped: must be a list"),
        (lambda b: b["briefs"].append("not a brief"), "briefs.json/briefs/3: 'not a brief' is not of type 'object'"),
    ],
    ids=["null-skipped", "string-brief"],
)
def test_malformed_briefs_are_reported_not_raised(run, mutate, expected):
    briefs = copy.deepcopy(run["briefs"])
    mutate(briefs)
    assert expected in check_briefs(briefs, run["selected"])


def test_unhashable_week_is_reported_not_raised(run, run_dir, rubric):
    run["ideas"]["week"] = ["2026-W42"]
    errors, _ = validate_run(run_dir(), run["selected"], rubric)
    assert "ideas.json/week: must be an ISO week like 2026-W42" in errors


@pytest.mark.parametrize(
    "repo, mechanism, flagged",
    [
        ("someone/browser-agent", "An agent drives a real browser from a plain-language task.", False),
        ("someone/agents", "Several agents split a task and merge their results.", False),
        ("someone/tally", "A counter totally replaces the manual count of votes.", False),
        ("someone/tally", "Tally counts votes from a shared sheet.", True),
        ("someone/deepseek-harness", "A plugin core like deepseek harness, minus the brand.", True),
    ],
)
def test_product_name_check(run, repo, mechanism, flagged):
    briefs = copy.deepcopy(run["briefs"])
    brief = briefs["briefs"][0]
    brief.update(id=repo, url=f"https://github.com/{repo}", mechanism=mechanism)
    errors = [e for e in check_briefs(briefs) if "names the product" in e]
    assert bool(errors) is flagged


def test_cli_fails_when_the_selected_file_is_missing(run, run_dir, capsys):
    run["briefs"]["week"] = run["ideas"]["week"] = run["scores"]["week"] = "1999-W01"
    for idea in run["ideas"]["ideas"]:
        idea["idea_id"] = idea["idea_id"].replace("2026-W42", "1999-W01")
    for score in run["scores"]["scores"]:
        score["idea_id"] = score["idea_id"].replace("2026-W42", "1999-W01")
    path = run_dir()
    assert main([str(path)]) == 1
    assert "1999-W01.selected.json not found" in capsys.readouterr().err
    assert main([str(path), "--no-selected"]) == 0
    assert "selected items not checked (--no-selected)" in capsys.readouterr().out
