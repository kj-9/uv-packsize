"""Network-free public CLI coverage for explicit project/lock analysis."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

from uv_packsize.cli import cli
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
)
from uv_packsize.project_lock_installer import (
    ProjectLockInstallError,
    ProjectLockInstallErrorReason,
)
from uv_packsize.project_lock_reader import (
    ProjectLockInputError,
    ProjectLockInputErrorReason,
    ProjectLockInputField,
)

_PROJECT = Path(__file__).parent / "golden" / "project-lock" / "pyproject.toml"
_LOCK = Path(__file__).parent / "golden" / "project-lock" / "uv.lock"


def _arguments(*extra: str) -> list[str]:
    return ["--project", str(_PROJECT), "--lockfile", str(_LOCK), *extra]


def _project_double(monkeypatch, *, expected_python: str | None = None):
    """Run the CLI's private inventory callback against a test-owned venv."""

    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr("uv_packsize.cli._uv_version", lambda: "0.11.3")
    environment = SimpleNamespace(
        context=ResolutionContext(
            requirements=("example-project",),
            python_version="3.14.0",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        layouts=(),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.discover_installed_environment", lambda **_kwargs: environment
    )
    monkeypatch.setattr(
        "uv_packsize.cli.analyze_installed_environment",
        lambda *, context, layouts: AnalysisResult(
            context=context,
            distributions=(
                DistributionResult(
                    name="dependency",
                    version="1",
                    files=(
                        FileEntry(
                            path="site-packages/dependency.py",
                            canonical_identity="site-packages/dependency.py",
                            logical_bytes=1,
                            category=FileCategory.PYTHON,
                            origin=FileOrigin.RECORD,
                        ),
                    ),
                ),
            ),
        ),
    )

    def install(snapshot, *, build_policy, collect_inventory, python_version):
        assert build_policy is BuildPolicy.WHEEL_ONLY
        assert python_version == expected_python
        return collect_inventory(Path("/private/temporary-project-environment"))

    monkeypatch.setattr("uv_packsize.cli.install_validated_project_lock", install)


def test_project_lock_options_are_exposed_by_cli_help():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    for option in (
        "--project PATH",
        "--lockfile PATH",
        "--workspace-member TEXT",
        "--group TEXT",
        "--all-groups",
        "--extra TEXT",
    ):
        assert option in result.output


def test_project_lock_json_is_v3_one_document_and_redacts_input_paths(monkeypatch):
    _project_double(monkeypatch)

    result = CliRunner().invoke(cli, _arguments("--json"))

    assert result.exit_code == 0
    assert result.stdout.endswith("\n")
    document = json.loads(result.stdout)
    assert document["schema_version"] == 3
    assert document["context"]["input_kind"] == "project-lock"
    assert str(_PROJECT) not in result.stdout
    assert str(_LOCK) not in result.stdout
    assert "Calculating size" not in result.stdout
    assert "Calculating size" in result.stderr


def test_project_lock_text_report_keeps_progress_on_stderr(monkeypatch):
    _project_double(monkeypatch)

    result = CliRunner().invoke(cli, _arguments())

    assert result.exit_code == 0
    assert "--- Rich Analysis Summary ---" in result.stdout
    assert "--- Package Sizes ---" not in result.stdout
    assert result.stderr == (
        "Calculating size for the selected project lock...\n"
        "Installing the selected project lock...\n"
        "Analyzing sizes...\n"
        "\nCalculation complete.\n"
    )


def test_project_lock_rich_text_report_replaces_the_standard_primary(monkeypatch):
    _project_double(monkeypatch)

    result = CliRunner().invoke(cli, _arguments("--report", "rich"))

    assert result.exit_code == 0
    assert "--- Rich Analysis Summary ---" in result.stdout
    assert "Input kind: project-lock" in result.stdout
    assert "--- Package Sizes ---" not in result.stdout
    assert result.stderr == (
        "Calculating size for the selected project lock...\n"
        "Installing the selected project lock...\n"
        "Analyzing sizes...\n"
        "\nCalculation complete.\n"
    )


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_project_lock_quiet_keeps_final_text_and_suppresses_progress(
    monkeypatch, report_format
):
    _project_double(monkeypatch)

    result = CliRunner().invoke(cli, _arguments("--report", report_format, "--quiet"))

    assert result.exit_code == 0
    expected = (
        "Package Sizes" if report_format == "standard" else "Rich Analysis Summary"
    )
    assert expected in result.stdout
    assert result.stderr == ""


def test_project_lock_forwards_an_explicit_python_selection_to_the_bridge(monkeypatch):
    _project_double(monkeypatch, expected_python="3.14")

    result = CliRunner().invoke(cli, _arguments("--json", "--python", "3.14"))

    assert result.exit_code == 0


def test_project_lock_baseline_comparison_and_budget_use_v3_v2_contracts(
    monkeypatch, tmp_path
):
    _project_double(monkeypatch)
    baseline = tmp_path / "project-baseline.json"

    recorded = CliRunner().invoke(
        cli, _arguments("--json", "--write-baseline", str(baseline))
    )
    assert recorded.exit_code == 0
    assert baseline.read_text() == recorded.stdout

    compared = CliRunner().invoke(
        cli,
        _arguments("--baseline", str(baseline), "--comparison-json"),
    )
    assert compared.exit_code == 0
    document = json.loads(compared.stdout)
    assert document["schema_version"] == 2
    assert document["context"]["input_kind"] == "project-lock"
    assert "lock_identity" not in compared.stdout

    budget = CliRunner().invoke(cli, _arguments("--json", "--max-total", "0"))
    assert budget.exit_code == 5, budget.output
    assert budget.stdout == ""


def test_project_lock_comparison_json_ignores_rich_report(monkeypatch, tmp_path):
    _project_double(monkeypatch)
    baseline = tmp_path / "project-baseline.json"
    recorded = CliRunner().invoke(
        cli, _arguments("--json", "--write-baseline", str(baseline))
    )
    assert recorded.exit_code == 0
    monkeypatch.setattr(
        "uv_packsize.cli.project_rich_comparison",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not project")),
    )

    default = CliRunner().invoke(
        cli, _arguments("--baseline", str(baseline), "--comparison-json")
    )
    rich = CliRunner().invoke(
        cli,
        _arguments(
            "--baseline", str(baseline), "--comparison-json", "--report", "rich"
        ),
    )

    assert default.exit_code == rich.exit_code == 0
    assert default.stdout == rich.stdout
    assert default.stderr == rich.stderr


def test_project_lock_quiet_json_and_comparison_preserve_stdout_bytes(
    monkeypatch, tmp_path
):
    _project_double(monkeypatch)
    baseline = tmp_path / "project-baseline.json"
    default_json = CliRunner().invoke(cli, _arguments("--json"))
    quiet_json = CliRunner().invoke(cli, _arguments("--json", "--quiet"))

    assert quiet_json.exit_code == default_json.exit_code == 0
    assert quiet_json.stdout == default_json.stdout
    assert quiet_json.stderr == ""
    baseline.write_text(default_json.stdout)

    default_comparison = CliRunner().invoke(
        cli, _arguments("--baseline", str(baseline), "--comparison-json")
    )
    quiet_comparison = CliRunner().invoke(
        cli,
        _arguments("--baseline", str(baseline), "--comparison-json", "--quiet"),
    )

    assert quiet_comparison.exit_code == default_comparison.exit_code == 0
    assert quiet_comparison.stdout == default_comparison.stdout
    assert quiet_comparison.stderr == ""


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_project_lock_color_always_decorates_only_final_report(
    monkeypatch, report_format
):
    _project_double(monkeypatch)

    plain = CliRunner().invoke(cli, _arguments("--report", report_format))
    colored = CliRunner().invoke(
        cli, _arguments("--report", report_format, "--color", "always")
    )

    assert colored.exit_code == plain.exit_code == 0
    assert click.unstyle(colored.stdout) == plain.stdout
    assert colored.stderr == plain.stderr
    assert "\x1b[" in colored.stdout
    assert "\x1b[" not in colored.stderr


@pytest.mark.parametrize("color_mode", ["auto", "always", "never"])
def test_project_lock_json_ignores_every_color_mode(monkeypatch, color_mode):
    _project_double(monkeypatch)
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    default = CliRunner().invoke(cli, _arguments("--json"))
    selected = CliRunner().invoke(cli, _arguments("--json", "--color", color_mode))

    assert selected.exit_code == default.exit_code == 0
    assert selected.stdout == default.stdout
    assert selected.stderr == default.stderr
    assert "\x1b[" not in selected.output


@pytest.mark.parametrize("color_mode", ["auto", "always", "never"])
def test_project_lock_comparison_json_ignores_every_color_mode(
    monkeypatch, tmp_path, color_mode
):
    _project_double(monkeypatch)
    baseline = tmp_path / "project-baseline.json"
    recorded = CliRunner().invoke(
        cli, _arguments("--json", "--write-baseline", str(baseline))
    )
    assert recorded.exit_code == 0
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    default = CliRunner().invoke(
        cli, _arguments("--baseline", str(baseline), "--comparison-json")
    )
    selected = CliRunner().invoke(
        cli,
        _arguments(
            "--baseline",
            str(baseline),
            "--comparison-json",
            "--color",
            color_mode,
        ),
    )

    assert selected.exit_code == default.exit_code == 0
    assert selected.stdout == default.stdout
    assert selected.stderr == default.stderr
    assert "\x1b[" not in selected.output


def test_project_lock_explicit_standard_never_is_the_legacy_plain_escape(monkeypatch):
    _project_double(monkeypatch)

    standard = CliRunner().invoke(
        cli, _arguments("--report", "standard", "--color", "never")
    )

    assert standard.exit_code == 0
    assert "--- Package Sizes ---" in standard.stdout
    assert "--- Rich Analysis Summary ---" not in standard.stdout
    assert "\x1b[" not in standard.output


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--project", "project.toml"], "must be used together"),
        (["--lockfile", "uv.lock"], "must be used together"),
        (["--group", "dev"], "require --project and --lockfile"),
        (
            ["--project", "project.toml", "--lockfile", "uv.lock", "package"],
            "cannot be used with --project",
        ),
        (
            [
                "--project",
                "project.toml",
                "--lockfile",
                "uv.lock",
                "--group",
                "dev",
                "--all-groups",
            ],
            "cannot be used with --all-groups",
        ),
        (
            ["--project", "project.toml", "--lockfile", "uv.lock", "--explain"],
            "--explain cannot be used with --project",
        ),
        (
            ["--project", "project.toml", "--lockfile", "uv.lock", "--breakdown"],
            "--breakdown cannot be used with --project",
        ),
        (
            [
                "--project",
                "project.toml",
                "--lockfile",
                "uv.lock",
                "--contributions",
            ],
            "--contributions cannot be used with --project",
        ),
    ],
)
def test_project_lock_usage_guards_precede_reader_and_external_work(
    monkeypatch, arguments, message
):
    def unavailable(*_args, **_kwargs):
        raise AssertionError("reader or installer must not run")

    monkeypatch.setattr("uv_packsize.cli._read_validated_project_lock", unavailable)
    monkeypatch.setattr("uv_packsize.cli.shutil.which", unavailable)

    result = CliRunner().invoke(cli, arguments)

    assert result.exit_code == 2
    assert result.stdout == ""
    assert message in result.output


@pytest.mark.parametrize(
    ("selector", "unsafe_value"),
    [
        ("--workspace-member", "../member"),
        ("--group", "https://example.invalid/group"),
        ("--extra", " extra"),
    ],
)
def test_project_lock_unsafe_selectors_are_usage_errors_before_reader_or_installer(
    monkeypatch, selector, unsafe_value
):
    def unavailable(*_args, **_kwargs):
        raise AssertionError("reader or installer must not run")

    monkeypatch.setattr("uv_packsize.cli._read_validated_project_lock", unavailable)
    monkeypatch.setattr("uv_packsize.cli.install_validated_project_lock", unavailable)

    result = CliRunner().invoke(cli, _arguments(selector, unsafe_value, "--json"))

    assert result.exit_code == 2
    assert result.stdout == ""
    assert f"{selector} must be a safe package name." in result.stderr
    assert unsafe_value not in result.output


def test_project_lock_reader_and_installer_failures_are_sanitized_and_keep_json_empty(
    monkeypatch,
):
    _project_double(monkeypatch)

    def fail_install(*_args, **_kwargs):
        raise ProjectLockInstallError(ProjectLockInstallErrorReason.UV_SYNC_FAILED)

    monkeypatch.setattr("uv_packsize.cli.install_validated_project_lock", fail_install)
    result = CliRunner().invoke(cli, _arguments("--json"))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "uv-sync-failed" in result.stderr
    assert str(_PROJECT) not in result.stderr


def test_project_lock_reader_failure_is_exit_three_and_does_not_reflect_input(
    monkeypatch,
):
    def fail_reader(*_args, **_kwargs):
        raise ProjectLockInputError(
            ProjectLockInputErrorReason.INVALID_TOML,
            ProjectLockInputField.LOCK_FILE,
        )

    monkeypatch.setattr("uv_packsize.cli._read_validated_project_lock", fail_reader)
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda _command: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    result = CliRunner().invoke(cli, _arguments("--json"))

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "code=invalid-toml, field=lock-file" in result.stderr
    assert str(_PROJECT) not in result.stderr
