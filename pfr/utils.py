import os as _os
import requests as _requests
import time as _time

def getHTML(url):
    """Gets the HTML for the given URL using a GET request.

    Incorporates an exponential timeout.

    :url: the absolute URL of the desired page.
    :returns: a string of HTML.

    """
    K = 60*3 # K is length of next backoff (in seconds)
    html = None
    numTries = 0
    while not html and numTries < 10:
        numTries += 1
        try:
            html = _requests.get(url).text
        except _requests.ConnectionError as e:
            errnum = e.args[0].args[1].errno
            if errnum == 61:
                # Connection Refused
                if K >= 60:
                    print 'Waiting {} minutes...'.format(K/60.0)
                else:
                    print 'Waiting {} seconds...'.format(K)
                # sleep
                for _ in xrange(K):
                    _time.sleep(1)
                # backoff gets doubled, capped at 3 hours
                K *= 2
                K = min(K, 60*60*3)
            else:
                # Some other error code
                raise e
    _time.sleep(2)
    return html

def relURLToPlayerID(url):
    """Converts relative or absolute player URL to player ID.

    :returns: playerID associated with the given player URL.
    :rtype: str
    """
    playerID, _ = _os.path.splitext(_os.path.basename(url))
    return playerID

def parsePlayDetails(details):
    """
    
    :returns:
    """
    details = details.lower()
    
    ptype = 'pass' if 'pass' in details else 'rush'
    if ptype == 'pass':
        pass

    RUSH_OPTS = ['LE', 'LT', 'LG', 'M', 'RG', 'RT', 'RE']
    PASS_OPTS = ['SL', 'SM', 'SR', 'DL', 'DM', 'DR']


    return None
