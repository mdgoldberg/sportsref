import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'BoxScore',
]

yr = datetime.datetime.now().year

@sportsref.decorators.memoized
class BoxScore:

    def __init__(self, bsID):
        self.bsID = bsID

    def __eq__(self, other):
        return self.bsID == other.bsID

    def __hash__(self):
        return hash(self.bsID)

    @sportsref.decorators.memoized
    def getDoc(self):
        url = urlparse.urljoin(
            sportsref.nfl.BASE_URL, 'boxscores/{}.htm'.format(self.bsID)
        )
        doc = pq(sportsref.utils.getHTML(url))
        return doc

    @sportsref.decorators.memoized
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.bsID)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoized
    def weekday(self):
        """Returns the day of the week on which the game occurred.
        :returns: String representation of the day of the week for the game.

        """
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoized
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.getDoc()
        table = doc('table#linescore')
        home = sportsref.utils.relURLToID(table('tr').eq(2)('a').attr['href'])
        return home

    @sportsref.decorators.memoized
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.getDoc()
        table = doc('table#linescore')
        away = sportsref.utils.relURLToID(table('tr').eq(1)('a').attr['href'])
        return away

    @sportsref.decorators.memoized
    def homeScore(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        doc = self.getDoc()
        table = doc('table#linescore')
        homeScore = table('tr').eq(2)('td')[-1].text_content()
        return int(homeScore)

    @sportsref.decorators.memoized
    def awayScore(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        doc = self.getDoc()
        table = doc('table#linescore')
        awayScore = table('tr').eq(1)('td')[-1].text_content()
        return int(awayScore)

    @sportsref.decorators.memoized
    def winner(self):
        """Returns the team ID of the winning team. Returns NaN if a tie."""
        hmScore = self.homeScore()
        awScore = self.awayScore()
        if hmScore > awScore:
            return self.home()
        elif hmScore < awScore:
            return self.away()
        else:
            return np.nan

    @sportsref.decorators.memoized
    def week(self):
        """Returns the week in which this game took place. 18 is WC round, 19
        is Div round, 20 is CC round, 21 is SB.
        :returns: Integer from 1 to 21.
        """
        doc = self.getDoc()
        rawTxt = doc('div#page_content table').eq(0)('tr td').eq(0).text()
        match = re.search(r'Week (\d+)', rawTxt)
        if match:
            return int(match.group(1))
        else:
            return 21 # super bowl is week 21

    @sportsref.decorators.memoized
    def season(self):
        """
        Returns the year ID of the season in which this game took place.
        Useful for week 17 January games.

        :returns: An int representing the year of the season.
        """
        doc = self.getDoc()
        rawTxt = doc('div#page_content table').eq(0)('tr td').eq(0).text()
        match = re.search(r'Week \d+ (\d{4})', rawTxt)
        if match:
            return int(match.group(1))
        else:
            # super bowl happens in calendar year after the season's year
            return self.date().year - 1 

    @sportsref.decorators.memoized
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
        doc = self.getDoc()
        pretable = next(div for div in doc('div.table_heading').items()
                        if div('h2:contains("Starting Lineups")'))
        tableCont = pretable.nextAll('div.table_container')
        tableCont = [tableCont.eq(0), tableCont.eq(1)]
        a, h = (tc('table.stats_table') for tc in tableCont)
        data = []
        for h, table in enumerate((a, h)):
            team = self.home() if h else self.away()
            for i, row in enumerate(table('tr[class=""]').items()):
                datum = {}
                datum['playerID'] = sportsref.utils.relURLToID(
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

    @sportsref.decorators.memoized
    def gameInfo(self):
        """Gets a dictionary of basic information about the game. Note: line
        is given in terms of the home team (if the home team is favored, the
        line will be negative).
        :returns: Dictionary of game information.

        """
        # starting values
        giDict = {
            'home': self.home(),
            'home_score': self.homeScore(),
            'away': self.away(),
            'away_score': self.awayScore(),
            'weekday': self.weekday(),
            'line': self.line(),
            'weather': self.weather()
        }
        doc = self.getDoc()
        giTable = doc('table#game_info')
        for tr in giTable('tr[class=""]').items():
            td0, td1 = tr('td').items()
            key = td0.text().lower()
            key = re.sub(r'\W+', '_', key).strip('_')
            # keys to skip
            if key in ['tickets']:
                continue
            # adjustments
            elif key == 'attendance':
                val = int(td1.text().replace(',',''))
            elif key == 'over_under':
                val = float(td1.text().split()[0])
            elif key == 'won_toss':
                txt = td1.text()
                if 'deferred' in txt:
                    giDict['deferred'] = True
                    defIdx = txt.index('deferred')
                    tm = txt[:defIdx-2]
                else:
                    giDict['deferred'] = False
                    tm = txt

                if tm in sportsref.nfl.teams.Team(self.home()).name():
                    val = self.home()
                else:
                    val = self.away()
            # create datetime.time object for start time
            elif key == 'start_time_et':
                txt = td1.text()
                colon = txt.index(':')
                hour = int(txt[:colon])
                mins = int(txt[colon+1:colon+3])
                hour += (0 if txt[colon+3] == 'a' or hour == 12 else 12)
                val = datetime.time(hour=hour, minute=mins)
            # give duration in minutes
            elif key == 'duration':
                hrs, mins = td1.text().split(':')
                val = int(hrs)*60 + int(mins)
            # keys to skip since they're already added
            elif key in ('vegas_line', 'weather'):
                continue
            else:
                val = sportsref.utils.flattenLinks(td1).strip()
            giDict[key] = val

        return giDict

    @sportsref.decorators.memoized
    def line(self):
        doc = self.getDoc()
        table = doc('table#game_info tr')
        tr = table.filter(lambda i: 'Vegas Line' in this.text_content())
        td0, td1 = tr('td').items()
        m = re.match(r'(.+?) ([\-\.\d]+)$', td1.text())
        if m:
            favorite, line = m.groups()
            line = float(line)
            # give in terms of the home team
            if favorite != sportsref.nfl.teams.teamNames()[self.home()]:
                line = -line
        else:
            line = 0
        return line

    @sportsref.decorators.memoized
    def weather(self):
        """Returns a dictionary of weather-related info.

        :returns: Dict of weather data; None if weather data not available.
        """
        doc = self.getDoc()
        table = doc('table#game_info tr')
        tr = table.filter(lambda i: 'Weather' in this.text_content())
        if len(tr) == 0:
            # no weather found, because it's a dome
            # TODO: what's relative humidity in a dome?
            return {
                'temp': 70, 'windChill': 70, 'relHumid': None, 'windMPH': 0
            }
        td0, td1 = tr('td').items()
        regex = (
            r'(?:(?P<temp>\-?\d+) degrees )?'
            r'(?:relative humidity (?P<relHumid>\d+)%, )?'
            r'(?:wind (?P<windMPH>\d+) mph, )?'
            r'(?:wind chill (?P<windChill>\-?\d+))?'
        )
        m = re.match(regex, td1.text())
        d = m.groupdict()

        # cast values to int
        for k in d:
            try:
                d[k] = int(d[k])
            except TypeError:
                pass

        # one-off fixes
        d['windChill'] = (d['windChill'] if pd.notnull(d['windChill'])
                          else d['temp'])
        d['windMPH'] = d['windMPH'] if pd.notnull(d['windMPH']) else 0
        return d

    @sportsref.decorators.memoized
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        doc = self.getDoc()
        table = doc('table#pbp_data')
        pbp = sportsref.utils.parseTable(table)
        # make the following features conveniently available on each row
        pbp['bsID'] = self.bsID
        pbp['home'] = self.home()
        pbp['away'] = self.away()
        pbp['season'] = self.season()
        pbp['week'] = self.week()
        feats = sportsref.nfl.pbp.expandDetails(pbp)

        # add team and opp columns by iterating through rows
        df = sportsref.nfl.pbp.addTeamColumns(feats)
        # add WPA column (requires diff, can't be done row-wise)
        df['home_wpa'] = df.home_wp.diff()
        # lag score columns, fill in 0-0 to start
        for col in ('home_wp', 'pbp_score_hm', 'pbp_score_aw'):
            if col in df.columns:
                df[col] = df[col].shift(1)
        df.ix[0, ['pbp_score_hm', 'pbp_score_aw']] = 0
        # fill in WP NaN's
        df.home_wp.fillna(method='ffill', inplace=True)
        # fix first play border after diffing/shifting for WP and WPA
        firstPlaysOfGame = df[df.secsElapsed == 0].index
        line = self.line()
        for i in firstPlaysOfGame:
            initwp = sportsref.nfl.winProb.initialWinProb(line)
            df.ix[i, 'home_wp'] = initwp
            df.ix[i, 'home_wpa'] = df.ix[i+1, 'home_wp'] - initwp
        # fix last play border after diffing/shifting for WP and WPA
        lastPlayIdx = df.iloc[-1].name
        lastPlayWP = df.ix[lastPlayIdx, 'home_wp']
        # if a tie, final WP is 50%; otherwise, determined by winner
        winner = self.winner()
        finalWP = 50. if pd.isnull(winner) else (winner == self.home()) * 100.
        df.ix[lastPlayIdx, 'home_wpa'] = finalWP - lastPlayWP
        # fix WPA for timeouts and plays after timeouts
        timeouts = df[df.isTimeout].index
        for to in timeouts:
            df.ix[to, 'home_wpa'] = 0.
            if to + 2 in df.index:
                wpa = df.ix[to+2, 'home_wp'] - df.ix[to+1, 'home_wp']
            else:
                wpa = finalWP - df.ix[to+1, 'home_wp']
            df.ix[to+1, 'home_wpa'] = wpa
        # add team-related features to DataFrame
        df = df.apply(sportsref.nfl.pbp.addTeamFeatures, axis=1)
        # fill distToGoal NaN's
        df['distToGoal'] = np.where(df.isKickoff, 65, df.distToGoal)
        df.distToGoal.fillna(method='bfill', inplace=True)
        df.distToGoal.fillna(method='ffill', inplace=True) # for last play

        return df

    @sportsref.decorators.memoized
    def refInfo(self):
        """Gets a dictionary of ref positions and the ref IDs of the refs for
        that game.
        :returns: A dictionary of ref positions and IDs.

        """
        doc = self.getDoc()
        refDict = {}
        refTable = doc('table#ref_info')
        for tr in refTable('tr[class=""]').items():
            td0, td1 = tr('td').items()
            key = td0.text().lower()
            key = re.sub(r'\W', '_', key)
            val = sportsref.utils.flattenLinks(td1)
            refDict[key] = val
        return refDict

    @sportsref.decorators.memoized
    def playerStats(self):
        """Gets the stats for offense, defense, returning, and kicking of
        individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        tableIDs = ('skill_stats', 'def_stats', 'st_stats', 'kick_stats')
        dfs = []
        for tID in tableIDs:
            table = doc('#{}'.format(tID))
            dfs.append(sportsref.utils.parseTable(table))
        df = pd.concat(dfs, ignore_index=True)
        df = df.reset_index(drop=True)
        df['team'] = df['team'].str.lower()
        return df
