"""Record interactions and save as an automated test."""

import os
from typing import Any, Callable
from textual.css.query import NoMatches, TooManyMatches
from textual.dom import DOMNode
from textual.errors import NoWidget
from textual.events import Event, Key, MouseDown, MouseMove, MouseUp
from textual.geometry import Offset
from textual.pilot import Pilot
from textual.screen import Screen
from textual_paint.paint import PaintApp

def unique_file(path: str) -> str:
    filename, extension = os.path.splitext(path)
    counter = 1

    while os.path.exists(path):
        path = f"{filename}_{counter}{extension}"
        counter += 1

    return path

def indent(text: str, spaces: int) -> str:
    return "\n".join(" " * spaces + line for line in text.splitlines())

async def async_exec(code: str, **kwargs: object) -> object:
    # This dict will be used for passing variables to the `exec`ed code
    # as well as retrieving the function defined by the code.
    scope = kwargs

    # Make an async function with the code and `exec` it
    exec(f"async def async_exec_code():\n{indent(code, 4)}", scope)

    # Get `async_exec_code` from the scope, call it and return the result
    return await scope['async_exec_code']()  # type: ignore

def get_selector(target: DOMNode) -> tuple[str, int|None]:
    """Return a selector that can be used to find the widget."""
    app = target.app
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
        # FIXME: I think this can fail due to a race condition,
        # when clicking a button that closes a dialog, removing the button from the DOM.
        # Maybe intercept events differently, like by overriding post_message?
        return selector, app.query(selector).nodes.index(target)  # type: ignore
        # smarter differentiators would be nice, like tooltip or text content,
        # but at least with indices, you'll know when you changed the tab order
    except NoMatches:
        raise Exception(f"Selector {selector!r} didn't match the target widget ({target!r})")
    if query_result is not target:
        raise Exception(f"Selector {selector!r} matched a different widget than the target ({query_result!r} rather than {target!r})")

    return selector, None

class PilotRecorder():
    def __init__(self) -> None:
        self.app: PaintApp | None = None
        self.steps: list[tuple[Event, Offset, str, int|None]] = []
        self.replaying: bool = False
        self.output_file = unique_file("tests/test_paint_something.py")
        self.next_after_exit: Callable[[], None] | None = None

        original_on_event = PaintApp.on_event
        recorder = self
        async def on_event(self: PaintApp, event: Event) -> None:
            await original_on_event(self, event)
            recorder.record_event(event)
        self.app_on_event = on_event
    
    def record_event(self, event: Event) -> None:
        assert self.app is not None, "app should be set if we're recording an event from it"
        if self.replaying:
            return
        # Handling any event means including it in the undo stack right now.
        # Don't want to undo a single mouse-move, especially when it doesn't do anything yet.
        # if isinstance(event, (MouseDown, MouseMove, MouseUp)):
        if isinstance(event, MouseDown):
            try:
                widget, _ = self.app.get_widget_at(*event.screen_offset)
            except NoWidget:
                return
            offset = event.screen_offset - widget.region.offset
            self.steps.append((event, offset, *get_selector(widget)))
            self.steps_changed()
        elif isinstance(event, Key):
            if event.key == "ctrl+z" and self.steps:
                self.steps.pop()
                self.steps_changed()
                self.run()  # restart the app to replay up to this point
            elif event.key == "ctrl+c":
                self.save_replay()
            else:
                self.steps.append((event, Offset(), "", None))
                self.steps_changed()

    def steps_changed(self) -> None:
        # Could implement a debug view of the steps, but just saving to the file is good enough for now.
        self.save_replay()

    async def replay_steps(self, pilot: Pilot[Any]) -> None:
        if not self.steps:
            return
        self.replaying = True
        await async_exec(self.get_replay_code(), pilot=pilot, Offset=Offset)
        self.replaying = False

    def run(self) -> None:
        def startup_and_replay() -> None:
            self.next_after_exit = None  # important to allowing you to exit; don't keep launching the app
            self.app = PaintApp()
            self.app.on_event = self.app_on_event.__get__(self.app)
            self.app.run(auto_pilot=self.replay_steps)
            # run is blocking, so this will happen after the app exits
            if self.next_after_exit:
                self.next_after_exit()
        if self.app is not None:
            # exit can't be awaited, because it stops the whole event loop (eventually)
            # but we need to wait for the event loop to stop before we can start a new app
            self.next_after_exit = startup_and_replay
            self.app.exit()
        else:
            startup_and_replay()

    def get_replay_code(self) -> str:
        steps_code = ""
        for event, offset, selector, index in self.steps:
            if isinstance(event, MouseDown):
                if index is None:
                    steps_code += f"await pilot.click({selector!r}, offset=Offset({offset.x}, {offset.y}))\n"
                else:
                    steps_code += f"widget = pilot.app.query({selector!r})[{index!r}]\n"
                    # can't pass a widget to pilot.click, only a selector, or None
                    steps_code += f"await pilot.click(offset=Offset({offset.x}, {offset.y}) + widget.region.offset)\n"
            elif isinstance(event, MouseMove):
                # TODO: generate code for drags (but not extraneous mouse movement)
                pass
            elif isinstance(event, MouseUp):
                pass
            elif isinstance(event, Key):
                steps_code += f"await pilot.press({event.key!r})\n"
            else:
                raise Exception(f"Unexpected event type {type(event)}")
        return steps_code or "pass"

    def save_replay(self) -> None:
        assert self.app is not None, "app should be set by now"

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
{indent(self.get_replay_code(), 8)}

    assert snap_compare(PAINT, run_before=test_paint_something_steps, terminal_size=({self.app.size.width}, {self.app.size.height}))
"""
        with open(self.output_file, "w") as f:
            f.write(script)

if __name__ == "__main__":
    recorder = PilotRecorder()
    recorder.run()
