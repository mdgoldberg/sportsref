from functools import wraps as _wraps
import os as _os

def switchToDir(dirPath):
    """
    Decorator that switches to given directory before executing function, and
    then returning to orignal directory.
    """

    def decorator(func):
        _wraps(func)
        def wrapFunc(*args, **kwargs):
            orig_cwd = _os.getcwd()
            _os.chdir(dirPath)
            ret = func(*args, **kwargs)
            _os.chdir(orig_cwd)
            return ret
        return wrapFunc

    return decorator
