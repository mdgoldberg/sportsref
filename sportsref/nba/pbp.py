from builtins import enumerate, int, list, range, zip

import operator
import re

import numpy as np
import pandas as pd

import sportsref

PLAYER_RE = r'\w{0,7}\d{2}'

HM_LINEUP_COLS = ['hm_player{}'.format(i) for i in range(1, 6)]
AW_LINEUP_COLS = ['aw_player{}'.format(i) for i in range(1, 6)]
ALL_LINEUP_COLS = AW_LINEUP_COLS + HM_LINEUP_COLS


def parse_play(boxscore_id, details, is_hm):
    """Parse play details from a play-by-play string describing a play.

    Assuming valid input, this function returns structured data in a dictionary
    describing the play. If the play detail string was invalid, this function
    returns None.

    :param boxscore_id: the boxscore ID of the play
    :param details: detail string for the play
    :param is_hm: bool indicating whether the offense is at home
    :param returns: dictionary of play attributes or None if invalid
    :rtype: dictionary or None
    """
    # if input isn't a string, return None
    if not details or not isinstance(details, basestring):
        return None

    bs = sportsref.nba.BoxScore(boxscore_id)
    aw, hm = bs.away(), bs.home()
    season = sportsref.nba.Season(bs.season())
    hm_roster = set(bs.basic_stats().query('is_home == True').player_id.values)

    p = {}
    p['detail'] = details
    p['home'] = hm
    p['away'] = aw
    p['is_home_play'] = is_hm

    # parsing field goal attempts
    shotRE = (r'(?P<shooter>{0}) (?P<is_fgm>makes|misses) '
              '(?P<is_three>2|3)\-pt shot').format(PLAYER_RE)
    distRE = r' (?:from (?P<shot_dist>\d+) ft|at rim)'
    assistRE = r' \(assist by (?P<assister>{0})\)'.format(PLAYER_RE)
    blockRE = r' \(block by (?P<blocker>{0})\)'.format(PLAYER_RE)
    shotRE = r'{0}{1}(?:{2}|{3})?'.format(shotRE, distRE, assistRE, blockRE)
    m = re.match(shotRE, details, re.IGNORECASE)
    if m:
        p['is_fga'] = True
        p.update(m.groupdict())
        p['shot_dist'] = p['shot_dist'] if p['shot_dist'] is not None else 0
        p['shot_dist'] = int(p['shot_dist'])
        p['is_fgm'] = p['is_fgm'] == 'makes'
        p['is_three'] = p['is_three'] == '3'
        p['is_assist'] = pd.notnull(p.get('assister'))
        p['is_block'] = pd.notnull(p.get('blocker'))
        shooter_home = p['shooter'] in hm_roster
        p['team'] = hm if shooter_home else aw
        p['opp'] = aw if shooter_home else hm
        return p

    # parsing jump balls
    jumpRE = ((r'Jump ball: (?P<away_jumper>{0}) vs\. (?P<home_jumper>{0})'
               r'(?: \((?P<gains_poss>{0}) gains possession\))?')
              .format(PLAYER_RE))
    m = re.match(jumpRE, details, re.IGNORECASE)
    if m:
        p['is_jump_ball'] = True
        p.update(m.groupdict())
        return p

    # parsing rebounds
    rebRE = (r'(?P<is_oreb>Offensive|Defensive) rebound'
             r' by (?P<rebounder>{0}|Team)').format(PLAYER_RE)
    m = re.match(rebRE, details, re.I)
    if m:
        p['is_reb'] = True
        p.update(m.groupdict())
        p['is_oreb'] = p['is_oreb'].lower() == 'offensive'
        p['is_dreb'] = not p['is_oreb']
        if p['rebounder'] == 'Team':
            p['reb_team'], other = (hm, aw) if is_hm else (aw, hm)
        else:
            reb_home = p['rebounder'] in hm_roster
            p['reb_team'], other = (hm, aw) if reb_home else (aw, hm)
        p['team'] = p['reb_team'] if p['is_oreb'] else other
        p['opp'] = p['reb_team'] if p['is_dreb'] else other
        return p

    # parsing free throws
    ftRE = (r'(?P<ft_shooter>{}) (?P<is_ftm>makes|misses) '
            r'(?P<is_tech_fta>technical )?(?P<is_flag_fta>flagrant )?'
            r'(?P<is_clearpath_fta>clear path )?free throw'
            r'(?: (?P<fta_num>\d+) of (?P<tot_fta>\d+))?').format(PLAYER_RE)
    m = re.match(ftRE, details, re.I)
    if m:
        p['is_fta'] = True
        p.update(m.groupdict())
        p['is_ftm'] = p['is_ftm'] == 'makes'
        p['is_tech_fta'] = bool(p['is_tech_fta'])
        p['is_flag_fta'] = bool(p['is_flag_fta'])
        p['is_clearpath_fta'] = bool(p['is_clearpath_fta'])
        p['is_pf_fta'] = not p['is_tech_fta']
        if p['tot_fta']:
            p['tot_fta'] = int(p['tot_fta'])
        if p['fta_num']:
            p['fta_num'] = int(p['fta_num'])
        ft_home = p['ft_shooter'] in hm_roster
        p['ft_team'] = hm if ft_home else aw
        if not p['is_tech_fta']:
            p['team'] = hm if ft_home else aw
            p['opp'] = aw if ft_home else hm
        return p

    # parsing substitutions
    subRE = (r'(?P<sub_in>{0}) enters the game for '
             r'(?P<sub_out>{0})').format(PLAYER_RE)
    m = re.match(subRE, details, re.I)
    if m:
        p['is_sub'] = True
        p.update(m.groupdict())
        sub_home = p['sub_in'] in hm_roster or p['sub_out'] in hm_roster
        p['sub_team'] = hm if sub_home else aw
        return p

    # parsing turnovers
    toReasons = (r'(?P<to_type>[^;]+)(?:; steal by '
                 r'(?P<stealer>{0}))?').format(PLAYER_RE)
    toRE = (r'Turnover by (?P<to_by>{}|Team) '
            r'\((?:{})\)').format(PLAYER_RE, toReasons)
    m = re.match(toRE, details, re.I)
    if m:
        p['is_to'] = True
        p.update(m.groupdict())
        p['to_type'] = p['to_type'].lower()
        if p['to_type'] == 'offensive foul':
            return None
        p['is_steal'] = pd.notnull(p['stealer'])
        p['is_travel'] = p['to_type'] == 'traveling'
        p['is_shot_clock_viol'] = p['to_type'] == 'shot clock'
        p['is_oob'] = p['to_type'] == 'step out of bounds'
        p['is_three_sec_viol'] = p['to_type'] == '3 sec'
        p['is_backcourt_viol'] = p['to_type'] == 'back court'
        p['is_off_goaltend'] = p['to_type'] == 'offensive goaltending'
        p['is_double_dribble'] = p['to_type'] == 'dbl dribble'
        p['is_discont_dribble'] = p['to_type'] == 'discontinued dribble'
        p['is_carry'] = p['to_type'] == 'palming'
        if p['to_by'] == 'Team':
            p['team'] = hm if is_hm else aw
            p['opp'] = aw if is_hm else hm
        else:
            to_home = p['to_by'] in hm_roster
            p['team'] = hm if to_home else aw
            p['opp'] = aw if to_home else hm
        return p

    # parsing shooting fouls
    shotFoulRE = (r'Shooting(?P<is_block_foul> block)? foul by (?P<fouler>{0})'
                  r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(shotFoulRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_shot_foul'] = True
        p.update(m.groupdict())
        p['is_block_foul'] = bool(p['is_block_foul'])
        foul_on_home = p['fouler'] in hm_roster
        p['team'] = aw if foul_on_home else hm
        p['opp'] = hm if foul_on_home else aw
        p['foul_team'] = p['opp']
        return p

    # parsing offensive fouls
    offFoulRE = (r'Offensive(?P<is_charge> charge)? foul '
                 r'by (?P<to_by>{0})'
                 r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(offFoulRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_off_foul'] = True
        p['is_to'] = True
        p.update(m.groupdict())
        p['is_charge'] = bool(p['is_charge'])
        p['fouler'] = p['to_by']
        foul_on_home = p['fouler'] in hm_roster
        p['team'] = hm if foul_on_home else aw
        p['opp'] = aw if foul_on_home else hm
        p['foul_team'] = p['team']
        return p

    # parsing personal fouls
    foulRE = (r'Personal (?P<is_take_foul>take )?(?P<is_block_foul>block )?'
              r'foul by (?P<fouler>{0})(?: \(drawn by '
              r'(?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(foulRE, details, re.I)
    if m:
        p['is_pf'] = True
        p.update(m.groupdict())
        p['is_take_foul'] = bool(p['is_take_foul'])
        p['is_block_foul'] = bool(p['is_block_foul'])
        foul_on_home = p['fouler'] in hm_roster
        p['team'] = aw if foul_on_home else hm
        p['opp'] = hm if foul_on_home else aw
        p['foul_team'] = p['opp']
        return p

    # TODO: parsing double personal fouls
    # double_foul_re = (r'Double personal foul by (?P<fouler1>{0}) and '
    #                   r'(?P<fouler2>{0})').format(PLAYER_RE)
    # m = re.match(double_Foul_re, details, re.I)
    # if m:
    #     p['is_pf'] = True
    #     p.update(m.groupdict())
    #     p['team'] =

    # parsing loose ball fouls
    looseBallRE = (r'Loose ball foul by (?P<fouler>{0})'
                   r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(looseBallRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_loose_ball_foul'] = True
        p.update(m.groupdict())
        foul_home = p['fouler'] in hm_roster
        p['foul_team'] = hm if foul_home else aw
        return p

    # parsing punching fouls
    # TODO

    # parsing away from play fouls
    awayFromBallRE = ((r'Away from play foul by (?P<fouler>{0})'
                       r'(?: \(drawn by (?P<drew_foul>{0})\))?')
                      .format(PLAYER_RE))
    m = re.match(awayFromBallRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_away_from_play_foul'] = True
        p.update(m.groupdict())
        foul_on_home = p['fouler'] in hm_roster
        # TODO: figure out who had the ball based on previous play
        p['foul_team'] = hm if foul_on_home else aw
        return p

    # parsing inbound fouls
    inboundRE = (r'Inbound foul by (?P<fouler>{0})'
                 r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(inboundRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_inbound_foul'] = True
        p.update(m.groupdict())
        foul_on_home = p['fouler'] in hm_roster
        p['team'] = aw if foul_on_home else hm
        p['opp'] = hm if foul_on_home else aw
        p['foul_team'] = p['opp']
        return p

    # parsing flagrant fouls
    flagrantRE = (r'Flagrant foul type (?P<flag_type>1|2) by (?P<fouler>{0})'
                  r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(flagrantRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_flagrant'] = True
        p.update(m.groupdict())
        foul_on_home = p['fouler'] in hm_roster
        p['foul_team'] = hm if foul_on_home else aw
        return p

    # parsing clear path fouls
    clearPathRE = (r'Clear path foul by (?P<fouler>{0})'
                   r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(clearPathRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_clear_path_foul'] = True
        p.update(m.groupdict())
        foul_on_home = p['fouler'] in hm_roster
        p['team'] = aw if foul_on_home else hm
        p['opp'] = hm if foul_on_home else aw
        p['foul_team'] = p['opp']
        return p

    # parsing timeouts
    timeoutRE = r'(?P<timeout_team>.*?) (?:full )?timeout'
    m = re.match(timeoutRE, details, re.I)
    if m:
        p['is_timeout'] = True
        p.update(m.groupdict())
        isOfficialTO = p['timeout_team'].lower() == 'official'
        name_to_id = season.team_names_to_ids()
        p['timeout_team'] = (
            'Official' if isOfficialTO else
            name_to_id.get(hm, name_to_id.get(aw, p['timeout_team']))
        )
        return p

    # parsing technical fouls
    techRE = (r'(?P<is_hanging>Hanging )?'
              r'(?P<is_taunting>Taunting )?'
              r'(?P<is_ill_def>Ill def )?'
              r'(?P<is_delay>Delay )?'
              r'(?P<is_unsport>Non unsport )?'
              r'tech(?:nical)? foul by '
              r'(?P<tech_fouler>{0}|Team)').format(PLAYER_RE)
    m = re.match(techRE, details, re.I)
    if m:
        p['is_tech_foul'] = True
        p.update(m.groupdict())
        p['is_hanging'] = bool(p['is_hanging'])
        p['is_taunting'] = bool(p['is_taunting'])
        p['is_ill_def'] = bool(p['is_ill_def'])
        p['is_delay'] = bool(p['is_delay'])
        p['is_unsport'] = bool(p['is_unsport'])
        foul_on_home = p['tech_fouler'] in hm_roster
        p['foul_team'] = hm if foul_on_home else aw
        return p

    # parsing ejections
    ejectRE = r'(?P<ejectee>{0}|Team) ejected from game'.format(PLAYER_RE)
    m = re.match(ejectRE, details, re.I)
    if m:
        p['is_ejection'] = True
        p.update(m.groupdict())
        if p['ejectee'] == 'Team':
            p['ejectee_team'] = hm if is_hm else aw
        else:
            eject_home = p['ejectee'] in hm_roster
            p['ejectee_team'] = hm if eject_home else aw
        return p

    # parsing defensive 3 seconds techs
    def3TechRE = (r'(?:Def 3 sec tech foul|Defensive three seconds)'
                  r' by (?P<tech_fouler>{})').format(PLAYER_RE)
    m = re.match(def3TechRE, details, re.I)
    if m:
        p['is_tech_foul'] = True
        p['is_def_three_secs'] = True
        p.update(m.groupdict())
        foul_on_home = p['tech_fouler'] in hm_roster
        p['team'] = aw if foul_on_home else hm
        p['opp'] = hm if foul_on_home else aw
        p['foul_team'] = p['opp']
        return p

    # parsing violations
    violRE = (r'Violation by (?P<violator>{0}|Team) '
              r'\((?P<viol_type>.*)\)').format(PLAYER_RE)
    m = re.match(violRE, details, re.I)
    if m:
        p['is_viol'] = True
        p.update(m.groupdict())
        if p['violator'] == 'Team':
            p['viol_team'] = hm if is_hm else aw
        else:
            viol_home = p['violator'] in hm_roster
            p['viol_team'] = hm if viol_home else aw
        return p

    p['is_error'] = True
    return p


def clean_features(df):
    """Fixes up columns of the passed DataFrame, such as casting T/F columns to
    boolean and filling in NaNs for team and opp.

    :param df: DataFrame of play-by-play data.
    :returns: Dataframe with cleaned columns.
    """
    df = pd.DataFrame(df)

    # drop duplicate rows
    # df.drop_duplicates(['secs_elapsed', 'detail'], inplace=True)

    # make indicator columns boolean type (and fill in NaNs)
    boolVals = set([True, False, None, np.nan])
    for c in df:
        if set(df[c].unique()[:5]) <= boolVals:
            df[c] = df[c].map(lambda x: x is True)

    # fix free throw columns on technicals
    df.ix[df.is_tech_fta, ['fta_num', 'tot_fta']] = 1

    # fill in NaN's/fix team, opp columns
    df.team.fillna(method='bfill', inplace=True)
    df.opp.fillna(method='bfill', inplace=True)
    df.team.fillna(method='ffill', inplace=True)
    df.opp.fillna(method='ffill', inplace=True)
    if 'is_jump_ball' in df.columns:
        df.ix[df['is_jump_ball'], ['team', 'opp']] = np.nan

    return df


def get_period_starters(df):
    """TODO
    """

    def players_from_play(play):
        """Figures out what players are in the game based on the players
        mentioned in a play. Returns away and home players as two sets.

        :param play: A dictionary representing a parsed play.
        :returns: (aw_players, hm_players)
        :rtype: tuple of lists
        """
        # if it's a tech FT from between periods, don't count this play
        if (
            play['clock_time'] == '12:00.0' and
            (play.get('is_tech_foul') or play.get('is_tech_fta'))
        ):
            return [], []

        stats = sportsref.nba.BoxScore(play['boxscore_id']).basic_stats()
        home_grouped = stats.groupby('is_home')
        hm_roster = set(home_grouped.player_id.get_group(True).values)
        aw_roster = set(home_grouped.player_id.get_group(False).values)
        player_keys = [
            'assister', 'away_jumper', 'blocker', 'drew_foul', 'fouler',
            'ft_shooter', 'gains_poss', 'home_jumper', 'rebounder', 'shooter',
            'stealer', 'sub_in', 'sub_out', 'to_by'
        ]
        players = [p for p in play[player_keys] if pd.notnull(p)]

        aw_players = [p for p in players if p in aw_roster]
        hm_players = [p for p in players if p in hm_roster]
        return aw_players, hm_players

    # create a mapping { quarter => (away_starters, home_starters) }
    n_periods = df.quarter.nunique()
    period_starters = [(set(), set()) for _ in range(n_periods)]

    # fill out this mapping quarter by quarter
    for qtr, qtr_grp in df.groupby(df.quarter):
        aw_starters, hm_starters = period_starters[qtr-1]
        exclude = set()
        # loop through sets of plays that happen at the "same time"
        for label, time_grp in qtr_grp.groupby(qtr_grp.secs_elapsed):
            # first, if they sub in and weren't already starters, exclude them
            sub_ins = set(time_grp.sub_in.dropna().values)
            exclude.update(sub_ins - aw_starters - hm_starters)
            # second, figure out new starters from each play at this time
            for i, row in time_grp.iterrows():
                aw_players, hm_players = players_from_play(row)
                # update overall sets for the quarter
                aw_starters.update(aw_players)
                hm_starters.update(hm_players)
            # remove excluded (subbed-in) players
            hm_starters -= exclude
            aw_starters -= exclude
            # check whether we have found all starters
            if len(hm_starters) > 5 or len(aw_starters) > 5:
                import ipdb
                ipdb.set_trace()
            if len(hm_starters) >= 5 and len(aw_starters) >= 5:
                break

        if len(hm_starters) != 5 or len(aw_starters) != 5:
            print('WARNING: wrong number of starters for a team in Q{} of {}'
                  .format(qtr, df.boxscore_id.iloc[0]))

    return period_starters


def get_period_starters_pm(boxscore_id):
    """NOTE: THIS FUNCTION WAS AN IDEA I TRIED THAT DOES NOT WORK AT THE
    MOMENT. PERHAPS THIS APPROACH COULD WORK IN THE FUTURE.

    Given a game's boxscore ID, returns a list of tuples of sets containing
    the starters for each period (quarter or OT) in the game. Mainly for use in
    the get_sparse_lineups and get_dense_lineups functions.

    The ith element of the list returned is a tuple in which the first
    element is the set of the away team's starters for period i+1, and the
    second element is the set of the home team's starters for period i+1.

    :param boxscore_id: A string containing the game's boxscore ID.
    :returns: [(away_set, home_set), ...]
    """

    def get_width(pq_obj):
        """Returns the pixel width of a PyQuery object representing a div.

        :pq_obj: PyQuery object with a style attribute containing its width.
        :returns: Pixel width of the div/element based on obj.attr['style'].
        :rtype: int
        """
        return int(re.search(r'width:(\d+)px', pq_obj.attr['style']).group(1))

    def get_player_intervals(player_pm_div):
        """Returns the widths at which a player was in the game, given a
        PyQuery object representing the player's 'div.player-plusminus'.

        :player_pm_div: PyQuery object representing a div with class
            player-plusminus.
        :returns: List of (start_width, end_width) tuples
        """
        widths = [
            get_width(div) + 1 for div in player_pm_div.children('div').items()
        ]
        in_mask = np.array([
            (div.hasClass('plus') or div.hasClass('minus') or
             div.hasClass('even'))
            for div in player_pm_div.children('div').items()
        ])
        in_mask = np.append(in_mask, not in_mask[-1])
        cum_widths = np.concatenate(([0], np.cumsum(widths)))
        keep = np.insert(np.diff(in_mask), 0, in_mask[0])
        in_mask_keep = in_mask[keep]
        cum_widths_in = cum_widths[keep][in_mask_keep]
        cum_widths_out = cum_widths[keep][~in_mask_keep]
        intervals = list(zip(cum_widths_in, cum_widths_out))
        return intervals

    def per_starters_from_div(div, is_home):
        """Given a PyQuery object representing one team's section on the
        BoxScore plus-minus page, returns a list of sets containing the team's
        starters for each period (quarter or OT) in the game.

        The ith element of the list returned is a set of the given team's
        starters for period i+1.

        :param div: PyQuery object representing a div.
        :param is_home: True when the div represents the home team
        :type is_home: bool
        :returns: [set_q1, set_q2, ...]
        """
        # get player names and start times
        player_names = (div('div.player span')
                        .map(lambda i, e: e.text_content()))
        player_intervals = [get_player_intervals(pm_div) for pm_div in
                            div('div.player-plusminus').items()]

        # convert player names to player IDs
        stats = bs.basic_stats().query('is_home == @is_home')
        name_to_id = stats.set_index('player_name').player_id.to_dict()
        player_ids = [name_to_id[name] for name in player_names]

        # filter to only times that are beginning of the quarter
        player_pers = [
            np.nonzero(
                [any(start <= p_start < end for start, end in intervals)
                 for p_start in per_starts]
            )[0]
            for intervals in player_intervals
        ]

        per_starters = [set() for _ in per_widths]
        for p_id, p_periods in zip(player_ids, player_pers):
            for per in p_periods:
                per_starters[per].add(p_id)

        return per_starters

    bs = sportsref.nba.BoxScore(boxscore_id)
    doc = bs.get_subpage_doc('plus-minus')
    aw_div, hm_div = doc('div.plusminus > div > div').items()

    # get start pixel values for each period
    per_widths = [get_width(ch) + (i > 0) for i, ch in
                  enumerate(hm_div('div.header').eq(0).children().items())]
    per_starts = np.concatenate(([0], np.cumsum(per_widths)[:-1])).tolist()

    # get each team's starters in each period
    aw_starters = per_starters_from_div(aw_div, is_home=False)
    hm_starters = per_starters_from_div(hm_div, is_home=True)

    assert len(aw_starters) == len(hm_starters)
    # TODO: make sure 5 starters for everything

    return list(zip(aw_starters, hm_starters))


def get_sparse_lineups(df):
    """TODO: Docstring for get_sparse_lineups.

    :param df: TODO
    :returns: TODO
    """

    if (set(ALL_LINEUP_COLS) - set(df.columns)):
        df = get_dense_lineups(df)

    all_players = reduce(
        operator.or_, [set(df[c].unique()) for c in ALL_LINEUP_COLS]
    )

    rows = df[ALL_LINEUP_COLS].values
    data = {'{}_in'.format(player_id):
            np.array([player_id in row for row in rows])
            for player_id in all_players}
    sparse_df = pd.DataFrame(data)
    return sparse_df


def get_dense_lineups(df):
    """Returns a new DataFrame based on the one it is passed. Specifically, it
    adds five columns for each team (ten total), where each column has the ID
    of a player on the court during the play.

    This information is figured out sequentially from the game's substitution
    data in the passed DataFrame, so the DataFrame passed as an argument must
    be from a specific BoxScore (rather than a DataFrame of non-consecutive
    plays). That is, the DataFrame must be of the form returned by
    :func:`nba.BoxScore.pbp <nba.BoxScore.pbp>`.

    .. note:: Note that the lineups reflect the teams in the game when the play
        happened, not after the play. For example, if a play is a substitution,
        the lineups for that play will be the lineups before the substituion
        occurs.

    :param df: A DataFrame of a game's play-by-play data.
    :returns: A DataFrame with additional lineup columns.

    """
    # TODO: add this precondition to documentation
    assert df['boxscore_id'].nunique() == 1

    def lineup_dict(aw_lineup, hm_lineup):
        """Returns a dictionary of lineups to be converted to columns.
        Specifically, the columns are 'aw_player1' through 'aw_player5' and
        'hm_player1' through 'hm_player5'.

        :param aw_lineup: The away team's current lineup.
        :param hm_lineup: The home team's current lineup.
        :returns: A dictionary of lineups.
        """
        return {
            '{}_player{}'.format(tm, i+1): player
            for tm, lineup in zip(['aw', 'hm'], [aw_lineup, hm_lineup])
            for i, player in enumerate(lineup)
        }

    def handle_sub(row, aw_lineup, hm_lineup):
        """Modifies the aw_lineup and hm_lineup lists based on the substitution
        that takes place in the given row."""
        assert row['is_sub']
        sub_lineup = hm_lineup if row['sub_team'] == row['home'] else aw_lineup
        try:
            # make the sub
            idx = sub_lineup.index(row['sub_out'])
            sub_lineup[idx] = row['sub_in']
        except ValueError:
            # if the sub was double-entered and it's already been executed...
            if (
                row['sub_in'] in sub_lineup
                and row['sub_out'] not in sub_lineup
            ):
                return aw_lineup, hm_lineup
            # otherwise, let's print and pretend this never happened
            print('ERROR IN SUB IN {}, Q{}, {}: {}'
                  .format(row['boxscore_id'], row['quarter'],
                          row['clock_time'], row['detail']))
            raise
        return aw_lineup, hm_lineup

    per_starters = get_period_starters(df)
    cur_qtr = 0
    aw_lineup, hm_lineup = [], []
    df = df.reset_index(drop=True)
    lineups = [{} for _ in range(df.shape[0])]

    # loop through select plays to determine lineups
    sub_or_per_start = df.is_sub | df.quarter.diff().astype(bool)
    for i, row in df.ix[sub_or_per_start].iterrows():
        if row['quarter'] > cur_qtr:
            # first row in a quarter
            assert row['quarter'] == cur_qtr + 1
            # first, finish up the last quarter's lineups
            if cur_qtr > 0 and not df.ix[i-1, 'is_sub']:
                lineups[i-1] = lineup_dict(aw_lineup, hm_lineup)
            # then, move on to the quarter, and enter the starting lineups
            cur_qtr += 1
            aw_lineup, hm_lineup = map(list, per_starters[cur_qtr-1])
            lineups[i] = lineup_dict(aw_lineup, hm_lineup)
            # if the first play in the quarter is a sub, handle that
            if row['is_sub']:
                aw_lineup, hm_lineup = handle_sub(row, aw_lineup, hm_lineup)
        else:
            # during the quarter
            # update lineups first then change lineups based on subs
            lineups[i] = lineup_dict(aw_lineup, hm_lineup)
            if row['is_sub']:
                aw_lineup, hm_lineup = handle_sub(row, aw_lineup, hm_lineup)

    # create and clean DataFrame
    lineup_df = pd.DataFrame(lineups)
    if lineup_df.iloc[-1].isnull().all():
        lineup_df.iloc[-1] = lineup_dict(aw_lineup, hm_lineup)
    lineup_df = lineup_df.groupby(df.quarter).fillna(method='bfill')

    # fill in NaN's
    bool_mat = lineup_df.isnull()
    mask = bool_mat.any(axis=1)
    if mask.any():
        bs = sportsref.nba.BoxScore(df.boxscore_id[0])
        hm_roster = bs.basic_stats().query('is_home == True').player_id.values

        stats = sportsref.nba.BoxScore(df.boxscore_id.iloc[0]).basic_stats()
        true_mp = pd.Series(
            stats.query('mp > 0')[['player_id', 'mp']]
            .set_index('player_id').to_dict()['mp']
        ) * 60
        calc_mp = pd.Series(
            {p: (df.secs_elapsed.diff() *
                 [p in row for row in lineup_df.values]).sum()
             for p in stats.query('mp > 0').player_id.values})
        diff = true_mp - calc_mp
        players_missing = diff.ix[diff.abs() >= 150]
        missing_df = pd.DataFrame(
            {'secs': players_missing.values,
             'is_home': players_missing.index.isin(hm_roster)},
            index=players_missing.index
        )

        if not missing_df.empty:
            # import ipdb
            # ipdb.set_trace()
            for is_home, group in missing_df.groupby('is_home'):
                player_id = group.index.item()
                tm_cols = (sportsref.nba.pbp.HM_LINEUP_COLS if is_home else
                           sportsref.nba.pbp.AW_LINEUP_COLS)
                row_mask = lineup_df.ix[:, tm_cols].isnull().any(axis=1)
                lineup_df.ix[row_mask, tm_cols] = (
                    lineup_df.ix[row_mask, tm_cols].fillna(player_id).values
                )

    return lineup_df
