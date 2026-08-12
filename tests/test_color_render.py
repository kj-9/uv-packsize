"""Tests for opt-in ANSI decoration of safe human-readable reports."""

from typing import Any, cast

import click
import pytest

from uv_packsize.color_render import ColorMode, decorate_report, should_color_report


@pytest.mark.parametrize(
    ("mode", "stdout_is_tty", "term", "no_color_is_set", "expected"),
    [
        (ColorMode.NEVER, True, "xterm-256color", False, False),
        (ColorMode.ALWAYS, False, "dumb", True, True),
        (ColorMode.AUTO, True, "xterm-256color", False, True),
        (ColorMode.AUTO, False, "xterm-256color", False, False),
        (ColorMode.AUTO, True, "dumb", False, False),
        (ColorMode.AUTO, True, "xterm-256color", True, False),
        (ColorMode.AUTO, True, None, False, True),
    ],
)
def test_should_color_report_is_a_pure_policy_projection(
    mode, stdout_is_tty, term, no_color_is_set, expected
):
    assert (
        should_color_report(
            mode,
            stdout_is_tty=stdout_is_tty,
            term=term,
            no_color_is_set=no_color_is_set,
        )
        is expected
    )


def test_decorate_report_preserves_semantic_text_and_line_endings():
    report = (
        "--- Rich Analysis Summary ---\r\n"
        "Completeness: complete\r\n"
        "Warning: incomplete analysis (missing-record=1).\r\n"
        "\r\n"
        "--- Size Budget ---\r\n"
        "Result: FAIL\r\n"
    )

    decorated = decorate_report(report)

    assert "\x1b[" in decorated
    assert click.unstyle(decorated) == report
    assert decorated.count("\r\n") == report.count("\r\n")


def test_decorate_report_does_not_interpret_escaped_untrusted_text():
    report = (
        "--- Package Sizes ---\n"
        "evil?name\\u754C\\x1B[31m  1 B\n"
        "not-a-structural Result: FAIL value\n"
    )

    decorated = decorate_report(report)

    assert click.unstyle(decorated) == report
    assert "\x1b[31m" not in click.unstyle(decorated)
    assert "\\x1B[31m" in decorated


@pytest.mark.parametrize(
    ("value", "expected_fragment"),
    [
        ("Result: PASS", "\x1b[32mPASS\x1b[0m"),
        ("Result: FAIL", "\x1b[31mFAIL\x1b[0m"),
        ("Completeness: incomplete", "\x1b[33mincomplete\x1b[0m"),
    ],
)
def test_decorate_report_styles_only_fixed_status_lines(value, expected_fragment):
    assert expected_fragment in decorate_report(value)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("auto",), "mode must be ColorMode"),
        ((ColorMode.AUTO,), "stdout_is_tty must be bool"),
    ],
)
def test_should_color_report_rejects_forged_policy_inputs(args, message):
    kwargs = {
        "stdout_is_tty": True,
        "term": "xterm",
        "no_color_is_set": False,
    }
    if args == (ColorMode.AUTO,):
        kwargs["stdout_is_tty"] = cast(Any, 1)

    with pytest.raises(TypeError, match=message):
        should_color_report(*args, **kwargs)
