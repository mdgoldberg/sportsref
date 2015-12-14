import copy
import multiprocessing as mp
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

import pfr

__all__ = [
    'getHTML',
    'relURLToID',
    'parseTable',
    'parsePlayDetails',
    'expandDetails'
]

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
    data = [
        [_flattenLinks(td) for td in row.items('td')]
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
        df.loc[:, 'year_id'] = df.year_id.fillna(method='ffill')
        df.loc[:, 'year_id'] = df.year_id.apply(lambda y: int(str(y)[:4]))

    # game_date -> bsID
    if 'game_date' in df.columns:
        df = df.rename(columns={'game_date': 'bsID'})

    # ignore * and + to note things
    df.replace(re.compile(r'[\*\+]'), '', inplace=True)

    return df

RUSH_OPTS = {
    'left end': 'LE', 'left tackle': 'LT', 'left guard': 'LG',
    'up the middle': 'M', 'middle': 'M',
    'right end': 'RE', 'right tackle': 'RT', 'right guard': 'RG',
}
PASS_OPTS = {
    'short left': 'SL', 'short middle': 'SM', 'short right': 'SR',
    'deep left': 'DL', 'deep middle': 'DM', 'deep right': 'DR',
}

@pfr.decorators.memoized
def parsePlayDetails(details):
    """Parses play details from play-by-play string and returns structured
    data.
    
    :returns: dictionary of play attributes
    """

    # if input isn't a string, return None
    if not isinstance(details, basestring):
        return None

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
        struct['isChallenged'] = True
        struct.update(match.groupdict())
        # if overturned, only record updated play
        if 'overturned' in details:
            overturnedIdx = details.index('overturned.')
            newStart = overturnedIdx + len('overturned.')
            details = details[newStart:].strip()
    else:
        struct['isChallenged'] = False

    # TODO: expand on laterals
    struct['isLateral'] = details.find('lateral') != -1

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
                r"(?: \(forced by (?P<fumbForcer>{0})\))?"
                r"(?:, recovered by (?P<fumbRecoverer>{0}) at )?"
                r"(?:, ball out of bounds at )?"
                r"(?:(?P<fumbRecFieldside>[a-z]+)?\-?(?P<fumbRecYdLine>\-?\d+))?"
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
             r'(?:(?P<intFieldside>[a-z]*)?\-?(?P<intYdLine>\-?\d*))?' +
             r'(?: and returned for (?P<intRetYds>\-?\d+) yards?\.?)?)?')
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
    nextREs.append(r'(?P<isTouchback>, touchback)')
    nextREs.append(r'(?P<oob>, out of bounds)')
    nextREs.append(
        r', returned by (?P<koReturner>{0}) for '.format(playerRE) +
        r'(?:(?P<koRetYds>\-?\d{1,3}) yards?|no gain)'
    )
    nextREs.append(
        (r'(?P<muffedCatch>, muffed catch by )(?P<muffedBy>{0}),'
        r' recovered by (?P<muffRecoverer>{0})').format(playerRE) +
        r' and returned for (?:(?P<muffRetYds>\-?\d+) yards|no gain)'
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
        r'(?:, (?P<isBlocked>blocked) by '
        r'(?P<fgBlocker>{0}))?'.format(playerRE) +
        r'(?:, recovered by (?P<fgBlockRecoverer>{0}))?'.format(playerRE) +
        r'(?: and returned for (?:(?P<fgBlockRetYds>\-?\d+) yards?|no gain))?'
        )
    fgREstr = r'{}{}{}{}{}'.format(fgKickerRE, fgBaseRE,
                                   fgBlockRE, tdRE, penaltyRE)
    fgRE = re.compile(fgREstr, re.IGNORECASE)

    # create punt regex
    punterRE = r'.*?(?P<punter>{0})'.format(playerRE)
    puntBlockRE = (
        (r' punts, (?P<isBlocked>blocked) by (?P<puntBlocker>{0})'
         r'(?:, recovered by (?P<puntBlockRecoverer>{0})').format(playerRE) +
        r'(?: and returned (?:(?P<puntBlockRetYds>\-?\d+) yards|no gain))?)?'
    )
    puntYdsRE = r' punts (?P<puntYds>\d+) yards?'
    nextREs = []
    nextREs.append(r', (?P<isFairCatch>fair catch) by (?P<fairCatcher>{0})'
                   .format(playerRE))
    nextREs.append(r', (?P<oob>out of bounds)')
    nextREs.append(
        (r'(?P<isMuffedCatch>, muffed catch by )(?P<muffedBy>{0}),'
        r' recovered by (?P<muffRecoverer>{0})').format(playerRE) +
        r' and returned for ' +
        r'(?:(?P<muffRetYds>\d+) yards|no gain)'
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
    extraPointREstr = (r'(?:(?P<xpKicker>{0}) kicks)? ?extra point '
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
        struct['isKickoff'] = True
        struct.update(match.groupdict())
        return struct

    # try parsing as a timeout
    match = timeoutRE.match(details)
    if match:
        # parse as timeout
        struct['isTimeout'] = True
        struct.update(match.groupdict())
        return struct
    
    # try parsing as a field goal
    match = fgRE.match(details)
    if match:
        # parse as a field goal
        struct['isFieldGoal'] = True
        struct.update(match.groupdict())
        x = struct.get('fgBlocker')
        return struct

    # try parsing as a punt
    match = puntRE.match(details)
    if match:
        # parse as a punt
        struct['isPunt'] = True
        struct.update(match.groupdict())
        return struct
    
    # try parsing as a kneel
    match = kneelRE.match(details)
    if match:
        # parse as a kneel
        struct['isKneel'] = True
        struct.update(match.groupdict())
        return struct
    
    # try parsing as a spike
    match = spikeRE.match(details)
    if match:
        # parse as a spike
        struct['isSpike'] = True
        struct.update(match.groupdict())
        return struct

    # try parsing as an XP
    match = extraPointRE.match(details)
    if match:
        # parse as an XP
        struct['isXP'] = True
        struct.update(match.groupdict())
        return struct

    # try parsing as a 2-point conversion
    match = twoPointRE.match(details)
    if match:
        # parse as a 2-point conversion
        struct['isTwoPoint'] = True
        realPlay = pfr.utils.parsePlayDetails(match.group('twoPoint'))
        if realPlay:
            struct.update(realPlay)
        return struct

    # try parsing as a pre-snap penalty
    match = psPenaltyRE.match(details)
    if match:
        # parse as a pre-snap penalty
        struct['isPresnapPenalty'] = True
        struct.update(match.groupdict())
        return struct

    # try parsing as a pass
    match = passRE.match(details)
    if match:
        # parse as a pass
        struct['isPass'] = True
        struct.update(match.groupdict())
        return struct

    # try parsing as a run
    match = rushRE.match(details)
    if match:
        # parse as a run
        struct['isRun'] = True
        struct.update(match.groupdict())
        return struct
    
    return None
        
@pfr.decorators.memoized
def cleanFeatures(struct):
    """Cleans up the features collected in parsePlayDetails.

    :struct: dict of features parsed from details string.
    :returns: the same dict, but with cleaner features (e.g., convert bools,
    ints, etc.)
    """
    struct = dict(struct)
    # First, clean up existing variables on a one-off basis
    struct['challengeUpheld'] = struct.get('challengeUpheld') == 'upheld'
    struct['fgGood'] = struct.get('fgGood') == 'good'
    struct['isBlocked'] = struct.get('isBlocked') == 'blocked'
    struct['isComplete'] = struct.get('isComplete') == 'complete'
    struct['isFairCatch'] = struct.get('isFairCatch') == 'fair catch'
    struct['isTD'] = struct.get('isTD') == ', touchdown'
    struct['isTouchback'] = struct.get('touchback') == ', touchback'
    struct['isMuffedCatch'] = pd.notnull(struct.get('isMuffedCatch'))
    struct['oob'] = pd.notnull(struct.get('oob'))
    struct['passLoc'] = PASS_OPTS.get(struct.get('passLoc'), np.nan)
    struct['penDeclined'] = struct.get('penDeclined') == 'Declined'
    if struct['quarter'] == 'OT': struct['quarter'] = 5
    struct['rushDir'] = RUSH_OPTS.get(struct.get('rushDir'), np.nan)
    struct['timeoutTeam'] = pfr.teams.teamIDs().get(struct.get('timeoutTeam'),
                                                    np.nan)
    struct['twoPointSuccess'] = struct.get('twoPointSuccess') == 'succeeds'
    struct['xpGood'] = struct.get('xpGood') == 'good'
    # Second, ensure types are correct
    bool_vars = [
        'fgGood', 'isBlocked', 'isChallenged', 'isComplete', 'isFairCatch',
        'isFieldGoal', 'isKickoff', 'isKneel', 'isLateral', 'isPass',
        'isPresnapPenalty', 'isPunt', 'isRun', 'isSpike', 'isTD',
        'isTimeout', 'isTouchback', 'isTwoPoint', 'isXP', 'isMuffedCatch',
        'oob', 'penDeclined', 'twoPointSuccess', 'xpGood'
    ]
    int_vars = [
        'down', 'fgBlockRetYds', 'fgDist', 'fumbRecYdLine', 'fumbRetYds',
        'intRetYds', 'intYdLine', 'koRetYds', 'koYds', 'muffRetYds',
        'pbp_score_aw', 'pbp_score_hm', 'penYds', 'puntBlockRetYds',
        'puntRetYds', 'puntYds', 'quarter', 'sackYds', 'timeoutNum', 'ydLine',
        'yds', 'yds_to_go'
    ]
    float_vars = [
        'exp_pts_after', 'exp_pts_before', 'home_wp'
    ]
    string_vars = [
        'challenger', 'detail', 'fairCatcher', 'fgBlockRecoverer',
        'fgBlocker', 'fgKicker', 'fieldside', 'fumbForcer',
        'fumbRecFieldside', 'fumbRecoverer', 'fumbler', 'intFieldside',
        'interceptor', 'kneelQB', 'koKicker', 'koReturner', 'muffRecoverer',
        'muffedBy', 'passLoc', 'passer', 'penOn', 'penalty',
        'puntBlockRecoverer', 'puntBlocker', 'puntReturner', 'punter',
        'qtr_time_remain', 'rushDir', 'rusher', 'sacker1', 'sacker2',
        'spikeQB', 'tackler1', 'tackler2', 'target', 'timeoutTeam',
        'xpKicker'
    ]
    for var in bool_vars:
        struct[var] = struct.get(var) == True
    for var in int_vars:
        try:
            struct[var] = int(struct.get(var))
        except (ValueError, TypeError) as e:
            struct[var] = np.nan
    for var in float_vars:
        try:
            struct[var] = float(struct.get(var))
        except (ValueError, TypeError) as e:
            struct[var] = np.nan
    for var in string_vars:
        if var not in struct or pd.isnull(struct[var]):
            struct[var] = np.nan
    # Third, create new helper variables based on parsed variables
    # creating fieldside and ydline from location
    fieldside, ydline = locToFeatures(struct['location'])
    struct['fieldside'] = fieldside
    struct['ydLine'] = ydline
    # creating secsElapsedInGame from qtr_time_remain and quarter
    if pd.notnull(struct.get('qtr_time_remain')):
        qtr = struct['quarter']
        mins, secs = map(int, struct['qtr_time_remain'].split(':'))
        struct['secsElapsedInGame'] = qtr*900 - mins*60 - secs
    else:
        struct['secsElapsedInGame'] = np.nan
    # if given a bsID and it's a play from scrimmage,
    # create columns for tm (offense), opp (defense)
    # TODO: include non-plays-from-scrimmage like kickoffs and XPs
    # TODO: get offense and defense teams even when penalty -> no play
    if 'bsID' in struct and not struct['isTimeout']:
        bs = pfr.boxscores.BoxScore(struct['bsID'])
        if struct['isRun']:
            pID = struct['rusher']
        elif struct['isPass']:
            pID = (struct['passer'] if pd.notnull(struct['passer'])
                   else struct['sackQB'])
        elif struct['isFieldGoal']:
            pID = struct['fgKicker']
        elif struct['isPunt']:
            pID = struct['punter']
        elif struct['isXP']:
            pID = struct['xpKicker']
        elif struct['isPresnapPenalty']:
            pID = struct['penOn']
        elif struct['isKickoff']:
            pID = struct['koKicker']
        elif struct['isSpike']:
            pID = struct['spikeQB']
        elif struct['isKneel']:
            pID = struct['kneelQB']
        else:
            pID = None
        if pID and len(pID) == 3:
            struct['team'] = pID
            struct['opp'] = bs.away() if bs.home() == pID else bs.home()
        elif pID:
            player = pfr.players.Player(pID)
            glog = player.gamelog()
            narrowed = glog.loc[glog.bsID == struct['bsID'], 'team']
            if not narrowed.empty:
                struct['team'] = narrowed.iloc[0]
                struct['opp'] = (bs.home() if bs.home() != struct['team']
                                 else bs.away())
    # creating columns for turnovers
    struct['isInt'] = pd.notnull(struct.get('interceptor'))
    struct['isFumble'] = pd.notnull(struct.get('fumbler'))
    # create column for isPenalty
    struct['isPenalty'] = pd.notnull(struct.get('penalty'))
    # create column for distToGoal
    if all(pd.notnull(struct.get(k)) for k in ('team', 'ydLine')):
        struct['distToGoal'] = (
            struct['ydLine'] if struct['team'] != struct['fieldside']
            else 100 - struct['ydLine'])
    # create column for offense's WP (if WP and team in dataset)
    if (pd.notnull(struct.get('home_wp')) and pd.notnull(struct.get('team'))):
        struct['team_wp'] = (struct['home_wp']
                             if struct['team'] == struct['home']
                             else 100. - struct['home_wp'])
    # create column for offense and defense scores if not already there
    if pd.notnull(struct.get('team')) and 'teamScore' not in struct:
        bs = pfr.boxscores.BoxScore(struct['bsID'])
        if bs.home() == struct['team']:
            struct['teamScore'] = struct['pbp_score_hm']
            struct['oppScore'] = struct['pbp_score_aw']
        else:
            struct['teamScore'] = struct['pbp_score_aw']
            struct['oppScore'] = struct['pbp_score_hm']
    return struct

@pfr.decorators.memoized
def expandDetails(df, detailCol='detail', keepErrors=False):
    """Expands the details column of the given dataframe and returns the
    resulting DataFrame.

    :df: The input DataFrame.
    :detailCol: The detail column name.
    :keepErrors: If True, leave in rows with unmatched play details; if False,
    remove them from the resulting DataFrame.
    :returns: Returns DataFrame with new columns from pbp parsing.
    """
    df = copy.deepcopy(df)
    dicts = map(pfr.utils.parsePlayDetails, df[detailCol])
    if keepErrors:
        cols = {c for d in dicts if d for c in d.iterkeys()}
        blankEntry = {c: np.nan for c in cols}
        dicts = [d if d else blankEntry for i, d in enumerate(dicts)]
    else:
        errors = [i for i, d in enumerate(dicts) if d is None]
        df = df.drop(errors).reset_index(drop=True)
        dicts = [d for i, d in enumerate(dicts) if i not in errors]
    # get details dataframe and merge it with original
    details = pd.DataFrame(dicts)
    df = pd.merge(df, details, left_index=True, right_index=True)
    # use cleanFeatures to clean up and add columns
    df = pd.DataFrame(list(df.apply(cleanFeatures, axis=1)))
    return df

@pfr.decorators.memoized
def locToFeatures(l):
    """Converts a location string "{Half}, {YardLine}" into a tuple of those
    values, the second being an int.

    :l: The string from the play by play table representing location.
    :returns: A tuple that separates out the values, making them missing
    (np.nan) when necessary.

    """
    if l:
        l = l.strip()
        if ' ' in l:
            r = l.split()
            r[0] = r[0].lower()
            r[1] = int(r[1])
        else:
            r = (np.nan, int(l))
    else:
        r = (np.nan, np.nan)
    return r

def _flattenLinks(td):
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
