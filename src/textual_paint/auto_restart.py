"""Automatically restarts the program when a file is changed."""

from __future__ import annotations

from typing import TYPE_CHECKING
import os
import sys
from textual.app import ScreenStackError

if TYPE_CHECKING:
    from .paint import PaintApp

def restart_program():
    """Restarts the current program, after resetting terminal state, and cleaning up file objects and descriptors."""

    try:
        _app.discard_backup()
    except Exception as e:
        print("Error discarding backup:", e)

    try:
        _app.exit()
        # It's meant to eventually call this, but we need it immediately (unless we delay with asyncio perhaps)
        # Otherwise the terminal will be left in a state where you can't (visibly) type anything
        # if you exit the app after reloading, since the new process will pick up the old terminal state.
        _app._driver.stop_application_mode()  # type: ignore
    except Exception as e:
        print("Error stopping application mode. The command line may not work as expected. The `reset` command should restore it on Linux.", e)

    try:
        try:
            if observer:
                observer.stop()
                observer.join(timeout=1)
                if observer.is_alive():
                    print("Timed out waiting for file change observer thread to stop.")
        except RuntimeError as e:
            # Ignore "cannot join current thread" error
            # join() might be redundant, but I'm keeping it just in case something with threading changes in the future
            if str(e) != "cannot join current thread":
                raise
    except Exception as e:
        print("Error stopping file change observer:", e)

    try:
        import psutil
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            try:
                os.close(handler.fd)
            except Exception as e:
                print(f"Error closing file descriptor ({handler.fd}):", e)
    except Exception as e:
        print("Error closing file descriptors:", e)

    # python = sys.executable
    # os.execl(python, python, *sys.argv)
    os.execl(sys.executable, *sys.orig_argv)

def restart_on_changes(app: PaintApp):
    """Restarts the current program when a file is changed"""
    
    from watchdog.events import PatternMatchingEventHandler, FileSystemEvent, EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED
    from watchdog.observers import Observer

    class RestartHandler(PatternMatchingEventHandler):
        """A handler for file changes"""
        def on_any_event(self, event: FileSystemEvent):
            if event.event_type in (EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED):
                # These seem like they'd just cause trouble... they're not changes, are they?
                return
            print("Reloading due to FS change:", event.event_type, event.src_path)
            try:
                _app.screen.styles.background = "red"
            except ScreenStackError:
                pass
            # The unsaved changes prompt seems to need call_from_thread,
            # or else it gets "no running event loop",
            # whereas restart_program() (inside or outside action_reload) needs to NOT use it,
            # or else nothing happens.
            # However, when _app.action_reload is called from the key binding,
            # it seems to work fine with or without unsaved changes.
            if _app.is_document_modified():
                _app.call_from_thread(_app.action_reload)
            else:
                restart_program()
            try:
                _app.screen.styles.background = "yellow"
            except ScreenStackError:
                pass

    global observer, _app
    _app = app
    observer = Observer()
    handler = RestartHandler(
        # Don't need to restart on changes to .css, since Textual will reload them in --dev mode
        # Could include localization files, but I'm not actively localizing this app at this point.
        # WET: WatchDog doesn't match zero directories for **, so we have to split up any patterns that use it.
        patterns=[
            "**/*.py", "*.py"
        ],
        ignore_patterns=[
            ".history/**/*", ".history/*",
            ".vscode/**/*", ".vscode/*",
            ".git/**/*", ".git/*",
            "node_modules/**/*", "node_modules/*",
            "__pycache__/**/*", "__pycache__/*",
            "venv/**/*", "venv/*",
        ],
        ignore_directories=True,
    )
    observer.schedule(handler, path='.', recursive=True)
    observer.start()
