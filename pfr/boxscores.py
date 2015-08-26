from bs4 import BeautifulSoup
import re
import requests
from urlparse import urljoin

from pfr.players import getGamelogURL
from pfr.utils import getHTML

dateRegex = re.compile(r'^\d{4}\-\d{2}\-\d{2}$')

def getBoxScoreURLs(playerURL, year):
    """Get list of box score URLs for a given player-season.

    :playerURL: absolute or relative URL for player
    :year: year for corresponding season in player-season.
    :returns: ["relative_box_score_URL"]

    """
    gamelogURL = getGamelogURL(playerURL, year)
    html = getHTML(gamelogURL)
    soup = BeautifulSoup(html, 'lxml')
    bsURLs = [boxscore_a.get('href')
              for boxscore_a in 
              soup.select('table#stats a[href*="/boxscores/"]')
              if re.match(dateRegex, boxscore_a.string)
              ]
    return bsURLs

