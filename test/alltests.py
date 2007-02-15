import unittest
import settestpath

import packagetests


def suite():
    # Append all test suites here:
    return unittest.TestSuite((
        packagetests.suite(),
    ))

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
