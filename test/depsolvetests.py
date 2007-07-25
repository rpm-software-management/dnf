import unittest
import settestpath

from yum import depsolve
from yum import transactioninfo
from yum import packages
from yum import packageSack


class FakeConf(object):

    def __init__(self):
        self.installonlypkgs = []


class FakeRepo(object):

    def __init__(self):
        self.id = None


class FakePackage(packages.PackageObject, packages.RpmBase):

    def __init__(self, name, version, release, epoch, arch):
        packages.PackageObject.__init__(self)
        packages.RpmBase.__init__(self)

        self.name = name
        self.version = version
        self.ver = version
        self.release = release
        self.rel = release
        self.epoch = epoch
        self.arch = arch

        self.prco['provides'].append((name, '=', (epoch, version, release)))

        self.repo = FakeRepo()
        self.repoid = None

    def addRequires(self, name, flag, evr):
        self.prco['requires'].append((name, flag, evr))


class FakeRpmDb(object):

    def __init__(self):
        self.packages = []

    def addPackage(self, po):
        self.packages.append(po)

    def whatProvides(self, name, flag, evr):
        results = []
        for package in self.packages:
            if package.checkPrco('provides', (name, flag, evr)):
                results.append(package.pkgtup)
        return results

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        # Create a match closure for what is being searched for
        lookfor = []        # A list of (search_name, search_value)
        loc = locals()
        for arg in ('name', 'arch', 'epoch', 'ver', 'rel'):
            val = loc[arg]
            if val != None:
                lookfor.append((arg, val))

        ret = []
        for package in self.packages:
            ok = True
            for name, val in lookfor:
                if getattr(package, name) != val:
                    ok = False
                    break
            if ok:
                ret.append(package)
        return ret

    def searchConflicts(self, name):
        # XXX no conflicts support for now
        return []

    def installed(self, name):
        for package in self.packages:
            if package.name == name:
                return True
        return False

class TestingDepsolve(depsolve.Depsolve):

    def getInstalledPackageObject(self, pkgtup):
        return self.rpmdb.searchNevra(pkgtup[0], pkgtup[2], pkgtup[3],
                pkgtup[4], pkgtup[1])[0]


def build_depsolver(tsInfo, rpmdb=FakeRpmDb(),
        pkgSack=packageSack.PackageSack()):
    solver = TestingDepsolve()
    solver.conf = FakeConf()
    solver.tsInfo = tsInfo
    solver.rpmdb = rpmdb
    solver.pkgSack = pkgSack
    return solver


class DepsolveTests(unittest.TestCase):

    def testInstallSinglePackageNoRequires(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')

        tsInfo = transactioninfo.TransactionData()
        tsInfo.addInstall(po)

        solver = build_depsolver(tsInfo)

        res = solver.resolveDeps()
        self.assertEquals(2, res[0])

    def testInstallSinglePackageRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))

        tsInfo = transactioninfo.TransactionData()
        tsInfo.addInstall(po)

        solver = build_depsolver(tsInfo)

        res = solver.resolveDeps()
        self.assertEquals(1, res[0])

    def testInstallSinglePackageRequireInstalled(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))

        tsInfo = transactioninfo.TransactionData()
        tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', None, 'i386')
        rpmdb = FakeRpmDb()
        rpmdb.addPackage(installedpo)

        solver = build_depsolver(tsInfo, rpmdb)

        res = solver.resolveDeps()
        self.assertEquals(2, res[0])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DepsolveTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
