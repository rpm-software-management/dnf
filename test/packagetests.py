import unittest
import settestpath

from yum import packages

class PackageTests(unittest.TestCase):

    def testInPrcoRange(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertTrue(po.inPrcoRange('provides', ("seth", "GE", (1, 0, 0))))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PackageTests))
    return suite
                
if __name__ == "__main__":
    unittest.main(defaultTest="suite")
