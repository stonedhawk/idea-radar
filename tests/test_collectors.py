"""Collector parsing and HTTP retry behaviour, from fixtures only."""
from __future__ import annotations

import io
import json
import urllib.error
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from collectors import common, github, hf, hn
from tests.conftest import load_fixture

FETCHED = "2026-10-15T01:30:00Z"
TODAY = date(2026, 10, 15)


@pytest.fixture
def gh_cfg(config):
    return {**config["github"], "topics": ["ai-agents", "mcp"]}


# GitHub


def test_github_queries_follow_the_spec(config):
    queries = github.build_queries(config["github"], TODAY)
    assert len(queries) == 2 * len(config["github"]["topics"])
    assert queries[0] == ("ai-agents", "topic:ai-agents created:>2026-09-15 stars:>30")
    assert queries[1] == ("ai-agents", "topic:ai-agents pushed:>2026-10-08 stars:>500")


def test_github_search_url_sorts_by_stars_top_30(config):
    params = parse_qs(urlparse(github.search_url("topic:mcp", config["github"]["per_query"])).query)
    assert params == {"q": ["topic:mcp"], "sort": ["stars"], "order": ["desc"], "per_page": ["30"]}


def test_github_collect_dedupes_and_keeps_first_topic(gh_cfg, fake_fetch):
    sleeps = []
    items = github.collect(gh_cfg, token="t", today=TODAY, fetched_at=FETCHED, fetch=fake_fetch, sleep=sleeps.append)
    ids = [it["id"] for it in items]
    assert ids == ["acme/agent-kit", "acme/brand-new", "bigco/orchestrator", "someone/mcp-server-fork"]
    assert all(it["primary_topic"] == "ai-agents" for it in items[:3])
    assert items[3]["primary_topic"] == "mcp"
    # 4 queries, a pause between each pair, none before the first.
    assert len(fake_fetch.calls) == 4
    assert sleeps == [gh_cfg["sleep_seconds"]] * 3


def test_github_collect_sends_the_token(gh_cfg, fake_fetch):
    github.collect(gh_cfg, token="secret", today=TODAY, fetched_at=FETCHED, fetch=fake_fetch, sleep=lambda s: None)
    assert all(headers["Authorization"] == "Bearer secret" for _, headers in fake_fetch.calls)


def test_github_normalize_fields():
    repo = load_fixture("github_search.json")["ai-agents:new"]["items"][1]
    item = github.normalize(repo, "ai-agents", FETCHED)
    assert item["description"] == ""  # null in the API
    assert item["license"] is None
    assert item["stars"] == 70
    assert item["fork"] is False and item["archived"] is False


def test_github_normalize_keeps_fork_flag():
    repo = load_fixture("github_search.json")["mcp:active"]["items"][0]
    item = github.normalize(repo, "mcp", FETCHED)
    assert item["fork"] is True
    assert item["license"] == "NOASSERTION"


@pytest.mark.parametrize("code, expected", [(200, True), (404, False)])
def test_readme_checker(code, expected):
    seen = []
    check = github.readme_checker("t", status=lambda url, headers: seen.append(url) or code)
    assert check("acme/agent-kit") is expected
    assert seen == ["https://api.github.com/repos/acme/agent-kit/readme"]


def test_readme_checker_raises_on_unexpected_status():
    check = github.readme_checker("t", status=lambda url, headers: 451)
    with pytest.raises(common.FetchError):
        check("acme/agent-kit")


# Show HN


def test_hn_url_filters(config):
    params = parse_qs(urlparse(hn.build_url(config["show_hn"], now_ts=1_800_000_000, page=0)).query)
    assert params["tags"] == ["show_hn"]
    assert params["numericFilters"] == [f"created_at_i>{1_800_000_000 - 7 * 86400},points>20"]


def test_hn_collect(config, fake_fetch):
    items = hn.collect(config["show_hn"], now_ts=1_792_050_000, fetched_at=FETCHED, fetch=fake_fetch)
    assert len(fake_fetch.calls) == 1  # nbPages is 1
    first, second = items
    assert first["id"] == "50092470"
    assert first["url"] == "https://news.ycombinator.com/item?id=50092470"
    assert first["link"] == "https://petal.example/"
    assert first["traction"] == 148.0
    assert first["description"] == "Hi HN! We built a screen sharing tool & open-sourced it."
    assert second["link"] is None
    assert second["description"] == ""


def test_hn_stops_at_max_pages(config):
    calls = []

    def fetch(url, headers):
        calls.append(url)
        return {"hits": [], "nbPages": 50}

    hn.collect(config["show_hn"], now_ts=0, fetched_at=FETCHED, fetch=fetch)
    assert len(calls) == config["show_hn"]["max_pages"]


# Hugging Face


def test_hf_url_expands_card_data(config):
    params = parse_qs(urlparse(hf.build_url(config["hf_spaces"])).query)
    assert params["sort"] == ["trendingScore"]
    assert params["limit"] == ["100"]
    assert "cardData" in params["expand[]"]


def test_hf_collect(config, fake_fetch):
    items = hf.collect(config["hf_spaces"], fetched_at=FETCHED, fetch=fake_fetch)
    jev = items[1]
    assert jev["title"] == "Jev Decision Index"
    assert jev["description"] == "Rank decisions by evidence"
    assert jev["license"] == "apache-2.0"
    assert jev["topics"] == ["static"]
    assert jev["traction"] == 136.0
    assert jev["url"] == "https://huggingface.co/spaces/multimodalart/jev-decision-index"
    no_card = items[2]
    assert no_card["title"] == "org/no-card"
    assert no_card["topics"] == ["docker", "mcp-server"]


# HTTP helpers


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_get_json_retries_once_then_succeeds(monkeypatch):
    attempts = []

    def urlopen(req, timeout):
        attempts.append(req.full_url)
        if len(attempts) == 1:
            raise urllib.error.URLError("reset")
        return _Resp(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    assert common.get_json("https://example.com/x", sleep=lambda s: None) == {"ok": True}
    assert len(attempts) == 2


def test_get_json_fails_after_two_errors(monkeypatch):
    attempts = []

    def urlopen(req, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(req.full_url, 502, "bad gateway", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    with pytest.raises(common.FetchError):
        common.get_json("https://example.com/x", sleep=lambda s: None)
    assert len(attempts) == 2


def test_get_status_returns_404_without_retry(monkeypatch):
    attempts = []

    def urlopen(req, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    assert common.get_status("https://example.com/x", sleep=lambda s: None) == 404
    assert len(attempts) == 1


def test_get_status_retries_rate_limit(monkeypatch):
    def urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "rate limited", {}, None)

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    with pytest.raises(common.FetchError):
        common.get_status("https://example.com/x", sleep=lambda s: None)


def test_make_item_rejects_unknown_source():
    with pytest.raises(ValueError):
        common.make_item(
            source="reddit", id="1", url="https://x", title="", description="", topics=[],
            language=None, license=None, traction=0, traction_kind="hn_points",
            created_at="", fetched_at="",
        )
