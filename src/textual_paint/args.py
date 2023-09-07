"""Command line arguments for the app."""

import argparse
import os
import re
import sys

from textual_paint.__init__ import DEVELOPMENT, __version__

PYTEST = "pytest" in sys.modules

parser = argparse.ArgumentParser(description='Paint in the terminal.', usage='%(prog)s [options] [filename]', prog="textual-paint")
parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
parser.add_argument('--theme', default='light', help='Theme to use, either "light" or "dark"', choices=['light', 'dark'])
parser.add_argument('--language', default='en', help='Language to use', choices=['ar', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hu', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'pt-br', 'ru', 'sk', 'sl', 'sv', 'tr', 'zh', 'zh-simplified'])
parser.add_argument('--ascii-only-icons', action='store_true', help='Use only ASCII characters for tool icons, no emoji or other Unicode symbols')
parser.add_argument('--ascii-only', action='store_true', help='Use only ASCII characters for the entire UI, for use in older terminals. Implies --ascii-only-icons')
parser.add_argument('--backup-folder', default=None, metavar="FOLDER", help='Folder to save backups to. By default a backup is saved alongside the edited file.')

# TODO: hide development options from help? there's quite a few of them now
dev_options = parser.add_argument_group('development options')
dev_options.add_argument('--inspect-layout', action='store_true', help='Enables DOM inspector (F12) and middle click highlight')
# This flag is important for my sanity during development,
# because it's very confusing to see an error message from the previous run,
# when a problem is actually solved.
# There are enough ACTUAL "that should have worked!!" moments to deal with.
# I really don't want false ones mixed in. You want to reward your brain for finding good solutions, after all.
dev_options.add_argument('--clear-screen', action='store_true', help='Clear the screen before starting, to avoid seeing outdated errors')
dev_options.add_argument('--restart-on-changes', action='store_true', help='Restart the app when the source code is changed')
dev_options.add_argument('--recode-samples', action='store_true', help='Open and save each file in samples/, for testing')

parser.add_argument('filename', nargs='?', default=None, help='Path to a file to open. File will be created if it doesn\'t exist.')

def update_cli_help_on_readme():
    """Update the readme with the current CLI usage info"""
    readme_help_start = re.compile(r"```\n.*--help\n")
    readme_help_end = re.compile(r"```")
    readme_file_path = os.path.join(os.path.dirname(__file__), "../../README.md")
    with open(readme_file_path, "r+", encoding="utf-8") as f:
        # By default, argparse uses the terminal width for formatting help text,
        # even when using format_help() to get a string.
        # The only way to override that is to override the formatter_class.
        # This is hacky, but it seems like the simplest way to fix the width
        # without creating a separate ArgumentParser, and without breaking the wrapping for --help.
        # This lambda works because python uses the same syntax for construction and function calls,
        # so formatter_class doesn't need to be an actual class.
        # See: https://stackoverflow.com/questions/44333577/explain-lambda-argparse-helpformatterprog-width
        width = 80
        old_formatter_class = parser.formatter_class
        parser.formatter_class = lambda prog: argparse.HelpFormatter(prog, width=width)
        help_text = parser.format_help()
        parser.formatter_class = old_formatter_class

        md = f.read()
        start_match = readme_help_start.search(md)
        if start_match is None:
            raise Exception("Couldn't find help section in readme")
        start = start_match.end()
        end_match = readme_help_end.search(md, start)
        if end_match is None:
            raise Exception("Couldn't find end of help section in readme")
        end = end_match.start()
        md = md[:start] + help_text + md[end:]
        f.seek(0)
        f.write(md)
        f.truncate()

if DEVELOPMENT:
    # A pre-commit hook might technically be best for this,
    # but I doubt it's worth the complexity.
    # I'm usually running with --restart-on-changes anyways,
    # while working on the project.
    update_cli_help_on_readme()

args = parser.parse_args([]) if PYTEST else parser.parse_args()
"""Parsed command line arguments."""

def get_help_text() -> str:
    """Get the help text for the command line arguments."""
    return parser.format_help()

__all__ = ["args", "get_help_text"]
