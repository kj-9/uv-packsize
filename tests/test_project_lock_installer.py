"""Network-free tests for the private validated project/lock installer bridge."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from uv_packsize.models import BuildPolicy
from uv_packsize.project_lock_installer import (
    _WINDOWS_PROCESS_ENVIRONMENT_KEYS,
    ProjectLockInstallError,
    ProjectLockInstallErrorReason,
    _run_uv_sync,
    install_validated_project_lock,
)
from uv_packsize.project_lock_reader import _read_validated_project_lock

PROJECT = """\
[project]
name = "Example_Project"

[project.optional-dependencies]
speed = []

[dependency-groups]
test = []
"""

LOCK = """\
version = 1
revision = 3
requires-python = ">=3.10"

[options]
prerelease-mode = "disallow"

[[package]]
name = "example-project"
version = "1.0.0"
source = { editable = "." }

[package.optional-dependencies]
speed = [{ name = "speed-dep" }]

[package.dev-dependencies]
test = [{ name = "test-dep" }]

[[package]]
name = "speed-dep"
version = "1.0.0"
source = { registry = "https://index.example.invalid/simple" }

[[package]]
name = "test-dep"
version = "1.0.0"
source = { registry = "https://index.example.invalid/simple" }
"""


def _snapshot(
    tmp_path: Path,
    *,
    dependency_groups: tuple[str, ...] = (),
    all_groups: bool = False,
    extras: tuple[str, ...] = (),
    project_text: str = PROJECT,
):
    project = tmp_path / "user-project.toml"
    lock = tmp_path / "user.lock"
    project.write_text(project_text)
    lock.write_text(LOCK)
    return (
        _read_validated_project_lock(
            project,
            lock,
            dependency_groups=dependency_groups,
            all_groups=all_groups,
            extras=extras,
        ),
        project,
        lock,
    )


def test_stages_same_validated_bytes_with_explicit_safe_argv_and_cleans_up(tmp_path):
    snapshot, project, lock = _snapshot(
        tmp_path,
        dependency_groups=("test",),
        extras=("speed",),
    )
    expected_project = project.read_bytes()
    expected_lock = lock.read_bytes()
    observed_command: list[str] = []
    observed_stage: Path | None = None
    observed_target: Path | None = None
    existing_prefix = tmp_path / "existing-prefix"
    existing_prefix.mkdir()
    (existing_prefix / "keep.txt").write_text("keep")

    # The bridge must use the bytes captured before this later input mutation.
    project.write_text('private = "changed-after-validation"\n')
    lock.write_text('private = "changed-after-validation"\n')

    def run(command: list[str], environment: dict[str, str]):
        nonlocal observed_stage, observed_target
        stage = Path(command[command.index("--project") + 1])
        staged_project = stage / "pyproject.toml"
        staged_lock = stage / "uv.lock"
        target = Path(environment["UV_PROJECT_ENVIRONMENT"])
        observed_command.extend(command)
        observed_stage = stage
        observed_target = target
        assert staged_project.read_bytes() == expected_project
        assert staged_lock.read_bytes() == expected_lock
        assert target.is_absolute()
        return subprocess.CompletedProcess(
            command, 0, "private output", "private error"
        )

    def collect(target: Path) -> str:
        assert target == observed_target
        return "collected"

    assert (
        install_validated_project_lock(
            snapshot,
            build_policy=BuildPolicy.WHEEL_ONLY,
            collect_inventory=collect,
            run_uv_sync=run,
        )
        == "collected"
    )

    assert observed_stage is not None
    assert observed_target is not None
    assert observed_command == [
        "uv",
        "sync",
        "--project",
        str(observed_stage),
        "--locked",
        "--no-install-project",
        "--no-default-groups",
        "--group",
        "test",
        "--extra",
        "speed",
        "--no-build",
    ]
    assert "--lockfile" not in observed_command
    assert "--frozen" not in observed_command
    assert "workspace" not in " ".join(observed_command)
    assert not observed_stage.exists()
    assert not observed_target.exists()
    assert project.read_text() == 'private = "changed-after-validation"\n'
    assert lock.read_text() == 'private = "changed-after-validation"\n'
    assert (existing_prefix / "keep.txt").read_text() == "keep"


def test_all_groups_and_allow_build_are_projected_without_implicit_groups(tmp_path):
    snapshot, _, _ = _snapshot(tmp_path, all_groups=True, extras=("speed",))
    observed: list[str] = []

    def run(command: list[str], _environment: dict[str, str]):
        observed.extend(command)
        return subprocess.CompletedProcess(command, 0)

    assert (
        install_validated_project_lock(
            snapshot,
            build_policy=BuildPolicy.ALLOW_BUILD,
            collect_inventory=lambda _target: "ok",
            run_uv_sync=run,
        )
        == "ok"
    )

    assert "--all-groups" in observed
    assert "--group" not in observed
    assert observed.count("--no-default-groups") == 1
    assert "--extra" in observed
    assert "speed" in observed
    assert "--no-build" not in observed


@pytest.mark.parametrize(
    ("failure", "expected_reason"),
    [
        ("uv", ProjectLockInstallErrorReason.UV_SYNC_FAILED),
        ("inventory", ProjectLockInstallErrorReason.INVENTORY_FAILED),
        ("unexpected", ProjectLockInstallErrorReason.UNEXPECTED),
    ],
)
def test_failure_paths_are_sanitized_and_always_clean_temporary_files(
    tmp_path, failure, expected_reason
):
    snapshot, _, _ = _snapshot(tmp_path)
    observed: dict[str, Path] = {}

    def run(command: list[str], environment: dict[str, str]):
        stage = Path(command[command.index("--project") + 1])
        observed["stage"] = stage
        observed["target"] = Path(environment["UV_PROJECT_ENVIRONMENT"])
        if failure == "uv":
            return subprocess.CompletedProcess(
                command,
                2,
                "https://user:token@example.invalid/stdout",
                "https://user:token@example.invalid/stderr",
            )
        if failure == "unexpected":
            raise RuntimeError("https://user:token@example.invalid/runner")
        return subprocess.CompletedProcess(command, 0)

    def collect(_target: Path) -> None:
        raise RuntimeError("https://user:token@example.invalid/inventory")

    with pytest.raises(ProjectLockInstallError) as captured:
        install_validated_project_lock(
            snapshot,
            build_policy=BuildPolicy.WHEEL_ONLY,
            collect_inventory=collect,
            run_uv_sync=run,
        )

    assert captured.value.reason is expected_reason
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)
    assert not observed["stage"].exists()
    assert not observed["target"].exists()


def test_cleanup_failure_is_a_sanitized_operational_error(tmp_path, monkeypatch):
    snapshot, _, _ = _snapshot(tmp_path)
    observed: dict[str, Path] = {}

    def run(command: list[str], environment: dict[str, str]):
        observed["root"] = Path(command[command.index("--project") + 1]).parent
        observed["target"] = Path(environment["UV_PROJECT_ENVIRONMENT"])
        return subprocess.CompletedProcess(command, 0)

    def cleanup_failure(_path: Path):
        raise OSError("https://user:token@example.invalid/cleanup")

    monkeypatch.setattr(
        "uv_packsize.project_lock_installer.shutil.rmtree", cleanup_failure
    )

    with pytest.raises(ProjectLockInstallError) as captured:
        install_validated_project_lock(
            snapshot,
            build_policy=BuildPolicy.WHEEL_ONLY,
            collect_inventory=lambda _target: "ok",
            run_uv_sync=run,
        )

    assert captured.value.reason is ProjectLockInstallErrorReason.CLEANUP_FAILED
    assert "token" not in str(captured.value)
    assert "example.invalid" not in str(captured.value)
    # Restore the test-owned root because its removal was deliberately mocked.
    monkeypatch.undo()
    shutil.rmtree(observed["root"])


def test_bridge_does_not_adopt_an_ambient_project_environment(tmp_path, monkeypatch):
    snapshot, _, _ = _snapshot(tmp_path)
    ambient = tmp_path / "ambient-prefix"
    ambient.mkdir()
    (ambient / "keep.txt").write_text("keep")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(ambient))
    observed_environment: dict[str, str] = {}

    def run(command: list[str], environment: dict[str, str]):
        observed_environment.update(environment)
        return subprocess.CompletedProcess(command, 0)

    install_validated_project_lock(
        snapshot,
        build_policy=BuildPolicy.WHEEL_ONLY,
        collect_inventory=lambda _target: None,
        run_uv_sync=run,
    )

    assert Path(observed_environment["UV_PROJECT_ENVIRONMENT"]) != ambient
    assert (ambient / "keep.txt").read_text() == "keep"
    assert os.environ["UV_PROJECT_ENVIRONMENT"] == str(ambient)


@pytest.mark.parametrize(
    ("build_policy", "expected_build_option"),
    [
        (BuildPolicy.WHEEL_ONLY, "--no-build"),
        (BuildPolicy.ALLOW_BUILD, None),
    ],
)
def test_bridge_ignores_ambient_uv_and_virtual_environment_controls(
    tmp_path, monkeypatch, build_policy, expected_build_option
):
    """Only the validated selection and explicit policy may control sync."""

    snapshot, _, _ = _snapshot(
        tmp_path,
        project_text=PROJECT + "\n[tool.uv]\nmanaged = true\n",
    )
    poisoned_environment = {
        "UV_PROJECT": "/private/secret/project",
        "UV_WORKING_DIR": "/private/secret/workdir",
        "UV_CONFIG_FILE": "/private/secret/uv.toml",
        "UV_NO_CONFIG": "0",
        "UV_PROJECT_ENVIRONMENT": "/private/secret/environment",
        "UV_INDEX_URL": "https://user:token@index.example.invalid/simple",
        "UV_DEFAULT_INDEX": "https://user:token@default.example.invalid/simple",
        "UV_FIND_LINKS": "/private/secret/wheels",
        "UV_CONSTRAINT": "/private/secret/constraints.txt",
        "UV_CACHE_DIR": "/private/secret/cache",
        "UV_NO_BUILD": "0",
        "UV_NO_BUILD_ISOLATION": "1",
        "UV_PYTHON": "/private/secret/python",
        "UV_MANAGED_PYTHON": "1",
        "UV_NO_SYNC": "1",
        "UV_ACTIVE": "1",
        "UV_UNRECOGNIZED_SETTING": "must-not-be-inherited",
        "VIRTUAL_ENV": "/private/secret/venv",
        "CONDA_PREFIX": "/private/secret/conda",
        "PIP_INDEX_URL": "https://user:token@pip.example.invalid/simple",
        "PIP_FIND_LINKS": "/private/secret/pip-wheels",
        "PYTHONHOME": "/private/secret/python-home",
        "PYTHONPATH": "/private/secret/python-path",
    }
    for key, value in poisoned_environment.items():
        monkeypatch.setenv(key, value)
    observed_command: list[str] | None = None
    observed_environment: dict[str, str] | None = None

    def run(command: list[str], environment: dict[str, str]):
        nonlocal observed_command, observed_environment
        observed_command = command
        observed_environment = environment
        return subprocess.CompletedProcess(command, 0)

    assert (
        install_validated_project_lock(
            snapshot,
            build_policy=build_policy,
            collect_inventory=lambda _target: "ok",
            run_uv_sync=run,
        )
        == "ok"
    )

    assert observed_environment is not None
    environment = observed_environment
    expected_keys = {
        "PATH",
        "UV_CACHE_DIR",
        "UV_PROJECT_ENVIRONMENT",
        "UV_NO_CONFIG",
    }
    if os.name == "nt":
        expected_keys.update(
            key for key in _WINDOWS_PROCESS_ENVIRONMENT_KEYS if key in os.environ
        )
    assert set(environment) == expected_keys
    assert environment["UV_NO_CONFIG"] == "1"
    assert Path(environment["UV_PROJECT_ENVIRONMENT"]).is_absolute()
    assert Path(environment["UV_CACHE_DIR"]) == (
        Path(environment["UV_PROJECT_ENVIRONMENT"]).parent / "uv-cache"
    )
    assert environment["UV_CACHE_DIR"] != poisoned_environment["UV_CACHE_DIR"]
    assert (
        environment["UV_PROJECT_ENVIRONMENT"]
        != poisoned_environment["UV_PROJECT_ENVIRONMENT"]
    )
    for key in poisoned_environment:
        if key not in {"UV_CACHE_DIR", "UV_PROJECT_ENVIRONMENT", "UV_NO_CONFIG"}:
            assert key not in environment

    assert observed_command is not None
    command = observed_command
    assert ("--no-build" in command) is (expected_build_option is not None)
    assert "--active" not in command


def test_default_runner_uses_the_isolated_stage_as_its_working_directory(
    tmp_path, monkeypatch
):
    stage = tmp_path / "stage"
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("uv_packsize.project_lock_installer.subprocess.run", fake_run)
    command = ["uv", "sync", "--project", str(stage), "--locked"]

    _run_uv_sync(command, {"UV_PROJECT_ENVIRONMENT": str(tmp_path / "target")})

    assert captured["cwd"] == stage
