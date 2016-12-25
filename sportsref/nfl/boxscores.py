import re
import datetime

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq
import six

import sportsref

__all__ = [
    'BoxScore',
]


class BoxScore(six.with_metaclass(sportsref.decorators.Cached, object)):

    def __init__(self, boxscore_id):
        self.boxscore_id = boxscore_id

    def __eq__(self, other):
        return self.boxscore_id == other.boxscore_id

    def __hash__(self):
        return hash(self.boxscore_id)

    def __repr__(self):
        return 'BoxScore({})'.format(self.boxscore_id)

    def __str__(self):
        return '{} Week {}: {} @ {}'.format(
            self.season(), self.week(), self.away(), self.home()
        )

    def __reduce__(self):
        return BoxScore, (self.boxscore_id,)

    @sportsref.decorators.memoize
    def get_doc(self):
        url = (sportsref.nfl.BASE_URL +
               '/boxscores/{}.htm'.format(self.boxscore_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.boxscore_id)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoize
    def weekday(self):
        """Returns the day of the week on which the game occurred.
        :returns: String representation of the day of the week for the game.

        """
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoize
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        relURL = table('tr').eq(1)('a').eq(2).attr['href']
        home = sportsref.utils.rel_url_to_id(relURL)
        return home

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        relURL = table('tr').eq(2)('a').eq(2).attr['href']
        away = sportsref.utils.rel_url_to_id(relURL)
        return away

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        home_score = table('tr').eq(1)('td')[-1].text_content()
        return int(home_score)

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        doc = self.get_doc()
        table = doc('table.linescore')
        away_score = table('tr').eq(2)('td')[-1].text_content()
        return int(away_score)

    @sportsref.decorators.memoize
    def winner(self):
        """Returns the team ID of the winning team. Returns NaN if a tie."""
        hmScore = self.home_score()
        awScore = self.away_score()
        if hmScore > awScore:
            return self.home()
        elif hmScore < awScore:
            return self.away()
        else:
            return np.nan

    @sportsref.decorators.memoize
    def week(self):
        """Returns the week in which this game took place. 18 is WC round, 19
        is Div round, 20 is CC round, 21 is SB.
        :returns: Integer from 1 to 21.
        """
        doc = self.get_doc()
        rawTxt = doc('div#page_content table').eq(0)('tr td').eq(0).text()
        match = re.search(r'Week (\d+)', rawTxt)
        if match:
            return int(match.group(1))
        else:
            return 21  # super bowl is week 21

    @sportsref.decorators.memoize
    def season(self):
        """
        Returns the year ID of the season in which this game took place.
        Useful for week 17 January games.

        :returns: An int representing the year of the season.
        """
        doc = self.get_doc()
        rawTxt = doc('div#page_content table').eq(0)('tr td').eq(0).text()
        match = re.search(r'Week \d+ (\d{4})', rawTxt)
        if match:
            return int(match.group(1))
        else:
            # else, it's the super bowl; super bowl happens in calendar year
            # after the season's year
            return self.date().year - 1

    @sportsref.decorators.memoize
    def starters(self):
        """Returns a DataFrame where each row is an entry in the starters table
        from PFR.

        The columns are:
        * player_id - the PFR player ID for the player (note that this column
        is not necessarily all unique; that is, one player can be a starter in
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
        doc = self.get_doc()
        a = doc('table#vis_starters')
        h = doc('table#home_starters')
        data = []
        for h, table in enumerate((a, h)):
            team = self.home() if h else self.away()
            for i, row in enumerate(table('tbody tr').items()):
                datum = {}
                datum['player_id'] = sportsref.utils.rel_url_to_id(
                    row('a')[0].attrib['href']
                )
                datum['playerName'] = row('th').text()
                datum['position'] = row('td').text()
                datum['team'] = team
                datum['home'] = (h == 1)
                datum['offense'] = (i <= 10)
                data.append(datum)
        return pd.DataFrame(data)

    @sportsref.decorators.memoize
    def line(self):
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        line_text = giTable.get('vegas_line', None)
        if line_text is None:
            return np.nan
        m = re.match(r'(.+?) ([\-\.\d]+)$', line_text)
        if m:
            favorite, line = m.groups()
            line = float(line)
            # give in terms of the home team
            year = self.season()
            if favorite != sportsref.nfl.teams.team_names(year)[self.home()]:
                line = -line
        else:
            line = 0
        return line

    @sportsref.decorators.memoize
    def surface(self):
        """The playing surface on which the game was played.

        :returns: string representing the type of surface. Returns np.nan if
        not avaiable.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        return giTable.get('surface', np.nan)

    @sportsref.decorators.memoize
    def over_under(self):
        """
        Returns the over/under for the game as a float, or np.nan if not
        available.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        if 'over_under' in giTable:
            ou = giTable['over_under']
            return float(ou.split()[0])
        else:
            return np.nan

    @sportsref.decorators.memoize
    def coin_toss(self):
        """Gets information relating to the opening coin toss.

        Keys are:
        * wonToss - contains the ID of the team that won the toss
        * deferred - bool whether the team that won the toss deferred it

        :returns: Dictionary of coin toss-related info.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
        if 'Won Toss' in giTable:
            # TODO: finish coinToss function
            pass
        else:
            return np.nan

    @sportsref.decorators.memoize
    def weather(self):
        """Returns a dictionary of weather-related info.

        Keys of the returned dict:
        * temp
        * windChill
        * relHumidity
        * windMPH

        :returns: Dict of weather data.
        """
        doc = self.get_doc()
        table = doc('table#game_info')
        giTable = sportsref.utils.parse_info_table(table)
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

    @sportsref.decorators.memoize
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        doc = self.get_doc()
        table = doc('table#pbp')
        df = sportsref.utils.parse_table(table)
        # make the following features conveniently available on each row
        df['boxscore_id'] = self.boxscore_id
        df['home'] = self.home()
        df['away'] = self.away()
        df['season'] = self.season()
        df['week'] = self.week()
        feats = sportsref.nfl.pbp.expand_details(df)

        # add team and opp columns by iterating through rows
        df = sportsref.nfl.pbp.add_team_columns(feats)
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
            df.ix[i, 'home_wpa'] = df.ix[i + 1, 'home_wp'] - initwp
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
                wpa = df.ix[to + 2, 'home_wp'] - df.ix[to + 1, 'home_wp']
            else:
                wpa = finalWP - df.ix[to + 1, 'home_wp']
            df.ix[to + 1, 'home_wpa'] = wpa
        # add team-related features to DataFrame
        df = df.apply(sportsref.nfl.pbp.add_team_features, axis=1)
        # fill distToGoal NaN's
        df['distToGoal'] = np.where(df.isKickoff, 65, df.distToGoal)
        df.distToGoal.fillna(method='bfill', inplace=True)
        df.distToGoal.fillna(method='ffill', inplace=True)  # for last play

        return df

    @sportsref.decorators.memoize
    def ref_info(self):
        """Gets a dictionary of ref positions and the ref IDs of the refs for
        that game.

        :returns: A dictionary of ref positions and IDs.
        """
        doc = self.get_doc()
        table = doc('table#officials')
        return sportsref.utils.parse_info_table(table)

    @sportsref.decorators.memoize
    def player_stats(self):
        """Gets the stats for offense, defense, returning, and kicking of
        individual players in the game.
        :returns: A DataFrame containing individual player stats.
        """
        doc = self.get_doc()
        tableIDs = ('player_offense', 'player_defense', 'returns', 'kicking')
        dfs = []
        for tID in tableIDs:
            table = doc('#{}'.format(tID))
            dfs.append(sportsref.utils.parse_table(table))
        df = pd.concat(dfs, ignore_index=True)
        df = df.reset_index(drop=True)
        df['team'] = df['team'].str.lower()
        return df
