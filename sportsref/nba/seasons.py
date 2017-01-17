import future
import future.utils

import pandas as pd
from pyquery import PyQuery as pq

import sportsref


class Season(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    """Object representing a given NBA season."""

    def __init__(self, year):
        """Initializes a Season object for an NBA season.

        :year: The year of the season we want.
        """
        self.yr = int(year)

    def __eq__(self, other):
        return (self.yr == other.yr)

    def __hash__(self):
        return hash(self.yr)

    def __repr__(self):
        return 'Season({})'.format(self.yr)

    def _subpage_url(self, page):
        return (sportsref.nba.BASE_URL +
                '/leagues/NBA_{}_{}.html'.format(self.yr, page))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        url = (sportsref.nba.BASE_URL +
               '/leagues/NBA_{}.html'.format(self.yr))
        return pq(sportsref.utils.get_html(url))

    @sportsref.decorators.memoize
    def get_sub_doc(self, subpage):
        """Returns PyQuery object for a given subpage URL.
        :subpage: The subpage of the season, e.g. 'per_game'.
        :returns: PyQuery object.
        """
        html = sportsref.utils.get_html(self._subpage_url(subpage))
        return pq(html)

    @sportsref.decorators.memoize
    def get_team_ids(self):
        """Returns a list of the team IDs for the given year.
        :returns: List of team IDs.
        """
        df = self.team_stats_per_game()
        if not df.empty:
            return df.index.tolist()
        else:
            print 'ERROR: no teams found'
            return []

    @sportsref.decorators.memoize
    def team_ids_to_names(self):
        """Mapping from 3-letter team IDs to full team names.
        :returns: Dictionary with team IDs as keys and full team strings as
        values.
        """
        doc = self.get_main_doc()
        team_ids = sportsref.utils.parse_table(
            doc('table#team-stats-per_game'), flatten=True)['team_id']
        team_names = sportsref.utils.parse_table(
            doc('table#team-stats-per_game'), flatten=False)['team_name']
        if len(team_names) != len(team_ids):
            raise Exception("team names and team IDs don't align")
        return dict(zip(team_ids, team_names))

    @sportsref.decorators.memoize
    def team_names_to_ids(self):
        """Mapping from full team names to 3-letter team IDs.
        :returns: Dictionary with tean names as keys and team IDs as values.
        """
        d = self.team_ids_to_names()
        return {v: k for k, v in d.items()}

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def get_schedule(self, kind='R'):
        """Returns a list of BoxScore IDs for every game in the season.
        Only needs to handle 'R' or 'P' options because decorator handles 'B'.

        :param kind: 'R' for regular season, 'P' for playoffs, 'B' for both.
            Defaults to 'R'.
        :returns: DataFrame of schedule information.
        :rtype: pd.DataFrame
        """
        kind = kind.upper()[0]
        dfs = []

        # get games from each month
        for month in ('october', 'november', 'december', 'january', 'february',
                      'march', 'april', 'may', 'june'):
            try:
                doc = self.get_sub_doc('games-{}'.format(month))
            except ValueError:
                continue
            table = doc('table#schedule')
            df = sportsref.utils.parse_table(table)
            dfs.append(df)
        df = pd.concat(dfs)

        # figure out which games are regular season
        team_per_game = self.team_stats_per_game()
        n_reg_games = int(team_per_game.g.sum() / 2)

        # expand `date_game` column to month/day/year
        date_df = df['date_game'].str.extract(
            'month=(?P<month>\d+)&day=(?P<day>\d+)&year=(?P<year>\d+)',
            expand=True)

        df = pd.concat((df, date_df), axis=1).drop('date_game', axis=1)

        # clean up some columns
        df.rename(columns={'box_score_text': 'boxscore_id'}, inplace=True)

        # subset appropriately based on `kind`
        if kind == 'P':
            return df.iloc[n_reg_games:]
        else:
            return df.iloc[:n_reg_games]

    def finals_winner(self):
        """Returns the team ID for the winner of that year's NBA Finals.
        :returns: 3-letter team ID for champ.
        """
        raise NotImplementedError('nba.Season.finals_winner')

    def finals_loser(self):
        """Returns the team ID for the loser of that year's NBA Finals.
        :returns: 3-letter team ID for runner-up.
        """
        raise NotImplementedError('nba.Season.finals_loser')

    @sportsref.decorators.memoize
    def _get_team_stats_table(self, selector):
        """Helper function for stats tables on season pages. Returns a
        DataFrame."""
        doc = self.get_main_doc()
        table = doc(selector)
        df = sportsref.utils.parse_table(table)
        df = df.drop('ranker', axis=1)
        return df

    def team_stats_per_game(self):
        """Returns a Pandas DataFrame of each team's basic per-game stats for
        the season."""
        return self._get_team_stats_table('table#team-stats-per_game')

    def opp_stats_per_game(self):
        """Returns a Pandas DataFrame of each team's opponent's basic per-game
        stats for the season."""
        return self._get_team_stats_table('table#opponent-stats-per_game')

    def team_stats_totals(self):
        """Returns a Pandas DataFrame of each team's basic stat totals for the
        season."""
        return self._get_team_stats_table('table#team-stats-base')

    def opp_stats_totals(self):
        """Returns a Pandas DataFrame of each team's opponent's basic stat
        totals for the season."""
        return self._get_team_stats_table('table#opponent-stats-base')

    def misc_stats(self):
        """Returns a Pandas DataFrame of miscellaneous stats about each team's
        season."""
        return self._get_team_stats_table('table#misc_stats')

    def team_stats_shooting(self):
        """Returns a Pandas DataFrame of each team's shooting stats for the
        season."""
        return self._get_team_stats_table('table#team_shooting')

    def opp_stats_shooting(self):
        """Returns a Pandas DataFrame of each team's opponent's shooting stats
        for the season."""
        return self._get_team_stats_table('table#opponent_shooting')

    @sportsref.decorators.memoize
    def _get_player_stats_table(self, identifier):
        """Helper function for player season stats.

        :identifier: string identifying the type of stat, e.g. 'per_game'.
        :returns: A DataFrame of stats.
        """
        doc = self.get_sub_doc(identifier)
        table = doc('table#{}_stats'.format(identifier))
        df = sportsref.utils.parse_table(table)
        df = df.drop('ranker', axis=1)
        return df

    def player_stats_per_game(self):
        """Returns a DataFrame of per-game player stats for a season."""
        return self._get_player_stats_table('per_game')

    def player_stats_totals(self):
        """Returns a DataFrame of player stat totals for a season."""
        return self._get_player_stats_table('totals')

    def player_stats_per36(self):
        """Returns a DataFrame of player per-36 min stats for a season."""
        return self._get_player_stats_table('per_minute')

    def player_stats_per100(self):
        """Returns a DataFrame of player per-100 poss stats for a season."""
        return self._get_player_stats_table('per_poss')

    def player_stats_advanced(self):
        """Returns a DataFrame of player per-100 poss stats for a season."""
        return self._get_player_stats_table('advanced')
