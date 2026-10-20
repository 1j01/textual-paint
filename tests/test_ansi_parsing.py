"""Test parsing of ANSI art.

These use tiny synthetic files rather than samples, to pin down specific behaviors.

Run with `pytest tests/test_ansi_parsing.py`, or `pytest` to run all tests.
"""

from textual_paint.ansi_art_document import AnsiArtDocument


def cell_text(document: AnsiArtDocument) -> list[str]:
    """Get the characters of each row of the document."""
    # There can be extra rows in `ch` beyond `height`, for the document's other purposes.
    return ["".join(row) for row in document.ch[:document.height]]

def cell_rgb(document: AnsiArtDocument, y: int, x: int) -> tuple[int, int, int]:
    """Get the foreground color of a cell as an (r, g, b) tuple, asserting that it has one."""
    color = document.st[y][x].color
    assert color is not None, "cell has no foreground color"
    triplet = color.triplet
    assert triplet is not None, "color has no RGB triplet"
    return (triplet.red, triplet.green, triplet.blue)

def cell_bg_rgb(document: AnsiArtDocument, y: int, x: int) -> tuple[int, int, int]:
    """Get the background color of a cell as an (r, g, b) tuple, asserting that it has one."""
    bgcolor = document.st[y][x].bgcolor
    assert bgcolor is not None, "cell has no background color"
    triplet = bgcolor.triplet
    assert triplet is not None, "color has no RGB triplet"
    return (triplet.red, triplet.green, triplet.blue)

def test_ignores_cursor_visibility_sequences() -> None:
    """chafa emits ESC[?25l and ESC[?25h to hide and show the cursor.

    stransi can't parse these, and used to crash with
    `ValueError: invalid literal for int() with base 10: '?25'`.
    See https://github.com/1j01/textual-paint/issues/12
    """
    document = AnsiArtDocument.from_ansi("\x1b[?25l\x1b[31mAB\x1b[0m\x1b[?25h")
    # The escape sequences shouldn't be loaded as text, either.
    assert cell_text(document) == ["AB"]
    assert document.width == 2
    assert document.height == 1
    assert cell_rgb(document, 0, 0)[0] == 128

def test_ignores_cursor_visibility_sequences_after_text() -> None:
    """Test that the sequences are also ignored when they don't start a chunk of text.

    stransi leaves unrecognized sequences in the text stream in this case,
    which used to end up in the document as a bunch of visible garbage characters.
    """
    document = AnsiArtDocument.from_ansi("AB\x1b[?25h\n")
    assert cell_text(document) == ["AB"]

def test_reset_attribute_resets_colors() -> None:
    """Test that ESC[0m (reset) resets the colors, rather than keeping the previous style."""
    document = AnsiArtDocument.from_ansi("\x1b[31mX\x1b[0mY")
    assert cell_text(document) == ["XY"]
    assert cell_rgb(document, 0, 0) == (128, 0, 0)
    assert cell_rgb(document, 0, 1) == (0, 0, 0)
    assert cell_bg_rgb(document, 0, 1) == (255, 255, 255)

def test_default_color_sequences_reset_colors() -> None:
    """Test that ESC[39m and ESC[49m reset the foreground and background colors respectively."""
    document = AnsiArtDocument.from_ansi("\x1b[37;44mX\x1b[39mY\x1b[49mZ")
    assert cell_text(document) == ["XYZ"]
    # Background is kept when only the foreground is reset.
    assert cell_bg_rgb(document, 0, 0) == cell_bg_rgb(document, 0, 1)
    # Foreground is reset to the default (black).
    assert cell_rgb(document, 0, 1) == (0, 0, 0)
    # Background is reset to the default (white).
    assert cell_bg_rgb(document, 0, 2) == (255, 255, 255)

def test_ignores_unsupported_sequences() -> None:
    """Test that sequences that stransi doesn't model don't prevent opening a file."""
    # Strikethrough is not represented in the document model.
    document = AnsiArtDocument.from_ansi("\x1b[9mX")
    assert cell_text(document) == ["X"]
    assert document.width == 1
    assert document.height == 1

def test_opens_chafa_style_ans_file() -> None:
    """Test that a file in the style of `chafa some_file.png > output.ans` can be opened."""
    content = (
        "\x1b[?25l\x1b[38;5;196m  \x1b[0m\n"
        "\x1b[38;5;46m  \x1b[0m\x1b[?25h"
    ).encode("utf-8")
    document = AnsiArtDocument.decode_based_on_file_extension(content, "output.ans")
    assert cell_text(document) == ["  ", "  "]
    assert document.width == 2
    assert document.height == 2
    assert cell_rgb(document, 0, 0) == (255, 0, 0)
    assert cell_rgb(document, 1, 0) == (0, 255, 0)
