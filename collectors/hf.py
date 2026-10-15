"""Hugging Face Spaces collector: the trendingScore feed (SPEC 6.1).

The list endpoint returns no title or description unless cardData is
expanded, so the request asks for it explicitly.
"""
from __future__ import annotations

from urllib.parse import urlencode

from .common import get_json, make_item

SPACES_URL = "https://huggingface.co/api/spaces"
SPACE_PAGE = "https://huggingface.co/spaces/{}"
EXPAND = ("cardData", "trendingScore", "likes", "createdAt", "sdk", "tags")


def build_url(cfg: dict) -> str:
    params = [("sort", "trendingScore"), ("limit", cfg["limit"])]
    params += [("expand[]", field) for field in EXPAND]
    return f"{SPACES_URL}?{urlencode(params)}"


def normalize(space: dict, fetched_at: str) -> dict:
    card = space.get("cardData") or {}
    license_value = card.get("license")
    if isinstance(license_value, list):
        license_value = ", ".join(str(v) for v in license_value)
    return make_item(
        source="hf_space",
        id=space["id"],
        url=SPACE_PAGE.format(space["id"]),
        title=card.get("title") or space["id"],
        description=card.get("short_description") or "",
        # Drop housekeeping tags such as "region:us".
        topics=[t for t in space.get("tags") or [] if ":" not in t],
        language=None,
        license=license_value,
        traction=float(space.get("trendingScore") or 0),
        traction_kind="hf_trending",
        created_at=space.get("createdAt") or "",
        fetched_at=fetched_at,
    )


def collect(cfg: dict, *, fetched_at: str, fetch=get_json) -> list[dict]:
    data = fetch(build_url(cfg), None)
    return [normalize(space, fetched_at) for space in data]
