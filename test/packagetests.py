import unittest
import settestpath

from yum import packages

class InPrcoRangePackageTests(unittest.TestCase):

    def testProvidesGePass(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertTrue(po.inPrcoRange('provides', ("seth", "GE", (1, 0, 0))))

    def testProvidesGePassWithEqual(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertTrue(po.inPrcoRange('provides', ("seth", "GE", (1, 2, 3))))

    def testProvidesGeFailOnEpoch(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "GE", (2, 0, 0))))

    def testProvidesGeFailOnVersion(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "GE", (1, 3, 0))))

    def testProvidesGeFailOnRelease(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "GE", (1, 2, 4))))

    def testProvidesGtPass(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertTrue(po.inPrcoRange('provides', ("seth", "GT", (1, 0, 0))))

    def testProvidesGtFail(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "GT", (1, 2, 4))))

    def testProvidesGtFailOnEqual(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "GT", (1, 2, 3))))

    def testProvidesEqPass(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.assertTrue(po.inPrcoRange('provides', ("seth", "EQ", (1, 2, 3))))

    def testProvidesEqFailGt(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 8)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "EQ", (1, 2, 3))))

    def testProvidesEqFailLt(self):
        po = packages.RpmBase()
        po.prco['provides'].append(("seth", "EQ", (1, 2, 2)))
        self.assertFalse(po.inPrcoRange('provides', ("seth", "EQ", (1, 2, 3))))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(InPrcoRangePackageTests))
    return suite
                
if __name__ == "__main__":
    unittest.main(defaultTest="suite")
