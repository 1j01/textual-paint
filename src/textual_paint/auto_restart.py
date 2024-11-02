"""Automatically restarts the program when a file is changed."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from textual.app import ScreenStackError

if TYPE_CHECKING:
    from textual_paint.gallery import GalleryApp
    from textual_paint.paint import PaintApp

def restart_program() -> None:
    """Restarts the current program, after resetting terminal state, and cleaning up file objects and descriptors."""

    if hasattr(_app, "discard_backup"):
        try:
            _app.discard_backup()  # type: ignore
        except Exception as e:
            print("Error discarding backup:", e)

    try:
        _app.exit()
        # It's meant to eventually call this, but we need it immediately (unless we delay with asyncio perhaps)
        # Otherwise the terminal will be left in a state where you can't (visibly) type anything
        # if you exit the app after reloading, since the new process will pick up the old terminal state.
        _app._driver.stop_application_mode()  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]
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
        try:
            import psutil
        except ImportError:
            print("psutil module not available; skipping file descriptor cleanup for auto-restart.")
        else:
            p = psutil.Process(os.getpid())
            for handler in p.open_files() + p.connections():
                if handler.fd == -1:
                    # On Windows, this happens for kernel32.dll.mui, KernelBase.dll.mui, and about 4 sockets. Dunno man.
                    # print("Skipping invalid file descriptor (-1) for:", handler)
                    continue
                try:
                    os.close(handler.fd)
                except Exception as e:
                    print(f"Error closing file descriptor ({handler.fd}):", e)
    except Exception as e:
        print("Error closing file descriptors:", e)

    # python = sys.executable
    # os.execl(python, python, *sys.argv)
    # print(sys.executable, sys.orig_argv)
    if os.name == "nt":
        # On Windows, os.exec* bungles the arguments: https://github.com/python/cpython/issues/64650
        # This is a very bad and fragile workaround.
        # After several hours of my life wasted, it doesn't even work correctly. The reloaded process has some broken terminal state.
        # (Perhaps `App._driver` does not exist and the error is being swallowed? And/or there's a way to actually wait for the App to exit properly?)
        # Also this doesn't work when debugging in VS Code with debugpy. I mean it wouldn't be able to attach anyways, but this escaping itself breaks somehow.
        os.execl(sys.executable, *(f'"{arg.replace('"', '""')}"' if " " in arg else arg.replace('"', '""') for arg in sys.orig_argv))
    else:
        os.execl(sys.executable, *sys.orig_argv)

def restart_on_changes(app: PaintApp|GalleryApp) -> None:
    """Restarts the current program when a file is changed"""

    from watchdog.events import (EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED,
                                 FileSystemEvent, RegexMatchingEventHandler)
    from watchdog.observers import Observer

    # Why RegexMatchingEventHandler instead of PatternMatchingEventHandler?
    # Because watchdog doesn't match zero directories for `**` patterns, requiring writing everything twice,
    # and the ignore patterns weren't working at all on Windows.
    class RestartHandler(RegexMatchingEventHandler):
        """A handler for file changes"""
        def on_any_event(self, event: FileSystemEvent) -> None:
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
            if hasattr(app, "is_document_modified") and _app.is_document_modified():  # type: ignore
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
        # BTW: I have a VS Code launch configuration specifically for testing this.
        # NOTE: watchdog uses pattern.match() which matches from the beginning of a string
        # but it doesn't have to be a full match, so it's asymmetrical in how it treats the beginning and end.
        regexes=[
            r".*\.py$",
        ],
        ignore_regexes=[
            r".*(/|\\|^)\.[^/\\]", # dotfiles and dotfolders, e.g. .git, .vscode, .history, .venv, .env, .pytest_cache
            r".*(/|\\|^)node_modules(/|\\|$)",
            r".*(/|\\|^)__pycache__(/|\\|$)",
            r".*(/|\\|^)v?env(/|\\|$)", # just in case you don't use the folder name ".venv" recommended in the readme, and which the VS Code launch tasks are set up for
            # only matching *.py files, so we don't need to handle *.ans~ or *.py~
            # r".*~$", # backup files, as saved by Textual Paint (and some text editors)
        ],
        ignore_directories=True,
    )
    observer.schedule(handler, path='.', recursive=True)
    observer.start()
