import unittest
import settestpath

import depsolvetests
import packagetests
import operationstests

def suite():
    # Append all test suites here:
    return unittest.TestSuite((
        depsolvetests.suite(),
        operationstests.suite(),
        packagetests.suite(),
    ))

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
