import unittest
import testbase
from glob import glob
import os.path

def suite():
    files = glob(os.path.join(os.path.dirname(__file__), '*.py'))
    modules = [os.path.basename(f)[:-3] for f in files]
    suites = []

    print "Test modules:"
    for m in modules:
        if m in ('alltests', 'testbase'):
            continue
        module = __import__(m)
        if hasattr(module, 'suite'):
            print "\t%s" % m
            suites.append(module.suite())

    # Append all test suites here:
    return unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
