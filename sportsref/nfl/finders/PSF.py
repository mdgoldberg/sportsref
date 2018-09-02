from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import map, zip
from past.builtins import basestring
import collections
import json
import os
import time
import urllib.parse

from pyquery import PyQuery as pq

from ... import decorators, utils

PSF_URL = ('http://www.pro-football-reference.com/'
           'play-index/psl_finder.cgi')

PSF_CONSTANTS_FILENAME = 'PSFConstants.json'


def PlayerSeasonFinder(**kwargs):
    """ Docstring will be filled in by __init__.py """

    if 'offset' not in kwargs:
        kwargs['offset'] = 0

    playerSeasons = []
    while True:
        querystring = _kwargs_to_qs(**kwargs)
        url = '{}?{}'.format(PSF_URL, querystring)
        if kwargs.get('verbose', False):
            print(url)
        html = utils.get_html(url)
        doc = pq(html)
        table = doc('table#results')
        df = utils.parse_table(table)
        if df.empty:
            break

        thisSeason = list(zip(df.player_id, df.year))
        playerSeasons.extend(thisSeason)

        if doc('*:contains("Next Page")'):
            kwargs['offset'] += 100
        else:
            break

    return playerSeasons


def _kwargs_to_qs(**kwargs):
    """Converts kwargs given to PSF to a querystring.

    :returns: the querystring.
    """
    # start with defaults
    inpOptDef = inputs_options_defaults()
    opts = {
        name: dct['value']
        for name, dct in inpOptDef.items()
    }

    # clean up keys and values
    for k, v in kwargs.items():
        del kwargs[k]
        # bool => 'Y'|'N'
        if isinstance(v, bool):
            kwargs[k] = 'Y' if v else 'N'
        # tm, team => team_id
        elif k.lower() in ('tm', 'team'):
            kwargs['team_id'] = v
        # yr, year, yrs, years => year_min, year_max
        elif k.lower() in ('yr', 'year', 'yrs', 'years'):
            if isinstance(v, collections.Iterable):
                lst = list(v)
                kwargs['year_min'] = min(lst)
                kwargs['year_max'] = max(lst)
            elif isinstance(v, basestring):
                v = list(map(int, v.split(',')))
                kwargs['year_min'] = min(v)
                kwargs['year_max'] = max(v)
            else:
                kwargs['year_min'] = v
                kwargs['year_max'] = v
        # pos, position, positions => pos[]
        elif k.lower() in ('pos', 'position', 'positions'):
            if isinstance(v, basestring):
                v = v.split(',')
            elif not isinstance(v, collections.Iterable):
                v = [v]
            kwargs['pos[]'] = v
        # draft_pos, ... => draft_pos[]
        elif k.lower() in (
            'draft_pos', 'draftpos', 'draftposition', 'draftpositions',
            'draft_position', 'draft_positions'
        ):
            if isinstance(v, basestring):
                v = v.split(',')
            elif not isinstance(v, collections.Iterable):
                v = [v]
            kwargs['draft_pos[]'] = v
        # if not one of these cases, put it back in kwargs
        else:
            kwargs[k] = v

    # update based on kwargs
    for k, v in kwargs.items():
        # if overwriting a default, overwrite it (with a list so the
        # opts -> querystring list comp works)
        if k in opts or k in ('pos[]', 'draft_pos[]'):
            # if multiple values separated by commas, split em
            if isinstance(v, basestring):
                v = v.split(',')
            # otherwise, make sure it's a list
            elif not isinstance(v, collections.Iterable):
                v = [v]
            # then, add list of values to the querystring dict *opts*
            opts[k] = v
        if 'draft' in k:
            opts['draft'] = [1]

    opts['request'] = [1]
    opts['offset'] = [kwargs.get('offset', 0)]

    qs = '&'.join(
        '{}={}'.format(urllib.parse.quote_plus(name), val)
        for name, vals in sorted(opts.items()) for val in vals
    )

    return qs


@decorators.switch_to_dir(os.path.dirname(os.path.realpath(__file__)))
def inputs_options_defaults():
    """Handles scraping options for player-season finder form.

    :returns: {'name1': {'value': val, 'options': [opt1, ...] }, ... }
    """
    # set time variables
    if os.path.isfile(PSF_CONSTANTS_FILENAME):
        modtime = int(os.path.getmtime(PSF_CONSTANTS_FILENAME))
        curtime = int(time.time())
    # if file found and it's been <= a week
    if (os.path.isfile(PSF_CONSTANTS_FILENAME)
            and curtime - modtime <= 7 * 24 * 60 * 60):

        # just read the dict from cached file
        with open(PSF_CONSTANTS_FILENAME, 'r') as const_f:
            def_dict = json.load(const_f)

    # otherwise, we must regenerate the dict and rewrite it
    else:

        print('Regenerating PSFConstants file')

        html = utils.get_html(PSF_URL)
        doc = pq(html)

        def_dict = {}
        # start with input elements
        for inp in doc('form#psl_finder input[name]'):
            name = inp.attrib['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp.attrib['type']
                }

            # handle checkboxes and radio buttons
            if inp.attrib['type'] in ('checkbox', 'radio'):
                # deal with default value
                if 'checked' in inp.attrib:
                    def_dict[name]['value'].add(inp.attrib['value'])
                # add to options
                def_dict[name]['options'].add(inp.attrib['value'])
            # handle other types of inputs (only other type is hidden?)
            else:
                def_dict[name]['value'].add(inp.attrib.get('value', ''))

        # deal with dropdowns (select elements)
        for sel in doc.items('form#psl_finder select[name]'):
            name = sel.attr['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': 'select'
                }

            # deal with default value
            defaultOpt = sel('option[selected]')
            if len(defaultOpt):
                defaultOpt = defaultOpt[0]
                def_dict[name]['value'].add(defaultOpt.attrib.get('value', ''))
            else:
                def_dict[name]['value'].add(
                    sel('option')[0].attrib.get('value', '')
                )

            # deal with options
            def_dict[name]['options'] = {
                opt.attrib['value'] for opt in sel('option')
                if opt.attrib.get('value')
            }

        def_dict.pop('request', None)
        def_dict.pop('use_favorites', None)

        with open(PSF_CONSTANTS_FILENAME, 'w+') as f:
            for k in def_dict:
                try:
                    def_dict[k]['value'] = sorted(
                        list(def_dict[k]['value']), key=int
                    )
                    def_dict[k]['options'] = sorted(
                        list(def_dict[k]['options']), key=int
                    )
                except Exception:
                    def_dict[k]['value'] = sorted(list(def_dict[k]['value']))
                    def_dict[k]['options'] = sorted(
                        list(def_dict[k]['options'])
                    )
            json.dump(def_dict, f)

    return def_dict
