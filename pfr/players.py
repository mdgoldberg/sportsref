import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

from pfr import utils, BASE_URL

__all__ = [
    'Player',
]

yr = datetime.datetime.now().year

class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = urlparse.urljoin(
            BASE_URL, '/players/{0[0]}/{0}.htm'
        ).format(self.pID)

    def age(self, year=yr):
        doc = pq(utils.getHTML(self.mainURL))
        span = doc('div#info_box span#necro-birth')
        birthstring = span.attr('data-birth')
        dateargs = re.match(r'(\d{4})\-(\d{2})\-(\d{2})', birthstring).groups()
        dateargs = map(int, dateargs)
        birthdate = datetime.date(*dateargs)
        delta = datetime.date(year=year, month=9, day=1) - birthdate
        age = delta.days / 365.
        return age

    def av(self, year=yr):
        doc = pq(utils.getHTML(self.mainURL))
        try:
            tables = doc('table').filter(
                lambda i,e: 'AV' in e.text_content()
            )
            
            if len(tables) > 1:
                print 'TOO MANY TABLES for AV for player ' + self.pID
            
            table = pq(tables[0])
            df = utils.parseTable(table)
            df = df.query('year_id == @year')
            if not df.empty:
                return df['av'].iloc[0]
            else:
                return np.nan
        except Exception as e:
            raise e
            print 'Exception raised, returning 0'
            return 0
