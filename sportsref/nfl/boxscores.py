import re
import datetime

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'BoxScore',
]

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
        url = sportsref.nfl.BASE_URL + '/boxscores/{}.htm'.format(self.bsID)
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
        table = doc('table.linescore')
        relURL = table('tr').eq(2)('a').eq(2).attr['href']
        home = sportsref.utils.relURLToID(relURL)
        return home

    @sportsref.decorators.memoized
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.getDoc()
        table = doc('table.linescore')
        relURL = table('tr').eq(1)('a').eq(2).attr['href']
        away = sportsref.utils.relURLToID(relURL)
        return away

    @sportsref.decorators.memoized
    def homeScore(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        doc = self.getDoc()
        table = doc('table.linescore')
        homeScore = table('tr').eq(2)('td')[-1].text_content()
        return int(homeScore)

    @sportsref.decorators.memoized
    def awayScore(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        doc = self.getDoc()
        table = doc('table.linescore')
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
        rawTxt = doc('div#div_other_scores a').eq(0).attr['href']
        match = re.search(r'week_(\d+)', rawTxt)
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
        season = int(self.bsID[0:4])
        if int(self.bsID[4:6]) <= 2: season -= 1
        return season

    @sportsref.decorators.memoized
    def starters(self):
        """Returns a DataFrame where each row is an entry in the starters table
        from PFR.
        
        The columns are:
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
        a = doc('table#vis_starters')
        h = doc('table#home_starters')
        data = []
        for h, table in enumerate((a, h)):
            team = self.home() if h else self.away()
            for i, row in enumerate(table('tbody tr').items()):
                datum = {}
                try:
                    datum['playerID'] = sportsref.utils.relURLToID(
                        row('a')[0].attrib['href']
                    )
                except IndexError:
                    pass
                datum['playerName'] = row('th').text()
                datum['position'] = row('td').text()
                datum['team'] = team
                datum['home'] = (h == 1)
                datum['offense'] = (i <= 10)
                data.append(datum)
        df = pd.DataFrame(data)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        return df.dropna()

    @sportsref.decorators.memoized
    def line(self):
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        line_text = giTable.get('vegas_line', None)
        if line_text is None:
            return np.nan
        m = re.match(r'(.+?) ([\-\.\d]+)$', line_text)
        if m:
            favorite, line = m.groups()
            line = float(line)
            # give in terms of the home team
            year = self.season()
            if favorite != sportsref.nfl.teams.teamNames(year)[self.home()]:
                line = -line
        else:
            line = 0
        return line

    @sportsref.decorators.memoized
    def surface(self):
        """The playing surface on which the game was played.

        :returns: string representing the type of surface. Returns np.nan if
        not avaiable.
        """
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        return giTable.get('surface', np.nan)

    @sportsref.decorators.memoized
    def roof(self):
        """The playing surface on which the game was played.

        :returns: string representing the roof of stadium. Returns np.nan if
        not avaiable.
        """
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        return giTable.get('roof', np.nan)

    @sportsref.decorators.memoized
    def over_under(self):
        """
        Returns the over/under for the game as a float, or np.nan if not
        available.
        """
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        if 'over_under' in giTable:
            ou = giTable['over_under']
            return float(ou.split()[0])
        else:
            return np.nan

    @sportsref.decorators.memoized
    def coinToss(self):
        """Gets information relating to the opening coin toss.

        Keys are:
        * wonToss - contains the ID of the team that won the toss
        * deferred - bool whether the team that won the toss deferred it

        :returns: Dictionary of coin toss-related info.
        """
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        if 'Won Toss' in giTable:
            # TODO: finish coinToss function
            pass
        else:
            return np.nan

    @sportsref.decorators.memoized
    def weather(self):
        """Returns a dictionary of weather-related info.

        Keys of the returned dict:
        * temp
        * windChill
        * relHumidity
        * windMPH

        :returns: Dict of weather data.
        """
        doc = self.getDoc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parseInfoTable(table)
        if 'weather' in giTable:
            regex = (
                r'(?:(?P<temp>\-?\d+) degrees )?'
                r'(?:relative humidity (?P<relHumidity>\d+)%, )?'
                r'(?:wind (?P<windMPH>\d+) mph, )?'
                r'(?:wind chill (?P<windChill>\-?\d+))?'
            )
            m = re.match(regex, giTable['weather'])
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
        else:
            # no weather found, because it's a dome
            # TODO: what's relative humidity in a dome?
            return {
                'temp': 70, 'windChill': 70, 'relHumidity': None, 'windMPH': 0
            }

    @sportsref.decorators.memoized
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        doc = self.getDoc()
        table = doc('table#pbp')
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
        table = doc('table#officials')
        return sportsref.utils.parseInfoTable(table)

    @sportsref.decorators.memoized
    def playerStats(self):
        """Gets the stats for offense, defense, returning, and kicking of
        individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        tableIDs = ('player_offense', 'player_defense', 'returns', 'kicking')
        dfs = []
        for tID in tableIDs:
            table = doc('#{}'.format(tID))
            dfs.append(sportsref.utils.parseTable(table))
        df = pd.concat(dfs, ignore_index=True)
        df = df.reset_index(drop=True)
        df['team'] = df['team'].str.lower()
        return df

    @sportsref.decorators.memoized
    def statsTeam(self):
        """Gets the summarized stats for each team.
        :returns: A DataFrame containing team stats.
        """
        doc = self.getDoc()
        table = doc('#team_stats')
        df = sportsref.utils.parseTable(table)
        df = df.transpose()
        df.columns = df.iloc[0]
        df.columns.name = None
        df.drop(['stat'], inplace=True)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        df['team'] = [self.away(), self.home()]
        df['home'] = [False, True]
        # create features from lines with multiple stats in 1 row
        df = pd.concat(
            [df,
             df['Rush-Yds-TDs'].str.extract(
                    r'(?:(?P<rushAtt>\d+))?'
                    r'(?:-(?P<rushYds>\d+))?'
                    r'(?:-(?P<rushTds>\d+))?',
                    expand=False),
             df['Cmp-Att-Yd-TD-INT'].str.extract(
                    r'(?:(?P<passCmp>\d+))?'
                    r'(?:-(?P<passAtt>\d+))?'
                    r'(?:-(?P<passYds>\d+))?'
                    r'(?:-(?P<passTds>\d+))?'
                    r'(?:-(?P<passInt>\d+))?',
                    expand=False),
             df['Sacked-Yards'].str.extract(
                    r'(?:(?P<sacks>\d+))?'
                    r'(?:-(?P<sacksYds>\d+))?',
                    expand=False),
             df['Fumbles-Lost'].str.extract(
                    r'(?:(?P<fumbles>\d+))?'
                    r'(?:-(?P<fumblesLost>\d+))?',
                    expand=False),
             df['Sacked-Yards'].str.extract(
                    r'(?:(?P<pentalties>\d+))?'
                    r'(?:-(?P<pentaltiesYds>\d+))?',
                    expand=False),
             df['Third Down Conv.'].str.extract(
                    r'(?:(?P<thirdDownAtt>\d+))?'
                    r'(?:-(?P<thirdDownConv>\d+))?',
                    expand=False),
             df['Fourth Down Conv.'].str.extract(
                    r'(?:(?P<fourthDownAtt>\d+))?'
                    r'(?:-(?P<fourthDownConv>\d+))?',
                    expand=False)
             ], axis=1
        )
        # multi stat features to drop
        dropCols = [
            'Rush-Yds-TDs',
            'Cmp-Att-Yd-TD-INT',
            'Sacked-Yards',
            'Fumbles-Lost',
            'Penalties-Yards',
            'Sacked-Yards',
            'Third Down Conv.',
            'Fourth Down Conv.'
        ]
        # features to rename
        newCols = {
            'First Downs':'firstDowns',
            'Net Pass Yards':'netPassYards',
            'Total Yards':'totalYards',
            'Turnovers':'turnovers',
            'Time of Possession':'timeOfPossession'
        }
        df.drop(dropCols, axis=1, inplace=True)
        df.rename(columns = newCols, inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    @sportsref.decorators.memoized
    def statsOffense(self):
        """Gets the stats for offense of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#player_offense')
        df = sportsref.utils.parseTable(table)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        df['team'] = df['team'].str.lower()
        return df

    @sportsref.decorators.memoized
    def statsDefense(self):
        """Gets the stats for defense of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#player_defense')
        df = sportsref.utils.parseTable(table)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        # bsID 201202050nwe with no defense table...
        try:
            df['team'] = df['team'].str.lower()
        except:
            pass
        return df

    @sportsref.decorators.memoized
    def statsReturns(self):
        """Gets the stats for returns of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#returns')
        df = sportsref.utils.parseTable(table)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        # bsID with no returns table...
        try:
            df['team'] = df['team'].str.lower()
        except:
            pass
        return df

    @sportsref.decorators.memoized
    def statsKicking(self):
        """Gets the stats for kicking of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#kicking')
        df = sportsref.utils.parseTable(table)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        df['team'] = df['team'].str.lower()
        return df

    @sportsref.decorators.memoized
    def passDirections(self):
        """Gets the stats for kicking of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#targets_directions')
        df = sportsref.utils.parseTable(table)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        df['team'] = df['team'].str.lower()
        # sum short and deep stats
        df['rec_targets_s'] = df[['rec_targets_sl',
                                  'rec_targets_sm',
                                  'rec_targets_sr'
                                 ]].sum(axis=1)
        df['rec_targets_d'] = df[['rec_targets_dl',
                                  'rec_targets_dm',
                                  'rec_targets_dr'
                                ]].sum(axis=1)
        df['rec_catches_s'] = df[['rec_catches_sl',
                                  'rec_catches_sm',
                                  'rec_catches_sr'
                                ]].sum(axis=1)
        df['rec_catches_d'] = df[['rec_catches_dl',
                                  'rec_catches_dm',
                                  'rec_catches_dr'
                                ]].sum(axis=1)
        return df

    @sportsref.decorators.memoized
    def snapCounts(self):
        """Gets the snap counts of individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.getDoc()
        table = doc('#home_snap_counts')
        dfH = sportsref.utils.parseTable(table)
        dfH['team'] = self.home()
        table = doc('#vis_snap_counts')
        dfV = sportsref.utils.parseTable(table)
        dfV['team'] = self.away()
        df = pd.concat([dfH, dfV], ignore_index=True)
        df['bsID'] = self.bsID
        df['season'] = self.season()
        df['week'] = self.week()
        df = df.reset_index(drop=True)      
        return df

    @sportsref.decorators.memoized
    def gameInfo(self):
        """Returns a one row dataframe of game info.

        :returns: DataFrame of game info.
        """
        doc = self.getDoc()
        d = {
            'season':self.season(),
            'week':self.week(),
            'bsID':self.bsID,
            'date':self.date(),
            'weekday':self.weekday(),
            'home':self.home(),
            'away':self.away(),
            'homeScore':self.homeScore(),
            'awayScore':self.awayScore(),
            'winner':self.winner(),
            'line':self.line(),
            'overUnder':self.over_under(),
            'roof':self.roof()
        }
        d.update(self.weather())
        rawTxt = doc('div.scorebox_meta div').eq(1).text()
        regex = (r"(?:Start Time : (?P<startTime>\d+:\d+ ?[apAP][mM]))?")
        d.update(re.match(regex, rawTxt).groupdict())
        df = pd.DataFrame(d, index=[0])
        return df
