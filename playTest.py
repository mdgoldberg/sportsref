import operator as op

import pandas as pd

from pfr.finders import GPF
from pfr import utils

p = GPF.GamePlayFinder(type='PASS', yr=2014, order_by='game_date')
r = GPF.GamePlayFinder(type='RUSH', yr=2014, order_by='game_date')

plays = pd.concat([p,r])

matches = pd.DataFrame(map(utils.parsePlayDetails, plays.Detail))
