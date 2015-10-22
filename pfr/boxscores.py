import datetime
import re
import urlparse

import requests
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from pfr import utils, BASE_URL

__all__ = [
]

yr = datetime.datetime.now().year

class BoxScore:

    def __init__(self, bsID):
        self.bsID = bsID
        self.mainURL = urlparse.urljoin(
            BASE_URL, '/boxscores/{}.htm'.format(self.bsID)
        )

    def date(self):
        match = re.match(r'(\d{4})(\d{2})(\d{2})', self.bsID)
        year, month, day = map(int, match.groups())
        return datetime.date(year=year, month=month, day=day)

    def home(self):
        """Returns home team ID.
        :returns: 3-character string representing home team's ID.
        """
        return self.bsID[-3:]

    def away(self):
        """Returns away team ID.
        :returns: 3-character string representing away team's ID.
        """
        doc = pq(utils.getHTML(self.mainURL))
        table = doc('table#linescore')
        away = utils.relURLToID(pq(table('tr')[1])('a').attr['href'])
        return away

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
        * home - 1 if the player's team was at home, 0 if they were away
        * offense - 1 if the player is starting on an offensive position, 0 if
        defense.

        :returns: A pandas DataFrame. See the description for details.
        """
        doc = pq(utils.getHTML(self.mainURL))
        pretable = next(div for div in map(pq, doc('div.table_heading')) 
                        if div('h2:contains("Starting Lineups")'))
        tableCont = map(pq, pretable.nextAll('div.table_container')[:2])
        a, h = (tc('table.stats_table') for tc in tableCont)
        data = []
        for h, table in enumerate((a, h)):
            team = self.home() if h else self.away()
            for i, row in enumerate(map(pq, table('tr[class=""]'))):
                datum = {}
                datum['playerID'] = utils.relURLToID(row('a')[0].attrib['href'])
                datum['playerName'] = row('a').filter(
                    lambda i,e: len(e.text_content()) > 0
                ).text()
                datum['position'] = row('td')[1].text_content()
                datum['team'] = team
                datum['home'] = (h == 1)
                datum['offense'] = (i <= 10)
                data.append(datum)
        return pd.DataFrame(data)


