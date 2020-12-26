import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = ["team_names", "team_ids", "list_teams", "Team"]


@sportsref.decorators.memoize
def team_names(year):
    """Returns a mapping from team ID to full team name for a given season.
    Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with teamID keys and full team name values.
    """
    doc = pq(sportsref.utils.get_html(sportsref.nfl.BASE_URL + "/teams/"))
    active_table = doc("table#teams_active")
    active_df = sportsref.utils.parse_table(active_table)
    inactive_table = doc("table#teams_inactive")
    inactive_df = sportsref.utils.parse_table(inactive_table)
    df = pd.concat((active_df, inactive_df))
    df = df.loc[~df["has_class_partial_table"]]
    ids = df.team_id.str[:3].values
    names = [tr("th a") for tr in list(active_table("tr").items())]
    names.extend(tr("th a") for tr in list(inactive_table("tr").items()))
    names = [_f for _f in names if _f]
    names = [lst[0].text_content() for lst in names]
    # combine IDs and team names into pandas series
    series = pd.Series(names, index=ids)
    # create a mask to filter to teams from the given year
    mask = ((df.year_min <= year) & (year <= df.year_max)).values
    # filter, convert to a dict, and return
    return series[mask].to_dict()


@sportsref.decorators.memoize
def team_ids(year):
    """Returns a mapping from team name to team ID for a given season. Inverse
    mapping of team_names. Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with full team name keys and teamID values.
    """
    names = team_names(year)
    return {v: k for k, v in list(names.items())}


@sportsref.decorators.memoize
def list_teams(year):
    """Returns a list of team IDs for a given season.

    :year: The year of the season in question (as an int).
    :returns: A list of team IDs.
    """
    return list(team_names(year).keys())


class Team(object, metaclass=sportsref.decorators.Cached):
    def __init__(self, teamID):
        self.teamID = teamID

    def __eq__(self, other):
        return self.teamID == other.teamID

    def __hash__(self):
        return hash(self.teamID)

    def __repr__(self):
        return "Team({})".format(self.teamID)

    def __str__(self):
        return self.name()

    def __reduce__(self):
        return Team, (self.teamID,)

    @sportsref.decorators.memoize
    def team_year_url(self, yr_str):
        return sportsref.nfl.BASE_URL + "/teams/{}/{}.htm".format(self.teamID, yr_str)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        relURL = "/teams/{}".format(self.teamID)
        teamURL = sportsref.nfl.BASE_URL + relURL
        mainDoc = pq(sportsref.utils.get_html(teamURL))
        return mainDoc

    @sportsref.decorators.memoize
    def get_year_doc(self, yr_str):
        return pq(sportsref.utils.get_html(self.team_year_url(yr_str)))

    @sportsref.decorators.memoize
    def name(self):
        """Returns the real name of the franchise given the team ID.

        Examples:
        'nwe' -> 'New England Patriots'
        'sea' -> 'Seattle Seahawks'

        :returns: A string corresponding to the team's full name.
        """
        doc = self.get_main_doc()
        headerwords = doc("div#meta h1")[0].text_content().split()
        lastIdx = headerwords.index("Franchise")
        teamwords = headerwords[:lastIdx]
        return " ".join(teamwords)

    @sportsref.decorators.memoize
    def roster(self, year):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster; defaults to current year.
        :returns: A DataFrame containing roster information for that year.
        """
        doc = self.get_year_doc("{}_roster".format(year))
        roster_table = doc("table#games_played_team")
        df = sportsref.utils.parse_table(roster_table)
        starter_table = doc("table#starters")
        if not starter_table.empty:
            start_df = sportsref.utils.parse_table(starter_table)
            start_df = start_df.dropna(axis=0, subset=["position"])
            starters = start_df.set_index("position").player_id
            df["is_starter"] = df.player_id.isin(starters)
            df["starting_pos"] = df.player_id.map(
                lambda pid: (
                    starters[starters == pid].index[0]
                    if pid in starters.values
                    else None
                )
            )
        return df

    @sportsref.decorators.memoize
    def boxscores(self, year):
        """Gets list of BoxScore objects corresponding to the box scores from
        that year.

        :year: The year for which we want the boxscores; defaults to current
        year.
        :returns: np.array of strings representing boxscore IDs.
        """
        doc = self.get_year_doc(year)
        table = doc("table#games")
        df = sportsref.utils.parse_table(table)
        if df.empty:
            return np.array([])
        return df.boxscore_id.values

    @sportsref.decorators.memoize
    def _year_info_pq(self, year, keyword):
        """Returns a PyQuery object containing the info from the meta div at
        the top of the team year page with the given keyword.

        :year: Int representing the season.
        :keyword: A keyword to filter to a single p tag in the meta div.
        :returns: A PyQuery object for the selected p element.
        """
        doc = self.get_year_doc(year)
        p_tags = doc("div#meta div:not(.logo) p")
        texts = [p_tag.text_content().strip() for p_tag in p_tags]
        try:
            return next(
                pq(p_tag)
                for p_tag, text in zip(p_tags, texts)
                if keyword.lower() in text.lower()
            )
        except StopIteration:
            if len(texts):
                raise ValueError("Keyword not found in any p tag.")
            else:
                raise ValueError("No meta div p tags found.")

    # TODO: add functions for OC, DC, PF, PA, W-L, etc.
    # TODO: Also give a function at BoxScore.homeCoach and BoxScore.awayCoach
    # TODO: BoxScore needs a gameNum function to do this?

    @sportsref.decorators.memoize
    def head_coaches_by_game(self, year):
        """Returns head coach data by game.

        :year: An int representing the season in question.
        :returns: An array with an entry per game of the season that the team
        played (including playoffs). Each entry is the head coach's ID for that
        game in the season.
        """
        coach_str = self._year_info_pq(year, "Coach").text()
        regex = r"(\S+?) \((\d+)-(\d+)-(\d+)\)"
        coachAndTenure = []
        m = True
        while m:
            m = re.search(regex, coach_str)
            coachID, wins, losses, ties = m.groups()
            # nextIndex = m.end(4) + 1
            # coachStr = coachStr[nextIndex:]
            tenure = int(wins) + int(losses) + int(ties)
            coachAndTenure.append((coachID, tenure))

        coachIDs = [cID for cID, games in coachAndTenure for _ in range(games)]
        return np.array(coachIDs[::-1])

    @sportsref.decorators.memoize
    def wins(self, year):
        """Returns the # of regular season wins a team in a year.

        :year: The year for the season in question.
        :returns: The number of regular season wins.
        """
        schedule = self.schedule(year)
        if schedule.empty:
            return np.nan
        return schedule.query("week_num <= 17").is_win.sum()

    @sportsref.decorators.memoize
    def schedule(self, year):
        """Returns a DataFrame with schedule information for the given year.

        :year: The year for the season in question.
        :returns: Pandas DataFrame with schedule information.
        """
        doc = self.get_year_doc(year)
        table = doc("table#games")
        df = sportsref.utils.parse_table(table)
        if df.empty:
            return pd.DataFrame()
        df = df.loc[df["week_num"].notnull()]
        df["week_num"] = np.arange(len(df)) + 1
        df["is_win"] = df["game_outcome"] == "W"
        df["is_loss"] = df["game_outcome"] == "L"
        df["is_tie"] = df["game_outcome"] == "T"
        df["is_bye"] = df["game_outcome"].isnull()
        df["is_ot"] = df["overtime"].notnull()
        return df

    @sportsref.decorators.memoize
    def srs(self, year):
        """Returns the SRS (Simple Rating System) for a team in a year.

        :year: The year for the season in question.
        :returns: A float of SRS.
        """
        try:
            srs_text = self._year_info_pq(year, "SRS").text()
        except ValueError:
            return None
        m = re.match(r"SRS\s*?:\s*?(\S+)", srs_text)
        if m:
            return float(m.group(1))
        else:
            return None

    @sportsref.decorators.memoize
    def sos(self, year):
        """Returns the SOS (Strength of Schedule) for a team in a year, based
        on SRS.

        :year: The year for the season in question.
        :returns: A float of SOS.
        """
        try:
            sos_text = self._year_info_pq(year, "SOS").text()
        except ValueError:
            return None
        m = re.search(r"SOS\s*:\s*(\S+)", sos_text)
        if m:
            return float(m.group(1))
        else:
            return None

    @sportsref.decorators.memoize
    def off_coordinator(self, year):
        """Returns the coach ID for the team's OC in a given year.

        :year: An int representing the year.
        :returns: A string containing the coach ID of the OC.
        """
        try:
            oc_anchor = self._year_info_pq(year, "Offensive Coordinator")("a")
            if oc_anchor:
                return oc_anchor.attr["href"]
        except ValueError:
            return None

    @sportsref.decorators.memoize
    def def_coordinator(self, year):
        """Returns the coach ID for the team's DC in a given year.

        :year: An int representing the year.
        :returns: A string containing the coach ID of the DC.
        """
        try:
            dc_anchor = self._year_info_pq(year, "Defensive Coordinator")("a")
            if dc_anchor:
                return dc_anchor.attr["href"]
        except ValueError:
            return None

    @sportsref.decorators.memoize
    def stadium(self, year):
        """Returns the ID for the stadium in which the team played in a given
        year.

        :year: The year in question.
        :returns: A string representing the stadium ID.
        """
        anchor = self._year_info_pq(year, "Stadium")("a")
        return sportsref.utils.rel_url_to_id(anchor.attr["href"])

    @sportsref.decorators.memoize
    def off_scheme(self, year):
        """Returns the name of the offensive scheme the team ran in the given
        year.

        :year: Int representing the season year.
        :returns: A string representing the offensive scheme.
        """
        scheme_text = self._year_info_pq(year, "Offensive Scheme").text()
        m = re.search(r"Offensive Scheme[:\s]*(.+)\s*", scheme_text, re.I)
        if m:
            return m.group(1)
        else:
            return None

    @sportsref.decorators.memoize
    def def_alignment(self, year):
        """Returns the name of the defensive alignment the team ran in the
        given year.

        :year: Int representing the season year.
        :returns: A string representing the defensive alignment.
        """
        scheme_text = self._year_info_pq(year, "Defensive Alignment").text()
        m = re.search(r"Defensive Alignment[:\s]*(.+)\s*", scheme_text, re.I)
        if m:
            return m.group(1)
        else:
            return None

    @sportsref.decorators.memoize
    def team_stats(self, year):
        """Returns a Series (dict-like) of team stats from the team-season
        page.

        :year: Int representing the season.
        :returns: A Series of team stats.
        """
        doc = self.get_year_doc(year)
        table = doc("table#team_stats")
        df = sportsref.utils.parse_table(table)
        if df.empty:
            return pd.Series()
        return df.loc[df.player_id == "Team Stats"].iloc[0]

    @sportsref.decorators.memoize
    def opp_stats(self, year):
        """Returns a Series (dict-like) of the team's opponent's stats from the
        team-season page.

        :year: Int representing the season.
        :returns: A Series of team stats.
        """
        doc = self.get_year_doc(year)
        table = doc("table#team_stats")
        df = sportsref.utils.parse_table(table)
        return df.loc[df.player_id == "Opp. Stats"].iloc[0]

    @sportsref.decorators.memoize
    def passing(self, year):
        doc = self.get_year_doc(year)
        table = doc("table#passing")
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def rushing_and_receiving(self, year):
        doc = self.get_year_doc(year)
        table = doc("#rushing_and_receiving")
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def off_splits(self, year):
        """Returns a DataFrame of offensive team splits for a season.

        :year: int representing the season.
        :returns: Pandas DataFrame of split data.
        """
        doc = self.get_year_doc("{}_splits".format(year))
        tables = doc("table.stats_table")
        dfs = [sportsref.utils.parse_table(table) for table in list(tables.items())]
        dfs = [
            df.assign(split=df.columns[0]).rename(
                columns={df.columns[0]: "split_value"}
            )
            for df in dfs
        ]
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs).reset_index(drop=True)

    @sportsref.decorators.memoize
    def def_splits(self, year):
        """Returns a DataFrame of defensive team splits (i.e. opponent splits)
        for a season.

        :year: int representing the season.
        :returns: Pandas DataFrame of split data.
        """
        doc = self.get_year_doc("{}_opp_splits".format(year))
        tables = doc("table.stats_table")
        dfs = [sportsref.utils.parse_table(table) for table in list(tables.items())]
        dfs = [
            df.assign(split=df.columns[0]).rename(
                columns={df.columns[0]: "split_value"}
            )
            for df in dfs
        ]
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs).reset_index(drop=True)
