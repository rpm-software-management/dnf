import unittest
import settestpath

from yum import packages

class InPrcoRangePackageTests(unittest.TestCase):

    def setUp(self):
        self.po = packages.RpmBase()
        self.po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))

    def testProvidesGePass(self):
        dep = ("seth", "GE", (1, 0, 0))
        self.assertTrue(self.po.inPrcoRange('provides', dep)) 

    def testProvidesGePassWithEqual(self):
        dep = ("seth", "GE", (1, 2, 3))
        self.assertTrue(self.po.inPrcoRange('provides', dep)) 

    def testProvidesGeFailOnEpoch(self):
        dep = ("seth", "GE", (2, 0, 0))
        self.assertFalse(self.po.inPrcoRange('provides', dep)) 

    def testProvidesGeFailOnVersion(self):
        dep = ("seth", "GE", (1, 3, 0))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesGeFailOnRelease(self):
        dep = ("seth", "GE", (1, 2, 4))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesGtPass(self):
        dep = ("seth", "GT", (1, 0, 0))
        self.assertTrue(self.po.inPrcoRange('provides', dep))

    def testProvidesGtFail(self):
        dep = ("seth", "GT", (1, 2, 4))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesGtFailOnEqual(self):
        dep = ("seth", "GT", (1, 2, 3))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesEqPass(self):
        dep = ("seth", "EQ", (1, 2, 3))
        self.assertTrue(self.po.inPrcoRange('provides', dep))

    def testProvidesEqFailGt(self):
        dep = ("seth", "EQ", (1, 2, 0))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesEqFailLt(self):
        dep = ("seth", "EQ", (1, 2, 4))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesLePassEq(self):
        dep = ("seth", "LE", (1, 2, 3))
        self.assertTrue(self.po.inPrcoRange('provides', dep))

    def testProvidesLePassGt(self):
        dep = ("seth", "LE", (1, 5, 2))
        self.assertTrue(self.po.inPrcoRange('provides', dep))

    def testProvidesLeFail(self):
        dep = ("seth", "LE", (0, 2, 2))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesLtPass(self):
        dep = ("seth", "LT", (1, 2, 6))
        self.assertTrue(self.po.inPrcoRange('provides', dep))

    def testProvidesLtFailEq(self):
        dep = ("seth", "LT", (1, 2, 3))
        self.assertFalse(self.po.inPrcoRange('provides', dep))

    def testProvidesLtFailGt(self):
        dep = ("seth", "LT", (1, 0, 2))
        self.assertFalse(self.po.inPrcoRange('provides', dep))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(InPrcoRangePackageTests))
    return suite
                
if __name__ == "__main__":
    unittest.main(defaultTest="suite")
