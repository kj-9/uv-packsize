"""Network-free proof that the default installer never executes an sdist backend."""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
from pathlib import Path

from local_sdist_factory import build_sdist

PROJECT_ROOT = Path(__file__).parents[1]
_REQUIREMENT = "uv-packsize-fixture-sdist==1.0.0"
_PROCESS_ENVIRONMENT_NAMES = ("PATH", "SystemRoot", "WINDIR", "ComSpec", "PATHEXT")


def test_local_sdist_is_deterministic_and_contains_only_the_sentinel_backend(tmp_path):
    first = build_sdist(tmp_path / "first")
    second = build_sdist(tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == sorted(
            member.name for member in members
        )
        assert all(member.mtime == 0 and member.mode == 0o644 for member in members)
        pyproject = archive.extractfile(
            "uv-packsize-fixture-sdist-1.0.0/pyproject.toml"
        )
        backend = archive.extractfile(
            "uv-packsize-fixture-sdist-1.0.0/uv_packsize_fixture_sdist_backend.py"
        )
        assert pyproject is not None
        assert backend is not None
        pyproject_contents = pyproject.read()
        assert (
            b'build-backend = "uv_packsize_fixture_sdist_backend"' in pyproject_contents
        )
        assert b'backend-path = ["."]' in pyproject_contents
        assert b"UV_PACKSIZE_TEST_SENTINEL" in backend.read()


def test_default_wheel_only_install_rejects_local_sdist_without_running_backend(
    tmp_path,
):
    wheelhouse = tmp_path / "wheelhouse"
    build_sdist(wheelhouse)
    sentinel = tmp_path / "backend-was-imported"

    completed = _run_cli(tmp_path, wheelhouse, sentinel)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert not sentinel.exists()
    assert "Could not install the requested packages with the wheel-only policy" in (
        completed.stderr
    )
    assert "--allow-build only if you trust the package source" in completed.stderr
    assert "Error:" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert _REQUIREMENT not in completed.stderr
    assert str(tmp_path) not in completed.stderr
    assert "uv_packsize_fixture_sdist_backend" not in completed.stderr
    assert "UV_PACKSIZE_TEST_SENTINEL" not in completed.stderr


def _run_cli(
    tmp_path: Path, wheelhouse: Path, sentinel: Path
) -> subprocess.CompletedProcess[str]:
    environment = _integration_environment(tmp_path, wheelhouse, sentinel)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "uv_packsize",
            "--python",
            sys.executable,
            "--json",
            _REQUIREMENT,
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def _integration_environment(
    tmp_path: Path, wheelhouse: Path, sentinel: Path
) -> dict[str, str]:
    """Return only the variables needed for an offline, config-free uv run."""

    environment = {
        name: value
        for name in _PROCESS_ENVIRONMENT_NAMES
        if (value := os.environ.get(name)) is not None
    }
    home = tmp_path / "home"
    app_data = tmp_path / "app-data"
    local_app_data = tmp_path / "local-app-data"
    temporary_directory = tmp_path / "temporary"
    cache_directory = tmp_path / "uv-cache"
    for directory in (
        home,
        app_data,
        local_app_data,
        temporary_directory,
        cache_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    environment.update(
        {
            "UV_NO_INDEX": "1",
            "UV_FIND_LINKS": str(wheelhouse),
            "UV_OFFLINE": "1",
            "UV_NO_PROGRESS": "1",
            "UV_NO_CONFIG": "1",
            "UV_NO_CACHE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_CACHE_DIR": str(cache_directory),
            "UV_PACKSIZE_TEST_SENTINEL": str(sentinel),
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(app_data),
            "LOCALAPPDATA": str(local_app_data),
            "TMPDIR": str(temporary_directory),
            "TEMP": str(temporary_directory),
            "TMP": str(temporary_directory),
            "PYTHONUTF8": "1",
        }
    )
    return environment
