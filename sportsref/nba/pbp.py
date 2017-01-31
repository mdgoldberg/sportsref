from builtins import enumerate, int, range

import copy
import operator
import re

import numpy as np
import pandas as pd

import sportsref

PLAYER_RE = r'\w{0,7}\d{2}'

HM_LINEUP_COLS = ['hm_player{}'.format(i) for i in range(1, 6)]
AW_LINEUP_COLS = ['aw_player{}'.format(i) for i in range(1, 6)]
ALL_LINEUP_COLS = AW_LINEUP_COLS + HM_LINEUP_COLS


def parse_play(details, hm, aw, is_hm, yr):
    """Parse play details from a play-by-play string describing a play.

    Assuming valid input, this function returns structured data in a dictionary
    describing the play. If the play detail string was invalid, this function
    returns None.

    :param details: detail string for the play
    :param hm: the ID of the home team
    :param aw: the ID of the away team
    :param is_hm: bool indicating whether the offense is at home
    :param yr: year of the game
    :param returns: dictionary of play attributes or None if invalid
    :rtype: dictionary or None
    """
    # if input isn't a string, return None
    if not isinstance(details, basestring) or not details:
        return None

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
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
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
        p['reb_team'], other = (hm, aw) if is_hm else (aw, hm)
        p['team'] = p['reb_team'] if p['is_oreb'] else other
        p['opp'] = p['reb_team'] if p['is_dreb'] else other
        return p

    # parsing free throws
    ftRE = (r'(?P<ft_shooter>{}) (?P<is_ftm>makes|misses) '
            r'(?P<is_tech_ft>technical )?(?P<is_flag_ft>flagrant )?'
            r'(?P<is_clearpath_ft>clear path )?free throw'
            r'(?: (?P<ft_num>\d+) of (?P<tot_fta>\d+))?').format(PLAYER_RE)
    m = re.match(ftRE, details, re.I)
    if m:
        p['is_fta'] = True
        p.update(m.groupdict())
        p['is_ftm'] = p['is_ftm'] == 'makes'
        p['is_tech_ft'] = bool(p['is_tech_ft'])
        p['is_flag_ft'] = bool(p['is_flag_ft'])
        p['is_clearpath_ft'] = bool(p['is_clearpath_ft'])
        if p['tot_fta']:
            p['tot_fta'] = int(p['tot_fta'])
        if p['ft_num']:
            p['ft_num'] = int(p['ft_num'])
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        return p

    # parsing substitutions
    subRE = (r'(?P<sub_in>{0}) enters the game for '
             r'(?P<sub_out>{0})').format(PLAYER_RE)
    m = re.match(subRE, details, re.I)
    if m:
        p['is_sub'] = True
        p.update(m.groupdict())
        p['sub_team'] = hm if is_hm else aw
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
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
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
        # TODO: is_hm is not to be trusted on fouls
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
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
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
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
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
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
        p['foul_team'] = hm if is_hm else aw
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
        p['is_away_from_ball_foul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foul_team'] = p['opp']
        return p

    # parsing inbound fouls
    inboundRE = (r'Inbound foul by (?P<fouler>{0})'
                 r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(inboundRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_inbound_foul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
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
        p['foul_team'] = hm if is_hm else aw
        return p

    # parsing clear path fouls
    clearPathRE = (r'Clear path foul by (?P<fouler>{0})'
                   r'(?: \(drawn by (?P<drew_foul>{0})\))?').format(PLAYER_RE)
    m = re.match(clearPathRE, details, re.I)
    if m:
        p['is_pf'] = True
        p['is_clear_path_foul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foul_team'] = p['opp']
        return p

    # parsing timeouts
    timeoutRE = r'(?P<timeout_team>.*?) (?:full )?timeout'
    m = re.match(timeoutRE, details, re.I)
    if m:
        p['is_timeout'] = True
        p.update(m.groupdict())
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        isOfficialTO = p['timeout_team'].lower() == 'official'
        p['timeout_team'] = ('Official' if isOfficialTO else
                             sportsref.nba.Season(yr).team_names_to_ids()
                             .get(p['team'], p['team']))
        return p

    # parsing technical fouls
    techRE = (r'(?P<is_hanging>Hanging )?'
              r'(?P<is_taunting>Taunting )?'
              r'(?P<is_ill_def>Ill def )?'
              r'(?P<is_delay>Delay )?'
              r'(?P<is_unsport>Non unsport )?'
              r'tech(?:nical)? foul by '
              r'(?P<fouler>{0}|Team)').format(PLAYER_RE)
    m = re.match(techRE, details, re.I)
    if m:
        p['is_tech_foul'] = True
        p.update(m.groupdict())
        p['is_hanging'] = bool(p['is_hanging'])
        p['is_taunting'] = bool(p['is_taunting'])
        p['is_ill_def'] = bool(p['is_ill_def'])
        p['is_delay'] = bool(p['is_delay'])
        p['is_unsport'] = bool(p['is_unsport'])
        p['foul_team'] = hm if is_hm else aw
        return p

    # parsing ejections
    ejectRE = r'(?P<ejectee>{0}) ejected from game'.format(PLAYER_RE)
    m = re.match(ejectRE, details, re.I)
    if m:
        p['is_ejection'] = True
        p['ejectee_team'] = hm if is_hm else aw
        return p

    # parsing defensive 3 seconds techs
    def3TechRE = (r'(?:Def 3 sec tech foul|Defensive three seconds)'
                  r' by (?P<fouler>{})').format(PLAYER_RE)
    m = re.match(def3TechRE, details, re.I)
    if m:
        p['is_tech_foul'] = True
        p['is_def_three_secs'] = True
        p.update(m.groupdict())
        p['foul_team'] = hm if is_hm else aw
        return p

    # parsing violations
    violRE = (r'Violation by (?P<violator>{0}|Team) '
              r'\((?P<viol_type>.*)\)').format(PLAYER_RE)
    m = re.match(violRE, details, re.I)
    if m:
        p['is_viol'] = True
        p.update(m.groupdict())
        p['viol_team'] = hm if is_hm else aw
        return p

    p['is_error'] = True
    return p


def clean_features(df):
    """Fixes up columns of the passed DataFrame, such as casting T/F columns to
    boolean and filling in NaNs for team and opp.

    :param df: DataFrame of play-by-play data.
    :returns: Dataframe with cleaned columns.
    """
    df = copy.deepcopy(df)
    # make indicator columns boolean type (and fill in NaNs)
    boolVals = set([True, False, None, np.nan])
    for c in df:
        if set(df[c].unique()[:5]) <= boolVals:
            df[c] = df[c].map(lambda x: x is True)

    # fix free throw columns on technicals
    df.ix[df.is_tech_ft, ['ft_num', 'tot_fta']] = 1

    # fill in NaN's in team, opp columns except for jump balls
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
        aw_players = set()
        hm_players = set()

        is_hm = play['is_home_play']
        home_on_off = play['home'] == play['team']
        off_players = hm_players if home_on_off else aw_players
        def_players = aw_players if home_on_off else hm_players
        stats = sportsref.nba.BoxScore(play['boxscore_id']).basic_stats()
        hm_roster = stats.groupby('is_home').player_id.get_group(True).values
        if play['is_fga']:
            off_players.add(play['shooter'])
        if play['is_reb']:
            reb_players = hm_players if is_hm else aw_players
            reb_players.add(play['rebounder'])
        if play['is_assist']:
            off_players.add(play['assister'])
        if play['is_steal']:
            def_players.add(play['stealer'])
        if play['is_block']:
            def_players.add(play['blocker'])
        if play['is_to']:
            off_players.add(play['to_by'])
        if play['is_fta']:
            off_players.add(play['ft_shooter'])
        if play['is_pf']:
            foul_on_hm = play['fouler'] in hm_roster
            foul_players = (hm_players if foul_on_hm else aw_players)
            foul_players.add(play['fouler'])
            if pd.notnull(play['drew_foul']):
                drawn_players = (aw_players if foul_on_hm else hm_players)
                drawn_players.add(play['drew_foul'])
        if play['is_sub']:
            sub_players = hm_players if is_hm else aw_players
            sub_players.add(play['sub_out'])
        if False and play['is_jump_ball']:
            hm_players.add(play['home_jumper'])
            aw_players.add(play['away_jumper'])

        aw_players = [p for p in aw_players if re.match(PLAYER_RE, p)]
        hm_players = [p for p in hm_players if re.match(PLAYER_RE, p)]
        return aw_players, hm_players

    # create a mapping { quarter => (away_starters, home_starters) }
    n_periods = df.quarter.nunique()
    period_starters = [(set(), set()) for _ in range(n_periods)]

    # fill out this mapping quarter by quarter
    for qtr, group in df.groupby(df.quarter):
        aw_starters, hm_starters = period_starters[qtr-1]
        aw_exclude, hm_exclude = set(), set()
        for i, row in group.iterrows():
            new_aw_starters, new_hm_starters = players_from_play(row)
            # make sure players who sub in don't count as starters
            if row['is_sub']:
                starters = hm_starters if row['is_home_play'] else aw_starters
                exclude = hm_exclude if row['is_home_play'] else aw_exclude
                if row['sub_in'] not in starters:
                    exclude.add(row['sub_in'])
            # update overall sets for the quarter
            hm_starters.update(new_hm_starters)
            hm_starters -= hm_exclude
            aw_starters.update(new_aw_starters)
            aw_starters -= aw_exclude
            if len(hm_starters) >= 5 and len(aw_starters) >= 5:
                break

        if len(hm_starters) != 5 or len(aw_starters) != 5:
            print('WARNING: wrong number of starters for a team in Q{} of {}'
                  .format(qtr, df.boxscore_id.iloc[0]))

    return period_starters


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
        sub_lineup = hm_lineup if row['is_home_play'] else aw_lineup
        try:
            # make the sub
            idx = sub_lineup.index(row['sub_out'])
            sub_lineup[idx] = row['sub_in']
        except ValueError:
            # if the sub was double-entered and it's already been executed...
            if row['sub_in'] in sub_lineup:
                return aw_lineup, hm_lineup
            # otherwise, let's print and pretend this never happened
            print('ERROR IN SUB IN {}, Q{}, {}: {}'
                  .format(row['boxscore_id'], row['quarter'],
                          row['clock_time'], row['detail']))
            pass
        return aw_lineup, hm_lineup

    per_starters = get_period_starters(df)
    cur_qtr = 0
    aw_lineup, hm_lineup = [], []
    df = df.reset_index(drop=True)
    lineups = [{} for _ in range(df.shape[0])]

    sub_or_per_start = df.is_sub | df.quarter.diff().astype(bool)
    for i, row in df.ix[sub_or_per_start].iterrows():
        if row['quarter'] > cur_qtr:
            # first row in a quarter
            assert row['quarter'] == cur_qtr + 1
            # first, finish up the last quarter's lineups
            if cur_qtr > 0:
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

    lineup_df = pd.DataFrame(lineups)
    if lineup_df.iloc[-1].isnull().all():
        lineup_df.iloc[-1] = lineup_dict(aw_lineup, hm_lineup)
    lineup_df.fillna(method='bfill', inplace=True)

    bool_mat = lineup_df.isnull()
    mask = bool_mat.any(axis=1)
    if mask.sum():
        print 'found some nulls in {}'.format(df.boxscore_id.iloc[0])
        n_missing = bool_mat.sum(axis=1)
        secs_missing = (df.secs_elapsed.diff()[mask] * n_missing).sum()

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
        players_missing = diff.ix[diff.abs() > 20]

        if not players_missing.empty:
            player_id = players_missing.index.item()
            if diff[player_id] != secs_missing:
                import ipdb
                ipdb.set_trace()
            lineup_df = lineup_df.fillna(player_id)

    return lineup_df
