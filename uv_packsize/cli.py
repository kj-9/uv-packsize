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


@click.group()
@click.version_option()
def cli():
    "report size of python package with its deps using uv"


@cli.command(name="size")
@click.argument("package_name")
def size_command(package_name):
    """Report the size of a Python package and its dependencies using uv."""
    click.echo(f"Calculating size for {package_name}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")

        # Create a virtual environment
        click.echo(f"Creating virtual environment in {venv_dir}...")
        result = subprocess.run(
            ["uv", "venv", venv_dir], check=True, capture_output=True
        )

        # Determine the Python executable path within the venv
        python_executable = os.path.join(venv_dir, "bin", "python")
        if not os.path.exists(python_executable):  # For Windows
            python_executable = os.path.join(venv_dir, "Scripts", "python.exe")

        click.echo(f"Installing {package_name} and its dependencies...")
        result = subprocess.run(
            ["uv", "pip", "install", "--python", python_executable, package_name],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            click.echo(f"Error installing package: {package_name}", err=True)
            click.echo(
                f"uv pip install stdout: {result.stdout.decode().strip()}", err=True
            )
            click.echo(
                f"uv pip install stderr: {result.stderr.decode().strip()}", err=True
            )
            sys.exit(result.returncode)

        # Find site-packages directory
        # uv installs packages into a .venv/lib/pythonX.Y/site-packages directory
        # We need to find the pythonX.Y part dynamically
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

        click.echo("\n--- Package Sizes ---")
        for pkg, size in sorted(
            package_sizes.items(), key=lambda item: item[1], reverse=True
        ):
            click.echo(f"{pkg}: {size / (1024 * 1024):.2f} MB")

    click.echo("\nCalculation complete.")
