import numpy as np
from pyquery import PyQuery as pq

import sportsref


class Team(object, metaclass=sportsref.decorators.Cached):
    def __init__(self, team_id):
        self.team_id = team_id.upper()

    def __eq__(self, other):
        return self.team_id == other.team_id

    def __hash__(self):
        return hash(self.team_id)

    @sportsref.decorators.memoize
    def team_year_url(self, yr_str):
        return f"{sportsref.nba.BASE_URL}/teams/{self.team_id}/{yr_str}.htm"

    @sportsref.decorators.memoize
    def get_main_doc(self):
        team_url = f"{sportsref.nba.BASE_URL}/teams/{self.team_id}"
        main_doc = pq(sportsref.utils.get_html(team_url))
        return main_doc

    @sportsref.decorators.memoize
    def get_year_doc(self, yr_str):
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
        name = doc('div#info h1[itemprop="name"]').text()
        return name

    @sportsref.decorators.memoize
    def roster(self, year):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        doc = self.get_year_doc(year)
        table = doc("table#roster")
        df = sportsref.utils.parse_table(table)
        df["years_experience"] = (
            df["years_experience"].replace("R", 0).replace("", np.nan).astype(float)
        )
        return df

    # TODO: kind_rpb
    @sportsref.decorators.memoize
    def schedule(self, year):
        """Gets schedule information for a team-season.

        :year: The year for which we want the schedule.
        :returns: DataFrame of schedule information.
        """
        doc = self.get_year_doc(f"{year}_games")
        table = doc("table#games")
        df = sportsref.utils.parse_table(table)
        return df
