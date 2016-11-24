import numpy as np
from pyquery import PyQuery as pq

import sportsref


@sportsref.decorators.memoized
class Season(object):

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
        return sportsref.nba.BASE_URL + '/leagues/NBA_{}.html'.format(page)

    @sportsref.decorators.memoized
    def get_main_doc(self):
        """Returns PyQuery object for the main season URL.
        :returns: PyQuery object.
        """
        return pq(sportsref.utils.get_html(self._subpage_url(self._yr)))

    @sportsref.decorators.memoized
    def get_schedule_doc(self):
        """Returns PyQuery object for the season schedule URL.
        :returns: PyQuery object.
        """
        html = sportsref.utils.get_html(
            self._subpage_url('{}_games'.format(self._yr))
        )
        return pq(html)

    @sportsref.decorators.memoized
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

    @sportsref.decorators.memoized
    def team_ids_to_names(self):
        """Mapping from 3-letter team IDs to full team names.
        :returns: Dictionary with team IDs as keys and full team strings as
        values.
        """
        doc = self.get_main_doc()
        team_ids = sportsref.utils.parse_table(
            doc('table#team-stats-per_game'), flatten=True)['team_name']
        team_names = sportsref.utils.parse_table(
            doc('table#team-stats-per_game'), flatten=False)['team_name']
        if len(team_names) != len(team_ids):
            raise Exception("team names and team IDs don't align")
        return dict(zip(team_ids, team_names))

    @sportsref.decorators.memoized
    def team_names_to_ids(self):
        """Mapping from full team names to 3-letter team IDs.
        :returns: Dictionary with tean names as keys and team IDs as values.
        """
        d = self.team_ids_to_names()
        return {v: k for k, v in d.items()}

    @sportsref.decorators.memoized
    @sportsref.decorators.kind_rpb(include_type=False)
    def get_boxscore_ids(self, kind='R'):
        """Returns a list of BoxScore IDs for every game in the season.
        Only needs to handle 'R' or 'P' options because decorator handles 'B'.

        :kind: 'R' for regular season, 'P' for playoffs, 'B' for both.
        :returns: List of IDs for nba.BoxScore objects.
        """
        doc = self.get_schedule_doc() # noqa
        raise Exception('not yet implemented - nba.Season.get_boxscore_ids')

    def finals_winner(self):
        """Returns the team ID for the winner of that year's NBA Finals.
        :returns: 3-letter team ID for champ.
        """
        doc = self.get_main_doc()
        playoff_table = doc('div#all_playoffs > table')
        anchor = playoff_table('tr').eq(0)('td').eq(1)('a').eq(0)
        href = sportsref.utils.rel_url_to_id(anchor.attr['href'])
        return href

    def finals_loser(self):
        """Returns the team ID for the loser of that year's NBA Finals.
        :returns: 3-letter team ID for runner-up..
        """
        doc = self.get_main_doc()
        playoff_table = doc('div#all_playoffs > table')
        anchor = playoff_table('tr').eq(0)('td').eq(1)('a').eq(1)
        href = sportsref.utils.rel_url_to_id(anchor.attr['href'])
        return href

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

    def team_stats(self):
        """Returns a Pandas DataFrame of each team's basic stat totals for the
        season.
        :returns: Pandas DataFrame of team stats, with team ID as index.
        """
        doc = self.get_main_doc()
        table = doc('table#team-stats-per_game')
        df = sportsref.utils.parse_table(table)
        df = df.drop('ranker', axis=1).set_index('team_name')
        df.index.name = 'team_id'
        return df

    def opp_stats(self):
        """Returns a Pandas DataFrame of each team's opponent's basic stat
        totals for the season.
        :returns: Pandas DataFrame of each team's opponent's stats, with team
        ID as index.
        """
        doc = self.get_main_doc()
        table = doc('table#opponent')
        df = sportsref.utils.parse_table(table)
        return df.drop('ranker', axis=1).set_index('team_name')

    def misc_stats(self, with_arena=False):
        """Returns a Pandas DataFrame of miscellaneous stats about each team's
        season.
        :with_arena: Include arena name column in DataFrame. Defaults to False.
        :returns: Pandas DataFrame of each team's miscellaneous season stats,
        with team ID as index.
        """
        doc = self.get_main_doc()
        table = doc('table#misc')
        df = sportsref.utils.parse_table(table)
        df['attendance'] = (df['attendance']
                            .str.replace(',', '')
                            .astype(float))
        df.fillna(df.mean(), inplace=True)
        if not with_arena:
            df.drop('arena_name', axis=1, inplace=True)
        return df.drop('ranker', axis=1).set_index('team_name')
