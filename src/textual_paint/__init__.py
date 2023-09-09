"""MS Paint for the terminal, built with Textual."""

__author__ = "Isaiah Odhner"
__copyright__ = "Copyright Isaiah Odhner"
__credits__ = ["Isaiah Odhner"]
__maintainer__ = "Isaiah Odhner"
__email__ = "isaiahodhner@gmail.com"
__version__ = "0.2.0"
__license__ = "MIT"

# Set version string when in a git repository
# to distinguish production from development versions.

from os.path import dirname, exists
from subprocess import check_output

DEVELOPMENT = exists(dirname(__file__) + "/../../.git")
"""Whether running from a Git repository."""

import sys

PYTEST = "pytest" in sys.modules
"""Whether running from pytest."""

if DEVELOPMENT:
    __version__ = "development " + check_output(["git", "describe", "--tags"], cwd=dirname(__file__)).strip().decode()

if PYTEST:
    # Avoid version string in About Paint dialog affecting snapshots.
    __version__ = "snapshot test edition :)"
