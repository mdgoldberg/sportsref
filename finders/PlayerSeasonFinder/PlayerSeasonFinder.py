from bs4 import BeautifulSoup
from copy import deepcopy
import json
import os
from pprint import pprint
import requests
import time

from constants import constants

def PlayerSeasonFinder(**kwargs):

    opts = kwArgsToOpts(**kwargs)
    querystring = '&'.join(['{}={}'.format(k, v) for k, v in opts.iteritems()])
    url = ('http://www.pro-football-reference.com/' +
           'play-index/psl_finder.cgi?' +
           querystring)
    print url
    html = requests.get(url).text
    soup = BeautifulSoup(html, 'lxml')
    for row in soup.select('table#stats tbody tr[class=""]'):
        row.select_one('a').get('href')
        # I'm here

def kwArgsToOpts(**kwargs):

    # if positions addressed in one kwarg, give it priority over pos_is_X
    # entries by overwriting each of those it addresses
    ext = {}
    for k, v in kwargs.iteritems():
        if k.lower() in ('pos', 'position', 'positions'):
            v = [v] if not isinstance(v, list) else v
            for pos in constants['POSITIONS']:
                if pos in v:
                    ext['pos_is_' + pos] = 'Y'
    kwargs.update(ext)

    # same as above for draft position
    ext = {}
    for k, v in kwargs.iteritems():
        if k.lower() in ('draft_pos', 'draft_position', 'draft_positions'):
            v = [v] if not isinstance(v, list) else v
            for pos in constants['POSITIONS']:
                if pos in v:
                    ext['draft_pos_is_' + pos] = 'Y'
                else:
                    ext['draft_pos_is_' + pos] = 'N'
    kwargs.update(ext)

    # start with defaults
    opts = deepcopy(constants['INPUTS_DEFAULTS'])
    # update based on kwargs
    for k, v in kwargs.iteritems():
        # small changes to keys/values for convenience
        k = 'team_id' if k in ('tm', 'team') else k
        v = 'Y' if v == True else v
        v = 'N' if v == False else v
        # if overwriting a default
        if k in opts:
            opts[k] = v

    # if no positions were selected, then select all positions
    noPos = True
    for k in kwargs:
        if k.startswith('pos_is_') and kwargs[k] in ('Y', True, 'y'):
            noPos = False
            break
    if noPos:
        for pos in constants['POSITIONS']:
            opts['pos_is_' + pos] = 'Y'

    # same as above for draft positions
    noPos = True
    for k in kwargs:
        if k.startswith('draft_pos_is_') and kwargs[k] in ('Y', True, 'y'):
            noPos = False
            break
    if noPos:
        for pos in constants['POSITIONS']:
            opts['draft_pos_is_' + pos] = 'Y'

    # turning on draft flag if necessary
    draft = False
    for k in opts:
        if k in constants['DRAFT_INPUTS']:
            draft = True
    if draft:
        opts['draft'] = '1'

    return opts

PlayerSeasonFinder(**{
    'year_min': 2000, 'year_max': 2014, 'pos': 'rb', 'order_by': 'rush_yds_per_g'
})
