"""Create deterministic, dependency-free wheels for local integration tests."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_wheelhouse(wheelhouse: Path) -> dict[str, Path]:
    """Write the three universal test wheels and return them by project name."""

    wheelhouse.mkdir(parents=True, exist_ok=True)
    wheel_paths = {
        "uv-packsize-fixture-shared": _write_wheel(
            wheelhouse=wheelhouse,
            name="uv-packsize-fixture-shared",
            requirements=(),
            members={"uv_packsize_fixture_shared.py": b"VALUE = 'shared'\n"},
        ),
        "uv-packsize-fixture-root-a": _write_wheel(
            wheelhouse=wheelhouse,
            name="uv-packsize-fixture-root-a",
            requirements=("uv-packsize-fixture-shared (==1.0.0)",),
            members={
                "uv_packsize_fixture_root_a.py": (
                    b"from uv_packsize_fixture_shared import VALUE\n\n"
                    b"def main():\n    return VALUE\n"
                ),
                "uv_packsize_fixture_root_a-1.0.0.data/data/share/"
                "uv-packsize-fixture-root-a/payload.txt": b"root-a payload\n",
                "uv_packsize_fixture_root_a-1.0.0.data/headers/"
                "uv_packsize_fixture_root_a.h": b"#define ROOT_A 1\n",
                "uv_packsize_fixture_root_a-1.0.0.data/scripts/"
                "uv-packsize-fixture-root-a-data-script": b"#!/bin/sh\necho root-a\n",
            },
            entry_points=(
                "[console_scripts]\n"
                "uv-packsize-fixture-root-a = uv_packsize_fixture_root_a:main\n"
            ),
        ),
        "uv-packsize-fixture-root-b": _write_wheel(
            wheelhouse=wheelhouse,
            name="uv-packsize-fixture-root-b",
            requirements=("uv-packsize-fixture-shared (==1.0.0)",),
            members={
                "uv_packsize_fixture_root_b.py": (
                    b"from uv_packsize_fixture_shared import VALUE\n"
                    b"VALUE_FROM_B = VALUE\n"
                )
            },
        ),
    }
    return wheel_paths


def _write_wheel(
    *,
    wheelhouse: Path,
    name: str,
    requirements: tuple[str, ...],
    members: dict[str, bytes],
    entry_points: str | None = None,
) -> Path:
    normalized_name = name.replace("-", "_")
    version = "1.0.0"
    dist_info = f"{normalized_name}-{version}.dist-info"
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
        *(f"Requires-Dist: {requirement}" for requirement in requirements),
        "",
    ]
    contents = {
        **members,
        f"{dist_info}/METADATA": "\n".join(metadata_lines).encode(),
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\n"
        b"Generator: uv-packsize-local-wheel-factory\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n",
    }
    if entry_points is not None:
        contents[f"{dist_info}/entry_points.txt"] = entry_points.encode()

    record_path = f"{dist_info}/RECORD"
    record_rows = [
        (member, _record_hash(contents[member]), str(len(contents[member])))
        for member in sorted(contents)
    ]
    record_rows.append((record_path, "", ""))
    record_buffer = io.StringIO(newline="")
    csv.writer(record_buffer, lineterminator="\n").writerows(record_rows)
    contents[record_path] = record_buffer.getvalue().encode()

    wheel_path = wheelhouse / f"{normalized_name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for member in sorted(contents):
            mode = 0o755 if ".data/scripts/" in member else 0o644
            info = zipfile.ZipInfo(member, date_time=_FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = mode << 16
            archive.writestr(info, contents[member])
    return wheel_path


def _record_hash(contents: bytes) -> str:
    digest = hashlib.sha256(contents).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"
