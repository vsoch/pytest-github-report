__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2022, Vanessa Sochat"
__license__ = "MPL 2.0"

__version__ = "0.0.1"
AUTHOR = "Vanessa Sochat"
NAME = "pw-github-report"
PACKAGE_URL = "https://github.com/PlanetWatchers/pw-github-report"
KEYWORDS = "github, report, markdown, CI"
DESCRIPTION = "Generate a GitHub report using pytest in GitHub Workflows"
LICENSE = "LICENSE"

################################################################################
# Global requirements

INSTALL_REQUIRES = (
    ("pytest", {"min_version": None}),
    ("pytablewriter", {"min_version": None}),
)
INSTALL_REQUIRES_ALL = INSTALL_REQUIRES
