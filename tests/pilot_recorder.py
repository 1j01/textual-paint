import os
from textual.css.query import NoMatches, TooManyMatches
from textual.dom import DOMNode
from textual.events import Event, Key, MouseDown, MouseMove, MouseUp
from textual.geometry import Offset
from textual.screen import Screen
from textual_paint.paint import PaintApp

def unique_file(path: str) -> str:
    filename, extension = os.path.splitext(path)
    counter = 1

    while os.path.exists(path):
        # path = f"{filename} ({counter}){extension}"
        path = f"{filename}_{counter}{extension}"
        counter += 1

    return path

OUTPUT_FILE = unique_file("tests/test_paint_something.py")

steps: list[tuple[Event, Offset, str, int|None]] = []

def get_selector(target: DOMNode) -> tuple[str, int|None]:
    """Return a selector that can be used to find the widget."""
    assert app is not None, "app should be set by now"
    widget = target
    if widget.id:
        return f"#{widget.id}", None
    selector = widget.css_identifier
    while widget.parent and not isinstance(widget.parent, Screen):
        widget = widget.parent
        if widget.id:
            selector = f"#{widget.id} {selector}"
            break
        else:
            selector = f"{widget.css_identifier} {selector}"
    try:
        query_result = app.query_one(selector)
    except TooManyMatches:
        # raise Exception(f"Selector {selector!r} matches more than one widget ({app.query(selector).nodes!r})")
        return selector, app.query(selector).nodes.index(target)
        # smarter differentiators would be nice, like tooltip or text content,
        # but at least with indices, you'll know when you changed the tab order
    except NoMatches:
        raise Exception(f"Selector {selector!r} didn't match the target widget ({target!r})")
    if query_result is not target:
        raise Exception(f"Selector {selector!r} matched a different widget than the target ({query_result!r} rather than {target!r})")

    return selector, None

original_on_event = PaintApp.on_event
async def on_event(self: PaintApp, event: Event) -> None:
    await original_on_event(self, event)
    if isinstance(event, (MouseDown, MouseMove, MouseUp)):
        widget, _ = self.get_widget_at(*event.screen_offset)
        offset = event.screen_offset - widget.region.offset
        steps.append((event, offset, *get_selector(widget)))
        # This doesn't hold:
        # assert event.x == event.screen_x - widget.region.x, f"event.x ({event.x}) should be event.screen_x ({event.screen_x}) - widget ({widget!r}).region.x ({widget.region.x})"
        # assert event.y == event.screen_y - widget.region.y, f"event.y ({event.y}) should be event.screen_y ({event.screen_y}) - widget ({widget!r}).region.y ({widget.region.y})"
        # I think the offset == screen_offset once it's bubbled up to the app?
    elif isinstance(event, Key):
        if event.key == "ctrl+z":
            steps.pop()
            replay()
        elif event.key == "ctrl+c":
            save_replay()

app: PaintApp | None = None

def replay() -> None:
    global app
    if app is not None:
        app.exit()
    app = PaintApp()
    app.on_event = on_event.__get__(app)
    async def replay_steps() -> None:
        assert app is not None, "app should be set by now"
        for event, offset, selector, index in steps:
            await app.on_event(event)
    app.call_later(replay_steps)
    app.run() # blocking

def indent(text: str, spaces: int) -> str:
    return "\n".join(" " * spaces + line for line in text.splitlines())

def save_replay() -> None:
    assert app is not None, "app should be set by now"
    helpers_code = ""
    steps_code = ""
    for event, offset, selector, index in steps:
        if isinstance(event, MouseDown):
            if index is None:
                steps_code += f"await pilot.click({selector!r}, offset=Offset({offset.x}, {offset.y}))\n"
            else:
                steps_code += f"widget = pilot.app.query({selector!r})[{index!r}]\n"
                # can't pass a widget to pilot.click, only a selector, or None
                steps_code += f"await pilot.click(offset=Offset({offset.x}, {offset.y}) + widget.region.offset)\n"


    script = f"""\
from pathlib import Path, PurePath
from typing import Awaitable, Callable, Iterable, Protocol

import pytest
from textual.geometry import Offset
from textual.pilot import Pilot
from textual.widgets import Input

class SnapCompareType(Protocol):
    \"\"\"Type of the function returned by the snap_compare fixture.\"\"\"
    def __call__(
        self,
        app_path: str | PurePath,
        press: Iterable[str] = (),
        terminal_size: tuple[int, int] = (80, 24),
        run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,  # type: ignore
    ) -> bool:
        ...

# Relative paths are treated as relative to this file, when using snap_compare.
PAINT = Path("../src/textual_paint/paint.py")

# Prevent flaky tests due to timing issues.
Input.cursor_blink = False  # type: ignore

def test_paint_something(snap_compare: SnapCompareType):
    async def test_paint_something_steps(pilot: Pilot[None]):
{indent(helpers_code, 8)}
{indent(steps_code, 8)}

    assert snap_compare(PAINT, run_before=test_paint_something_steps, terminal_size=({app.size.width}, {app.size.height}))
"""
    with open(OUTPUT_FILE, "w") as f:
        f.write(script)
    # app.exit(None, Text(f"Saved replay to {OUTPUT_FILE}"))

if __name__ == "__main__":
    replay() # with no steps, this will just run the app, ready for recording
