import os
from urlparse import urljoin

from pfr import PFR_BASE_URL

def getGamelogURL(playerURL, year):
    """Returns gamelog URL for given player-season.

    :playerURL: either relative or absolute player URL.
    :year: year corresponding to season in player-season.
    :returns: URL for the gamelog of the player-season.
    """

    playerURL_base, playerURL_ext = os.path.splitext(playerURL)
    gamelogURL = urljoin(urljoin(PFR_BASE_URL, playerURL_base + '/'),
                         'gamelog/{}'.format(year)
                         )
    return gamelogURL
