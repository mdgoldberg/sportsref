import datetime
import re
import urlparse

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import pfr
from pfr import utils

__all__ = [
    'Player',
]

yr = datetime.datetime.now().year

class Player:

    def __init__(self, playerID):
        self.pID = playerID
        self.mainURL = urlparse.urljoin(
            pfr.BASE_URL,
            '/players/{0[0]}/{0}.htm'
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

