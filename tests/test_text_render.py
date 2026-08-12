import pytest

from uv_packsize.text_render import render_table, render_total_table, safe_display


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("plain ASCII", "plain ASCII"),
        ("wide\u3000", "wide\\u3000"),
        ("combininge\u0301", "combininge\\u0301"),
        ("emoji\U0001f642", "emoji\\U0001F642"),
        ("bidi\u202e", "bidi?"),
        ("ansi\x1b[31m\n", "ansi?[31m?"),
    ],
)
def test_safe_display_is_deterministic_visible_ascii(value, expected):
    displayed = safe_display(value)

    assert displayed == expected
    assert displayed.isascii()
    assert len(displayed) == len(displayed.encode("ascii"))


def test_render_table_sanitizes_before_calculating_right_alignment():
    lines = render_table(
        ("Name", "Size"),
        (("evil\x1b[31m", "1 B"), ("wide\u3000", "1.00 KiB")),
        (1,),
    )

    assert "\x1b" not in "\n".join(lines)
    assert "evil?[31m" in lines[2]
    assert "wide\\u3000" in lines[3]
    assert lines[2].index("1 B") + len("1 B") == lines[3].index("1.00 KiB") + len(
        "1.00 KiB"
    )


def test_render_table_validates_shape_and_handles_empty_rows():
    assert render_table(("Name", "Size"), (), (1,)) == (
        "Name  Size",
        "----  ----",
    )
    with pytest.raises(ValueError, match="header column count"):
        render_table(("Name", "Size"), (("only one",),), (1,))
    with pytest.raises(ValueError, match="header columns"):
        render_table(("Name",), (), (1,))


def test_render_total_table_keeps_stable_empty_case():
    assert render_total_table(
        title="Package Sizes",
        header=("Package", "Size"),
        rows=(),
        footer=("Total Package Size", "0 B"),
    ) == ("--- Package Sizes ---\nNo items to display.\nTotal Package Size  0 B")


def test_render_table_does_not_read_terminal_or_locale_environment(monkeypatch):
    expected = render_table(("Name", "Size"), (("wide\u3000", "1.00 KiB"),), (1,))
    monkeypatch.setenv("COLUMNS", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("LC_ALL", "unavailable-locale")

    assert (
        render_table(("Name", "Size"), (("wide\u3000", "1.00 KiB"),), (1,)) == expected
    )
