import future
import future.utils

import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'team_names',
    'team_ids',
    'list_teams',
    'Team',
]


@sportsref.decorators.memoize
def team_names(year):
    """Returns a mapping from team ID to full team name for a given season.
    Example of a full team name: "New England Patriots"

    :year: The year of the season in question (as an int).
    :returns: A dictionary with teamID keys and full team name values.
    """
    doc = pq(sportsref.utils.get_html(sportsref.nfl.BASE_URL + '/teams/'))
    active_table = doc('table#teams_active')
    active_df = sportsref.utils.parse_table(active_table)
    inactive_table = doc('table#teams_inactive')
    inactive_df = sportsref.utils.parse_table(inactive_table)
    df = pd.concat((active_df, inactive_df))
    df = df.loc[~df['has_class_partial_table']]
    ids = df.team_id.str[:3].values
    names = [tr('th a') for tr in active_table('tr').items()]
    names.extend(tr('th a') for tr in inactive_table('tr').items())
    names = filter(None, names)
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
    return {v: k for k, v in names.iteritems()}


@sportsref.decorators.memoize
def list_teams(year):
    """Returns a list of team IDs for a given season.

    :year: The year of the season in question (as an int).
    :returns: A list of team IDs.
    """
    return team_names(year).keys()


class Team(future.utils.with_metaclass(sportsref.decorators.Cached, object)):

    def __init__(self, teamID):
        self.teamID = teamID

    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    def __repr__(self):
        return 'Team({})'.format(self.teamID)

    def __str__(self):
        return self.name()

    def __reduce__(self):
        return Team, (self.teamID,)

    @sportsref.decorators.memoize
    def team_year_url(self, yr_str):
        return (sportsref.nfl.BASE_URL +
                '/teams/{}/{}.htm'.format(self.teamID, yr_str))

    @sportsref.decorators.memoize
    def get_main_doc(self):
        relURL = '/teams/{}'.format(self.teamID)
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
        headerwords = doc('div#meta h1')[0].text_content().split()
        lastIdx = headerwords.index('Franchise')
        teamwords = headerwords[:lastIdx]
        return ' '.join(teamwords)

    @sportsref.decorators.memoize
    def injury_status(self, year):
        """Returns the player's injury status each week of the given year.

        :year: The year for which we want the injury report;
        :returns: A DataFrame containing player's injury status for that year.
        """
        doc = self.get_year_doc(str(year) + '_injuries')
        table = doc('table#team_injuries')
        columns = [c.attrib['data-stat']
                   for c in table('thead tr:not([class]) th[data-stat]')]

        # get data
        rows = list(table('tbody tr')
                    .not_('.thead, .stat_total, .stat_average')
                    .items())
        data = [
            [str(int(td.has_class('dnp'))) +
             str(sportsref.utils.flatten_links(td)) for td in row.items('th,td')
            ]
            for row in rows
        ]

        # make DataFrame and a few small fixes
        df = pd.DataFrame(data, columns=columns, dtype='float')
        if not df.empty:
            df.rename(columns={'player': 'playerID'}, inplace=True)
            df['playerID'] = df.playerID.str[1:]
            df = pd.melt(df, id_vars=['playerID'])
            df['season'] = year
            df['week'] = pd.to_numeric(df.variable.str[5:])
            df['team'] = self.teamID
            statusMap = {
                'P':'Probable',
                'Q':'Questionable',
                'D':'Doubfult',
                'O':'Out',
                'PUP':'Physically Unable to Perform',
                'IR':'Injured Reserve',
                'None':'None'
            }
            df['status'] = df.value.str[1:].map(statusMap)
            did_not_play_map = {
                '1':True,
                '0':False
            }
            df['did_not_play'] = df.value.str[0].map(did_not_play_map)
            #df['did_not_play'] = df['did_not_play'].astype(bool)
            #df.drop(['variable','value'], axis=1, inplace=True)
            df['season'] = df['season'].astype(int)
            df['week'] = df['week'].astype(int)
            # drop rows if player is None
            df = df[df['playerID'] != 'None'].reset_index(drop=True)
            df['player_id'] = df['playerID']
        # set col order
        cols = ['season', 'week', 'team', 'player_id', 'status', 'did_not_play']
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
        return df

    @sportsref.decorators.memoize
    def roster(self, year):
        """Returns the roster table for the given year.

        :year: The year for which we want the roster;
        :returns: A DataFrame containing roster information for that year.
        """
        doc = self.get_year_doc('{}_roster'.format(year))
        table = doc('table#games_played_team')
        df = sportsref.utils.parse_table(table)
        if not df.empty:
            df['season'] = int(year)
            df['team'] = self.teamID
            player_names = [c.text for c in table('tbody tr td a[href]')
                           if c.attrib['href'][1:8]=='players']
            if len(df) == len(player_names):
                df['player_name'] = player_names
            df.rename(columns={'pos':'position',
                               'g':'games_played',
                               'gs':'games_started',
                               'birth_date_mod':'birth_date',
                               'av':'pfr_approx_value',
                               'college_id':'college'
                              }, inplace=True)
        cols = ['season', 'team', 'player_id',
                'player_name', 'position', 'uniform_number', 'games_played', 'games_started',
                'pfr_approx_value', 'experience', 'age', 'birth_date', 'height', 'weight',
                'college', 'draft_info', 'salary',]
        for col in cols:
            if col not in df: df[col] = np.nan
        df = df[cols]
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
        table = doc('table#games')
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
        p_tags = doc('div#meta div:not(.logo) p')
        texts = [p_tag.text_content().strip() for p_tag in p_tags]
        try:
            return next(
                pq(p_tag) for p_tag, text in zip(p_tags, texts)
                if keyword.lower() in text.lower()
            )
        except StopIteration:
            if len(texts):
                raise ValueError('Keyword not found in any p tag.')
            else:
                raise ValueError('No meta div p tags found.')

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
        coach_str = self._year_info_pq(year, 'Coach').text()
        regex = r'(\S+?) \((\d+)-(\d+)-(\d+)\)'
        coachAndTenure = []
        m = True
        while m:
            m = re.search(regex, coach_str)
            coachID, wins, losses, ties = m.groups()
            nextIndex = m.end(4) + 1
            coachStr = coachStr[nextIndex:]
            tenure = int(wins) + int(losses) + int(ties)
            coachAndTenure.append((coachID, tenure))

        coachIDs = [
            cID for cID, games in coachAndTenure for _ in xrange(games)
        ]
        return np.array(coachIDs[::-1])

    @sportsref.decorators.memoize
    def srs(self, year):
        """Returns the SRS (Simple Rating System) for a team in a year.

        :year: The year for the season in question.
        :returns: A float of SRS.
        """
        srs_text = self._year_info_pq(year, 'SRS').text()
        m = re.match(r'SRS\s*?:\s*?(\S+)', srs_text)
        if m:
            return float(m.group(1))
        else:
            return np.nan

    @sportsref.decorators.memoize
    def sos(self, year):
        """Returns the SOS (Strength of Schedule) for a team in a year, based
        on SRS.

        :year: The year for the season in question.
        :returns: A float of SOS.
        """
        sos_text = self._year_info_pq(year, 'SOS').text()
        m = re.search(r'SOS\s*:\s*(\S+)', sos_text)
        if m:
            return float(m.group(1))
        else:
            return np.nan

    @sportsref.decorators.memoize
    def off_coordinator(self, year):
        """Returns the coach ID for the team's OC in a given year.

        :year: An int representing the year.
        :returns: A string containing the coach ID of the OC.
        """
        try:
            oc_anchor = self._year_info_pq(year, 'Offensive Coordinator')('a')
            if oc_anchor:
                return oc_anchor.attr['href']
        except ValueError:
            return np.nan

    @sportsref.decorators.memoize
    def def_coordinator(self, year):
        """Returns the coach ID for the team's DC in a given year.

        :year: An int representing the year.
        :returns: A string containing the coach ID of the DC.
        """
        try:
            dc_anchor = self._year_info_pq(year, 'Defensive Coordinator')('a')
            if dc_anchor:
                return dc_anchor.attr['href']
        except ValueError:
            return np.nan

    @sportsref.decorators.memoize
    def stadium(self, year):
        """Returns the ID for the stadium in which the team played in a given
        year.

        :year: The year in question.
        :returns: A string representing the stadium ID.
        """
        anchor = self._year_info_pq(year, 'Stadium')('a')
        return sportsref.utils.rel_url_to_id(anchor.attr['href'])

    @sportsref.decorators.memoize
    def off_scheme(self, year):
        """Returns the name of the offensive scheme the team ran in the given
        year.

        :year: Int representing the season year.
        :returns: A string representing the offensive scheme.
        """
        scheme_text = self._year_info_pq(year, 'Offensive Scheme').text()
        m = re.search(r'Offensive Scheme[:\s]*(.+)\s*', scheme_text, re.I)
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
        scheme_text = self._year_info_pq(year, 'Defensive Alignment').text()
        m = re.search(r'Defensive Alignment[:\s]*(.+)\s*', scheme_text, re.I)
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
        table = doc('table#team_stats')
        df = sportsref.utils.parse_table(table)
        return df.loc[df.player_id == 'Team Stats'].iloc[0]

    @sportsref.decorators.memoize
    def opp_stats(self, year):
        """Returns a Series (dict-like) of the team's opponent's stats from the
        team-season page.

        :year: Int representing the season.
        :returns: A Series of team stats.
        """
        doc = self.get_year_doc(year)
        table = doc('table#team_stats')
        df = sportsref.utils.parse_table(table)
        return df.loc[df.player_id == 'Opp. Stats'].iloc[0]

    @sportsref.decorators.memoize
    def passing(self, year):
        doc = self.get_year_doc(year)
        table = doc('table#passing')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def rushing_and_receiving(self, year):
        doc = self.get_year_doc(year)
        table = doc('#rushing_and_receiving')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def off_splits(self, year):
        """Returns a DataFrame of offensive team splits for a season.

        :year: int representing the season.
        :returns: Pandas DataFrame of split data.
        """
        doc = self.get_year_doc('{}_splits'.format(year))
        tables = doc('table.stats_table')
        dfs = [sportsref.utils.parse_table(table) for table in tables.items()]
        dfs = [
            df.assign(split=df.columns[0])
            .rename(columns={df.columns[0]: 'split_value'})
            for df in dfs
        ]
        return pd.concat(dfs).reset_index(drop=True)

    @sportsref.decorators.memoize
    def def_splits(self, year):
        """Returns a DataFrame of defensive team splits (i.e. opponent splits)
        for a season.

        :year: int representing the season.
        :returns: Pandas DataFrame of split data.
        """
        doc = self.get_year_doc('{}_opp_splits'.format(year))
        tables = doc('table.stats_table')
        dfs = [sportsref.utils.parse_table(table) for table in tables.items()]
        dfs = [
            df.assign(split=df.columns[0])
            .rename(columns={df.columns[0]: 'split_value'})
            for df in dfs
        ]
        return pd.concat(dfs).reset_index(drop=True)
