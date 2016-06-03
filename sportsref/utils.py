import re
import time

import pandas as pd
from pyquery import PyQuery as pq
import requests

import sportsref

@sportsref.decorators.memoized
@sportsref.decorators.cacheHTML
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

def parseTable(table):
    """Parses a table from SR into a pandas dataframe.

    :table: the PyQuery object representing the HTML table
    :returns: Pandas dataframe
    """
    if not len(table):
        return pd.DataFrame()
    # get columns
    columns = [c.attrib['data-stat']
               for c in table('thead tr[class=""] th[data-stat]')]

    # get data
    rows = list(table('tbody tr')
                .not_('.thead, .stat_total, .stat_average')
                .items())
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

    # year_id -> year (as int)
    if 'year_id' in df.columns:
        df.rename(columns={'year_id': 'year'}, inplace=True)
        df.year = df.year.fillna(method='ffill')
        if df.year.dtype == basestring:
            df.year = df.year.map(lambda s: s[:4]).astype(int)
        else:
            df.year = df.year.astype(int)

    # game_date -> bsID
    if 'game_date' in df.columns:
        df.rename(columns={'game_date': 'bsID'}, inplace=True)

    # ignore *,+, and other characters used to note things
    df.replace(re.compile(ur'[\*\+\u2605)]', re.U), '', inplace=True)

    return df

def flattenLinks(td):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PyQuery object for the HTML to convert
    :returns: the string with the links flattened to IDs

    """

    # helper function to flatten individual strings/links
    def _flattenC(c):
        if isinstance(c, basestring):
            return c
        elif 'href' in c.attrib:
            cID = relURLToID(c.attrib['href'])
            return cID if cID else c.text_content()
        else:
            return c.text_content()

    # if there's no text, just return None
    if not td.text():
        return None

    return ''.join(_flattenC(c) for c in td.contents())

@sportsref.decorators.memoized
def relURLToID(url):
    """Converts a relative URL to a unique ID.

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

    :returns: ID associated with the given relative URL.
    """
    yearRegex = r'.*/years/(\d{4}).*|.*/gamelog/(\d{4}).*'
    playerRegex = r'.*/players/(?:\w/)?(.+?)(?:/|\.html?)'
    boxscoresRegex = r'/boxscores/(.+?)\.html?'
    teamRegex = r'/teams/(\w{3})/.*'
    coachRegex = r'/coaches/(.+?)\.html?'
    stadiumRegex = r'/stadiums/(.+?)\.html?'
    refRegex = r'/officials/(.+?r)\.html?'
    collegeRegex = r'.*/schools/(\S+?)/.*'
    hsRegex = r'/schools/high_schools\.cgi\?id=([^\&]{8})'
    bsDateRegex = r'/boxscores/index\.cgi\?(month=\d+&day=\d+&year=\d+)'

    regexes = [
        yearRegex,
        playerRegex,
        boxscoresRegex,
        teamRegex,
        coachRegex,
        stadiumRegex,
        refRegex,
        collegeRegex,
        hsRegex,
        bsDateRegex,
    ]

    for regex in regexes:
        match = re.match(regex, url, re.I)
        if match:
            return match.group(1)

    print 'WARNING. NO MATCH WAS FOUND FOR "{}"'.format(url)
    return 'noIDer00'

