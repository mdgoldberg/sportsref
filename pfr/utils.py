import operator as op
import os
import re
import sys
import time

import lxml
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq
import requests

# import findspark
# findspark.init()
# findspark.find()
# import pyspark
# sc = pyspark.SparkContext('local', 'pfr')
# sqlsc = pyspark.sql.SQLContext(sc)

import pfr

__all__ = [
    'getHTML',
    'relURLToID',
    'parseTable',
    'parsePlayDetails',
    'expandDetails'
]

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
    time.sleep(1.5)
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
    * teams/...
    * years/...
    * coaches/...
    * officials/...

    :returns: ID associated with the given relative URL.
    """
    playerRegex = re.compile(r'/players/[A-Z]/(.+?)\.html?')
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
    if isinstance(table, pq):
        pass
    elif isinstance(table, lxml.html.HtmlElement):
        table = pq(table.text_content())
    elif isinstance(table, basestring):
        table = pq(table)
    else:
        raise 'UNKNOWN TYPE PASSED TO parseTable'

    # get columns
    columns = [c.attrib['data-stat']
               for c in table('thead tr[class=""] th[data-stat]')]
    
    # get data
    data = [
        [_flattenLinks(td) for td in row('td')]
        for row in map(pq, table('tbody tr').not_('.thead'))
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype='float')
    
    # small fixes to DataFrame

    # team_index table (and others?) fix
    if 'year_id' in df.columns and 'league_id' in df.columns:
        df['year_id'] = df['league_id']
        del df['league_id']

    if 'year_id' in df.columns:
        df = df.query('year_id != "AFL"')
        df.year_id = df.year_id.apply(
            lambda y: int(y[:4]) if isinstance(y, basestring) else y
        )

    # ignore * and + to note things
    df.replace(re.compile(r'[\*\+]'), '', inplace=True)

    return df

def parsePlayDetails(details):
    """Parses play details from play-by-play string and returns structured
    data.
    
    :returns: dictionary of play attributes
    """

    # if input isn't a string, return None
    if not isinstance(details, basestring):
        return None

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

    playerRE = r"\S{6,8}\d{2}"


    # initialize return dictionary - struct
    struct = {}

    # handle challenges
    # TODO: record the play both before & after an overturned challenge
    challengeRE = re.compile(
        r'.+\. (?P<challenger>.+?) challenged.*? the play was '
        '(?P<challengeUpheld>upheld|overturned)\.',
        re.IGNORECASE
    )
    match = challengeRE.match(details)
    if match:
        struct['challenged'] = True
        struct.update(match.groupdict())
        struct['challengeUpheld'] = struct['challengeUpheld'] == 'upheld'
        # if overturned, only record updated play
        if 'overturned' in details:
            overturnedIdx = details.index('overturned.')
            newStart = overturnedIdx + len('overturned.')
            details = details[newStart:].strip()
    else:
        struct['challenged'] = False

    # TODO: expand on laterals
    struct['lateral'] = details.find('lateral') != -1

    # create rushing regex
    rusherRE = r"(?P<rusher>{0})".format(playerRE)
    rushOptRE = r"(?: {})?".format(rushOptRE)
    rushYardsRE = r"(?:(?:(?P<yds>\-?\d+) yards?)|(?:no gain))"
    # cases: tackle, fumble, td, penalty
    tackleRE = (r"(?: \(tackle by (?P<tackler1>{0})"
                r"(?: and (?P<tackler2>{0}))?\))?"
                .format(playerRE))
    fumbleRE = (r"(?:"
                r"\. (?P<fumbler>{0}) fumbles"
                r"(?: \(forced by (?P<forcer>{0})\))?"
                r"(?:, recovered by (?P<recoverer>{0}) at )?"
                r"(?:, ball out of bounds at )?"
                r"(?:(?P<fumbRecFieldside>[a-z]*)?\-?(?P<fumbRecYdLine>\-?\d*))?"
                r"(?: and returned for (?P<fumbRetYds>\-?\d*) yards)?"
                r")?"
                .format(playerRE))
    tdRE = r"(?P<isTD>, touchdown)?"
    penaltyRE = (r"(?:.*?"
                 r"\. Penalty on (?P<penOn>{0}|): "
                 r"(?P<penalty>[^\(,]+)"
                 r"(?: \((?P<penDeclined>Declined)\)|"
                 r", (?P<penYds>\d*) yards?)"
                 r")?"
                 .format(playerRE))

    rushREstr = (
        r"{}{}(?: for {}{}{}{}{})?"
    ).format(rusherRE, rushOptRE, rushYardsRE, tackleRE, fumbleRE, tdRE,
             penaltyRE)
    rushRE = re.compile(rushREstr, re.IGNORECASE)

    # create passing regex
    # TODO: capture "defended by X" for defensive stats
    passerRE = r"(?P<passer>{0})".format(playerRE)
    sackRE = (r"(?:sacked (?:by (?P<sacker1>{0})(?: and (?P<sacker2>{0}))? )?"
              r"for (?P<sackYds>\-?\d+) yards?)"
              .format(playerRE))
    # create throw RE
    completeRE = r"pass (?P<isComplete>(?:in)?complete)"
    passOptRE = r"(?: {})?".format(passOptRE)
    targetedRE=r"(?: (?:to |intended for )?(?P<target>{0}))?".format(playerRE)
    passYardsRE = r"(?: for (?:(?P<yds>\-?\d+) yards?|no gain))"
    intRE = (r'(?: is intercepted by (?P<interceptor>{0}) at '.format(playerRE) +
             r'(?P<intYdLine>\w{3}\-+?\d+) and returned for ' +
             r'(?P<intRetYds>\-?\d+) yards?\.?)')
    throwRE = r'(?:{}{}{}(?:(?:{}|{}){})?)'.format(
        completeRE, passOptRE, targetedRE, passYardsRE, intRE, tackleRE
    )
    passREstr = (
        r"{} (?:{}|{})(?:{}{}{})?"
    ).format(passerRE, sackRE, throwRE, fumbleRE, tdRE, penaltyRE)
    passRE = re.compile(passREstr, re.IGNORECASE)

    # create kickoff regex
    koKickerRE = r'(?P<koKicker>{0})'.format(playerRE)
    koYardsRE = r' kicks (?:off|onside) (?P<koYds>\d{1,3}) yards'
    nextREs = []
    nextREs.append(r'(?P<touchback>, touchback)')
    nextREs.append(r'(?P<oob>, out of bounds)')
    nextREs.append(
        r', returned by (?P<koReturner>{0}) for '.format(playerRE) +
        r'(?:(?P<koRetYds>\-?\d{1,3}) yards?|no gain)'
    )
    # TODO: finish muffed KO features now stored in rawMuffRet
    nextREs.append(
        (r'(?P<muffedCatch>, muffed catch by )(?P<muffedBy>{0}),'
        r' recovered by (?P<muffRecoverer>{0})').format(playerRE) +
        r' and returned for (?P<rawMuffRet>[^\.]+?)'
    )
    nextRE = r'(?:{})?'.format('|'.join(nextREs))
    kickoffREstr = r'{}{}{}{}{}{}{}'.format(
        koKickerRE, koYardsRE, nextRE,
        tackleRE, fumbleRE, tdRE, penaltyRE
    )
    kickoffRE = re.compile(kickoffREstr, re.IGNORECASE)

    # create timeout regex
    timeoutREstr = r'Timeout #(?P<timeoutNum>\d) by (?P<timeoutTeam>.+)'
    timeoutRE = re.compile(timeoutREstr, re.IGNORECASE)

    # create FG regex
    fgKickerRE = r'(?P<fgKicker>{0})'.format(playerRE)
    fgBaseRE = (r' (?P<fgDist>\d+) yard field goal'
                r' (?P<fgGood>good|no good)')
    fgBlockRE = (
        r'(?:, (?P<blocked>blocked) by (?P<fgBlocker>{0}))?'.format(playerRE) +
        r'(?:, recovered by (?P<fgBlockRecoverer>{0}))?'.format(playerRE) +
        r'(?: and returned for (?:(?P<fgBlockRetYds>\-?\d+) yards?|no gain))?'
        )
    fgREstr = r'{}{}{}{}'.format(fgKickerRE, fgBaseRE, fgBlockRE, tdRE)
    fgRE = re.compile(fgREstr, re.IGNORECASE)

    # create punt regex
    punterRE = r'.*?(?P<punter>{0})'.format(playerRE)
    puntBlockRE = (
        (r' punts, (?P<blocked>blocked) by (?P<puntBlocker>{0})'
         r'(?:, recovered by (?P<puntBlockRecoverer>{0})').format(playerRE) +
        r'(?: and returned (?:(?P<puntBlockRetYds>\-?\d+) yards|no gain))?)?'
    )
    puntYdsRE = r' punts (?P<puntYds>\d+) yards?'
    nextREs = []
    nextREs.append(r', (?P<fairCatch>fair catch) by (?P<fairCatcher>{0})'
                   .format(playerRE))
    nextREs.append(r', (?P<oob>out of bounds)')
    nextREs.append(
        (r'(?P<muffedCatch>, muffed catch by )(?P<muffedBy>{0}),'
        r' recovered by (?P<muffRecoverer>{0})').format(playerRE) +
        r' and returned for ' +
        r'(?P<rawMuffRet>[^\.]+?)'
    )
    nextREs.append(
        r', returned by (?P<puntReturner>{0}) for '.format(playerRE) +
        r'(?:(?P<puntRetYds>\-?\d+) yards?|no gain)'
    )
    nextRE = r'(?:{})?'.format('|'.join(nextREs))
    puntREstr = r'{}(?:{}|{}){}{}{}{}{}'.format(
        punterRE, puntBlockRE, puntYdsRE, nextRE,
        tackleRE, fumbleRE, tdRE, penaltyRE
    )
    puntRE = re.compile(puntREstr, re.IGNORECASE)

    # create kneel regex
    kneelREstr = (r'(?P<kneelQB>{0}) kneels for '.format(playerRE) +
                  r'(?:(?P<yds>\-?\d+) yards?|no gain)')
    kneelRE = re.compile(kneelREstr, re.IGNORECASE)

    # create spike regex
    spikeREstr = r'(?P<spikeQB>{0}) spiked the ball'.format(playerRE)
    spikeRE = re.compile(spikeREstr, re.IGNORECASE)

    # create XP regex
    extraPointREstr = (r'(?:(?P<kicker>{0}) kicks)? ?extra point '
                       r'(?P<xpGood>good|no good)').format(playerRE)
    extraPointRE = re.compile(extraPointREstr, re.IGNORECASE)

    # create 2pt conversion regex
    twoPointREstr = (
        r'Two Point Attempt: (?P<twoPoint>.*?),?\s+conversion '
        r'(?P<twoPointSuccess>succeeds|fails)'
    )
    twoPointRE = re.compile(twoPointREstr, re.IGNORECASE)

    # create penalty regex
    psPenaltyREstr = (
        r'Penalty on (?P<penOn>{0}|'.format(playerRE) + r'\w{3}): ' +
        r'(?P<penalty>[^\(,]+)(?: \((?P<penDeclined>Declined)\)|' +
        r', (?P<penYds>\d*) yards?|' +
        r'.*? \(no play\))')
    psPenaltyRE = re.compile(psPenaltyREstr, re.IGNORECASE)

    # try parsing as a kickoff
    match = kickoffRE.match(details)
    if match:
        # parse as a kickoff
        struct.update(match.groupdict())
        struct['isKickoff'] = True
        # change type to int when applicable
        for k in ('koYds', 'koRetYds', 'penYds'):
            struct[k] = int(struct.get(k, 0)) if struct.get(k) else 0
        # change type to bool when applicable
        for k in ('isTD','oob','touchback','muffedCatch','penDeclined'):
            struct[k] = bool(struct.get(k))
        return struct

    # try parsing as a timeout
    match = timeoutRE.match(details)
    if match:
        # parse as timeout
        struct.update(match.groupdict())
        struct['isTimeout'] = True
        struct['timeoutTeam'] = pfr.teams.teamNames()[struct['timeoutTeam']]
        struct['timeoutNum'] = int(struct.get('timeoutNum', 0))
        return struct
    
    # try parsing as a field goal
    match = fgRE.match(details)
    if match:
        # parse as a field goal
        struct.update(match.groupdict())
        struct['isFieldGoal'] = True
        struct['fgDist'] = int(struct.get('fgDist', 0))
        struct['fgGood'] = struct['fgGood'] == 'good'
        struct['fgBlockRetYds'] = (int(struct.get('fgBlockRetYds', 0))
                                   if struct.get('fgBlockRetYds') else np.nan)
        for k in ('blocked', 'isTD'):
            struct[k] = bool(struct.get(k, False))
        return struct

    # try parsing as a punt
    match = puntRE.match(details)
    if match:
        # parse as a punt
        struct.update(match.groupdict())
        struct['isPunt'] = True
        # change type to int when applicable
        for k in ('puntYds', 'puntRetYds', 'penYds', 'puntBlockRetYds'):
            struct[k] = int(struct.get(k, 0)) if struct.get(k) else np.nan
        # change type to bool when applicable
        for k in ('isTD', 'oob', 'touchback', 'muffedCatch', 
                  'penDeclined', 'blocked', 'fairCatch'):
            struct[k] = bool(struct.get(k))
        return struct
    
    # try parsing as a kneel
    match = kneelRE.match(details)
    if match:
        # parse as a kneel
        struct.update(match.groupdict())
        struct['isKneel'] = True
        struct['kneelYds'] = (int(struct.get('kneelYds', 0))
                              if struct.get('kneelYds') else 0)
        return struct
    
    # try parsing as a spike
    match = spikeRE.match(details)
    if match:
        # parse as a spike
        struct.update(match.groupdict())
        struct['isSpike'] = True
        return struct

    # try parsing as an XP
    match = extraPointRE.match(details)
    if match:
        # parse as an XP
        struct.update(match.groupdict())
        struct['isXP'] = True
        struct['xpGood'] = struct['xpGood'] == 'good'
        return struct

    # try parsing as a 2-point conversion
    match = twoPointRE.match(details)
    if match:
        # parse as a 2-point conversion
        struct['isTwoPoint'] = True
        realPlay = pfr.utils.parsePlayDetails(match.group('twoPoint'))
        if realPlay:
            struct.update(realPlay)
        struct['twoPointSuccess'] = match.group('twoPointSuccess')=='succeeds'
        return struct

    # try parsing as a penalty
    match = psPenaltyRE.match(details)
    if match:
        # parse as a penalty
        struct.update(match.groupdict())
        struct['isPresapPenalty'] = True
        struct['penYds'] = (int(struct.get('penYds', 0))
                            if struct.get('penYds') else 0)
        struct['penDeclined'] = bool(struct['penDeclined'])
        return struct

    # try parsing as a pass
    match = passRE.match(details)
    if match:
        # parse as a pass
        struct.update(match.groupdict())
        struct['isPass'] = True
        struct['isSack'] = details.find('sack') > -1
        struct['isInterception'] = details.find('intercepted') > -1
        # change type to int when applicable
        for k in ('yds','fumbRecYdLine','fumbRetYds','penYds'):
            struct[k] = int(struct.get(k, 0)) if struct.get(k) else 0
        # change type to bool when applicable
        struct['isTD'] = bool(struct['isTD'])
        struct['penDeclined'] = bool(struct['penDeclined'])
        struct['isComplete'] = struct['isComplete'] == 'complete'
        # convert pass type
        struct['passLoc'] = PASS_OPTS.get(struct['passLoc'], None)
        return struct

    # try parsing as a run
    match = rushRE.match(details)
    if match:
        # parse as a run
        struct.update(match.groupdict())
        struct['isRun'] = True
        # change type to int when applicable
        for k in ('yds', 'fumbRecYdLine', 'fumbRetYds', 'penYds'):
            struct[k] = int(struct.get(k, 0)) if struct.get(k) else 0
        # change type to bool when applicable
        struct['isTD'] = bool(struct['isTD'])
        struct['penDeclined'] = bool(struct['penDeclined'])
        # convert rush type
        struct['rushDir'] = RUSH_OPTS.get(struct['rushDir'], None)
        return struct
    
    print details
    return None
        

def expandDetails(df, detail='detail', keepErrors=False):
    """Expands the details column of the given dataframe and returns the
    resulting DataFrame.

    :df: The input DataFrame.
    :detail: The detail column name.
    :keepErrors: If True, leave in rows with unmatched play details; if False,
    remove them from the resulting DataFrame.
    :returns: Returns DataFrame with new columns from pbp parsing.
    """
    dicts = map(pfr.utils.parsePlayDetails, df[detail])
    if keepErrors:
        cols = set(c for d in dicts if d for c in d.iterkeys())
        blankEntry = {c: None for c in cols}
        dicts = [d if d else blankEntry for i, d in enumerate(dicts)]
    else:
        errors = [i for i, d in enumerate(dicts) if d is None]
        df = df.drop(errors).reset_index(drop=True)
        dicts = [d for i, d in enumerate(dicts) if i not in errors]
    # get details dataframe and merge it with original
    details = pd.DataFrame(dicts)
    df = pd.merge(df, details, left_index=True, right_index=True)
    # enforce bool types when applicable, filling in False for nulls
    for col in details.columns:
        if all(pd.isnull(item) or item in (True, False)
               for item in df[col]):
            df[col] = df[col].fillna(False)
            df[col] = df[col].astype(bool)
    return df

def _flattenLinks(td):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PQ object, HtmlElement, or string of raw HTML to convert
    :returns: the string with the links flattened to IDs

    """
    # ensure it's a PyQuery object
    if isinstance(td, basestring) or isinstance(td, lxml.html.HtmlElement):
        td = pq(td)

    # if there's no text, just return None
    if not td.text():
        return None

    def _flattenC(c):
        if isinstance(c, basestring):
            return c
        elif 'href' in c.attrib:
            cID = relURLToID(c.attrib['href'])
            return cID if cID else pq(c).text()
        else:
            return pq(c).text()

    return ''.join(_flattenC(c) for c in td.contents())
