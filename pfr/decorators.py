import collections
import datetime
import functools
import os
import re
import time
import urlparse

import appdirs
import numpy as np
import pandas as pd

def switchToDir(dirPath):
    """
    Decorator that switches to given directory before executing function, and
    then returning to orignal directory.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            orig_cwd = os.getcwd()
            os.chdir(dirPath)
            ret = func(*args, **kwargs)
            os.chdir(orig_cwd)
            return ret
        return wrapper

    return decorator

def cacheHTML(func):
    """Caches the HTML returned by the specified function `func`. Caches it in
    the user cache determined by the appdirs package.
    """

    CACHE_DIR = appdirs.user_cache_dir('pfr', 'mgoldberg')
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    @functools.wraps(func)
    def wrapper(url):
        parsed = urlparse.urlparse(url)
        relURL = parsed.path
        if parsed.query:
            relURL += '?' + parsed.query
        noPathFN = relURL.replace('/', '')
        fn = '{}/{}'.format(CACHE_DIR, noPathFN)

        # TODO: fix this problem?
        if len(noPathFN) > 255:
            # filename is too long, just evaluate the function
            return func(url).decode('utf-8', 'ignore')
        
        # set time variables (in seconds)
        if os.path.isfile(fn):
            modtime = int(os.path.getmtime(fn))
            curtime = int(time.time())

        def cacheValid(ct, mt, fn):
            # first, if we can ensure that the file won't change,
            # then we're safe caching it
            if 'boxscore' in fn:
                return True
            m = re.search(r'(\d{4})', fn)
            if m:
                year = int(m.group(1))
                now = datetime.datetime.now()
                curSeason = now.year - (1 if now.month <= 2 else 0)
                if year < curSeason:
                    return True

            # otherwise, check if it's currently the offseason
            today = datetime.date.today()
            endOfSeason = datetime.date(today.year, 2, 10)
            startOfSeason = datetime.date(today.year, 9, 1)
            # if we're in the offseason, don't worry about it
            if endOfSeason < today < startOfSeason:
                return True

            # otherwise, check if new data could have been updated since mod
            # (assumed that new game data is added the day after that game)
            modDay = today - datetime.timedelta(seconds=ct-mt)
            lastGameDay = today
            while (lastGameDay.weekday() + 1) % 7 not in (0, 1, 2, 5):
                lastGameDay = lastGameDay - datetime.timedelta(days=1)
            return modDay >= lastGameDay

        # if file found and caching is valid, read from file
        if os.path.isfile(fn) and cacheValid(curtime, modtime, fn):
            with open(fn, 'r') as f:
                text = f.read()
            return text
        # otherwise, download html and cache it
        else:
            text = func(url)
            with open(fn, 'w+') as f:
                f.write(text)
            return text
    
    return wrapper

def memoized(fun):
    """A simple memoize decorator."""
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):

        # deal with lists in args
        isList = lambda a: isinstance(a, list) or isinstance(a, np.ndarray)
        def deListify(arg):
            if isList(arg):
                return tuple(map(deListify, arg))
            else:
                return arg

        # deal with dicts in args
        isDict = lambda d: isinstance(d, dict) or isinstance(d, pd.Series)
        def deDictify(arg):
            if isDict(arg):
                items = dict(arg).items()
                items = [(k, deListify(deDictify(v))) for k, v in items]
                return frozenset(sorted(items))
            else:
                return arg
        
        clean_args = tuple(map(deListify, args))
        clean_args = tuple(map(deDictify, clean_args))
        clean_kwargs = deDictify(kwargs)

        key = (clean_args, clean_kwargs)
        try:
            ret = cache[key]
            return ret
        except KeyError:
            ret = cache[key] = fun(*args, **kwargs)
            return ret
        except TypeError:
            print 'memoization type error here', fun.__name__, key
            return fun(*args, **kwargs)

    cache = {}
    return wrapper

def kindRPB(fun):
    """Supports functions that return a DataFrame and have a `kind` keyword
    argument that specifies regular season ('R'), playoffs ('P'), or both
    ('B'). If given 'B', it will call the function with both 'R' and 'P' and
    concatenate the results.
    """
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        kind = kwargs.get('kind', 'R').upper()
        if kind == 'B':
            kwargs['kind'] = 'R'
            reg = fun(*args, **kwargs)
            reg['game_type'] = 'R'
            kwargs['kind'] = 'P'
            poffs = fun(*args, **kwargs)
            poffs['game_type'] = 'P'
            return pd.concat((reg, poffs), ignore_index=True)
        else:
            df = fun(*args, **kwargs)
            df['game_type'] = kind
            return df

    return wrapper
