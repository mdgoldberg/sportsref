import collections
from copy import deepcopy
import json
import os
from pprint import pprint
import requests
import time

from bs4 import BeautifulSoup
import pandas as pd

from pfr.decorators import switchToDir
from pfr.utils import getHTML

GAME_PLAY_URL = ('http://www.pro-football-reference.com/'
                 'play-index/play_finder.cgi')

CONSTANTS_FN = 'GPFConstants.json'

def GamePlayFinder(**kwargs):
    """ Docstring will be filled in by __init__.py """

    querystring = kwArgsToQS(**kwargs)
    url = '{}?{}'.format(GAME_PLAY_URL, querystring)
    # if verbose, print url
    if kwargs.get('verbose', False):
        print url
    html = getHTML(url)
    soup = BeautifulSoup(html, 'lxml')
    
    # try to parse soup
    try:
        table = soup.select_one('#div_ table.stats_table')
        cols = [
            th.string
            for th in table.select('thead tr th[data-stat]')
        ]
        cols[-1] = 'EPDiff'
        data = [
            [td.get_text() if td.get_text() else '0'
             for td in row.find_all('td')]
            for row in table.select('tbody tr[class=""]')
        ]
        plays = pd.DataFrame(data, columns=cols, dtype=float)
    except Exception:
        # if parsing goes wrong, return empty DataFrame
        plays = pd.DataFrame()

    return plays

def kwArgsToQS(**kwargs):
    """Converts kwargs given to GPF to a querystring.

    :returns: the querystring.
    """
    # start with defaults
    inpOptDef = getInputsOptionsDefaults()
    opts = {
        name: dct['value']
        for name, dct in inpOptDef.iteritems()
    }

    # clean up keys and values
    for k, v in kwargs.items():
        # bool => 'Y'|'N'
        if isinstance(v, bool):
            kwargs[k] = 'Y' if v else 'N'
        # tm, team => team_id
        if k.lower() in ('tm', 'team'):
            del kwargs[k]
            kwargs['team_id'] = v
        # yr, year, yrs, years => year_min, year_max
        if k.lower() in ('yr', 'year', 'yrs', 'years'):
            del kwargs[k]
            if isinstance(v, collections.Iterable):
                lst = list(v)
                kwargs['year_min'] = min(lst)
                kwargs['year_max'] = max(lst)
            elif isinstance(v, basestring):
                v = map(int, v.split(','))
                kwargs['year_min'] = min(v)
                kwargs['year_max'] = max(v)
            else:
                kwargs['year_min'] = v
                kwargs['year_max'] = v
        # if playoff_round defined, then turn on playoff flag
        if k == 'playoff_round':
            kwargs['game_type'] = 'P'
        if isinstance(v, basestring):
            v = v.split(',')
        if not isinstance(v, collections.Iterable):
            v = [v]

    # reset values to blank for defined kwargs
    for k in kwargs:
        if k in opts:
            opts[k] = []

    # update based on kwargs
    for k, v in kwargs.iteritems():
        # if overwriting a default, overwrite it
        if k in opts:
            # if multiple values separated by commas, split em
            if isinstance(v, basestring):
                v = v.split(',')
            elif not isinstance(v, collections.Iterable):
                v = [v]
            for val in v:
                opts[k].append(val)

    opts['request'] = [1]
    
    qs = '&'.join('{}={}'.format(name, val)
                  for name, vals in sorted(opts.iteritems()) for val in vals)

    return qs

@switchToDir(os.path.dirname(os.path.realpath(__file__)))
def getInputsOptionsDefaults():
    """Handles scraping options for play finder form.

    :returns: {'name1': {'value': val, 'options': [opt1, ...] }, ... }

    """
    # set time variables
    if os.path.isfile(CONSTANTS_FN):
        modtime = os.path.getmtime(CONSTANTS_FN)
        curtime = time.time()
    else:
        modtime = 0
        curtime = 0
    # if file not found or it's been >= a day, generate new constants
    if not (os.path.isfile(CONSTANTS_FN) and
            int(curtime) - int(modtime) <= 24*60*60):

        # must generate the file
        print 'Regenerating constants file'

        html = getHTML(GAME_PLAY_URL)
        soup = BeautifulSoup(html, 'lxml')
        
        def_dict = {}
        # start with input elements
        for inp in soup.select('form#play_finder input[name]'):
            name = inp['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp['type']
                }

            # handle checkboxes and radio buttons
            if inp['type'] in ('checkbox', 'radio'):
                # deal with default value
                if 'checked' in inp.attrs:
                    def_dict[name]['value'].add(inp['value'])
                # add to options
                def_dict[name]['options'].add(inp['value'])
            # handle other types of inputs (only other type is hidden?)
            else:
                def_dict[name]['value'].add(inp.get('value', ''))


        # for dropdowns (select elements)
        for sel in soup.select('form#play_finder select[name]'):
            name = sel['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp['type']
                }
            
            # deal with default value
            defaultOpt = sel.select_one('option[selected]')
            if defaultOpt:
                def_dict[name]['value'].add(defaultOpt.get('value', ''))
            else:
                def_dict[name]['value'].add(
                    sel.select_one('option').get('value', '')
                )

            # deal with options
            def_dict[name]['options'] = {opt['value']
                                         for opt in sel.select('option')
                                         if opt.get('value')}
        
        # ignore QB kneels by default
        def_dict['include_kneels']['value'] = ['0']

        def_dict.pop('request', None)
        def_dict.pop('use_favorites', None)
        
        with open(CONSTANTS_FN, 'w+') as f:
            for k in def_dict:
                try:
                    def_dict[k]['value'] = sorted(
                        list(def_dict[k]['value']), key=int
                    )
                    def_dict[k]['options'] = sorted(
                        list(def_dict[k]['options']), key=int
                    )
                except:
                    def_dict[k]['value'] = sorted(list(def_dict[k]['value']))
                    def_dict[k]['options'] = sorted(list(def_dict[k]['options']))
            json.dump(def_dict, f)

    # else, just read variable from cached file
    else:
        with open(CONSTANTS_FN, 'r') as const_f:
            def_dict = json.load(const_f)

    return def_dict
