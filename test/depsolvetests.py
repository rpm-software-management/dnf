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

    def __init__(self, id=None):
        self.id = id


class FakeRpmSack(packageSack.PackageSack):
    def installed(self, name=None, arch=None, epoch=None, ver=None, rel=None, po=None):
        if po:
            name = po.name
            arch = po.arch
            epoch = po.epoch
            ver = po.version
            rel = po.release
        return len(self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)) > 0

class FakePackage(packages.PackageObject, packages.RpmBase):

    def __init__(self, name, version, release, epoch, arch, repo=None):
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

        if repo is None:
            repo = FakeRepo()
        self.repo = repo
        self.repoid = repo.id

        # Just a unique integer
        self.id = self.__hash__()

    def addProvides(self, name, evr):
        self.prco['provides'].append((name, '=', evr))
    def addRequires(self, name, flag, evr):
        self.prco['requires'].append((name, flag, evr))
    def addConflict(self, name, flag, evr):
        self.prco['conflicts'].append((name, flag, evr))
    def addObsolete(self, name, flag, evr):
        self.prco['obsoletes'].append((name, flag, evr))


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


def build_depsolver(tsInfo, rpmdb=None, pkgSack=None):
    if rpmdb is None:
        rpmdb   = packageSack.PackageSack()
    if pkgSack is None:
        pkgSack = packageSack.PackageSack()
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
        self.rpmdb  = FakeRpmSack()
        self.xsack  = packageSack.PackageSack()
        self.repo   = FakeRepo("installed")

    def FakeInstPkg(self, name, version, release, epoch, arch):
        return FakePackage(name, version, release, epoch, arch, self.repo)

    def resolveCode(self):
        solver = build_depsolver(self.tsInfo, self.rpmdb, self.xsack)
        result = solver.resolveDeps()
        res = {0 : 'empty', 2 : 'ok', 1 : 'err'}
        return (res[result[0]])

    def testEmpty(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        self.tsInfo.addInstall(po)
        self.tsInfo.remove(po.pkgtup)
        self.assertEquals('empty', self.resolveCode())

    def testInstallSinglePackageNoRequires(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        self.tsInfo.addInstall(po)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireInstalled(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireInstalledRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '2', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireInstalledRequireInstall(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)
        po = FakePackage('zap', '1', '2', None, 'i386')
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())


    def testInstallSinglePackageRequireVer1NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireVer1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireVer2NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireVer2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireVer3NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('1', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '0', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireVer3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireVer4NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireVer4_1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())
    def testInstallSinglePackageRequireVer4_2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '3', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())
    def testInstallSinglePackageRequireVer4_3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = self.FakeInstPkg('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())
    def testInstallSinglePackageRequireVer4_4Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '1', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())
    def testInstallSinglePackageRequireVer4_5Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '0.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', self.resolveCode())

    def testInstallSinglePackageRequireXtraBadVer(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        po.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zap', '1.3', '4', '0', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        po.addRequires('zap', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zap', '2.6', '8', '4', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr()
        self.assertEquals(2, len(txmbrs))
        txmbrs = self.tsInfo.matchNaevr('zap')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zap', 'i386', '4', '2.6', '8'), txmbrs[0].pkgtup)
        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(0, len(txmbrs))
        txmbrs = self.tsInfo.matchNaevr('zsh')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zsh', 'i386', None, '1', '1'), txmbrs[0].pkgtup)
        
    def testInstallSinglePackageRequireInstalledRequireXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        ipo.addRequires('zap', 'EQ', ('4', '2.6', '8'))
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zap', '2.6', '8', '4', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr()
        self.assertEquals(1, len(txmbrs))
        txmbrs = self.tsInfo.matchNaevr('zap')
        self.assertEquals(0, len(txmbrs))
        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(0, len(txmbrs))
        txmbrs = self.tsInfo.matchNaevr('zsh')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zsh', 'i386', None, '1', '1'), txmbrs[0].pkgtup)
        
    def testInstallSinglePackageRequireUpgradeRequireXtraErr(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        ipo.addRequires('zap', 'EQ', ('2', '1.3', '3'))
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zip', '2.6', '8', '4', 'i386')
        xpo.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.xsack.addPackage(xpo)
        xpo = FakePackage('zap', '1.3', '4', '2', 'i386')
        xpo.addRequires('zsh', 'EQ', ('2', '4', '8'))
        self.xsack.addPackage(xpo)

        self.assertEquals('err', self.resolveCode())

    def testInstallSinglePackageRequireUpgradeRequireXtraOk(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        ipo.addRequires('zap', 'EQ', ('2', '1.3', '3'))
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zip', '2.6', '8', '4', 'i386')
        xpo.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.xsack.addPackage(xpo)
        xpo = FakePackage('zap', '1.3', '4', '2', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr()
        self.assertEquals(4, len(txmbrs))
        
        txmbrs = self.tsInfo.matchNaevr('zap')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zap', 'i386', '2', '1.3', '4'), txmbrs[0].pkgtup)
        
        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(2, len(txmbrs))
        self.assertEquals(('zip', 'i386', '4', '2.6', '8'), txmbrs[0].pkgtup)
        self.assertEquals(txmbrs[0].ts_state, 'u')
        self.assertEquals(('zip', 'i386', '2', '1.3', '4'), txmbrs[1].pkgtup)
        self.assertEquals(txmbrs[1].ts_state, None)
        
        txmbrs = self.tsInfo.matchNaevr('zsh')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zsh', 'i386', None, '1', '1'), txmbrs[0].pkgtup)
        
    def testInstallSinglePackageRequireMultiXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '2.6', '8', '4', 'i386')
        xpo.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.xsack.addPackage(xpo)
        
        xpo = FakePackage('zap', '1.3', '4', '2', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr()
        self.assertEquals(3, len(txmbrs))
        
        txmbrs = self.tsInfo.matchNaevr('zap')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zap', 'i386', '2', '1.3', '4'), txmbrs[0].pkgtup)
        
        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zip', 'i386', '4', '2.6', '8'), txmbrs[0].pkgtup)
        
        txmbrs = self.tsInfo.matchNaevr('zsh')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zsh', 'i386', None, '1', '1'), txmbrs[0].pkgtup)
        
    def testInstallSinglePackageRequireInstalledMultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)
        
        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(0, len(txmbrs))

    def testInstallSinglePackageRequireXtra1MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zip', 'i386', None, '1', '3'), txmbrs[0].pkgtup)

    def testInstallSinglePackageRequireXtra2_64MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)
        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zip', 'x86_64', None, '1', '3'), txmbrs[0].pkgtup)

    def testInstallSinglePackageRequireXtra2_32MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)
        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zip', 'i386', None, '1', '3'), txmbrs[0].pkgtup)

    def testUpdateSinglePackage(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zsh')
        self.assertEquals(2, len(txmbrs))

    def testUpdateSinglePackageNewRequires(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addUpdate(po, oldpo=ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))
        self.assertEquals(('zip', 'x86_64', None, '1', '3'), txmbrs[0].pkgtup)

    def testUpdateSinglePackageOldRequires(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.rpmdb.addPackage(xpo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(0, len(txmbrs))

    def testUpdateSinglePackageOldRequiresGone(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.rpmdb.addPackage(xpo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', self.resolveCode())

    def testUpdateSinglePackageObsoletesOldRequirement(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        opo = FakePackage('zip', '1', '1', None, 'i386')
        self.rpmdb.addPackage(opo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        ipo.addObsolete('zip', None, (None, None, None))

        self.tsInfo.addObsoleting(po, opo)
        self.tsInfo.addObsoleted(opo, po)

        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', self.resolveCode())

        txmbrs = self.tsInfo.matchNaevr('zip')
        self.assertEquals(1, len(txmbrs))

        txmbrs = self.tsInfo.matchNaevr(name='zsh', rel='3')
        self.assertEquals(1, len(txmbrs))
        self.assertTrue('i', txmbrs[0].ts_state)

        txmbrs = self.tsInfo.matchNaevr(name='zsh', rel='1')
        self.assertEquals(1, len(txmbrs))
        self.assertTrue('e', txmbrs[0].ts_state)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DepsolveTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
