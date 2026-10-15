"""GitHub collector: REST repository search, two queries per topic (SPEC 6.2).

Traction is left as a placeholder here. scripts/scan.py replaces it with
velocity_7d once it has the star history (SPEC 6.3).
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from urllib.parse import urlencode

from .common import FetchError, get_json, get_status, make_item

API = "https://api.github.com"
SEARCH_URL = f"{API}/search/repositories"


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def build_queries(cfg: dict, today: date) -> list[tuple[str, str]]:
    """Return (topic, query) pairs: new repos, then established active repos."""
    new_since = today - timedelta(days=cfg["new_window_days"])
    active_since = today - timedelta(days=cfg["active_window_days"])
    queries = []
    for topic in cfg["topics"]:
        queries.append(
            (topic, f"topic:{topic} created:>{new_since.isoformat()} stars:>{cfg['new_min_stars']}")
        )
        queries.append(
            (topic, f"topic:{topic} pushed:>{active_since.isoformat()} stars:>{cfg['est_min_stars']}")
        )
    return queries


def search_url(query: str, per_page: int) -> str:
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    return f"{SEARCH_URL}?{urlencode(params)}"


def normalize(repo: dict, topic: str, fetched_at: str) -> dict:
    license_info = repo.get("license") or {}
    return make_item(
        source="github",
        id=repo["full_name"],
        url=repo["html_url"],
        title=repo["name"],
        description=repo.get("description") or "",
        topics=list(repo.get("topics") or []),
        language=repo.get("language"),
        license=license_info.get("spdx_id"),
        traction=0.0,
        traction_kind="velocity_7d_estimated",
        created_at=repo["created_at"],
        fetched_at=fetched_at,
        primary_topic=topic,
        stars=int(repo["stargazers_count"]),
        fork=bool(repo.get("fork")),
        archived=bool(repo.get("archived")),
    )


def collect(
    cfg: dict,
    *,
    token: str,
    today: date,
    fetched_at: str,
    fetch=get_json,
    sleep=time.sleep,
) -> list[dict]:
    """Run every query and return unique repos.

    A repo found by several queries keeps the topic of the first one, which
    becomes its primary topic for the diversity cap.
    """
    headers = auth_headers(token)
    seen: dict[str, dict] = {}
    for i, (topic, query) in enumerate(build_queries(cfg, today)):
        if i:
            sleep(cfg["sleep_seconds"])
        data = fetch(search_url(query, cfg["per_query"]), headers)
        for repo in data.get("items", []):
            seen.setdefault(repo["full_name"], normalize(repo, topic, fetched_at))
    return list(seen.values())


def readme_checker(token: str, *, status=get_status):
    """Return has_readme(full_name) backed by GET /repos/{full_name}/readme."""
    headers = auth_headers(token)

    def has_readme(full_name: str) -> bool:
        code = status(f"{API}/repos/{full_name}/readme", headers)
        if code == 200:
            return True
        if code == 404:
            return False
        raise FetchError(f"README check for {full_name} returned HTTP {code}")

    return has_readme
