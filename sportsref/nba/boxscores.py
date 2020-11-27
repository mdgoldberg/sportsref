import datetime
import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

CLOCK_REGEX = re.compile(r"(\d+):(\d+)\.(\d+)")


class BoxScore(object, metaclass=sportsref.decorators.Cached):
    def __init__(self, boxscore_id):
        self.boxscore_id = boxscore_id

    def __eq__(self, other):
        return self.boxscore_id == other.boxscore_id

    def __hash__(self):
        return hash(self.boxscore_id)

    def __repr__(self):
        return f"BoxScore({self.boxscore_id})"

    @sportsref.decorators.memoize
    def get_main_doc(self):
        url = f"{sportsref.nba.BASE_URL}/boxscores/{self.boxscore_id}.html"
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def get_subpage_doc(self, page):
        url = f"{sportsref.nba.BASE_URL}/boxscores/{page}/{self.boxscore_id}.html"
        doc = pq(sportsref.utils.get_html(url))
        return doc

    @sportsref.decorators.memoize
    def date(self):
        """Returns the date of the game. See Python datetime.date documentation
        for more.
        :returns: A datetime.date object with year, month, and day attributes.
        """
        match = re.match(r"(\d{4})(\d{2})(\d{2})", self.boxscore_id)
        year, month, day = list(map(int, match.groups()))
        return datetime.date(year=year, month=month, day=day)

    @sportsref.decorators.memoize
    def weekday(self):
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        date = self.date()
        wd = date.weekday()
        return days[wd]

    @sportsref.decorators.memoize
    def linescore(self):
        """Returns the linescore for the game as a DataFrame."""
        doc = self.get_main_doc()
        table = doc("table#line_score")
        df = sportsref.utils.parse_table(table)
        df.index = ["away", "home"]
        return df

    @sportsref.decorators.memoize
    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        linescore = self.linescore()
        return linescore.loc["home", "team_id"]

    @sportsref.decorators.memoize
    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        linescore = self.linescore()
        return linescore.loc["away", "team_id"]

    @sportsref.decorators.memoize
    def home_score(self):
        """Returns score of the home team.
        :returns: int of the home score.
        """
        linescore = self.linescore()
        return linescore.loc["home", "T"]

    @sportsref.decorators.memoize
    def away_score(self):
        """Returns score of the away team.
        :returns: int of the away score.
        """
        linescore = self.linescore()
        return linescore.loc["away", "T"]

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
            return None

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

    def _get_player_stats(self, table_id_fmt):
        """Returns a DataFrame of player stats from the game (either basic or
        advanced, depending on the argument.

        :param table_id_fmt: Format string for str.format with a placeholder
            for the team ID (e.g. 'box-{}-game-basic')
        :returns: DataFrame of player stats
        """

        # get data
        doc = self.get_main_doc()
        tms = self.away(), self.home()
        team_table_ids = [table_id_fmt.format(tm.upper()) for tm in tms]
        tables = [doc(f"table#{table_id}") for table_id in team_table_ids]
        dfs = [sportsref.utils.parse_table(table) for table in tables]

        # clean data and add features
        for i, (tm, df) in enumerate(zip(tms, dfs)):
            no_time = df["mp"] == 0
            stat_cols = [
                col for col, dtype in list(df.dtypes.items()) if dtype != "object"
            ]
            df.loc[no_time, stat_cols] = 0
            df["team_id"] = tm
            df["is_home"] = i == 1
            df["is_starter"] = [p < 5 for p in range(df.shape[0])]
            df.drop_duplicates(subset="player_id", keep="first", inplace=True)

        return pd.concat(dfs)

    @sportsref.decorators.memoize
    def basic_stats(self):
        """Returns a DataFrame of basic player stats from the game."""
        return self._get_player_stats("box-{}-game-basic")

    @sportsref.decorators.memoize
    def advanced_stats(self):
        """Returns a DataFrame of advanced player stats from the game."""
        return self._get_player_stats("box-{}-game-advanced")

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
            doc = self.get_subpage_doc("pbp")
        except Exception:
            raise ValueError(
                f"Error fetching PBP subpage for boxscore {self.boxscore_id}"
            )

        table = doc("table#pbp")
        trs = [
            tr
            for tr in list(table("tr").items())
            if (
                not tr.attr["class"]
                or (tr.attr["id"] and tr.attr["id"].startswith("q"))
            )
        ]
        rows = [tr.children("td") for tr in trs]
        n_rows = len(trs)
        data = []
        cur_qtr = 0

        for i in range(n_rows):
            tr = trs[i]
            row = rows[i]
            play = {}

            # increment cur_qtr when we hit a new quarter
            if tr.attr["id"] and tr.attr["id"].startswith("q"):
                assert int(tr.attr["id"][1:]) == cur_qtr + 1
                cur_qtr += 1
                continue

            # add time of play to entry
            clock_str = row.eq(0).text()
            mins, secs, tenths = list(
                map(int, re.match(CLOCK_REGEX, clock_str).groups())
            )
            secs_in_period = 12 * 60 * min(cur_qtr, 4) + 5 * 60 * (
                cur_qtr - 4 if cur_qtr > 4 else 0
            )
            secs_elapsed = secs_in_period - (60 * mins + secs + 0.1 * tenths)
            play["secs_elapsed"] = secs_elapsed
            play["clock_str"] = clock_str
            play["quarter"] = cur_qtr

            # handle single play description
            # ex: beginning/end of quarter, jump ball
            if row.length == 2:
                desc = row.eq(1)
                # handle jump balls
                if desc.text().lower().startswith("jump ball: "):
                    play["is_jump_ball"] = True
                    jump_ball_str = sportsref.utils.flatten_links(desc)
                    play.update(
                        sportsref.nba.pbp.parse_play(
                            self.boxscore_id, jump_ball_str, is_home=None
                        )
                    )
                # ignore rows marking beginning/end of quarters
                elif desc.text().lower().startswith(
                    "start of "
                ) or desc.text().lower().startswith("end of "):
                    continue
                # if another case, log and continue
                else:
                    if not desc.text().lower().startswith("end of "):
                        print(
                            f"{self.boxscore_id}, Q{cur_qtr}, {clock_str} other case: {desc.text()}"
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
                new_play = sportsref.nba.pbp.parse_play(
                    self.boxscore_id, desc, is_hm_play
                )
                if not new_play:
                    continue
                elif isinstance(new_play, list):
                    # this happens when a row needs to be expanded to 2 rows;
                    # ex: double personal foul -> two PF rows

                    # first, update and append the first row
                    orig_play = dict(play)
                    play.update(new_play[0])
                    data.append(play)
                    # second, set up the second row to be appended below
                    play = orig_play
                    new_play = new_play[1]
                elif new_play.get("is_error"):
                    print(f"can't parse: {desc}, boxscore: {self.boxscore_id}")
                    # import pdb; pdb.set_trace()
                play.update(new_play)

            # otherwise, I don't know what this was
            else:
                raise Exception(f"don't know how to handle row of length {row.length}")

            data.append(play)

        # convert to DataFrame and clean columns
        df = pd.DataFrame.from_records(data)
        df.sort_values("secs_elapsed", inplace=True, kind="mergesort")
        df = sportsref.nba.pbp.clean_features(df)

        # add columns for home team, away team, boxscore_id, date
        away, home = self.away(), self.home()
        df["home"] = home
        df["away"] = away
        df["boxscore_id"] = self.boxscore_id
        df["season"] = self.season()
        date = self.date()
        df["year"] = date.year
        df["month"] = date.month
        df["day"] = date.day

        def _clean_rebs(df):
            df.reset_index(drop=True, inplace=True)
            no_reb_after = (
                ((df.fta_num < df.tot_fta) | df.is_ftm | df.get("is_tech_fta", False))
                .shift(1)
                .fillna(False)
            )
            no_reb_before = ((df.fta_num == df.tot_fta)).shift(-1).fillna(False)
            se_end_qtr = df.loc[df.clock_str == "0:00.0", "secs_elapsed"].unique()
            no_reb_when = df.secs_elapsed.isin(se_end_qtr)
            drop_mask = (df.rebounder == "Team") & (
                no_reb_after | no_reb_before | no_reb_when
            )
            df.drop(df.loc[drop_mask].index, axis=0, inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df

        # get rid of 'rebounds' after FTM, non-final FTA, or tech FTA
        df = _clean_rebs(df)

        # track possession number for each possession
        # TODO: see 201604130PHO, secs_elapsed == 2756
        # things that end a poss:
        # FGM, dreb, TO, end of Q, made last FT, lost jump ball,
        # def goaltending, shot clock violation
        new_poss = (df.off_team == df.home).diff().fillna(False)
        # def rebound considered part of the new possession
        df["poss_id"] = np.cumsum(new_poss) + df.is_dreb
        # create poss_id with rebs -> new possessions for granular groupbys
        poss_id_reb = np.cumsum(new_poss | df.is_reb)

        # make sure plays with the same clock time are in the right order
        # TODO: make sort_cols depend on what cols are in the play?
        # or combine related plays, like and-1 shot and foul
        # issues come up with FGA after timeout in 201604130LAL
        # issues come up with PF between FGA and DREB in 201604120SAS
        sort_cols = [
            col
            for col in [
                "is_reb",
                "is_fga",
                "is_pf",
                "is_tech_foul",
                "is_ejection",
                "is_tech_fta",
                "is_timeout",
                "is_pf_fta",
                "fta_num",
                "is_viol",
                "is_to",
                "is_jump_ball",
                "is_sub",
            ]
            if col in df.columns
        ]
        asc_true = ["fta_num"]
        ascend = [(col in asc_true) for col in sort_cols]
        for label, group in df.groupby([df.secs_elapsed, poss_id_reb]):
            if len(group) > 1:
                df.loc[group.index, :] = group.sort_values(
                    sort_cols, ascending=ascend, kind="mergesort"
                ).values

        # 2nd pass: get rid of 'rebounds' after FTM, non-final FTA, etc.
        df = _clean_rebs(df)

        # makes sure off/def and poss_id are correct for subs after rearranging
        # some possessions above
        df.loc[df["is_sub"], ["off_team", "def_team", "poss_id"]] = np.nan
        df.off_team.fillna(method="bfill", inplace=True)
        df.def_team.fillna(method="bfill", inplace=True)
        df.poss_id.fillna(method="bfill", inplace=True)
        # make off_team and def_team NaN for jump balls
        if "is_jump_ball" in df.columns:
            df.loc[df["is_jump_ball"], ["off_team", "def_team"]] = np.nan

        # make sure 'off_team' is always the team shooting FTs, even on techs
        # (impt for keeping track of the score)
        if "is_tech_fta" in df.columns:
            tech_fta = df["is_tech_fta"]
            df.loc[tech_fta, "off_team"] = df.loc[tech_fta, "fta_team"]
            df.loc[tech_fta, "def_team"] = np.where(
                df.loc[tech_fta, "off_team"] == home, away, home
            )
        df.drop("fta_team", axis=1, inplace=True)
        # redefine poss_id_reb
        new_poss = (df.off_team == df.home).diff().fillna(False)
        poss_id_reb = np.cumsum(new_poss | df.is_reb)

        # get rid of redundant subs
        for (se, tm, pnum), group in df[df.is_sub].groupby(
            [df.secs_elapsed, df.sub_team, poss_id_reb]
        ):
            if len(group) > 1:
                sub_in = set()
                sub_out = set()
                # first, figure out who's in and who's out after subs
                for i, row in group.iterrows():
                    if row["sub_in"] in sub_out:
                        sub_out.remove(row["sub_in"])
                    else:
                        sub_in.add(row["sub_in"])
                    if row["sub_out"] in sub_in:
                        sub_in.remove(row["sub_out"])
                    else:
                        sub_out.add(row["sub_out"])
                assert len(sub_in) == len(sub_out)
                # second, add those subs
                n_subs = len(sub_in)
                for idx, p_in, p_out in zip(group.index[:n_subs], sub_in, sub_out):
                    assert df.loc[idx, "is_sub"]
                    df.loc[idx, "sub_in"] = p_in
                    df.loc[idx, "sub_out"] = p_out
                    df.loc[idx, "sub_team"] = tm
                    df.loc[idx, "detail"] = f"{p_in} enters the game for {p_out}"
                # third, if applicable, remove old sub entries when there are
                # redundant subs
                n_extra = len(group) - len(sub_in)
                if n_extra:
                    extra_idxs = group.index[-n_extra:]
                    df.drop(extra_idxs, axis=0, inplace=True)

        df.reset_index(drop=True, inplace=True)

        # add column for pts and score
        df["pts"] = df["is_ftm"] + 2 * df["is_fgm"] + (df["is_fgm"] & df["is_three"])
        df["hm_pts"] = np.where(df.off_team == df.home, df.pts, 0)
        df["aw_pts"] = np.where(df.off_team == df.away, df.pts, 0)
        df["hm_score"] = np.cumsum(df["hm_pts"])
        df["aw_score"] = np.cumsum(df["aw_pts"])

        # more helpful columns
        # "play" is differentiated from "poss" by counting OReb as new play
        # "plays" end with non-and1 FGA, TO, last non-tech FTA, or end of qtr
        # (or double lane viol)
        new_qtr = df.quarter.diff().shift(-1).fillna(False).astype(bool)  # noqa
        and1 = (  # noqa
            df.is_fgm
            & df.is_pf.shift(-1).fillna(False)
            & df.is_fta.shift(-2).fillna(False)
            & ~df.secs_elapsed.diff().shift(-1).fillna(False).astype(bool)
        )
        double_lane = df.get("viol_type") == "double lane"  # noqa

        new_play = df.eval(
            "(is_fga & ~(@and1)) | is_to | @new_qtr |"
            "(is_fta & ~is_tech_fta & fta_num == tot_fta) |"
            "@double_lane"
        )
        df["play_id"] = np.cumsum(new_play).shift(1).fillna(0)
        df["hm_off"] = df.off_team == df.home

        # get lineup data
        if dense_lineups:
            df = pd.concat((df, sportsref.nba.pbp.get_dense_lineups(df)), axis=1)
        if sparse_lineups:
            df = pd.concat((df, sportsref.nba.pbp.get_sparse_lineups(df)), axis=1)

        # TODO: add shot clock as a feature

        return df
