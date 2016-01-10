import collections
import datetime
import functools
import os
import time
import urlparse

import appdirs

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
            return func(url).encode('ascii', 'replace')
        
        # set time variables (in seconds)
        if os.path.isfile(fn):
            modtime = int(os.path.getmtime(fn))
            curtime = int(time.time())

        def cacheValid(ct, mt):
            today = datetime.date.today()
            endOfSeason = datetime.date(today.year, 2, 10)
            startOfSeason = datetime.date(today.year, 9, 1)
            # if we're in the offseason, don't worry about it
            if endOfSeason < today < startOfSeason:
                return True

            # otherwise, check if new data could have been updated
            # (assumed that new game data is added the day after that game)
            modDay = today - datetime.timedelta(seconds=ct-mt)
            lastGameDay = today
            while (lastGameDay.weekday() + 1) % 7 not in (0, 1, 2, 5):
                lastGameDay = lastGameDay - datetime.timedelta(days=1)
            return modDay >= lastGameDay

        # if file found and it's been <= a month, read from file
        if os.path.isfile(fn) and cacheValid(curtime, modtime):
            with open(fn, 'r') as f:
                text = f.read()
            return text
        # otherwise, download html and cache it
        else:
            text = func(url)#.encode('ascii', 'replace')
            with open(fn, 'w+') as f:
                f.write(text)
            return text
    
    return wrapper

def memoized(fun):
    """A simple memoize decorator."""
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        # TODO: deal with dicts in args
        key = (args, frozenset(sorted(kwargs.items())))
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
