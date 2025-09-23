import os

from click.testing import CliRunner

from uv_packsize.cli import cli


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
        result = runner.invoke(cli, ["uv-packsize==0.1.0a0", "--bin"])
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
