"""Record interactions and save as an automated test.

TODO:
- Handle right clicks, middle clicks, and modifier keys.
- Handle mouse wheel events.
- Handle paste events.
- Ignore clicks on the #pilot-recorder-steps widget.
- Add a way to toggle the steps view.
- Try adding a delay before reloading so you can undo multiple steps at once.
- Auto-save to a WIP test file.
- Ideally the supporting functions like drag() should be part of Pilot.
- Ideally SnapCompareType should be part of pytest-textual-snapshot.

FIXME:
- Clicks on the wrong thing sometimes
- Steps view doesn't update sometimes
"""

import os
from typing import Any, Callable

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App
from textual.css.query import NoMatches, TooManyMatches
from textual.dom import DOMNode
from textual.errors import NoWidget
from textual.events import Event, Key, MouseDown, MouseMove, MouseUp
from textual.geometry import Offset
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Static


def unique_file(path: str) -> str:
    """Return a path that doesn't exist yet, by appending a number to the filename."""
    filename, extension = os.path.splitext(path)
    counter = 1

    while os.path.exists(path):
        path = f"{filename}_{counter}{extension}"
        counter += 1

    return path

def indent(text: str, spaces: int) -> str:
    """Return the text indented by the given number of spaces (including the first line)."""
    return "\n".join(" " * spaces + line for line in text.splitlines())

async def async_exec(code: str, **kwargs: object) -> object:
    """Execute the given code in an async function and return the result. Keyword arguments are made available as variables."""
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
        return selector, app.query(selector).nodes.index(target)  # type: ignore
        # smarter differentiators would be nice, like tooltip or text content,
        # but at least with indices, you'll know when you changed the tab order
    except NoMatches:
        raise Exception(f"Selector {selector!r} didn't match the target widget ({target!r})")
    if query_result is not target:
        raise Exception(f"Selector {selector!r} matched a different widget than the target ({query_result!r} rather than {target!r})")

    return selector, None

original_on_event = App.on_event  # type: ignore

class PilotRecorder():
    """Record (and undo and replay) interactions with an app, and save as a test."""
    def __init__(self, app_class: Callable[[], App[Any]], app_path: str, output_file: str | None = None) -> None:
        """Initialize the test recorder.
        
        app_class: A function that returns an App instance.
        app_path: The path to the app's source code, relative to output_file.
        output_file: The path to save the test to.
        """
        self.app_path = app_path
        self.app_class = app_class
        self.output_file = output_file or unique_file("tests/test_playback.py")

        self.app: App[Any] | None = None
        self.steps: list[tuple[Event, Offset, str, int|None]] = []
        self.replaying: bool = False
        self.next_after_exit: Callable[[], None] | None = None

        self.steps_view = Static(id="pilot-recorder-steps")
        self.steps_view.styles.dock = "right"
        self.steps_view.styles.width = 40
        self.steps_view.styles.height = "100%"

        recorder = self
        async def on_event(self: App[Any], event: Event) -> None:
            # - Record before the event is handled, so a clicked widget that removes itself,
            #   such as an OK button in a dialog, will still be in the DOM when we record it.
            # - Every event seems to be received twice, once with _forwarded set and once without.
            #   I don't claim to understand the forwarding scheme, but ignoring either
            #   the forwarded or the un-forwarded events seems workable.
            if not event._forwarded:  # pyright: ignore[reportPrivateUsage]
                recorder.handle_event(event)
            await original_on_event(self, event)
        self.app_on_event = on_event

    def handle_event(self, event: Event) -> None:
        """Record the event as a step, or handle certain key presses as commands."""
        assert self.app is not None, "app should be set if we're recording an event from it"
        if isinstance(event, (MouseDown, MouseMove, MouseUp)):
            if self.replaying:
                return
            try:
                widget, _ = self.app.get_widget_at(*event.screen_offset)
            except NoWidget:
                return
            offset = event.screen_offset - widget.region.offset
            try:
                selector, index = get_selector(widget)
            except Exception as e:
                # e.g. Scrollbar can't be queried for
                # Currently this means you can't drag a scrollbar
                # in a test recording, but if you're not trying to,
                # this shouldn't be fatal.
                print(e)
                return
            self.steps.append((event, offset, selector, index))
            self.steps_changed()
        elif isinstance(event, Key):
            if event.key == "ctrl+z" and self.steps:
                while self.steps and isinstance(self.steps[-1][0], (MouseMove, MouseUp)):
                    self.steps.pop()
                self.steps.pop()
                while self.steps and isinstance(self.steps[-1][0], MouseMove):
                    self.steps.pop()

                self.steps_changed()
                self.run()  # restart the app to replay up to this point
            elif event.key == "ctrl+r":
                self.run()  # restart and replay
            elif event.key == "ctrl+c":
                self.save_replay()
                self.app.exit(None, message=Text("Saved test recording to " + self.output_file))
            else:
                if self.replaying:
                    return
                self.steps.append((event, Offset(), "", None))
                self.steps_changed()

    def steps_changed(self) -> None:
        """Update the steps view any time the steps change."""
        self.update_steps_view()

    def update_steps_view(self, highlight_lines: set[int] | None = None) -> None:
        assert self.app is not None, "app should be set when updating the steps view"
        if self.steps_view.parent != self.app.screen:
            self.app.screen.mount(self.steps_view)
        # self.steps_view.update("\n".join(
        #     (f"{step_index + 1}. {event!r}" + ("{offset!r}, {selector!r}, {index!r}" if isinstance(event, (MouseDown, MouseMove, MouseUp)) else ""))
        #     for step_index, (event, offset, selector, index) in enumerate(self.steps)
        # ))
        self.steps_view.update(Syntax(self.get_replay_code(), "python", line_numbers=True, highlight_lines=highlight_lines))

    def highlight_line(self, line_index: int) -> None:
        """Highlight the given line in the steps view."""
        self.update_steps_view({line_index + 1})

    async def replay_steps(self, pilot: Pilot[Any]) -> None:
        """Replay the recorded steps, in the current app instance."""
        if not self.steps:
            return
        await pilot._wait_for_screen(timeout=5.0)  # pyright: ignore[reportPrivateUsage]
        self.replaying = True
        replay_code = self.get_replay_code()
        # Fix import
        replay_code = replay_code.replace("from tests.pilot_helpers import", "from pilot_helpers import")
        # Instrument with highlight_line calls
        replay_code = "\n".join(line if "def " in line or len(line) == 0 or line[0] == " " else f"highlight_line({line_index}); {line}" for line_index, line in enumerate(replay_code.splitlines()))
        await async_exec(replay_code, pilot=pilot, Offset=Offset, highlight_line=self.highlight_line)
        self.replaying = False

    def run(self) -> None:
        """Start the app, or restart it to replay the recorded steps."""
        def startup_and_replay() -> None:
            """Start the app, hook its events, and replay steps if there are any."""
            self.next_after_exit = None  # important to allowing you to exit; don't keep launching the app
            self.app = self.app_class()
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
        """Return code to replay the recorded steps."""
        helpers: set[str] = set()
        steps_code = ""
        for step_index, (event, offset, selector, index) in enumerate(self.steps):
            # steps_code += f"# {event!r}, {offset!r}, {selector!r}, {index!r})\n"
            if isinstance(event, (MouseDown, MouseMove)):
                pass
            elif isinstance(event, MouseUp):
                # Detect drags
                # TODO: record Click events and don't trigger a drag if there's a Click after the MouseUp
                # or maybe just enable replaying a Click at the end of the drag sequence...
                # If you're drawing on a canvas, the Click doesn't matter,
                # but if you're clicking a button, the drag doesn't matter.
                # You probably never need both in the same test (maybe testing a text field's selection and focus?),
                # but it's impossible to know which is intended. (If it's a Button, 99%+ you want a Click, but there are many widgets.)
                # Maybe best is to include in a comment, "# Did you mean `await pilot.click(...)`?"
                # or more neutrally, "# Drag ended with Click event."
                # "# If you want just a click, use (...) and remove the drag helper if it's not needed."
                # "# If you want just a drag, remove click=True."
                if isinstance(self.steps[step_index - 1][0], MouseMove):
                    helpers.add("drag")
                    # find the last mouse down event
                    # TODO: make sure the offsets are all relative to
                    # the initial position of the widget that got MouseDown.
                    for previous_step_index in range(step_index - 1, -1, -1):
                        previous_event, _, _, _ = self.steps[previous_step_index]
                        if isinstance(previous_event, MouseDown):
                            break
                    else:
                        raise Exception(f"Mouse up event {step_index} has no matching mouse down event")
                    offsets = [step[1] for step in self.steps[previous_step_index:step_index + 1]]
                    steps_code += f"await drag(pilot, {selector!r}, [{', '.join(repr(offset) for offset in offsets)}])\n"
                    continue

                # Handle clicks
                if index is None:
                    steps_code += f"await pilot.click({selector!r}, offset=Offset({offset.x}, {offset.y}))\n"
                else:
                    # Strategy: click on the screen, offset by the widget's position.
                    # steps_code += f"widget = pilot.app.query({selector!r})[{index!r}]\n"
                    # # can't pass a widget to pilot.click, only a selector, or None
                    # steps_code += f"await pilot.click(offset=Offset({offset.x}, {offset.y}) + widget.region.offset)\n"
                    # Strategy: add a class to the widget, and click on that.
                    helpers.add("click_by_index")
                    steps_code += f"await click_by_index(pilot, {selector!r}, {index!r})\n"
            elif isinstance(event, Key):
                steps_code += f"await pilot.press({event.key!r})\n"
            else:
                raise Exception(f"Unexpected event type {type(event)}")
        helper_code = f"from tests.pilot_helpers import {', '.join(helpers)}\n\n" if helpers else ""
        return (helper_code + steps_code) or "pass"

    def get_test_code(self) -> str:
        """Return pytest code that uses the replay."""
        assert self.app is not None, "app should be set"
        return f"""\
from pathlib import Path, PurePath
from typing import Awaitable, Callable, Iterable, Protocol

import pytest
from textual.geometry import Offset
from textual.pilot import Pilot
from textual.widgets import Input

class SnapCompareType(Protocol):
    \"""Type of the function returned by the snap_compare fixture.\"""
    def __call__(
        self,
        app_path: str | PurePath,
        press: Iterable[str] = (),
        terminal_size: tuple[int, int] = (80, 24),
        run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,  # type: ignore
    ) -> bool:
        ...

# Relative paths are treated as relative to this file, when using snap_compare.
APP_PATH = Path({self.app_path!r})

# Prevent flaky tests due to timing issues.
Input.cursor_blink = False  # type: ignore

def test_playback(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
{indent(self.get_replay_code(), 8)}

    assert snap_compare(APP_PATH, run_before=automate_app, terminal_size=({self.app.size.width}, {self.app.size.height}))
"""

    def save_replay(self) -> None:
        """Save the pytest code."""
        assert self.app is not None, "app should be set by now"

        script = self.get_test_code()
        with open(self.output_file, "w") as f:
            f.write(script)

if __name__ == "__main__":
    from textual_paint.paint import PaintApp
    recorder = PilotRecorder(PaintApp, "../src/textual_paint/paint.py")
    recorder.run()
