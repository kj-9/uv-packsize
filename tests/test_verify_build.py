"""Release artifact metadata verifier tests."""

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).parents[1]
_verify_metadata = cast(
    Callable[[bytes, str], object],
    runpy.run_path(str(ROOT / "scripts/verify_build.py"))["_verify_metadata"],
)
CRITICAL_MODULES = cast(
    set[str], runpy.run_path(str(ROOT / "scripts/verify_build.py"))["CRITICAL_MODULES"]
)


def metadata(*requirements: str) -> bytes:
    headers = [
        "Metadata-Version: 2.4",
        "Name: uv-packsize",
        "Version: 0.2.0",
        "Requires-Python: >=3.10",
        *(f"Requires-Dist: {requirement}" for requirement in requirements),
        "",
        "",
    ]
    return "\n".join(headers).encode("utf-8")


def test_runtime_dependencies_are_normalized_and_marker_is_required():
    _verify_metadata(
        metadata("CLICK", "packaging", "tomli; python_version < '3.11'"),
        "artifact",
    )

    with pytest.raises(ValueError, match="unexpected Requires-Dist metadata"):
        _verify_metadata(metadata("click", "packaging"), "artifact")

    with pytest.raises(ValueError, match="unexpected Requires-Dist metadata"):
        _verify_metadata(
            metadata("click", "packaging", 'tomli; python_version >= "3.11"'),
            "artifact",
        )


def test_runtime_dependency_set_rejects_extras_and_duplicates():
    with pytest.raises(ValueError, match="unexpected Requires-Dist metadata"):
        _verify_metadata(
            metadata(
                "click",
                "packaging",
                'tomli; python_version < "3.11"',
                "unexpected",
            ),
            "artifact",
        )
    with pytest.raises(ValueError, match="unexpected Requires-Dist metadata"):
        _verify_metadata(
            metadata(
                "click",
                "packaging",
                'tomli; python_version < "3.11"',
                "tomli; python_version < '3.11'",
            ),
            "artifact",
        )


def test_critical_modules_include_project_lock_installer():
    assert "uv_packsize/project_lock_installer.py" in CRITICAL_MODULES
