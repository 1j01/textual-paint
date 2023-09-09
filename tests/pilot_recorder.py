import re
from rich.text import Text
from textual.css.query import NoMatches, TooManyMatches
from textual.dom import DOMNode
from textual.events import Event, Key, MouseDown, MouseMove, MouseUp
from textual.screen import Screen
from textual_paint.paint import PaintApp

OUTPUT_FILE = "tests/test_paint_something.py"

steps: list[tuple[Event, str]] = []

def get_selector(target: DOMNode) -> str:
    """Return a selector that can be used to find the widget."""
    widget = target
    if widget.id:
        return f"#{widget.id}"
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
        raise Exception(f"Selector {selector!r} matches more than one widget ({app.query(selector).nodes!r})")
    except NoMatches:
        raise Exception(f"Selector {selector!r} didn't match the target widget ({target!r})")
    if query_result is not target:
        raise Exception(f"Selector {selector!r} matched a different widget than the target ({query_result!r} rather than {target!r})")

    return selector

original_on_event = PaintApp.on_event
async def on_event(self: PaintApp, event: Event) -> None:
    await original_on_event(self, event)
    if isinstance(event, (MouseDown, MouseMove, MouseUp)):
        widget, _ = self.get_widget_at(event.x, event.y)
        steps.append((event, get_selector(widget)))
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
        for event in steps:
            await app.on_event(event)
    app.call_later(replay_steps)
    app.run() # blocking

def indent(text: str, spaces: int) -> str:
    return re.sub(r"^", " " * spaces, text, flags=re.MULTILINE)

def save_replay() -> None:
    helpers_code = ""
    steps_code = ""
    for event, selector in steps:
        if isinstance(event, MouseDown):
            steps_code += f"await pilot.click({selector!r}, offset=Offset({event.x}, {event.y}))\n"

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

    assert snap_compare(PAINT, run_before=test_paint_something_steps, size=({app.size.width}, {app.size.height}))
"""
    with open(OUTPUT_FILE, "w") as f:
        f.write(script)
    # app.exit(None, Text(f"Saved replay to {OUTPUT_FILE}"))

if __name__ == "__main__":
    replay() # with no steps, this will just run the app, ready for recording
