import operator as op

import pandas as pd

from pfr.finders import GamePlayFinder as GPF
from pfr import utils

r = GPF.GamePlayFinder(playerID='BellLe00', type='RUSH', yr=2014, yards=3, yg_gtlt='lt')
r2 = GPF.GamePlayFinder(yr=2014, type='RUSH', yards=-2, yg_gtlt='lt')
r = pd.concat([r,r2])
del r2

matches = r.Detail.apply(lambda x: (x, utils.parsePlayDetails(x)))
missed = filter(lambda x: not x[1], matches)
print missed
