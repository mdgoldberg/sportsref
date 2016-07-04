import re

import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref

__all__ = [
    'Team',
]

@sportsref.decorators.memoized
class Team:

    def __init__(self, teamID):
        self.teamID = teamID
        
    def __eq__(self, other):
        return (self.teamID == other.teamID)

    def __hash__(self):
        return hash(self.teamID)

    @sportsref.decorators.memoized
    def getMainDoc(self):
        relURL = '/schools/{}'.format(self.teamID)
        teamURL = sportsref.ncaaf.BASE_URL + relURL
        mainDoc = pq(sportsref.utils.getHTML(teamURL))
        return mainDoc

    @sportsref.decorators.memoized
    def teamYearURL(self, yr_str):
        return (sportsref.ncaaf.BASE_URL +
                '/schools/{}/{}.html'.format(self.teamID, yr_str))

    @sportsref.decorators.memoized
    def getYearDoc(self, yr_str):
        return pq(sportsref.utils.getHTML(self.teamYearURL(yr_str)))

    def conference(self, year):
        """Returns the ID of the conference in which the team played that year.
        :year: The year in question.
        :returns: The conference ID.
        """
        doc = self.getYearDoc(year)
        anch = doc('div#info_box span:contains("Conference:")').next('a')
        return sportsref.utils.relURLToID(anch.attr['href'])

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

# TODO - BEGIN HERE
