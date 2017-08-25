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

    def __init__(self, boxscore_id):
        self.boxscore_id = boxscore_id

    def __eq__(self, other):
        return self.boxscore_id == other.boxscore_id

    def __hash__(self):
        return hash(self.boxscore_id)

    def __repr__(self):
        return 'BoxScore({})'.format(self.boxscore_id)

    @sportsref.decorators.memoize
    def get_main_doc(self):
        url = ('{}/boxscores/{}.html'
               .format(sportsref.nba.BASE_URL, self.boxscore_id))
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def get_subpage_doc(self, page):
        url = (sportsref.nba.BASE_URL +
               '/boxscores/{}/{}.html'.format(page, self.boxscore_id))
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

        return pd.DataFrame(data, columns=columns, dtype='float')

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

        def time_to_mp(t):
            if not t or t.find(':') == -1:
                return 0.
            else:
                mins, secs = map(int, t.split(':'))
                return mins + secs / 60.

        # get data
        doc = self.get_main_doc()
        tms = self.away(), self.home()
        tm_ids = ['box_{}_basic'.format(tm) for tm in tms]
        tables = [doc('table#{}'.format(tm_id).lower()) for tm_id in tm_ids]
        dfs = [sportsref.utils.parse_table(table) for table in tables]

        # clean data and add features
        for i, (tm, df) in enumerate(zip(tms, dfs)):
            if 'mp' in df.columns:
                got_time = df['mp'].str.find(':')
                stat_cols = [c for c, t in df.dtypes.iteritems()
                             if t != object]
                df.ix[got_time == -1, stat_cols] = 0
                df.ix[:, 'mp'] = df.mp.map(time_to_mp)
            df.ix[:, 'team'] = tm
            df.ix[:, 'is_home'] = i == 1
            df.ix[:, 'is_starter'] = [i < 5 for i in range(df.shape[0])]
            df.drop_duplicates(subset='player_id', keep='first', inplace=True)

        return pd.concat(dfs)

    @sportsref.decorators.memoize
    def advanced_stats(self):
        """Returns a DataFrame of advanced player stats from the game."""
        # TODO: include a "is_starter" column
        pass

    @sportsref.decorators.memoize
    def pbp(self, dense_lineups=False, sparse_lineups=False):
        """Returns a dataframe of the play-by-play data from the game.

        :param dense_lineups: If True, adds 10 columns containing the names of
            the players on the court. Defaults to False.
        :param sparse_lineups: If True, adds binary columns denoting whether a
            given player is in the game at the time of a pass. Defaults to
            False.
        :returns: pandas DataFrame of play-by-play. Similar to GPF.
        """
        try:
            doc = self.get_subpage_doc('pbp')
        except:
            raise ValueError(
                'No PBP data found for boxscore "{}"'.format(self.boxscore_id)
            )
        table = doc('table#pbp')
        trs = [
            tr for tr in table('tr').items()
            if (not tr.attr['class'] or  # regular data rows
                tr.attr['id'] and tr.attr['id'].startswith('q'))  # qtr bounds
        ]
        rows = [tr.children('td') for tr in trs]
        n_rows = len(trs)
        data = []
        cur_qtr = 0
        bsid = self.boxscore_id

        for i in range(n_rows):
            tr = trs[i]
            row = rows[i]
            p = {}

            # increment cur_qtr when we hit a new quarter
            if tr.attr['id'] and tr.attr['id'].startswith('q'):
                assert int(tr.attr['id'][1:]) == cur_qtr + 1
                cur_qtr += 1
                continue

            # add time of play to entry
            t_str = row.eq(0).text()
            t_regex = r'(\d+):(\d+)\.(\d+)'
            mins, secs, tenths = map(int, re.match(t_regex, t_str).groups())
            endQ = (12 * 60 * min(cur_qtr, 4) +
                    5 * 60 * (cur_qtr - 4 if cur_qtr > 4 else 0))
            secsElapsed = endQ - (60 * mins + secs + 0.1 * tenths)
            p['secs_elapsed'] = secsElapsed
            p['clock_time'] = t_str
            p['quarter'] = cur_qtr

            # handle single play description
            # ex: beginning/end of quarter, jump ball
            if row.length == 2:
                desc = row.eq(1)
                # handle jump balls
                if desc.text().lower().startswith('jump ball: '):
                    p['is_jump_ball'] = True
                    jb_str = sportsref.utils.flatten_links(desc)
                    p.update(
                        sportsref.nba.pbp.parse_play(bsid, jb_str, None)
                    )
                # ignore rows marking beginning/end of quarters
                elif (
                    desc.text().lower().startswith('start of ') or
                    desc.text().lower().startswith('end of ')
                ):
                    continue
                # if another case, log and continue
                else:
                    if not desc.text().lower().startswith('end of '):
                        print(
                            '{}, Q{}, {} other case: {}'
                            .format(self.boxscore_id, cur_qtr,
                                    t_str, desc.text())
                        )
                    continue

            # handle team play description
            # ex: shot, turnover, rebound, foul, sub, etc.
            elif row.length == 6:
                aw_desc, hm_desc = row.eq(1), row.eq(5)
                is_hm_play = bool(hm_desc.text())
                desc = hm_desc if is_hm_play else aw_desc
                desc = sportsref.utils.flatten_links(desc)
                # parse the play
                new_p = sportsref.nba.pbp.parse_play(bsid, desc, is_hm_play)
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
                    print("can't parse: {}, boxscore: {}"
                          .format(desc, self.boxscore_id))
                    # import pdb; pdb.set_trace()
                p.update(new_p)

            # otherwise, I don't know what this was
            else:
                raise Exception(("don't know how to handle row of length {}"
                                 .format(row.length)))

            data.append(p)

        # convert to DataFrame and clean columns
        df = pd.DataFrame.from_records(data)
        df = sportsref.nba.pbp.clean_features(df)

        # add columns for home team, away team, boxscore_id, date
        away, home = self.away(), self.home()
        df['home'] = home
        df['away'] = away
        df['boxscore_id'] = self.boxscore_id
        df['season'] = self.season()
        date = self.date()
        df['year'] = date.year
        df['month'] = date.month
        df['day'] = date.day

        # get rid of 'rebounds' after FTM, non-final FTA, or tech FTA
        df.reset_index(drop=True, inplace=True)
        no_reb_mask = (
            (df.fta_num < df.tot_fta) | df.is_ftm |
            df.get('is_tech_fta', False)
        )
        drop_mask = (
            df.is_reb & no_reb_mask.shift(1).fillna(False)
        ).nonzero()[0]
        df.drop(drop_mask, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        # track possession number for each possession
        new_poss = (df.team == df.home).diff().fillna(False)
        # def rebound considered part of the new possession
        df['poss_num'] = np.cumsum(new_poss) + df.is_dreb
        # create poss_num with rebs -> new possessions for granular groupbys
        poss_num_reb = np.cumsum(new_poss | df.is_reb)

        # make sure plays with the same clock time are in the right order
        sort_cols = [col for col in
                     ['is_reb', 'is_fga', 'is_pf', 'is_tech_foul',
                      'is_ejection', 'is_tech_fta', 'is_timeout', 'is_pf_fta',
                      'is_sub']
                     if col in df.columns]
        for label, group in df.groupby([df.secs_elapsed, poss_num_reb]):
            if len(group) > 1:
                df.ix[group.index, :] = group.sort_values(
                    sort_cols, ascending=False
                ).values

        # makes sure team and poss_num are correct for subs after rearranging
        # some possessions above
        df.ix[df['is_sub'], ['team', 'opp', 'poss_num']] = np.nan
        df.team.fillna(method='bfill', inplace=True)
        df.opp.fillna(method='bfill', inplace=True)
        df.poss_num.fillna(method='bfill', inplace=True)
        # make sure 'team' is the team shooting tech FTs
        # (impt for keeping track of the score)
        if 'is_tech_fta' in df.columns:
            tech_fta = df['is_tech_fta']
            df.ix[tech_fta, 'team'] = df.ix[tech_fta, 'ft_team']
            df.ix[tech_fta, 'opp'] = np.where(
                df.ix[tech_fta, 'team'] == home, away, home
            )
        # redefine poss_num_reb
        new_poss = (df.team == df.home).diff().fillna(False)
        poss_num_reb = np.cumsum(new_poss | df.is_reb)

        # get rid of redundant subs
        for (se, tm, pnum), group in df[df.is_sub].groupby(
            [df.secs_elapsed, df.sub_team, poss_num_reb]
        ):
            if len(group) > 1:
                sub_in = set()
                sub_out = set()
                # first, figure out who's in and who's out after subs
                for i, row in group.iterrows():
                    if row['sub_in'] in sub_out:
                        sub_out.remove(row['sub_in'])
                    else:
                        sub_in.add(row['sub_in'])
                    if row['sub_out'] in sub_in:
                        sub_in.remove(row['sub_out'])
                    else:
                        sub_out.add(row['sub_out'])
                assert len(sub_in) == len(sub_out)
                # second, add those subs
                n_subs = len(sub_in)
                for idx, p_in, p_out in zip(
                    group.index[:n_subs], sub_in, sub_out
                ):
                    assert df.ix[idx, 'is_sub']
                    df.ix[idx, 'sub_in'] = p_in
                    df.ix[idx, 'sub_out'] = p_out
                    df.ix[idx, 'sub_team'] = tm
                    df.ix[idx, 'detail'] = (
                        '{} enters the game for {}'.format(p_in, p_out)
                    )
                # third, if applicable, remove old sub entries when there are
                # redundant subs
                n_extra = len(group) - len(sub_in)
                if n_extra:
                    extra_idxs = group.index[-n_extra:]
                    df.drop(extra_idxs, axis=0, inplace=True)

        df.reset_index(drop=True, inplace=True)

        # add column for pts and score
        df['pts'] = (df['is_ftm'] + 2 * df['is_fgm'] +
                     (df['is_fgm'] & df['is_three']))
        df['hm_pts'] = np.where(df.team == df.home, df.pts, 0)
        df['aw_pts'] = np.where(df.team == df.away, df.pts, 0)
        df['hm_score'] = np.cumsum(df['hm_pts'])
        df['aw_score'] = np.cumsum(df['aw_pts'])

        # get lineup data
        if dense_lineups:
            df = pd.concat(
                (df, sportsref.nba.pbp.get_dense_lineups(df)), axis=1
            )
        if sparse_lineups:
            df = pd.concat(
                (df, sportsref.nba.pbp.get_sparse_lineups(df)), axis=1
            )

        # TODO: add shot clock as a feature

        return df
