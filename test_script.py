from collections import Counter
import multiprocessing as mp
import pandas as pd
from pprint import pprint
import sys

from pfr.finders import PlayerSeasonFinder, GamePlayFinder
from pfr.utils import relURLToPlayerID

psf = PlayerSeasonFinder(
    pos='rb', year_min=2013, order_by='fantasy_points_per_game',
    c1stat='rush_att', c1val=100, c1comp='gt'
)

print len(psf)

dfs = []
pIDs = []
for ps in psf:
    pURL, yr = ps
    pID = relURLToPlayerID(pURL)
    pIDs.append(pID)
    df = GamePlayFinder(player_id=pID, year_min=yr, year_max=yr, type='rush')
    dfs.append(df)

total_df = pd.concat(dfs, keys=pIDs)
total_df.to_csv('total_df.csv')
