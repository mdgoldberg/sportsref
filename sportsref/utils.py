import ctypes
import multiprocessing
import re
import threading
import time

import pandas as pd
import requests
from pyquery import PyQuery as pq

import sportsref

# time between requests, in seconds
THROTTLE_DELAY = 0.5

# variables used to throttle requests across processes
throttle_thread_lock = threading.Lock()
throttle_process_lock = multiprocessing.Lock()
last_request_time = multiprocessing.Value(
    ctypes.c_longdouble, time.time() - 10 * THROTTLE_DELAY
)


@sportsref.decorators.cache
def get_html(url):
    """Gets the HTML for the given URL using a GET request.

    :url: the absolute URL of the desired page.
    :returns: a string of HTML.
    """
    global last_request_time
    with throttle_process_lock:
        with throttle_thread_lock:
            # sleep until THROTTLE_DELAY secs have passed since last request
            wait_left = THROTTLE_DELAY - (time.time() - last_request_time.value)
            if wait_left > 0:
                time.sleep(wait_left)

            # make request
            response = requests.get(url)

            # update last request time for throttling
            last_request_time.value = time.time()

    # raise ValueError on 4xx status code, get rid of comments, and return
    if 400 <= response.status_code < 500:
        raise ValueError(
            f'Status Code {response.status_code} received fetching URL "{url}"'
        )
    html = response.text
    html = html.replace("<!--", "").replace("-->", "")

    return html


def parse_table(table, flatten=True, footer=False):
    """Parses a table from sports-reference sites into a pandas dataframe.

    :param table: the PyQuery object representing the HTML table
    :param flatten: if True, flattens relative URLs to IDs. otherwise, leaves
        all fields as text without cleaning.
    :param footer: If True, returns the summary/footer of the page. Recommended
        to use this with flatten=False. Defaults to False.
    :returns: pd.DataFrame
    """
    if not len(table):
        return pd.DataFrame()

    # get columns
    columns = [
        c.attrib["data-stat"] for c in table("thead tr:not([class]) th[data-stat]")
    ]

    # get data
    rows = list(
        table("tbody tr" if not footer else "tfoot tr")
        .not_(".thead, .stat_total, .stat_average")
        .items()
    )
    data = [
        [flatten_links(td) if flatten else td.text() for td in row.items("th,td")]
        for row in rows
    ]

    # make DataFrame
    df = pd.DataFrame(data, columns=columns, dtype="float")

    # add has_class columns
    allClasses = set(
        cls for row in rows if row.attr["class"] for cls in row.attr["class"].split()
    )
    for cls in allClasses:
        df["has_class_" + cls] = [
            bool(row.attr["class"] and cls in row.attr["class"].split()) for row in rows
        ]

    # cleaning the DataFrame

    df.drop(["ranker", "Xxx", "Yyy", "Zzz"], axis=1, inplace=True, errors="ignore")

    # year_id -> year (as int)
    if "year_id" in df.columns:
        df.rename(columns={"year_id": "year"}, inplace=True)
        if flatten:
            df.year = df.year.fillna(method="ffill")
            df["year"] = df.year.map(lambda s: str(s)[:4]).astype(int)

    # pos -> position
    if "pos" in df.columns:
        df.rename(columns={"pos": "position"}, inplace=True)

    # boxscore_word, game_date -> boxscore_id and separate into Y, M, D columns
    for bs_id_col in ("boxscore_word", "game_date", "box_score_text"):
        if bs_id_col in df.columns:
            df.rename(columns={bs_id_col: "boxscore_id"}, inplace=True)
            break

    # ignore *, +, and other characters used to note things
    df.replace(re.compile(r"[\*\+\u2605]", re.U), "", inplace=True)
    for col in df.columns:
        if hasattr(df[col], "str"):
            df[col] = df[col].str.strip()

    # player -> player_id and/or player_name
    if "player" in df.columns:
        if flatten:
            df.rename(columns={"player": "player_id"}, inplace=True)
            # when flattening, keep a column for names
            player_names = parse_table(table, flatten=False)["player_name"]
            df["player_name"] = player_names
        else:
            df.rename(columns={"player": "player_name"}, inplace=True)

    # team, team_name -> team_id
    for team_col in ("team", "team_name"):
        if team_col in df.columns:
            # first, get rid of faulty rows
            df = df.loc[~df[team_col].isin(["XXX"])]
            if flatten:
                df.rename(columns={team_col: "team_id"}, inplace=True)

    # season -> int
    if "season" in df.columns and flatten:
        df["season"] = df["season"].astype(int)

    # handle date_game columns (different types)
    if "date_game" in df.columns and flatten:
        date_re = r"month=(?P<month>\d+)&day=(?P<day>\d+)&year=(?P<year>\d+)"
        date_df = df["date_game"].str.extract(date_re, expand=True)
        if date_df.notnull().all(axis=1).any():
            df = pd.concat((df, date_df), axis=1)
        else:
            df.rename(columns={"date_game": "boxscore_id"}, inplace=True)

    # game_location -> is_home
    if "game_location" in df.columns and flatten:
        df["game_location"] = df["game_location"].isnull()
        df.rename(columns={"game_location": "is_home"}, inplace=True)

    # mp: (min:sec) -> float(min + sec / 60), notes -> NaN, new column
    if "mp" in df.columns and df.dtypes["mp"] == object and flatten:
        mp_df = (
            df["mp"].str.extract(r"(?P<m>\d+):(?P<s>\d+)", expand=True).astype(float)
        )
        no_match = mp_df.isnull().all(axis=1)
        if no_match.any():
            df.loc[no_match, "note"] = df.loc[no_match, "mp"]
        df["mp"] = mp_df["m"] + mp_df["s"] / 60

    # converts number-y things to floats
    def convert_to_float(val):
        # percentages: (number%) -> float(number * 0.01)
        m = re.search(r"([-\.\d]+)\%", val if isinstance(val, str) else str(val), re.U)
        try:
            if m:
                return float(m.group(1)) / 100 if m else val
            if m:
                return int(m.group(1)) + int(m.group(2)) / 60
        except ValueError:
            return val
        # salaries: $ABC,DEF,GHI -> float(ABCDEFGHI)
        m = re.search(r"\$[\d,]+", val if isinstance(val, str) else str(val), re.U)
        try:
            if m:
                return float(re.sub(r"\$|,", "", val))
        except Exception:
            return val
        # generally try to coerce to float, unless it's an int or bool
        try:
            if isinstance(val, (int, bool)):
                return val
            else:
                return float(val)
        except Exception:
            return val

    if flatten:
        df = df.applymap(convert_to_float)

    df = df.loc[df.astype(bool).any(axis=1)]

    return df


def parse_info_table(table):
    """Parses an info table, like the "Game Info" table or the "Officials"
    table on the PFR Boxscore page. Keys are lower case and have spaces/special
    characters converted to underscores.

    :table: PyQuery object representing the HTML table.
    :returns: A dictionary representing the information.
    """
    ret = {}
    for tr in list(table("tr").not_(".thead").items()):
        th, td = list(tr("th, td").items())
        key = th.text().lower()
        key = re.sub(r"\W", "_", key)
        val = sportsref.utils.flatten_links(td)
        ret[key] = val
    return ret


def parse_awards_table(table):
    """Parses an awards table, like the "Pro Bowls" table on a PFR player page.

    :table: PyQuery object representing the HTML table.
    :returns: A list of the entries in the table, with flattened links.
    """
    return [flatten_links(tr) for tr in list(table("tr").items())]


def flatten_links(td, _recurse=False):
    """Flattens relative URLs within text of a table cell to IDs and returns
    the result.

    :td: the PyQuery object for the HTML to convert
    :returns: the string with the links flattened to IDs
    """

    # helper function to flatten individual strings/links
    def _flatten_node(c):
        if isinstance(c, str):
            return c
        elif "href" in c.attrib:
            c_id = rel_url_to_id(c.attrib["href"])
            return c_id if c_id else c.text_content()
        else:
            return flatten_links(pq(c), _recurse=True)

    # if there's no text, just return None
    if td is None or not td.text():
        return "" if _recurse else None

    td.remove("span.note")
    return "".join(_flatten_node(c) for c in td.contents())


@sportsref.decorators.memoize
def rel_url_to_id(url):
    """Converts a relative URL to a unique ID.

    Here, 'ID' refers generally to the unique ID for a given 'type' that a
    given datum has. For example, 'BradTo00' is Tom Brady's player ID - this
    corresponds to his relative URL, '/players/B/BradTo00.htm'. Similarly,
    '201409070dal' refers to the boxscore of the SF @ DAL game on 09/07/14.

    Supported types:
    * player/...
    * boxscores/...
    * teams/...
    * years/...
    * leagues/...
    * awards/...
    * coaches/...
    * officials/...
    * schools/...
    * schools/high_schools.cgi?id=...

    :returns: ID associated with the given relative URL.
    """
    yearRegex = r".*/years/(\d{4}).*|.*/gamelog/(\d{4}).*"
    playerRegex = r".*/players/(?:\w/)?(.+?)(?:/|\.html?)"
    boxscoresRegex = r".*/boxscores/(.+?)\.html?"
    teamRegex = r".*/teams/(\w{3})/.*"
    coachRegex = r".*/coaches/(.+?)\.html?"
    stadiumRegex = r".*/stadiums/(.+?)\.html?"
    refRegex = r".*/officials/(.+?r)\.html?"
    collegeRegex = r".*/schools/(\S+?)/.*|.*college=([^&]+)"
    hsRegex = r".*/schools/high_schools\.cgi\?id=([^\&]{8})"
    bsDateRegex = r".*/boxscores/index\.f?cgi\?(month=\d+&day=\d+&year=\d+)"
    leagueRegex = r".*/leagues/(.*_\d{4}).*"
    awardRegex = r".*/awards/(.+)\.htm"

    regexes = [
        yearRegex,
        playerRegex,
        boxscoresRegex,
        teamRegex,
        coachRegex,
        stadiumRegex,
        refRegex,
        collegeRegex,
        hsRegex,
        bsDateRegex,
        leagueRegex,
        awardRegex,
    ]

    for regex in regexes:
        match = re.match(regex, url, re.I)
        if match:
            return [_f for _f in match.groups() if _f][0]

    # things we don't want to match but don't want to print a WARNING
    if any(url.startswith(s) for s in ("/play-index/",)):
        return url

    print(f'WARNING. NO MATCH WAS FOUND FOR "{url}"')
    return url
