from functools import wraps
import os

def switchToDir(dirPath):
    """
    Decorator that switches to given directory before executing function, and
    then returning to orignal directory.
    """

    def decorator(func):
        @wraps(func)
        def wrapFunc(*args, **kwargs):
            orig_cwd = os.getcwd()
            os.chdir(dirPath)
            ret = func(*args, **kwargs)
            os.chdir(orig_cwd)
            return ret
        return wrapFunc

    return decorator
