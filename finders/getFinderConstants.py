import argparse
from bs4 import BeautifulSoup
import json
import requests

URL = 'http://www.pro-football-reference.com/play-index/psl_finder.cgi'

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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('constfile', nargs='?', default='finderConstants.json',
                        help='file to output as finder constants JSON')

    args = parser.parse_args()
    constfile = args.constfile

    html = requests.get(URL).text
    soup = BeautifulSoup(html, 'lxml')

    obj = {
        'POSITIONS': getPositions(soup),
        'STATS': getStats(soup),
        'TEAMS': getTeams(soup)
    }

    with open(constfile, 'w') as f:
        json.dump(obj, f)
