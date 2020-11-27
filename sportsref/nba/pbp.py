import re

import numpy as np
import pandas as pd

import sportsref

HM_LINEUP_COLS = ["hm_player{}".format(i) for i in range(1, 6)]
AW_LINEUP_COLS = ["aw_player{}".format(i) for i in range(1, 6)]
ALL_LINEUP_COLS = AW_LINEUP_COLS + HM_LINEUP_COLS

PLAYER_RE = r"\w{0,7}\d{2}"

# parsing field goal attempts
shot_re = (
    rf"(?P<shooter>{PLAYER_RE}) "
    r"(?P<is_fgm>makes|misses) "
    r"(?P<is_three>2|3)\-pt "
    r"(?P<shot_type>jump shot|hook shot|layup|dunk) "
    r"(?:from (?P<shot_dist>\d+) ft|at rim)"
)
assist_re = rf" \(assist by (?P<assister>{PLAYER_RE})\)"
block_re = rf" \(block by (?P<blocker>{PLAYER_RE})\)"
SHOT_RE = re.compile(rf"{shot_re}(?:{assist_re}|{block_re})?", flags=re.I)

# parsing jump balls
jump_re = (
    rf"Jump ball: (?P<away_jumper>{PLAYER_RE}) vs\. (?P<home_jumper>{PLAYER_RE})"
    rf"(?: \((?P<gains_poss>{PLAYER_RE}) gains possession\))?"
)
JUMP_RE = re.compile(jump_re, flags=re.I)

# parsing rebounds
reb_re = rf"(?P<is_oreb>Offensive|Defensive) rebound by (?P<rebounder>{PLAYER_RE}|Team)"
REB_RE = re.compile(reb_re, flags=re.I)

# parsing free throws
ft_re = (
    rf"(?P<ft_shooter>{PLAYER_RE}) (?P<is_ftm>makes|misses) "
    r"(?P<is_tech_fta>technical )?(?P<is_flag_fta>flagrant )?"
    r"(?P<is_clearpath_fta>clear path )?free throw"
    r"(?: (?P<fta_num>\d+) of (?P<tot_fta>\d+))?"
)
FT_RE = re.compile(ft_re, flags=re.I)

# parsing substitutions
sub_re = rf"(?P<sub_in>{PLAYER_RE}) enters the game for (?P<sub_out>{PLAYER_RE})"
SUB_RE = re.compile(sub_re, flags=re.I)

# parsing turnovers
to_reasons = rf"(?P<to_type>[^;]+)(?:; steal by (?P<stealer>{PLAYER_RE}))?"
to_re = rf"Turnover by (?P<to_by>{PLAYER_RE}|Team) \((?:{to_reasons})\)"
TO_RE = re.compile(to_re, flags=re.I)

# parsing shooting fouls
shot_foul_re = (
    r"Shooting(?P<is_block_foul> block)? foul "
    rf"by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
SHOT_FOUL_RE = re.compile(shot_foul_re, flags=re.I)

# parsing offensive fouls
off_foul_re = (
    r"Offensive(?P<is_charge> charge)? foul "
    rf"by (?P<to_by>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
OFF_FOUL_RE = re.compile(off_foul_re, flags=re.I)

# parsing personal fouls
foul_re = (
    r"Personal (?P<is_take_foul>take )?(?P<is_block_foul>block )?"
    rf"foul by (?P<fouler>{PLAYER_RE})(?: \(drawn by "
    rf"(?P<drew_foul>{PLAYER_RE})\))?"
)
FOUL_RE = re.compile(foul_re, flags=re.I)

# parsing loose ball fouls
loose_ball_re = (
    rf"Loose ball foul by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
LOOSE_BALL_RE = re.compile(loose_ball_re, flags=re.I)

# parsing away from play fouls
away_from_ball_re = (
    rf"Away from play foul by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
AWAY_FROM_BALL_RE = re.compile(away_from_ball_re, flags=re.I)

# parsing inbound fouls
inbound_re = (
    rf"Inbound foul by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
INBOUND_RE = re.compile(inbound_re, flags=re.I)

# parsing flagrant fouls
flagrant_re = (
    rf"Flagrant foul type (?P<flag_type>1|2) by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
FLAGRANT_RE = re.compile(flagrant_re, flags=re.I)

# parsing clear path fouls
clear_path_re = (
    rf"Clear path foul by (?P<fouler>{PLAYER_RE})"
    rf"(?: \(drawn by (?P<drew_foul>{PLAYER_RE})\))?"
)
CLEAR_PATH_RE = re.compile(clear_path_re, flags=re.I)

# parsing timeouts
timeout_re = r"(?P<timeout_team>.*?) (?:full )?timeout"
TIMEOUT_RE = re.compile(timeout_re, flags=re.I)

# parsing technical fouls
tech_re = (
    r"(?P<is_hanging>Hanging )?"
    r"(?P<is_taunting>Taunting )?"
    r"(?P<is_ill_def>Ill def )?"
    r"(?P<is_delay>Delay )?"
    r"(?P<is_unsport>Non unsport )?"
    r"tech(?:nical)? foul by "
    rf"(?P<tech_fouler>{PLAYER_RE}|Team)"
)
TECH_RE = re.compile(tech_re, flags=re.I)

# parsing ejections
eject_re = rf"(?P<ejectee>{PLAYER_RE}|Team) ejected from game"
EJECT_RE = re.compile(eject_re, flags=re.I)

# parsing defensive 3 seconds techs
def3_tech_re = (
    r"(?:Def 3 sec tech foul|Defensive three seconds)"
    rf" by (?P<tech_fouler>{PLAYER_RE})"
)
DEF3_TECH_RE = re.compile(def3_tech_re, flags=re.I)

# parsing violations
viol_re = rf"Violation by (?P<violator>{PLAYER_RE}|Team) \((?P<viol_type>.*)\)"
VIOL_RE = re.compile(viol_re, flags=re.I)


def sparse_lineup_cols(df):
    regex = "{}_in".format(PLAYER_RE)
    return [c for c in df.columns if re.match(regex, c)]


def parse_play(boxscore_id, details, is_home):
    """Parse play details from a play-by-play string describing a play.

    Assuming valid input, this function returns structured data in a dictionary
    describing the play. If the play detail string was invalid, this function
    returns None.

    :param boxscore_id: the boxscore ID of the play
    :param details: detail string for the play
    :param is_home: bool indicating whether the offense is at home
    :param returns: dictionary of play attributes or None if invalid
    :rtype: dictionary or None
    """
    # if input isn't a string, return None
    if not details or not isinstance(details, str):
        return None

    bs = sportsref.nba.BoxScore(boxscore_id)
    aw, hm = bs.away(), bs.home()
    season = sportsref.nba.Season(bs.season())
    hm_roster = set(bs.basic_stats().query("is_home == True").player_id.values)

    play = {}
    play["detail"] = details
    play["home"] = hm
    play["away"] = aw
    play["is_home_play"] = is_home

    match = re.match(SHOT_RE, details)
    if match:
        play["is_fga"] = True
        play.update(match.groupdict())
        play["shot_dist"] = play["shot_dist"] if play["shot_dist"] is not None else 0
        play["shot_dist"] = int(play["shot_dist"])
        play["is_fgm"] = play["is_fgm"] == "makes"
        play["is_three"] = play["is_three"] == "3"
        play["is_assist"] = pd.notnull(play.get("assister"))
        play["is_block"] = pd.notnull(play.get("blocker"))
        shooter_home = play["shooter"] in hm_roster
        play["off_team"] = hm if shooter_home else aw
        play["def_team"] = aw if shooter_home else hm
        return play

    match = re.match(JUMP_RE, details)
    if match:
        play["is_jump_ball"] = True
        play.update(match.groupdict())
        return play

    match = re.match(REB_RE, details)
    if match:
        play["is_reb"] = True
        play.update(match.groupdict())
        play["is_oreb"] = play["is_oreb"].lower() == "offensive"
        play["is_dreb"] = not play["is_oreb"]
        play["is_team_rebound"] = play["rebounder"] == "Team"
        if play["is_team_rebound"]:
            play["reb_team"], other = (hm, aw) if is_home else (aw, hm)
        else:
            reb_home = play["rebounder"] in hm_roster
            play["reb_team"], other = (hm, aw) if reb_home else (aw, hm)
        play["off_team"] = play["reb_team"] if play["is_oreb"] else other
        play["def_team"] = play["reb_team"] if play["is_dreb"] else other
        return play

    match = re.match(FT_RE, details)
    if match:
        play["is_fta"] = True
        play.update(match.groupdict())
        play["is_ftm"] = play["is_ftm"] == "makes"
        play["is_tech_fta"] = bool(play["is_tech_fta"])
        play["is_flag_fta"] = bool(play["is_flag_fta"])
        play["is_clearpath_fta"] = bool(play["is_clearpath_fta"])
        play["is_pf_fta"] = not play["is_tech_fta"]
        if play["tot_fta"]:
            play["tot_fta"] = int(play["tot_fta"])
        if play["fta_num"]:
            play["fta_num"] = int(play["fta_num"])
        ft_home = play["ft_shooter"] in hm_roster
        play["fta_team"] = hm if ft_home else aw
        if not play["is_tech_fta"]:
            play["off_team"] = hm if ft_home else aw
            play["def_team"] = aw if ft_home else hm
        return play

    match = re.match(SUB_RE, details)
    if match:
        play["is_sub"] = True
        play.update(match.groupdict())
        sub_home = play["sub_in"] in hm_roster or play["sub_out"] in hm_roster
        play["sub_team"] = hm if sub_home else aw
        return play

    match = re.match(TO_RE, details)
    if match:
        play["is_to"] = True
        play.update(match.groupdict())
        play["to_type"] = play["to_type"].lower()
        if play["to_type"] == "offensive foul":
            return None
        play["is_steal"] = pd.notnull(play["stealer"])
        play["is_travel"] = play["to_type"] == "traveling"
        play["is_shot_clock_viol"] = play["to_type"] == "shot clock"
        play["is_oob"] = play["to_type"] == "step out of bounds"
        play["is_three_sec_viol"] = play["to_type"] == "3 sec"
        play["is_backcourt_viol"] = play["to_type"] == "back court"
        play["is_off_goaltend"] = play["to_type"] == "offensive goaltending"
        play["is_double_dribble"] = play["to_type"] == "dbl dribble"
        play["is_discont_dribble"] = play["to_type"] == "discontinued dribble"
        play["is_carry"] = play["to_type"] == "palming"
        if play["to_by"] == "Team":
            play["off_team"] = hm if is_home else aw
            play["def_team"] = aw if is_home else hm
        else:
            to_home = play["to_by"] in hm_roster
            play["off_team"] = hm if to_home else aw
            play["def_team"] = aw if to_home else hm
        return play

    match = re.match(SHOT_FOUL_RE, details)
    if match:
        play["is_pf"] = True
        play["is_shot_foul"] = True
        play.update(match.groupdict())
        play["is_block_foul"] = bool(play["is_block_foul"])
        foul_on_home = play["fouler"] in hm_roster
        play["off_team"] = aw if foul_on_home else hm
        play["def_team"] = hm if foul_on_home else aw
        play["foul_team"] = play["def_team"]
        return play

    match = re.match(OFF_FOUL_RE, details)
    if match:
        play["is_pf"] = True
        play["is_off_foul"] = True
        play["is_to"] = True
        play["to_type"] = "offensive foul"
        play.update(match.groupdict())
        play["is_charge"] = bool(play["is_charge"])
        play["fouler"] = play["to_by"]
        foul_on_home = play["fouler"] in hm_roster
        play["off_team"] = hm if foul_on_home else aw
        play["def_team"] = aw if foul_on_home else hm
        play["foul_team"] = play["off_team"]
        return play

    match = re.match(FOUL_RE, details)
    if match:
        play["is_pf"] = True
        play.update(match.groupdict())
        play["is_take_foul"] = bool(play["is_take_foul"])
        play["is_block_foul"] = bool(play["is_block_foul"])
        foul_on_home = play["fouler"] in hm_roster
        play["off_team"] = aw if foul_on_home else hm
        play["def_team"] = hm if foul_on_home else aw
        play["foul_team"] = play["def_team"]
        return play

    # TODO: parsing double personal fouls
    # double_foul_re = (r'Double personal foul by (?P<fouler1>{0}) and '
    #                   r'(?P<fouler2>{0})').format(PLAYER_RE)
    # m = re.match(double_Foul_re, details)
    # if m:
    #     p['is_pf'] = True
    #     p.update(m.groupdict())
    #     p['off_team'] =

    match = re.match(LOOSE_BALL_RE, details)
    if match:
        play["is_pf"] = True
        play["is_loose_ball_foul"] = True
        play.update(match.groupdict())
        foul_home = play["fouler"] in hm_roster
        play["foul_team"] = hm if foul_home else aw
        return play

    # parsing punching fouls
    # TODO

    match = re.match(AWAY_FROM_BALL_RE, details)
    if match:
        play["is_pf"] = True
        play["is_away_from_play_foul"] = True
        play.update(match.groupdict())
        foul_on_home = play["fouler"] in hm_roster
        # TODO: figure out who had the ball based on previous play
        play["foul_team"] = hm if foul_on_home else aw
        return play

    match = re.match(INBOUND_RE, details)
    if match:
        play["is_pf"] = True
        play["is_inbound_foul"] = True
        play.update(match.groupdict())
        foul_on_home = play["fouler"] in hm_roster
        play["off_team"] = aw if foul_on_home else hm
        play["def_team"] = hm if foul_on_home else aw
        play["foul_team"] = play["def_team"]
        return play

    match = re.match(FLAGRANT_RE, details)
    if match:
        play["is_pf"] = True
        play["is_flagrant"] = True
        play.update(match.groupdict())
        foul_on_home = play["fouler"] in hm_roster
        play["foul_team"] = hm if foul_on_home else aw
        return play

    match = re.match(CLEAR_PATH_RE, details)
    if match:
        play["is_pf"] = True
        play["is_clear_path_foul"] = True
        play.update(match.groupdict())
        foul_on_home = play["fouler"] in hm_roster
        play["off_team"] = aw if foul_on_home else hm
        play["def_team"] = hm if foul_on_home else aw
        play["foul_team"] = play["def_team"]
        return play

    match = re.match(TIMEOUT_RE, details)
    if match:
        play["is_timeout"] = True
        play.update(match.groupdict())
        isOfficialTO = play["timeout_team"].lower() == "official"
        name_to_id = season.team_names_to_ids()
        play["timeout_team"] = (
            "Official"
            if isOfficialTO
            else name_to_id.get(hm, name_to_id.get(aw, play["timeout_team"]))
        )
        return play

    match = re.match(TECH_RE, details)
    if match:
        play["is_tech_foul"] = True
        play.update(match.groupdict())
        play["is_hanging"] = bool(play["is_hanging"])
        play["is_taunting"] = bool(play["is_taunting"])
        play["is_ill_def"] = bool(play["is_ill_def"])
        play["is_delay"] = bool(play["is_delay"])
        play["is_unsport"] = bool(play["is_unsport"])
        foul_on_home = play["tech_fouler"] in hm_roster
        play["foul_team"] = hm if foul_on_home else aw
        return play

    match = re.match(EJECT_RE, details)
    if match:
        play["is_ejection"] = True
        play.update(match.groupdict())
        if play["ejectee"] == "Team":
            play["ejectee_team"] = hm if is_home else aw
        else:
            eject_home = play["ejectee"] in hm_roster
            play["ejectee_team"] = hm if eject_home else aw
        return play

    match = re.match(DEF3_TECH_RE, details)
    if match:
        play["is_tech_foul"] = True
        play["is_def_three_secs"] = True
        play.update(match.groupdict())
        foul_on_home = play["tech_fouler"] in hm_roster
        play["off_team"] = aw if foul_on_home else hm
        play["def_team"] = hm if foul_on_home else aw
        play["foul_team"] = play["def_team"]
        return play

    match = re.match(VIOL_RE, details)
    if match:
        play["is_viol"] = True
        play.update(match.groupdict())
        if play["viol_type"] == "kicked_ball":
            play["is_to"] = True
            play["to_by"] = play["violator"]
        if play["violator"] == "Team":
            play["viol_team"] = hm if is_home else aw
        else:
            viol_home = play["violator"] in hm_roster
            play["viol_team"] = hm if viol_home else aw
        return play

    play["is_error"] = True
    return play


def clean_features(df):
    """Fixes up columns of the passed DataFrame, such as casting T/F columns to
    boolean and filling in NaNs for team and opp.

    :param df: DataFrame of play-by-play data.
    :returns: Dataframe with cleaned columns.
    """
    df = pd.DataFrame(df)

    bool_vals = set([True, False, None, np.nan])
    sparse_cols = sparse_lineup_cols(df)
    for col in df:

        # make indicator columns boolean type (and fill in NaNs)
        if set(df[col].unique()[:5]) <= bool_vals:
            df[col] = df[col] == True  # noqa

        # fill NaN's in sparse lineup columns to 0
        elif col in sparse_cols:
            df[col] = df[col].fillna(0)

    # fix free throw columns on technicals
    df.loc[df.is_tech_fta, ["fta_num", "tot_fta"]] = 1

    # fill in NaN's/fix off_team and def_team columns
    df.off_team.fillna(method="bfill", inplace=True)
    df.def_team.fillna(method="bfill", inplace=True)
    df.off_team.fillna(method="ffill", inplace=True)
    df.def_team.fillna(method="ffill", inplace=True)

    return df


def clean_multigame_features(df):
    """TODO: Docstring for clean_multigame_features.

    :df: TODO
    :returns: TODO
    """
    df = pd.DataFrame(df)
    if df.index.value_counts().max() > 1:
        df.reset_index(drop=True, inplace=True)

    df = clean_features(df)

    # if it's many games in one DataFrame, make poss_id and play_id unique
    for col in ("play_id", "poss_id"):
        diffs = df[col].diff().fillna(0)
        if (diffs < 0).any():
            new_col = np.cumsum(diffs.astype(bool))  # noqa
            df.eval("{} = @new_col".format(col), inplace=True)

    return df


def get_period_starters(df):
    """TODO"""

    def players_from_play(play):
        """Figures out what players are in the game based on the players
        mentioned in a play. Returns away and home players as two sets.

        :param play: A dictionary representing a parsed play.
        :returns: (aw_players, hm_players)
        :rtype: tuple of lists
        """
        # if it's a tech FT from between periods, don't count this play
        if play["clock_str"] == "12:00.0" and (
            play.get("is_tech_foul") or play.get("is_tech_fta")
        ):
            return [], []

        stats = sportsref.nba.BoxScore(play["boxscore_id"]).basic_stats()
        home_grouped = stats.groupby("is_home")
        hm_roster = set(home_grouped.player_id.get_group(True).values)
        aw_roster = set(home_grouped.player_id.get_group(False).values)
        player_keys = [
            "assister",
            "away_jumper",
            "blocker",
            "drew_foul",
            "fouler",
            "ft_shooter",
            "gains_poss",
            "home_jumper",
            "rebounder",
            "shooter",
            "stealer",
            "sub_in",
            "sub_out",
            "to_by",
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
        aw_starters, hm_starters = period_starters[qtr - 1]
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
            print(
                "WARNING: wrong number of starters for a team in Q{} of {}".format(
                    qtr, df.boxscore_id.iloc[0]
                )
            )

    return period_starters


def get_sparse_lineups(df):
    """TODO: Docstring for get_sparse_lineups.

    :param df: TODO
    :returns: TODO
    """

    # get the lineup data using get_dense_lineups if necessary
    if set(ALL_LINEUP_COLS) - set(df.columns):
        lineup_df = get_dense_lineups(df)
    else:
        lineup_df = df[ALL_LINEUP_COLS]

    # create the sparse representation
    hm_lineups = lineup_df[HM_LINEUP_COLS].values
    aw_lineups = lineup_df[AW_LINEUP_COLS].values
    # +1 for home, -1 for away
    hm_df = pd.DataFrame(
        [
            {"{}_in".format(player_id): 1 for player_id in lineup}
            for lineup in hm_lineups
        ],
        dtype=int,
    )
    aw_df = pd.DataFrame(
        [
            {"{}_in".format(player_id): -1 for player_id in lineup}
            for lineup in aw_lineups
        ],
        dtype=int,
    )
    sparse_df = pd.concat((hm_df, aw_df), axis=1).fillna(0)
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
    assert df["boxscore_id"].nunique() == 1

    def lineup_dict(aw_lineup, hm_lineup):
        """Returns a dictionary of lineups to be converted to columns.
        Specifically, the columns are 'aw_player1' through 'aw_player5' and
        'hm_player1' through 'hm_player5'.

        :param aw_lineup: The away team's current lineup.
        :param hm_lineup: The home team's current lineup.
        :returns: A dictionary of lineups.
        """
        return {
            "{}_player{}".format(tm, i + 1): player
            for tm, lineup in zip(["aw", "hm"], [aw_lineup, hm_lineup])
            for i, player in enumerate(lineup)
        }

    def handle_sub(row, aw_lineup, hm_lineup):
        """Modifies the aw_lineup and hm_lineup lists based on the substitution
        that takes place in the given row."""
        assert row["is_sub"]
        sub_lineup = hm_lineup if row["sub_team"] == row["home"] else aw_lineup
        try:
            # make the sub
            idx = sub_lineup.index(row["sub_out"])
            sub_lineup[idx] = row["sub_in"]
        except ValueError:
            # if the sub was double-entered and it's already been executed...
            if row["sub_in"] in sub_lineup and row["sub_out"] not in sub_lineup:
                return aw_lineup, hm_lineup
            # otherwise, let's print and pretend this never happened
            print(
                "ERROR IN SUB IN {}, Q{}, {}: {}".format(
                    row["boxscore_id"], row["quarter"], row["clock_str"], row["detail"]
                )
            )
            raise
        return aw_lineup, hm_lineup

    per_starters = get_period_starters(df)
    cur_qtr = 0
    aw_lineup, hm_lineup = [], []
    df = df.reset_index(drop=True)
    lineups = [{} for _ in range(df.shape[0])]

    # loop through select plays to determine lineups
    sub_or_per_start = df.is_sub | df.quarter.diff().astype(bool)
    for i, row in df.loc[sub_or_per_start].iterrows():
        if row["quarter"] > cur_qtr:
            # first row in a quarter
            assert row["quarter"] == cur_qtr + 1
            # first, finish up the last quarter's lineups
            if cur_qtr > 0 and not df.loc[i - 1, "is_sub"]:
                lineups[i - 1] = lineup_dict(aw_lineup, hm_lineup)
            # then, move on to the quarter, and enter the starting lineups
            cur_qtr += 1
            aw_lineup, hm_lineup = list(map(list, per_starters[cur_qtr - 1]))
            lineups[i] = lineup_dict(aw_lineup, hm_lineup)
            # if the first play in the quarter is a sub, handle that
            if row["is_sub"]:
                aw_lineup, hm_lineup = handle_sub(row, aw_lineup, hm_lineup)
        else:
            # during the quarter
            # update lineups first then change lineups based on subs
            lineups[i] = lineup_dict(aw_lineup, hm_lineup)
            if row["is_sub"]:
                aw_lineup, hm_lineup = handle_sub(row, aw_lineup, hm_lineup)

    # create and clean DataFrame
    lineup_df = pd.DataFrame(lineups)
    if lineup_df.iloc[-1].isnull().all():
        lineup_df.iloc[-1] = lineup_dict(aw_lineup, hm_lineup)
    lineup_df = lineup_df.groupby(df.quarter).fillna(method="bfill")

    # fill in NaN's based on minutes played
    bool_mat = lineup_df.isnull()
    mask = bool_mat.any(axis=1)
    if mask.any():
        bs = sportsref.nba.BoxScore(df.boxscore_id[0])
        # first, get the true minutes played from the box score
        stats = sportsref.nba.BoxScore(df.boxscore_id.iloc[0]).basic_stats()
        true_mp = (
            pd.Series(
                stats.query("mp > 0")[["player_id", "mp"]]
                .set_index("player_id")
                .to_dict()["mp"]
            )
            * 60
        )
        # next, calculate minutes played based on the lineup data
        calc_mp = pd.Series(
            {
                p: (
                    df.secs_elapsed.diff() * [p in row for row in lineup_df.values]
                ).sum()
                for p in stats.query("mp > 0").player_id.values
            }
        )
        # finally, figure which players are missing minutes
        diff = true_mp - calc_mp
        players_missing = diff.loc[diff.abs() >= 150]
        hm_roster = bs.basic_stats().query("is_home == True").player_id.values
        missing_df = pd.DataFrame(
            {
                "secs": players_missing.values,
                "is_home": players_missing.index.isin(hm_roster),
            },
            index=players_missing.index,
        )

        if missing_df.empty:
            # TODO: log this as a warning (or error?)
            print(
                "There are NaNs in the lineup data, but no players were "
                "found to be missing significant minutes"
            )
        else:
            # import ipdb
            # ipdb.set_trace()
            for is_home, group in missing_df.groupby("is_home"):
                player_id = group.index.item()
                tm_cols = (
                    sportsref.nba.pbp.HM_LINEUP_COLS
                    if is_home
                    else sportsref.nba.pbp.AW_LINEUP_COLS
                )
                row_mask = lineup_df[tm_cols].isnull().any(axis=1)
                lineup_df.loc[row_mask, tm_cols] = (
                    lineup_df.loc[row_mask, tm_cols].fillna(player_id).values
                )

    return lineup_df
