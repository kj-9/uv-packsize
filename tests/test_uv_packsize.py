import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from uv_packsize.cli import (
    UvCommandError,
    _analyze_package_sizes,
    _command_failure_message,
    _create_venv,
    _install_package,
    _run_uv,
    cli,
)

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


def test_basic_package_size():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["iniconfig==2.0.0"])
        assert result.exit_code == 0
        assert "iniconfig" in result.output
        assert "Total size:" in result.output


def test_bin_option():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["uv-packsize==0.1.1", "--bin"])
        assert result.exit_code == 0
        assert "uv-packsize" in result.output
        assert "Total Binaries Size" in result.output


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


def test_command_failure_uses_stdout_fallback_and_truncates_details():
    error = UvCommandError(
        ["uv", "pip", "install", "secret-command-value"],
        9,
        "first line\nsecond line\nthird line\nfourth line",
        "",
    )

    message = _command_failure_message(error)

    assert "Could not install the requested packages (uv exit code 9)." in message
    assert "first line\nsecond line\nthird line\n..." in message
    assert "fourth line" not in message
    assert "secret-command-value" not in message


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


def test_install_package_propagates_uv_failure(monkeypatch):
    failure = UvCommandError(["uv", "pip", "install"], 1, "stdout", "stderr")

    def fail(command):
        assert command == [
            "uv",
            "pip",
            "install",
            "--python",
            "/venv/bin/python",
            "example==1.0",
        ]
        raise failure

    monkeypatch.setattr("uv_packsize.cli._run_uv", fail)

    with pytest.raises(UvCommandError) as raised:
        _install_package("/venv/bin/python", ["example==1.0"])

    assert raised.value is failure


@pytest.mark.parametrize(
    ("failed_stage", "expected_summary"),
    [
        ("venv", "Could not create the virtual environment"),
        ("install", "Could not install the requested packages"),
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
                "less useful stdout",
                "specific uv diagnostic\nadditional context",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("uv_packsize.cli._run_uv", run)

    result = CliRunner().invoke(cli, ["example-package", "--python", "0.0"])

    assert result.exit_code != 0
    assert result.exit_code == 1
    assert expected_summary in result.stderr
    assert "uv exit code 2" in result.stderr
    assert "specific uv diagnostic" in result.stderr
    assert "secret-command-value" not in result.stderr
    assert "Traceback" not in result.stderr


def test_python_version_option(monkeypatch):
    """Test that the --python option is correctly passed."""
    called_with_args = {}

    def mock_create_venv(venv_dir, python=None):
        called_with_args["venv_dir"] = venv_dir
        called_with_args["python"] = python
        return os.path.join(venv_dir, "bin", "python")

    def mock_install_package(python_executable, package_name):
        # Prevent the test from actually trying to install anything
        pass

    monkeypatch.setattr("uv_packsize.cli._create_venv", mock_create_venv)
    monkeypatch.setattr("uv_packsize.cli._install_package", mock_install_package)

    runner = CliRunner()
    runner.invoke(cli, ["some-package", "--python", "3.11"])

    assert called_with_args.get("python") == "3.11"


def test_multiple_packages():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["iniconfig==2.0.0", "six"])
        assert result.exit_code == 0
        assert "iniconfig" in result.output
        assert "six" in result.output
        assert "Total size:" in result.output


def test_package_sizes_use_distribution_record(tmp_path):
    site_packages = tmp_path / "venv" / "lib" / "python3.13" / "site-packages"
    dist_info = site_packages / "example_package-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (site_packages / "example.py").write_bytes(b"module contents")
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: example-package\nVersion: 1.0\n"
    )
    (dist_info / "RECORD").write_text(
        "example.py,,\nexample_package-1.0.dist-info/METADATA,,\n"
        "example_package-1.0.dist-info/RECORD,,\n"
        "../../../bin/example,,\n"
    )

    sizes = _analyze_package_sizes(tmp_path / "venv")

    assert sizes == {
        "example-package": sum(
            path.stat().st_size
            for path in [
                site_packages / "example.py",
                dist_info / "METADATA",
                dist_info / "RECORD",
            ]
        )
    }


def test_package_sizes_include_bytecode_for_standalone_modules(tmp_path):
    site_packages = tmp_path / "venv" / "Lib" / "site-packages"
    dist_info = site_packages / "six-1.0.dist-info"
    pycache = site_packages / "__pycache__"
    dist_info.mkdir(parents=True)
    pycache.mkdir()
    (site_packages / "six.py").write_bytes(b"source")
    (pycache / "six.cpython-313.pyc").write_bytes(b"compiled")
    (dist_info / "METADATA").write_text("Name: six\nVersion: 1.0\n")
    (dist_info / "RECORD").write_text("six.py,,\n")

    sizes = _analyze_package_sizes(tmp_path / "venv")

    assert sizes["six"] == len(b"source") + len(b"compiled")


def test_missing_record_counts_only_dist_info_files(tmp_path):
    site_packages = tmp_path / "venv" / "lib" / "python3.13" / "site-packages"
    package_dir = site_packages / "example_package"
    dist_info = site_packages / "example_package-1.0.dist-info"
    package_dir.mkdir(parents=True)
    dist_info.mkdir()
    (package_dir / "__init__.py").write_bytes(b"package contents")
    metadata = dist_info / "METADATA"
    metadata.write_text("Name: example-package\nVersion: 1.0\n")

    sizes = _analyze_package_sizes(tmp_path / "venv")

    assert sizes == {"example-package": metadata.stat().st_size}


def test_package_name_falls_back_when_metadata_is_missing(tmp_path):
    site_packages = tmp_path / "venv" / "Lib" / "site-packages"
    dist_info = site_packages / "my_package-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "RECORD").write_text("my_package-1.0.dist-info/RECORD,,\n")

    assert _analyze_package_sizes(tmp_path / "venv").keys() == {"my_package"}


def test_package_name_is_required():
    result = CliRunner().invoke(cli, [])

    assert result.exit_code != 0
    assert "Missing argument 'PACKAGE_NAMES...'" in result.output
