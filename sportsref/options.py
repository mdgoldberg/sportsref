from __future__ import print_function
OPTIONS = {
    'cache': True,
    'memoize': True,
}


def get_option(option):
    option = option.lower()
    if option in OPTIONS:
        return OPTIONS[option]
    else:
        print('option {} not recognized'.format(option))
        return None


def set_option(option, value):
    option = option.lower()
    if option in OPTIONS:
        OPTIONS[option] = value
    else:
        print('option {} not recognized'.format(option))
