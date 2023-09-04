"""MS Paint for the terminal, built with Textual."""

__author__ = "Isaiah Odhner"
__copyright__ = "Copyright Isaiah Odhner"
__credits__ = ["Isaiah Odhner"]
__maintainer__ = "Isaiah Odhner"
__email__ = "isaiahodhner@gmail.com"
__version__ = "0.1.0"
__license__ = "MIT"

# Set version string when in a git repository
# to distinguish production from development versions.
from os.path import exists, dirname
from subprocess import check_output
if exists(dirname(__file__) + "/../../.git"):
    __version__ = "development " + check_output(["git", "describe", "--tags"], cwd=dirname(__file__)).strip().decode()
