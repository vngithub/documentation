import sys


def prnt(s):
    """Print a string without a newline."""
    if sys.version_info >= (3, 0):
        return print (s, end='')
    else:
        return sys.stdout.write(s)
