"""Shared item model and HTTP helpers for the collectors.

Every source normalises to the shape in schemas/scan_item.json. The HTTP
helpers try twice, so a request that fails twice raises and fails the job.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "idea-radar (+https://github.com/stonedhawk/idea-radar)"

# Order matters: scan files and selected files list sources in this order.
SOURCES = ("github", "show_hn", "hf_space")

TRACTION_KINDS = (
    "velocity_7d_measured",
    "velocity_7d_estimated",
    "hn_points",
    "hf_trending",
)


class FetchError(RuntimeError):
    """A request failed on every attempt."""


def _request(url: str, headers: dict | None) -> urllib.request.Request:
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    merged.update(headers or {})
    return urllib.request.Request(url, headers=merged)


def get_json(
    url: str,
    headers: dict | None = None,
    *,
    attempts: int = 2,
    backoff: float = 5.0,
    timeout: float = 30.0,
    sleep=time.sleep,
) -> Any:
    """GET url and decode JSON, retrying once before raising FetchError."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(_request(url, headers), timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt + 1 < attempts:
            sleep(backoff)
    raise FetchError(f"GET {url} failed {attempts} times: {last}")


def get_status(
    url: str,
    headers: dict | None = None,
    *,
    attempts: int = 2,
    backoff: float = 5.0,
    timeout: float = 30.0,
    sleep=time.sleep,
) -> int:
    """Return the HTTP status for url.

    A 4xx is an answer (404 means "not there"), except 403 and 429, which on
    GitHub mean rate limiting and are retried like network errors.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(_request(url, headers), timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code not in (403, 429):
                return exc.code
            last = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt + 1 < attempts:
            sleep(backoff)
    raise FetchError(f"GET {url} failed {attempts} times: {last}")


def make_item(
    *,
    source: str,
    id: str,
    url: str,
    title: str,
    description: str,
    topics: list[str],
    language: str | None,
    license: str | None,
    traction: float,
    traction_kind: str,
    created_at: str,
    fetched_at: str,
    **extra: Any,
) -> dict:
    """Build one scan item. Source-specific fields go in extra."""
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    if traction_kind not in TRACTION_KINDS:
        raise ValueError(f"unknown traction_kind {traction_kind!r}")
    item = {
        "source": source,
        "id": id,
        "url": url,
        "title": title,
        "description": description,
        "topics": topics,
        "language": language,
        "license": license,
        "traction": traction,
        "traction_kind": traction_kind,
        "created_at": created_at,
        "fetched_at": fetched_at,
    }
    item.update(extra)
    return item
