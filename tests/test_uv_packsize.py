from click.testing import CliRunner

from uv_packsize.cli import cli


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")


def test_size_command_basic():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["size", "iniconfig"])
        assert result.exit_code == 0
        assert "iniconfig" in result.output
        assert "MB" in result.output


def test_size_command_non_existent_package():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["size", "non-existent-package-12345"])
        assert result.exit_code != 0
        assert (
            "Could not find package" in result.output
            or "No solution found" in result.output
        )
