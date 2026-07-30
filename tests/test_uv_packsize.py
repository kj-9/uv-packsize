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

from uv_packsize.analysis import AnalysisContextError, AnalysisContextErrorCode
from uv_packsize.cli import (
    UvCommandError,
    _command_failure_message,
    _create_venv,
    _install_package,
    _run_uv,
    _uv_version,
    cli,
)
from uv_packsize.environment import (
    EnvironmentDiscoveryError,
    EnvironmentDiscoveryErrorCode,
)
from uv_packsize.inventory import InventoryScanError, InventoryScanErrorCode
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import BuildPolicy

EXPECTED_VERSION = "0.1.2"
PROJECT_ROOT = Path(__file__).parent.parent


def test_project_metadata():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    project = pyproject.partition("[project]")[2].partition("\n[")[0]

    assert re.search(
        rf'^version = "{re.escape(EXPECTED_VERSION)}"$', project, re.MULTILINE
    )
    assert re.search(r'^requires-python = ">=3\.10"$', project, re.MULTILINE)

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

    assert re.search(r"^\s+needs: \[test\]$", deploy_job.group("body"), re.MULTILINE)
    assert re.search(r"^\s+make verify-build$", deploy_job.group("body"), re.MULTILINE)
    assert deploy_job.group("body").index("make verify-build") < deploy_job.group(
        "body"
    ).index("uses: pypa/gh-action-pypi-publish")


def test_build_verifier_rejects_unexpected_publish_file(tmp_path):
    (tmp_path / "uv_packsize-0.1.2-py3-none-any.whl").touch()
    (tmp_path / "uv_packsize-0.1.2.tar.gz").touch()
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


def _run_local_layout(  # noqa: PLR0913
    monkeypatch,
    installed_venv,
    package_names,
    *,
    show_scripts=False,
    json_output=False,
    allow_build=False,
):
    venv_path, python, _site_packages = installed_venv
    monkeypatch.setattr("uv_packsize.cli.shutil.which", lambda _command: "/usr/bin/uv")

    def create_venv(venv_dir, _python=None, *, err=False):
        assert err is json_output
        click.echo("Creating virtual environment...", err=err)
        shutil.copytree(venv_path, venv_dir, symlinks=True)
        return str(Path(venv_dir) / python.relative_to(venv_path))

    def install_package(_python_executable, names, *, build_policy, err=False):
        assert err is json_output
        expected_policy = (
            BuildPolicy.ALLOW_BUILD if allow_build else BuildPolicy.WHEEL_ONLY
        )
        assert build_policy is expected_policy
        package_count = len(names)
        package_label = "package" if package_count == 1 else "packages"
        possessive = "its" if package_count == 1 else "their"
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
    if allow_build:
        arguments.append("--allow-build")
    return CliRunner().invoke(cli, arguments)


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


def test_cli_help_describes_json_and_bin_interaction():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "--json" in result.output
    assert "Write the versioned analysis result as JSON to stdout." in result.output
    assert "--bin" in result.output
    assert "Text output only:" in result.output
    assert "--allow-build" in result.output
    assert "Allow source builds during installation; disabled by" in result.output
    assert "default." in result.output


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
