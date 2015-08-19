import os as _os
from urlparse import urljoin as _urljoin

from pfr import PFR_BASE_URL as _PFR_BASE_URL

def getGamelogURL(playerURL, year):
    """Returns gamelog URL for given player-season.

    :playerURL: either relative or absolute player URL.
    :year: year corresponding to season in player-season.
    :returns: URL for the gamelog of the player-season.

    """

    playerURL_base, playerURL_ext = _os.path.splitext(playerURL)
    gamelogURL = _urljoin(_urljoin(_PFR_BASE_URL, playerURL_base + '/'),
                          'gamelog/{}'.format(year)
                          )
    return gamelogURL
