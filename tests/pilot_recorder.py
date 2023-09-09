import os
from textual.css.query import NoMatches, TooManyMatches
from textual.dom import DOMNode
from textual.events import Event, Key, MouseDown, MouseMove, MouseUp
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

steps: list[tuple[Event, str, int|None]] = []

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
        widget, _ = self.get_widget_at(event.x, event.y)
        steps.append((event, *get_selector(widget)))
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
        for event, selector, index in steps:
            await app.on_event(event)
    app.call_later(replay_steps)
    app.run() # blocking

def indent(text: str, spaces: int) -> str:
    return "\n".join(" " * spaces + line for line in text.splitlines())

def save_replay() -> None:
    assert app is not None, "app should be set by now"
    helpers_code = ""
    steps_code = ""
    for event, selector, index in steps:
        if isinstance(event, MouseDown):
            if index is None:
                steps_code += f"await pilot.click({selector!r}, offset=Offset({event.x}, {event.y}))\n"
            else:
                steps_code += f"widget = pilot.app.query({selector!r})[{index!r}]\n"
                # steps_code += f"await pilot.click(widget, offset=Offset({event.x}, {event.y}))\n" # would be nice
                steps_code += f"await pilot.click(offset=Offset({event.x}, {event.y}) + widget.region.offset)\n"


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
