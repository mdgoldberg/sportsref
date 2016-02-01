import datetime
import math
import multiprocessing as mp
import pickle
import sys

import pandas as pd, numpy as np, matplotlib.pyplot as plt
from sklearn import preprocessing, metrics, pipeline, calibration
from sklearn import ensemble, linear_model, neural_network, neighbors, svm, naive_bayes
from sklearn.cross_validation import train_test_split
from sklearn.grid_search import GridSearchCV

import pfr

def readData(years):
    print 'reading data...'
    dfs = (pd.read_csv('{}plays.csv'.format(yr), low_memory=False)
           for yr in years)
    df = pd.concat(dfs)
    df = df.ix[~df.isError & ~df.isNoPlay & ~df.isTimeout].reset_index(drop=True)
    df['distToGoal'] = df.apply(lambda r: 2 if r.isXP else r.distToGoal,
                                axis=1)
    df.distToGoal.fillna(method='bfill', inplace=True)
    return df

def getFeatures(df):
    print 'generating features...'
    feats = pd.DataFrame(index=df.index)
    feats['pfrWP'] = df.home_wp
    feats['secsElapsed'] = df.secsElapsed
    feats['quarter'] = df.quarter.astype(int)
    homeOnOff = (df.team == df.home).astype(int).replace(0, -1)
    feats['homeOnOff'] = homeOnOff
    feats['down'] = np.where(df.down.notnull(), df.down, np.where(df.isKickoff, 0, 5)).astype(np.uint8)
    feats['yds_to_go'] = np.where(df.yds_to_go.notnull(), df.yds_to_go, np.where(df.isKickoff, 65, 2))
    feats['line'] = df.bsID.apply(lambda b: pfr.boxscores.BoxScore(b).line())
    feats['homeMargin'] = df.pbp_score_hm - df.pbp_score_aw
    feats['homeYdLine'] = np.where(df.home == df.team, df.distToGoal, 100 - df.distToGoal)
    feats['isKickoff'] = df.isKickoff
    pf = preprocessing.PolynomialFeatures(degree=3, interaction_only=False, include_bias=False)
    cols = feats.columns
    feats = pd.DataFrame(pf.fit_transform(feats), index=feats.index).astype(float)
    # set new columns after getting interaction terms
    newcols = []
    for entry in pf.powers_:
        newFeature = []
        for feat, coef in zip(cols, entry):
            if coef > 0:
                newFeature.append(feat+'^'+str(coef))
        newcols.append('_'.join(newFeature))
    feats.columns = newcols
    
    def getHomeWon(b):
        bs = pfr.boxscores.BoxScore(b)
        return bs.winner() == bs.home() if pd.notnull(bs.winner()) else None

    targets = df.bsID.apply(getHomeWon)
    ties = targets.ix[targets.isnull()].index
    df.drop(ties, inplace=True)
    feats.drop(ties, inplace=True)
    targets.drop(ties, inplace=True)
    
    return feats.astype(float), targets.astype(bool)

def fitModel(model, X, y, grid=None, fn=None):
    print 'fitting model...'
    if grid:
        gs = GridSearchCV(model, grid, refit=True, n_jobs=-1, verbose=2)
        gs.fit(X, y)
        model = gs.best_estimator_
    else:
        model.fit(X, y)

    if fn:
        with open(fn, 'wb') as f:
            pickle.dump(model, f)

    print model
    return model

def readModel(fn):
    print 'reading in model...'
    with open(fn, 'rb') as f:
        model = pickle.load(f)
    return model

def evaluateModel(model, X, y):
    print 'evaluation...'
    preds = model.predict(X)
    print 'Accuracy:', np.mean(y == preds)
    probs = model.predict_proba(X)[:, 1]
    print 'AUC score:', metrics.roc_auc_score(y, probs)
    print 'Log loss:', metrics.log_loss(y, probs)
    print 'F1 score:', metrics.f1_score(y, preds)
    return probs

# train on 02-13, predict on 14-15
traindf = readData(range(2002, 2014))
Xtrain, ytrain = getFeatures(traindf)
testdf = readData(range(2014, 2016))
Xtest, ytest = getFeatures(testdf)

# fit scaler to training data, then transform all data
scaler = preprocessing.StandardScaler()
scaler.fit(Xtrain)
Xtrain = pd.DataFrame(scaler.transform(Xtrain), index=Xtrain.index, columns=Xtrain.columns)
Xtest = pd.DataFrame(scaler.transform(Xtest), index=Xtest.index, columns=Xtest.columns)

# ----------- MODELING -----------

model = linear_model.LogisticRegression(solver='liblinear', n_jobs=-1, verbose=1, C=0.1, penalty='l1')
grid = dict(penalty=['l1', 'l2'], C=[1e-1, 1e0])

model = fitModel(model, Xtrain, ytrain)#, fn='winprob_model_v2.pkl')#, grid)

# model = readModel('winprob_model_v2.pkl')

finalProbs = evaluateModel(model, Xtest, ytest)

alldf = Xtest.copy()
alldf['homeWon'] = ytest
alldf['pfrWP'] = testdf.ix[Xtest.index, 'home_wp']
alldf['probs'] = finalProbs * 100.
alldf['absDiff'] = np.abs(ytest - finalProbs) * 100.
alldf['absPfrDiff'] = (alldf.pfrWP - alldf.probs).abs()
alldf['bucket'] = pd.cut(alldf.probs, 100, labels=False)
alldf['pfrBucket'] = pd.cut(alldf.pfrWP, 100, labels=False)

df = pd.concat((testdf, alldf), axis=1)
df['my_home_wp'] = alldf.probs
df['my_home_wpa'] = alldf.probs.diff()
for bsID in df.bsID.unique():
    subdf = df.ix[df.bsID == bsID]
    bs = pfr.boxscores.BoxScore(bsID)
    initwp = pfr.utils.initialWinProb(bs.line())
    homeWon = bs.winner() == bs.home()
    gameStart = subdf.index.min()
    gameEnd = subdf.index.max()
    df.ix[subdf.index, 'my_home_wpa'] = subdf['my_home_wpa'].shift(-1)
    df.ix[gameStart, 'home_wpa'] = subdf.ix[gameStart+1, 'my_home_wp'] - initwp
    df.ix[gameEnd, 'my_home_wpa'] = 100*homeWon - df.ix[gameEnd, 'my_home_wp']

def plotGame(df, bsID):
    game = df.ix[df.bsID == bsID]
    homeWon = game.homeWon.unique().item() * 100.
    se = np.append(game.secsElapsed.values, [game.secsElapsed.max() + 1])
    wp = np.append(game.my_home_wp.values, [homeWon])
    pfrwp = np.append(game.home_wp.values, [homeWon])
    plt.plot(se, wp, 'b')
    plt.plot(se, pfrwp, 'r')
    plt.yticks(np.arange(0, 100, 5))
    for q in np.arange(0, se.max(), 900): plt.axvline(q, c='g')

def plotProbs(inprobs, c='k', label=None, sort=False):
    if sort:
        inprobs = np.sort(inprobs)
    plt.plot(np.arange(0, 1, 1./len(inprobs)), inprobs, label=label, c=c)
    unif = np.arange(0, 1, 0.01)
    plt.plot(unif, unif, 'k', label='y=x')
    plt.legend(loc=0)
