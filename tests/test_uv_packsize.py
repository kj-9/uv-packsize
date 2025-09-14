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


def test_dev_option_with_dagster():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Run without --dev
        result_no_dev = runner.invoke(cli, ["dagster"])
        assert result_no_dev.exit_code == 0
        assert "Error installing package" not in result_no_dev.output

        # Run with --dev
        result_with_dev = runner.invoke(cli, ["dagster", "--dev"])
        assert result_with_dev.exit_code != 0
        assert (
            "Error installing package" in result_with_dev.output
            or "No such group" in result_with_dev.output
        )


def test_bin_option_with_dagster():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Install dagster with --bin
        result = runner.invoke(cli, ["dagster", "--bin"])
        assert result.exit_code == 0
        assert "dagster" in result.output  # Check if dagster package is listed
        # Dagster installs several binaries, e.g., 'dagster', 'dagster-graphql'
        # We can check for the presence of 'dagster' binary
        assert "dagster:" in result.output
        assert "Total Binaries in .venv/bin:" in result.output
