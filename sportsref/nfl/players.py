import re
import datetime

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from .. import decorators, utils
from . import NFL_BASE_URL

__all__ = [
    'Player',
]

@decorators.memoized
class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = (NFL_BASE_URL +
                        '/players/{0[0]}/{0}.htm').format(self.pID)

    def __eq__(self, other):
        return self.pID == other.pID

    def __hash__(self):
        return hash(self.pID)

    def __reduce__(self):
        return Player, (self.pID,)

    @decorators.memoized
    def getDoc(self):
        doc = pq(utils.getHTML(self.mainURL))
        return doc

    @decorators.memoized
    def name(self):
        doc = self.getDoc()
        name = doc('div#meta h1:first').text()
        return name

    @decorators.memoized
    def age(self, year, month=9, day=1):
        doc = self.getDoc()
        span = doc('div#meta span#necro-birth')
        birthstring = span.attr('data-birth')
        dateargs = re.match(r'(\d{4})\-(\d{2})\-(\d{2})', birthstring).groups()
        dateargs = map(int, dateargs)
        birthDate = datetime.date(*dateargs)
        delta = datetime.date(year=year, month=month, day=day) - birthDate
        age = delta.days / 365.
        return age

    @sportsref.decorators.memoized
    def position(self):
        doc = self.getDoc()
        rawText = (doc('div#meta p')
                   .filter(lambda i,e: 'Position' in e.text_content())
                   .text())
        rawPos = re.search(r'Position\W*(\S+)', rawText, re.I).group(1)
        allPositions = rawPos.split('-')
        # right now, returning just the primary position for those with
        # multiple positions
        return allPositions[0]

    @sportsref.decorators.memoized
    def height(self):
        doc = self.getDoc()
        rawText = doc('div#meta p span[itemprop="height"]').text()
        feet, inches = map(int, rawText.split('-'))
        return feet * 12 + inches

    @sportsref.decorators.memoized
    def weight(self):
        doc = self.getDoc()
        rawText = doc('div#meta p span[itemprop="weight"]').text()
        weight = re.match(r'(\d+)lb', rawText, re.I).group(1)
        return int(weight)

    @sportsref.decorators.memoized
    def hand(self):
        doc = self.getDoc()
        try:
            rawText = (doc('div#meta p')
                       .filter(lambda i,e: 'Throws' in e.text_content())
                       .text())
            rawHand = re.search(r'Throws\W+(\S+)', rawText, re.I).group(1)
        except AttributeError:
            return np.nan
        return rawHand[0] # 'L' or 'R'

    @sportsref.decorators.memoized
    def draftPick(self):
        doc = self.getDoc()
        rawDraft = doc('div#meta p:contains("Draft")').text()
        m = re.search(r'Draft.*? round \((\d+).*?overall\)', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if not m or 'Supplemental' in rawDraft:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftClass(self):
        doc = self.getDoc()
        rawDraft = doc('div#meta p:contains("Draft")').text()
        m = re.search(r'Draft.*?of the (\d{4}) NFL', rawDraft, re.I)
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoized
    def draftTeam(self):
        doc = self.getDoc()
        rawDraft = doc('div#meta p:contains("Draft")')
        draftStr = sportsref.utils.flattenLinks(rawDraft)
        m = re.search(r'Draft\W+(\w+)', draftStr)
        if not m:
            return np.nan
        else:
            return m.group(1)

    @sportsref.decorators.memoized
    def college(self):
        doc = self.getDoc()
        rawText = doc('div#meta p:contains("College")')
        cleanedText = sportsref.utils.flattenLinks(rawText)
        college = re.search(r'College: (\S+)', cleanedText).group(1)
        return college

    @sportsref.decorators.memoized
    def highSchool(self):
        doc = self.getDoc()
        rawText = doc('div#meta p:contains("High School")')
        cleanedText = sportsref.utils.flattenLinks(rawText)
        hs = re.search(r'High School: (\S+)', cleanedText).group(1)
        return hs

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
        url = (NFL_BASE_URL + '/players/{0[0]}/{0}/gamelog').format(self.pID)
        doc = pq(utils.getHTML(url))
        table = doc('#stats') if kind == 'R' else doc('#stats_playoffs')
        df = utils.parseTable(table)
        if year is not None:
            df = df.query('year == @year').reset_index(drop=True)
        return df

    @decorators.memoized
    @decorators.kindRPB(include_type=True)
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
