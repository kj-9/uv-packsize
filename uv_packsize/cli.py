"""Click entry point for temporary-environment package-size analysis."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from uv_packsize.analysis import AnalysisContextError, analyze_installed_environment
from uv_packsize.environment import (
    EnvironmentDiscoveryError,
    discover_installed_environment,
)
from uv_packsize.inventory import InventoryError
from uv_packsize.models import BuildPolicy
from uv_packsize.render import render_analysis_report

_UV_VERSION = re.compile(
    r"uv\s+([0-9]+(?:\.[0-9]+)+(?:[-+][A-Za-z0-9.-]+)?)"
    r"(?:\s+\([A-Za-z0-9 ._+-]+\))?"
)


class UvCommandError(Exception):
    """A failed uv command with its diagnostic output preserved."""

    def __init__(self, command, exit_code, stdout, stderr):
        self.command = tuple(command)
        self.exit_code = exit_code
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        super().__init__(f"uv command failed with exit code {exit_code}")


class UvVersionError(ValueError):
    """The ``uv --version`` response was not a safe version value."""


def _run_uv(command):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise UvCommandError(command, 127, "", str(error)) from error

    if result.returncode != 0:
        raise UvCommandError(
            command,
            result.returncode,
            result.stdout,
            result.stderr,
        )
    return result


def _create_venv(venv_dir, python=None):
    click.echo("Creating virtual environment...")

    command = ["uv", "venv"]
    if python:
        command.extend(["--python", python])
    command.append(venv_dir)
    _run_uv(command)

    python_executable = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(python_executable):  # For Windows
        python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
    return python_executable


def _install_package(python_executable, package_names):
    package_count = len(package_names)
    package_label = "package" if package_count == 1 else "packages"
    possessive = "its" if package_count == 1 else "their"
    click.echo(
        f"Installing {package_count} requested {package_label} and {possessive} dependencies..."
    )
    install_command = [
        "uv",
        "pip",
        "install",
        "--python",
        python_executable,
    ]
    install_command.extend(package_names)

    _run_uv(install_command)


def _uv_version() -> str:
    """Return a validated version from the installed ``uv`` executable."""

    result = _run_uv(["uv", "--version"])
    match = _UV_VERSION.fullmatch(result.stdout.strip())
    if match is None:
        raise UvVersionError("invalid uv version output")
    return match.group(1)


def _command_failure_message(error):
    """Return a public summary without forwarding uv's untrusted diagnostics."""

    arguments = error.command[1:]
    if arguments[:1] == ("venv",):
        summary = "Could not create the virtual environment"
    elif arguments[:2] == ("pip", "install"):
        summary = "Could not install the requested packages"
    elif arguments == ("--version",):
        summary = "Could not determine the uv version"
    else:
        summary = "uv command failed"

    return f"{summary} (uv exit code {error.exit_code})."


def _analysis_failure_message(error: Exception) -> str:
    """Produce a stable CLI diagnostic without filesystem or probe details."""

    if isinstance(error, EnvironmentDiscoveryError):
        return f"Could not inspect the temporary environment ({error.code.value})."
    if isinstance(error, AnalysisContextError):
        return f"Could not analyze the installed environment ({error.code.value})."
    if isinstance(error, InventoryError):
        code = getattr(error, "code", None)
        if code is not None:
            return f"Could not analyze installed files ({code.value})."
        return "Could not analyze installed files."
    raise TypeError("error must be an expected analysis failure")


@click.command()
@click.version_option()
@click.argument("package_names", nargs=-1, required=True)
@click.option(
    "--bin",
    is_flag=True,
    help="Display RECORD-owned scripts separately without changing the total.",
)
@click.option(
    "-p",
    "--python",
    "python_version",
    help="Specify the Python version for the virtual environment.",
)
def cli(package_names, bin, python_version):
    """Report the size of a Python package and its dependencies using uv."""
    if not shutil.which("uv"):
        raise click.ClickException(
            "'uv' command not found. Please install it first. "
            "See https://github.com/astral-sh/uv for installation instructions."
        )

    package_count = len(package_names)
    package_label = "package" if package_count == 1 else "packages"
    click.echo(f"Calculating size for {package_count} requested {package_label}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        try:
            python_executable = _create_venv(venv_dir, python_version)
            _install_package(python_executable, package_names)
            uv_version = _uv_version()
        except UvCommandError as error:
            raise click.ClickException(_command_failure_message(error)) from None
        except UvVersionError:
            raise click.ClickException("Could not determine the uv version.") from None

        click.echo("Analyzing sizes...")
        try:
            environment = discover_installed_environment(
                venv_path=Path(venv_dir),
                venv_python=Path(python_executable),
                requirements=tuple(package_names),
                uv_version=uv_version,
                build_policy=BuildPolicy.ALLOW_BUILD,
                compile_bytecode=False,
                extras=(),
                index_identifiers=(),
                resolution_strategy="highest",
            )
            result = analyze_installed_environment(
                context=environment.context,
                layouts=environment.layouts,
            )
        except (
            EnvironmentDiscoveryError,
            AnalysisContextError,
            InventoryError,
        ) as error:
            raise click.ClickException(_analysis_failure_message(error)) from None

        click.echo(render_analysis_report(result, show_scripts=bin))

    click.echo("\nCalculation complete.")
