# flake8: noqa

SITE_ABBREV = {
    "http://www.pro-football-reference.com": "pfr",
    "http://www.basketball-reference.com": "bkref",
    "http://www.sports-reference.com/cfb": "ncaaf",
    "http://www.sports-reference.com/cbb": "ncaab",
}

from sportsref.options import get_option, set_option
from sportsref import decorators, utils, nfl, nba

__all__ = [
    "decorators",
    "utils",
    "nfl",
    "nba",
    "get_option",
    "set_option",
    "SITE_ABBREV",
]
