import future
import future.utils

import numpy as np
from pyquery import PyQuery as pq

import sportsref


class Team(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    def __init__(self, team_id):
        self.team_id = team_id

    def __eq__(self, other):
        return (self.team_id == other.team_id)

    def __hash__(self):
        return hash(self.team_id)

    @sportsref.decorators.memoize
    def team_year_url(self, yr_str):
        return (sportsref.euro.BASE_URL +
                '/teams/{}/{}.htm'.format(self.team_id, yr_str))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        relURL = '/teams/{}'.format(self.team_id)
        teamURL = sportsref.euro.BASE_URL + relURL
        mainDoc = pq(sportsref.utils.get_html(teamURL))
        return mainDoc

    @sportsref.decorators.memoize
    def get_year_level_doc(self, yr_str, level='B'):
        return pq(sportsref.utils.get_html(self.team_year_url(yr_str)))

    @sportsref.decorators.memoize
    def name(self):
        """Returns the real name of the franchise given the team ID.

        Examples:
        'BOS' -> 'Boston Celtics'
        'NJN' -> 'Brooklyn Nets'

        :returns: A string corresponding to the team's full name.
        """
        doc = self.get_main_doc()
        name = doc('title').text().replace(' Seasons | Basketball-Reference.com', '')
        return name

    def get_stats_table(self, table_id, year, level='B'):
        doc = self.get_year_doc(year)
        table = doc('table#{}'.format(table_id)
        df = sportsref.utils.parse_table(table)

        return df

    @sportsref.decorators.memoize
    def all_team_opp_stats(self, year, level='B'):
        return self.get_stats_table(year, 'team_and_opp', level=level)

    @sportsref.decorators.memoize    
    def stats_per_game(self, year, level='B'):
        return self.get_stats_table(year, 'per_game', level=level)

    @sportsref.decorators.memoize
    def stats_totals(self, year, level='B'):
        return self.get_stats_table(year, 'totals', level=level)

    @sportsref.decorators.memoize
    def stats_per36(self, year, level='B'):
        return self.get_stats_table(year, 'per_minute', level=level)  

    @sportsref.decorators.memoize
    def stats_advanced(self, year, level='B'):
        return self.get_stats_table(year, 'advanced', level=level)

