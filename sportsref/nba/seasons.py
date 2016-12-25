import numpy as np
from pyquery import PyQuery as pq
import six

import sportsref


class Season(six.with_metaclass(sportsref.decorators.Cached, object)):

    """Object representing a given NBA season."""

    def __init__(self, year):
        """Initializes a Season object for an NBA season.

        :year: The year of the season we want.
        """
        self._yr = int(year)

    def __eq__(self, other):
        return (self._yr == other._yr)

    def __hash__(self):
        return hash(self._yr)

    def _subpage_url(self, page):
        return (sportsref.nba.BASE_URL +
                '/leagues/NBA_{}_{}.html'.format(self._yr, page))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        url = (sportsref.nba.BASE_URL +
               '/leagues/NBA_{}.html'.format(self._yr))
        return pq(sportsref.utils.get_html(url))

    @sportsref.decorators.memoize
    def get_doc(self, subpage):
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
        df = self.team_stats()
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
    @sportsref.decorators.kind_rpb(include_type=False)
    def get_boxscore_ids(self, kind='R'):
        """Returns a list of BoxScore IDs for every game in the season.
        Only needs to handle 'R' or 'P' options because decorator handles 'B'.

        :kind: 'R' for regular season, 'P' for playoffs, 'B' for both.
        :returns: List of IDs for nba.BoxScore objects.
        """
        doc = self.get_doc('games') # noqa
        raise Exception('not yet implemented - nba.Season.get_boxscore_ids')

    def finals_winner(self):
        """Returns the team ID for the winner of that year's NBA Finals.
        :returns: 3-letter team ID for champ.
        """
        playoffs = self.playoff_series_results()
        home, away, home_won = playoffs[0]
        return home if home_won else away

    def finals_loser(self):
        """Returns the team ID for the loser of that year's NBA Finals.
        :returns: 3-letter team ID for runner-up.
        """
        playoffs = self.playoff_series_results()
        home, away, home_won = playoffs[0]
        return away if home_won else home

    @sportsref.decorators.memoize
    def playoff_series_results(self):
        """Returns the winning and losing team of every playoff series in the
        given year.
        :returns: Returns a list of tuples of the form
        (home team ID, away team ID, bool(home team won)).
        """
        doc = self.get_main_doc()
        table = doc('table#all_playoffs')

        # get winners/losers
        atags = [tr('td:eq(1) a')
                 for tr in table.items('tr')
                 if len(tr('td')) == 3]
        relURLs = [(a.eq(0).attr['href'], a.eq(1).attr['href']) for a in atags]
        wl = [tuple(map(sportsref.utils.rel_url_to_id, ru)) for ru in relURLs]

        # get home team
        atags = table('tr.toggleable table tr:eq(0) td:eq(0) a')
        bsIDs = [sportsref.utils.rel_url_to_id(a.attrib['href'])
                 for a in atags]
        home = np.array([sportsref.nba.BoxScore(bs).home() for bs in bsIDs])

        # get winners and losers
        win, loss = map(np.array, zip(*wl))
        homeWon = home == win
        ret = zip(home, np.where(homeWon, loss, win), homeWon)

        return ret

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
        doc = self.get_doc(identifier)
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
