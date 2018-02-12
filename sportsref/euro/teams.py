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
    def team_year_url(self, year, level='B'):
        yr_str = str(year)
        if level == 'C':
            yr_str += '_' + self.get_league_id(year=year)
        elif level == 'E':
            yr_str += '_euroleague' 
  
        return (sportsref.euro.BASE_URL +
                '/teams/{}/{}.htm'.format(self.team_id, yr_str))

    @sportsref.decorators.memoize
    def schedule_url(self, year):
        return (sportsref.euro.BASE_URL + '/schedules/{}/{}.html'.format(self.team_id, year))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        relURL = '/teams/{}'.format(self.team_id)
        teamURL = sportsref.euro.BASE_URL + relURL
        mainDoc = pq(sportsref.utils.get_html(teamURL))
        return mainDoc

    @sportsref.decorators.memoize
    def get_year_doc(self, yr_str, level='B'):
        return pq(sportsref.utils.get_html(self.team_year_url(yr_str, level=level)))

    @sportsref.decorators.memoize
    def get_schedule_doc(self, year):
        return pq(sportsref.utils.get_html(self.schedule_url(year)))    

    @sportsref.decorators.memoize
    def get_league_id(self, year=2018):
        """ Year parameter here in case team switched club-play leagues - also makes it easier to find in doc"""
        doc = self.get_main_doc()
        table = doc('table#team-index-club')

        start = '/euro/'
        end = '/{}.html'.format(year)

        for a in table('a[href$="{}"]'.format(end)).items():
            if 'years' not in a.attr('href'): 
                return a.attr('href')[len(start):-len(end)]  

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
        doc = self.get_year_doc(year, level=level)
        table = doc('table#{}'.format(table_id))
        print(table_id)
        df = sportsref.utils.parse_table(table)

        return df

    @sportsref.decorators.memoize
    def schedule(self, year, level='B'):
        doc = self.get_schedule_doc(year)
        for t in doc('table').items():
            if self.team_id in t.attr('id'):
                if 'Euroleague' in t.attr('id'):
                    e_id = t.attr('id')
                else:
                    c_id = t.attr('id')

        if level == 'C':
            table_id = c_id
        
        else:
            table_id = e_id

        table = doc('table#{}'.format(table_id))
        df = sportsref.utils.parse_table(table)
        return df
        

    @sportsref.decorators.memoize
    def all_team_opp_stats(self, year, level='B'):
        return self.get_stats_table('team_and_opp', year, level=level)

    @sportsref.decorators.memoize    
    def stats_per_game(self, year, level='B'):
        return self.get_stats_table('per_game', year, level=level)

    @sportsref.decorators.memoize
    def stats_totals(self, year, level='B'):
        return self.get_stats_table('totals', year, level=level)

    @sportsref.decorators.memoize
    def stats_per36(self, year, level='B'):
        return self.get_stats_table('per_minute', year, level=level)  

    @sportsref.decorators.memoize
    def stats_advanced(self, year, level='B'):
        return self.get_stats_table('advanced', year, level=level)

