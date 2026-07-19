import argparse
import configparser
import os
import subprocess
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

EXPECTED_NAME = "uv-packsize"
EXPECTED_VERSION = "0.1.2"
EXPECTED_REQUIRES_PYTHON = ">=3.10"
EXPECTED_ENTRY_POINT = "uv_packsize.cli:cli"
WHEEL_DIST_INFO = f"uv_packsize-{EXPECTED_VERSION}.dist-info"
SDIST_ROOT = f"uv_packsize-{EXPECTED_VERSION}"
CRITICAL_MODULES = {
    "uv_packsize/__init__.py",
    "uv_packsize/__main__.py",
    "uv_packsize/cli.py",
}


def _verify_metadata(data, artifact):
    metadata = BytesParser().parsebytes(data)
    expected = {
        "Name": EXPECTED_NAME,
        "Version": EXPECTED_VERSION,
        "Requires-Python": EXPECTED_REQUIRES_PYTHON,
    }
    actual = {field: metadata.get(field) for field in expected}
    if actual != expected:
        raise ValueError(
            f"{artifact}: unexpected metadata: expected {expected}, got {actual}"
        )
    return metadata


def _verify_wheel(path):
    metadata_path = f"{WHEEL_DIST_INFO}/METADATA"
    entry_points_path = f"{WHEEL_DIST_INFO}/entry_points.txt"
    with zipfile.ZipFile(path) as wheel:
        damaged_file = wheel.testzip()
        if damaged_file is not None:
            raise ValueError(f"{path}: CRC check failed for {damaged_file}")
        names = set(wheel.namelist())
        required_paths = CRITICAL_MODULES | {metadata_path, entry_points_path}
        for required_path in sorted(required_paths):
            if required_path not in names:
                raise ValueError(f"{path}: missing {required_path}")
        metadata = _verify_metadata(wheel.read(metadata_path), path)
        if "click" not in metadata.get_all("Requires-Dist", []):
            raise ValueError(f"{path}: missing Requires-Dist: click")
        entry_points = wheel.read(entry_points_path).decode("utf-8")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(entry_points)
    actual_entry_point = parser.get("console_scripts", "uv-packsize", fallback=None)
    if actual_entry_point != EXPECTED_ENTRY_POINT:
        raise ValueError(
            f"{path}: unexpected uv-packsize entry point: "
            f"expected {EXPECTED_ENTRY_POINT!r}, got {actual_entry_point!r}"
        )


def _verify_sdist(path):
    with tarfile.open(path, "r:gz") as sdist:
        members = sdist.getmembers()
        roots = set()
        for member in members:
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"{path}: unsafe archive path {member.name!r}")
            if not member_path.parts:
                raise ValueError(f"{path}: empty archive path")
            roots.add(member_path.parts[0])
            if not (member.isfile() or member.isdir()):
                raise ValueError(
                    f"{path}: unsafe archive member type for {member.name!r}"
                )
        if roots != {SDIST_ROOT}:
            raise ValueError(f"{path}: expected root {SDIST_ROOT!r}, got {roots}")

        required_files = {
            f"{SDIST_ROOT}/LICENSE",
            f"{SDIST_ROOT}/README.md",
            f"{SDIST_ROOT}/pyproject.toml",
            *(f"{SDIST_ROOT}/{module}" for module in CRITICAL_MODULES),
        }
        regular_files = {member.name for member in members if member.isfile()}
        missing_files = required_files - regular_files
        if missing_files:
            raise ValueError(f"{path}: missing files: {sorted(missing_files)}")

        metadata_members = [
            member
            for member in members
            if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        if len(metadata_members) != 1 or not metadata_members[0].isfile():
            raise ValueError(f"{path}: expected one regular root PKG-INFO file")
        metadata_file = sdist.extractfile(metadata_members[0])
        if metadata_file is None:
            raise ValueError(f"{path}: could not read root PKG-INFO")
        _verify_metadata(metadata_file.read(), path)


def _smoke_test_wheel(path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory() as temporary_directory:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--with",
                str(path.resolve()),
                "--",
                "uv-packsize",
                "--version",
            ],
            check=False,
            capture_output=True,
            cwd=temporary_directory,
            encoding="utf-8",
            errors="replace",
            env=environment,
            text=True,
        )
    expected_output = f"uv-packsize, version {EXPECTED_VERSION}\n"
    if result.returncode != 0 or result.stdout != expected_output:
        raise ValueError(
            f"{path}: installed entry point smoke test failed with exit code "
            f"{result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}"
        )
    print(f"Verified installed entry point from {path}")


def verify_build(directory):
    publish_files = {
        path
        for path in directory.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }
    wheels = sorted(directory.glob(f"uv_packsize-{EXPECTED_VERSION}-*.whl"))
    sdist = directory / f"uv_packsize-{EXPECTED_VERSION}.tar.gz"
    expected_files = {*wheels, sdist}
    if len(wheels) != 1 or publish_files != expected_files:
        raise ValueError(
            f"{directory}: expected exactly one wheel and one sdist for "
            f"{EXPECTED_NAME} {EXPECTED_VERSION}; found "
            f"{sorted(path.name for path in publish_files)}"
        )

    _verify_wheel(wheels[0])
    _verify_sdist(sdist)
    _smoke_test_wheel(wheels[0])
    print(f"Verified {wheels[0]}")
    print(f"Verified {sdist}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    try:
        verify_build(args.directory)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
