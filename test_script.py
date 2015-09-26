from collections import Counter
import multiprocessing as mp
import pandas as pd
from pprint import pprint
import sys

from pfr import utils
from pfr.finders import PlayerSeasonFinder as PSF
from pfr.finders import GamePlayFinder as GPF

# RBs with >= 100 rushes since 2010
psf = PSF.PlayerSeasonFinder(
    pos='rb', year_min=2010, order_by='rush_att',
    c1stat='rush_att', c1val=100, c1comp='gt', verbose=True
)

print len(psf)

dfs = []
pURLs = []
for ps in psf:
    print ps
    pURL, yr = ps
    pURLs.append(pURL)
    df = GPF.GamePlayFinder(player_id=pURL, year=yr, type='rush')
    dfs.append(df)

total_df = pd.concat(dfs)
total_df.to_csv('total_df.csv', index=False)
