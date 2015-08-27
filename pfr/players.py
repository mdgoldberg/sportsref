from pfr import PFR_BASE_URL

def getGamelogURL(playerID, year):
    """Returns gamelog URL for given player-season.

    :playerID: PFR player ID
    :year: year corresponding to season in player-season.
    :returns: URL for the gamelog of the player-season.
    """
    template = '{0}/players/{1[0]}/{1}/gamelog/{2}/'
    gamelogURL = template.format(PFR_BASE_URL, playerID, year)
    return gamelogURL
