import os.path
import sys

def dnf_toplevel():
    return os.path.normpath(os.path.join(__file__, "../../"))

toplevel = dnf_toplevel()
assert(sys.path[0] == toplevel) # nosetests ensures this
