import unittest
import settestpath

from yum import packages
from rpmUtils import miscutils

class InPrcoRangePackageTests(unittest.TestCase):

    def setUp(self):
        self.po = packages.RpmBase()
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

def _perms(evr): # Magic comp. sci. stuff ... oooh
    e, v, r = evr
    for num in range(8):
        perm = []
        if num & 1:
            perm.append(e)
        else:
            perm.append(None)
        if num & 2:
            perm.append(v)
        else:
            perm.append(None)
        if num & 4:
            perm.append(r)
        else:
            perm.append(None)
        yield tuple(perm)

class RangeCompareTests(unittest.TestCase):

    def testRangeCompare(self):
        def tst(requires, provides, result):
            print requires, provides
            self.assertEquals(miscutils.rangeCompare(requires, provides),result)
        def tst_lege_prov(requires, provides, result):
            if not result or provides[1] != 'EQ':
                return
            for flag in ('GE', 'LE'): # EQ is a subset of either LE or GE
                nprovides = (provides[0], flag, provides[2])
                tst(requires, nprovides, result)
        def tst_lege_reqs(requires, provides, result):
            tst_lege_prov(requires, provides, result)
            if not result or requires[1] != 'EQ':
                return
            for flag in ('GE', 'LE'): # EQ is a subset of either LE or GE
                nrequires = (requires[0], flag, requires[2])
                tst(nrequires, provides, result)
                tst_lege_prov(nrequires, provides, result)
        def tst_none_reqs(requires, provides, result):
            if (not result or requires[1] or provides[1] != 'EQ' or
                requires[2] != (None, None, None)):
                return
            tst_lege_prov(requires, provides, result)
            # Doesn't matter about versions
            for flag in ('GE', 'EQ', 'LE'):
                nrequires = (requires[0], flag, requires[2])
                tst(nrequires, provides, result)
                tst_lege_prov(nrequires, provides, result)
        def tst_none_expand(requires, provides, result, *args):
            if requires[2] != (None, None, None):
                return
            # Expand parts of the version, replacing with data from provides.
            # Eg. (None, None, None) and ('1', '2', '3') becomes:
            #     (None, None, None)
            #     ('1',  None,  None)
            #     (None,  '2',  None)
            #     (None, None,  '3')
            #     ('1',   '2',  None)
            #     ...
            #     ('1',   '2',   '3')

            for evr in _perms(provides[2]):
                nrequires = (requires[0], requires[1], evr)
                for func in args:
                    func(nrequires, provides, result)

        for requires, provides, result in (
            (('foo', 'EQ', ('0', '1.4.4', '0')),   ('foo', 'EQ', ('0', '1.4.4', '0')),  1),
            (('foo', 'EQ', ('0', '1.4.4', '0')),   ('foo', 'EQ', (None, '1.4.4', '0')), 1),
            (('foo', 'EQ', ('0', '1.4.4', '0')),   ('foo', 'EQ', ('0', '1.4.4', None)), 1),
            (('foo', 'EQ', ('0', '1.4.4', None)),  ('foo', 'EQ', ('0', '1.4.4', '8')),  1),
            (('foo', 'LT', ('0', '1.5.4', None)),  ('foo', 'EQ', ('0', '1.4.4', '7')),  1),
            (('foo', 'GE', ('0', '1.4.4', '7.1')), ('foo', 'EQ', ('0', '1.4.4', '7')),  0),
            (('foo', 'EQ', ('0', '1.4', None)),    ('foo', 'EQ', ('0', '1.4.4', '7')),  0),
            (('foo', 'GT', ('1', '1.4.4', None)),  ('foo', 'EQ', ('3', '1.2.4', '7')),  1),
            (('foo', None, (None, None, None)),    ('foo', 'EQ', ('3', '1.2.4', '7')),  1),
            (('fuu', None, (None, None, None)),    ('foo', 'EQ', ('3', '1.2.4', '7')),  0),
            (('foo', None, (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  1),

            (('foo', 'EQ', (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  0),
            (('foo', 'LT', (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  0),
            (('foo', 'LE', (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  0),
            (('foo', 'GE', (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  1),
            (('foo', 'GT', (None, None, None)),    ('foo', 'GT', ('3', '1.2.4', '7')),  1),

            (('foo', 'EQ', (None, None, None)),    ('foo', 'LT', ('3', '1.2.4', '7')),  0),
            (('foo', 'LT', (None, None, None)),    ('foo', 'LT', ('3', '1.2.4', '7')),  1),
            (('foo', 'LE', (None, None, None)),    ('foo', 'LT', ('3', '1.2.4', '7')),  1),
            (('foo', 'GE', (None, None, None)),    ('foo', 'LT', ('3', '1.2.4', '7')),  0),
            (('foo', 'GT', (None, None, None)),    ('foo', 'LT', ('3', '1.2.4', '7')),  0),
            ):

            tst(requires, provides, result)

            tst_lege_reqs(requires, provides, result)
            tst_none_expand(requires, provides, result,
                            tst, tst_lege_reqs, tst_none_reqs)
