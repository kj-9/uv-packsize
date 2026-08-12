import json
import os
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

import uv_packsize.baseline as baseline_module
import uv_packsize.budget_config_source as budget_source_module
from uv_packsize.analysis import AnalysisContextError, AnalysisContextErrorCode
from uv_packsize.baseline import BaselineError, load_baseline
from uv_packsize.baseline_write import BaselineWriteError
from uv_packsize.budget import BudgetPolicy
from uv_packsize.budget_config_source import (
    BudgetPolicySourceError,
    BudgetPolicySourceErrorReason,
    BudgetPolicySourceSection,
)
from uv_packsize.cli import (
    UvCommandError,
    _command_failure_message,
    _create_venv,
    _install_package,
    _run_uv,
    _uv_version,
    cli,
)
from uv_packsize.comparison_json_render import render_comparison_json
from uv_packsize.diff import (
    ComparisonIncompatibilityReason,
    IncompatibleComparisonError,
)
from uv_packsize.environment import (
    EnvironmentDiscoveryError,
    EnvironmentDiscoveryErrorCode,
)
from uv_packsize.existing_prefix import (
    ExistingPrefixDiscoveryError,
    ExistingPrefixDiscoveryErrorCode,
)
from uv_packsize.installed_metadata import (
    InstalledMetadataAdapterError,
    InstalledMetadataAdapterErrorCode,
)
from uv_packsize.inventory import InventoryScanError, InventoryScanErrorCode
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import BuildPolicy, CaseRule

EXPECTED_VERSION = "0.2.0"
PROJECT_ROOT = Path(__file__).parent.parent


def test_project_metadata():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    project = pyproject.partition("[project]")[2].partition("\n[")[0]

    assert re.search(
        rf'^version = "{re.escape(EXPECTED_VERSION)}"$', project, re.MULTILINE
    )
    assert re.search(r'^requires-python = ">=3\.10"$', project, re.MULTILINE)
    assert '"Development Status :: 5 - Production/Stable"' in project

    classifier_block = re.search(
        r"^classifiers = \[(.*?)^\]$", project, re.MULTILINE | re.DOTALL
    )
    assert classifier_block is not None
    python_classifiers = {
        classifier
        for classifier in re.findall(r'"([^"]+)"', classifier_block.group(1))
        if classifier.startswith("Programming Language :: Python ::")
    }
    assert "Programming Language :: Python :: 3 :: Only" in python_classifiers
    assert python_classifiers - {"Programming Language :: Python :: 3 :: Only"} == {
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    }


def test_project_build_config_limits_setuptools_package_discovery():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    package_find = pyproject.partition("[tool.setuptools.packages.find]")[2].partition(
        "\n["
    )[0]

    assert re.search(r'^include = \["uv_packsize\*"\]$', package_find, re.MULTILINE)


def test_lock_root_metadata_matches_project():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    project = pyproject.partition("[project]")[2].partition("\n[")[0]
    lock = (PROJECT_ROOT / "uv.lock").read_text()
    lock_header = lock.partition("[[package]]")[0]

    project_name = re.search(r'^name = "([^"]+)"$', project, re.MULTILINE)
    project_version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    project_python = re.search(r'^requires-python = "([^"]+)"$', project, re.MULTILINE)
    lock_python = re.search(r'^requires-python = "([^"]+)"$', lock_header, re.MULTILINE)
    assert project_name is not None
    assert project_version is not None
    assert project_python is not None
    assert lock_python is not None

    root_packages = [
        package
        for package in lock.split("[[package]]")[1:]
        if re.search(
            rf'^name = "{re.escape(project_name.group(1))}"$',
            package,
            re.MULTILINE,
        )
    ]
    assert len(root_packages) == 1
    lock_version = re.search(r'^version = "([^"]+)"$', root_packages[0], re.MULTILINE)
    assert lock_version is not None

    assert lock_version.group(1) == project_version.group(1)
    assert lock_python.group(1) == project_python.group(1)
    assert '[tool.uv]\nprerelease = "disallow"' in pyproject
    assert '[options]\nprerelease-mode = "disallow"' in lock


def test_makefile_uses_locked_uv_runs():
    makefile = (PROJECT_ROOT / "makefile").read_text()

    assert re.search(r"^UV_RUN=uv run --locked$", makefile, re.MULTILINE)
    assert re.search(r"^sync:\n\tuv sync$", makefile, re.MULTILINE)
    assert re.search(r"^build:\n\tuv build --no-sources$", makefile, re.MULTILINE)
    assert re.search(r"^verify-build: build$", makefile, re.MULTILINE)


def test_ci_checks_lock_and_supported_python_versions():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    job_pattern = r"^  {job}:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|\Z)"

    test_job = re.search(
        job_pattern.format(job="test"), workflow, re.MULTILINE | re.DOTALL
    )
    assert test_job is not None
    matrix = re.search(
        r"^\s+python-version: \[(?P<versions>[^]]+)\]$",
        test_job.group("body"),
        re.MULTILINE,
    )
    assert matrix is not None
    assert re.findall(r'"([^"]+)"', matrix.group("versions")) == [
        "3.10",
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    ]

    lock_job = re.search(
        job_pattern.format(job="lock"), workflow, re.MULTILINE | re.DOTALL
    )
    assert lock_job is not None
    assert re.search(r"^\s+run: uv lock --check$", lock_job.group("body"), re.MULTILINE)

    for job in [lock_job, test_job]:
        assert re.findall(
            r'^\s+version: "([^"]+)"$', job.group("body"), re.MULTILINE
        ) == ["0.11.3"]

    lint_job = re.search(
        job_pattern.format(job="lint"), workflow, re.MULTILINE | re.DOTALL
    )
    assert lint_job is not None
    assert re.findall(
        r'^\s+version: "([^"]+)"$', lint_job.group("body"), re.MULTILINE
    ) == ["0.11.3"]
    assert workflow.count("uses: astral-sh/setup-uv@v7") == 3
    assert "astral-sh/setup-uv@v6" not in workflow


def test_publish_workflow_verifies_supported_release_artifacts():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "publish.yml").read_text()
    job_pattern = r"^  {job}:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|\Z)"

    test_job = re.search(
        job_pattern.format(job="test"), workflow, re.MULTILINE | re.DOTALL
    )
    deploy_job = re.search(
        job_pattern.format(job="deploy"), workflow, re.MULTILINE | re.DOTALL
    )
    assert test_job is not None
    assert deploy_job is not None

    matrix = re.search(
        r"^\s+python-version: \[(?P<versions>[^]]+)\]$",
        test_job.group("body"),
        re.MULTILINE,
    )
    assert matrix is not None
    assert re.findall(r'"([^"]+)"', matrix.group("versions")) == [
        "3.10",
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    ]

    for job in [test_job, deploy_job]:
        assert re.findall(
            r'^\s+version: "([^"]+)"$', job.group("body"), re.MULTILINE
        ) == ["0.11.3"]

    assert re.search(
        r"^\s+needs: \[verify, test\]$", deploy_job.group("body"), re.MULTILINE
    )
    assert re.search(r"^\s+make verify-build$", deploy_job.group("body"), re.MULTILINE)
    assert deploy_job.group("body").index("make verify-build") < deploy_job.group(
        "body"
    ).index("uses: pypa/gh-action-pypi-publish")
    assert workflow.count("uses: astral-sh/setup-uv@v7") == 3
    assert "astral-sh/setup-uv@v6" not in workflow


def test_update_workflow_uses_the_node_24_setup_uv_major_without_semantic_changes():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "update.yml").read_text()

    assert workflow.count("uses: astral-sh/setup-uv@v7") == 1
    assert "astral-sh/setup-uv@v6" not in workflow
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: write" in workflow
    assert "pull-requests: write" in workflow


def test_publish_workflow_checks_out_and_validates_the_release_tag():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "publish.yml").read_text()

    assert workflow.count("ref: ${{ github.event.release.tag_name }}") == 3
    assert "fetch-depth: 0" in workflow
    assert "RELEASE_TAG: ${{ github.event.release.tag_name }}" in workflow
    assert 'expected_tag="v$(python -c' in workflow
    assert "refs/tags/$RELEASE_TAG^{commit}" in workflow
    assert '"$GITHUB_SHA"' in workflow
    assert "uv lock --check" in workflow
    assert "make ci-check" in workflow


def test_build_verifier_rejects_unexpected_publish_file(tmp_path):
    (tmp_path / "uv_packsize-0.2.0-py3-none-any.whl").touch()
    (tmp_path / "uv_packsize-0.2.0.tar.gz").touch()
    unexpected = tmp_path / "uv_packsize-0.1.1-py3-none-any.whl"
    unexpected.touch()

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "verify_build.py"),
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )

    assert result.returncode != 0
    assert unexpected.name in result.stderr


def test_version(tmp_path):
    dist_info = tmp_path / f"uv_packsize-{EXPECTED_VERSION}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: uv-packsize\nVersion: {EXPECTED_VERSION}\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(PROJECT_ROOT)])

    # A separate process and test-owned dist-info avoid both Click's callback
    # cache and metadata left in the active environment by a previous install.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from uv_packsize.cli import cli; cli(prog_name='uv-packsize')",
            "--version",
        ],
        check=False,
        capture_output=True,
        cwd=tmp_path,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == f"uv-packsize, version {EXPECTED_VERSION}\n"
    assert result.stderr == ""


@pytest.fixture
def installed_venv(tmp_path):
    """An actual stdlib venv with a test-owned installed layout."""

    venv_path = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(venv_path)
    python = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    completed = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    site_packages = Path(completed.stdout.strip())
    return venv_path, python, site_packages


def _record_path(site_packages, path):
    return os.path.relpath(path, site_packages).replace(os.sep, "/")


def _add_distribution(  # noqa: PLR0913
    *,
    venv_path,
    site_packages,
    name,
    version="1.0",
    source=None,
    include_script=True,
    include_data=True,
    missing_file=False,
):
    dist_info = site_packages / f"{name}-{version}.dist-info"
    dist_info.mkdir()
    metadata = dist_info / "METADATA"
    metadata.write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
    if source is None:
        source = site_packages / f"{name}.py"
        source.write_bytes(b"x" * 2048)

    files = [source, metadata]
    if include_script:
        script_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
        script = script_dir / f"{name}-cli"
        script.write_bytes(b"#!/test/script\n")
        files.append(script)
    if include_data:
        data = venv_path / "share" / f"{name}.txt"
        data.parent.mkdir(exist_ok=True)
        data.write_bytes(b"package data")
        files.append(data)

    record = dist_info / "RECORD"
    files.append(record)
    rows = [f"{_record_path(site_packages, file)},," for file in files]
    if missing_file:
        rows.append("missing-file.py,,")
    record.write_text("\n".join(rows) + "\n")
    return source


def _mock_successful_uv_version(monkeypatch):
    monkeypatch.setattr(
        "uv_packsize.cli._run_uv",
        lambda command: subprocess.CompletedProcess(
            command,
            0,
            "uv 0.11.3 (45da18ac3 2026-04-01 aarch64-apple-darwin)\n",
            "",
        ),
    )


def _run_local_layout(  # noqa: PLR0912, PLR0913, PLR0915
    monkeypatch,
    installed_venv,
    package_names,
    *,
    show_scripts=False,
    json_output=False,
    explain=False,
    breakdown=False,
    contributions=False,
    allow_build=False,
    baseline=None,
    comparison_json=False,
    write_baseline=None,
    overwrite_baseline=False,
    budget_config=None,
    max_total=None,
    max_increase=None,
    incomplete_policy=None,
    report_format="standard",
    quiet=False,
    color_mode=None,
):
    venv_path, python, _site_packages = installed_venv
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")

    def create_venv(venv_dir, _python=None, *, err=False, quiet=False):
        assert err is (
            json_output or baseline is not None or write_baseline is not None
        )
        if not quiet:
            click.echo("Creating virtual environment...", err=err)
        shutil.copytree(venv_path, venv_dir, symlinks=True)
        return str(Path(venv_dir) / python.relative_to(venv_path))

    def install_package(
        _python_executable, names, *, build_policy, err=False, quiet=False
    ):
        assert err is (
            json_output or baseline is not None or write_baseline is not None
        )
        expected_policy = (
            BuildPolicy.ALLOW_BUILD if allow_build else BuildPolicy.WHEEL_ONLY
        )
        assert build_policy is expected_policy
        package_count = len(names)
        package_label = "package" if package_count == 1 else "packages"
        possessive = "its" if package_count == 1 else "their"
        if not quiet:
            click.echo(
                f"Installing {package_count} requested {package_label} and {possessive} dependencies...",
                err=err,
            )

    monkeypatch.setattr("uv_packsize.cli._create_venv", create_venv)
    monkeypatch.setattr("uv_packsize.cli._install_package", install_package)
    _mock_successful_uv_version(monkeypatch)
    arguments = [*package_names]
    if show_scripts:
        arguments.append("--bin")
    if json_output:
        arguments.append("--json")
    if comparison_json:
        arguments.append("--comparison-json")
    if explain:
        arguments.append("--explain")
    if breakdown:
        arguments.append("--breakdown")
    if contributions:
        arguments.append("--contributions")
    if allow_build:
        arguments.append("--allow-build")
    if baseline is not None:
        arguments.extend(("--baseline", str(baseline)))
    if write_baseline is not None:
        arguments.extend(("--write-baseline", str(write_baseline)))
    if overwrite_baseline:
        arguments.append("--overwrite-baseline")
    if budget_config is not None:
        arguments.extend(("--budget-config", str(budget_config)))
    if max_total is not None:
        arguments.extend(("--max-total", str(max_total)))
    if max_increase is not None:
        arguments.extend(("--max-increase", str(max_increase)))
    if incomplete_policy is not None:
        arguments.extend(("--incomplete-policy", incomplete_policy))
    if report_format is not None:
        arguments.extend(("--report", report_format))
    if quiet:
        arguments.append("--quiet")
    if color_mode is not None:
        arguments.extend(("--color", color_mode))
    return CliRunner().invoke(cli, arguments)


def test_cli_budget_help_guards_and_source_failures_precede_baseline_and_uv(
    monkeypatch, tmp_path
):
    help_result = CliRunner().invoke(cli, ["--help"])
    assert help_result.exit_code == 0
    assert "--budget-config PATH" in help_result.output
    assert "--max-total BYTES" in help_result.output
    assert "--max-increase BYTES" in help_result.output
    assert "--incomplete-policy [fail|allow-partial]" in help_result.output

    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("baseline loader must not run")
        ),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("uv discovery must not run")
        ),
    )
    secret_config = tmp_path / "secret-policy.toml"
    monkeypatch.setattr(
        "uv_packsize.cli.load_budget_policy",
        lambda *_args: (_ for _ in ()).throw(
            BudgetPolicySourceError(
                BudgetPolicySourceErrorReason.INVALID_TOML,
                BudgetPolicySourceSection.DOCUMENT,
            )
        ),
    )
    source_failure = CliRunner().invoke(
        cli,
        [
            "--budget-config",
            str(secret_config),
            "--baseline",
            "baseline.json",
            "sample==1.0",
        ],
    )
    assert source_failure.exit_code == 3
    assert "code=invalid-toml, field=document" in source_failure.output
    assert str(secret_config) not in source_failure.output

    monkeypatch.setattr(
        "uv_packsize.cli.load_budget_policy",
        lambda *_args: BudgetPolicy(max_increase_logical_bytes=1),
    )
    missing_baseline = CliRunner().invoke(
        cli, ["--budget-config", "policy.toml", "sample==1.0"]
    )
    assert missing_baseline.exit_code == 2
    assert "--max-increase requires --baseline." in missing_baseline.output

    prefix_policy = CliRunner().invoke(
        cli,
        [
            "--prefix",
            "prefix",
            "--site-packages",
            "lib/site-packages",
            "--case-rule",
            "sensitive",
            "--max-total",
            "1",
        ],
    )
    assert prefix_policy.exit_code == 2
    assert "--max-total cannot be used with --prefix." in prefix_policy.output


def test_cli_budget_observable_rewrite_is_safe_exit_three_before_other_inputs(
    monkeypatch, tmp_path
):
    private_config = tmp_path / "credential-token-policy.toml"
    private_config.write_text(
        "[tool.uv-packsize.budget]\nmax_total_logical_bytes = 7 # private-content\n",
        encoding="utf-8",
    )
    real_fstat = budget_source_module.os.fstat
    calls = 0

    def changed_post_fstat(descriptor: int):
        nonlocal calls
        calls += 1
        observed = real_fstat(descriptor)
        if calls == 1:
            return observed
        values = list(observed)
        values[8] += 1
        return budget_source_module.os.stat_result(values)

    monkeypatch.setattr(budget_source_module.os, "fstat", changed_post_fstat)
    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("baseline loader must not run")
        ),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(AssertionError("uv must not run")),
    )

    result = CliRunner().invoke(
        cli,
        [
            "--budget-config",
            str(private_config),
            "--baseline",
            "private-baseline.json",
            "sample==1.0",
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "code=changed-file, field=file" in result.stderr
    for unsafe in (
        "credential-token",
        "private-content",
        "private-baseline",
        "Traceback",
    ):
        assert unsafe not in result.stderr


def test_cli_budget_applies_field_overrides_and_keeps_json_machine_output_empty_on_fail(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    config = tmp_path / "pyproject.toml"
    config.write_text(
        "[tool.uv-packsize.budget]\n"
        "max_total_logical_bytes = 999999\n"
        "incomplete_policy = 'allow-partial'\n"
    )

    passed = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        budget_config=config,
    )
    assert passed.exit_code == 0
    assert "--- Size Budget ---" in passed.stdout
    assert "Incomplete-result policy: allow-partial." in passed.stdout

    failed = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        budget_config=config,
        max_total=0,
    )
    assert failed.exit_code == 5
    assert failed.stdout == ""
    assert "--- Size Budget ---" in failed.stderr
    assert "Maximum total logical size exceeded" in failed.stderr
    assert "Size budget was exceeded." in failed.stderr


def test_cli_budget_config_keeps_unoverridden_fields(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    recorded = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert recorded.exit_code == 0
    baseline = tmp_path / "baseline.json"
    baseline.write_text(recorded.stdout)
    config = tmp_path / "pyproject.toml"
    config.write_text(
        "[tool.uv-packsize.budget]\n"
        "max_total_logical_bytes = 0\n"
        "max_increase_logical_bytes = 999999\n"
        "incomplete_policy = 'allow-partial'\n"
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        budget_config=config,
        max_total=999999,
    )

    assert result.exit_code == 0
    assert "Maximum total logical size" in result.stdout
    assert "Maximum logical-size increase" in result.stdout
    assert "Incomplete-result policy: allow-partial." in result.stdout


def test_cli_budget_pass_keeps_json_and_comparison_json_bytes_and_stderr(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    recorded = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert recorded.exit_code == 0
    baseline = tmp_path / "baseline.json"
    baseline.write_text(recorded.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli.render_analysis_json", lambda *_args: '{"stable":true}\n'
    )
    plain_json = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    policy_json = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        incomplete_policy="fail",
    )
    monkeypatch.setattr(
        "uv_packsize.cli.render_comparison_json",
        lambda *_args: '{"comparison":true}\n',
    )
    plain_comparison = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )
    policy_comparison = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
        incomplete_policy="fail",
    )

    assert plain_json.exit_code == policy_json.exit_code == 0
    assert plain_json.stdout == policy_json.stdout
    assert plain_json.stderr == policy_json.stderr
    assert plain_comparison.exit_code == policy_comparison.exit_code == 0
    assert plain_comparison.stdout == policy_comparison.stdout
    assert plain_comparison.stderr == policy_comparison.stderr


def test_cli_budget_text_violation_follows_primary_report(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], max_total=0
    )

    assert result.exit_code == 5
    assert result.stdout.index("--- Package Sizes ---") < result.stdout.index(
        "--- Size Budget ---"
    )
    assert "Result: FAIL" in result.stdout
    assert "Error: Size budget was exceeded." in result.stderr


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--budget-config", "policy.toml"),
        ("--max-total", "1"),
        ("--max-increase", "1"),
        ("--incomplete-policy", "fail"),
    ],
)
def test_cli_prefix_rejects_every_budget_input_before_external_work(
    monkeypatch, option, value
):
    def unavailable(*_args, **_kwargs):
        raise AssertionError("external work must not run")

    monkeypatch.setattr("uv_packsize.cli.load_budget_policy", unavailable)
    monkeypatch.setattr("uv_packsize.cli.discover_existing_prefix", unavailable)
    result = CliRunner().invoke(
        cli,
        [
            "--prefix",
            "prefix",
            "--site-packages",
            "lib/site-packages",
            "--case-rule",
            "sensitive",
            option,
            value,
        ],
    )

    assert result.exit_code == 2
    assert f"{option} cannot be used with --prefix." in result.output


def test_cli_budget_noop_and_incomplete_policy_contract(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
        missing_file=True,
    )

    no_op = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        incomplete_policy="allow-partial",
    )
    assert no_op.exit_code == 0
    assert "No limits configured; this is a no-op policy." in no_op.stdout
    assert "Completeness is not evaluated by a no-op policy." in no_op.stdout

    incomplete_failure = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        max_total=999999,
    )
    assert incomplete_failure.exit_code == 5
    assert "Result: FAIL" in incomplete_failure.stdout
    assert "Incomplete measurement is not allowed" in incomplete_failure.stdout

    allow_partial = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        max_total=999999,
        incomplete_policy="allow-partial",
    )
    assert allow_partial.exit_code == 0
    assert "Result: PASS" in allow_partial.stdout
    assert "Current measurement completeness: incomplete." in allow_partial.stdout


def test_cli_budget_violation_prevents_baseline_publication(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    target = tmp_path / "baseline.json"

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        write_baseline=target,
        max_total=0,
    )

    assert result.exit_code == 5
    assert result.stdout == ""
    assert not target.exists()
    assert "--- Size Budget ---" in result.stderr


def test_cli_budget_max_increase_requires_and_uses_a_compatible_baseline(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    source = _add_distribution(
        venv_path=venv_path, site_packages=site_packages, name="sample"
    )
    recorded = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert recorded.exit_code == 0
    baseline = tmp_path / "baseline.json"
    baseline.write_text(recorded.stdout)
    source.write_bytes(b"x" * 4096)

    failed = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
        max_increase=0,
    )

    assert failed.exit_code == 5
    assert failed.stdout == ""
    assert "Observed canonical global logical-size increase" in failed.stderr
    assert "Maximum logical-size increase exceeded" in failed.stderr


def test_cli_write_baseline_help_and_guards_precede_external_work(monkeypatch):
    help_result = CliRunner().invoke(cli, ["--help"])
    assert help_result.exit_code == 0
    assert "--write-baseline PATH" in help_result.output
    assert "--overwrite-baseline" in help_result.output

    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("baseline loader must not run")
        ),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("uv discovery must not run")
        ),
    )
    cases = (
        (["--overwrite-baseline", "sample==1.0"], "requires --write-baseline"),
        (
            ["--write-baseline", "out.json", "--prefix", "prefix"],
            "--prefix cannot be used with --write-baseline.",
        ),
        (
            ["--write-baseline", "out.json", "--baseline", "old.json", "sample==1.0"],
            "--baseline cannot be used with --write-baseline.",
        ),
    )
    for arguments, message in cases:
        result = CliRunner().invoke(cli, arguments)
        assert result.exit_code == 2
        assert message in result.output


def test_cli_write_baseline_json_is_stdout_exact_and_called_once(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    target = tmp_path / "baseline.json"
    calls = []
    real_render = __import__(
        "uv_packsize.cli", fromlist=["render_fresh_baseline"]
    ).render_fresh_baseline

    def render_once(result):
        calls.append(result)
        return real_render(result)

    monkeypatch.setattr("uv_packsize.cli.render_fresh_baseline", render_once)
    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        write_baseline=target,
    )
    assert result.exit_code == 0
    assert result.stdout.encode() == target.read_bytes()
    assert len(calls) == 1
    assert result.stderr.endswith("\nCalculation complete.\n")


def test_cli_write_baseline_text_flags_keep_saved_json_and_safe_failures(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    target = tmp_path / "baseline.json"
    plain = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], write_baseline=target
    )
    assert plain.exit_code == 0
    saved = target.read_bytes()
    assert json.loads(saved)["schema_version"] == 1
    assert "--- Package Sizes ---" in plain.stdout

    no_clobber = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], write_baseline=target
    )
    assert no_clobber.exit_code == 3
    assert no_clobber.stdout == ""
    assert "Could not write baseline (code=exists, field=file)." in no_clobber.stderr
    assert target.read_bytes() == saved

    overwrite = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        write_baseline=target,
        overwrite_baseline=True,
    )
    assert overwrite.exit_code == 0
    assert target.read_bytes() == saved

    monkeypatch.setattr(
        "uv_packsize.cli.write_baseline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            BaselineWriteError("unsupported-platform", "file")
        ),
    )
    failed = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        write_baseline=tmp_path / "bad.json",
    )
    assert failed.exit_code == 3
    assert failed.stdout == ""
    assert "code=unsupported-platform, field=file" in failed.stderr


@pytest.mark.parametrize(
    ("options", "report_fragment", "uses_graph"),
    [
        ({"show_scripts": True}, "Binaries in .venv/bin", False),
        ({"explain": True}, "--- Requested Roots ---", True),
        ({"breakdown": True}, "--- File Category Breakdown ---", True),
        ({"contributions": True}, "--- Root Contributions ---", True),
    ],
)
def test_cli_write_baseline_text_presentation_keeps_fresh_payload_and_writes_once(  # noqa: PLR0913
    monkeypatch, installed_venv, tmp_path, options, report_fragment, uses_graph
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    plain = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert plain.exit_code == 0

    rendered = []
    published = []
    graph_calls = []
    real_render = __import__(
        "uv_packsize.cli", fromlist=["render_fresh_baseline"]
    ).render_fresh_baseline
    real_graph = __import__(
        "uv_packsize.cli", fromlist=["build_installed_dependency_graph"]
    ).build_installed_dependency_graph

    def capture_render(result):
        payload = real_render(result)
        rendered.append(payload)
        return payload

    def capture_write(path, payload, *, overwrite):
        published.append((path, payload, overwrite))

    def build_once(*args):
        graph_calls.append(args)
        return real_graph(*args)

    monkeypatch.setattr("uv_packsize.cli.render_fresh_baseline", capture_render)
    monkeypatch.setattr("uv_packsize.cli.write_baseline", capture_write)
    monkeypatch.setattr("uv_packsize.cli.build_installed_dependency_graph", build_once)
    target = tmp_path / "baseline.json"
    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        write_baseline=target,
        **options,
    )

    assert result.exit_code == 0
    assert report_fragment in result.stdout
    assert rendered == [plain.stdout.encode()]
    assert published == [(target, plain.stdout.encode(), False)]
    assert len(graph_calls) == int(uses_graph)
    assert result.stderr.endswith("\nCalculation complete.\n")


@pytest.mark.parametrize("failure_kind", ("presentation", "graph"))
def test_cli_write_baseline_does_not_publish_after_presentation_or_graph_failure(
    monkeypatch, installed_venv, tmp_path, failure_kind
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    published = []
    target = tmp_path / "baseline.json"
    monkeypatch.setattr(
        "uv_packsize.cli.write_baseline",
        lambda *args, **kwargs: published.append((args, kwargs)),
    )
    if failure_kind == "presentation":
        failure = RuntimeError("presentation failed")
        monkeypatch.setattr(
            "uv_packsize.cli.render_analysis_report",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
        )
        options = {}
    else:
        monkeypatch.setattr(
            "uv_packsize.cli.build_installed_dependency_graph",
            lambda *_args: (_ for _ in ()).throw(
                InstalledMetadataAdapterError(
                    InstalledMetadataAdapterErrorCode.CONTEXT_MISMATCH, "private"
                )
            ),
        )
        options = {"explain": True}

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        write_baseline=target,
        **options,
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert not target.exists()
    assert published == []
    assert "Calculating size" in result.stderr


def test_cli_json_write_baseline_ignores_text_options_without_graph_or_payload_change(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not build graph")),
    )
    plain_target = tmp_path / "plain.json"
    plain = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        write_baseline=plain_target,
    )
    decorated_target = tmp_path / "decorated.json"
    decorated = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        show_scripts=True,
        explain=True,
        breakdown=True,
        contributions=True,
        write_baseline=decorated_target,
    )

    assert plain.exit_code == decorated.exit_code == 0
    assert plain.stdout == decorated.stdout
    assert (
        plain.stdout.encode()
        == plain_target.read_bytes()
        == decorated_target.read_bytes()
    )


def test_cli_baseline_compare_renders_only_diff_and_projects_current_directly(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    captured = []
    original = __import__(
        "uv_packsize.cli", fromlist=["analyze_installed_environment"]
    ).analyze_installed_environment

    def capture(**kwargs):
        result = original(**kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr("uv_packsize.cli.analyze_installed_environment", capture)
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    before = baseline.read_bytes()
    baseline_loads = []
    real_load = load_baseline

    def load_once(path):
        baseline_loads.append(path)
        return real_load(path)

    monkeypatch.setattr("uv_packsize.cli.load_baseline", load_once)
    monkeypatch.setattr(
        "uv_packsize.cli.render_analysis_json",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not serialize")),
    )

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], baseline=baseline
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("--- Size Comparison ---\n")
    assert "Calculating size" not in result.stdout
    assert "Calculation complete" not in result.stdout
    assert result.stderr == (
        "Calculating size for 1 requested package...\n"
        "Creating virtual environment...\n"
        "Installing 1 requested package and its dependencies...\n"
        "Analyzing sizes...\n"
        "Comparing with baseline...\n"
    )
    assert baseline.read_bytes() == before
    assert baseline_loads == [baseline]
    assert len(captured) == 2


def test_cli_comparison_json_renders_the_diff_once_without_analysis_roundtrip(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    expected = []
    real_render = render_comparison_json

    def render_once(diff):
        expected.append(diff)
        return real_render(diff)

    monkeypatch.setattr("uv_packsize.cli.render_comparison_json", render_once)
    monkeypatch.setattr(
        "uv_packsize.cli.render_analysis_json",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not serialize")),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )

    assert result.exit_code == 0
    assert result.stdout == real_render(expected[0])
    assert result.stderr == (
        "Calculating size for 1 requested package...\n"
        "Creating virtual environment...\n"
        "Installing 1 requested package and its dependencies...\n"
        "Analyzing sizes...\n"
        "Comparing with baseline...\n"
    )
    assert len(expected) == 1
    assert json.loads(result.stdout)["schema_version"] == 1


def test_cli_comparison_json_ignores_rich_report_without_projection(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli.project_rich_comparison",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not project")),
    )

    default = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )
    rich = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
        report_format="rich",
    )

    assert default.exit_code == rich.exit_code == 0
    assert default.stdout == rich.stdout
    assert default.stderr == rich.stderr


def test_cli_comparison_json_requires_baseline_before_external_work(monkeypatch):
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not inspect uv")),
    )

    result = CliRunner().invoke(cli, ["--comparison-json", "sample==1.0"])

    assert result.exit_code == 2
    assert "--comparison-json requires --baseline." in result.output


@pytest.mark.parametrize(
    "option",
    ["--prefix", "--json", "--bin", "--explain", "--breakdown", "--contributions"],
)
def test_cli_baseline_option_guards_precede_loader_and_uv(monkeypatch, option):
    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not load")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not inspect uv")),
    )
    arguments = ["--baseline", "private-baseline.json", option]
    if option == "--prefix":
        arguments.extend(("/private/prefix", "sample==1.0"))
    else:
        arguments.append("sample==1.0")

    result = CliRunner().invoke(cli, arguments)

    assert result.exit_code == 2
    assert f"{option} cannot be used with --baseline." in result.output


@pytest.mark.parametrize(
    "arguments, message",
    [
        (
            ("--baseline", "private-baseline.json"),
            "Missing argument 'PACKAGE_NAMES...'",
        ),
        (
            (
                "--baseline",
                "private-baseline.json",
                "--site-packages",
                "lib/site",
                "sample==1.0",
            ),
            "--site-packages and --case-rule require --prefix.",
        ),
        (
            (
                "--baseline",
                "private-baseline.json",
                "--case-rule",
                "sensitive",
                "sample==1.0",
            ),
            "--site-packages and --case-rule require --prefix.",
        ),
    ],
)
def test_cli_baseline_shared_fresh_guards_precede_loader_and_uv(
    monkeypatch, arguments, message
):
    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not load")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not inspect uv")),
    )

    result = CliRunner().invoke(cli, list(arguments))

    assert result.exit_code == 2
    assert message in result.output


@pytest.mark.parametrize(
    "failure",
    [BaselineError("read-failed", "file"), BaselineError("malformed-json", "document")],
)
def test_cli_baseline_load_failures_are_safe_and_typed(monkeypatch, failure):
    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    result = CliRunner().invoke(
        cli, ["--baseline", "/private/secret-baseline.json", "sample==1.0"]
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "secret-baseline" not in result.stderr
    assert "Traceback" not in result.stderr
    assert "code=" in result.stderr and "field=" in result.stderr


def test_cli_baseline_close_failure_is_safe_exit_three_before_uv(monkeypatch, tmp_path):
    source = PROJECT_ROOT / "tests" / "golden" / "analysis-result-v1.json"
    private_source = tmp_path / "credential-token-baseline.json"
    private_source.write_bytes(source.read_bytes())
    real_close = baseline_module.os.close

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise OSError("private close detail")

    monkeypatch.setattr(baseline_module.os, "close", close_then_fail)
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda _command: (_ for _ in ()).throw(AssertionError("uv must not run")),
    )

    result = CliRunner().invoke(cli, ["--baseline", str(private_source), "sample==1.0"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "code=read-failed, field=file" in result.stderr
    for unsafe in ("credential-token", "private close detail", "Traceback"):
        assert unsafe not in result.stderr


@pytest.mark.parametrize(
    "failure",
    [BaselineError("read-failed", "file"), BaselineError("malformed-json", "document")],
)
def test_cli_comparison_json_baseline_load_failure_is_safe_exit_three(
    monkeypatch, failure
):
    monkeypatch.setattr(
        "uv_packsize.cli.load_baseline",
        lambda *_args: (_ for _ in ()).throw(failure),
    )

    result = CliRunner().invoke(
        cli,
        [
            "--baseline",
            "/private/secret-baseline.json",
            "--comparison-json",
            "sample==1.0",
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "secret-baseline" not in result.stderr
    assert "Traceback" not in result.stderr
    assert "code=" in result.stderr and "field=" in result.stderr


def test_cli_baseline_context_mismatch_is_safe_exit_four(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "private-baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        allow_build=True,
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert "reason=context-mismatch" in result.stderr
    for unsafe in ("private-baseline", "sample==1.0", "Traceback"):
        assert unsafe not in result.stderr


def test_cli_comparison_json_incompatible_comparison_is_safe_exit_four(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "private-baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli.compare_baselines",
        lambda *_args: (_ for _ in ()).throw(
            IncompatibleComparisonError(
                ComparisonIncompatibilityReason.CONTEXT_MISMATCH
            )
        ),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert "reason=context-mismatch" in result.stderr
    for unsafe in ("private-baseline", "sample==1.0", "Traceback"):
        assert unsafe not in result.stderr


@pytest.mark.parametrize("reason", list(ComparisonIncompatibilityReason))
def test_cli_baseline_maps_each_incompatibility_reason_to_exit_four(
    monkeypatch, installed_venv, tmp_path, reason
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli.compare_baselines",
        lambda *_args: (_ for _ in ()).throw(IncompatibleComparisonError(reason)),
    )

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], baseline=baseline
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert f"reason={reason.value}" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_baseline_operational_failure_keeps_stdout_empty(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr("uv_packsize.cli.load_baseline", lambda _path: object())
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UvCommandError(("uv", "venv"), 9, "", "private diagnostic")
        ),
    )

    result = CliRunner().invoke(cli, ["--baseline", "baseline.json", "sample==1.0"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Calculating size" in result.stderr
    assert "Could not create the virtual environment (uv exit code 9)." in result.stderr
    assert "private diagnostic" not in result.stderr


def test_cli_comparison_json_operational_failure_keeps_stdout_empty(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr("uv_packsize.cli.load_baseline", lambda _path: object())
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UvCommandError(("uv", "venv"), 9, "", "private diagnostic")
        ),
    )

    result = CliRunner().invoke(
        cli,
        ["--baseline", "baseline.json", "--comparison-json", "sample==1.0"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Calculating size" in result.stderr
    assert "Could not create the virtual environment (uv exit code 9)." in result.stderr
    assert "private diagnostic" not in result.stderr


def test_cli_baseline_incomplete_comparison_is_successful_and_partial(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    source = _add_distribution(
        venv_path=venv_path, site_packages=site_packages, name="sample"
    )
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    source.unlink()

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], baseline=baseline
    )

    assert result.exit_code == 0
    assert "Warning: incomplete comparison; deltas may be partial" in result.stdout


def test_cli_comparison_json_incomplete_comparison_is_successful(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    source = _add_distribution(
        venv_path=venv_path, site_packages=site_packages, name="sample"
    )
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    source.unlink()

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["completeness"] == "incomplete"


@pytest.mark.parametrize(
    "failure", [TypeError("private payload"), ValueError("private payload")]
)
def test_cli_comparison_json_render_failure_is_sanitized_and_keeps_stdout_empty(
    monkeypatch, installed_venv, tmp_path, failure
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    assert initial.exit_code == 0
    baseline.write_text(initial.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli.render_comparison_json",
        lambda _diff: (_ for _ in ()).throw(failure),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Could not render comparison JSON." in result.stderr
    assert "private payload" not in result.stderr


def _reported_total(output):
    match = re.search(r"^Total size:\s+(.+)$", output, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_cli_analyzes_actual_local_venv_layout_once(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    real_analyze = __import__(
        "uv_packsize.cli", fromlist=["analyze_installed_environment"]
    )
    original = real_analyze.analyze_installed_environment
    calls = []

    def analyze_once(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr("uv_packsize.cli.analyze_installed_environment", analyze_once)
    result = _run_local_layout(monkeypatch, installed_venv, ["sample==1.0"])

    assert result.exit_code == 0
    assert "Calculating size for 1 requested package..." in result.output
    assert "Analyzing sizes..." in result.output
    assert "sample" in result.output
    assert _reported_total(result.output).endswith("KiB")
    assert result.stderr == ""
    assert len(calls) == 1
    context = calls[0]["context"]
    assert context.requirements == ("sample==1.0",)
    assert context.uv_version == "0.11.3"
    assert context.build_policy is BuildPolicy.WHEEL_ONLY
    assert context.compile_bytecode is False


def test_cli_allow_build_passes_permission_to_installer_and_context(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    calls = []
    original = __import__(
        "uv_packsize.cli", fromlist=["analyze_installed_environment"]
    ).analyze_installed_environment

    def analyze_once(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr("uv_packsize.cli.analyze_installed_environment", analyze_once)
    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], allow_build=True
    )

    assert result.exit_code == 0
    assert calls[0]["context"].build_policy is BuildPolicy.ALLOW_BUILD


def test_bin_is_presentation_only_for_prefix_wide_record_files(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )

    default = _run_local_layout(monkeypatch, installed_venv, ["sample==1.0"])
    with_scripts = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], show_scripts=True
    )

    assert default.exit_code == 0
    assert with_scripts.exit_code == 0
    assert "Binaries in .venv/bin" not in default.output
    assert "Binaries in .venv/bin" in with_scripts.output
    assert "sample-cli" in with_scripts.output
    assert _reported_total(default.output) == _reported_total(with_scripts.output)


def test_cli_report_standard_is_byte_identical_to_the_default(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    default = _run_local_layout(monkeypatch, installed_venv, ["sample==1.0"])
    explicit = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format="standard",
    )

    assert default.exit_code == explicit.exit_code == 0
    assert default.stdout == explicit.stdout
    assert default.stderr == explicit.stderr


def test_cli_rich_report_replaces_primary_and_keeps_only_binary_section(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    report = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        show_scripts=True,
        report_format="rich",
    )

    assert report.exit_code == 0
    assert "--- Rich Analysis Summary ---" in report.stdout
    assert "--- Largest Distributions (Showing 1 of 1) ---" in report.stdout
    assert "--- Package Sizes ---" not in report.stdout
    assert "--- Binaries in .venv/bin ---" in report.stdout
    assert report.stdout.index("Largest Distributions") < report.stdout.index(
        "Binaries"
    )


def test_cli_json_ignores_rich_report_without_projecting_or_building_graph(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli.project_rich_analysis",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not project")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not build graph")),
    )

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    rich = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        report_format="rich",
        explain=True,
        breakdown=True,
        contributions=True,
    )

    assert default.exit_code == rich.exit_code == 0
    assert default.stdout == rich.stdout
    assert default.stderr == rich.stderr


def test_cli_rich_projection_failure_is_sanitized(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli.project_rich_analysis",
        lambda *_args: (_ for _ in ()).throw(ValueError("private/path/token")),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format="rich",
    )

    assert result.exit_code == 1
    assert "Could not render rich report." in result.output
    assert "private/path/token" not in result.output


def test_cli_rich_budget_failure_keeps_primary_before_budget_section(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format="rich",
        max_total=0,
    )

    assert result.exit_code == 5
    assert result.stdout.index("--- Rich Analysis Summary ---") < result.stdout.index(
        "--- Size Budget ---"
    )
    assert "--- Package Sizes ---" not in result.stdout


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_quiet_suppresses_only_fresh_text_progress(
    monkeypatch, installed_venv, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format=report_format,
        quiet=True,
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    expected_title = (
        "Package Sizes" if report_format == "standard" else "Rich Analysis Summary"
    )
    assert expected_title in result.stdout
    for status in (
        "Calculating size",
        "Creating virtual environment",
        "Installing 1 requested package",
        "Analyzing sizes",
        "Calculation complete",
    ):
        assert status not in result.output


def test_cli_quiet_json_preserves_stdout_bytes_and_suppresses_stderr_progress(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    quiet = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        quiet=True,
        report_format="rich",
    )

    assert default.exit_code == quiet.exit_code == 0
    assert quiet.stdout == default.stdout
    assert quiet.stderr == ""


def test_cli_quiet_graph_and_write_keep_final_report_and_baseline(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    target = tmp_path / "baseline.json"

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format="rich",
        explain=True,
        breakdown=True,
        contributions=True,
        write_baseline=target,
        quiet=True,
    )

    assert result.exit_code == 0
    assert "--- Rich Analysis Summary ---" in result.stdout
    assert "--- Requested Roots ---" in result.stdout
    assert "--- File Category Breakdown ---" in result.stdout
    assert "--- Root Contributions ---" in result.stdout
    assert result.stderr == ""
    assert json.loads(target.read_text())["schema_version"] == 1


def test_cli_quiet_json_write_preserves_stdout_and_baseline_bytes(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    default_target = tmp_path / "default.json"
    quiet_target = tmp_path / "quiet.json"

    default = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        write_baseline=default_target,
    )
    quiet = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        write_baseline=quiet_target,
        quiet=True,
    )

    assert quiet.exit_code == default.exit_code == 0
    assert quiet.stdout == default.stdout
    assert quiet_target.read_bytes() == default_target.read_bytes()
    assert quiet.stderr == ""


def test_cli_quiet_comparison_json_preserves_bytes_and_suppresses_progress(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    baseline.write_text(initial.stdout)

    default = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )
    quiet = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
        quiet=True,
    )

    assert default.exit_code == quiet.exit_code == 0
    assert quiet.stdout == default.stdout
    assert quiet.stderr == ""


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_quiet_text_comparison_keeps_final_report(
    monkeypatch, installed_venv, tmp_path, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    baseline.write_text(initial.stdout)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        report_format=report_format,
        quiet=True,
    )

    assert result.exit_code == 0
    expected = (
        "Size Comparison" if report_format == "standard" else "Rich Comparison Summary"
    )
    assert expected in result.stdout
    assert result.stderr == ""


def test_cli_quiet_json_budget_violation_keeps_budget_and_error(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        max_total=0,
        quiet=True,
    )

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "--- Size Budget ---" in result.stderr
    assert "Error: Size budget was exceeded." in result.stderr
    assert "Calculating size" not in result.stderr


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_quiet_text_budget_violation_keeps_report_budget_and_error(
    monkeypatch, installed_venv, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format=report_format,
        max_total=0,
        quiet=True,
    )

    assert result.exit_code == 5
    expected = (
        "Package Sizes" if report_format == "standard" else "Rich Analysis Summary"
    )
    assert expected in result.stdout
    assert "--- Size Budget ---" in result.stdout
    assert "Error: Size budget was exceeded." in result.stderr
    assert "Calculating size" not in result.output


def test_cli_quiet_operational_failure_keeps_error_and_empty_stdout(
    monkeypatch, installed_venv
):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UvCommandError(("uv", "venv"), 7, "", "private failure")
        ),
    )

    result = CliRunner().invoke(cli, ["--json", "--quiet", "sample==1.0"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Could not create the virtual environment (uv exit code 7)." in result.stderr
    assert "Calculating size" not in result.stderr
    assert "private failure" not in result.stderr


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_color_always_decorates_only_final_human_report(
    monkeypatch, installed_venv, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    plain = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
        contributions=True,
        max_total=10_000,
        report_format=report_format,
    )
    colored = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
        contributions=True,
        max_total=10_000,
        report_format=report_format,
        color_mode="always",
    )

    assert colored.exit_code == plain.exit_code == 0
    assert click.unstyle(colored.stdout) == plain.stdout
    assert colored.stderr == plain.stderr
    assert "\x1b[" in colored.stdout
    assert "Result: \x1b[32mPASS\x1b[0m" in colored.stdout
    for progress in (
        "Calculating size",
        "Creating virtual environment",
        "Installing 1 requested package",
        "Analyzing sizes",
        "Explaining dependencies",
        "Calculation complete",
    ):
        line = next(line for line in colored.output.splitlines() if progress in line)
        assert "\x1b[" not in line


@pytest.mark.parametrize(
    ("stdout_is_tty", "term", "no_color"),
    [
        (False, "xterm-256color", None),
        (True, "dumb", None),
        (True, "xterm-256color", ""),
    ],
)
def test_cli_new_text_defaults_are_plain_rich_when_auto_is_disabled(  # noqa: PLR0913
    monkeypatch, installed_venv, stdout_is_tty, term, no_color
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr("uv_packsize.cli._stdout_is_tty", lambda: stdout_is_tty)
    monkeypatch.setenv("TERM", term)
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format=None,
        color_mode=None,
    )

    assert result.exit_code == 0
    assert "--- Rich Analysis Summary ---" in result.stdout
    assert "--- Largest Distributions (Showing 1 of 1) ---" in result.stdout
    assert "--- Package Sizes ---" not in result.stdout
    assert "\x1b[" not in result.output


def test_cli_new_text_defaults_color_rich_report_on_eligible_tty(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr("uv_packsize.cli._stdout_is_tty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format=None,
        color_mode=None,
    )

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    assert "--- Rich Analysis Summary ---" in click.unstyle(result.stdout)
    assert "\x1b[" not in result.stderr


def test_cli_new_text_defaults_use_largest_rich_comparison(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    recorded = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    baseline.write_text(recorded.stdout)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        report_format=None,
        color_mode=None,
    )

    assert result.exit_code == 0
    assert "--- Rich Comparison Summary ---" in result.stdout
    assert "--- Largest Distribution Changes (Showing 0 of 0) ---" in result.stdout
    assert "--- Size Comparison ---" not in result.stdout


def test_cli_explicit_standard_never_preserves_the_full_plain_escape(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr("uv_packsize.cli._stdout_is_tty", lambda: True)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        report_format="standard",
        color_mode="never",
    )

    assert result.exit_code == 0
    assert "--- Package Sizes ---" in result.stdout
    assert "--- Rich Analysis Summary ---" not in result.stdout
    assert "\x1b[" not in result.output


def test_cli_color_never_is_byte_exact_with_the_default(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    default = _run_local_layout(monkeypatch, installed_venv, ["sample==1.0"])
    never = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        color_mode="never",
    )

    assert never.exit_code == default.exit_code == 0
    assert never.stdout == default.stdout
    assert never.stderr == default.stderr


@pytest.mark.parametrize(
    ("stdout_is_tty", "term", "no_color", "has_color"),
    [
        (True, "xterm-256color", None, True),
        (False, "xterm-256color", None, False),
        (True, "dumb", None, False),
        (True, "xterm-256color", "", False),
    ],
)
def test_cli_color_auto_uses_only_stdout_tty_term_and_no_color(  # noqa: PLR0913
    monkeypatch, installed_venv, stdout_is_tty, term, no_color, has_color
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr("uv_packsize.cli._stdout_is_tty", lambda: stdout_is_tty)
    monkeypatch.setenv("TERM", term)
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        color_mode="auto",
    )

    assert result.exit_code == 0
    assert ("\x1b[" in result.stdout) is has_color


def test_cli_color_always_ignores_non_tty_term_and_no_color(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr("uv_packsize.cli._stdout_is_tty", lambda: False)
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("NO_COLOR", "1")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        color_mode="always",
    )

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout


@pytest.mark.parametrize("color_mode", ["auto", "always", "never"])
def test_cli_json_ignores_every_color_mode(monkeypatch, installed_venv, color_mode):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    selected = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        color_mode=color_mode,
    )

    assert selected.exit_code == default.exit_code == 0
    assert selected.stdout == default.stdout
    assert selected.stderr == default.stderr
    assert "\x1b[" not in selected.output


def test_cli_json_ignores_new_text_defaults_without_tty_inspection(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    defaults = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        report_format=None,
        color_mode=None,
    )
    legacy_flags = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        report_format="standard",
        color_mode="never",
    )

    assert defaults.exit_code == legacy_flags.exit_code == 0
    assert defaults.stdout == legacy_flags.stdout
    assert defaults.stderr == legacy_flags.stderr


def test_cli_color_always_keeps_operational_errors_plain(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UvCommandError(("uv", "venv"), 7, "", "private failure")
        ),
    )

    result = CliRunner().invoke(cli, ["--color", "always", "sample==1.0"])

    assert result.exit_code == 1
    assert "Could not create the virtual environment" in result.stderr
    assert "\x1b[" not in result.output


def test_cli_invalid_color_usage_is_plain():
    result = CliRunner().invoke(cli, ["--color", "sometimes", "sample"])

    assert result.exit_code == 2
    assert "Invalid value for '--color'" in result.stderr
    assert "\x1b[" not in result.output


def test_cli_color_always_decorates_comparison_and_keeps_progress_plain(
    monkeypatch, installed_venv, tmp_path
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    baseline.write_text(initial.stdout)

    plain = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], baseline=baseline
    )
    colored = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        report_format="rich",
        color_mode="always",
    )
    rich_plain = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        report_format="rich",
    )

    assert plain.exit_code == colored.exit_code == rich_plain.exit_code == 0
    assert click.unstyle(colored.stdout) == rich_plain.stdout
    assert colored.stderr == rich_plain.stderr
    assert "\x1b[" in colored.stdout
    assert "\x1b[" not in colored.stderr


@pytest.mark.parametrize("color_mode", ["auto", "always", "never"])
def test_cli_comparison_json_ignores_every_color_mode(
    monkeypatch, installed_venv, tmp_path, color_mode
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    baseline = tmp_path / "baseline.json"
    initial = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    baseline.write_text(initial.stdout)
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    default = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
    )
    selected = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        baseline=baseline,
        comparison_json=True,
        color_mode=color_mode,
    )

    assert selected.exit_code == default.exit_code == 0
    assert selected.stdout == default.stdout
    assert selected.stderr == default.stderr
    assert "\x1b[" not in selected.output


def test_cli_color_budget_failure_decorates_report_but_not_error(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        max_total=0,
        color_mode="always",
    )

    assert result.exit_code == 5
    assert "Result: \x1b[31mFAIL\x1b[0m" in result.stdout
    assert "Error: Size budget was exceeded." in result.stderr
    assert "\x1b[" not in result.stderr


def test_cli_json_budget_failure_ignores_color_and_keeps_stderr_plain(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        max_total=0,
        color_mode="always",
    )

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "--- Size Budget ---" in result.stderr
    assert "Error: Size budget was exceeded." in result.stderr
    assert "\x1b[" not in result.stderr


def test_cli_json_writes_only_the_stable_serializer_to_stdout(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    real_analyze = __import__(
        "uv_packsize.cli", fromlist=["analyze_installed_environment"]
    )
    original = real_analyze.analyze_installed_environment
    results = []

    def capture_result(**kwargs):
        result = original(**kwargs)
        results.append(result)
        return result

    monkeypatch.setattr("uv_packsize.cli.analyze_installed_environment", capture_result)
    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )

    assert result.exit_code == 0
    assert result.stdout == render_analysis_json(results[0])
    assert json.loads(result.stdout)["schema_version"] == 1
    assert "Calculating size" not in result.stdout
    assert "Package Sizes" not in result.stdout
    assert result.stderr == (
        "Calculating size for 1 requested package...\n"
        "Creating virtual environment...\n"
        "Installing 1 requested package and its dependencies...\n"
        "Analyzing sizes...\n"
        "\nCalculation complete.\n"
    )


def test_cli_json_is_repeatable_and_ignores_bin_presentation(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    repeated = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    with_bin = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        show_scripts=True,
        json_output=True,
    )

    assert default.exit_code == repeated.exit_code == with_bin.exit_code == 0
    assert default.stdout == repeated.stdout == with_bin.stdout
    assert default.stderr == repeated.stderr == with_bin.stderr


def test_cli_json_ignores_explain_without_reading_installed_metadata(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.summarize_footprint",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not be called")),
    )

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    with_explain = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        json_output=True,
        explain=True,
    )

    assert default.exit_code == with_explain.exit_code == 0
    assert default.stdout == with_explain.stdout
    assert default.stderr == with_explain.stderr


def test_cli_json_ignores_all_text_only_options_without_reading_metadata(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.summarize_footprint",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.summarize_root_contributions",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not be called")),
    )

    default = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], json_output=True
    )
    for options in (
        {"breakdown": True},
        {"contributions": True},
        {"explain": True, "breakdown": True},
        {"explain": True, "breakdown": True, "contributions": True},
    ):
        text_options = _run_local_layout(
            monkeypatch,
            installed_venv,
            ["sample==1.0"],
            json_output=True,
            **options,
        )
        assert text_options.exit_code == default.exit_code == 0
        assert text_options.stdout == default.stdout
        assert text_options.stderr == default.stderr


def test_cli_breakdown_does_not_sanitize_footprint_invariant_errors(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    failure = ValueError("footprint invariant failure")
    monkeypatch.setattr(
        "uv_packsize.cli.summarize_footprint",
        lambda *_args: (_ for _ in ()).throw(failure),
    )

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], breakdown=True
    )

    assert result.exit_code == 1
    assert result.exception is failure
    assert "Could not explain installed dependencies." not in result.output


def test_cli_breakdown_renders_categories_and_roles_once(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    calls = []
    original = __import__(
        "uv_packsize.cli", fromlist=["build_installed_dependency_graph"]
    ).build_installed_dependency_graph

    def build_once(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr("uv_packsize.cli.build_installed_dependency_graph", build_once)
    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], breakdown=True
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert "Explaining dependencies..." not in result.output
    assert "--- File Category Breakdown ---" in result.output
    assert "--- Dependency Size Attribution ---" in result.output
    assert "self" in result.output
    assert _reported_total(result.output) in result.output


def test_cli_explain_and_breakdown_composes_sections_without_duplicate_warning(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    (site_packages / "sample-1.0.dist-info" / "METADATA").unlink()

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
    )

    assert result.exit_code == 0
    assert "Explaining dependencies..." in result.output
    assert "--- Requested Roots ---" in result.output
    assert "--- File Category Breakdown ---" in result.output
    assert "Unavailable: incomplete dependency graph." in result.output
    assert result.output.count("Warning: incomplete dependency graph") == 1


def test_cli_contributions_renders_once_and_composes_all_sections(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    calls = []
    original = __import__(
        "uv_packsize.cli", fromlist=["build_installed_dependency_graph"]
    ).build_installed_dependency_graph

    def build_once(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr("uv_packsize.cli.build_installed_dependency_graph", build_once)
    default = _run_local_layout(monkeypatch, installed_venv, ["sample==1.0"])
    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
        contributions=True,
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert (
        result.output.partition("\n\n--- Requested Roots ---")[0].split(
            "Explaining dependencies...\n", maxsplit=1
        )[1]
        == default.output.split("Analyzing sizes...\n", maxsplit=1)[1].rsplit(
            "\n\nCalculation complete.\n", maxsplit=1
        )[0]
    )
    assert result.output.count("--- Package Sizes ---") == 1
    assert (
        result.output.index("--- Requested Roots ---")
        < result.output.index("--- File Category Breakdown ---")
        < result.output.index("--- Root Contributions ---")
    )


def test_cli_rich_report_composes_explanations_with_one_graph_build(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    calls = []
    original = __import__(
        "uv_packsize.cli", fromlist=["build_installed_dependency_graph"]
    ).build_installed_dependency_graph

    def build_once(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr("uv_packsize.cli.build_installed_dependency_graph", build_once)
    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
        contributions=True,
        report_format="rich",
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert result.output.count("--- Rich Analysis Summary ---") == 1
    assert "--- Package Sizes ---" not in result.output
    assert (
        result.output.index("--- Requested Roots ---")
        < result.output.index("--- File Category Breakdown ---")
        < result.output.index("--- Root Contributions ---")
    )


def test_cli_contributions_composes_incomplete_warning_once(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    (site_packages / "sample-1.0.dist-info" / "METADATA").unlink()

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["sample==1.0"],
        explain=True,
        breakdown=True,
        contributions=True,
    )

    assert result.exit_code == 0
    assert result.output.count("Warning: incomplete dependency graph") == 1
    assert result.output.count("Unavailable: incomplete dependency graph.") == 4
    assert "--- Root Contributions ---" in result.output


def test_cli_explain_renders_installed_metadata_attribution(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], explain=True
    )

    assert result.exit_code == 0
    assert "Explaining dependencies..." in result.output
    assert "--- Requested Roots ---" in result.output
    assert "--- Dependency Attribution ---" in result.output
    assert "--- Dependency Paths ---" in result.output
    assert "1  sample  recognized" in result.output


def test_cli_explain_reports_incomplete_metadata_graph_without_failing(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    (site_packages / "sample-1.0.dist-info" / "METADATA").unlink()

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], explain=True
    )

    assert result.exit_code == 0
    assert (
        "Warning: incomplete dependency graph (missing-metadata: 1)." in result.output
    )


@pytest.mark.parametrize(
    "failure",
    [
        InstalledMetadataAdapterError(
            InstalledMetadataAdapterErrorCode.CONTEXT_MISMATCH,
            "/private/tmp/secret-environment",
        ),
        ValueError("secret requirement @ https://token@example.invalid/simple"),
    ],
)
def test_cli_explain_sanitizes_expected_bridge_failures(
    monkeypatch, installed_venv, failure
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(failure),
    )

    result = _run_local_layout(
        monkeypatch,
        installed_venv,
        ["private @ https://token@example.invalid/simple"],
        explain=True,
    )

    assert result.exit_code == 1
    assert "Could not explain installed dependencies." in result.stderr
    public_output = result.stdout + result.stderr
    for unsafe_value in (
        "secret-environment",
        "secret requirement",
        "token@example.invalid",
        "Traceback",
    ):
        assert unsafe_value not in public_output


def test_cli_explain_does_not_mask_programmer_errors(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="sample",
    )
    failure = TypeError("programmer bug")
    monkeypatch.setattr(
        "uv_packsize.cli.build_installed_dependency_graph",
        lambda *_args: (_ for _ in ()).throw(failure),
    )

    result = _run_local_layout(
        monkeypatch, installed_venv, ["sample==1.0"], explain=True
    )

    assert result.exit_code == 1
    assert result.exception is failure


def test_cli_help_describes_json_and_bin_interaction():
    result = CliRunner().invoke(cli, ["--help"])
    normalized_help = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "--json" in result.output
    assert "Write the versioned analysis result as JSON" in result.output
    assert "stdout." in result.output
    assert "--report [standard|rich]" in result.output
    assert (
        "Rich shows a redacted primary top-five summary; ignored with --json or "
        "--comparison-json. [default: rich]" in normalized_help
    )
    assert "--bin" in result.output
    assert "Text output only:" in result.output
    assert "--explain" in result.output
    assert "installed-metadata" in result.output
    assert "attribution." in result.output
    assert "--breakdown" in result.output
    assert "global file-category" in result.output
    assert "dependency-role sizes." in result.output
    assert "--contributions" in result.output
    assert "non-split requested-" in result.output
    assert "root byte contributions." in result.output
    assert "--allow-build" in result.output
    assert "Allow source builds during installation;" in result.output
    assert "default." in result.output
    assert "--prefix" in result.output
    assert "--site-packages REL" in result.output
    assert "--case-rule" in result.output


def test_cli_json_invalid_usage_keeps_click_exit_code_two():
    result = CliRunner().invoke(cli, ["--json"])

    assert result.exit_code == 2
    assert "Missing argument 'PACKAGE_NAMES...'" in result.output


def test_cli_displays_resolved_distributions_and_incomplete_warning(
    monkeypatch, installed_venv
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="resolved-package",
        missing_file=True,
    )

    result = _run_local_layout(monkeypatch, installed_venv, ["input-name>=1"])

    assert result.exit_code == 0
    assert "resolved-package" in result.output
    assert "Warning: incomplete analysis (missing-file: 1)." in result.output


def test_cli_reports_duplicate_owned_files_once_globally(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    shared = _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="first",
        include_script=False,
        include_data=False,
    )
    _add_distribution(
        venv_path=venv_path,
        site_packages=site_packages,
        name="second",
        source=shared,
        include_script=False,
        include_data=False,
    )

    result = _run_local_layout(monkeypatch, installed_venv, ["first", "second"])

    assert result.exit_code == 0
    assert "first" in result.output
    assert "second" in result.output
    assert "duplicate-owned files are counted once globally" in result.output


def test_uv_not_found(monkeypatch):
    """Test that the CLI exits gracefully if uv is not installed."""
    monkeypatch.setenv("PATH", "")
    runner = CliRunner()
    result = runner.invoke(cli, ["iniconfig==2.0.0"])
    assert result.exit_code == 1
    assert "'uv' command not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_uv_preserves_failure_details(monkeypatch):
    command = ["uv", "example", "--flag"]

    def fail(_command, **kwargs):
        assert _command == command
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        return subprocess.CompletedProcess(
            _command,
            23,
            stdout="captured stdout",
            stderr="captured stderr",
        )

    monkeypatch.setattr("uv_packsize.cli.subprocess.run", fail)

    with pytest.raises(UvCommandError) as raised:
        _run_uv(command)

    assert raised.value.command == tuple(command)
    assert raised.value.exit_code == 23
    assert raised.value.stdout == "captured stdout"
    assert raised.value.stderr == "captured stderr"

    empty_output = UvCommandError(command, 1, None, None)
    assert empty_output.stdout == ""
    assert empty_output.stderr == ""


def test_run_uv_returns_successful_result(monkeypatch):
    command = ["uv", "example"]
    completed = subprocess.CompletedProcess(
        command, 0, stdout="captured stdout", stderr="captured stderr"
    )
    monkeypatch.setattr(
        "uv_packsize.cli.subprocess.run", lambda _command, **_kwargs: completed
    )

    assert _run_uv(command) is completed


def test_run_uv_converts_os_error(monkeypatch):
    command = ["uv", "example"]

    def fail(_command, **_kwargs):
        raise OSError("could not start uv")

    monkeypatch.setattr("uv_packsize.cli.subprocess.run", fail)

    with pytest.raises(UvCommandError) as raised:
        _run_uv(command)

    assert raised.value.command == tuple(command)
    assert raised.value.exit_code == 127
    assert raised.value.stdout == ""
    assert raised.value.stderr == "could not start uv"
    assert isinstance(raised.value.__cause__, OSError)


def test_command_failure_does_not_expose_untrusted_uv_diagnostics():
    error = UvCommandError(
        ["uv", "pip", "install", "secret-command-value"],
        9,
        "https://token@example.invalid/simple\n/private/tmp/venv",
        "https://token@example.invalid/error\n/private/tmp/venv",
    )

    message = _command_failure_message(error)

    assert "Could not install the requested packages (uv exit code 9)." in message
    assert "secret-command-value" not in message
    assert "token@example.invalid" not in message
    assert "/private/tmp/venv" not in message


def test_create_venv_propagates_uv_failure(monkeypatch, tmp_path):
    failure = UvCommandError(["uv", "venv"], 2, "stdout", "stderr")
    venv_dir = tmp_path / "venv"

    def fail(command):
        assert command == ["uv", "venv", "--python", "0.0", venv_dir]
        raise failure

    monkeypatch.setattr("uv_packsize.cli._run_uv", fail)

    with pytest.raises(UvCommandError) as raised:
        _create_venv(venv_dir, "0.0")

    assert raised.value is failure


@pytest.mark.parametrize(
    ("build_policy", "expected_command"),
    [
        (
            BuildPolicy.WHEEL_ONLY,
            [
                "uv",
                "pip",
                "install",
                "--python",
                "/venv/bin/python",
                "--no-build",
                "example==1.0",
            ],
        ),
        (
            BuildPolicy.ALLOW_BUILD,
            [
                "uv",
                "pip",
                "install",
                "--python",
                "/venv/bin/python",
                "example==1.0",
            ],
        ),
    ],
)
def test_install_package_propagates_uv_failure(
    monkeypatch, build_policy, expected_command
):
    failure = UvCommandError(["uv", "pip", "install"], 1, "stdout", "stderr")

    def fail(command):
        assert command == expected_command
        raise failure

    monkeypatch.setattr("uv_packsize.cli._run_uv", fail)

    with pytest.raises(UvCommandError) as raised:
        _install_package(
            "/venv/bin/python",
            ["example==1.0"],
            build_policy=build_policy,
        )

    assert raised.value is failure


@pytest.mark.parametrize(
    ("failed_stage", "expected_summary"),
    [
        ("venv", "Could not create the virtual environment"),
        (
            "install",
            "Could not install the requested packages with the wheel-only policy",
        ),
    ],
)
def test_cli_formats_uv_failures_without_traceback(
    monkeypatch, failed_stage, expected_summary
):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")

    def run(command):
        stage = "venv" if command[1] == "venv" else "install"
        if stage == failed_stage:
            raise UvCommandError(
                [*command, "secret-command-value"],
                2,
                "https://token@example.invalid/simple",
                "/private/tmp/venv: specific uv diagnostic",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("uv_packsize.cli._run_uv", run)

    requirements = [
        "private @ https://token@example.invalid/simple",
        "/private/tmp/secret-package.whl",
    ]
    result = CliRunner().invoke(cli, [*requirements, "--python", "0.0"])
    public_output = result.stdout + result.stderr

    assert result.exit_code != 0
    assert result.exit_code == 1
    assert "Calculating size for 2 requested packages..." in result.stdout
    if failed_stage == "install":
        assert (
            "Installing 2 requested packages and their dependencies..." in result.stdout
        )
    assert expected_summary in result.stderr
    assert "uv exit code 2" in result.stderr
    if failed_stage == "install":
        assert "A compatible wheel may be unavailable" in result.stderr
        assert "--allow-build only if you trust the package source" in result.stderr
    assert "secret-command-value" not in public_output
    assert "token@example.invalid" not in public_output
    assert "/private/tmp/venv" not in public_output
    assert "private @ https://token@example.invalid/simple" not in public_output
    assert "/private/tmp/secret-package.whl" not in public_output
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("failed_stage", ["venv", "install"])
def test_cli_json_uv_failures_keep_stdout_empty_and_stderr_sanitized(
    monkeypatch, failed_stage
):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")

    def run(command):
        stage = "venv" if command[1] == "venv" else "install"
        if stage == failed_stage:
            raise UvCommandError(
                [*command, "secret-command-value"],
                2,
                "https://token@example.invalid/simple",
                "/private/tmp/venv: specific uv diagnostic",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("uv_packsize.cli._run_uv", run)
    requirements = [
        "private @ https://token@example.invalid/simple",
        "/private/tmp/secret-package.whl",
    ]
    result = CliRunner().invoke(cli, ["--json", *requirements])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Calculating size for 2 requested packages..." in result.stderr
    assert "Could not" in result.stderr
    for unsafe_value in (
        "secret-command-value",
        "token@example.invalid",
        "/private/tmp/venv",
        "private @ https://token@example.invalid/simple",
        "/private/tmp/secret-package.whl",
        "Traceback",
    ):
        assert unsafe_value not in result.stderr


def test_uv_version_requires_a_single_safe_version_line(monkeypatch):
    monkeypatch.setattr(
        "uv_packsize.cli._run_uv",
        lambda command: subprocess.CompletedProcess(
            command,
            0,
            "uv 0.11.3 (45da18ac3 2026-04-01 aarch64-apple-darwin)\n",
            "",
        ),
    )
    assert _uv_version() == "0.11.3"

    monkeypatch.setattr(
        "uv_packsize.cli._run_uv",
        lambda command: subprocess.CompletedProcess(
            command, 0, "uv 0.11.3\nsecret output", ""
        ),
    )
    with pytest.raises(ValueError, match="invalid uv version output"):
        _uv_version()


def test_cli_rejects_malformed_uv_version_without_echoing_output(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda _venv_dir, _python=None, **_kwargs: "/venv/bin/python",
    )
    monkeypatch.setattr(
        "uv_packsize.cli._install_package", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "uv_packsize.cli._run_uv",
        lambda command: subprocess.CompletedProcess(command, 0, "secret output", ""),
    )

    result = CliRunner().invoke(cli, ["sample"])

    assert result.exit_code == 1
    assert "Could not determine the uv version." in result.stderr
    assert "secret output" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_formats_uv_version_failure_without_traceback(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda _venv_dir, _python=None, **_kwargs: "/venv/bin/python",
    )
    monkeypatch.setattr(
        "uv_packsize.cli._install_package", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "uv_packsize.cli._run_uv",
        lambda command: (_ for _ in ()).throw(
            UvCommandError(
                command,
                2,
                "https://token@example.invalid/simple",
                "/private/tmp/venv: specific uv diagnostic",
            )
        ),
    )

    requirements = [
        "private @ https://token@example.invalid/simple",
        "/private/tmp/secret-package.whl",
    ]
    result = CliRunner().invoke(cli, requirements)
    public_output = result.stdout + result.stderr

    assert result.exit_code == 1
    assert "Calculating size for 2 requested packages..." in result.stdout
    assert "Could not determine the uv version (uv exit code 2)." in result.stderr
    assert "token@example.invalid" not in public_output
    assert "/private/tmp/venv" not in public_output
    assert "specific uv diagnostic" not in public_output
    assert "private @ https://token@example.invalid/simple" not in public_output
    assert "/private/tmp/secret-package.whl" not in public_output
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            EnvironmentDiscoveryError(
                EnvironmentDiscoveryErrorCode.INVALID_VENV, "secret-path"
            ),
            "Could not inspect the temporary environment (invalid-venv).",
        ),
        (
            AnalysisContextError(
                AnalysisContextErrorCode.CASE_RULE_MISMATCH, "secret-path"
            ),
            "Could not analyze the installed environment (case-rule-mismatch).",
        ),
        (
            InventoryScanError(InventoryScanErrorCode.FILESYSTEM_ERROR, "secret-path"),
            "Could not analyze installed files (filesystem-error).",
        ),
    ],
)
def test_cli_sanitizes_expected_analysis_failures(monkeypatch, failure, expected):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda _venv_dir, _python=None, **_kwargs: "/venv/bin/python",
    )
    monkeypatch.setattr(
        "uv_packsize.cli._install_package", lambda *_args, **_kwargs: None
    )
    _mock_successful_uv_version(monkeypatch)
    if isinstance(failure, EnvironmentDiscoveryError):
        monkeypatch.setattr(
            "uv_packsize.cli.discover_installed_environment",
            lambda **_kwargs: (_ for _ in ()).throw(failure),
        )
    else:
        monkeypatch.setattr(
            "uv_packsize.cli.discover_installed_environment",
            lambda **_kwargs: SimpleNamespace(context=object(), layouts=()),
        )
        monkeypatch.setattr(
            "uv_packsize.cli.analyze_installed_environment",
            lambda **_kwargs: (_ for _ in ()).throw(failure),
        )

    result = CliRunner().invoke(cli, ["sample"])

    assert result.exit_code == 1
    assert expected in result.stderr
    assert "secret-path" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_json_sanitizes_discovery_failure_and_keeps_stdout_empty(monkeypatch):
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")
    monkeypatch.setattr(
        "uv_packsize.cli._create_venv",
        lambda _venv_dir, _python=None, **_kwargs: "/venv/bin/python",
    )
    monkeypatch.setattr(
        "uv_packsize.cli._install_package", lambda *_args, **_kwargs: None
    )
    _mock_successful_uv_version(monkeypatch)
    monkeypatch.setattr(
        "uv_packsize.cli.discover_installed_environment",
        lambda **_kwargs: (_ for _ in ()).throw(
            EnvironmentDiscoveryError(
                EnvironmentDiscoveryErrorCode.INVALID_VENV,
                "/private/tmp/secret-venv",
            )
        ),
    )

    result = CliRunner().invoke(
        cli,
        [
            "--json",
            "private @ https://token@example.invalid/simple",
            "/private/tmp/secret-package.whl",
        ],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert (
        "Could not inspect the temporary environment (invalid-venv)." in result.stderr
    )
    for unsafe_value in (
        "token@example.invalid",
        "/private/tmp/secret-venv",
        "/private/tmp/secret-package.whl",
        "Traceback",
    ):
        assert unsafe_value not in result.stderr


def test_package_name_is_required():
    result = CliRunner().invoke(cli, [])

    assert result.exit_code != 0
    assert "Missing argument 'PACKAGE_NAMES...'" in result.output


def test_cli_color_option_is_public_and_defaults_to_auto():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "--color [auto|always|never]" in result.output
    assert "[default: auto]" in result.output


def test_cli_quiet_keeps_click_usage_errors():
    result = CliRunner().invoke(cli, ["--quiet"])

    assert result.exit_code == 2
    assert "Usage:" in result.stderr
    assert "Missing argument 'PACKAGE_NAMES...'" in result.stderr
    assert result.stdout == ""


def _prefix_arguments(venv_path, site_packages, *additional):
    return [
        "--prefix",
        str(venv_path),
        "--site-packages",
        site_packages.relative_to(venv_path).as_posix(),
        "--case-rule",
        CaseRule.INSENSITIVE.value if os.name == "nt" else CaseRule.SENSITIVE.value,
        *additional,
    ]


def test_cli_prefix_analyzes_without_uv_or_install_helpers(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    def unavailable(*_args, **_kwargs):
        raise AssertionError("install-mode helper must not be called")

    monkeypatch.setattr("uv_packsize.cli.shutil.which", unavailable)
    monkeypatch.setattr("uv_packsize.cli._create_venv", unavailable)
    monkeypatch.setattr("uv_packsize.cli._install_package", unavailable)
    monkeypatch.setattr("uv_packsize.cli._uv_version", unavailable)
    monkeypatch.setattr("uv_packsize.cli.subprocess.run", unavailable)

    result = CliRunner().invoke(cli, _prefix_arguments(venv_path, site_packages))

    assert result.exit_code == 0
    assert "Analyzing existing prefix..." in result.stdout
    assert "sample" in result.stdout
    assert "Existing prefix analysis complete." in result.stdout
    assert "Calculating size" not in result.output


def test_cli_prefix_rich_report_marks_build_policy_unknown(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, "--report", "rich")
    )

    assert result.exit_code == 0
    assert "--- Rich Analysis Summary ---" in result.stdout
    assert "Input kind: existing-prefix" in result.stdout
    assert "Build policy: unknown" in result.stdout
    assert "--- Package Sizes ---" not in result.stdout


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_prefix_quiet_keeps_final_text_and_suppresses_progress(
    installed_venv, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = CliRunner().invoke(
        cli,
        _prefix_arguments(
            venv_path, site_packages, "--report", report_format, "--quiet"
        ),
    )

    assert result.exit_code == 0
    expected = (
        "Package Sizes" if report_format == "standard" else "Rich Analysis Summary"
    )
    assert expected in result.stdout
    assert "Analyzing existing prefix" not in result.output
    assert "Existing prefix analysis complete" not in result.output
    assert result.stderr == ""


def test_cli_prefix_json_uses_v2_and_hides_prefix(monkeypatch, installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli.shutil.which",
        lambda *_args: (_ for _ in ()).throw(AssertionError("uv must not be checked")),
    )

    result = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, "--json")
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["context"]["input_kind"] == "existing-prefix"
    assert str(venv_path) not in result.stdout + result.stderr
    assert (
        result.stderr
        == "Analyzing existing prefix...\n\nExisting prefix analysis complete.\n"
    )


def test_cli_prefix_quiet_json_preserves_stdout_bytes(installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    default = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, "--json")
    )
    quiet = CliRunner().invoke(
        cli,
        _prefix_arguments(
            venv_path, site_packages, "--json", "--report", "rich", "--quiet"
        ),
    )

    assert quiet.exit_code == default.exit_code == 0
    assert quiet.stdout == default.stdout
    assert quiet.stderr == ""


@pytest.mark.parametrize("report_format", ["standard", "rich"])
def test_cli_prefix_color_always_decorates_only_final_report(
    installed_venv, report_format
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    plain = CliRunner().invoke(
        cli,
        _prefix_arguments(venv_path, site_packages, "--report", report_format),
    )
    colored = CliRunner().invoke(
        cli,
        _prefix_arguments(
            venv_path,
            site_packages,
            "--report",
            report_format,
            "--color",
            "always",
        ),
    )

    assert colored.exit_code == plain.exit_code == 0
    assert click.unstyle(colored.stdout) == plain.stdout
    assert colored.stderr == plain.stderr
    assert "\x1b[" in colored.stdout
    assert "Analyzing existing prefix...\n\x1b[" in colored.stdout


@pytest.mark.parametrize("color_mode", ["auto", "always", "never"])
def test_cli_prefix_json_ignores_every_color_mode(
    monkeypatch, installed_venv, color_mode
):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")
    monkeypatch.setattr(
        "uv_packsize.cli._stdout_is_tty",
        lambda: (_ for _ in ()).throw(AssertionError("JSON must not inspect TTY")),
    )

    default = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, "--json")
    )
    selected = CliRunner().invoke(
        cli,
        _prefix_arguments(venv_path, site_packages, "--json", "--color", color_mode),
    )

    assert selected.exit_code == default.exit_code == 0
    assert selected.stdout == default.stdout
    assert selected.stderr == default.stderr
    assert "\x1b[" not in selected.output


def test_cli_prefix_json_ignores_text_presentation_options(installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    plain = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, "--json")
    )
    decorated = CliRunner().invoke(
        cli,
        _prefix_arguments(
            venv_path,
            site_packages,
            "--json",
            "--bin",
            "--explain",
            "--breakdown",
            "--contributions",
        ),
    )

    assert plain.exit_code == decorated.exit_code == 0
    assert plain.stdout == decorated.stdout
    assert plain.stderr == decorated.stderr


def test_cli_prefix_bin_uses_generic_binary_title(installed_venv):
    venv_path, _python, site_packages = installed_venv
    _add_distribution(venv_path=venv_path, site_packages=site_packages, name="sample")

    result = CliRunner().invoke(
        cli,
        _prefix_arguments(
            venv_path,
            site_packages,
            "--bin",
            "--report",
            "standard",
            "--color",
            "never",
        ),
    )

    assert result.exit_code == 0
    assert "--- Binaries in prefix ---" in result.stdout
    assert "Binaries in .venv/bin" not in result.stdout
    assert _reported_total(result.stdout) in result.stdout


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["sample", "--prefix", "/private/secret"], "PACKAGE_NAMES cannot"),
        (["--prefix", "/private/secret", "--allow-build"], "--allow-build cannot"),
        (["--prefix", "/private/secret", "--python", "3.12"], "--python cannot"),
        (["--prefix", "/private/secret"], "--site-packages is required"),
        (
            ["--prefix", "/private/secret", "--site-packages", "lib/site-packages"],
            "--case-rule is required",
        ),
    ],
)
def test_cli_prefix_guards_are_usage_errors_and_do_not_echo_path(arguments, message):
    result = CliRunner().invoke(cli, arguments)

    assert result.exit_code == 2
    assert message in result.output
    assert "/private/secret" not in result.output


@pytest.mark.parametrize("option", ["--explain", "--breakdown", "--contributions"])
def test_cli_prefix_rejects_text_graph_options(installed_venv, option):
    venv_path, _python, site_packages = installed_venv
    result = CliRunner().invoke(
        cli, _prefix_arguments(venv_path, site_packages, option)
    )

    assert result.exit_code == 2
    assert f"{option} is unavailable with --prefix." in result.output


def test_cli_prefix_sanitizes_discovery_failure(monkeypatch, tmp_path):
    secret_prefix = tmp_path / "secret-prefix"
    secret_prefix.mkdir()
    site = secret_prefix / "site"
    site.mkdir()
    monkeypatch.setattr(
        "uv_packsize.cli.discover_existing_prefix",
        lambda **_kwargs: (_ for _ in ()).throw(
            ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.INVALID_PREFIX,
                str(secret_prefix),
            )
        ),
    )

    result = CliRunner().invoke(
        cli,
        [
            "--prefix",
            str(secret_prefix),
            "--site-packages",
            "site",
            "--case-rule",
            "sensitive",
        ],
    )

    assert result.exit_code == 1
    assert "Could not inspect the existing prefix (invalid-prefix)." in result.stderr
    assert str(secret_prefix) not in result.output
    assert "Traceback" not in result.output


def test_cli_prefix_sanitizes_inventory_failure(monkeypatch, tmp_path):
    secret_prefix = tmp_path / "secret-prefix"
    secret_prefix.mkdir()
    site = secret_prefix / "site"
    site.mkdir()
    monkeypatch.setattr(
        "uv_packsize.cli.discover_existing_prefix",
        lambda **_kwargs: SimpleNamespace(context=object(), layouts=()),
    )
    monkeypatch.setattr(
        "uv_packsize.cli.analyze_installed_environment",
        lambda **_kwargs: (_ for _ in ()).throw(
            InventoryScanError(InventoryScanErrorCode.FILESYSTEM_ERROR, str(site))
        ),
    )

    result = CliRunner().invoke(
        cli,
        [
            "--prefix",
            str(secret_prefix),
            "--site-packages",
            "site",
            "--case-rule",
            "sensitive",
        ],
    )

    assert result.exit_code == 1
    assert (
        "Could not analyze existing prefix files (filesystem-error)." in result.stderr
    )
    assert str(secret_prefix) not in result.output
    assert str(site) not in result.output
    assert "Traceback" not in result.output
