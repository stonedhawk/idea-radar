"""AGENTS.md is the one instruction file, and it matches the repo (any agent can follow it)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.conftest import ROOT

AGENTS = (ROOT / "AGENTS.md").read_text()


def tracked(pattern: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", pattern], cwd=ROOT, capture_output=True, text=True, check=True)
    return [Path(name) for name in out.stdout.split("\0") if name]


def test_agents_md_sends_agents_to_the_spec():
    assert "Read `SPEC.md`" in AGENTS


def test_every_command_in_agents_md_exists():
    scripts = set(re.findall(r"python (scripts/[a-z_]+\.py)", AGENTS))
    assert scripts
    assert [s for s in sorted(scripts) if not (ROOT / s).is_file()] == []


@pytest.mark.parametrize(
    "folder, suffix",
    [("scripts", ".py"), ("prompts", ".md"), ("schemas", ".json"), ("config", ".yaml")],
)
def test_agents_md_names_every_step_file(folder, suffix):
    files = [p for p in (ROOT / folder).glob(f"*{suffix}") if p.name != "__init__.py"]
    assert files
    missing = [f"{folder}/{p.name}" for p in files if f"{folder}/{p.name}" not in AGENTS]
    assert missing == []


def test_agents_md_documents_every_env_var_the_code_reads():
    used = set()
    for path in tracked("*.py"):
        used |= set(re.findall(r"os\.environ\.get\(\"([A-Z_]+)\"\)", (ROOT / path).read_text()))
        used |= set(re.findall(r"^ENV_[A-Z_]+ = \"([A-Z_]+)\"", (ROOT / path).read_text(), re.M))
    assert {"GITHUB_TOKEN", "GH_TOKEN", "IDEA_RADAR_PUBLISH_DIR"} <= used
    assert [v for v in sorted(used) if f"`{v}`" not in AGENTS] == []


def test_no_model_ids_in_the_repo():
    """Models are picked in the agent, never in the repo."""
    model_id = re.compile(r"\b(claude-(opus|sonnet|haiku|fable)[-0-9a-z.]*|gpt-[0-9][-0-9a-z.]*|gemini-[0-9][-0-9a-z.]*)\b")
    offenders = []
    for path in tracked("*"):
        if path.parts[0] == "data" or not (ROOT / path).is_file():
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        offenders += [f"{path}: {m.group(0)}" for m in model_id.finditer(text)]
    assert offenders == []


def test_no_machine_paths_in_the_repo():
    """Every path is relative to the repo root, so any agent on any machine can run it."""
    # Built from parts so this file does not match itself.
    home = re.compile("|".join(["/" + "Users/", "/" + "home/[a-z]", r"[A-Z]:\\" + "Users"]))
    offenders = []
    for path in tracked("*"):
        if path.parts[0] == "data" or not (ROOT / path).is_file():
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if home.search(text):
            offenders.append(str(path))
    assert offenders == []
