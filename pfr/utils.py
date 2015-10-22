import os
import re
import sys
import time

import lxml
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq
import requests

import decorators

__all__ = [
    'getHTML',
    'relURLToID',
    'parseTable',
    'parsePlayDetails',
]

@decorators.cacheHTML
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
                # backoff gets doubled, capped at 1 hour
                K *= 2
                K = min(K, 60*60)
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
    playerRegex = re.compile(r'/players/[A-Z]/(.+?)\.html?')
    boxscoresRegex = re.compile(r'/boxscores/(.+?)\.html?')
    teamRegex = re.compile(r'/teams/(\w{3})/.*')
    yearRegex = re.compile(r'/years/(\d{4})/')
    coachRegex = re.compile(r'/coaches/(.+?)\.html?')

    regexes = [
        playerRegex,
        boxscoresRegex,
        teamRegex,
        yearRegex,
        coachRegex,
    ]

    for regex in regexes:
        match = regex.match(url)
        if match:
            return match.group(1)

    print 'WARNING. WARNING. NO MATCH WAS FOUND FOR {}'.format(url)
    return ''


def parseTable(table):
    """Parses a table from PFR into a pandas dataframe.

    :table: the PyQuery, HtmlElement, or raw HTML of the table
    :returns: Pandas dataframe
    """
    if isinstance(table, pq):
        pass
    elif isinstance(table, lxml.html.HtmlElement):
        table = pq(table.text_content())
    elif isinstance(table, basestring):
        table = pq(table)
    else:
        raise 'UNKNOWN TYPE PASSED TO parseTable'

    # get columns and over-headers (if they exist)
    columns = [c.attrib['data-stat']
               for c in table('thead tr[class=""] th[data-stat]')]
    
    # get data
    data = [
        [_flattenLinks(td) for td in row('td')]
        for row in map(pq, table('tbody tr'))
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype='float')
    
    # small fixes to DataFrame
    # ignore * and + after the year
    if 'year_id' in df.columns:
        df.year_id = df.year_id.apply(
            lambda y: int(y[:4]) if isinstance(y, basestring) else y
        )
    
    return df
    

def parsePlayDetails(details):
    """Parses play details from play-by-play and returns structured data.
    
    Currently only handles passes and rushes.

    :returns: dictionary of play attributes
    """
    
    RUSH_OPTS = {
        'left end': 'LE', 'left tackle': 'LT', 'left guard': 'LG',
        'up the middle': 'M', 'middle': 'M',
        'right end': 'RE', 'right tackle': 'RT', 'right guard': 'RG',
    }
    PASS_OPTS = {
        'short left': 'SL', 'short middle': 'SM', 'short right': 'SR',
        'deep left': 'DL', 'deep middle': 'DM', 'deep right': 'DR',
    }

    rushOptRE = r'(?P<rushDir>{})'.format(
        r'|'.join(RUSH_OPTS.iterkeys())
    )
    passOptRE = r'(?P<passLoc>{})'.format(
        r'|'.join(PASS_OPTS.iterkeys())
    )

    playerRE = r"\S{6}\d{2}"

    # create rushing regex
    rusherRE = r"(?P<rusher>{0})".format(playerRE)
    rushOptRE = r"(?: {})?".format(rushOptRE)
    yardsRE = r"(?:(?:(?P<yds>\-?\d+) yards?)|(?:no gain))"
    # cases after this: tackle, fumble, td, penalty
    tackleRE = (r"(?: \(tackle by (?P<tackler1>{0})"
                r"(?: and (?P<tackler2>{0}))?\))?"
                .format(playerRE))
    fumbleRE = (r"(?:"
                r"\. (?P<fumbler>{0}) fumbles"
                r"(?: \(forced by (?P<forcer>{0})\))?"
                r"(?:, recovered by (?P<recoverer>{0}) at )?"
                r"(?:, ball out of bounds at )?"
                r"(?:(?P<fumbRecFieldside>\w*)\-(?P<fumbRecYdLine>\-?\d*))?"
                r"(?: and returned for (?P<fumbRetYds>\-?\d*) yards)?"
                r")?"
                .format(playerRE))
    tdRE = r"(?P<isTD>, touchdown)?"
    penaltyRE = (r"(?:.*?"
                 r"\. Penalty on (?P<penOn>{0}): "
                 r"(?P<penalty>[^\(,]+)"
                 r"(?: \((?P<penDeclined>Declined)\)|"
                 r", (?P<penYds>\d*) yards?)"
                 r")?"
                 .format(playerRE))

    rushREstr = (
        r"{}{} for {}{}{}{}{}"
    ).format(rusherRE, rushOptRE, yardsRE, tackleRE, fumbleRE, tdRE, penaltyRE)
    rushRE = re.compile(rushREstr, re.IGNORECASE)

    # create passing regex
    passerRE = r"(?P<passer>{0})".format(playerRE)
    sackRE = (r"sacked by (?P<sacker1>{0})(?: and (?P<sacker2>{0}))? "
              r"for (?P<sackYds>\-?\d+) yards?"
              .format(playerRE))
    completeRE = r"pass (?P<isComplete>(?:in)?complete)"
    passOptRE = r"(?: {})?".format(passOptRE)
    targetedRE = r"(?: (?:to|intended for)? (?P<target>{0}))?".format(playerRE)
    yardsRE = r"(?: for (?:(?P<recYds>\-?\d+) yards?|no gain))?"
    throwRE = r'{}{}{}{}{}'.format(
        completeRE, passOptRE, targetedRE, yardsRE, tackleRE
    )
    
    passREstr = (
        r"{} (?:{}|{}){}{}{}"
    ).format(passerRE, sackRE, throwRE, fumbleRE, tdRE, penaltyRE)
    passRE = re.compile(passREstr, re.IGNORECASE)

    # try rushing
    match = rushRE.match(details)
    # if it was a run...
    if match:
        # parse as a run
        struct = match.groupdict()
        struct['isRun'] = True
        struct['isPass'] = False
        # change type to int when applicable
        for k in ('yds', 'fumbRecYdLine', 'fumbRetYds', 'penYds'):
            struct[k] = int(struct[k]) if struct[k] else 0
        # change type to bool when applicable
        struct['isTD'] = bool(struct['isTD'])
        struct['penDeclined'] = bool(struct['penDeclined'])
        # convert rush type
        struct['rushDir'] = RUSH_OPTS.get(struct['rushDir'], None)
        return struct
    # otherwise, try parsing as a pass
    else:
        match = passRE.match(details)
        # if that didn't work, return None
        if not match: return None

        # parse as a pass
        struct = match.groupdict()
        struct['isPass'] = True
        struct['isRun'] = False
        # change type to int when applicable
        for k in ('recYds','fumbRecYdLine','fumbRetYds','penYds','sackYds'):
            struct[k] = int(struct[k]) if struct[k] else 0
        # change type to bool when applicable
        struct['isTD'] = bool(struct['isTD'])
        struct['penDeclined'] = bool(struct['penDeclined'])
        struct['isComplete'] = struct['isComplete'] == 'complete'
        # convert pass type
        struct['passLoc'] = PASS_OPTS.get(struct['passLoc'], None)
        return struct

def _flattenLinks(td):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PQ object, HtmlElement, or string of raw HTML to convert
    :returns: the string with the links flattened to IDs

    """
    # ensure it's a PyQuery object
    if isinstance(td, basestring) or isinstance(td, lxml.html.HtmlElement):
        td = pq(td)

    # if there's no text, just return np.nan
    if not td.text():
        return np.nan

    def _flattenC(c):
        if isinstance(c, basestring):
            return c
        elif 'href' in c.attrib:
            cID = relURLToID(c.attrib['href'])
            return cID if cID else pq(c).text()
        else:
            return pq(c).text()

    return ''.join(_flattenC(c) for c in td.contents())
