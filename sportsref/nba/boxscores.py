import future
import future.utils

import datetime
import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref


class BoxScore(
    future.utils.with_metaclass(sportsref.decorators.Cached, object)
):

    def __init__(self, bs_id):
        self.bs_id = bs_id

    def __eq__(self, other):
        return self.bs_id == other.bs_id

    def __hash__(self):
        return hash(self.bs_id)

    def __repr__(self):
        return 'BoxScore({})'.format(self.bs_id)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        url = sportsref.nba.BASE_URL + '/boxscores/{}.html'.format(self.bs_id)
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def get_subpage_doc(self, page):
        url = (sportsref.nba.BASE_URL +
               '/boxscores/{}/{}.html'.format(page, self.bs_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.bs_id)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoize
    def weekday(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday']
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoize
    def linescore(self):
        """Returns the linescore for the game as a DataFrame."""
        doc = self.get_main_doc()
        table = doc('table#line_score')

        columns = [th.text() for th in table('tr.thead').items('th')]
        columns[0] = 'team_id'

        data = [
            [sportsref.utils.flatten_links(td) for td in tr('td').items()]
            for tr in table('tr.thead').next_all('tr').items()
        ]

        return pd.DataFrame(data, columns=columns)

    @sportsref.decorators.memoize
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        linescore = self.linescore()
        return linescore.ix[1, 'team_id']

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        linescore = self.linescore()
        return linescore.ix[0, 'team_id']

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        linescore = self.linescore()
        return linescore.ix[1, 'T']

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        linescore = self.linescore()
        return linescore.ix[0, 'T']

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

    @sportsref.decorators.memoize
    def basic_stats(self):
        """Returns a DataFrame of basic player stats from the game."""
        # TODO: include a "is_starter" column
        pass

    @sportsref.decorators.memoize
    def advanced_stats(self):
        """Returns a DataFrame of advanced player stats from the game."""
        # TODO: include a "is_starter" column
        pass

    @sportsref.decorators.memoize
    def pbp(self):
        """Returns a dataframe of the play-by-play data from the game.

        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        try:
            doc = self.get_subpage_doc('pbp')
        except ValueError:
            return pd.DataFrame()
        table = doc('table.stats_table:last')
        rows = [tr.children('td') for tr in table('tr').items() if tr('td')]
        data = []
        year = self.season()
        cur_qtr = 0
        cur_aw_score = 0
        cur_hm_score = 0
        for row in rows:
            p = {}

            # add time of play to entry
            t_str = row.eq(0).text()
            t_regex = r'(\d+):(\d+)\.(\d+)'
            mins, secs, tenths = map(int, re.match(t_regex, t_str).groups())
            endQ = (12 * 60 * min(cur_qtr, 4) +
                    5 * 60 * (cur_qtr - 4 if cur_qtr > 4 else 0))
            secsElapsed = endQ - (60 * mins + secs + 0.1 * tenths)
            p['secs_elapsed'] = secsElapsed

            # add scores to entry
            p['hm_score'] = cur_hm_score
            p['aw_score'] = cur_aw_score
            p['quarter'] = cur_qtr

            # handle single play description
            # ex: beginning/end of quarter, jump ball
            if row.length == 2:
                desc = row.eq(1)
                if desc.text().lower().startswith('start of '):
                    # handle start of quarter/OT
                    cur_qtr += 1
                    continue
                elif desc.text().lower().startswith('jump ball: '):
                    # handle jump ball
                    p['is_jump_ball'] = True
                    jb_str = sportsref.utils.flatten_links(desc)
                    n = None
                    p.update(
                        sportsref.nba.pbp.parse_play(jb_str, n, n, n, year)
                    )
                else:
                    # if another case, continue
                    if not desc.text().lower().startswith('end of '):
                        print 'other case:', desc.text()
                    continue

            # handle team play description
            # ex: shot, turnover, rebound, foul, sub, etc.
            elif row.length == 6:
                aw_desc, sc_desc, hm_desc = row.eq(1), row.eq(3), row.eq(5)
                is_hm_play = bool(hm_desc.text())
                desc = hm_desc if is_hm_play else aw_desc
                desc = sportsref.utils.flatten_links(desc)
                # update scores
                scores = re.match(r'(\d+)\-(\d+)', sc_desc.text()).groups()
                cur_aw_score, cur_hm_score = map(int, scores)
                # get home and away
                hm, aw = self.home(), self.away()
                # handle the play
                new_p = sportsref.nba.pbp.parse_play(
                    desc, hm, aw, is_hm_play, year
                )
                if not new_p:
                    continue
                elif isinstance(new_p, list):
                    # this happens when a row needs to be expanded to 2 rows;
                    # ex: double personal foul -> two PF rows

                    # first, update and append the first row
                    orig_p = dict(p)
                    p.update(new_p[0])
                    data.append(p)
                    # second, set up the second row to be appended below
                    p = orig_p
                    new_p = new_p[1]
                elif new_p.get('is_error'):
                    print "can't parse: %s, boxscore: %s" % (desc, self.bs_id)
                    # import pdb; pdb.set_trace()
                p.update(new_p)

            # otherwise, I don't know what this was
            else:
                raise Exception(("don't know how to handle row of length {}"
                                 .format(row.length)))

            data.append(p)

        # convert to DataFrame
        df = pd.DataFrame.from_records(data)

        # add columns for home team, away team, and bs_id
        df['home'] = self.home()
        df['away'] = self.away()
        df['bs_id'] = self.bs_id

        # TODO: track current lineup for each team

        # TODO: track possession number for each possession

        # TODO: add shot clock as a feature

        # clean columns
        df = sportsref.nba.pbp.clean_features(df)

        # fill in NaN's in team, opp columns except for jump balls
        df.team.fillna(method='bfill', inplace=True)
        df.opp.fillna(method='bfill', inplace=True)
        df.team.fillna(method='ffill', inplace=True)
        df.opp.fillna(method='ffill', inplace=True)
        if 'is_jump_ball' in df.columns:
            df.ix[df['is_jump_ball'], ['team', 'opp']] = np.nan

        return df
