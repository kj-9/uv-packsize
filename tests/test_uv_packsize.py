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
        assert "MB" in result.output


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
        assert "Total Binaries Size:" in result.output
