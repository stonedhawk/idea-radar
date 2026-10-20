"""The scan workflow's commit step, run against throwaway git repos."""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest
import yaml

from tests.conftest import ROOT

pytestmark = pytest.mark.skipif(not shutil.which("git") or not shutil.which("bash"), reason="needs git and bash")

WORKFLOW = ROOT / ".github" / "workflows" / "scan.yml"


def commit_step() -> str:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["scan"]["steps"]
    return next(s["run"] for s in steps if s.get("name") == "Commit scan")


@pytest.fixture
def git_env(tmp_path):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def git(*args, cwd=tmp_path):
        return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout

    return env, git


def test_commit_step_rebases_when_main_moved_during_the_scan(tmp_path, git_env):
    env, git = git_env
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", "-b", "main", str(remote))
    git("clone", "-q", str(remote), "seed")
    (tmp_path / "seed" / "README.md").write_text("seed\n")
    git("add", "README.md", cwd=tmp_path / "seed")
    git("commit", "-qm", "seed", cwd=tmp_path / "seed")
    git("push", "-q", "origin", "main", cwd=tmp_path / "seed")

    # The runner checks out main, then someone merges a PR while it collects.
    git("clone", "-q", "--depth", "1", f"file://{remote}", "runner")  # as actions/checkout does
    (tmp_path / "seed" / "AGENTS.md").write_text("merged meanwhile\n")
    git("add", "AGENTS.md", cwd=tmp_path / "seed")
    git("commit", "-qm", "merged PR", cwd=tmp_path / "seed")
    git("push", "-q", "origin", "main", cwd=tmp_path / "seed")

    runner = tmp_path / "runner"
    (runner / "data" / "scans").mkdir(parents=True)
    (runner / "data" / "scans" / "2026-W43.json").write_text("{}\n")
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", commit_step()],
        cwd=runner,
        env={**env, "WEEK": "2026-W43", "GITHUB_REF_NAME": "main"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("log", "--format=%s", "main", cwd=remote).split("\n")[:3] == ["scan: 2026-W43", "merged PR", "seed"]
