"""Show HN collector: Algolia search_by_date, points within the window (SPEC 6.1)."""
from __future__ import annotations

import html
import re
from urllib.parse import urlencode

from .common import get_json, make_item

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id={}"

_TAG = re.compile(r"<[^>]+>")


def build_url(cfg: dict, now_ts: int, page: int) -> str:
    since = now_ts - cfg["window_days"] * 86400
    params = {
        "tags": "show_hn",
        "numericFilters": f"created_at_i>{since},points>{cfg['min_points']}",
        "hitsPerPage": cfg["hits_per_page"],
        "page": page,
    }
    return f"{SEARCH_URL}?{urlencode(params)}"


def clean_text(text: str | None, limit: int = 500) -> str:
    """Strip HTML from a post body and collapse whitespace."""
    plain = html.unescape(_TAG.sub(" ", text or ""))
    return " ".join(plain.split())[:limit]


def normalize(hit: dict, fetched_at: str) -> dict:
    object_id = str(hit["objectID"])
    return make_item(
        source="show_hn",
        id=object_id,
        url=ITEM_URL.format(object_id),
        title=hit.get("title") or "",
        description=clean_text(hit.get("story_text")),
        topics=[],
        language=None,
        license=None,
        traction=float(hit.get("points") or 0),
        traction_kind="hn_points",
        created_at=hit["created_at"],
        fetched_at=fetched_at,
        link=hit.get("url") or None,
    )


def collect(cfg: dict, *, now_ts: int, fetched_at: str, fetch=get_json) -> list[dict]:
    items: dict[str, dict] = {}
    for page in range(cfg["max_pages"]):
        data = fetch(build_url(cfg, now_ts, page), None)
        for hit in data.get("hits", []):
            item = normalize(hit, fetched_at)
            items.setdefault(item["id"], item)
        if page + 1 >= data.get("nbPages", 0):
            break
    return list(items.values())
