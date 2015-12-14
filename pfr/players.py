import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import pfr

__all__ = [
    'Player',
]

yr = datetime.datetime.now().year

class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = urlparse.urljoin(
            pfr.BASE_URL, '/players/{0[0]}/{0}.htm'
        ).format(self.pID)
        self.doc = None # filled in when necessary

    def __eq__(self, other):
        return self.pID == other.pID

    def __hash__(self):
        return hash(self.pID)

    def getDoc(self):
        if self.doc:
            return self.doc
        else:
            self.doc = pq(pfr.utils.getHTML(self.mainURL))
            return self.doc

    def age(self, year=yr):
        doc = self.getDoc()
        span = doc('div#info_box span#necro-birth')
        birthstring = span.attr('data-birth')
        dateargs = re.match(r'(\d{4})\-(\d{2})\-(\d{2})', birthstring).groups()
        dateargs = map(int, dateargs)
        birthdate = datetime.date(*dateargs)
        delta = datetime.date(year=year, month=9, day=1) - birthdate
        age = delta.days / 365.
        return age

    def av(self, year=yr):
        doc = self.getDoc()
        tables = doc('table[id]').filter(
            lambda i,e: 'AV' in e.text_content()
        )
        # if no AV table, return NaN
        if not tables:
            return np.nan
        # otherwise, extract the AV
        table = tables.eq(0)
        df = pfr.utils.parseTable(table)
        df = df.query('year_id == @year')
        # if the player has an AV for that year, return it
        if not df.empty:
            return df['av'].iloc[0]
        # otherwise, return NaN
        else:
            return np.nan

    def gamelog(self):
        """Gets the career gamelog of the given player.
        :returns: A DataFrame with the player's career gamelog.
        """
        url = urlparse.urljoin(
            pfr.BASE_URL, '/players/{0[0]}/{0}/gamelog'
        ).format(self.pID)
        doc = pq(pfr.utils.getHTML(url))
        table = doc('#stats')
        df = pfr.utils.parseTable(table)
        return df

    def passing(self):
        doc = self.getDoc()
        table = doc('#passing')
        df = pfr.utils.parseTable(table)
        return df

    def rushing_and_receiving(self):
        doc = self.getDoc()
        table = doc('#rushing_and_receiving')
        df = pfr.utils.parseTable(table)
        return df
