import os
import re
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from uv_packsize.cli import _analyze_package_sizes, cli

EXPECTED_VERSION = "0.1.2"
PROJECT_ROOT = Path(__file__).parent.parent


def test_project_metadata():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    project = pyproject.partition("[project]")[2].partition("\n[")[0]

    assert re.search(r'^version = "0\.1\.2"$', project, re.MULTILINE)
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


def test_makefile_uses_locked_uv_runs():
    makefile = (PROJECT_ROOT / "makefile").read_text()

    assert re.search(r"^UV_RUN=uv run --locked$", makefile, re.MULTILINE)
    assert re.search(r"^sync:\n\tuv sync$", makefile, re.MULTILINE)


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


def test_non_existent_package():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["non-existent-package-12345"])
        assert result.exit_code != 0
        assert (
            "Error installing package" in result.output
            or "No solution found" in result.output
        )


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
    assert result.exit_code != 0
    assert "'uv' command not found" in result.output


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
