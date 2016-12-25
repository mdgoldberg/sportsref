import datetime
import re
import urlparse

import numpy as np
from pyquery import PyQuery as pq
import six

import sportsref

__all__ = [
    'Player',
]


class Player(six.with_metaclass(sportsref.decorators.Cached, object)):

    def __init__(self, player_id):
        self.player_id = player_id
        self.mainURL = (sportsref.nfl.BASE_URL +
                        '/players/{0[0]}/{0}.htm').format(self.player_id)

    def __eq__(self, other):
        return self.player_id == other.player_id

    def __hash__(self):
        return hash(self.player_id)

    def __repr__(self):
        return 'Player({})'.format(self.player_id)

    def __str__(self):
        return self.name()

    def __reduce__(self):
        return Player, (self.player_id,)

    def _subpage_url(self, page, year=None):
        # if no year, return career version
        if year is None:
            return urlparse.urljoin(
                self.mainURL, '{}/{}/'.format(self.player_id, page)
            )
        # otherwise, return URL for a given year
        else:
            return urlparse.urljoin(
                self.mainURL, '{}/{}/{}/'.format(self.player_id, page, year)
            )

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
    def age(self, year, month=9, day=1):
        doc = self.get_doc()
        span = doc('div#meta span#necro-birth')
        birthstring = span.attr('data-birth')
        try:
            dateargs = re.match(r'(\d{4})\-(\d{2})\-(\d{2})',
                                birthstring).groups()
            dateargs = map(int, dateargs)
            birthDate = datetime.date(*dateargs)
            delta = datetime.date(year=year, month=month, day=day) - birthDate
            age = delta.days / 365.
            return age
        except Exception:
            return np.nan

    @sportsref.decorators.memoize
    def position(self):
        doc = self.get_doc()
        rawText = (doc('div#meta p')
                   .filter(lambda i, e: 'Position' in e.text_content())
                   .text())
        rawPos = re.search(r'Position\W*(\S+)', rawText, re.I).group(1)
        allPositions = rawPos.split('-')
        # right now, returning just the primary position for those with
        # multiple positions
        return allPositions[0]

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
    def hand(self):
        doc = self.get_doc()
        try:
            rawText = (doc('div#meta p')
                       .filter(lambda i, e: 'Throws' in e.text_content())
                       .text())
            rawHand = re.search(r'Throws\W+(\S+)', rawText, re.I).group(1)
        except AttributeError:
            return np.nan
        return rawHand[0]  # 'L' or 'R'

    @sportsref.decorators.memoize
    def current_team(self):
        doc = self.get_doc()
        team = (doc('div#meta p')
                .filter(lambda i, e: 'Team' in e.text_content()))
        text = sportsref.utils.flatten_links(team)
        try:
            m = re.match(r'Team: (\w{3})', text)
            return m.group(1)
        except Exception:
            return np.nan

    @sportsref.decorators.memoize
    def draft_pick(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content())
                    .text())
        m = re.search(r'Draft.*? round \((\d+).*?overall\)', rawDraft, re.I)
        # if not drafted or taken in supplemental draft, return NaN
        if m is None or 'Supplemental' in rawDraft:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoize
    def draft_class(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content())
                    .text())
        m = re.search(r'Draft.*?of the (\d{4}) NFL', rawDraft, re.I)
        if not m:
            return np.nan
        else:
            return int(m.group(1))

    @sportsref.decorators.memoize
    def draft_team(self):
        doc = self.get_doc()
        rawDraft = (doc('div#meta p')
                    .filter(lambda i, e: 'Draft' in e.text_content()))
        try:
            draftStr = sportsref.utils.flatten_links(rawDraft)
            m = re.search(r'Draft\W+(\w+)', draftStr)
            return m.group(1)
        except Exception:
            return np.nan

    @sportsref.decorators.memoize
    def college(self):
        doc = self.get_doc()
        rawText = (doc('div#meta p')
                   .filter(lambda i, e: 'College' in e.text_content()))
        cleanedText = sportsref.utils.flatten_links(rawText)
        college = re.search(r'College:\s*(\S+)', cleanedText).group(1)
        return college

    @sportsref.decorators.memoize
    def high_school(self):
        doc = self.get_doc()
        rawText = (doc('div#meta p')
                   .filter(lambda i, e: 'High School' in e.text_content()))
        cleanedText = sportsref.utils.flatten_links(rawText)
        hs = re.search(r'High School:\s*(\S+)', cleanedText).group(1)
        return hs

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def gamelog(self, year=None, kind='R'):
        """Gets the career gamelog of the given player.
        :kind: One of 'R', 'P', or 'B' (for regular season, playoffs, or both).
        Case-insensitive; defaults to 'R'.
        :year: The year for which the gamelog should be returned; if None,
        return entire career gamelog. Defaults to None.
        :returns: A DataFrame with the player's career gamelog.
        """
        url = self._subpage_url('gamelog', None)  # year is filtered later
        doc = pq(sportsref.utils.get_html(url))
        table = doc('#stats') if kind == 'R' else doc('#stats_playoffs')
        df = sportsref.utils.parse_table(table)
        if year is not None:
            df = df.query('year == @year').reset_index(drop=True)
        return df

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def passing(self, kind='R'):
        """Gets yearly passing stats for the player.

        :kind: One of 'R', 'P', or 'B'. Case-insensitive; defaults to 'R'.
        :returns: Pandas DataFrame with passing stats.
        """
        doc = self.get_doc()
        table = doc('#passing') if kind == 'R' else doc('#passing_playoffs')
        df = sportsref.utils.parse_table(table)
        return df

    @sportsref.decorators.memoize
    @sportsref.decorators.kind_rpb(include_type=True)
    def rushing_and_receiving(self, kind='R'):
        """Gets yearly rushing/receiving stats for the player.

        :kind: One of 'R', 'P', or 'B'. Case-insensitive; defaults to 'R'.
        :returns: Pandas DataFrame with rushing/receiving stats.
        """
        doc = self.get_doc()
        table = (doc('#rushing_and_receiving') if kind == 'R'
                 else doc('#rushing_and_receiving_playoffs'))
        if not table:
            table = (doc('#receiving_and_rushing') if kind == 'R'
                     else doc('#receiving_and_rushing_playoffs'))
        df = sportsref.utils.parse_table(table)
        return df

    def _plays(self, year, play_type):
        """Returns a DataFrame of plays for a given year for a given play type
        (like rushing, receiving, or passing).

        :year: The year for the season.
        :play_type: A type of play for which there are plays (as of this
        writing, either "passing", "rushing", or "receiving")
        :returns: A DataFrame of plays, each row is a play. Returns None if
        there were no such plays in that year.
        """
        url = self._subpage_url('{}-plays'.format(play_type), year)
        doc = pq(sportsref.utils.get_html(url))
        table = doc('table#all_plays')
        if table:
            plays = sportsref.nfl.pbp.expand_details(
                sportsref.utils.parse_table(table), detailCol='description'
            )
            return plays
        else:
            return None

    @sportsref.decorators.memoize
    def passing_plays(self, year):
        """Returns a pbp DataFrame of a player's passing plays in a season.

        :year: The year for the season.
        :returns: A DataFrame of stats, each row is a play.
        """
        return self._plays(year, 'passing')

    @sportsref.decorators.memoize
    def rushing_plays(self, year):
        """Returns a pbp DataFrame of a player's rushing plays in a season.

        :year: The year for the season.
        :returns: A DataFrame of stats, each row is a play.
        """
        return self._plays(year, 'rushing')

    @sportsref.decorators.memoize
    def receiving_plays(self, year):
        """Returns a pbp DataFrame of a player's receiving plays in a season.

        :year: The year for the season.
        :returns: A DataFrame of stats, each row is a play.
        """
        return self._plays(year, 'receiving')

    @sportsref.decorators.memoize
    def splits(self, year=None):
        """Returns a DataFrame of splits data for a player-year.

        :year: The year for the season in question. If None, returns career
        splits.
        :returns: A DataFrame of splits data.
        """
        # get the table
        url = self._subpage_url('splits', year)
        doc = pq(sportsref.utils.get_html(url))
        table = doc('table#stats')
        df = sportsref.utils.parse_table(table)
        # cleaning the data
        if not df.empty:
            df.split_id.fillna(method='ffill', inplace=True)
        return df

    @sportsref.decorators.memoize
    def advanced_splits(self, year=None):
        """Returns a DataFrame of advanced splits data for a player-year.

        :year: The year for the season in question. If None, returns career
        advanced splits.
        :returns: A DataFrame of advanced splits data.
        """
        # get the table
        url = self._subpage_url('splits', year)
        doc = pq(sportsref.utils.get_html(url))
        table = doc('table#advanced_splits')
        df = sportsref.utils.parse_table(table)
        # cleaning the data
        if not df.empty:
            df.split_type.fillna(method='ffill', inplace=True)
        return df
