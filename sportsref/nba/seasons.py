import pandas as pd
from pyquery import PyQuery as pq

import sportsref


class Season(object, metaclass=sportsref.decorators.Cached):

    """Object representing a given NBA season."""

    def __init__(self, year):
        """Initializes a Season object for an NBA season.

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
        return sportsref.nba.BASE_URL + "/leagues/NBA_{}_{}.html".format(self.yr, page)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        url = sportsref.nba.BASE_URL + "/leagues/NBA_{}.html".format(self.yr)
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
            print("ERROR: no teams found")
            return []

    @sportsref.decorators.memoize
    def team_ids_to_names(self):
        """Mapping from 3-letter team IDs to full team names.
        :returns: Dictionary with team IDs as keys and full team strings as
        values.
        """
        doc = self.get_main_doc()
        table = doc("table#team-stats-per_game")
        flattened = sportsref.utils.parse_table(table, flatten=True)
        unflattened = sportsref.utils.parse_table(table, flatten=False)
        team_ids = flattened["team_id"]
        team_names = unflattened["team_name"]
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
    def schedule(self, kind="R"):
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
        for month in (
            "october",
            "november",
            "december",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
        ):
            try:
                doc = self.get_sub_doc("games-{}".format(month))
            except ValueError:
                continue
            table = doc("table#schedule")
            df = sportsref.utils.parse_table(table)
            dfs.append(df)
        df = pd.concat(dfs).reset_index(drop=True)

        # figure out how many regular season games
        try:
            sportsref.utils.get_html(
                "{}/playoffs/NBA_{}.html".format(sportsref.nba.BASE_URL, self.yr)
            )
            is_past_season = True
        except ValueError:
            is_past_season = False

        if is_past_season:
            team_per_game = self.team_stats_per_game()
            n_reg_games = int(team_per_game.g.sum() // 2)
        else:
            n_reg_games = len(df)

        # subset appropriately based on `kind`
        if kind == "P":
            return df.iloc[n_reg_games:]
        else:
            return df.iloc[:n_reg_games]

    def finals_winner(self):
        """Returns the team ID for the winner of that year's NBA Finals.
        :returns: 3-letter team ID for champ.
        """
        raise NotImplementedError("nba.Season.finals_winner")

    def finals_loser(self):
        """Returns the team ID for the loser of that year's NBA Finals.
        :returns: 3-letter team ID for runner-up.
        """
        raise NotImplementedError("nba.Season.finals_loser")

    def standings(self):
        """Returns a DataFrame containing standings information."""
        doc = self.get_sub_doc("standings")

        east_table = doc("table#confs_standings_E")
        east_df = sportsref.utils.parse_table(east_table)
        east_df.sort_values("wins", ascending=False, inplace=True)
        east_df["seed"] = list(range(1, len(east_df) + 1))
        east_df["conference"] = "E"

        west_table = doc("table#confs_standings_W")
        west_df = sportsref.utils.parse_table(west_table)
        west_df.sort_values("wins", ascending=False, inplace=True)
        west_df["seed"] = list(range(1, len(west_df) + 1))
        west_df["conference"] = "W"

        full_df = pd.concat([east_df, west_df], axis=0).reset_index(drop=True)
        full_df["gb"] = [
            gb if isinstance(gb, int) or isinstance(gb, float) else 0
            for gb in full_df["gb"]
        ]
        full_df = full_df.drop("has_class_full_table", axis=1)

        expanded_table = doc("table#expanded_standings")
        expanded_df = sportsref.utils.parse_table(expanded_table)

        full_df = pd.merge(full_df, expanded_df, on="team_id")
        return full_df

    @sportsref.decorators.memoize
    def _get_team_stats_table(self, selector):
        """Helper function for stats tables on season pages. Returns a
        DataFrame."""
        doc = self.get_main_doc()
        table = doc(selector)
        df = sportsref.utils.parse_table(table)
        df.set_index("team_id", inplace=True)
        return df

    def team_stats_per_game(self):
        """Returns a Pandas DataFrame of each team's basic per-game stats for
        the season."""
        return self._get_team_stats_table("table#team-stats-per_game")

    def opp_stats_per_game(self):
        """Returns a Pandas DataFrame of each team's opponent's basic per-game
        stats for the season."""
        return self._get_team_stats_table("table#opponent-stats-per_game")

    def team_stats_totals(self):
        """Returns a Pandas DataFrame of each team's basic stat totals for the
        season."""
        return self._get_team_stats_table("table#team-stats-base")

    def opp_stats_totals(self):
        """Returns a Pandas DataFrame of each team's opponent's basic stat
        totals for the season."""
        return self._get_team_stats_table("table#opponent-stats-base")

    def misc_stats(self):
        """Returns a Pandas DataFrame of miscellaneous stats about each team's
        season."""
        return self._get_team_stats_table("table#misc_stats")

    def team_stats_shooting(self):
        """Returns a Pandas DataFrame of each team's shooting stats for the
        season."""
        return self._get_team_stats_table("table#team_shooting")

    def opp_stats_shooting(self):
        """Returns a Pandas DataFrame of each team's opponent's shooting stats
        for the season."""
        return self._get_team_stats_table("table#opponent_shooting")

    @sportsref.decorators.memoize
    def _get_player_stats_table(self, identifier):
        """Helper function for player season stats.

        :identifier: string identifying the type of stat, e.g. 'per_game'.
        :returns: A DataFrame of stats.
        """
        doc = self.get_sub_doc(identifier)
        table = doc("table#{}_stats".format(identifier))
        df = sportsref.utils.parse_table(table)
        return df

    def player_stats_per_game(self):
        """Returns a DataFrame of per-game player stats for a season."""
        return self._get_player_stats_table("per_game")

    def player_stats_totals(self):
        """Returns a DataFrame of player stat totals for a season."""
        return self._get_player_stats_table("totals")

    def player_stats_per36(self):
        """Returns a DataFrame of player per-36 min stats for a season."""
        return self._get_player_stats_table("per_minute")

    def player_stats_per100(self):
        """Returns a DataFrame of player per-100 poss stats for a season."""
        return self._get_player_stats_table("per_poss")

    def player_stats_advanced(self):
        """Returns a DataFrame of player per-100 poss stats for a season."""
        return self._get_player_stats_table("advanced")

    def mvp_voting(self):
        """Returns a DataFrame containing information about MVP voting."""
        raise NotImplementedError("nba.Season.mvp_voting")

    def roy_voting(self):
        """Returns a DataFrame containing information about ROY voting."""
        url = "{}/awards/awards_{}.html".format(sportsref.nba.BASE_URL, self.yr)
        doc = pq(sportsref.utils.get_html(url))
        table = doc("table#roy")
        df = sportsref.utils.parse_table(table)
        return df
