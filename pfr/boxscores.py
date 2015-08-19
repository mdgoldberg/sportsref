from bs4 import BeautifulSoup
import requests
from urlparse import urljoin

from pfr.players import getGamelogURL

def getBoxScoreURLs(playerURL, year):
    """Get list of box score URLs for a given player-season.

    :playerURL: absolute or relative URL for player
    :year: year for corresponding season in player-season.
    :returns: ["relative_box_score_URL"]

    """
    gamelogURL = getGamelogURL(playerURL, year)
    html = requests.get(gamelogURL).text
    soup = BeautifulSoup(html, 'lxml')
    bsURLs = [boxscore_a.get('href')
              for boxscore_a in 
              soup.select('table#stats a[href*="/boxscores/"]')]
    return bsURLs

