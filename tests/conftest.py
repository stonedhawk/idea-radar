"""Shared fixtures. Every test runs with the network blocked."""
from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise RuntimeError("network access in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def schema() -> dict:
    return json.loads((ROOT / "schemas" / "scan_item.json").read_text())


class FakeFetch:
    """Serves fixture files in place of the three APIs and records each call."""

    def __init__(self):
        self.github = load_fixture("github_search.json")
        self.hn = load_fixture("hn_search.json")
        self.hf = load_fixture("hf_spaces.json")
        self.calls: list[tuple[str, dict | None]] = []

    def __call__(self, url: str, headers: dict | None = None):
        self.calls.append((url, headers))
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if parsed.netloc == "api.github.com":
            query = params["q"][0]
            topic = query.split()[0].removeprefix("topic:")
            kind = "new" if "created:>" in query else "active"
            return self.github.get(f"{topic}:{kind}", {"items": []})
        if parsed.netloc == "hn.algolia.com":
            return self.hn
        if parsed.netloc == "huggingface.co":
            return self.hf
        raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def fake_fetch() -> FakeFetch:
    return FakeFetch()
