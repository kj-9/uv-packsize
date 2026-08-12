"""Offline public project/lock CLI coverage using real ``uv sync``."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

from local_wheel_factory import build_wheelhouse

PROJECT_ROOT = Path(__file__).parents[1]
_ROOT_A = "uv-packsize-fixture-root-a"
_ROOT_B = "uv-packsize-fixture-root-b"
_SHARED = "uv-packsize-fixture-shared"


def test_real_uv_sync_project_lock_selects_only_explicit_groups_and_extras(tmp_path):
    project, lockfile, environment = _locked_inputs(tmp_path)
    original = _input_bytes(project, lockfile)

    default = _run_project(environment, project, lockfile, "--json")
    group = _run_project(environment, project, lockfile, "--group", "test", "--json")
    extra = _run_project(environment, project, lockfile, "--extra", "feature", "--json")

    assert default.returncode == group.returncode == extra.returncode == 0
    default_document = json.loads(default.stdout)
    group_document = json.loads(group.stdout)
    extra_document = json.loads(extra.stdout)
    assert _distribution_names(default_document) == {_ROOT_A, _SHARED}
    assert _distribution_names(group_document) == {_ROOT_A, _ROOT_B, _SHARED}
    assert _distribution_names(extra_document) == {_ROOT_A, _ROOT_B, _SHARED}
    assert default_document["schema_version"] == 3
    assert default_document["context"]["input_kind"] == "project-lock"
    assert default_document["context"]["dependency_group_selection"] == "none"
    assert default_document["context"]["dependency_groups"] == []
    assert default_document["context"]["extras"] == []
    assert group_document["context"]["dependency_group_selection"] == "explicit"
    assert group_document["context"]["dependency_groups"] == ["test"]
    assert extra_document["context"]["extras"] == ["feature"]
    assert _input_bytes(project, lockfile) == original
    _assert_temporary_work_is_cleaned(tmp_path)


def test_real_uv_sync_project_lock_baseline_write_diff_and_budget(tmp_path):
    project, lockfile, environment = _locked_inputs(tmp_path)
    original = _input_bytes(project, lockfile)
    baseline = tmp_path / "project-baseline.json"

    recorded = _run_project(
        environment, project, lockfile, "--json", "--write-baseline", str(baseline)
    )
    assert recorded.returncode == 0, recorded.stderr
    assert baseline.read_text() == recorded.stdout
    assert json.loads(recorded.stdout)["schema_version"] == 3

    same = _run_project(
        environment, project, lockfile, "--baseline", str(baseline), "--comparison-json"
    )
    assert same.returncode == 0, same.stderr
    assert json.loads(same.stdout)["schema_version"] == 2
    assert json.loads(same.stdout)["context"]["lock_changed"] is False

    # Whitespace does not change the locked resolution but does change the
    # opaque lock fingerprint; the v2 comparison exposes only the boolean.
    lockfile.write_bytes(lockfile.read_bytes() + b"\n")
    changed = _run_project(
        environment, project, lockfile, "--baseline", str(baseline), "--comparison-json"
    )
    assert changed.returncode == 0, changed.stderr
    assert json.loads(changed.stdout)["context"]["lock_changed"] is True

    budget = _run_project(environment, project, lockfile, "--json", "--max-total", "0")
    assert budget.returncode == 5
    assert budget.stdout == ""
    assert _input_bytes(project, lockfile)["project"] == original["project"]
    _assert_temporary_work_is_cleaned(tmp_path)


def test_real_uv_sync_project_lock_rich_analysis_and_comparison(tmp_path):
    project, lockfile, environment = _locked_inputs(tmp_path)
    baseline = tmp_path / "project-baseline.json"
    recorded = _run_project(environment, project, lockfile, "--json")
    baseline.write_text(recorded.stdout)

    analysis = _run_project(
        environment, project, lockfile, "--group", "test", "--report", "rich"
    )
    comparison = _run_project(
        environment,
        project,
        lockfile,
        "--baseline",
        str(baseline),
        "--report",
        "rich",
    )

    assert recorded.returncode == analysis.returncode == comparison.returncode == 0
    assert analysis.stdout.startswith("--- Rich Analysis Summary ---\n")
    assert "Input kind: project-lock" in analysis.stdout
    assert "Build policy: wheel-only" in analysis.stdout
    assert "--- Largest Distributions (Showing 3 of 3) ---" in analysis.stdout
    assert "1.0.0" not in analysis.stdout
    assert comparison.stdout.startswith("--- Rich Comparison Summary ---\n")
    assert "Input kind: project-lock" in comparison.stdout
    assert "Lock changed: no" in comparison.stdout
    assert "lock_identity" not in comparison.stdout
    _assert_temporary_work_is_cleaned(tmp_path)


def test_real_uv_sync_stale_lock_is_sanitized_and_cleans_temporary_prefix(tmp_path):
    project, lockfile, environment = _locked_inputs(tmp_path)
    project_bytes = project.read_bytes()
    lock_bytes = lockfile.read_bytes()
    project.write_bytes(
        project_bytes.replace(
            b'requires-python = ">=3.10"', b'requires-python = ">=3.11"'
        )
    )

    completed = _run_project(environment, project, lockfile)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "Calculating size for the selected project lock..." in completed.stderr
    assert "Installing the selected project lock..." in completed.stderr
    assert "uv-sync-failed" in completed.stderr
    assert str(project) not in completed.stderr
    assert str(lockfile) not in completed.stderr
    assert "root-b==1.0.0" not in completed.stderr
    assert lockfile.read_bytes() == lock_bytes
    _assert_temporary_work_is_cleaned(tmp_path)


def test_project_lock_exit_two_three_and_four_are_public_and_redacted(tmp_path):
    project, lockfile, environment = _locked_inputs(tmp_path)

    usage = _run_project(environment, project, lockfile, _ROOT_A)
    assert usage.returncode == 2
    assert usage.stdout == ""

    malformed = tmp_path / "malformed.lock"
    malformed.write_text('token = "https://user:secret@example.invalid"\n')
    invalid = _run_project(environment, project, malformed, "--json")
    assert invalid.returncode == 3
    assert invalid.stdout == ""
    assert "secret" not in invalid.stderr
    assert str(malformed) not in invalid.stderr

    fresh_baseline = tmp_path / "fresh.json"
    fresh = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv_packsize",
            "--python",
            sys.executable,
            "--json",
            _ROOT_A + "==1.0.0",
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    assert fresh.returncode == 0, fresh.stderr
    fresh_baseline.write_text(fresh.stdout)
    incompatible = _run_project(
        environment, project, lockfile, "--baseline", str(fresh_baseline)
    )
    assert incompatible.returncode == 4
    assert incompatible.stdout == ""
    assert str(fresh_baseline) not in incompatible.stderr


def _locked_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    project = tmp_path / "inputs" / "pyproject.toml"
    project.parent.mkdir()
    project.write_text(
        """
[project]
name = "uv-packsize-project-fixture"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = ["uv-packsize-fixture-root-a==1.0.0"]

[dependency-groups]
test = ["uv-packsize-fixture-root-b==1.0.0"]

[project.optional-dependencies]
feature = ["uv-packsize-fixture-root-b==1.0.0"]
"""
    )
    environment = _environment(tmp_path, wheelhouse)
    locked = subprocess.run(
        ["uv", "lock", "--offline", "--no-progress"],
        check=False,
        capture_output=True,
        cwd=project.parent,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    assert locked.returncode == 0, locked.stderr
    return project, project.parent / "uv.lock", environment


def _run_project(
    environment: dict[str, str], project: Path, lockfile: Path, *options: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "uv_packsize",
            "--project",
            str(project),
            "--lockfile",
            str(lockfile),
            *options,
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def _input_bytes(project: Path, lockfile: Path) -> dict[str, bytes]:
    return {"project": project.read_bytes(), "lock": lockfile.read_bytes()}


def _distribution_names(document: dict[str, object]) -> set[str]:
    distributions = document["distributions"]
    assert isinstance(distributions, list)
    names = set()
    for item in distributions:
        assert isinstance(item, dict)
        name = cast(dict[str, object], item)["name"]
        assert isinstance(name, str)
        names.add(name)
    return names


def _assert_temporary_work_is_cleaned(tmp_path: Path) -> None:
    temporary = tmp_path / "temporary"
    assert not list(temporary.glob("uv-packsize-project-lock-*"))


def _environment(tmp_path: Path, wheelhouse: Path) -> dict[str, str]:
    environment = {"PATH": os.environ["PATH"]}
    home = tmp_path / "home"
    temporary = tmp_path / "temporary"
    cache = tmp_path / "uv-cache"
    for directory in (home, temporary, cache):
        directory.mkdir()
    environment.update(
        {
            "UV_NO_INDEX": "1",
            "UV_FIND_LINKS": str(wheelhouse),
            "UV_OFFLINE": "1",
            "UV_NO_PROGRESS": "1",
            "UV_NO_CONFIG": "1",
            "UV_NO_CACHE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_CACHE_DIR": str(cache),
            "HOME": str(home),
            "TMPDIR": str(temporary),
            "TEMP": str(temporary),
            "TMP": str(temporary),
            "PYTHONUTF8": "1",
        }
    )
    return environment
