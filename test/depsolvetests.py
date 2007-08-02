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

        # Just a unique integer
        self.id = self.__hash__()

    def addRequires(self, name, flag, evr):
        self.prco['requires'].append((name, flag, evr))


class TestingDepsolve(depsolve.Depsolve):

    def getInstalledPackageObject(self, pkgtup):
        return self.rpmdb.searchNevra(pkgtup[0], pkgtup[2], pkgtup[3],
                pkgtup[4], pkgtup[1])[0]


def build_depsolver(tsInfo, rpmdb=packageSack.PackageSack(),
        pkgSack=packageSack.PackageSack()):
    # XXX this side-affect is hacky:
    tsInfo.setDatabases(rpmdb, pkgSack)

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
        rpmdb = packageSack.PackageSack()
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
