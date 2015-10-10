from pfr.finders import GamePlayFinder as GPF

r = GPF.GamePlayFinder(playerID='SpilC.00', yr=2014, yards=1, yd_gtlt='lt')
r2 = GPF.GamePlayFinder(yr=2014, yards=-1, yd_gtlt='lt')
r = pd.concat([r,r2])
del r2

