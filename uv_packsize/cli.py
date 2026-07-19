import csv
import os
import shutil
import subprocess
import tempfile
from email.parser import BytesParser
from pathlib import Path

import click


class UvCommandError(Exception):
    """A failed uv command with its diagnostic output preserved."""

    def __init__(self, command, exit_code, stdout, stderr):
        self.command = tuple(command)
        self.exit_code = exit_code
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        super().__init__(f"uv command failed with exit code {exit_code}")


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
    click.echo(f"Installing {', '.join(package_names)} and its dependencies...")
    install_command = [
        "uv",
        "pip",
        "install",
        "--python",
        python_executable,
    ]
    install_command.extend(package_names)

    _run_uv(install_command)


def _command_failure_message(error):
    arguments = error.command[1:]
    if arguments[:1] == ("venv",):
        summary = "Could not create the virtual environment"
    elif arguments[:2] == ("pip", "install"):
        summary = "Could not install the requested packages"
    else:
        summary = "uv command failed"

    output = error.stderr.strip() or error.stdout.strip()
    detail_lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = "\n".join(detail_lines[:3])
    if len(detail_lines) > 3:
        detail += "\n..."

    message = f"{summary} (uv exit code {error.exit_code})."
    if detail:
        message += f"\n{detail}"
    return message


def _find_site_packages(venv_dir):
    for root, dirs, _files in os.walk(venv_dir):
        if "site-packages" in dirs:
            return Path(root, "site-packages")

    raise click.ClickException(
        "Could not find site-packages in the virtual environment."
    )


def _distribution_name(dist_info_dir):
    metadata_path = dist_info_dir / "METADATA"
    if metadata_path.is_file():
        with metadata_path.open("rb") as metadata_file:
            name = BytesParser().parse(metadata_file).get("Name")
        if name:
            return name

    # A fallback for malformed installations without METADATA. The directory name
    # is normally `{normalized_name}-{version}.dist-info`.
    stem = dist_info_dir.name.removesuffix(".dist-info")
    return stem.rsplit("-", 1)[0]


def _record_files(dist_info_dir, site_packages_dir):
    record_path = dist_info_dir / "RECORD"
    if not record_path.is_file():
        return [path for path in dist_info_dir.rglob("*") if path.is_file()]

    files = []
    with record_path.open(newline="", encoding="utf-8") as record_file:
        for relative_path, *_rest in csv.reader(record_file):
            path = (site_packages_dir / relative_path).resolve()
            try:
                path.relative_to(site_packages_dir.resolve())
            except ValueError:
                # Console scripts are recorded as paths outside site-packages and
                # are reported separately by --bin.
                continue
            if path.is_file():
                files.append(path)
                if path.suffix == ".py":
                    files.extend(path.parent.glob(f"__pycache__/{path.stem}.*.pyc"))
    return files


def _analyze_package_sizes(venv_dir):
    site_packages_dir = _find_site_packages(venv_dir)

    aggregated_sizes = {}
    for dist_info_dir in site_packages_dir.glob("*.dist-info"):
        package_name = _distribution_name(dist_info_dir)
        # RECORD is the authoritative mapping between distributions and installed
        # files. A set prevents malformed manifests from double-counting entries.
        size = sum(
            path.stat().st_size
            for path in set(_record_files(dist_info_dir, site_packages_dir))
        )
        if size > 0:
            aggregated_sizes[package_name] = (
                aggregated_sizes.get(package_name, 0) + size
            )
    return aggregated_sizes


def _analyze_binary_sizes(venv_dir):
    binaries = []
    bin_dir = os.path.join(venv_dir, "bin")

    # Scripts to exclude from binary analysis
    exclude_scripts = {
        "activate",
        "activate.csh",
        "activate.fish",
        "activate.nu",
        "activate.ps1",
        "activate.bat",
        "activate_this.py",
        "deactivate.bat",
        "pydoc.bat",  # Often a boilerplate script
    }

    if os.path.exists(bin_dir):
        bin_files = [
            f
            for f in os.listdir(bin_dir)
            if os.path.isfile(os.path.join(bin_dir, f))
            and not os.path.islink(os.path.join(bin_dir, f))
            and f not in exclude_scripts
        ]

        for filename in bin_files:
            filepath = os.path.join(bin_dir, filename)
            file_size = os.path.getsize(filepath)
            if file_size > 0:
                binaries.append((filename, file_size))

    return binaries


def _format_size(size_in_bytes):
    if size_in_bytes == 0:
        return "0 B"
    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes / (1024 * 1024):.2f} MB"


def _print_table(  # noqa: PLR0913
    title, data, footer_title, footer_value, name_width, size_width
):
    if not data:
        click.echo(f"\n--- {title} ---")
        click.echo("No items to display.")
        return

    # Header
    click.echo(f"\n--- {title} ---")
    header_title = "Package" if "Package" in title else "Binary"
    header = f"{header_title.ljust(name_width)}  {'Size'.rjust(size_width)}"
    click.echo(header)
    click.echo(f"{'-' * name_width}  {'-' * size_width}")

    # Body
    for name, size in sorted(data, key=lambda item: item[1], reverse=True):
        click.echo(f"{name.ljust(name_width)}  {_format_size(size).rjust(size_width)}")

    # Footer
    click.echo(f"{'-' * name_width}  {'-' * size_width}")
    click.echo(
        f"{footer_title.ljust(name_width)}  {_format_size(footer_value).rjust(size_width)}"
    )


@click.command()
@click.version_option()
@click.argument("package_names", nargs=-1, required=True)
@click.option(
    "--bin",
    is_flag=True,
    help="Include the size of binaries in the .venv/bin directory.",
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

    click.echo(f"Calculating size for {', '.join(package_names)}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        try:
            python_executable = _create_venv(venv_dir, python_version)
            _install_package(python_executable, package_names)
        except UvCommandError as error:
            raise click.ClickException(_command_failure_message(error)) from None

        click.echo("Analyzing sizes...")
        package_sizes = _analyze_package_sizes(venv_dir)
        package_items = list(package_sizes.items())
        total_package_size = sum(package_sizes.values())

        binaries = _analyze_binary_sizes(venv_dir) if bin else []
        bin_items = binaries
        total_bin_size = sum(size for name, size in bin_items)

        # Determine column widths
        all_items = package_items + bin_items
        name_width = max((len(name) for name, size in all_items), default=0)
        name_width = max(
            name_width, len("Total Package Size"), len("Total Binaries Size")
        )

        all_sizes = [size for name, size in all_items] + [
            total_package_size,
            total_bin_size,
        ]
        size_width = max((len(_format_size(s)) for s in all_sizes), default=0)

        _print_table(
            "Package Sizes",
            package_items,
            "Total Package Size",
            total_package_size,
            name_width,
            size_width,
        )

        total_size = total_package_size

        if bin:
            _print_table(
                "Binaries in .venv/bin",
                bin_items,
                "Total Binaries Size",
                total_bin_size,
                name_width,
                size_width,
            )
            total_size += total_bin_size

        click.echo(
            f"\n{'Total size:'.ljust(name_width)}  {_format_size(total_size).rjust(size_width)}"
        )

    click.echo("\nCalculation complete.")
