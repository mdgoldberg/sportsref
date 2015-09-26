import re
from urlparse import urljoin

import requests
from pyquery import PyQuery as pq

from pfr import players, utils

__all__ = [
    'getBoxScoreURLs',
]

dateRegex = re.compile(r'^\d{4}\-\d{2}\-\d{2}$')

def getBoxScoreURLs(playerID, year):
    """Get list of box score URLs for a given player-season.

    :playerID: PFR player ID
    :year: year for corresponding season in player-season.
    :returns: list of relative box score URLs
    :rtype: [string]

    """
    gamelogURL = players.getGamelogURL(playerID, year)
    html = utils.getHTML(gamelogURL)
    doc = pq(html)
    bsURLs = [boxscore_a.attrib['href']
              for boxscore_a in 
              doc('table#stats a[href*="/boxscores/"]')
              if re.match(dateRegex, boxscore_a.text)
              ]
    return bsURLs
