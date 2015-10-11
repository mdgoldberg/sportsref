import operator as op

import pandas as pd

from pfr.finders import GamePlayFinder as GPF
from pfr import utils

r = GPF.GamePlayFinder(type='RUSH', yr=2014)

matches = r.Detail.apply(lambda x: (x, utils.parsePlayDetails(x)))
missed = filter(lambda x: not x[1], matches)
print missed
