"""Network-free CLI integration coverage using real local wheel installation."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from local_wheel_factory import build_wheelhouse

PROJECT_ROOT = Path(__file__).parents[1]
_ROOT_A = "uv-packsize-fixture-root-a"
_ROOT_B = "uv-packsize-fixture-root-b"
_SHARED = "uv-packsize-fixture-shared"
_REQUIREMENTS = (f"{_ROOT_A}==1.0.0", f"{_ROOT_B}==1.0.0")
_PROCESS_ENVIRONMENT_NAMES = ("PATH", "SystemRoot", "WINDIR", "ComSpec", "PATHEXT")


def test_local_wheels_are_deterministic_and_have_valid_record_rows(tmp_path):
    first_wheelhouse = tmp_path / "first"
    second_wheelhouse = tmp_path / "second"
    first = build_wheelhouse(first_wheelhouse)
    second = build_wheelhouse(second_wheelhouse)

    assert set(first) == {_ROOT_A, _ROOT_B, _SHARED}
    for name, first_wheel in first.items():
        second_wheel = second[name]
        assert first_wheel.read_bytes() == second_wheel.read_bytes()
        with zipfile.ZipFile(first_wheel) as archive:
            members = archive.infolist()
            member_names = [member.filename for member in members]
            assert member_names == sorted(member_names)
            assert len(member_names) == len(set(member_names))
            assert all(member.compress_type == zipfile.ZIP_STORED for member in members)
            assert all(member.date_time == (1980, 1, 1, 0, 0, 0) for member in members)
            record_names = [
                member.filename
                for member in members
                if member.filename.endswith("/RECORD")
            ]
            assert len(record_names) == 1
            record_name = record_names[0]
            record_rows = list(
                csv.reader(io.StringIO(archive.read(record_name).decode("utf-8")))
            )
            member_contents = {
                member.filename: archive.read(member)
                for member in members
                if member.filename != record_name
            }
        assert all(len(row) == 3 for row in record_rows)
        assert record_rows[-1] == [record_name, "", ""]
        records = {path: (digest, size) for path, digest, size in record_rows}
        assert len(records) == len(record_rows)
        assert set(records) == set(member_names)
        for member in members:
            digest, size = records[member.filename]
            if member.filename == record_name:
                assert (digest, size) == ("", "")
                continue
            contents = member_contents[member.filename]
            assert digest == _sha256_record_hash(contents)
            assert size == str(len(contents))


def test_integration_environment_excludes_parent_uv_configuration(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UV_CONFIG_FILE", "/secret/uv.toml")
    monkeypatch.setenv("UV_CONSTRAINT", "/secret/constraints.txt")
    monkeypatch.setenv("PYTHONPATH", "/secret/pythonpath")

    environment = _integration_environment(tmp_path, tmp_path / "wheelhouse")

    assert "UV_CONFIG_FILE" not in environment
    assert "UV_CONSTRAINT" not in environment
    assert "PYTHONPATH" not in environment


def test_real_uv_install_from_local_wheels_renders_text_and_scripts(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    default = _run_cli(tmp_path, wheelhouse)
    with_scripts = _run_cli(tmp_path, wheelhouse, "--bin")

    assert default.returncode == with_scripts.returncode == 0
    assert _table_names(default.stdout, "Package Sizes") == {
        _ROOT_A,
        _ROOT_B,
        _SHARED,
    }
    assert "Binaries in .venv/bin" not in default.stdout
    assert "Binaries in .venv/bin" in with_scripts.stdout
    script_paths = _table_names(with_scripts.stdout, "Binaries in .venv/bin")
    assert any(_is_installed_script(path, _ROOT_A) for path in script_paths)
    assert any(
        _is_installed_script(path, f"{_ROOT_A}-data-script") for path in script_paths
    )
    assert _reported_total(default.stdout) == _reported_total(with_scripts.stdout)
    assert default.stderr == with_scripts.stderr == ""


def test_real_uv_install_from_local_wheels_emits_complete_schema_v1_json(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    completed = _run_cli(tmp_path, wheelhouse, "--json")

    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result["schema_version"] == 1
    assert result["context"]["build_policy"] == "wheel-only"
    assert result["completeness"] == "complete"
    assert result["warnings"] == []
    assert completed.stderr == (
        "Calculating size for 2 requested packages...\n"
        "Creating virtual environment...\n"
        "Installing 2 requested packages and their dependencies...\n"
        "Analyzing sizes...\n"
        "\nCalculation complete.\n"
    )

    distributions = {
        distribution["name"]: distribution for distribution in result["distributions"]
    }
    assert {name: distributions[name]["version"] for name in distributions} == {
        _ROOT_A: "1.0.0",
        _ROOT_B: "1.0.0",
        _SHARED: "1.0.0",
    }
    assert all(
        distribution["completeness"] == "complete"
        for distribution in distributions.values()
    )
    assert all(
        distribution["warnings"] == [] for distribution in distributions.values()
    )

    root_a_files = distributions[_ROOT_A]["files"]
    assert {file["category"] for file in root_a_files} >= {
        "python",
        "metadata",
        "script",
        "data",
    }
    root_a_paths = {file["path"] for file in root_a_files}
    assert any(path.endswith("/uv_packsize_fixture_root_a.h") for path in root_a_paths)
    assert any(path.endswith("/payload.txt") for path in root_a_paths)
    assert any(_is_installed_script(path, _ROOT_A) for path in root_a_paths)
    assert any(
        _is_installed_script(path, f"{_ROOT_A}-data-script") for path in root_a_paths
    )

    distribution_total = sum(
        distribution["totals"]["logical_bytes"]
        for distribution in distributions.values()
    )
    assert result["totals"] == {
        "global_logical_bytes": distribution_total,
        "distribution_logical_bytes": distribution_total,
    }


def _run_cli(
    tmp_path: Path, wheelhouse: Path, *options: str
) -> subprocess.CompletedProcess[str]:
    environment = _integration_environment(tmp_path, wheelhouse)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "uv_packsize",
            "--python",
            sys.executable,
            *options,
            *_REQUIREMENTS,
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def _integration_environment(tmp_path: Path, wheelhouse: Path) -> dict[str, str]:
    """Return only the process variables required for an isolated uv run."""

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


def _table_names(output: str, title: str) -> set[str]:
    section = output.split(f"--- {title} ---\n", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    lines = section.splitlines()
    separator_indexes = [
        index for index, line in enumerate(lines) if re.fullmatch(r"-+(?:  -+)?", line)
    ]
    assert len(separator_indexes) == 2
    return {
        line.rsplit("  ", maxsplit=1)[0].strip()
        for line in lines[separator_indexes[0] + 1 : separator_indexes[1]]
    }


def _reported_total(output: str) -> str:
    match = re.search(r"^Total size:\s+(.+)$", output, re.MULTILINE)
    assert match is not None
    return match.group(1)


def _is_installed_script(path: str, name: str) -> bool:
    script_directory, separator, filename = path.partition("/")
    return (
        separator == "/"
        and script_directory in {"bin", "Scripts"}
        and (filename == name or filename.startswith(f"{name}."))
    )


def _sha256_record_hash(contents: bytes) -> str:
    digest = hashlib.sha256(contents).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"
