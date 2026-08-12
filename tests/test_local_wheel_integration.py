"""Network-free CLI integration coverage using real local wheel installation."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path
from typing import cast

import click
import pytest
from local_wheel_factory import build_wheelhouse

from uv_packsize.render import format_size

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


@pytest.mark.skipif(os.name != "posix", reason="atomic baseline writer is POSIX-only")
def test_real_uv_rich_report_composes_text_features_budget_and_baseline_write(
    tmp_path,
):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    baseline = tmp_path / "rich-baseline.json"

    completed = _run_cli(
        tmp_path,
        wheelhouse,
        "--report",
        "rich",
        "--color",
        "always",
        "--bin",
        "--explain",
        "--breakdown",
        "--contributions",
        "--max-total",
        str(2**63 - 1),
        "--write-baseline",
        str(baseline),
    )

    assert completed.returncode == 0, completed.stderr
    plain_stdout = click.unstyle(completed.stdout)
    assert "\x1b[" in completed.stdout
    assert plain_stdout.startswith("--- Rich Analysis Summary ---\n")
    assert "Input kind: fresh-install" in plain_stdout
    assert "Build policy: wheel-only" in plain_stdout
    assert "Completeness: complete" in plain_stdout
    assert "--- Top Distributions (Showing 3 of 3) ---" in plain_stdout
    assert "--- Package Sizes ---" not in plain_stdout
    for section in (
        "--- Binaries in .venv/bin ---",
        "--- Requested Roots ---",
        "--- File Category Breakdown ---",
        "--- Root Contributions ---",
        "--- Size Budget ---",
    ):
        assert section in plain_stdout
    assert "Result: PASS" in plain_stdout
    assert json.loads(baseline.read_text())["schema_version"] == 1


def test_real_uv_rich_comparison_and_json_ignore_contract(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    baseline = tmp_path / "baseline.json"
    standard_json = _run_cli(tmp_path, wheelhouse, "--json")
    baseline.write_text(standard_json.stdout)

    rich_json = _run_cli(
        tmp_path, wheelhouse, "--json", "--report", "rich", "--color", "always"
    )
    comparison = _run_cli(
        tmp_path,
        wheelhouse,
        "--baseline",
        str(baseline),
        "--report",
        "rich",
        "--color",
        "always",
    )
    standard_comparison_json = _run_cli(
        tmp_path, wheelhouse, "--baseline", str(baseline), "--comparison-json"
    )
    rich_comparison_json = _run_cli(
        tmp_path,
        wheelhouse,
        "--baseline",
        str(baseline),
        "--comparison-json",
        "--report",
        "rich",
        "--color",
        "always",
    )

    assert standard_json.returncode == rich_json.returncode == 0
    assert standard_json.stdout == rich_json.stdout
    assert standard_json.stderr == rich_json.stderr
    assert comparison.returncode == 0, comparison.stderr
    assert "\x1b[" in comparison.stdout
    comparison_plain = click.unstyle(comparison.stdout)
    assert comparison_plain.startswith("--- Rich Comparison Summary ---\n")
    assert "Input kind: fresh-install" in comparison_plain
    assert "--- Top Changes (Showing 0 of 0) ---" in comparison_plain
    assert "No distribution changes." in comparison_plain
    assert standard_comparison_json.returncode == rich_comparison_json.returncode == 0
    assert standard_comparison_json.stdout == rich_comparison_json.stdout
    assert standard_comparison_json.stderr == rich_comparison_json.stderr


def test_real_uv_install_from_local_wheels_explains_shared_dependency(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    completed = _run_cli(tmp_path, wheelhouse, "--explain")

    assert completed.returncode == 0
    assert "--- Requested Roots ---" in completed.stdout
    assert f"1  {_ROOT_A}  recognized" in completed.stdout
    assert f"2  {_ROOT_B}  recognized" in completed.stdout
    assert "--- Dependency Attribution ---" in completed.stdout
    assert f"{_SHARED}  1.0.0  direct  yes" in completed.stdout
    assert "--- Dependency Paths ---" in completed.stdout
    assert f"1  {_ROOT_A} -> {_SHARED}" in completed.stdout
    assert f"2  {_ROOT_B} -> {_SHARED}" in completed.stdout
    assert completed.stderr == ""


def test_real_uv_install_from_local_wheels_renders_global_breakdown(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    default = _run_cli(tmp_path, wheelhouse)
    completed = _run_cli(tmp_path, wheelhouse, "--breakdown")
    with_scripts = _run_cli(tmp_path, wheelhouse, "--breakdown", "--bin")
    raw_result = json.loads(_run_cli(tmp_path, wheelhouse, "--json").stdout)

    category_totals = {
        category: sum(
            file["logical_bytes"]
            for distribution in raw_result["distributions"]
            for file in distribution["files"]
            if file["category"] == category
        )
        for category in ("python", "native", "data", "metadata", "script", "other")
    }
    shared_total = next(
        distribution["totals"]["logical_bytes"]
        for distribution in raw_result["distributions"]
        if distribution["name"] == _SHARED
    )
    global_total = raw_result["totals"]["global_logical_bytes"]

    assert default.returncode == completed.returncode == with_scripts.returncode == 0
    assert _reported_total(default.stdout) == _reported_total(completed.stdout)
    assert _reported_total(completed.stdout) == _reported_total(with_scripts.stdout)
    assert _table_rows(completed.stdout, "File Category Breakdown") == {
        category: format_size(total) for category, total in category_totals.items()
    }
    assert _table_footer(completed.stdout, "File Category Breakdown") == format_size(
        global_total
    )
    role_rows = _table_rows(completed.stdout, "Dependency Size Attribution")
    assert set(role_rows) == {
        "self",
        "direct",
        "transitive",
        "unattributed",
        "mixed-ownership",
    }
    assert role_rows["direct"] == format_size(shared_total)
    assert _table_footer(
        completed.stdout, "Dependency Size Attribution"
    ) == format_size(global_total)
    assert "Binaries in .venv/bin" in with_scripts.stdout
    assert completed.stderr == with_scripts.stderr == ""


def test_real_uv_install_from_local_wheels_combines_explanation_and_breakdown(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    completed = _run_cli(tmp_path, wheelhouse, "--explain", "--breakdown")

    assert completed.returncode == 0
    assert completed.stdout.index("--- Requested Roots ---") < completed.stdout.index(
        "--- File Category Breakdown ---"
    )
    assert completed.stdout.index("--- Dependency Paths ---") < completed.stdout.index(
        "--- Dependency Size Attribution ---"
    )
    assert completed.stderr == ""


def test_real_uv_install_from_local_wheels_renders_non_split_contributions(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    completed = _run_cli(tmp_path, wheelhouse, "--contributions")
    combined = _run_cli(
        tmp_path, wheelhouse, "--explain", "--breakdown", "--contributions"
    )
    raw_result = json.loads(_run_cli(tmp_path, wheelhouse, "--json").stdout)
    totals = {
        distribution["name"]: distribution["totals"]["logical_bytes"]
        for distribution in raw_result["distributions"]
    }
    global_total = raw_result["totals"]["global_logical_bytes"]
    exclusive_root_a = totals[_ROOT_A]
    exclusive_root_b = totals[_ROOT_B]
    shared_exact_root_set = totals[_SHARED]
    root_a_closure = totals[_ROOT_A] + totals[_SHARED]
    root_b_closure = totals[_ROOT_B] + totals[_SHARED]

    assert completed.returncode == combined.returncode == 0
    assert global_total == exclusive_root_a + exclusive_root_b + shared_exact_root_set
    assert root_a_closure == exclusive_root_a + shared_exact_root_set
    assert root_b_closure == exclusive_root_b + shared_exact_root_set
    assert completed.stdout.count("--- Package Sizes ---") == 1
    assert "--- Root Contributions ---" in completed.stdout
    assert "--- Shared Root-Set Bytes ---" in completed.stdout
    assert "--- Contribution Reconciliation ---" in completed.stdout
    assert re.search(
        rf"{re.escape(_ROOT_A)}\s+1\s+{re.escape(format_size(exclusive_root_a))}"
        rf"\s+{re.escape(format_size(shared_exact_root_set))}\s+{re.escape(format_size(root_a_closure))}",
        completed.stdout,
    )
    assert re.search(
        rf"{re.escape(_ROOT_B)}\s+2\s+{re.escape(format_size(exclusive_root_b))}"
        rf"\s+{re.escape(format_size(shared_exact_root_set))}\s+{re.escape(format_size(root_b_closure))}",
        completed.stdout,
    )
    assert (
        f"{_ROOT_A}, {_ROOT_B}" in completed.stdout
        and format_size(shared_exact_root_set) in completed.stdout
    )
    assert re.search(
        rf"Global total\s+{re.escape(format_size(global_total))}", completed.stdout
    )
    assert (
        combined.stdout.index("--- Requested Roots ---")
        < combined.stdout.index("--- File Category Breakdown ---")
        < combined.stdout.index("--- Root Contributions ---")
    )
    assert completed.stderr == combined.stderr == ""


def test_real_uv_contributions_preserve_duplicate_root_indices_without_bytes(
    tmp_path,
):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    unique = _run_cli(tmp_path, wheelhouse, "--contributions")
    unique_json = _run_cli(tmp_path, wheelhouse, "--json")
    duplicate = _run_cli(
        tmp_path,
        wheelhouse,
        "--contributions",
        requirements=(_REQUIREMENTS[0], _REQUIREMENTS[1], _REQUIREMENTS[0]),
    )
    duplicate_json = _run_cli(
        tmp_path,
        wheelhouse,
        "--json",
        requirements=(_REQUIREMENTS[0], _REQUIREMENTS[1], _REQUIREMENTS[0]),
    )

    assert unique.returncode == unique_json.returncode == 0
    assert duplicate.returncode == duplicate_json.returncode == 0
    unique_payload = json.loads(unique_json.stdout)
    duplicate_payload = json.loads(duplicate_json.stdout)
    unique_totals = {
        distribution["name"]: distribution["totals"]["logical_bytes"]
        for distribution in unique_payload["distributions"]
    }
    duplicate_totals = {
        distribution["name"]: distribution["totals"]["logical_bytes"]
        for distribution in duplicate_payload["distributions"]
    }

    assert (
        duplicate_payload["totals"]["global_logical_bytes"]
        == unique_payload["totals"]["global_logical_bytes"]
    )
    assert duplicate_totals == unique_totals
    assert unique_payload["totals"]["global_logical_bytes"] == sum(
        unique_totals[name] for name in (_ROOT_A, _ROOT_B, _SHARED)
    )
    assert _reported_total(unique.stdout) == _reported_total(duplicate.stdout)
    assert re.search(rf"{re.escape(_ROOT_A)}\s+1, 3\s+", duplicate.stdout)
    assert re.search(
        rf"{re.escape(_ROOT_A)}\s+1, 3\s+"
        rf"{re.escape(format_size(unique_totals[_ROOT_A]))}\s+"
        rf"{re.escape(format_size(unique_totals[_SHARED]))}\s+"
        rf"{re.escape(format_size(unique_totals[_ROOT_A] + unique_totals[_SHARED]))}",
        duplicate.stdout,
    )
    assert duplicate.stdout.count(f"{_ROOT_A}, {_ROOT_B}") == 1


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


def test_real_uv_local_wheel_baseline_compare_is_read_only_and_stdout_only(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    baseline = tmp_path / "baseline.json"
    recorded = _run_cli(tmp_path, wheelhouse, "--json")
    assert recorded.returncode == 0
    baseline.write_text(recorded.stdout)
    before = baseline.read_bytes()

    completed = _run_cli(tmp_path, wheelhouse, "--baseline", str(baseline))

    assert completed.returncode == 0
    assert completed.stdout.startswith("--- Size Comparison ---\n")
    assert "Global logical size" in completed.stdout
    assert "Distribution-owned aggregate" in completed.stdout
    assert "0 B" in completed.stdout
    assert "--- Distribution Changes ---\nNo distribution changes." in completed.stdout
    assert "Calculating size" not in completed.stdout
    assert completed.stderr == (
        "Calculating size for 2 requested packages...\n"
        "Creating virtual environment...\n"
        "Installing 2 requested packages and their dependencies...\n"
        "Analyzing sizes...\n"
        "Comparing with baseline...\n"
    )
    assert baseline.read_bytes() == before


@pytest.mark.skipif(os.name != "posix", reason="atomic baseline writer is POSIX-only")
def test_real_uv_local_wheel_write_baseline_roundtrip_and_no_clobber(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    baseline = tmp_path / "baseline.json"

    written = _run_cli(
        tmp_path, wheelhouse, "--json", "--write-baseline", str(baseline)
    )
    assert written.returncode == 0
    assert written.stdout.encode() == baseline.read_bytes()
    assert stat.S_IMODE(baseline.stat().st_mode) == 0o600
    before = baseline.read_bytes()

    compared = _run_cli(tmp_path, wheelhouse, "--baseline", str(baseline))
    comparison_json = _run_cli(
        tmp_path, wheelhouse, "--baseline", str(baseline), "--comparison-json"
    )
    assert compared.returncode == comparison_json.returncode == 0
    assert baseline.read_bytes() == before

    second = _run_cli(tmp_path, wheelhouse, "--json", "--write-baseline", str(baseline))
    assert second.returncode == 3
    assert second.stdout == ""
    assert "Could not write baseline (code=exists, field=file)." in second.stderr
    assert baseline.read_bytes() == before

    overwritten = _run_cli(
        tmp_path,
        wheelhouse,
        "--json",
        "--write-baseline",
        str(baseline),
        "--overwrite-baseline",
    )
    assert overwritten.returncode == 0
    assert overwritten.stdout.encode() == baseline.read_bytes()
    assert _run_cli(tmp_path, wheelhouse, "--baseline", str(baseline)).returncode == 0


def test_real_uv_local_wheel_comparison_json_is_complete_and_read_only(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    baseline = tmp_path / "baseline.json"
    recorded = _run_cli(tmp_path, wheelhouse, "--json")
    assert recorded.returncode == 0
    baseline.write_text(recorded.stdout)
    before = baseline.read_bytes()

    completed = _run_cli(
        tmp_path, wheelhouse, "--baseline", str(baseline), "--comparison-json"
    )

    assert completed.returncode == 0
    assert completed.stdout.endswith("\n")
    assert not completed.stdout.endswith("\n\n")
    document = json.loads(completed.stdout)
    assert list(document) == [
        "schema_version",
        "measurement",
        "context",
        "baseline",
        "current",
        "changes",
        "completeness",
    ]
    assert document["schema_version"] == 1
    assert document["context"] == {
        "input_kind": "fresh-install",
        "comparison_context_fingerprint": document["context"][
            "comparison_context_fingerprint"
        ],
    }
    assert re.fullmatch(
        r"[0-9a-f]{64}", document["context"]["comparison_context_fingerprint"]
    )
    assert document["baseline"]["totals"] == document["current"]["totals"]
    assert document["changes"]["totals"] == {
        "global_logical_bytes_delta": 0,
        "distribution_logical_bytes_delta": 0,
    }
    distributions = document["changes"]["distributions"]
    assert [item["name"] for item in distributions] == sorted(
        (_ROOT_A, _ROOT_B, _SHARED)
    )
    assert all(item["kind"] == "unchanged" for item in distributions)
    assert all(item["baseline"] == item["current"] for item in distributions)
    assert all(item["logical_bytes_delta"] == 0 for item in distributions)
    nonreconciliation = document["changes"]["nonreconciliation"]
    assert nonreconciliation == {
        "present": False,
        "distribution_minus_global_logical_bytes_delta": 0,
        "reason": None,
    }
    assert document["completeness"] == "complete"
    assert completed.stderr == (
        "Calculating size for 2 requested packages...\n"
        "Creating virtual environment...\n"
        "Installing 2 requested packages and their dependencies...\n"
        "Analyzing sizes...\n"
        "Comparing with baseline...\n"
    )
    assert baseline.read_bytes() == before


def test_real_uv_local_wheel_budget_config_enforces_without_machine_output(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    config = tmp_path / "pyproject.toml"
    config.write_text(
        "[tool.uv-packsize.budget]\n"
        "max_total_logical_bytes = 0\n"
        "incomplete_policy = 'allow-partial'\n"
    )
    baseline = tmp_path / "baseline.json"

    failed = _run_cli(tmp_path, wheelhouse, "--json", "--budget-config", str(config))
    write_failed = _run_cli(
        tmp_path,
        wheelhouse,
        "--json",
        "--budget-config",
        str(config),
        "--write-baseline",
        str(baseline),
    )

    assert failed.returncode == write_failed.returncode == 5
    assert failed.stdout == write_failed.stdout == ""
    assert "--- Size Budget ---" in failed.stderr
    assert "Maximum total logical size exceeded" in failed.stderr
    assert "Size budget was exceeded." in failed.stderr
    assert not baseline.exists()


def test_real_uv_install_from_local_wheels_json_text_options_are_byte_identical(
    tmp_path,
):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)

    default = _run_cli(tmp_path, wheelhouse, "--json")
    for options in (
        ("--bin",),
        ("--explain",),
        ("--breakdown",),
        ("--contributions",),
        ("--bin", "--explain"),
        ("--bin", "--breakdown"),
        ("--explain", "--breakdown"),
        ("--explain", "--contributions"),
        ("--breakdown", "--contributions"),
        ("--bin", "--explain", "--breakdown"),
        ("--bin", "--explain", "--breakdown", "--contributions"),
    ):
        with_text_option = _run_cli(tmp_path, wheelhouse, "--json", *options)

        assert default.returncode == with_text_option.returncode == 0
        assert default.stdout == with_text_option.stdout
        assert default.stderr == with_text_option.stderr


def test_existing_prefix_local_wheels_match_fresh_inventory_and_hide_local_paths(
    tmp_path,
):
    """A real read-only prefix scan has v2-only, non-reversible context."""

    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    fresh = _run_cli(tmp_path, wheelhouse, "--json")
    fresh_payload = json.loads(fresh.stdout)
    prefix, site_packages_relative = _install_persistent_prefix(tmp_path, wheelhouse)

    completed = _run_prefix_cli(
        tmp_path,
        prefix,
        site_packages_relative,
        fresh_payload["context"]["case_rule"],
        "--json",
    )

    assert fresh.returncode == completed.returncode == 0
    prefix_payload = json.loads(completed.stdout)
    assert fresh_payload["schema_version"] == 1
    assert prefix_payload["schema_version"] == 2
    for field in ("warnings", "duplicate_ownerships", "completeness"):
        assert prefix_payload[field] == fresh_payload[field]

    fresh_distributions = _distributions_by_name(fresh_payload)
    prefix_distributions = _distributions_by_name(prefix_payload)
    assert set(prefix_distributions) == set(fresh_distributions)
    for name, fresh_distribution in fresh_distributions.items():
        prefix_distribution = prefix_distributions[name]
        assert prefix_distribution["version"] == fresh_distribution["version"]
        assert prefix_distribution["warnings"] == fresh_distribution["warnings"]
        assert prefix_distribution["completeness"] == fresh_distribution["completeness"]
        assert _non_script_files(prefix_distribution) == _non_script_files(
            fresh_distribution
        )
        assert _script_file_projections(
            prefix_distribution
        ) == _script_file_projections(fresh_distribution)

    # uv-generated POSIX console scripts embed the install interpreter in their
    # shebang. Prefix scans must therefore preserve all non-script inventory
    # bytes while allowing logical script sizes (and only those sizes) to vary.
    fresh_non_script_bytes = _global_unique_bytes(fresh_payload, include_scripts=False)
    prefix_non_script_bytes = _global_unique_bytes(
        prefix_payload, include_scripts=False
    )
    fresh_script_bytes = _global_unique_bytes(fresh_payload, include_scripts=True) - (
        fresh_non_script_bytes
    )
    prefix_script_bytes = _global_unique_bytes(prefix_payload, include_scripts=True) - (
        prefix_non_script_bytes
    )
    assert prefix_non_script_bytes == fresh_non_script_bytes
    assert (
        prefix_payload["totals"]["global_logical_bytes"]
        - fresh_payload["totals"]["global_logical_bytes"]
        == prefix_script_bytes - fresh_script_bytes
    )
    assert prefix_payload["context"] == {
        "input_kind": "existing-prefix",
        "requirements": [],
        "python_version": None,
        "platform": None,
        "architecture": None,
        "path_flavor": "windows" if os.name == "nt" else "posix",
        "case_rule": fresh_payload["context"]["case_rule"],
        "uv_version": None,
        "build_policy": None,
        "compile_bytecode": None,
        "extras": [],
        "index_identifiers": [],
        "resolution_strategy": None,
    }
    for local_path in (
        prefix,
        prefix / site_packages_relative,
        wheelhouse,
        tmp_path / "home",
    ):
        assert str(local_path) not in completed.stdout
    assert completed.stderr == (
        "Analyzing existing prefix...\n\nExisting prefix analysis complete.\n"
    )


def test_existing_prefix_local_wheels_bin_and_json_options_preserve_contract(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    fresh = _run_cli(tmp_path, wheelhouse, "--json")
    assert fresh.returncode == 0
    case_rule = json.loads(fresh.stdout)["context"]["case_rule"]
    prefix, site_packages_relative = _install_persistent_prefix(tmp_path, wheelhouse)

    default = _run_prefix_cli(tmp_path, prefix, site_packages_relative, case_rule)
    with_scripts = _run_prefix_cli(
        tmp_path, prefix, site_packages_relative, case_rule, "--bin"
    )
    assert default.returncode == with_scripts.returncode == 0
    assert "Binaries in prefix" not in default.stdout
    assert "Binaries in .venv/bin" not in default.stdout
    assert "--- Binaries in prefix ---" in with_scripts.stdout
    assert "Binaries in .venv/bin" not in with_scripts.stdout
    assert _reported_total(default.stdout) == _reported_total(with_scripts.stdout)
    script_paths = _table_names(with_scripts.stdout, "Binaries in prefix")
    assert any(_is_installed_script(path, _ROOT_A) for path in script_paths)
    assert any(
        _is_installed_script(path, f"{_ROOT_A}-data-script") for path in script_paths
    )
    assert default.stderr == with_scripts.stderr == ""

    plain_json = _run_prefix_cli(
        tmp_path, prefix, site_packages_relative, case_rule, "--json"
    )
    for options in (
        ("--bin",),
        ("--explain",),
        ("--breakdown",),
        ("--contributions",),
        ("--bin", "--explain"),
        ("--bin", "--breakdown"),
        ("--explain", "--breakdown"),
        ("--explain", "--contributions"),
        ("--breakdown", "--contributions"),
        ("--bin", "--explain", "--breakdown"),
        ("--bin", "--explain", "--breakdown", "--contributions"),
    ):
        decorated = _run_prefix_cli(
            tmp_path, prefix, site_packages_relative, case_rule, "--json", *options
        )
        assert plain_json.returncode == decorated.returncode == 0
        assert plain_json.stdout == decorated.stdout
        assert plain_json.stderr == decorated.stderr


def test_existing_prefix_scan_does_not_mutate_real_local_wheel_environment(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    build_wheelhouse(wheelhouse)
    fresh = _run_cli(tmp_path, wheelhouse, "--json")
    assert fresh.returncode == 0
    case_rule = json.loads(fresh.stdout)["context"]["case_rule"]
    prefix, site_packages_relative = _install_persistent_prefix(tmp_path, wheelhouse)
    before = _prefix_snapshot(prefix)

    completed = _run_prefix_cli(
        tmp_path, prefix, site_packages_relative, case_rule, "--json"
    )

    assert completed.returncode == 0
    assert _prefix_snapshot(prefix) == before


def _run_cli(
    tmp_path: Path,
    wheelhouse: Path,
    *options: str,
    requirements: tuple[str, ...] = _REQUIREMENTS,
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
            *requirements,
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def _run_prefix_cli(
    tmp_path: Path,
    prefix: Path,
    site_packages_relative: str,
    case_rule: str,
    *options: str,
) -> subprocess.CompletedProcess[str]:
    """Run the public prefix branch without using ``uv`` as the CLI runner."""

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "uv_packsize",
            "--prefix",
            str(prefix),
            "--site-packages",
            site_packages_relative,
            "--case-rule",
            case_rule,
            *options,
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=_integration_environment(tmp_path, tmp_path / "unused-wheelhouse"),
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def _install_persistent_prefix(tmp_path: Path, wheelhouse: Path) -> tuple[Path, str]:
    """Install the fixture wheels once; this is test setup, not CLI execution."""

    # Keep this deliberately unlike the temporary-install location. On POSIX,
    # generated console-script shebangs then exercise the documented
    # path-dependent script-byte difference between fresh and prefix scans.
    prefix = tmp_path / "persistent-existing-prefix" / "venv"
    environment = _integration_environment(tmp_path, wheelhouse)
    _run_setup_uv(
        environment,
        "venv",
        "--python",
        sys.executable,
        str(prefix),
    )
    python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run_setup_uv(
        environment,
        "pip",
        "install",
        "--python",
        str(python),
        "--no-build",
        *_REQUIREMENTS,
    )
    purelib = Path(
        sysconfig.get_path(
            "purelib",
            vars={"base": str(prefix), "platbase": str(prefix)},
        )
    )
    return prefix, str(purelib.relative_to(prefix))


def _run_setup_uv(environment: dict[str, str], *arguments: str) -> None:
    completed = subprocess.run(
        ["uv", *arguments],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _prefix_snapshot(prefix: Path) -> dict[str, tuple[int, int, str | None]]:
    """Capture every entry's lstat state and raw symlink target, if any."""

    snapshot = {}
    for path in (prefix, *sorted(prefix.rglob("*"))):
        status = path.lstat()
        relative = "." if path == prefix else path.relative_to(prefix).as_posix()
        target: str | None = None
        digest: str | None = None
        if stat.S_ISLNK(status.st_mode):
            target = os.readlink(path)
        elif stat.S_ISREG(status.st_mode):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[relative] = (status.st_mode, status.st_size, target or digest)
    return snapshot


def _distributions_by_name(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    distributions = _json_object_list(payload["distributions"])
    result = {}
    for distribution in distributions:
        name = distribution["name"]
        assert isinstance(name, str)
        result[name] = distribution
    assert len(result) == len(distributions)
    return result


def _non_script_files(distribution: dict[str, object]) -> list[dict[str, object]]:
    files = _json_object_list(distribution["files"])
    return [file for file in files if file["category"] != "script"]


def _script_file_projections(
    distribution: dict[str, object],
) -> list[dict[str, object]]:
    files = _json_object_list(distribution["files"])
    return [
        {key: value for key, value in file.items() if key != "logical_bytes"}
        for file in files
        if file["category"] == "script"
    ]


def _global_unique_bytes(payload: dict[str, object], *, include_scripts: bool) -> int:
    """Return fixture-global logical bytes deduplicated by public file path."""

    files_by_path: dict[str, int] = {}
    for distribution in _distributions_by_name(payload).values():
        files = _json_object_list(distribution["files"])
        for file in files:
            if not include_scripts and file["category"] == "script":
                continue
            path = file["path"]
            logical_bytes = file["logical_bytes"]
            assert isinstance(path, str)
            assert isinstance(logical_bytes, int)
            previous = files_by_path.setdefault(path, logical_bytes)
            assert previous == logical_bytes
    return sum(files_by_path.values())


def _json_object_list(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return [cast(dict[str, object], item) for item in value]


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
    return set(_table_rows(output, title))


def _table_rows(output: str, title: str) -> dict[str, str]:
    section = _table_section(output, title)
    lines = section.splitlines()
    separator_indexes = [
        index for index, line in enumerate(lines) if re.fullmatch(r"-+(?:  -+)?", line)
    ]
    assert len(separator_indexes) == 2
    return {
        name.strip(): size.strip()
        for line in lines[separator_indexes[0] + 1 : separator_indexes[1]]
        for name, size in (line.rsplit("  ", maxsplit=1),)
    }


def _table_footer(output: str, title: str) -> str:
    return _table_section(output, title).splitlines()[-1].rsplit("  ", maxsplit=1)[1]


def _table_section(output: str, title: str) -> str:
    return output.split(f"--- {title} ---\n", maxsplit=1)[1].split("\n\n", maxsplit=1)[
        0
    ]


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
