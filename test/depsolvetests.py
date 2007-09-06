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

    def __init__(self, tsInfo, rpmdb, pkgSack):
        depsolve.Depsolve.__init__(self)

        self.conf = FakeConf()
        self.tsInfo = tsInfo
        self._tsInfo = tsInfo
        self.rpmdb = rpmdb
        self.pkgSack = pkgSack

    def getInstalledPackageObject(self, pkgtup):
        return self.rpmdb.searchNevra(pkgtup[0], pkgtup[2], pkgtup[3],
                pkgtup[4], pkgtup[1])[0]


def build_depsolver(tsInfo, rpmdb=packageSack.PackageSack(),
        pkgSack=packageSack.PackageSack()):
    # XXX this side-affect is hacky:
    tsInfo.setDatabases(rpmdb, pkgSack)

    solver = TestingDepsolve(tsInfo, rpmdb, pkgSack)
    return solver


class DepsolveTests(unittest.TestCase):

    tsInfo = None
    rpmdb  = None
    def setUp(self):
        """ Called at the start of each test. """
        self.tsInfo = transactioninfo.TransactionData()
        self.rpmdb  = packageSack.PackageSack()

    def resolveCode(self, *args):
        solver = build_depsolver(*args)
        result = solver.resolveDeps()
        res = {2 : 'ok', 1 : 'err'}
        return (res[result[0]])

    def testInstallSinglePackageNoRequires(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        self.tsInfo.addInstall(po)

        self.assertEquals('ok', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        self.assertEquals('err', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireInstalled(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireInstalledRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '2', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('err', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireInstalledRequireInstall(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)
        po = FakePackage('zap', '1', '2', None, 'i386')
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))


    def testInstallSinglePackageRequireVer1NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireVer1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireVer2NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireVer2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireVer3NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('1', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '0', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireVer3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireVer4NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode(self.tsInfo))

    def testInstallSinglePackageRequireVer4_1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))
    def testInstallSinglePackageRequireVer4_2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '3', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))
    def testInstallSinglePackageRequireVer4_3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))
    def testInstallSinglePackageRequireVer4_4Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '1', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))
    def testInstallSinglePackageRequireVer4_5Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '0.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireNotProvidedMultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        self.rpmdb.addPackage(ipo)

        # self.assertEquals('err', self.resolveCode(self.tsInfo, self.rpmdb))

    def testInstallSinglePackageRequireInstalledMultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        self.rpmdb.addPackage(ipo)
        ipo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode(self.tsInfo, self.rpmdb))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DepsolveTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
