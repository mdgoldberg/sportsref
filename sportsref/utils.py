import re
import time

import pandas as pd
from pyquery import PyQuery as pq
import requests

import sportsref


@sportsref.decorators.memoize
@sportsref.decorators.cache_html
def get_html(url):
    """Gets the HTML for the given URL using a GET request.

    Incorporates an exponential timeout starting with 2 seconds.

    :url: the absolute URL of the desired page.
    :returns: a string of HTML.

    """
    K = 60*3  # K is length of next backoff (in seconds)
    TOTAL_TIME = 0.4  # num of secs we we wait between last request & return
    html = None
    numTries = 0
    while not html and numTries < 10:
        numTries += 1
        start = time.time()
        try:
            response = requests.get(url)
            if 400 <= response.status_code < 500:
                raise ValueError(
                    "Invalid ID led to an error in fetching HTML")
            html = response.text
            html = html.replace('<!--', '').replace('-->', '')
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
    timeRemaining = int(1000 * (TOTAL_TIME - timeOnRequest))  # in milliseconds
    for _ in xrange(timeRemaining):
        # wait one millisecond
        time.sleep(0.001)
    return html


def parse_table(table, flatten=True):
    """Parses a table from SR into a pandas dataframe.

    :table: the PyQuery object representing the HTML table
    :flatten: if True, flattens relative URLs to IDs. otherwise, leaves as
    text.
    :returns: Pandas dataframe
    """
    if not len(table):
        return pd.DataFrame()

    # get columns
    columns = [c.attrib['data-stat']
               for c in table('thead tr:not([class]) th[data-stat]')]

    # get data
    rows = list(table('tbody tr')
                .not_('.thead, .stat_total, .stat_average')
                .items())
    data = [
        [flatten_links(td) if flatten else td.text()
         for td in row.items('th,td')]
        for row in rows
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype='float')

    # add has_class columns
    allClasses = set(
        cls
        for row in rows
        if row.attr['class']
        for cls in row.attr['class'].split()
    )
    for cls in allClasses:
        df['has_class_' + cls] = [
            bool(row.attr['class'] and
                 cls in row.attr['class'].split())
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

    # boxscore_word, game_date -> boxscore_id and separate into Y, M, D columns
    bs_id_col = None
    if 'boxscore_word' in df.columns:
        bs_id_col = 'boxscore_word'
    elif 'game_date' in df.columns:
        bs_id_col = 'game_date'
    if flatten and bs_id_col:
        df = df.loc[df[bs_id_col].notnull()]  # drop bye weeks
        df['year'] = df[bs_id_col].str[:4].astype(int)
        df['month'] = df[bs_id_col].str[4:6].astype(int)
        df['day'] = df[bs_id_col].str[6:8].astype(int)
        df.rename(columns={bs_id_col: 'boxscore_id'}, inplace=True)

    # ignore *,+, and other characters used to note things
    df.replace(re.compile(ur'[\*\+\u2605)]', re.U), '', inplace=True)
    for col in df.columns:
        if hasattr(df[col], 'str'):
            df.ix[:, col] = df.ix[:, col].str.strip()

    # player -> player_id
    if flatten and 'player' in df.columns:
        df.rename(columns={'player': 'player_id'}, inplace=True)

    # team_name -> team_id
    if flatten and 'team_name' in df.columns:
        df.rename(columns={'team_name': 'team_id'}, inplace=True)

    # get rid of faulty rows
    if 'team_id' in df.columns:
        df = df.ix[~df['team_id'].isin(['XXX'])]

    # season -> int
    if 'season' in df.columns:
        df['season'] = df['season'].astype(int)

    # (number%) -> float(number * 0.01)
    def convertPct(val):
        m = re.search(r'([-\d]+)\%', str(val))
        return float(m.group(1)) / 100. if m else val
    df = df.applymap(convertPct)

    return df


def parse_info_table(table):
    """Parses an info table, like the "Game Info" table or the "Officials"
    table on the PFR Boxscore page. Keys are lower case and have spaces/special
    characters converted to underscores.

    :table: PyQuery object representing the HTML table.
    :returns: A dictionary representing the information.
    """
    ret = {}
    for tr in table('tbody tr').items():
        th, td = tr('th, td').items()
        key = th.text().lower()
        key = re.sub(r'\W', '_', key)
        val = sportsref.utils.flatten_links(td)
        ret[key] = val
    return ret


def flatten_links(td, _recurse=False):
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
            cID = rel_url_to_id(c.attrib['href'])
            return cID if cID else c.text_content()
        else:
            return flatten_links(pq(c), _recurse=True)

    # if there's no text, just return None
    if not td or not td.text():
        return '' if _recurse else None

    return ''.join(_flattenC(c) for c in td.contents())


@sportsref.decorators.memoize
def rel_url_to_id(url):
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
    * leagues/...
    * coaches/...
    * officials/...
    * schools/...
    * schools/high_schools.cgi?id=...

    :returns: ID associated with the given relative URL.
    """
    yearRegex = r'.*/years/(\d{4}).*|.*/gamelog/(\d{4}).*'
    playerRegex = r'.*/players/(?:\w/)?(.+?)(?:/|\.html?)'
    boxscoresRegex = r'.*/boxscores/(.+?)\.html?'
    teamRegex = r'.*/teams/(\w{3})/.*'
    coachRegex = r'.*/coaches/(.+?)\.html?'
    stadiumRegex = r'.*/stadiums/(.+?)\.html?'
    refRegex = r'.*/officials/(.+?r)\.html?'
    collegeRegex = r'.*/schools/(\S+?)/.*'
    hsRegex = r'.*/schools/high_schools\.cgi\?id=([^\&]{8})'
    bsDateRegex = r'.*/boxscores/index\.cgi\?(month=\d+&day=\d+&year=\d+)'
    leagueRegex = r'.*/leagues/(.*_\d{4}).*'

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
        leagueRegex,
    ]

    for regex in regexes:
        match = re.match(regex, url, re.I)
        if match:
            return filter(None, match.groups())[0]

    print 'WARNING. NO MATCH WAS FOUND FOR "{}"'.format(url)
    return 'noIDer00'
