"""Budget policy project-source tests without CLI or network access."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from uv_packsize import budget_config_source
from uv_packsize.budget import BudgetPolicy, IncompleteBudgetPolicy
from uv_packsize.budget_config import (
    BudgetPolicyConfigError,
    BudgetPolicyConfigErrorReason,
)
from uv_packsize.budget_config_source import (
    MAX_BUDGET_CONFIG_BYTES,
    BudgetPolicySourceError,
    BudgetPolicySourceErrorReason,
    BudgetPolicySourceSection,
    load_budget_policy,
)


def write_project(tmp_path: Path, content: str | bytes) -> Path:
    path = tmp_path / "pyproject.toml"
    if type(content) is str:
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(cast(bytes, content))
    return path


def test_explicit_budget_table_is_loaded_from_the_closed_tool_section(tmp_path):
    path = write_project(
        tmp_path,
        """\
[tool.uv-packsize.budget]
max_total_logical_bytes = 100
max_increase_logical_bytes = 7
incomplete_policy = "allow-partial"
""",
    )

    policy = load_budget_policy(path)

    assert policy == BudgetPolicy(
        max_total_logical_bytes=100,
        max_increase_logical_bytes=7,
        incomplete_policy=IncompleteBudgetPolicy.ALLOW_PARTIAL,
    )


@pytest.mark.parametrize(
    "content",
    [
        "[project]\nname = 'example'\n",
        "[tool]\nother = 1\n",
        "[tool.uv-packsize]\nother = 1\n",
    ],
)
def test_absent_budget_section_returns_no_source_policy(tmp_path, content):
    assert load_budget_policy(write_project(tmp_path, content)) is None


def test_explicit_empty_budget_table_is_an_explicit_no_op_policy(tmp_path):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")

    assert load_budget_policy(path) == BudgetPolicy()


@pytest.mark.parametrize(
    ("content", "reason", "section"),
    [
        (
            "tool = 'not-a-table'\n",
            BudgetPolicySourceErrorReason.INVALID_TOOL_SECTION,
            BudgetPolicySourceSection.TOOL,
        ),
        (
            "[tool]\nuv-packsize = 'not-a-table'\n",
            BudgetPolicySourceErrorReason.INVALID_UV_PACKSIZE_SECTION,
            BudgetPolicySourceSection.UV_PACKSIZE,
        ),
        (
            "[tool.uv-packsize]\nbudget = 'not-a-table'\n",
            BudgetPolicySourceErrorReason.INVALID_BUDGET_SECTION,
            BudgetPolicySourceSection.BUDGET,
        ),
    ],
)
def test_non_table_config_sections_are_sanitized(tmp_path, content, reason, section):
    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(write_project(tmp_path, content))

    assert caught.value.reason is reason
    assert caught.value.section is section
    assert caught.value.path == section.value


def test_policy_parser_errors_propagate_without_exposing_config_values(tmp_path):
    secret = "token://private.example/never-reflect"
    path = write_project(
        tmp_path,
        f"[tool.uv-packsize.budget]\n{secret!r} = {secret!r}\n",
    )

    with pytest.raises(BudgetPolicyConfigError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicyConfigErrorReason.UNKNOWN_FIELD
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (
            b"[tool.uv-packsize.budget]\nvalue = \xff\n",
            BudgetPolicySourceErrorReason.INVALID_ENCODING,
        ),
        (
            b"[tool.uv-packsize.budget\nsecret = 'private'\n",
            BudgetPolicySourceErrorReason.INVALID_TOML,
        ),
    ],
)
def test_toml_parse_failures_are_sanitized(tmp_path, content, reason):
    secret = "private"
    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(write_project(tmp_path, content))

    assert caught.value.reason is reason
    assert caught.value.section is BudgetPolicySourceSection.DOCUMENT
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_missing_file_and_non_regular_file_have_fixed_errors(tmp_path):
    with pytest.raises(BudgetPolicySourceError) as missing:
        load_budget_policy(tmp_path / "private-missing.toml")
    assert missing.value.reason is BudgetPolicySourceErrorReason.FILE_NOT_FOUND
    assert missing.value.section is BudgetPolicySourceSection.FILE

    with pytest.raises(BudgetPolicySourceError) as directory:
        load_budget_policy(tmp_path)
    assert directory.value.reason is BudgetPolicySourceErrorReason.NOT_REGULAR_FILE
    assert directory.value.section is BudgetPolicySourceSection.FILE


def test_platform_path_error_is_sanitized_without_reflecting_the_path():
    path = Path("\0private-project.toml")

    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.READ_FAILED
    assert caught.value.section is BudgetPolicySourceSection.FILE
    assert "private" not in str(caught.value)


def test_read_error_and_size_limit_are_sanitized(tmp_path, monkeypatch):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")

    def fail_open(_path, _flags):
        raise PermissionError("private permission failure")

    monkeypatch.setattr(budget_config_source.os, "open", fail_open)
    with pytest.raises(BudgetPolicySourceError) as read:
        load_budget_policy(path)
    assert read.value.reason is BudgetPolicySourceErrorReason.READ_FAILED
    assert "private" not in str(read.value)

    monkeypatch.undo()
    path.write_bytes(b"#" * (MAX_BUDGET_CONFIG_BYTES + 1))
    with pytest.raises(BudgetPolicySourceError) as too_large:
        load_budget_policy(path)
    assert too_large.value.reason is BudgetPolicySourceErrorReason.SIZE_LIMIT


def test_symlink_target_is_allowed_as_ordinary_explicit_project_file(tmp_path):
    target = write_project(
        tmp_path, "[tool.uv-packsize.budget]\nmax_total_logical_bytes = 1\n"
    )
    link = tmp_path / "project-link.toml"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip()

    assert load_budget_policy(link) == BudgetPolicy(max_total_logical_bytes=1)


def test_regular_file_replaced_by_fifo_is_rejected_without_blocking(
    tmp_path, monkeypatch
):
    if not hasattr(budget_config_source.os, "mkfifo"):
        pytest.skip()
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    real_open = budget_config_source.os.open

    def replace_with_fifo(open_path, flags):
        path.unlink()
        budget_config_source.os.mkfifo(path)
        return real_open(open_path, flags)

    monkeypatch.setattr(budget_config_source.os, "open", replace_with_fifo)
    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.NOT_REGULAR_FILE


def test_regular_file_replacement_is_rejected_by_identity(tmp_path, monkeypatch):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    replacement = tmp_path / "replacement.toml"
    replacement.write_text("[tool.uv-packsize.budget]\n", encoding="utf-8")
    real_open = budget_config_source.os.open

    def replace_regular_file(open_path, flags):
        budget_config_source.os.replace(replacement, path)
        return real_open(open_path, flags)

    monkeypatch.setattr(budget_config_source.os, "open", replace_regular_file)
    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.CHANGED_FILE


def test_same_inode_same_length_observable_rewrite_is_rejected(tmp_path, monkeypatch):
    original = "[tool.uv-packsize.budget]\nmax_total_logical_bytes = 1\n"
    replacement = "[tool.uv-packsize.budget]\nmax_total_logical_bytes = 2\n"
    assert len(replacement) == len(original)
    path = write_project(tmp_path, original)
    before = path.stat()
    real_read = budget_config_source.os.read
    rewritten = False

    def rewrite_after_read(descriptor: int, count: int) -> bytes:
        nonlocal rewritten
        chunk = real_read(descriptor, count)
        if chunk and not rewritten:
            rewritten = True
            path.write_text(replacement, encoding="utf-8")
            budget_config_source.os.utime(
                path,
                ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000),
            )
            after = path.stat()
            assert (after.st_dev, after.st_ino, after.st_size) == (
                before.st_dev,
                before.st_ino,
                before.st_size,
            )
        return chunk

    monkeypatch.setattr(budget_config_source.os, "read", rewrite_after_read)

    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert rewritten is True
    assert caught.value.reason is BudgetPolicySourceErrorReason.CHANGED_FILE
    assert caught.value.section is BudgetPolicySourceSection.FILE


@pytest.mark.parametrize("post_change", ["missing", "replacement"])
def test_post_read_path_change_is_rejected_as_changed_file(
    tmp_path, monkeypatch, post_change
):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    replacement = tmp_path / "replacement.toml"
    replacement.write_text("[tool.uv-packsize.budget]\n", encoding="utf-8")
    real_read = budget_config_source.os.read
    changed = False

    def change_after_read(descriptor: int, count: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, count)
        if chunk and not changed:
            changed = True
            if post_change == "missing":
                path.unlink()
            else:
                budget_config_source.os.replace(replacement, path)
        return chunk

    monkeypatch.setattr(budget_config_source.os, "read", change_after_read)

    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.CHANGED_FILE


def test_post_read_nonregular_path_is_changed_file(tmp_path, monkeypatch):
    if not hasattr(budget_config_source.os, "mkfifo"):
        pytest.skip()
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    real_read = budget_config_source.os.read
    changed = False

    def replace_after_read(descriptor: int, count: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, count)
        if chunk and not changed:
            changed = True
            path.unlink()
            budget_config_source.os.mkfifo(path)
        return chunk

    monkeypatch.setattr(budget_config_source.os, "read", replace_after_read)

    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.CHANGED_FILE


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (
            FileNotFoundError("private post-read missing detail"),
            BudgetPolicySourceErrorReason.CHANGED_FILE,
        ),
        (
            ValueError("private post-read value detail"),
            BudgetPolicySourceErrorReason.READ_FAILED,
        ),
        (
            OSError("private post-read OS detail"),
            BudgetPolicySourceErrorReason.READ_FAILED,
        ),
    ],
)
def test_post_read_stat_failures_are_sanitized(tmp_path, monkeypatch, failure, reason):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    real_fstat = budget_config_source.os.fstat
    calls = 0

    def fail_post_fstat(descriptor: int):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise failure
        return real_fstat(descriptor)

    monkeypatch.setattr(budget_config_source.os, "fstat", fail_post_fstat)

    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is reason
    assert "private post-read" not in str(caught.value)


def test_body_failure_wins_over_close_failure_and_successful_body_requires_close(
    tmp_path, monkeypatch
):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")
    real_fstat = budget_config_source.os.fstat
    calls = 0

    def changed_post_fstat(descriptor: int):
        nonlocal calls
        calls += 1
        observed = real_fstat(descriptor)
        if calls == 1:
            return observed
        values = list(observed)
        values[8] += 1
        return budget_config_source.os.stat_result(values)

    real_close = budget_config_source.os.close

    def close_then_fail(descriptor: int) -> bool:
        real_close(descriptor)
        return False

    monkeypatch.setattr(budget_config_source.os, "fstat", changed_post_fstat)
    monkeypatch.setattr(budget_config_source, "_safe_close", close_then_fail)
    with pytest.raises(BudgetPolicySourceError) as body_failure:
        load_budget_policy(path)
    assert body_failure.value.reason is BudgetPolicySourceErrorReason.CHANGED_FILE

    monkeypatch.undo()
    parse_calls = 0

    def unexpected_parse(_payload):
        nonlocal parse_calls
        parse_calls += 1
        raise AssertionError("parse must not run after close failure")

    monkeypatch.setattr(budget_config_source, "_safe_close", close_then_fail)
    monkeypatch.setattr(budget_config_source, "_parse", unexpected_parse)
    with pytest.raises(BudgetPolicySourceError) as close_failure:
        load_budget_policy(path)
    assert close_failure.value.reason is BudgetPolicySourceErrorReason.READ_FAILED
    assert parse_calls == 0


def test_path_boundary_is_exact_and_parser_availability_is_sanitized(
    tmp_path, monkeypatch
):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")

    with pytest.raises(TypeError):
        load_budget_policy(cast(Path, "pyproject.toml"))

    monkeypatch.setattr(budget_config_source, "_toml", None)
    with pytest.raises(BudgetPolicySourceError) as unavailable:
        load_budget_policy(path)
    assert unavailable.value.reason is BudgetPolicySourceErrorReason.PARSER_UNAVAILABLE
    assert unavailable.value.section is BudgetPolicySourceSection.DOCUMENT


def test_non_mapping_document_is_sanitized(tmp_path, monkeypatch):
    path = write_project(tmp_path, "[tool.uv-packsize.budget]\n")

    class FakeToml:
        @staticmethod
        def load(_source):
            return []

    monkeypatch.setattr(budget_config_source, "_toml", FakeToml)
    with pytest.raises(BudgetPolicySourceError) as caught:
        load_budget_policy(path)

    assert caught.value.reason is BudgetPolicySourceErrorReason.INVALID_DOCUMENT
    assert caught.value.section is BudgetPolicySourceSection.DOCUMENT
