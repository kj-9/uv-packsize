import os

from click.testing import CliRunner

from uv_packsize.cli import _analyze_package_sizes, cli


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"], prog_name="uv-packsize")
        assert result.exit_code == 0
        assert result.output.startswith("uv-packsize, version ")


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
