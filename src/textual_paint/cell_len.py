"""Workaround for rich.cells.cell_len measuring some characters incorrectly."""

import curses
from typing import cast
from rich._cell_widths import CELL_WIDTHS

CELL_WIDTHS = cast(list[tuple[int, int, int]], CELL_WIDTHS)  # type: ignore
"""A list of (start, end, width) tuples, where start and end form an inclusive range of codepoints having that width."""

def accurate_slow_cell_len(text: str) -> int:
    """Measure the width of a string in cells, manually, using DSR control codes.

    `rich.cells.cell_len` can be used in general, and is fast, using a table and caching,
    but some characters are measured incorrectly, causing misalignment of everything to the right of them,
    since the width varies by terminal/locale/font.

    This function uses a Device Status Report control code to get the cursor position after writing to the terminal,
    and measures the difference.
    
    It should be used sparingly, at startup, before `cell_len` is used to measure the characters in question,
    to avoid caching the wrong values.
    """
    curses.setupterm()

    stdscr = curses.initscr()

    try:
        # Draw the text at the top left of the screen
        stdscr.addstr(0, 0, text)

        # Get the ending cursor position
        _, end_col = stdscr.getyx()

        # The width is the difference between the starting and ending cursor positions,
        # and since the starting cursor position is always 0, it's just the ending cursor position.
        width = end_col

    finally:
        # End the curses session
        curses.endwin()

    return width

def patch_cell_widths_table(text: str) -> None:
    """Patch the cell length measurements table for tool icons, since it varies by terminal/locale/font.
    
    This should be called before the characters in question are ever measured with cell_len, to avoid caching the wrong values.
    """
    for char in text:
        codepoint = ord(char)
        tuple_for_char = (codepoint, codepoint, accurate_slow_cell_len(char))
        patched = False
        for i in range(len(CELL_WIDTHS)):
            start, end, width = CELL_WIDTHS[i]
            if codepoint >= start and codepoint <= end:
                # Break up the range into three ranges, and fix the width of the middle one targeting char.
                CELL_WIDTHS[i:i+1] = [
                    (start, codepoint - 1, width),
                    tuple_for_char,
                    (codepoint + 1, end, width),
                ]
                patched = True
                break
        if not patched:
            # Add a new range for char. This needs to be inserted in order,
            # since _get_codepoint_cell_size uses a binary search.
            for i in range(len(CELL_WIDTHS)):
                start, end, width = CELL_WIDTHS[i]
                if codepoint < start:
                    CELL_WIDTHS.insert(i, tuple_for_char)
                    break
            else:
                CELL_WIDTHS.append(tuple_for_char)


if __name__ == '__main__':
    from rich.cells import cell_len

    TEST_CHARS = 'aあ✏️🖌️🪣🫗👩🏻‍🦰'

    # Compare the two functions
    # THIS TEST IS MUTUALLY EXCLUSIVE WITH THE PATCHING TEST BELOW
    # SINCE `cell_len` USES A CACHE!
    # for char in TEST_CHARS:
    #     print(f'{char} ({char.encode("unicode_escape")}) cell_len: {cell_len(char)} accurate_slow_cell_len: {accurate_slow_cell_len(char)}')

    # print(f'{TEST_CHARS} ({TEST_CHARS.encode("unicode_escape")}) cell_len: {cell_len(TEST_CHARS)} accurate_slow_cell_len: {accurate_slow_cell_len(TEST_CHARS)}')
    
    # Test that patching the table brings the two functions in line
    for char in TEST_CHARS:
        patch_cell_widths_table(char)
        expected = accurate_slow_cell_len(char)
        actual = cell_len(char)
        assert actual == expected, f'Expected {expected} for {char} ({char.encode("unicode_escape")}), got {actual}'
    
    expected = accurate_slow_cell_len(TEST_CHARS)
    actual = cell_len(TEST_CHARS)
    assert actual == expected, f'Expected {expected} for {TEST_CHARS} ({TEST_CHARS.encode("unicode_escape")}), got {actual}'

