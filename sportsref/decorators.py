import codecs
import copy
import datetime
import hashlib
import functools
import os
import re
import urlparse

import appdirs
import mementos
import numpy as np
import pandas as pd
from pyquery import PyQuery as pq

import sportsref


def switch_to_dir(dirPath):
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


def _cacheValid_pfr(ct, mt, fn):
    # TODO: this is not comprehensive, can be a problem
    # first, if we can ensure that the file won't change,
    # then we're safe caching it
    import ipdb
    ipdb.set_trace()
    if 'boxscore' in fn:
        return True
    # if it's currently the offseason, then we're good
    today = datetime.date.today()
    endOfSeason = datetime.date(today.year, 2, 18)
    startOfSeason = datetime.date(today.year, 8, 25)
    if endOfSeason < today < startOfSeason:
        return True
    # now, check for a year in the filename
    m = re.search(r'(\d{4})', fn)
    if not m:
        if 'teams' in fn:
            return True
        else:
            return False
    year = int(m.group(1))
    # if it was a year prior to the current season, we're good
    curSeason = today.year - (today <= endOfSeason)
    if year < curSeason:
        return True
    # otherwise, check if new data could have been updated since mod
    # (assumed that new game data is added the day after that game)
    modDay = today - datetime.timedelta(seconds=ct - mt)
    lastGameDay = today
    while (lastGameDay.weekday() + 1) % 7 not in (0, 1, 2, 5):
        lastGameDay = lastGameDay - datetime.timedelta(days=1)
    return modDay >= lastGameDay


def _cacheValid_bkref(ct, mt, fn):
    # TODO: this might not be comprehensive
    # first, if we can ensure that the file won't change,
    # then we're safe caching it
    if 'boxscore' in fn:
        return True
    # now, check for a year in the filename
    m = re.search(r'(\d{4})', fn)
    if not m:
        return False
    year = int(m.group(1))
    today = datetime.date.today()
    endOfSeason = datetime.date(today.year, 6, 30)
    startOfSeason = datetime.date(today.year, 9, 23)
    # if it was a year prior to the current season, we're good
    curSeason = today.year - (today <= endOfSeason)
    if year < curSeason:
        return True
    # if we're in the offseason, we're good
    if endOfSeason < today < startOfSeason:
        return True
    # otherwise, check if new data could have been updated since mod
    # (assumed that new game data is added the day after that game)
    modDay = today - datetime.timedelta(seconds=ct - mt)
    return modDay >= today


def _cacheValid_cfb(ct, mt, fn):
    # TODO: caching for CFB
    return True


def cache_html(func):
    """Caches the HTML returned by the specified function `func`. Caches it in
    the user cache determined by the appdirs package.
    """

    CACHE_DIR = appdirs.user_cache_dir('sportsref', 'mgoldberg')
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    def cacheValidFuncs(s):
        return eval('_cacheValid_' + s)

    @functools.wraps(func)
    def wrapper(url):
        parsed = urlparse.urlparse(url)
        sport = sportsref.SITE_ABBREV.get(parsed.scheme + '://' +
                                          parsed.netloc)
        if sport is None:
            for ncaaSport in ('cfb', 'cbb'):
                if ncaaSport in url:
                    sport = ncaaSport
        relURL = parsed.path
        if parsed.query:
            relURL += '?' + parsed.query
        noPathFN = re.sub(r'\.html?', '', sport + relURL.replace('/', ''))
        file_hash = hashlib.md5()
        file_hash.update(noPathFN)
        file_hash = file_hash.hexdigest()
        filename = '{}/{}'.format(CACHE_DIR, file_hash)

        # set time variables (in seconds)
        if os.path.isfile(filename):
            # curtime = int(time.time())
            # modtime = int(os.path.getmtime(filename))
            # time_since_mod = datetime.timedelta(seconds=(curtime - modtime))
            # cacheValid = time_since_mod <= datetime.timedelta(days=12)
            cacheValid = True

        # if file found and caching is valid, read from file
        if os.path.isfile(filename) and cacheValid:
            with codecs.open(filename, 'r', encoding='utf-8',
                             errors='replace') as f:
                text = f.read()
            return text
        # otherwise, download html and cache it
        else:
            text = func(url)
            with codecs.open(filename, 'w+', encoding='utf-8') as f:
                f.write(text)
            return text

    return wrapper


def get_class_instance_key(cls, args, kwargs):
    """
    Returns a unique identifier for a class instantiation.
    """
    l = [id(cls)]
    for arg in args:
        l.append(id(arg))
    l.extend((k, id(v)) for k, v in kwargs.items())
    return tuple(sorted(l))


# technically not a decorator, but it's similar enough
Cached = mementos.memento_factory('Cached', get_class_instance_key)


def memoize(fun):
    """A decorator for memoizing functions."""
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):

        # deal with lists in args
        def isList(a):
            return isinstance(a, list) or isinstance(a, np.ndarray)

        def deListify(arg):
            if isList(arg):
                return tuple(map(deListify, arg))
            else:
                return arg

        # deal with dicts in args
        def isDict(d):
            return isinstance(d, dict) or isinstance(d, pd.Series)

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

        def _copy(v):
            if isinstance(v, pq):
                return v.clone()
            else:
                return copy.deepcopy(v)

        key = (clean_args, clean_kwargs)
        try:
            ret = _copy(cache[key])
            return ret
        except KeyError:
            cache[key] = fun(*args, **kwargs)
            ret = _copy(cache[key])
            return ret
        except TypeError:
            print 'memoization type error here', fun.__name__, key
            return fun(*args, **kwargs)

    cache = {}
    return wrapper


def kind_rpb(include_type=False):
    def decorator(fun):
        """Supports functions that return a DataFrame and have a `kind` keyword
        argument that specifies regular season ('R'), playoffs ('P'), or both
        ('B'). If given 'B', it will call the function with both 'R' and 'P'
        and concatenate the results.
        """
        @functools.wraps(fun)
        def wrapper(*args, **kwargs):
            kind = kwargs.get('kind', 'R').upper()
            if kind == 'B':
                kwargs['kind'] = 'R'
                reg = fun(*args, **kwargs)
                if include_type:
                    reg['is_playoffs'] = False
                kwargs['kind'] = 'P'
                poffs = fun(*args, **kwargs)
                if include_type:
                    poffs['is_playoffs'] = True
                return pd.concat((reg, poffs), ignore_index=True)
            else:
                df = fun(*args, **kwargs)
                if include_type:
                    df['is_playoffs'] = (kind == 'P')
                return df
        return wrapper
    return decorator
