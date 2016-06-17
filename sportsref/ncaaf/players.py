import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Player',
]

yr = datetime.datetime.now().year

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
        name = doc('div#info_box h1:first').text()
        return name

    @sportsref.decorators.memoized
    def position(self):
        doc = self.getDoc()
        rawText = (doc('div#info_box p')
                   .filter(lambda i,e: 'Position' in e.text_content())
                   .text())
        rawPos = re.search(r'Position: (\S+)', rawText, re.I).group(1)
        allPositions = rawPos.split('-')
        # TODO: right now, returning just the primary position for those with
        # multiple positions
        return allPositions[0]

    @sportsref.decorators.memoized
    def height(self):
        doc = self.getDoc()
        try:
            rawText = (doc('div#info_box p')
                       .filter(
                           lambda i,e: 'height:' in e.text_content().lower()
                       ).text())
            rawHeight = (re.search(r'Height: (\d\-\d{1,2})', rawText, re.I)
                         .group(1))
        except AttributeError:
            return np.nan
        feet, inches = map(int, rawHeight.split('-'))
        return feet*12 + inches

    @sportsref.decorators.memoized
    def weight(self):
        doc = self.getDoc()
        try:
            rawText = (doc('div#info_box p')
                       .filter(lambda i,e: 'Weight:' in e.text_content())
                       .text())
            rawWeight = re.search(r'Weight: (\S+)', rawText, re.I).group(1)
        except AttributeError:
            return np.nan
        return int(rawWeight)

    @sportsref.decorators.memoized
    def draftPick(self):
        doc = self.getDoc()
        rawDraft = doc('div#info_box > p:contains("Draft")').text()
        m = re.search(r'Draft:.*?, (\d+).*?overall.*', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftClass(self):
        doc = self.getDoc()
        rawDraft = doc('div#info_box > p:contains("Draft")').text()
        m = re.search(r'Draft:.*?of the (\d+) NFL', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftTeam(self):
        doc = self.getDoc()
        rawDraft = doc('div#info_box > p:contains("Draft")')
        draftStr = sportsref.utils.flattenLinks(rawDraft)
        m = re.search(r'by the (\w{3})', draftStr)
        if not m:
            return np.nan
        else:
            return m.group(1)

    @sportsref.decorators.memoized
    def college(self):
        """Gets the last college that the player played for."""
        doc = self.getDoc()
        aTag = doc('div#info_box > p:first a:last')
        college = sportsref.utils.relURLToID(aTag.attr['href'])
        return college

    # TODO: scrape player features that will be used for analysis
    # ex: pass/rush/rec/def season/career stats + awards
    # after that, get college-level and conference-level features

    @sportsref.decorators.memoized
    @sportsref.decorators.kindRPB(include_type=True)
    def gamelog(self, kind='R', year=None):
        """Gets the career gamelog of the given player.
        :kind: One of 'R', 'P', or 'B' (for regular season, playoffs, or both).
        Case-insensitive; defaults to 'R'.
        :year: The year for which the gamelog should be returned; if None,
        return entire career gamelog. Defaults to None.
        :returns: A DataFrame with the player's career gamelog.
        """
        url = urlparse.urljoin(
            sportsref.nfl.BASE_URL, '/players/{0[0]}/{0}/gamelog'
        ).format(self.pID)
        doc = pq(sportsref.utils.getHTML(url))
        table = doc('#stats') if kind == 'R' else doc('#stats_playoffs')
        df = sportsref.utils.parseTable(table)
        if year is not None:
            df = df.query('year == @year')
        return df

    @sportsref.decorators.memoized
    @sportsref.decorators.kindRPB(include_type=True)
    def passing(self, kind='R'):
        """Gets yearly passing stats for the player.

        :kind: One of 'R', 'P', or 'B'. Case-insensitive; defaults to 'R'.
        :returns: Pandas DataFrame with passing stats.
        """
        doc = self.getDoc()
        table = doc('#passing') if kind == 'R' else doc('#passing_playoffs')
        df = sportsref.utils.parseTable(table)
        return df

    # TODO: differentiate regular season and playoffs
    @sportsref.decorators.memoized
    def rushing_and_receiving(self):
        doc = self.getDoc()
        table = doc('#rushing_and_receiving')
        df = sportsref.utils.parseTable(table)
        return df
