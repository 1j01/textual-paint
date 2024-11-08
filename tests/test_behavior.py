"""General behavioral/functional tests.

Run with `pytest tests/test_behavior.py`, or `pytest` to run all tests.
"""

from pyfakefs.fake_filesystem import FakeFilesystem
import pytest
from textual.events import Paste

from textual_paint.char_input import CharInput
from textual_paint.paint import PaintApp


async def test_char_input_paste():
    app = PaintApp()
    async with app.run_test() as pilot:  # type: ignore
        char_input = app.query_one(CharInput)
        char_input.post_message(Paste("Hello, world!"))
        await pilot.pause()
        assert char_input.value == "!"

@pytest.mark.xfail(reason="Currently splitting on codepoints, not graphemes")
async def test_char_input_paste_emoji():
    app = PaintApp()
    async with app.run_test() as pilot:  # type: ignore
        char_input = app.query_one(CharInput)
        char_input.post_message(Paste("🆖👨‍👩‍👧‍👧"))  # 🆗 is too easy, 👨‍👩‍👧‍👧 uses zero-width joiner characters
        await pilot.pause()
        assert char_input.value == "👨‍👩‍👧‍👧"

async def test_file_drag_and_drop(my_fs: FakeFilesystem):
    # File drag and drop is treated as a paste in the terminal.
    # CharInput often has focus, and needs to propagate the event to the app.
    my_fs.create_file("/test_file_to_load.txt", contents="Hello, world!")
    app = PaintApp()
    async with app.run_test() as pilot:  # type: ignore
        char_input = app.query_one(CharInput)
        char_input.post_message(Paste("/test_file_to_load.txt"))
        await pilot.pause()
        # TODO: fix double handling of Paste event
        # It should ONLY load the file in this case, not also paste the filename into the char input.
        # assert char_input.value == " " # default, may become full block (█) in the future
        assert app.query_one("Canvas").render_line(0).text == "Hello, world!"

