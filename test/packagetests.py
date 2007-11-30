import unittest
import settestpath

from yum import packages
from rpmUtils import miscutils

class InPrcoRangePackageTests(unittest.TestCase):

    def setUp(self):
        self.po = packages.RpmBase()
        self.po.rel = 10
        self.po.prco['provides'].append(("seth", "EQ", (1, 2, 3)))
        self.po.prco['requires'].append(("foo", "GE", (4, 5, None)))

    def testRequiresEqPass(self):
        dep = ("foo", "EQ", (4, 5, 0))
        self.assertTrue(self.po.inPrcoRange('requires', dep))

    def testRequiresEqFailGt(self):
        dep = ("foo", "EQ", (4, 4, 0))
        self.assertFalse(self.po.inPrcoRange('requires', dep))

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


class PackageEvrTests(unittest.TestCase):

    def setUp(self):
        self.evr = packages.PackageEVR(0, 1, 2)

    def testLtPass(self):
        other_evr = packages.PackageEVR(0, 1, 5)
        self.assertTrue(self.evr < other_evr)

    def testLtFailEq(self):
        other_evr = packages.PackageEVR(0, 1, 2)
        self.assertFalse(self.evr < other_evr)

    def testLtFailGt(self):
        other_evr = packages.PackageEVR(0, 0, 2)
        self.assertFalse(self.evr < other_evr)

    def testLePassLt(self):
        other_evr = packages.PackageEVR(0, 1, 5)
        self.assertTrue(self.evr <= other_evr)

    def testLePassEq(self):
        other_evr = packages.PackageEVR(0, 1, 2)
        self.assertTrue(self.evr <= other_evr)

    def testLeFailGt(self):
        other_evr = packages.PackageEVR(0, 0, 2)
        self.assertFalse(self.evr <= other_evr)

    def testGtPass(self):
        other_evr = packages.PackageEVR(0, 1, 0)
        self.assertTrue(self.evr > other_evr)

    def testGtFailEq(self):
        other_evr = packages.PackageEVR(0, 1, 2)
        self.assertFalse(self.evr > other_evr)

    def testGtFailLt(self):
        other_evr = packages.PackageEVR(0, 2, 2)
        self.assertFalse(self.evr > other_evr)

    def testGePassGt(self):
        other_evr = packages.PackageEVR(0, 1, 0)
        self.assertTrue(self.evr >= other_evr)

    def testGePassEq(self):
        other_evr = packages.PackageEVR(0, 1, 2)
        self.assertTrue(self.evr >= other_evr)

    def testGeFailLt(self):
        other_evr = packages.PackageEVR(2, 1, 2)
        self.assertFalse(self.evr >= other_evr)

    def testEqPass(self):
        other_evr = packages.PackageEVR(0, 1, 2)
        self.assertTrue(self.evr == other_evr)

    def testEqFailGt(self):
        other_evr = packages.PackageEVR(0, 1, 0)
        self.assertFalse(self.evr == other_evr)

    def testEqFailLt(self):
        other_evr = packages.PackageEVR(0, 4, 2)
        self.assertFalse(self.evr == other_evr)


class StubPkg(object):

    def __init__(self, n, a, e, v, r):
        self.pkgtup = (n, a, e, v, r)


class BuildPackageDictRefTests(unittest.TestCase):

    def testNoPkg(self):
        pkgs = []
        self.assertEquals({}, packages.buildPkgRefDict(pkgs))

    def testOnePkg(self):
        pkg = StubPkg("yum", "noarch", 0, "3.1.1", 2)
        pkgs = [pkg]
        pkg_dict = packages.buildPkgRefDict(pkgs)

        self.assertEquals(7, len(pkg_dict))

        unseen_keys = ['yum', 'yum.noarch', 'yum-3.1.1-2.noarch', 'yum-3.1.1',
                'yum-3.1.1-2', '0:yum-3.1.1-2.noarch', 'yum-0:3.1.1-2.noarch']
        for key in pkg_dict.keys():
            self.assertTrue(key in unseen_keys)
            unseen_keys.remove(key)
            self.assertEquals(1, len(pkg_dict[key]))
            self.assertEquals(pkg, pkg_dict[key][0])

        self.assertEquals(0, len(unseen_keys))

class RangeCompareTests(unittest.TestCase):

    def testRangeCompare(self):
        for requires, provides, result in (
            (('foo', 'EQ', ('0', '1.4.4', '0')),   ('foo', 'EQ', ('0', '1.4.4', '0')),  1),
            (('foo', 'EQ', ('0', '1.4.4', '0')),   ('foo', 'EQ', ('0', '1.4.4', None)), 1),
            (('foo', 'EQ', ('0', '1.4.4', None)),  ('foo', 'EQ', ('0', '1.4.4', '8')),  1),
            (('foo', 'LT', ('0', '1.5.4', None)),  ('foo', 'EQ', ('0', '1.4.4', '7')),  1),
            (('foo', 'GE', ('0', '1.4.4', '7.1')), ('foo', 'EQ', ('0', '1.4.4', '7')),  0),
            (('foo', 'EQ', ('0', '1.4', None)),    ('foo', 'EQ', ('0', '1.4.4', '7')),  0),
            (('foo', 'GT', ('1', '1.4.4', None)),  ('foo', 'EQ', ('3', '1.2.4', '7')),  1),
            ):
            self.assertEquals(miscutils.rangeCompare(requires, provides), result)
