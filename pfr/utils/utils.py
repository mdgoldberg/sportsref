import re
import time

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq
import requests

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
    html = None
    numTries = 0
    while not html and numTries < 10:
        numTries += 1
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
    time.sleep(1.5)
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

    :returns: ID associated with the given relative URL.
    """
    playerRegex = re.compile(r'/players/[A-Z]/(.+?)(?:/|\.html?)')
    boxscoresRegex = re.compile(r'/boxscores/(.+?)\.html?')
    teamRegex = re.compile(r'/teams/(\w{3})/.*')
    yearRegex = re.compile(r'/years/(\d{4})/')
    coachRegex = re.compile(r'/coaches/(.+?)\.html?')
    stadiumRegex = re.compile(r'/stadiums/(.+?)\.html?')
    refRegex = re.compile(r'/officials/(.+?r)\.html?')

    regexes = [
        playerRegex,
        boxscoresRegex,
        teamRegex,
        yearRegex,
        coachRegex,
        stadiumRegex,
        refRegex,
    ]

    for regex in regexes:
        match = regex.match(url)
        if match:
            return match.group(1)

    print 'WARNING. NO MATCH WAS FOUND FOR {}'.format(url)
    return 'noIDer00'

def parseTable(table):
    """Parses a table from PFR into a pandas dataframe.

    :table: the PyQuery, HtmlElement, or raw HTML of the table
    :returns: Pandas dataframe
    """
    if not isinstance(table, pq):
        table = pq(table)

    # get columns
    columns = [c.attrib['data-stat']
               for c in table('thead tr[class=""] th[data-stat]')]
    
    # get data
    rows = table('tbody tr').not_('.thead')
    data = [
        [flattenLinks(td) for td in row.items('td')]
        for row in rows.items()
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype='float')

    # add hasClass columns
    allClasses = set(
        cls
        for row in rows.items()
        for cls in row.attr['class'].split()
    )
    for cls in allClasses:
        df.loc[:, 'hasClass_' + cls] = [
            cls in row.attr['class'].split()
            for row in rows.items()
        ]
    
    # small fixes to DataFrame

    # team_index table (and others?) fix
    if 'year_id' in df.columns and 'league_id' in df.columns:
        df['year_id'] = df['league_id']
        del df['league_id']

    if 'year_id' in df.columns:
        df = df.query('year_id != "AFL"')
        df.loc[:, 'year_id'] = df.year_id.fillna(method='ffill')
        df.loc[:, 'year_id'] = df.year_id.apply(lambda y: int(str(y)[:4]))

    # game_date -> bsID
    if 'game_date' in df.columns:
        df = df.rename(columns={'game_date': 'bsID'})

    # ignore * and + to note things
    df.replace(re.compile(r'[\*\+]'), '', inplace=True)

    return df

def flattenLinks(td):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PQ object, HtmlElement, or string of raw HTML to convert
    :returns: the string with the links flattened to IDs

    """
    # ensure it's a PyQuery object
    if not isinstance(td, pq):
        td = pq(td)

    # if there's no text, just return None
    if not td.text():
        return None

    def _flattenC(c):
        if isinstance(c, basestring):
            return c
        elif 'href' in c.attrib:
            cID = relURLToID(c.attrib['href'])
            return cID if cID else c.text_content()
        else:
            return c.text_content()

    return ''.join(_flattenC(c) for c in td.contents())
