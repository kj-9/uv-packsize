"""Terminal-safe primitives shared by human-readable renderers.

Text reports must not let installed metadata change terminal state or table
geometry. These helpers convert every non-printable or non-ASCII code point
to a visible ASCII escape before measuring and aligning it. They deliberately
do not inspect the terminal, locale, or ``COLUMNS`` environment variable.
"""

import unicodedata


def safe_display(value: str) -> str:
    """Return visible ASCII whose ``len`` equals its terminal display width.

    Printable ASCII is retained byte-for-byte. All other Unicode code points,
    including ANSI control bytes and format controls, are replaced with ``?``.
    Other non-ASCII code points, including combining marks and wide glyphs,
    are represented by fixed-width ASCII escapes.
    """

    if not isinstance(value, str):
        raise TypeError("value must be a str")

    escaped: list[str] = []
    for character in value:
        code_point = ord(character)
        if 0x20 <= code_point <= 0x7E:
            escaped.append(character)
        elif unicodedata.category(character).startswith("C"):
            escaped.append("?")
        elif code_point <= 0xFFFF:
            escaped.append(f"\\u{code_point:04X}")
        else:
            escaped.append(f"\\U{code_point:08X}")
    return "".join(escaped)


def render_table(
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    right_align_indexes: tuple[int, ...] = (),
) -> tuple[str, ...]:
    """Render a rectangular table from terminal-safe ASCII cells.

    Values are sanitized here rather than relying on each caller to remember
    that step. Empty row sets still have a deterministic header and separator.
    """

    _validate_table_shape(header, rows, right_align_indexes)
    displayed_header = tuple(safe_display(value) for value in header)
    displayed_rows = tuple(tuple(safe_display(value) for value in row) for row in rows)
    right_align = frozenset(right_align_indexes)
    widths = tuple(
        max(
            (len(displayed_header[index]), *(len(row[index]) for row in displayed_rows))
        )
        for index in range(len(displayed_header))
    )

    def line(row: tuple[str, ...]) -> str:
        return "  ".join(
            value.rjust(widths[index])
            if index in right_align
            else value.ljust(widths[index])
            for index, value in enumerate(row)
        )

    return (
        line(displayed_header),
        "  ".join("-" * width for width in widths),
        *(line(row) for row in displayed_rows),
    )


def render_total_table(
    *,
    title: str,
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    footer: tuple[str, str],
) -> str:
    """Render a titled table with a footer and stable empty-table handling."""

    if not isinstance(title, str):
        raise TypeError("title must be a str")
    if not isinstance(footer, tuple) or len(footer) != 2:
        raise ValueError("footer must contain exactly two cells")
    if len(header) != len(footer):
        raise ValueError("footer must match the header column count")
    if not rows:
        _validate_table_shape(header, rows, (1,))
        return "\n".join(
            (
                f"--- {safe_display(title)} ---",
                "No items to display.",
                "  ".join(safe_display(value) for value in footer),
            )
        )

    _validate_table_shape(header, rows, (1,))
    displayed_footer = tuple(safe_display(value) for value in footer)
    widths = tuple(
        max(
            len(safe_display(header[index])),
            *(len(safe_display(row[index])) for row in rows),
            len(displayed_footer[index]),
        )
        for index in range(len(header))
    )
    right_align = frozenset((1,))

    def line(row: tuple[str, ...]) -> str:
        return "  ".join(
            safe_display(value).rjust(widths[index])
            if index in right_align
            else safe_display(value).ljust(widths[index])
            for index, value in enumerate(row)
        )

    separator = "  ".join("-" * width for width in widths)
    return "\n".join(
        (
            f"--- {safe_display(title)} ---",
            line(header),
            separator,
            *(line(row) for row in rows),
            separator,
            line(displayed_footer),
        )
    )


def _validate_table_shape(
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    right_align_indexes: tuple[int, ...],
) -> None:
    if not isinstance(header, tuple) or not header:
        raise ValueError("header must contain at least one column")
    if not isinstance(rows, tuple):
        raise TypeError("rows must be a tuple")
    if not isinstance(right_align_indexes, tuple):
        raise TypeError("right_align_indexes must be a tuple")
    if any(not isinstance(value, str) for value in header):
        raise TypeError("header cells must be str")
    if any(
        not isinstance(index, int) or isinstance(index, bool)
        for index in right_align_indexes
    ):
        raise TypeError("right_align_indexes must contain int values")
    if any(index < 0 or index >= len(header) for index in right_align_indexes):
        raise ValueError("right_align_indexes must reference header columns")
    for row in rows:
        if not isinstance(row, tuple):
            raise TypeError("rows must contain tuples")
        if len(row) != len(header):
            raise ValueError("rows must match the header column count")
        if any(not isinstance(value, str) for value in row):
            raise TypeError("row cells must be str")
