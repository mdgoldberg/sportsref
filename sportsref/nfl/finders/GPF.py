import collections
import json
import os
import time

from pyquery import PyQuery as pq

from ... import decorators, utils
from .. import pbp

GPF_URL = ('http://www.pro-football-reference.com/'
           'play-index/play_finder.cgi')

GPF_CONSTANTS_FILENAME = 'GPFConstants.json'


@decorators.memoize
def GamePlayFinder(**kwargs):
    """ Docstring will be filled in by __init__.py """

    querystring = _kwargs_to_qs(**kwargs)
    url = '{}?{}'.format(GPF_URL, querystring)
    # if verbose, print url
    if kwargs.get('verbose', False):
        print url
    html = utils.get_html(url)
    doc = pq(html)

    # parse
    table = doc('table#all_plays')
    plays = utils.parse_table(table)

    # parse score column
    if 'score' in plays.columns:
        oScore, dScore = zip(*plays.score.apply(lambda s: s.split('-')))
        plays['teamScore'] = oScore
        plays['oppScore'] = dScore
    # add parsed pbp info
    if 'description' in plays.columns:
        plays = pbp.expandDetails(plays, detailCol='description')

    return plays


def _kwargs_to_qs(**kwargs):
    """Converts kwargs given to GPF to a querystring.

    :returns: the querystring.
    """
    # start with defaults
    inpOptDef = inputs_options_defaults()
    opts = {
        name: dct['value']
        for name, dct in inpOptDef.iteritems()
    }

    # clean up keys and values
    for k, v in kwargs.items():
        # pID, playerID => player_id
        if k.lower() in ('pid', 'playerid'):
            del kwargs[k]
            kwargs['player_id'] = v
        # player_id can accept rel URLs
        if k == 'player_id':
            if v.startswith('/players/'):
                kwargs[k] = utils.rel_url_to_id(v)
        # bool => 'Y'|'N'
        if isinstance(v, bool):
            kwargs[k] = 'Y' if v else 'N'
        # tm, team => team_id
        if k.lower() in ('tm', 'team'):
            del kwargs[k]
            kwargs['team_id'] = v
        # yr_min, yr_max => year_min, year_max
        if k.lower() in ('yr_min', 'yr_max'):
            del kwargs[k]
            if k.lower() == 'yr_min':
                kwargs['year_min'] = int(v)
            else:
                kwargs['year_max'] = int(v)
        # wk_min, wk_max => week_num_min, week_num_max
        if k.lower() in ('wk_min', 'wk_max'):
            del kwargs[k]
            if k.lower() == 'wk_min':
                kwargs['week_num_min'] = int(v)
            else:
                kwargs['week_num_max'] = int(v)
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
        # wk, week, wks, weeks => week_num_min, week_num_max
        if k.lower() in ('wk', 'week', 'wks', 'weeks'):
            del kwargs[k]
            if isinstance(v, collections.Iterable):
                lst = list(v)
                kwargs['week_num_min'] = min(lst)
                kwargs['week_num_max'] = max(lst)
            elif isinstance(v, basestring):
                v = map(int, v.split(','))
                kwargs['week_num_min'] = min(v)
                kwargs['week_num_max'] = max(v)
            else:
                kwargs['week_num_min'] = v
                kwargs['week_num_max'] = v
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


@decorators.switch_to_dir(os.path.dirname(os.path.realpath(__file__)))
def inputs_options_defaults():
    """Handles scraping options for play finder form.

    :returns: {'name1': {'value': val, 'options': [opt1, ...] }, ... }

    """
    # set time variables
    if os.path.isfile(GPF_CONSTANTS_FILENAME):
        modtime = int(os.path.getmtime(GPF_CONSTANTS_FILENAME))
        curtime = int(time.time())
    # if file found and it's been <= a week
    if (os.path.isfile(GPF_CONSTANTS_FILENAME)
            and curtime - modtime <= 7 * 24 * 60 * 60):

        # just read the dict from the cached file
        with open(GPF_CONSTANTS_FILENAME, 'r') as const_f:
            def_dict = json.load(const_f)

    # otherwise, we must regenerate the dict and rewrite it
    else:

        print 'Regenerating GPFConstants file'

        html = utils.get_html(GPF_URL)
        doc = pq(html)

        def_dict = {}
        # start with input elements
        for inp in doc('form#play_finder input[name]'):
            name = inp.attrib['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp.type
                }

            val = inp.attrib.get('value', '')
            # handle checkboxes and radio buttons
            if inp.type in ('checkbox', 'radio'):
                # deal with default value
                if 'checked' in inp.attrib:
                    def_dict[name]['value'].add(val)
                # add to options
                def_dict[name]['options'].add(val)
            # handle other types of inputs (only other type is hidden?)
            else:
                def_dict[name]['value'].add(val)

        # for dropdowns (select elements)
        for sel in doc.items('form#play_finder select[name]'):
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

        # ignore QB kneels by default
        def_dict['include_kneels']['value'] = ['0']

        def_dict.pop('request', None)
        def_dict.pop('use_favorites', None)

        with open(GPF_CONSTANTS_FILENAME, 'w+') as f:
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
                    def_dict[k]['options'] = sorted(
                        list(def_dict[k]['options'])
                    )
            json.dump(def_dict, f)

    return def_dict
