from functools import wraps
import os
import time
import urlparse

import appdirs

__all__ = [
    'switchToDir',
    'cacheHTML',
]

def switchToDir(dirPath):
    """
    Decorator that switches to given directory before executing function, and
    then returning to orignal directory.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            orig_cwd = os.getcwd()
            os.chdir(dirPath)
            ret = func(*args, **kwargs)
            os.chdir(orig_cwd)
            return ret
        return wrapper

    return decorator

def cacheHTML(func):

    CACHE_DIR = appdirs.user_cache_dir('pfr', 'mgoldberg')
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    @wraps(func)
    def wrapper(url):
        parsed = urlparse.urlparse(url)
        relURL = parsed.path
        if parsed.query:
            relURL += '?' + parsed.query
        relURL = relURL.strip('/').replace('/', '__')
        fn = '{}/{}'.format(CACHE_DIR, relURL)

        # TODO: fix this problem?
        if len(fn) > 255:
            # filename is too long, just evaluate the function
            return func(url).encode('ascii', 'replace')
        
        # set time variables
        if os.path.isfile(fn):
            modtime = os.path.getmtime(fn)
            curtime = time.time()
        else:
            modtime = 0
            curtime = 0
        # if file found, read from file (not using time variables for now)
        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                text = f.read()
            return text
        # otherwise, download html and cache it
        else:
            text = func(url).encode('ascii', 'replace')
            with open(fn, 'w+') as f:
                f.write(text)
            return text
    
    return wrapper
