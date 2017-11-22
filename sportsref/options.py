OPTIONS = {
    'cache': True,
}


def get_option(option):
    if option in OPTIONS:
        return OPTIONS[option]
    else:
        print('option {} not recognized'.format(option))
        return None

def set_option(option, value):
    if option in OPTIONS:
        OPTIONS[option] = value
    else:
        print('option {} not recognized'.format(option))
