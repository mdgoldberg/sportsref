from __future__ import print_function
from future import standard_library
standard_library.install_aliases()

import codecs
import copy
import datetime
import functools
import getpass
import hashlib
import os
import re
import time

import appdirs
from boltons import funcutils
import mementos
import pandas as pd
from pyquery import PyQuery as pq

import sportsref


# TODO: move PSFConstants and GPFConstants to appdirs cache dir
def switch_to_dir(dirPath):
    """
    Decorator that switches to given directory before executing function, and
    then returning to orignal directory.
    """

    def decorator(func):
        @funcutils.wraps(func)
        def wrapper(*args, **kwargs):
            orig_cwd = os.getcwd()
            os.chdir(dirPath)
            ret = func(*args, **kwargs)
            os.chdir(orig_cwd)
            return ret
        return wrapper

    return decorator


def _days_valid_pfr(url):
    # boxscores are static, but refresh quarterly to be sure
    if 'boxscore' in url:
        return 90
    # important dates
    today = datetime.date.today()
    start_of_season = datetime.date(today.year, 8, 15)
    end_of_season = datetime.date(today.year, 2, 15)
    # check for a year in the filename
    m = re.search(r'(\d{4})', url)
    if m:
        # if it was a year prior to the current season, we're good
        year = int(m.group(1))
        cur_season = today.year - (today <= end_of_season)
        if year < cur_season:
            return 90
    # if it's the offseason, refresh cache twice a month
    if end_of_season < today < start_of_season:
        return 15
    # otherwise, refresh every 2 days
    return 2


def _days_valid_bkref(url):
    # boxscores are static, but refresh quarterly to be sure
    if 'boxscore' in url:
        return 90
    # important dates
    today = datetime.date.today()
    start_of_season = datetime.date(today.year, 10, 1)
    end_of_season = datetime.date(today.year, 7, 1)
    # check for a year in the filename
    m = re.search(r'(\d{4})', url)
    if m:
        # if it was a year prior to the current season, we're good
        year = int(m.group(1))
        cur_season = today.year - (today <= end_of_season) + 1
        if year < cur_season:
            return 90
    # if it's the offseason, refresh cache once a month
    if end_of_season < today < start_of_season:
        return 30
    # otherwise, refresh every 2 days
    return 2


def _days_valid_cfb(url):
    # TODO: caching for CFB
    return 365


def cache(func):
    """Caches the HTML returned by the specified function `func`. Caches it in
    the user cache determined by the appdirs package.
    """

    CACHE_DIR = appdirs.user_cache_dir('sportsref', getpass.getuser())
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    @funcutils.wraps(func)
    def wrapper(url):
        # hash based on the URL
        file_hash = hashlib.md5()
        encoded_url = url.encode(errors='replace')
        file_hash.update(encoded_url)
        file_hash = file_hash.hexdigest()
        filename = '{}/{}'.format(CACHE_DIR, file_hash)

        sport_id = None
        for a_base_url, a_sport_id in sportsref.SITE_ABBREV.items():
            if url.startswith(a_base_url):
                sport_id = a_sport_id
                break
        else:
            print('No sport ID found for {}, not able to check cache'.format(url))

        # check whether cache is valid or stale
        file_exists = os.path.isfile(filename)
        if sport_id and file_exists:
            cur_time = int(time.time())
            mod_time = int(os.path.getmtime(filename))
            days_since_mod = datetime.timedelta(seconds=(cur_time - mod_time)).days
            days_cache_valid = globals()['_days_valid_{}'.format(sport_id)](url)
            cache_is_valid = days_since_mod < days_cache_valid
        else:
            cache_is_valid = False

        # if file found and cache is valid, read from file
        allow_caching = sportsref.get_option('cache')
        if file_exists and cache_is_valid and allow_caching:
            with codecs.open(filename, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        # otherwise, execute function and cache results
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


# used as a metaclass for classes that should be memoized
# (technically not a decorator, but it's similar enough)
Cached = mementos.memento_factory('Cached', get_class_instance_key)


def memoize(fun):
    """A decorator for memoizing functions.

    Only works on functions that take simple arguments - arguments that take
    list-like or dict-like arguments will not be memoized, and this function
    will raise a TypeError.
    """
    @funcutils.wraps(fun)
    def wrapper(*args, **kwargs):

        do_memoization = sportsref.get_option('memoize')
        if not do_memoization:
            return fun(*args, **kwargs)

        hash_args = tuple(args)
        hash_kwargs = frozenset(sorted(kwargs.items()))
        key = (hash_args, hash_kwargs)

        def _copy(v):
            if isinstance(v, pq):
                return v.clone()
            else:
                return copy.deepcopy(v)

        try:
            ret = _copy(cache[key])
            return ret
        except KeyError:
            cache[key] = fun(*args, **kwargs)
            ret = _copy(cache[key])
            return ret
        except TypeError:
            print('memoization type error in function {} for arguments {}'
                  .format(fun.__name__, key))
            raise

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
