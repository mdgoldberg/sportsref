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

@sportsref.decorators.memoized
class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = (sportsref.ncaaf.BASE_URL +
                        '/players/{0}.html'.format(self.pID))

    def __eq__(self, other):
        return self.pID == other.pID

    def __hash__(self):
        return hash(self.pID)

    @sportsref.decorators.memoized
    def getDoc(self):
        doc = pq(sportsref.utils.getHTML(self.mainURL))
        return doc

    @sportsref.decorators.memoized
    def name(self):
        doc = self.getDoc()
        name = doc('div#meta h1:first').text()
        return name

    @sportsref.decorators.memoized
    def position(self):
        doc = self.getDoc()
        rawText = (doc('div#meta p')
                   .filter(lambda i,e: 'Position' in e.text_content())
                   .text())
        rawPos = re.search(r'Position : (\S+)', rawText, re.I).group(1)
        allPositions = rawPos.split('/')
        # TODO: returning just the first position for those with
        # multiple positions. Should return the last position played
        return allPositions[0]

    @sportsref.decorators.memoized
    def height(self):
        doc = self.getDoc()
        rawText = doc('div#meta p span[itemprop="height"]').text()
        try:
            feet, inches = map(int, rawText.split('-'))
            return feet * 12 + inches
        except ValueError:
            return np.nan

    @sportsref.decorators.memoized
    def weight(self):
        doc = self.getDoc()
        rawText = doc('div#meta p span[itemprop="weight"]').text()
        try:
            weight = re.match(r'(\d+)lb', rawText, re.I).group(1)
            return int(weight)
        except AttributeError:
            return np.nan

    @sportsref.decorators.memoized
    def draftPick(self):
        doc = self.getDoc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()).text())
        m = re.search(r'Draft:.*?, (\d+).*?overall.*', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftClass(self):
        doc = self.getDoc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()).text())
        m = re.search(r'Draft:.*?of the (\d+) NFL', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftTeam(self):
        doc = self.getDoc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()))
        draftStr = sportsref.utils.flattenLinks(rawDraft)
        m = re.search(r'by the (\w{3})', draftStr)
        if not m:
            return np.nan
        else:
            return m.group(1)

    @sportsref.decorators.memoized
    def college(self):
        """Gets the last college (ID) that the player played for."""
        doc = self.getDoc()
        rawText = (doc('div#meta p')
                   .filter(lambda i, e: 'School' in e.text_content()))
        cleanedText = sportsref.utils.flattenLinks(rawText)
        college = re.search(r'School:\s*(\S+)', cleanedText).group(1)
        return college

    @sportsref.decorators.memoized
    def gamelog(self, year=None):
        """Gets the career gamelog of the given player.
        :year: The year for which the gamelog should be returned; if None,
        return entire career gamelog. Defaults to None.
        :returns: A DataFrame with the player's career gamelog.
        """
        url = sportsref.nfl.BASE_URL, '/players/{0}/gamelog/'.format(self.pID)
        doc = pq(sportsref.utils.getHTML(url))
        table = doc('#gamelog')
        df = sportsref.utils.parseTable(table)
        if year is not None:
            df = df.query('year == @year')
        return df

    @sportsref.decorators.memoized
    def passing(self):
        """Gets yearly passing stats for the player.
        :returns: Pandas DataFrame with passing stats.
        """
        doc = self.getDoc()
        table = doc('#passing')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def rushing_and_receiving(self):
        """Gets yearly rushing & receiving stats for the player.
        :returns: Pandas DataFrame with stats.
        """
        doc = self.getDoc()
        table = doc('#all_rushing')
        if not table:
            table = doc('#all_receiving')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def defense(self):
        """Gets yearly defensive stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.getDoc()
        table = doc('#all_defense')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def scoring(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.getDoc()
        table = doc('#all_scoring')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def punt_kick_returns(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.getDoc()
        table = doc('#all_punt_ret')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    @sportsref.decorators.memoized
    def kicking(self):
        """Gets yearly scoring stats for the player.
        :returns: Pandas DataFrame with defensive stats.
        """
        doc = self.getDoc()
        table = doc('#all_kicking')
        df = sportsref.utils.parseTable(table)
        if df.empty and table.length > 0:
            tree = etree.fromstring(str(table))
            comments = tree.xpath('//comment()')
            comment = etree.tostring(comments[0])
            contents = comment.replace("<!--", "").replace("-->", "")
            table = pq(contents)
            df = sportsref.utils.parseTable(table)
        return df

    def awards(self):
        """Gets the awards won by the player, if any.
        :returns: dictionary mapping year to awards won during that year.
        """
        ret = collections.defaultdict(list)
        doc = self.getDoc()
        anchors = doc('table#leaderboard td:contains("Awards and Honors") a')
        results = anchors.map(
            lambda i,e: sportsref.utils.relURLToID(e.attrib['href'])
        )
        for yr, award in zip(*[iter(results)]*2):
            ret[int(yr)].append(award)
        return dict(ret)

    @sportsref.decorators.memoized
    def all_annual_stats(self):
        """Gets yearly all annual stats for the player by grabbing
        each individual dataset and then merging them for full years.
        :kind: One of 'R', 'P', or 'B'. Case-insensitive; defaults to 'R'.
        :returns: Pandas DataFrame with all annual stats.
        """
        dfPassing = self.passing()
        # dfPassing = dfPassing.ix[dfPassing["has_class_full_table"]]
        dfRushRec = self.rushing_and_receiving()
        # dfRushRec = dfRushRec.ix[dfRushRec["has_class_full_table"]]
        dfDefense = self.defense()
        # dfDefense = dfDefense.ix[dfDefense["has_class_full_table"]]
        dfReturns = self.punt_kick_returns()
        # dfReturns = dfReturns.ix[dfReturns["has_class_full_table"]]
        dfKicking = self.kicking()
        # dfKicking = dfKicking.ix[dfKicking["has_class_full_table"]]
        dfScoring = self.scoring()
        # dfScoring = dfScoring.ix[dfScoring["has_class_full_table"]]
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
