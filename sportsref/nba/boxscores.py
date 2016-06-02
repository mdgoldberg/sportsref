import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

@sportsref.decorators.memoized
class BoxScore:

    def __init__(self, bsID):
        self.bsID = bsID

    def __eq__(self, other):
        return self.bsID == other.bsID

    def __hash__(self):
        return hash(self.bsID)

    @sportsref.decorators.memoized
    def getMainDoc(self):
        url = urlparse.urljoin(
            sportsref.nba.BASE_URL, 'boxscores/{}.html'.format(self.bsID)
        )
        doc = pq(sportsref.utils.getHTML(url))
        return doc

    @sportsref.decorators.memoized
    def getPBPDoc(self):
        url = urlparse.urljoin(
            sportsref.nba.BASE_URL, 'boxscores/pbp/{}.html'.format(self.bsID)
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
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        hm_href = table('tr td:eq(1) span a:eq(0)').attr['href']
        return sportsref.utils.relURLToID(hm_href)

    @sportsref.decorators.memoized
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        aw_href = table('tr td:eq(0) span a:eq(0)').attr['href']
        return sportsref.utils.relURLToID(aw_href)

    @sportsref.decorators.memoized
    def homeScore(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        hm_txt = table('tr td:eq(1) span:eq(0)').text()
        hm_sc = int(re.match(r'.*?(\d+)$', hm_txt).group(1))
        return hm_sc

    @sportsref.decorators.memoized
    def awayScore(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        doc = self.getMainDoc()
        table = doc('div#page_content div > div > table:eq(1) table')
        aw_txt = table('tr td:eq(0) span:eq(0)').text()
        aw_sc = int(re.match(r'.*?(\d+)$', aw_txt).group(1))
        return aw_sc

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
    def season(self):
        """
        Returns the year ID of the season in which this game took place.

        :returns: An int representing the year of the season.
        """
        d = self.date()
        if d.month >= 9:
            return d.year + 1
        else:
            return d.year
    
    @sportsref.decorators.memoized
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        doc = self.getPBPDoc()
        table = doc('table.stats_table:last')
        rows = [tr.children('td') for tr in table('tr').items() if tr('td')]
        data = []
        year = self.season()
        cur_qtr = 1
        cur_aw_score = 0
        cur_hm_score = 0
        for row in rows:
            p = {}

            # add time of play to entry
            t_str = row.eq(0).text()
            t_regex = r'(\d+):(\d+)\.(\d+)'
            mins, secs, tenths = map(int, re.match(t_regex, t_str).groups())
            endQ = (12*60*min(cur_qtr, 4) +
                    5*60*(cur_qtr - 4 if cur_qtr > 4 else 0))
            secsElapsed = endQ - (60*mins + secs + 0.1*tenths)
            p['secsElapsed'] = secsElapsed

            # add scores to entry
            p['hmScore'] = cur_hm_score
            p['awScore'] = cur_aw_score
            p['quarter'] = cur_qtr

            # handle single play description
            # ex: beginning/end of quarter, jump ball
            if row.length == 2:
                desc = row.eq(1)
                if desc.text().startswith('End of '):
                    # handle end of quarter/OT
                    cur_qtr += 1
                    continue
                elif desc.text().startswith('Jump ball: '):
                    # handle jump ball
                    p['isJumpBall'] = True
                    jb_str = sportsref.utils.flattenLinks(desc)
                    n = None
                    p.update(sportsref.nba.pbp.parsePlay(jb_str, n, n, n, year))
                else:
                    # if another case, continue
                    if not desc.text().lower().startswith('start of '):
                        print 'other case:', desc.text()
                    continue

            # handle team play description
            # ex: shot, turnover, rebound, foul, sub, etc.
            elif row.length == 6:
                aw_desc, sc_desc, hm_desc = row.eq(1), row.eq(3), row.eq(5)
                is_hm_play = bool(hm_desc.text())
                desc = hm_desc if is_hm_play else aw_desc
                desc = sportsref.utils.flattenLinks(desc)
                # update scores
                scores = re.match(r'(\d+)\-(\d+)', sc_desc.text()).groups()
                cur_aw_score, cur_hm_score = map(int, scores)
                # get home and away
                hm, aw = self.home(), self.away()
                # handle the play
                new_p = sportsref.nba.pbp.parsePlay(desc, hm, aw, is_hm_play, year)
                if new_p == -1:
                    continue
                elif new_p.get('isError'):
                    print "can't parse: %s, boxscore: %s" % (desc, self.bsID)
                    # import pdb; pdb.set_trace()
                p.update(new_p)

            # otherwise, I don't know what this was
            else:
                raise Exception(("don't know how to handle row of length {}"
                       .format(row.length)))

            data.append(p)

        # convert to DataFrame
        df = pd.DataFrame.from_records(data)

        # add columns for home team, away team, and bsID
        df['home'] = self.home()
        df['away'] = self.away()
        df['bsID'] = self.bsID

        # TODO: track current lineup for each team
        # TODO: track possession number for each possession

        # TODO: add shot clock as a feature OR
        # make PBP a standard of one entry per second
        # (so we can deduce shot clock and use as feature)

        # clean columns
        df = sportsref.nba.pbp.cleanFeatures(df)

        # fill in NaN's in team, opp columns except for jump balls
        df.team.fillna(method='bfill', inplace=True)
        df.opp.fillna(method='bfill', inplace=True)
        df.team.fillna(method='ffill', inplace=True)
        df.opp.fillna(method='ffill', inplace=True)
        if 'isJumpBall' in df.columns:
            df.ix[df.isJumpBall, ['team', 'opp']] = np.nan

        return df
