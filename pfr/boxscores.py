import datetime
import re
import urlparse

import requests
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import pfr

__all__ = [
    'BoxScore',
]

yr = datetime.datetime.now().year

class BoxScore:

    def __init__(self, bsID):
        self.bsID = bsID
        self.mainURL = urlparse.urljoin(
            pfr.BASE_URL, '/boxscores/{}.htm'.format(self.bsID)
        )

    def __eq__(self, other):
        return self.bsID == other.bsID

    def __hash__(self):
        return hash(self.bsID)

    @pfr.decorators.memoized
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.bsID)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @pfr.decorators.memoized
    def weekday(self):
        """Returns the day of the week on which the game occurred.
        :returns: String representation of the day of the week for the game.

        """
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @pfr.decorators.memoized
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        table = doc('table#linescore')
        home = pfr.utils.relURLToID(pq(table('tr')[2])('a').attr['href'])
        return home

    @pfr.decorators.memoized
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        table = doc('table#linescore')
        away = pfr.utils.relURLToID(pq(table('tr')[1])('a').attr['href'])
        return away

    @pfr.decorators.memoized
    def homeScore(self):
        """Returns score of the home team.
        :returns: int of the home score.

        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        table = doc('table#linescore')
        homeScore = pq(table('tr')[2])('td')[-1].text_content()
        return int(homeScore)

    @pfr.decorators.memoized
    def awayScore(self):
        """Returns score of the away team.
        :returns: int of the away score.

        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        table = doc('table#linescore')
        awayScore = pq(table('tr')[1])('td')[-1].text_content()
        return int(awayScore)

    @pfr.decorators.memoized
    def starters(self):
        """Returns a DataFrame where each row is an entry in the starters table
        from PFR. The columns are:
        * playerID - the PFR player ID for the player (note that this column is
        not necessarily all unique; that is, one player can be a starter in
        multiple positions, in theory).
        * playerName - the listed name of the player; this too is not
        necessarily unique.
        * position - the position at which the player started for their team.
        * team - the team for which the player started.
        * home - True if the player's team was at home, False if they were away
        * offense - True if the player is starting on an offensive position,
        False if defense.

        :returns: A pandas DataFrame. See the description for details.
        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        pretable = next(div for div in map(pq, doc('div.table_heading')) 
                        if div('h2:contains("Starting Lineups")'))
        tableCont = map(pq, pretable.nextAll('div.table_container')[:2])
        a, h = (tc('table.stats_table') for tc in tableCont)
        data = []
        for h, table in enumerate((a, h)):
            team = self.home() if h else self.away()
            for i, row in enumerate(map(pq, table('tr[class=""]'))):
                datum = {}
                datum['playerID'] = pfr.utils.relURLToID(
                    row('a')[0].attrib['href']
                )
                datum['playerName'] = row('a').filter(
                    lambda i,e: len(e.text_content()) > 0
                ).text()
                datum['position'] = row('td')[1].text_content()
                datum['team'] = team
                datum['home'] = (h == 1)
                datum['offense'] = (i <= 10)
                data.append(datum)
        return pd.DataFrame(data)

    @pfr.decorators.memoized
    def gameInfo(self):
        """Gets a dictionary of basic information about the game.
        :returns: Dictionary of game information.

        """
        # starting values
        giDict = {
            'home': self.home(),
            'homeScore': self.homeScore(),
            'away': self.away(),
            'awayScore': self.awayScore(),
            'weekday': self.weekday(),
        }
        doc = pq(pfr.utils.getHTML(self.mainURL))
        giTable = doc('table#game_info')
        for tr in map(pq, giTable('tr[class=""]')):
            td0, td1 = tr('td')
            key = td0.text_content()
            # keys to skip
            if key in ('Tickets'):
                continue
            # small adjustments
            elif key == 'Stadium':
                val = pfr.utils._flattenLinks(td1).strip()
            elif key == 'Attendance':
                val = int(td1.text_content().replace(',',''))
            elif key == 'Over/Under':
                val = float(td1.text_content().split()[0])
            elif key == 'Won Toss':
                txt = td1.text_content()
                if 'deferred' in txt:
                    giDict['deferred'] = True
                    defIdx = txt.index('deferred')
                    tm = txt[:defIdx-2]
                else:
                    giDict['deferred'] = False
                    tm = txt

                if tm in pfr.teams.Team(self.home()).name():
                    giDict['wonToss'] = self.home()
                else:
                    giDict['wonToss'] = self.away()

                continue
            # create datetime.time object for start time
            elif key == 'Start Time (ET)':
                txt = td1.text_content()
                colon = txt.index(':')
                hour = int(txt[:colon])
                mins = int(txt[colon+1:colon+3])
                hour += (0 if txt[colon+3] == 'a' else 12)
                giDict['startTimeET'] = datetime.time(hour=hour, minute=mins)
                continue
            # give duration in minutes
            elif key == 'Duration':
                hrs, mins = td1.text_content().split(':')
                val = int(hrs)*60 + int(mins)
            elif key == 'Vegas Line':
                favorite, line = re.match(r'(.+?) ([\-\.\d]+)',
                                          td1.text_content()).groups()
                line = float(line)
                # given in terms of the home team
                if favorite != pfr.teams.Team(self.home()).name():
                    line = -line
                giDict['line'] = line 
                giDict['favorite'] = self.home() if line < 0 else self.away()
                continue
            else:
                val = td1.text_content().strip()
            giDict[key] = val

        return giDict

    @pfr.decorators.memoized
    def pbp(self, keepErrors=False):
        """Returns a dataframe of the play-by-play data from the game.

        :keepErrors: See pfr.utils.expandDetails.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.

        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        table = doc('table#pbp_data')
        pbp = pfr.utils.parseTable(table)
        pbp['bsID'] = self.bsID
        pbp['home'] = self.home()
        pbp['away'] = self.away()
        pbp = pfr.utils.expandDetails(pbp, keepErrors=keepErrors)
        return pbp

    def refInfo(self):
        """Gets a dictionary of ref positions and the ref IDs of the refs for
        that game.
        :returns: A dictionary of ref positions and IDs.

        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        refDict = {}
        refTable = doc('table#ref_info')
        for tr in map(pq, refTable('tr[class=""]')):
            td0, td1 = tr('td')
            key = td0.text_content().lower().replace(' ', '_')
            val = pfr.utils._flattenLinks(td1)
            refDict[key] = val
        return refDict

    @pfr.decorators.memoized
    def playerStats(self):
        """Gets the stats for offense, defense, returning, and kicking of
        individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = pq(pfr.utils.getHTML(self.mainURL))
        tableIDs = ('skill_stats', 'def_stats', 'st_stats', 'kick_stats')
        dfs = []
        for tID in tableIDs:
            table = doc('#{}'.format(tID))
            dfs.append(pfr.utils.parseTable(table))
        df = pd.concat(dfs)
        df = df.reset_index(drop=True)
        df['team'] = df['team'].str.lower()
        return df
