import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import uv_packsize.baseline_write as writer
from uv_packsize.baseline import (
    MAX_BASELINE_BYTES,
    analysis_result_to_baseline,
    load_baseline,
    parse_baseline_json,
)
from uv_packsize.baseline_write import (
    BaselineWriteError,
    render_fresh_baseline,
    write_baseline,
)
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    ExistingPrefixContext,
    PathFlavor,
    ResolutionContext,
)

_PROJECT_ROOT = Path(__file__).parents[1]


def _result() -> AnalysisResult:
    return AnalysisResult(
        context=ResolutionContext(
            requirements=("example==1",),
            python_version="3.14",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="0.11",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        distributions=(),
    )


@pytest.fixture(autouse=True)
def _private_working_directory(tmp_path: Path, monkeypatch):
    """Use a same-user relative parent for the strict POSIX trust boundary."""

    monkeypatch.chdir(tmp_path)


def _target() -> Path:
    return Path("baseline.json")


def test_render_is_exact_public_v1_utf8_and_projectable():
    result = _result()
    payload = render_fresh_baseline(result)

    assert payload.endswith(b"\n")
    assert payload.decode("utf-8") == writer.render_analysis_json(result)
    assert parse_baseline_json(payload) == analysis_result_to_baseline(result)
    assert payload == render_fresh_baseline(result)


def test_render_rejects_nonfresh_and_sanitizes_serializer_failure(monkeypatch):
    existing = AnalysisResult(
        context=ExistingPrefixContext(
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
        ),
        distributions=(),
    )
    with pytest.raises(BaselineWriteError) as captured:
        render_fresh_baseline(existing)
    assert captured.value.code == "not-fresh-analysis"

    def fail_render(result: AnalysisResult) -> str:
        raise ValueError("private serializer token")

    monkeypatch.setattr(writer, "render_analysis_json", fail_render)
    with pytest.raises(BaselineWriteError) as captured:
        render_fresh_baseline(_result())
    assert captured.value.code == "render-failed"
    assert "private serializer token" not in str(captured.value)


@pytest.mark.parametrize(
    "payload", [b"{}", b"\xef\xbb\xbf{}", b"x" * (MAX_BASELINE_BYTES + 1)]
)
def test_write_rejects_invalid_payload_without_reflecting_it(
    tmp_path: Path, payload: bytes
):
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(_target(), payload)
    assert "baseline.json" not in str(captured.value)
    assert "x" * 20 not in str(captured.value)


def test_write_round_trip_no_clobber_and_overwrite(tmp_path: Path):
    target = _target()
    payload = render_fresh_baseline(_result())
    write_baseline(target, payload)
    assert load_baseline(target) == analysis_result_to_baseline(_result())
    assert stat.S_IMODE(target.stat().st_mode) == 0o600

    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(target, payload)
    assert captured.value.code == "exists"
    write_baseline(target, payload, overwrite=True)


@pytest.mark.skipif(os.name != "posix", reason="dir_fd contract is POSIX-specific")
def test_write_rejects_unsafe_existing_entries_and_parents(tmp_path: Path):
    payload = render_fresh_baseline(_result())
    directory = Path("directory")
    directory.mkdir()
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(directory, payload)
    assert captured.value.code == "not-regular-file"

    link = Path("link.json")
    link.symlink_to(Path("elsewhere"))
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(link, payload, overwrite=True)
    assert captured.value.code == "symlink"

    parent_link = Path("parent-link")
    parent_link.symlink_to(Path("."), target_is_directory=True)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(parent_link / "baseline.json", payload)
    assert captured.value.code in {"unsafe-parent", "parent-unavailable"}


def test_write_preserves_original_on_prepublish_write_failure(
    tmp_path: Path, monkeypatch
):
    target = _target()
    original = b"original"
    target.write_bytes(original)
    payload = render_fresh_baseline(_result())

    def fail_write(descriptor: int, data: object) -> int:
        raise OSError("private failure")

    monkeypatch.setattr(writer.os, "write", fail_write)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(target, payload, overwrite=True)
    assert captured.value.code == "write-failed"
    assert target.read_bytes() == original
    assert "private failure" not in str(captured.value)
    assert not list(tmp_path.glob(".uv-packsize-*.tmp"))


def test_directory_fsync_failure_keeps_published_file(tmp_path: Path, monkeypatch):
    target = _target()
    payload = render_fresh_baseline(_result())
    original_fsync = writer.os.fsync
    calls = 0

    def fail_directory_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("private directory failure")
        original_fsync(descriptor)

    monkeypatch.setattr(writer.os, "fsync", fail_directory_fsync)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(target, payload)
    assert captured.value.code == "directory-fsync-failed"
    assert target.read_bytes() == payload


def test_type_contract(tmp_path: Path):
    payload = render_fresh_baseline(_result())
    with pytest.raises(TypeError):
        write_baseline(Path("x"), cast(bytes, bytearray(payload)))
    with pytest.raises(TypeError):
        write_baseline(Path("x"), payload, overwrite=cast(bool, 1))


def test_feature_gate_happens_before_open(tmp_path: Path, monkeypatch):
    payload = render_fresh_baseline(_result())
    monkeypatch.delattr(writer.os, "O_NOFOLLOW", raising=False)

    def fail_open(*args: object, **kwargs: object) -> int:
        raise AssertionError("must not open before feature gate")

    monkeypatch.setattr(writer.os, "open", fail_open)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(_target(), payload)
    assert captured.value.code == "unsupported-platform"


def test_write_uses_lstat_when_lstat_dir_fd_is_not_advertised(
    tmp_path: Path, monkeypatch
):
    """Linux CPython 3.12 accepts this call despite omitting its capability."""

    payload = render_fresh_baseline(_result())
    supported = set(writer.os.supports_dir_fd)
    supported.discard(writer.os.lstat)
    monkeypatch.setattr(writer.os, "supports_dir_fd", supported)

    def fail_stat(*args: object, **kwargs: object) -> os.stat_result:
        raise AssertionError("the writer must use lstat(..., dir_fd=...)")

    monkeypatch.setattr(writer.os, "stat", fail_stat)
    target = _target()
    write_baseline(target, payload)
    assert target.read_bytes() == payload


def test_feature_gate_requires_core_dir_fd_operations_before_open(
    tmp_path: Path, monkeypatch
):
    payload = render_fresh_baseline(_result())
    supported = set(writer.os.supports_dir_fd)
    supported.discard(writer.os.open)
    monkeypatch.setattr(writer.os, "supports_dir_fd", supported)

    def fail_open(*args: object, **kwargs: object) -> int:
        raise AssertionError("must not open before feature gate")

    monkeypatch.setattr(writer.os, "open", fail_open)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(_target(), payload)
    assert captured.value.code == "unsupported-platform"


def test_parent_trust_allows_nonwritable_foreign_anchor_but_rejects_foreign_writable():
    foreign_sticky = SimpleNamespace(st_uid=os.getuid() + 1, st_mode=0o1777)
    foreign_readonly = SimpleNamespace(st_uid=os.getuid() + 1, st_mode=0o755)
    own_private = SimpleNamespace(st_uid=os.getuid(), st_mode=0o700)
    assert (
        writer._trusted_parent(cast(os.stat_result, foreign_sticky), os.getuid())
        is False
    )
    assert (
        writer._trusted_parent(cast(os.stat_result, foreign_readonly), os.getuid())
        is True
    )
    assert (
        writer._trusted_parent(cast(os.stat_result, own_private), os.getuid()) is True
    )


def test_absolute_target_under_nonwritable_foreign_anchors_succeeds():
    payload = render_fresh_baseline(_result())
    target = _PROJECT_ROOT / ".baseline-write-absolute-test.json"
    try:
        write_baseline(target, payload)
        assert target.read_bytes() == payload
    finally:
        target.unlink(missing_ok=True)


def test_replace_feature_failure_is_sanitized_and_preserves_old_target(
    tmp_path: Path, monkeypatch
):
    target = _target()
    target.write_bytes(b"old")
    payload = render_fresh_baseline(_result())

    def unsupported(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("private platform detail")

    monkeypatch.setattr(writer.os, "replace", unsupported)
    with pytest.raises(BaselineWriteError) as captured:
        write_baseline(target, payload, overwrite=True)
    assert captured.value.code == "replace-failed"
    assert target.read_bytes() == b"old"
    assert "private platform detail" not in str(captured.value)


def test_partial_write_and_eintr_are_retried(tmp_path: Path, monkeypatch):
    payload = render_fresh_baseline(_result())
    original_write = writer.os.write
    calls = 0

    def partial(descriptor: int, data: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InterruptedError
        view = memoryview(cast(bytes, data))
        return original_write(descriptor, view[: min(7, len(view))])

    monkeypatch.setattr(writer.os, "write", partial)
    target = _target()
    write_baseline(target, payload)
    assert target.read_bytes() == payload
    assert calls > 2
