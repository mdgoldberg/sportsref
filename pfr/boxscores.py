from bs4 import BeautifulSoup as _BeautifulSoup
import re as _re
import requests as _requests
from urlparse import urljoin as _urljoin

from pfr.players import getGamelogURL as _getGamelogURL

def getBoxScoreURLs(playerURL, year):
    """Get list of box score URLs for a given player-season.

    :playerURL: absolute or relative URL for player
    :year: year for corresponding season in player-season.
    :returns: ["relative_box_score_URL"]

    """
    gamelogURL = _getGamelogURL(playerURL, year)
    html = _requests.get(gamelogURL).text
    soup = _BeautifulSoup(html, 'lxml')
    bsURLs = [boxscore_a.get('href')
              for boxscore_a in 
              soup.select('table#stats a[href*="/boxscores/"]')
              if _re.match(r'^\d{4}\-\d{2}\-\d{2}$', boxscore_a.string)
              ]
    return bsURLs

