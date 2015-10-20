from functools import wraps
import os
import urlparse

import appdirs

__all__ = [
    'switchToDir',
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
        relURL = '{}?{}'.format(parsed.path, parsed.query)
        relURL = relURL.strip('/').replace('/', '__')
        fn = '{}/{}'.format(CACHE_DIR, relURL)

        # TODO: fix this problem?
        if len(fn) > 255:
            # filename is too long, just evaluate the function
            return func(url).encode('ascii', 'replace')
        
        # TODO: check how long since last cached
        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                text = f.read()
            return text
        else:
            text = func(url).encode('ascii', 'replace')
            with open(fn, 'w+') as f:
                f.write(text)
            return text
    
    return wrapper
