import argparse
from bs4 import BeautifulSoup
import json
import os
from pprint import pprint
import requests
import time

PLAYER_SEASON_URL = ('http://www.pro-football-reference.com/'
                     'play-index/psl_finder.cgi')

CONSTANTS_FN = 'finderConstants.json'

def getPositions(soup):
    striplen = len('pos_is_')
    return [
        posBox['name'][striplen:] for posBox in
        soup.select('form#psl_finder input[name^="pos_is"]')
    ]

def getStats(soup):
    return [
        option['value'] for option in 
        soup.select('form#psl_finder select#c1stat option') if option.get('value')
    ]

def getTeams(soup):
    teams = []
    for option in soup.select('form#psl_finder select#team_id option'):
        if 'disabled' in option.attrs and 'Defunct' in option.text:
            break
        if option.get('value'):
            teams.append(option['value'])
    return teams

def getInputsAndDefaults(soup):
    # start with input elements
    def_dict = {}
    for inp in soup.select('form#psl_finder input[name]'):
        if inp['type'] in ('checkbox', 'radio'):
            if 'checked' in inp.attrs:
                def_dict[inp['name']] = inp['value']
            else:
                def_dict[inp['name']] = def_dict.get(inp['name'], '')
        else:
            def_dict[inp['name']] = inp.get('value', '')

    # for dropdowns (select elements)
    for sel in soup.select('form#psl_finder select[name]'):
        defaultOpt = sel.select_one('option[selected]')
        if defaultOpt:
            def_dict[sel['name']] = defaultOpt.get('value', '')
        else:
            def_dict[sel['name']] = sel.select_one('option').get('value', '')

    for k in def_dict:
        if 'pos_is_' in k:
            def_dict[k] = 'N'
    
    return def_dict

def getDraftInputs(soup):
    draftInputs = []
    add = False
    for opt in soup.select('form#psl_finder [name]'):
        if opt['name'] == 'draft':
            add = True
        if add:
            draftInputs.append(opt['name'])
    return draftInputs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('constfile', nargs='?', default=CONSTANTS_FN,
                        help='file to output as finder constants JSON')

    args = parser.parse_args()
    constfile = args.constfile

    html = requests.get(PLAYER_SEASON_URL).text
    soup = BeautifulSoup(html, 'lxml')

    obj = {
        'POSITIONS': getPositions(soup),
        'STATS': getStats(soup),
        'TEAMS': getTeams(soup),
        'INPUTS_DEFAULTS': getInputsAndDefaults(soup),
        'DRAFT_INPUTS': getDraftInputs(soup),
    }

    with open(constfile, 'w') as f:
        json.dump(obj, f)
else:
    # switch to finders directory
    orig_cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    # if file not found or it's been a week, generate it
    modtime = os.path.getmtime(CONSTANTS_FN)
    curtime = time.time()
    if not os.path.exists(CONSTANTS_FN) or curtime - modtime >= 7*24*60*60:
        subprocess.call([
            'python',
            'getFinderConstants.py'
        ])
    # store defaults variable
    with open(CONSTANTS_FN, 'r') as const_f:
        constants = json.load(const_f)
