import numpy as np
from scipy.stats import norm


def initialWinProb(line):
    """Gets the initial win probability of a game given its Vegas line.

    :line: The Vegas line from the home team's perspective (negative means
    home team is favored).
    :returns: A float in [0., 100.] that represents the win probability.
    """
    line = float(line)
    probWin = 1. - norm.cdf(0.5, -line, 13.86)
    probTie = norm.cdf(0.5, -line, 13.86) - norm.cdf(-0.5, -line, 13.86)
    return 100. * (probWin + 0.5 * probTie)


def winProb(line, margin, secsElapsed, expPts):
    line = float(line)
    margin = float(margin)
    expPts = float(expPts)
    baseMean = -line
    baseStd = 13.46
    expMargin = margin + expPts
    minRemain = 60. - secsElapsed / 60. + 0.00001
    adjMean = baseMean * (minRemain / 60.)
    adjStd = baseStd / np.sqrt(60. / minRemain)
    probWin = 1. - norm.cdf(-expMargin + 0.5, adjMean, adjStd)
    probTie = (norm.cdf(-expMargin + 0.5, adjMean, adjStd) -
               norm.cdf(-expMargin - 0.5, adjMean, adjStd))
    return 100. * (probWin + 0.5 * probTie)
