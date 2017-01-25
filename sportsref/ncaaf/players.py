import re
import collections
from lxml import etree
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Player',
]

@sportsref.decorators.memoize
class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = (sportsref.ncaaf.BASE_URL +
                        '/players/{0}.html'.format(self.pID))

    def __eq__(self, other):
        return self.pID == other.pID

    def __hash__(self):
        return hash(self.pID)

    @sportsref.decorators.memoize
    def get_doc(self):
        doc = pq(sportsref.utils.get_html(self.mainURL))
        return doc

    @sportsref.decorators.memoize
    def name(self):
        doc = self.get_doc()
        name = doc('div#meta h1:first').text()
        return name

    @sportsref.decorators.memoize
    def position(self):
        doc = self.get_doc()
        rawText = (doc('div#meta p')
                   .filter(lambda i,e: 'Position' in e.text_content())
                   .text())
        rawPos = re.search(r'Position : (\S+)', rawText, re.I).group(1)
        allPositions = rawPos.split('/')
        # TODO: returning just the first position for those with
        # multiple positions. Should return the last position played
        return allPositions

    @sportsref.decorators.memoize
    def height(self):
        doc = self.get_doc()
        rawText = doc('div#meta p span[itemprop="height"]').text()
        try:
            feet, inches = map(int, rawText.split('-'))
            return feet * 12 + inches
        except ValueError:
            return np.nan

    @sportsref.decorators.memoize
    def weight(self):
        doc = self.get_doc()
        rawText = doc('div#meta p span[itemprop="weight"]').text()
        try:
            weight = re.match(r'(\d+)lb', rawText, re.I).group(1)
            return int(weight)
        except AttributeError:
            return np.nan

    @sportsref.decorators.memoize
    def draft_pick(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()).text())
        m = re.search(r'Draft:.*?, (\d+).*?overall.*', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoize
    def draft_class(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()).text())
        m = re.search(r'Draft:.*?of the (\d+) NFL', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoize
    def draft_team(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()))
        draftStr = sportsref.utils.flatten_links(rawDraft)
        m = re.search(r'by the (\w{3})', draftStr)
        if not m:
            return np.nan
        else:
            return m.group(1)

    @sportsref.decorators.memoize
    def college(self):
        """Gets the last college (ID) that the player played for."""
        doc = self.get_doc()
        rawText = (doc('div#meta p')
                   .filter(lambda i, e: 'School' in e.text_content()))
        cleanedText = sportsref.utils.flatten_links(rawText)
        college = re.search(r'School:\s*(\S+)', cleanedText).group(1)
        return college

    @sportsref.decorators.memoize
    def gamelog(self, year=None):
        """Gets the career gamelog of the given player.
        :year: The year for which the gamelog should be returned; if None,
        return entire career gamelog. Defaults to None.
        :returns: A DataFrame with the player's career gamelog.
        """
        url = sportsref.nfl.BASE_URL, '/players/{0}/gamelog/'.format(self.pID)
        doc = pq(sportsref.utils.get_html(url))
        table = doc('#gamelog')
        df = sportsref.utils.parse_table(table)
        if year is not None:
            df = df.query('year == @year')
        return df

    # @sportsref.decorators.memoize
    def passing(self):
        """Gets yearly passing stats for the player.
        :returns: Pandas DataFrame with passing stats.
        """
        doc = self.get_doc()
        table = doc('table#passing')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def rushing_and_receiving(self):
        """Gets yearly rushing & receiving stats for the player.
        :returns: Pandas DataFrame with stats.
        """
        doc = self.get_doc()
        table = doc('table#rushing')
        if not table:
            table = doc('table#receiving')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def defense(self):
        """Gets yearly defensive stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.get_doc()
        table = doc('table#defense')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def scoring(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.get_doc()
        table = doc('table#scoring')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def returns(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.get_doc()
        table = doc('table#punt_ret')
        if not table:
            table = doc('table#kick_ret')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    def kicking(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.get_doc()
        table = doc('table#kicking')
        df = sportsref.utils.parse_table(table)
        return df

    def awards(self):
        """Gets the awards won by the player, if any.
        :returns: dictionary mapping year to awards won during that year.
        """
        ret = collections.defaultdict(list)
        doc = self.get_doc()
        anchors = doc('table#leaderboard td:contains("Awards and Honors") a')
        results = anchors.map(
            lambda i,e: sportsref.utils.rel_url_to_id(e.attrib['href'])
        )
        for yr, award in zip(*[iter(results)]*2):
            ret[int(yr)].append(award)
        return dict(ret)

    @sportsref.decorators.memoize
    def all_annual_stats(self):
        """Gets yearly all annual stats for the player by grabbing
        each individual dataset and then merging them for full years.
        :kind: One of 'R', 'P', or 'B'. Case-insensitive; defaults to 'R'.
        :returns: Pandas DataFrame with all annual stats.
        """
        dfPassing = self.passing()
        dfRushRec = self.rushing_and_receiving()
        dfDefense = self.defense()
        dfReturns = self.returns()
        dfKicking = self.kicking()
        dfScoring = self.scoring()
        # the mergeList declares the common fields to merge on
        mergeList = ['year', 'school_name', 'conf_abbr', 'class', 'pos', 'g']
        dfAll = pd.DataFrame(columns=mergeList)
        if not dfPassing.empty:
            dfAll = dfAll.merge(dfPassing, 'outer', mergeList)
        if not dfRushRec.empty:
            dfAll = dfAll.merge(dfRushRec, 'outer', mergeList)
        if not dfDefense.empty:
            dfAll = dfAll.merge(dfDefense, 'outer', mergeList)
        if not dfReturns.empty:
            dfAll = dfAll.merge(dfReturns, 'outer', mergeList)
        if not dfKicking.empty:
            dfAll = dfAll.merge(dfKicking, 'outer', mergeList)
        if not dfScoring.empty:
            dfAll = dfAll.merge(dfScoring, 'outer', mergeList)
        return dfAll

def get_college_leaders_one_year(year):
    """ Returns college leader ids for a year from
    http://www.sports-reference.com/cfb

    :param year: the year for the data pull
    :return: A dataframe with the college id and college team name
    """
    # set link and table_name and then get the pyquery table
    link = "http://www.sports-reference.com/cfb/years/" + str(year) + \
           "-leaders.html"
    doc = pq(sportsref.utils.get_html(link))
    table = doc('#div_leaders')

    # check if valid return
    if not len(table):
        return pd.DataFrame()
    else:
        # identify columns, rows, data, and make dataframe
        rows = list(table('tr').items())
        data = []
        for row in rows:
            data.append([sportsref.utils.flatten_links(td)
                        .encode('ascii', 'ignore').split('  ')
                         for td in row.items('td') if
                         td.attr('class') == "who"].pop(0))
        players_one_yr = pd.DataFrame(data, columns=['collegeid', 'college'])
        return players_one_yr
