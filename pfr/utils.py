import os
import re
import time

import numpy as np
import requests

__all__ = [
    'getHTML',
    'relURLToID',
    'parsePlayDetails',
]

def getHTML(url):
    """Gets the HTML for the given URL using a GET request.

    Incorporates an exponential timeout starting with 2 seconds.

    :url: the absolute URL of the desired page.
    :returns: a string of HTML.

    """
    K = 60*3 # K is length of next backoff (in seconds)
    html = None
    numTries = 0
    while not html and numTries < 10:
        numTries += 1
        try:
            html = requests.get(url).text
        except requests.ConnectionError as e:
            errnum = e.args[0].args[1].errno
            if errnum == 61:
                # Connection Refused
                if K >= 60:
                    print 'Waiting {} minutes...'.format(K/60.0)
                else:
                    print 'Waiting {} seconds...'.format(K)
                # sleep
                for _ in xrange(K):
                    time.sleep(1)
                # backoff gets doubled, capped at 3 hours
                K *= 2
                K = min(K, 60*60*3)
            else:
                # Some other error code
                raise e
    time.sleep(2)
    return html

def relURLToID(url):
    """Converts relative PFR URL to ID.

    Here, 'ID' refers generally to the unique ID for a given 'type' that a
    given datum has. For example, 'BradTo00' is Tom Brady's player ID - this
    corresponds to his relative URL, '/players/B/BradTo00.htm'. Similarly,
    '201409070dal' refers to the boxscore of the SF @ DAL game on 09/07/14.

    Supported types:
    * player/...
    * boxscores/...

    :returns: ID associated with the given relative URL.
    """
    playerRegex = re.compile(r'/players/[A-Z]/(.+?)\.html?', re.IGNORECASE)
    boxscoresRegex = re.compile(r'/boxscores/(.+?)\.html?', re.IGNORECASE)

    # check if player ID
    match = playerRegex.match(url)
    if match:
        return match.group(1)
    
    # check if boxscores ID
    match = boxscoresRegex.match(url)
    if match:
        return match.group(1)

    return None

def parsePlayDetails(details):
    """Parses play details from play-by-play and returns structured data.
    
    Currently only handles passes and rushes.

    :returns: dictionary of play attributes
    """
    
    RUSH_OPTS = {
        'left end': 'LE', 'left tackle': 'LT', 'left guard': 'LG',
        'up the middle': 'M',
        'right end': 'RE', 'right tackle': 'RT', 'right guard': 'RG',
        '': None
    }
    PASS_OPTS = {
        'short left': 'SL', 'short middle': 'SM', 'short right': 'SR',
        'deep left': 'DL', 'deep middle': 'DM', 'deep right': 'DR',
        '': None
    }

    # have to sort them to make sure it matches empty string last
    rushOptRE = r'(?P<rushDir>{})'.format(
        r'|'.join(sorted(RUSH_OPTS.iterkeys(), reverse=True))
    )
    passOptRE = r'(?P<passLoc>{})'.format(
        r'|'.join(sorted(PASS_OPTS.iterkeys(), reverse=True))
    )

    playerRE = r"(?P<rusher>\S{6}\d{2})"
    rushOptRE = r"(?: {})?".format(rushOptRE)
    yardsRE = r"(?:(?:(?P<yds>\-?\d+) yards?)|(?:no gain))"
    # cases after this: tackle, fumble, or nothing

    rushREstr = (
        r"{}{} for {}"
    ).format(playerRE, rushOptRE, yardsRE)
    print rushREstr
    rushRE = re.compile(rushREstr, re.IGNORECASE)
    return rushRE
    match = rushRE.match(details)
    return match


    # first, figure out play type
    if ' pass ' in details or ' sacked ' in details:
        ptype = 'pass'
    # below line not tested
    elif any([ro in details for ro in RUSH_OPTS.itervalues()]):
        ptype = 'rush'

    if ptype == 'pass':
        # analyze the pass
        pass

    elif ptype == 'rush':
        # analyze the rush
        pass


    return None
