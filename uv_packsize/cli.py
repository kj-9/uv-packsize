import os
import shutil
import subprocess
import sys
import tempfile

import click


def get_dir_size(path):
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def _create_venv(venv_dir, python=None):
    click.echo("Creating virtual environment...")

    command = ["uv", "venv"]
    if python:
        command.extend(["--python", python])
    command.append(venv_dir)
    subprocess.run(command, check=True, capture_output=True)

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

    result = subprocess.run(
        install_command,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        click.echo(f"Error installing packages: {', '.join(package_names)}", err=True)
        click.echo(f"uv pip install stdout: {result.stdout.decode().strip()}", err=True)
        click.echo(f"uv pip install stderr: {result.stderr.decode().strip()}", err=True)
        sys.exit(result.returncode)


def _analyze_package_sizes(venv_dir):
    site_packages_dir = None
    for root, dirs, _files in os.walk(venv_dir):
        if "site-packages" in dirs:
            site_packages_dir = os.path.join(root, "site-packages")
            break

    if not site_packages_dir:
        click.echo(
            "Could not find site-packages directory in the virtual environment.",
            err=True,
        )
        sys.exit(1)

    aggregated_sizes = {}
    for item in os.listdir(site_packages_dir):
        item_path = os.path.join(site_packages_dir, item)
        if os.path.isdir(item_path):
            size = get_dir_size(item_path)
            if size > 0:
                if item.endswith(".dist-info"):
                    # Extract package name from dist-info (e.g., 'numpy-1.23.4.dist-info' -> 'numpy')
                    package_name = item.split("-")[0]
                    aggregated_sizes[package_name] = (
                        aggregated_sizes.get(package_name, 0) + size
                    )
                else:
                    aggregated_sizes[item] = aggregated_sizes.get(item, 0) + size
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
@click.argument("package_names", nargs=-1)
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
        click.echo(
            "Error: 'uv' command not found. Please install it first. "
            "See https://github.com/astral-sh/uv for installation instructions.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Calculating size for {', '.join(package_names)}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        python_executable = _create_venv(venv_dir, python_version)
        _install_package(python_executable, package_names)

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
