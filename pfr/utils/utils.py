import re
import time

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq
import requests
from scipy.stats import norm

import pfr

@pfr.decorators.memoized
@pfr.decorators.cacheHTML
def getHTML(url):
    """Gets the HTML for the given URL using a GET request.

    Incorporates an exponential timeout starting with 2 seconds.

    :url: the absolute URL of the desired page.
    :returns: a string of HTML.

    """
    K = 60*3 # K is length of next backoff (in seconds)
    TOTAL_TIME = 0.4 # num of secs we we wait between last request & return
    html = None
    numTries = 0
    while not html and numTries < 10:
        numTries += 1
        start = time.time()
        try:
            html = requests.get(url).content
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
    timeOnRequest = time.time() - start
    timeRemaining = int(1000*(TOTAL_TIME - timeOnRequest)) # in milliseconds
    for _ in xrange(timeRemaining):
        # wait one millisecond
        time.sleep(0.001)
    return html

@pfr.decorators.memoized
def relURLToID(url):
    """Converts relative PFR URL to ID.

    Here, 'ID' refers generally to the unique ID for a given 'type' that a
    given datum has. For example, 'BradTo00' is Tom Brady's player ID - this
    corresponds to his relative URL, '/players/B/BradTo00.htm'. Similarly,
    '201409070dal' refers to the boxscore of the SF @ DAL game on 09/07/14.

    Supported types:
    * player/...
    * boxscores/...
    * teams/...
    * years/...
    * coaches/...
    * officials/...
    * schools/...
    * schools/high_schools.cgi?id=...
    * http://sports-reference.com/... (no unique ID returned)

    :returns: ID associated with the given relative URL.
    """
    sportsReferenceRegex = re.compile(r'http://www\.sports-reference\.com/.*')
    if sportsReferenceRegex.search(url):
        print 'SPORTS-REFERENCE LINK: {}'.format(url)
        return url

    playerRegex = re.compile(r'/players/[A-Z]/(.+?)(?:/|\.html?)')
    boxscoresRegex = re.compile(r'/boxscores/(.+?)\.html?')
    teamRegex = re.compile(r'/teams/(\w{3})/.*')
    yearRegex = re.compile(r'/years/(\d{4})(?:_AFL)?/.*')
    coachRegex = re.compile(r'/coaches/(.+?)\.html?')
    stadiumRegex = re.compile(r'/stadiums/(.+?)\.html?')
    refRegex = re.compile(r'/officials/(.+?r)\.html?')
    collegeRegex = re.compile(r'/schools/(\S+?)/.*')
    hsRegex = re.compile(r'/schools/high_schools\.cgi\?id=([^\&]{8})')

    regexes = [
        playerRegex,
        boxscoresRegex,
        teamRegex,
        yearRegex,
        coachRegex,
        stadiumRegex,
        refRegex,
        collegeRegex,
        hsRegex,
    ]

    for regex in regexes:
        match = regex.search(url)
        if match:
            return match.group(1)

    print 'WARNING. NO MATCH WAS FOUND FOR "{}"'.format(url)
    return 'noIDer00'

def parseTable(table):
    """Parses a table from PFR into a pandas dataframe.

    :table: the PyQuery object representing the HTML table
    :returns: Pandas dataframe
    """
    if not len(table):
        return pd.DataFrame()
    # get columns
    columns = [c.attrib['data-stat']
               for c in table('thead tr[class=""] th[data-stat]')]
    
    # get data
    rows = list(table('tbody tr').not_('.thead, .stat_total').items())
    data = [
        [flattenLinks(td) for td in row.items('td')]
        for row in rows
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype='float')

    # add hasClass columns
    allClasses = set(
        cls
        for row in rows
        if row.attr['class']
        for cls in row.attr['class'].split()
    )
    for cls in allClasses:
        df['hasClass_' + cls] = [
            row.attr['class'] and
            cls in row.attr['class'].split()
            for row in rows
        ]
    
    # small fixes to DataFrame

    if 'year_id' in df.columns and 'league_id' in df.columns:
        df['year_id'] = df['league_id']
        del df['league_id']

    if 'year_id' in df.columns:
        df['year_id'] = df.year_id.fillna(method='ffill')
        df['year_id'] = df.year_id.astype(str).str[:4].astype(int)
        df.rename(columns={'year_id': 'year'}, inplace=True)

    # game_date -> bsID
    if 'game_date' in df.columns:
        df.rename(columns={'game_date': 'bsID'}, inplace=True)

    # ignore * and + to note things
    df.replace(re.compile(r'[\*\+]'), '', inplace=True)

    return df

def _flattenC(c):
    if isinstance(c, basestring):
        return c
    elif 'href' in c.attrib:
        cID = relURLToID(c.attrib['href'])
        return cID if cID else c.text_content()
    else:
        return c.text_content()

def flattenLinks(td):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PyQuery object for the HTML to convert
    :returns: the string with the links flattened to IDs

    """
    # if there's no text, just return None
    if not td.text():
        return None

    return ''.join(_flattenC(c) for c in td.contents())

def initialWinProb(line):
    """Gets the initial win probability of a game given its Vegas line.

    :line: The Vegas line from the home team's perspective (negative means
    home team is favored).
    :returns: A float in [0., 100.] that represents the win probability.
    """
    line = float(line)
    probWin = 1. - norm.cdf(0.5, -line, 13.86)
    probTie = norm.cdf(0.5, -line, 13.86) - norm.cdf(-0.5, -line, 13.86)
    return 100. * (probWin + 0.5 * probTie)

def winProb(line, margin, secsElapsed, expPts):
    line = float(line)
    margin = float(margin)
    expPts = float(expPts)
    baseMean = -line
    baseStd = 13.46
    expMargin = margin + expPts
    minRemain = 60. - secsElapsed / 60. + 0.00001
    adjMean = baseMean * (minRemain / 60.)
    adjStd = baseStd / np.sqrt(60. / minRemain)
    probWin = 1. - norm.cdf(-expMargin + 0.5, adjMean, adjStd)
    probTie = (norm.cdf(-expMargin + 0.5, adjMean, adjStd) -
               norm.cdf(-expMargin - 0.5, adjMean, adjStd))
    return 100. * (probWin + 0.5*probTie)
