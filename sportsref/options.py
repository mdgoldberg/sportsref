OPTIONS = {"cache": True, "memoize": True}


def get_option(option):
    option = option.lower()
    if option in OPTIONS:
        return OPTIONS[option]
    else:
        # TODO: log
        print(f"option {option} not recognized")
        return None


def set_option(option, value):
    option = option.lower()
    if option in OPTIONS:
        OPTIONS[option] = value
    else:
        # TODO: log
        print("option {option} not recognized")
