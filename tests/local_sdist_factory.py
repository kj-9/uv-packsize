"""Create a deterministic sdist whose build backend leaves an execution sentinel."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

_ARCHIVE_TIMESTAMP = 0
_PROJECT_NAME = "uv-packsize-fixture-sdist"
_VERSION = "1.0.0"


def build_sdist(wheelhouse: Path) -> Path:
    """Write one deterministic PEP 517 sdist that signals backend execution.

    The backend has no build requirements.  Importing it writes the file named
    by ``UV_PACKSIZE_TEST_SENTINEL`` so the integration test can distinguish a
    resolver rejection from an accidental build attempt.
    """

    wheelhouse.mkdir(parents=True, exist_ok=True)
    root = f"{_PROJECT_NAME}-{_VERSION}"
    contents = {
        f"{root}/pyproject.toml": (
            b"[build-system]\n"
            b"requires = []\n"
            b'build-backend = "uv_packsize_fixture_sdist_backend"\n'
            b'backend-path = ["."]\n'
        ),
        f"{root}/uv_packsize_fixture_sdist_backend.py": (
            b"import os\n"
            b"from pathlib import Path\n"
            b"\n"
            b'sentinel = os.environ.get("UV_PACKSIZE_TEST_SENTINEL")\n'
            b"if sentinel:\n"
            b'    Path(sentinel).write_text("backend imported\\n", encoding="utf-8")\n'
            b"\n"
            b"def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n"
            b'    raise RuntimeError("test backend must not build a wheel")\n'
        ),
    }
    sdist_path = wheelhouse / f"{_PROJECT_NAME}-{_VERSION}.tar.gz"
    with sdist_path.open("wb") as raw_archive:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_archive, mtime=_ARCHIVE_TIMESTAMP
        ) as compressed_archive:
            with tarfile.open(fileobj=compressed_archive, mode="w") as archive:
                for member, data in sorted(contents.items()):
                    info = tarfile.TarInfo(member)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = _ARCHIVE_TIMESTAMP
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
    return sdist_path
