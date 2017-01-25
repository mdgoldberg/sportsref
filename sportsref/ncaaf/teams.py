import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Team',
]

@sportsref.decorators.memoize
class Team:

    def __init__(self, teamID):
        self.teamID = teamID
        self.relURL = '/schools/{}'.format(self.teamID)
        self.teamURL = sportsref.ncaaf.BASE_URL + self.relURL
        
    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    @sportsref.decorators.memoize
    def getMainDoc(self):
        mainDoc = pq(sportsref.utils.get_html(self.teamURL))
        return mainDoc

    @sportsref.decorators.memoize
    def teamYearURL(self, yr_str):
        return (sportsref.ncaaf.BASE_URL +
                '/schools/{}/{}.html'.format(self.teamID, yr_str))

    @sportsref.decorators.memoize
    def getYearDoc(self, yr_str):
        return pq(sportsref.utils.get_html(self.teamYearURL(yr_str)))

    def conference(self, year):
        """Returns the ID of the conference in which the team played that year.
        :year: The year in question.
        :returns: The conference ID.
        """
        doc = self.getYearDoc(year)
        anch = doc('div#info_box span:contains("Conference:")').next('a')
        return sportsref.utils.rel_url_to_id(anch.attr['href'])

    def srs(self, year):
        """Returns the SRS (Simple Rating System) for the team for a given
        year.
        :year: The season in question.
        :returns: A float for the team's SRS in that season.
        """
        doc = self.getYearDoc(year)
        m = re.search(r'SRS.*?([\d\.]+)', doc.text())
        if m:
            return float(m.group(1))
        else:
            print "ERROR: NO SRS FOUND FOR {} in {}".format(self.teamID, year)
            return np.nan

    def sos(self, year):
        """Returns the SOS (Strength of Schedule) for the team for a given
        year.
        :year: The season in question.
        :returns: A float for the team's SOS in that season.
        """
        doc = self.getYearDoc(year)
        m = re.search(r'SOS.*?([\d\.]+)', doc.text())
        if m:
            return float(m.group(1))
        else:
            print "ERROR: NO SRS FOUND FOR {} in {}".format(self.teamID, year)
            return np.nan

    def get_roster(self, year):
        """ Returns the roster for a team for the year

        :param year: the year of the roster
        :return: a dataframe with the player_id, class, and position
        """
        url = (sportsref.ncaaf.BASE_URL +
               '/schools/{}/{}-roster.html'.format(self.teamID, str(year)))
        doc = pq(sportsref.utils.get_html(url))
        table = doc('#all_roster')
        df = sportsref.utils.parse_table(table)
        return df

def get_all_college_teams():
    """ Returns all the college teams from http://www.sports-reference.com/cfb

    :return: A dataframe with all the teams that have ever played in college
    football, the year they started and finished, their records, and their
    schedule strengths
    """
    # set link and table_name and then get the pyquery table
    link = "http://www.sports-reference.com/cfb/schools/"
    doc = pq(sportsref.utils.get_html(link))
    table = doc('#all_schools')
    df = sportsref.utils.parse_table(table)
    return df