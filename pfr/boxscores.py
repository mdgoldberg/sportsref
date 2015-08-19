from bs4 import BeautifulSoup as _BeautifulSoup
import requests as _requests
from urlparse import urljoin as _urljoin

from pfr.players import getGamelogURL as _getGamelogURL

def PStoBoxScoreURLs(playerURL, year):
    gamelogURL = _getGamelogURL(playerURL, year)
    html = _requests.get(gamelogURL).text
    soup = _BeautifulSoup(html, 'lxml')
    bsURLs = [boxscore_a.get('href')
              for boxscore_a in 
              soup.select('table#stats a[href*="/boxscores/"]')]
    return bsURLs

