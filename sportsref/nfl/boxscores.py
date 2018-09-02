import future
import future.utils

import re
import datetime

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'BoxScore',
]


@sportsref.decorators.memoize
def get_season_boxscores_IDs(year, past_only=True):
    """Returns a series of boxscore IDs for a given season.

    :year: The year of the season in question (as an int).
    :returns: A pandas series of boxscore IDs indexed by week number
    """
    url = sportsref.nfl.BASE_URL + '/years/{}/games.htm'.format(year)
    doc = pq(sportsref.utils.get_html(url))
    table = doc('table#games')
    df = sportsref.utils.parse_table(table)
    if past_only:
         df = df[(df['pts_win'].notnull()) & (df['gametime'].notnull())]
    if df['week_num'].dtype == 'O':
        df = df[df['week_num'].notnull()]
        df['week_num'] = df['week_num'].replace(to_replace={'WildCard': '18',
                                                            'Division': '19',
                                                            'ConfChamp':'20',
                                                            'SuperBowl':'21'})
        df = df[~df['week_num'].str.contains('Pre', na=False)]
        df['week_num'] = df['week_num'].apply(pd.to_numeric)
    df.set_index(['week_num'], inplace=True)
    return df['boxscore_id']

@sportsref.decorators.memoize
def get_future_boxscores_info(year):
    """Returns a dataframe of future games with basic game info.
    """
    url = sportsref.nfl.BASE_URL + '/years/{}/games.htm'.format(year)
    doc = pq(sportsref.utils.get_html(url))
    table = doc('table#games')
    df = sportsref.utils.parse_table(table)
    df = df[df['week_num'].apply(lambda x: type(x)!=str)].reset_index(drop=True)
    df['season'] = year
    df['week'] = df['week_num'].astype(int)
    df['date'] = df['boxscore_id'].apply(lambda x: BoxScore(x).date())
    df['weekday'] = df['boxscore_id'].apply(lambda x: BoxScore(x).weekday())
    df['start_time'] = df['gametime'].str.lower()
    df = df[(df['pts_win'].isnull()) & (df['gametime'].notnull())]
    cols_rename = {
        'loser':'home',
        'winner':'away',
        'home_team':'home',
        'visitor_team':'away',}
    df = df.rename(columns=cols_rename)
    cols = ['season','week','boxscore_id','date','weekday','start_time','home','away']
    df = df[cols].reset_index(drop=True)
    return df


class BoxScore(
    future.utils.with_metaclass(sportsref.decorators.Cached, object)
):

    def __init__(self, boxscore_id):
        self.boxscore_id = boxscore_id

    def __eq__(self, other):
        return self.boxscore_id == other.boxscore_id

    def __hash__(self):
        return hash(self.boxscore_id)

    def __repr__(self):
        return 'BoxScore({})'.format(self.boxscore_id)

    def __str__(self):
        return '{} Week {}: {} @ {}'.format(
            self.season(), self.week(), self.away(), self.home()
        )

    def __reduce__(self):
        return BoxScore, (self.boxscore_id,)

    @sportsref.decorators.memoize
    def get_doc(self):
        url = (sportsref.nfl.BASE_URL +
               '/boxscores/{}.htm'.format(self.boxscore_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def date(self):
        """
        Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.boxscore_id)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoize
    def weekday(self):
        """
        Returns the day of the week on which the game occurred.
        :returns: String representation of the day of the week for the game.
        """
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoize
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        relURL = table('tr').eq(2)('a').eq(2).attr['href']
        home = sportsref.utils.rel_url_to_id(relURL)
        return home

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        relURL = table('tr').eq(1)('a').eq(2).attr['href']
        away = sportsref.utils.rel_url_to_id(relURL)
        return away

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        home_score = table('tr').eq(2)('td')[-1].text_content()
        return int(home_score)

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        away_score = table('tr').eq(1)('td')[-1].text_content()
        return int(away_score)

    @sportsref.decorators.memoize
    def winner(self):
        """Returns the team ID of the winning team. Returns NaN if a tie."""
        hmScore = self.home_score()
        awScore = self.away_score()
        if hmScore > awScore:
            return self.home()
        elif hmScore < awScore:
            return self.away()
        else:
            return np.nan

    @sportsref.decorators.memoize
    def week(self):
        """Returns the week in which this game took place. 18 is WC round, 19
        is Div round, 20 is CC round, 21 is SB.
        :returns: Integer from 1 to 21.
        """
        doc = self.get_doc()
        raw = doc('div#div_other_scores h2 a').attr['href']
        match = re.match(
            r'/years/{}/week_(\d+)\.htm'.format(self.season()), raw
        )
        if match:
            return int(match.group(1))
        else:
            return 21  # super bowl is week 21

    @sportsref.decorators.memoize
    def season(self):
        """
        Returns the year ID of the season in which this game took place.
        Useful for week 17 January games.

        :returns: An int representing the year of the season.
        """
        date = self.date()
        return date.year - 1 if date.month <= 3 else date.year

    @sportsref.decorators.memoize
    def starters(self):
        """Returns a DataFrame where each row is an entry in the starters table
        from PFR.

        The columns are:
        * player_id - the PFR player ID for the player (note that this column
        is not necessarily all unique; that is, one player can be a starter in
        multiple positions, in theory).
        * player_name - the listed name of the player; this too is not
        necessarily unique.
        * position - the position at which the player started for their team.
        * team - the team for which the player started.
        * home - True if the player's team was at home, False if they were away
        * offense - True if the player is starting on an offensive position,
        False if defense.

        :returns: A pandas DataFrame. See the description for details.
        """
        doc = self.get_doc()
        h = doc('#home_starters')
        a = doc('#vis_starters')
        data = []
        for h, table in enumerate((a, h)):
            if h: team = self.home()
            else: team = self.away()
            #team = self.home() if h else self.away()
            for i, row in enumerate(table('tbody tr').items()):
                datum = {}
                # few cases where starters table has a blank name
                if len(row('a')) > 0:
                    datum['player_id'] = sportsref.utils.rel_url_to_id(
                        row('a')[0].attrib['href']
                    )
                    datum['player_name'] = row('th').text()
                    datum['position'] = row('td').text()
                    datum['team'] = team
                    datum['home'] = (h == 1)
                    datum['offense'] = (i <= 10)
                    data.append(datum)
        df = pd.DataFrame(data)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            teamMap = {
                True:self.home(),
                False:self.away()
            }
            df['team'] = df['home'].map(teamMap)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'player_name', 'position', 'home', 'offense']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df.dropna()

    @sportsref.decorators.memoize
    def line(self):
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        line_text = giTable.get('vegas_line', None)
        if line_text is None:
            return np.nan
        m = re.match(r'(.+?) ([\-\.\d]+)$', line_text)
        if m:
            favorite, line = m.groups()
            line = float(line)
            # give in terms of the home team
            year = self.season()
            if favorite != sportsref.nfl.teams.team_names(year)[self.home()]:
                line = -line
        else:
            line = 0
        return line

    @sportsref.decorators.memoize
    def surface(self):
        """The playing surface on which the game was played.

        :returns: string representing the type of surface. Returns np.nan if
        not avaiable.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        return giTable.get('surface', np.nan)

    @sportsref.decorators.memoize
    def roof(self):
        """Whether the stadium has a roof or not.

        :returns: string representing the roof of stadium. Returns np.nan if
        not avaiable.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        return giTable.get('roof', np.nan)


    @sportsref.decorators.memoize
    def over_under(self):
        """
        Returns the over/under for the game as a float, or np.nan if not
        available.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        if 'over_under' in giTable:
            ou = giTable['over_under']
            return float(ou.split()[0])
        else:
            return np.nan

    @sportsref.decorators.memoize
    def coin_toss(self):
        """Gets information relating to the opening coin toss.

        Keys are:
        * wonToss - contains the ID of the team that won the toss
        * deferred - bool whether the team that won the toss deferred it

        :returns: Dictionary of coin toss-related info.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        if 'Won Toss' in giTable:
            # TODO: finish coinToss function
            pass
        else:
            return np.nan

    @sportsref.decorators.memoize
    def weather(self):
        """Returns a dictionary of weather-related info.

        Keys of the returned dict:
        * temp
        * wind_chill
        * humidity
        * wind_mph

        :returns: Dict of weather data.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        if 'weather' in giTable:
            regex = (
                r'(?:(?P<temp>\-?\d+) degrees )?'
                r'(?:relative humidity (?P<humidity>\d+)%, )?'
                r'(?:wind (?P<wind_mph>\d+) mph, )?'
                r'(?:wind chill (?P<wind_chill>\-?\d+))?'
            )
            m = re.match(regex, giTable['weather'])
            d = m.groupdict()

            # cast values to int
            for k in d:
                try:
                    d[k] = int(d[k])
                except TypeError:
                    pass

            # one-off fixes
            d['wind_chill'] = (d['wind_chill'] if pd.notnull(d['wind_chill'])
                              else d['temp'])
            d['wind_mph'] = d['wind_mph'] if pd.notnull(d['wind_mph']) else 0
            return d
        else:
            # no weather found, because it's a dome
            # TODO: what's relative humidity in a dome?
            return {
                'temp': 70, 'wind_chill': 70, 'humidity': None, 'wind_mph': 0
            }

    @sportsref.decorators.memoize
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        Order of function calls:
            1. parse_table on the play-by-play table
            2. expand_details
                - calls parse_play_details & _clean_features
            3. _add_team_columns
            4. various fixes to clean data
            5. _add_team_features

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        doc = self.get_doc()
        table = doc('table#pbp')
        df = sportsref.utils.parse_table(table)
        # make the following features conveniently available on each row
        df['boxscore_id'] = self.boxscore_id
        df['home'] = self.home()
        df['away'] = self.away()
        df['season'] = self.season()
        df['week'] = self.week()
        feats = sportsref.nfl.pbp.expand_details(df)

        # add team and opp columns by iterating through rows
        df = sportsref.nfl.pbp._add_team_columns(feats)
        # add WPA column (requires diff, can't be done row-wise)
        df['home_wpa'] = df.home_wp.diff()
        # lag score columns, fill in 0-0 to start
        for col in ('home_wp', 'pbp_score_hm', 'pbp_score_aw'):
            if col in df.columns:
                df[col] = df[col].shift(1)
        df.loc[0, ['pbp_score_hm', 'pbp_score_aw']] = 0
        # fill in WP NaN's
        df.home_wp.fillna(method='ffill', inplace=True)
        # fix first play border after diffing/shifting for WP and WPA
        firstPlaysOfGame = df[df.secsElapsed == 0].index
        line = self.line()
        for i in firstPlaysOfGame:
            initwp = sportsref.nfl.winProb.initialWinProb(line)
            df.loc[i, 'home_wp'] = initwp
            df.loc[i, 'home_wpa'] = df.loc[i + 1, 'home_wp'] - initwp
        # fix last play border after diffing/shifting for WP and WPA
        lastPlayIdx = df.index[-1]
        lastPlayWP = df.loc[lastPlayIdx, 'home_wp']
        # if a tie, final WP is 50%; otherwise, determined by winner
        winner = self.winner()
        finalWP = 50. if pd.isnull(winner) else (winner == self.home()) * 100.
        df.loc[lastPlayIdx, 'home_wpa'] = finalWP - lastPlayWP
        # fix WPA for timeouts and plays after timeouts
        timeouts = df[df.isTimeout].index
        for to in timeouts:
            df.loc[to, 'home_wpa'] = 0.
            if to + 2 in df.index:
                wpa = df.loc[to + 2, 'home_wp'] - df.loc[to + 1, 'home_wp']
            else:
                wpa = finalWP - df.loc[to + 1, 'home_wp']
            df.loc[to + 1, 'home_wpa'] = wpa
        # add team-related features to DataFrame
        df = sportsref.nfl.pbp._add_team_features(df)
        # fill distToGoal NaN's
        df['distToGoal'] = np.where(df.isKickoff, 65, df.distToGoal)
        df.distToGoal.fillna(method='bfill', inplace=True)
        df.distToGoal.fillna(method='ffill', inplace=True)  # for last play

        return df

    @sportsref.decorators.memoize
    def ref_info(self):
        """Gets a dictionary of ref positions and the ref IDs of the refs for
        that game.

        :returns: A dictionary of ref positions and IDs.
        """
        doc = self.get_doc()
        table = doc('table#officials')
        return sportsref.utils.parse_info_table(table)

    @sportsref.decorators.memoize
    def player_stats(self):
        """Gets the stats for offense, defense, returning, and kicking of
        individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        tableIDs = ('player_offense', 'player_defense', 'returns', 'kicking')
        dfs = []
        for tID in tableIDs:
            table = doc('table#{}'.format(tID))
            dfs.append(sportsref.utils.parse_table(table))
        df = pd.concat(dfs, ignore_index=True)
        df = df.reset_index(drop=True)
        df['team'] = df['team'].str.lower()
        return df

    @sportsref.decorators.memoize
    def stats_team(self):
        """Gets the summarized stats for each team.
        :returns: A DataFrame containing team stats.
        """
        doc = self.get_doc()
        table = doc('#team_stats')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df = df.transpose()
            df.columns = df.iloc[0]
            df.columns.name = None
            df.drop(['stat'], inplace=True)
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = [self.away(), self.home()]
            df['home'] = [False, True]
            # create features from lines with multiple stats in 1 row
            df = pd.concat(
                [df,
                 df['Rush-Yds-TDs'].str.extract(
                        r'(?:(?P<rushAtt>\d+))?'
                        r'(?:-(?P<rushYds>\d+))?'
                        r'(?:-(?P<rushTds>\d+))?',
                        expand=False),
                 df['Cmp-Att-Yd-TD-INT'].str.extract(
                        r'(?:(?P<passCmp>\d+))?'
                        r'(?:-(?P<passAtt>\d+))?'
                        r'(?:-(?P<passYds>\d+))?'
                        r'(?:-(?P<passTds>\d+))?'
                        r'(?:-(?P<passInt>\d+))?',
                        expand=False),
                 df['Sacked-Yards'].str.extract(
                        r'(?:(?P<sacks>\d+))?'
                        r'(?:-(?P<sacksYds>\d+))?',
                        expand=False),
                 df['Fumbles-Lost'].str.extract(
                        r'(?:(?P<fumbles>\d+))?'
                        r'(?:-(?P<fumblesLost>\d+))?',
                        expand=False),
                 df['Sacked-Yards'].str.extract(
                        r'(?:(?P<pentalties>\d+))?'
                        r'(?:-(?P<pentaltiesYds>\d+))?',
                        expand=False),
                 df['Third Down Conv.'].str.extract(
                        r'(?:(?P<thirdDownAtt>\d+))?'
                        r'(?:-(?P<thirdDownConv>\d+))?',
                        expand=False),
                 df['Fourth Down Conv.'].str.extract(
                        r'(?:(?P<fourthDownAtt>\d+))?'
                        r'(?:-(?P<fourthDownConv>\d+))?',
                        expand=False)
                 ], axis=1
            )
            # multi stat features to drop
            dropCols = [
                'Rush-Yds-TDs',
                'Cmp-Att-Yd-TD-INT',
                'Sacked-Yards',
                'Fumbles-Lost',
                'Penalties-Yards',
                'Sacked-Yards',
                'Third Down Conv.',
                'Fourth Down Conv.'
            ]
            df.drop(dropCols, axis=1, inplace=True)
            # newCols = {
                # 'First Downs':'firstDowns',
                # 'Net Pass Yards':'netPassYards',
                # 'Total Yards':'totalYards',
                # 'Turnovers':'turnovers',
                # 'Time of Possession':'timeOfPossession'
            # }
            # df.rename(columns = newCols, inplace=True)
            df.reset_index(drop=True, inplace=True)
            df.rename(columns={'First Downs':'first_downs',
                               'passAtt':'pass_attempts',
                               'passCmp':'pass_completions',
                               'passYds':'pass_yards',
                               'Net Pass Yards':'net_pass_yards',
                               'passTds':'pass_tds',
                               'rushAtt':'rush_attempts',
                               'rushYds':'rush_yards',
                               'rushTds':'rush_tds',
                               'Total Yards':'total_yards',
                               'sacksYds':'sacks_yards',
                               'passInt':'pass_interceptions',
                               'fumblesLost':'fumbles_lost',
                               'Turnovers':'turnovers',
                               'pentaltiesYds':'penalty_yards',
                               'Time of Possession':'time_of_possession',
                               'thirdDownAtt':'third_down_attempts',
                               'thirdDownConv':'third_down_conversions',
                               'fourthDownAtt':'fourth_down_attempts',
                               'fourthDownConv':'fourth_down_conversions'
                              }, inplace=True)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team',
                'home', 'pass_attempts', 'pass_completions','pass_yards', 'net_pass_yards','pass_tds',
                'rush_attempts', 'rush_yards', 'rush_tds', 'total_yards',
                'first_downs', 'sacks', 'sacks_yards',
                'pass_interceptions', 'fumbles', 'fumbles_lost', 'turnovers',
                'time_of_possession', 'pentalties', 'penalty_yards',
                'third_down_attempts', 'third_down_conversions', 'fourth_down_attempts', 'fourth_down_conversions']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def stats_offense(self):
        """Gets the stats for offense of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#player_offense')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = df['team'].str.lower()
            df.rename(columns={'pass_att':'pass_attempts',
                               'pass_cmp':'pass_completions',
                               'pass_yds':'pass_yards',
                               'pass_td':'pass_tds',
                            #    'pass_long':'pass_long',
                            #    'pass_rating':'passRating',
                            #    'pass_sacked':'passSacked',
                            #    'pass_sacked_yds':'passSackedYds',
                            #    'pass_int':'passInt',
                               'rec_yds':'recYds',
                            #    'rec_td':'rec_tds',
                            #    'rec_long':'recLong',
                            #    'rush_att':'rushAtt',
                            #    'rush_yds':'rushYds',
                               'rush_td':'rush_tds'
                            #    'rush_long':'rushLong',
                            #    'fumbles_lost':'fumblesLost'
                              }, inplace=True)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'pass_attempts', 'pass_completions', 'pass_yards', 'pass_tds', 'pass_long', 'pass_rating',
                'pass_sacked', 'pass_sacked_yds', 'pass_int',
                'targets', 'rec', 'rec_yds', 'rec_tds', 'rec_long',
                'rush_att', 'rush_yds', 'rush_tds', 'rush_long', 'fumbles', 'fumbles_lost']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def stats_defense(self):
        """Gets the stats for defense of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#player_defense')
        df = sportsref.utils.parse_table(table)
        # make sure all cols are in the df
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = df['team'].str.lower()
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'sacks', 'tackles_solo', 'tackles_assists',
                'def_int', 'def_int_yds', 'def_int_td', 'def_int_long',
                'fumbles_forced', 'fumbles_rec', 'fumbles_rec_yds', 'fumbles_rec_td']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def stats_returns(self):
        """Gets the stats for returns of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#returns')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = df['team'].str.lower()
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'kick_ret', 'kick_ret_yds', 'kick_ret_yds_per_ret', 'kick_ret_long', 'kick_ret_td',
                'punt_ret', 'punt_ret_yds', 'punt_ret_yds_per_ret', 'punt_ret_long', 'punt_ret_td']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def stats_kicking(self):
        """Gets the stats for kicking of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#kicking')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = df['team'].str.lower()
            df.rename(columns={'punt':'punts',
                               'xpa':'extra_point_attempts',
                               'xpm':'extra_point_made',
                               'fga':'field_goal_attempts',
                               'fgm':'field_goal_made'
                            #    'punt_yds':'puntYds',
                            #    'punt_yds_per_punt':'puntYdsAvg',
                            #    'punt_long':'puntLong'
                              }, inplace=True)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'extra_point_attempts', 'extra_point_made', 'field_goal_attempts', 'field_goal_made',
                'punts', 'punt_yds', 'punt_yds_per_punt', 'punt_long']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def pass_directions(self):
        """Gets the stats for kicking of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#targets_directions')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['team'] = df['team'].str.lower()
            # sum short and deep stats
            df['rec_targets_s'] = df[['rec_targets_sl',
                                      'rec_targets_sm',
                                      'rec_targets_sr'
                                     ]].sum(axis=1)
            df['rec_targets_d'] = df[['rec_targets_dl',
                                      'rec_targets_dm',
                                      'rec_targets_dr'
                                    ]].sum(axis=1)
            df['rec_catches_s'] = df[['rec_catches_sl',
                                      'rec_catches_sm',
                                      'rec_catches_sr'
                                    ]].sum(axis=1)
            df['rec_catches_d'] = df[['rec_catches_dl',
                                      'rec_catches_dm',
                                      'rec_catches_dr'
                                    ]].sum(axis=1)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id',
                'rec_catches_d', 'rec_catches_dl', 'rec_catches_dm', 'rec_catches_dr',
                'rec_catches_s', 'rec_catches_sl', 'rec_catches_sm', 'rec_catches_sr',
                'rec_targets_d', 'rec_targets_dl', 'rec_targets_dm', 'rec_targets_dr',
                'rec_targets_s', 'rec_targets_sl', 'rec_targets_sm', 'rec_targets_sr',
                'rec_td_dl', 'rec_td_dm', 'rec_td_dr', 'rec_td_sl', 'rec_td_sm', 'rec_td_sr',
                'rec_yds_dl', 'rec_yds_dm', 'rec_yds_dr', 'rec_yds_sl', 'rec_yds_sm', 'rec_yds_sr',
                'rec_catches_no_dir', 'rec_targets_no_dir', 'rec_td_no_dir', 'rec_yds_no_dir']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def snap_counts(self):
        """Gets the snap counts of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        table = doc('#home_snap_counts')
        dfH = sportsref.utils.parse_table(table)
        if not dfH.empty:
            dfH['team'] = self.home()
        table = doc('#vis_snap_counts')
        dfV = sportsref.utils.parse_table(table)
        if not dfV.empty:
            dfV['team'] = self.away()
        df = pd.concat([dfH, dfV], ignore_index=True)
        if not df.empty:
            df['boxscore_id'] = self.boxscore_id
            df['season'] = self.season()
            df['week'] = self.week()
            df['off_pct'] = df['off_pct'].astype('float')
            df['def_pct'] = df['def_pct'].astype('float')
            df['st_pct'] = df['st_pct'].astype('float')
            df.rename(columns={'pos':'position',
                               'offense':'off_snaps',
                               'off_pct':'off_snaps_pct',
                               'defense':'def_snaps',
                               'def_pct':'def_snaps_pct',
                               'special_teams':'st_snaps',
                               'st_pct':'st_snaps_pct'
                              }, inplace=True)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id', 'team', 'player_id', 'position',
                'off_snaps', 'off_snaps_pct',
                'def_snaps', 'def_snaps_pct',
                'st_snaps', 'st_snaps_pct']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        df = df.reset_index(drop=True)
        return df

    @sportsref.decorators.memoize
    def game_info(self):
        """Returns a one row dataframe of game info.

        :returns: DataFrame of game info.
        """
        doc = self.get_doc()
        d = {
            'season':self.season(),
            'week':self.week(),
            'boxscore_id':self.boxscore_id,
            'date':self.date(),
            'weekday':self.weekday(),
            'home':self.home(),
            'away':self.away(),
            'home_score':self.home_score(),
            'away_score':self.away_score(),
            'winner':self.winner(),
            'line':self.line(),
            'over_under':self.over_under(),
            'roof':self.roof(),
            'surface':self.surface()
        }
        d.update(self.weather())
        rawTxt = doc('div.scorebox_meta div').eq(1).text()
        regex = (r"(?:Start Time : (?P<start_time>\d+:\d+ ?[apAP][mM]))?")
        d.update(re.match(regex, rawTxt).groupdict())
        df = pd.DataFrame(d, index=[0])
        df['season'] = df['season'].astype(int)
        df['week'] = df['week'].astype(int)
        cols = ['season', 'week', 'boxscore_id',
                'date', 'weekday', 'start_time', 'home', 'away', 'winner',
                'home_score', 'away_score', 'line', 'over_under', 'roof', 'surface',
                'temp', 'humidity', 'wind_chill', 'wind_mph']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df
