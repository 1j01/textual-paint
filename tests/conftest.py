"""This file is loaded by pytest automatically. Fixtures defined here are available to all tests in the folder.

https://docs.pytest.org/en/7.1.x/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files
"""

from pathlib import Path
from typing import Generator

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

# This is needed on Windows but not Ubuntu/macOS?
# I hate python's import system with a burning passion.
import sys, os; sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../src/')))
from textual_paint.figlet_font_writer import FIGletFontWriter


@pytest.fixture(params=[
    {"theme": "light", "ascii_only": False},
    {"theme": "dark", "ascii_only": False},
    {"theme": "light", "ascii_only": True},
    {"theme": "dark", "ascii_only": True},
], ids=lambda param: f"{param['theme']}_{'ascii' if param['ascii_only'] else 'unicode'}")
def each_theme(request: pytest.FixtureRequest):
    """Fixture to test each combination of UI styles."""
    theme = request.param.get("theme")
    ascii_only = request.param.get("ascii_only")
    from textual_paint.args import args
    args.theme = theme
    args.ascii_only = ascii_only

    yield # run the test

    args.theme = "light"
    args.ascii_only = False

REPO_DIR_ABSOLUTE = Path(__file__).parent.parent.resolve()

@pytest.fixture
def my_fs(fs: FakeFilesystem) -> Generator[FakeFilesystem, None, None]:
    """Fixture to fake the filesystem, except for the repo directory."""

    # Without the repo dir, textual paint will fail to load FIGlet fonts or dialog icons.
    # Without the __snapshots__ dir, pytest-textual-snapshot will show "No history for this test" in the report.
    print("adding real directory", REPO_DIR_ABSOLUTE)
    fs.add_real_directory(REPO_DIR_ABSOLUTE)

    # DirectoryTree stores a reference to Path for some reason, making my life more difficult.
    from textual.widgets._directory_tree import DirectoryTree
    orig_PATH = DirectoryTree.PATH
    DirectoryTree.PATH = Path

    # TODO: use proper(?) mocking or figure out how to get FigletFont to find the real font files.
    # This folder doesn't actually exist on my system, so it's not getting them from there.
    # from pyfiglet import SHARED_DIRECTORY
    # fs.add_real_directory(SHARED_DIRECTORY)

    # Don't fail trying to load the default font "standard", we don't need it!
    # `pkg_resources` doesn't seem to work with pyfakefs (or I don't know what directories I need to add)
    from pyfiglet import FigletFont
    def preloadFont(self: FigletFont, font: str):
        dumb_font = FIGletFontWriter(commentLines=["Stupid font for testing"])
        for ordinal in dumb_font.charOrder:
            dumb_font.figChars[ordinal] = "fallback font for testing"
        return dumb_font.createFigFileData()
    FigletFont.preloadFont = preloadFont
  
    # Add an extra file to show how a file looks in the EnhancedDirectoryTree widget.
    fs.create_file("/pyfakefs_added_file.txt", contents="pyfakefs ate ur FS")
    
    # Add files so both Users and home exist regardless of the OS.
    # And HOPEFULLY not other folders. I suppose if you clone the repo at the root,
    # you may see textual-paint in the file dialog snapshots, and if you clone it
    # anywhere that doesn't start with Users or home as the first part, that will show up too,
    # due to the real directory being added above.
    # Maybe I should fine a more fine-grained way to target the EnhancedDirectoryTree widget.
    fs.create_file("/Users/username/.bashrc", contents="")
    fs.create_file("/home/username/.bashrc", contents="")
    fs.create_file("/var/something.txt", contents="") # var shows on macOS
    fs.create_file("/tmp/something.txt", contents="") # tmp shows on Ubuntu and macOS
    fs.create_file("/media/something.txt", contents="") # in case you clone on an external drive
    # Roll with it...
    fs.create_file("/UsersHome/username/.bashrc", contents="")
    fs.create_file("/UsersNotAtHome/username/.bashrc", contents="")
    fs.create_file("/UsersWhoHaveLeftHomeForGood/username/.bashrc", contents="")
    fs.create_file("/homeWithNoUsers/.bashrc", contents="")

    yield fs

    # probably don't need to actually clean up, but whatever
    DirectoryTree.PATH = orig_PATH
