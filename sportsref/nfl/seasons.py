from pyquery import PyQuery as pq

import sportsref


__all__ = ["Season"]


class Season(object, metaclass=sportsref.decorators.Cached):

    """Object representing a given NFL season."""

    def __init__(self, year):
        """Initializes a Season object for an NFL season.

        :year: The year of the season we want.
        """
        self.yr = int(year)

    def __eq__(self, other):
        return self.yr == other.yr

    def __hash__(self):
        return hash(self.yr)

    def __repr__(self):
        return "Season({})".format(self.yr)

    def _subpage_url(self, page):
        return sportsref.nfl.BASE_URL + "/years/{}/{}.htm".format(self.yr, page)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        url = sportsref.nfl.BASE_URL + "/years/{}/".format(self.yr)
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
        return sportsref.nfl.teams.list_teams(self.yr)

    @sportsref.decorators.memoize
    def team_ids_to_names(self):
        """Mapping from 3-letter team IDs to full team names.

        :returns: Dictionary with team IDs as keys and full team strings as
            values.
        """
        return sportsref.nfl.teams.team_names(self.yr)

    @sportsref.decorators.memoize
    def team_names_to_ids(self):
        """Mapping from full team names to 3-letter team IDs.
        :returns: Dictionary with tean names as keys and team IDs as values.
        """
        return sportsref.nfl.teams.team_ids(self.yr)

    @sportsref.decorators.memoize
    def _get_player_stats_table(self, subpage, table_id):
        """Helper function for player season stats.

        :identifier: string identifying the type of stat, e.g. 'passing'.
        :returns: A DataFrame of stats.
        """
        doc = self.get_sub_doc(subpage)
        table = doc("table#{}".format(table_id))
        df = sportsref.utils.parse_table(table)
        return df

    def player_stats_passing(self):
        """Returns a DataFrame of passing player stats for a season."""
        return self._get_player_stats_table("passing", "passing")

    def player_stats_rushing(self):
        """Returns a DataFrame of rushing player stats for a season."""
        return self._get_player_stats_table("rushing", "rushing_and_receiving")

    def player_stats_receiving(self):
        """Returns a DataFrame of receiving player stats for a season."""
        return self._get_player_stats_table("receiving", "receiving")
