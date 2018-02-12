import future
import future.utils

import pandas as pd
from pyquery import PyQuery as pq

import sportsref


class Season(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    """Object representing a given NBA season."""

    def __init__(self, year, league_id):
        """Initializes a Season object for an NBA season.

        :year: The year of the season we want.
        """
        self.yr = int(year)
        self.lg_id = league_id

    def __eq__(self, other):
        return (self.yr == other.yr and self.lg_id == other.lg_id)

    def __hash__(self):
        return hash(self.yr)

    def __repr__(self):
        return 'Season({})'.format(self.yr)

    def _schedule_url(self):
        return (sportsref.euro.BASE_URL +
                '/{}/{}-schedule.html'.format(self.lg_id, self.yr))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        url = (sportsref.euro.BASE_URL +
               '/{}/{}.html'.format(self.lg_id, self.yr))
        return pq(sportsref.utils.get_html(url))

    @sportsref.decorators.memoize
    def get_schedule_doc(self):
        """Returns PyQuery object for a given subpage URL.
        :subpage: The subpage of the season, e.g. 'per_game'.
        :returns: PyQuery object.
        """
        html = sportsref.utils.get_html(self._schedule_url())
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
            print('ERROR: no teams found')
            return []

    @sportsref.decorators.memoize
    def team_ids_to_names(self):
        """Mapping from 3-letter team IDs to full team names.
        :returns: Dictionary with team IDs as keys and full team strings as
        values.
        """
        doc = self.get_main_doc()
        table = doc('table#team_stats_per_game')
        for a in table('a').items():
            a.removeAttr('href')
        
        name_table = sportsref.utils.parse_table(table)
        id_table = self.team_stats_per_game()

        team_ids = id_table.index.values
        team_names = name_table['team_name_season']
        if len(team_names) != len(team_ids):
            raise Exception("team names and team IDs don't align")
        return dict(list(zip(team_ids, team_names)))

    @sportsref.decorators.memoize
    def team_names_to_ids(self):
        """Mapping from full team names to 3-letter team IDs.
        :returns: Dictionary with tean names as keys and team IDs as values.
        """
        d = self.team_ids_to_names()
        return {v: k for k, v in list(d.items())}

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def schedule(self, kind='R'):
        """Returns a list of BoxScore IDs for every game in the season.
        Only needs to handle 'R' or 'P' options because decorator handles 'B'.

        :param kind: 'R' for regular season, 'P' for playoffs, 'B' for both.
            Defaults to 'R'.
        :returns: DataFrame of schedule information.
        :rtype: pd.DataFrame
        """
        doc = self.get_schedule_doc()
        table_id = 'table#games'
        if kind == 'P':
            table_id += '_playoffs'
        
        table = doc(table_id)
        df = sportsref.utils.parse_table(table)
        return df
  

    @sportsref.decorators.memoize
    def _get_team_stats_table(self, selector):
        """Helper function for stats tables on season pages. Returns a
        DataFrame."""
        doc = self.get_main_doc()
        table = doc(selector)
        df = sportsref.utils.parse_table(table)
        df['team_name_season'] = df['team_name_season'].apply(lambda x: x.split('/')[3])
        df.rename(columns={'team_name_season' : 'team_id'}, inplace=True)
        df.set_index('team_id', inplace=True)
        return df

    def standings(self):
        """Returns a Pandas DataFrame of each team's basic per-game stats for
        the season."""

        if self.lg_id == 'eurocup' or self.lg_id == 'euroleague':
            return self._get_team_stats_table('table#tournament_standings')
        else:
            return self._get_team_stats_table('table#league_standings')

    def team_stats_totals(self):
        """Returns a Pandas DataFrame of each team's basic per-game stats for
        the season."""
        return self._get_team_stats_table('table#team_stats_totals')

    def team_stats_per_game(self):
        """Returns a Pandas DataFrame of each team's basic per-game stats for
        the season."""
        return self._get_team_stats_table('table#team_stats_per_game')
