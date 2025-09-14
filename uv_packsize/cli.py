import os
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


def _create_venv(venv_dir):
    click.echo(f"Creating virtual environment in {venv_dir}...")
    subprocess.run(["uv", "venv", venv_dir], check=True, capture_output=True)

    python_executable = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(python_executable):  # For Windows
        python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
    return python_executable


def _install_package(python_executable, package_name):
    click.echo(f"Installing {package_name} and its dependencies...")
    install_command = [
        "uv",
        "pip",
        "install",
        "--python",
        python_executable,
        package_name,
    ]

    result = subprocess.run(
        install_command,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        click.echo(f"Error installing package: {package_name}", err=True)
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

    click.echo("Analyzing package sizes...")
    package_sizes = {}
    for item in os.listdir(site_packages_dir):
        item_path = os.path.join(site_packages_dir, item)
        if os.path.isdir(item_path):
            package_sizes[item] = get_dir_size(item_path)
    return package_sizes


def _analyze_binary_sizes(venv_dir):
    binaries_total_size = 0
    bin_dir = os.path.join(venv_dir, "bin")
    if os.path.exists(bin_dir):
        click.echo("--- Binaries in .venv/bin ---")
        bin_files = [
            f
            for f in os.listdir(bin_dir)
            if os.path.isfile(os.path.join(bin_dir, f))
            and not os.path.islink(os.path.join(bin_dir, f))
        ]

        sorted_binaries = []
        for filename in bin_files:
            filepath = os.path.join(bin_dir, filename)
            file_size = os.path.getsize(filepath)
            sorted_binaries.append((filename, file_size))

        sorted_binaries.sort(key=lambda item: item[1], reverse=True)

        for filename, file_size in sorted_binaries:
            if file_size > 0:
                if file_size < 1024 * 1024:  # Less than 1 MB, show in KB
                    click.echo(f"  {filename}: {file_size / 1024:.2f} KB")
                else:
                    click.echo(f"  {filename}: {file_size / (1024 * 1024):.2f} MB")
                binaries_total_size += file_size

        click.echo(f"Total Binaries Size: {binaries_total_size / (1024 * 1024):.2f} MB")
    return binaries_total_size


@click.command()
@click.version_option()
@click.argument("package_name")
@click.option(
    "--bin",
    is_flag=True,
    help="Include the size of binaries in the .venv/bin directory.",
)
def cli(package_name, bin):
    """Report the size of a Python package and its dependencies using uv."""
    click.echo(f"Calculating size for {package_name}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        python_executable = _create_venv(venv_dir)
        _install_package(python_executable, package_name)
        package_sizes = _analyze_package_sizes(venv_dir)

        click.echo("--- Package Sizes ---")
        total_package_size = 0
        for pkg, size in sorted(
            package_sizes.items(), key=lambda item: item[1], reverse=True
        ):
            if size > 0:
                if size < 1024 * 1024:  # Less than 1 MB, show in KB
                    click.echo(f"{pkg}: {size / 1024:.2f} KB")
                else:
                    click.echo(f"{pkg}: {size / (1024 * 1024):.2f} MB")
                total_package_size += size
        click.echo(f"Total Package Size: {total_package_size / (1024 * 1024):.2f} MB")
        total_size = total_package_size

        if bin:
            binaries_total_size = _analyze_binary_sizes(venv_dir)
            total_size += binaries_total_size

        click.echo(f"\nTotal size: {total_size / (1024 * 1024):.2f} MB")

    click.echo("\nCalculation complete.")
