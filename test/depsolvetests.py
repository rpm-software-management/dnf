import unittest
import testbase

from yum import YumBase
from yum import transactioninfo
from yum import packages
from yum import packageSack
from yum.constants import TS_INSTALL_STATES, TS_REMOVE_STATES

class FakeConf(object):

    def __init__(self):
        self.installonlypkgs = []
        self.exclude = []
        self.debuglevel = 0
        self.obsoletes = True
        self.exactarch = False
        self.exactarchlist = []
        self.installroot = '/'
        self.tsflags = []
        self.installonly_limit = 0

class FakeRepo(object):

    def __init__(self, id=None):
        self.id = id

class FakePackage(packages.YumAvailablePackage):

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

        self.prco['provides'].append((name, 'EQ', (epoch, version, release)))

        if repo is None:
            repo = FakeRepo()
        self.repo = repo
        self.repoid = repo.id

        # Just a unique integer
        self.id = self.__hash__()

    def addProvides(self, name, flag=None, evr=(None, None, None)):
        self.prco['provides'].append((name, flag, evr))
    def addRequires(self, name, flag=None, evr=(None, None, None)):
        self.prco['requires'].append((name, flag, evr))
    def addConflicts(self, name, flag=None, evr=(None, None, None)):
        self.prco['conflicts'].append((name, flag, evr))
    def addObsoletes(self, name, flag=None, evr=(None, None, None)):
        self.prco['obsoletes'].append((name, flag, evr))
    def addFile(self, name, ftype='file'):
        self.files[ftype].append(name)


class TestingDepsolve(YumBase):

    def __init__(self, tsInfo, rpmdb, pkgSack):
        YumBase.__init__(self)

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
        self.rpmdb  = packageSack.PackageSack()
        self.xsack  = packageSack.PackageSack()
        self.repo   = FakeRepo("installed")

    def FakeInstPkg(self, name, version, release, epoch, arch):
        return FakePackage(name, version, release, epoch, arch, self.repo)

    def resolveCode(self):
        solver = build_depsolver(self.tsInfo, self.rpmdb, self.xsack)
        result = solver.resolveDeps()
        res = {0 : 'empty', 2 : 'ok', 1 : 'err'}
        return (res[result[0]], result[1])

    def assertResult(self, pkgs, optional_pkgs=[], check_multilib_versions=True):
        errors = ["assertResult:\n"]
        pkgs = set(pkgs)
        optional_pkgs = set(optional_pkgs)
        installed = set()

        for pkg in self.rpmdb:
            # got removed
            if self.tsInfo.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES):
                if pkg in pkgs:
                    errors.append("Package %s got removed!\n" % pkg)
            else: # still installed
                installed.add(pkg)
                if pkg not in pkgs and pkg not in optional_pkgs:
                    errors.append("Package %s didn't got removed!\n" % pkg)

        for txmbr in self.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            installed.add(txmbr.po)
            if txmbr.po not in pkgs and txmbr.po not in optional_pkgs:
                errors.append("Package %s got installed!\n" % txmbr.po)
        for pkg in pkgs - installed:
            errors.append("Package %s didn't got installed!\n" % pkg)

        if len(errors) > 1:
            self.fail("".join(errors))

    def testEmpty(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        self.tsInfo.addInstall(po)
        self.tsInfo.remove(po.pkgtup)
        self.assertEquals('empty', *self.resolveCode())

    def testInstallSinglePackageNoRequires(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        self.tsInfo.addInstall(po)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po,))

    def testInstallSinglePackageRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireInstalled(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireInstalledRequireNotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '2', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireInstalledRequireInstall(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)
        po2 = FakePackage('zap', '1', '2', None, 'i386')
        self.tsInfo.addInstall(po2)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        po.addRequires('zap', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, po2, ipo))


    def testInstallSinglePackageRequireVer1NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireVer1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireVer2NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireVer2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireVer3NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('1', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '0', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireVer3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'GE', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireVer4NotProvided(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireVer4_1Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.0', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))
    def testInstallSinglePackageRequireVer4_2Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '3', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))
    def testInstallSinglePackageRequireVer4_3Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = self.FakeInstPkg('zip', '1.3', '4', None, 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))
    def testInstallSinglePackageRequireVer4_4Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '1', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))
    def testInstallSinglePackageRequireVer4_5Installed(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'LT', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '0.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireXtraBadVer(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        po.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zap', '1.3', '4', '0', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('err', *self.resolveCode())

    def testInstallSinglePackageRequireXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        po.addRequires('zap', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zap', '2.6', '8', '4', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo, xpo))
        
    def testInstallSinglePackageRequireInstalledRequireXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('2', '1.3', '4'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '4', '2', 'i386')
        ipo.addRequires('zap', 'EQ', ('4', '2.6', '8'))
        self.rpmdb.addPackage(ipo)
        
        xpo = FakePackage('zap', '2.6', '8', '4', 'i386')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))
        
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

        self.assertEquals('err', *self.resolveCode())

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
        xpo2 = FakePackage('zap', '1.3', '4', '2', 'i386')
        self.xsack.addPackage(xpo2)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo, xpo2))
        
    def testInstallSinglePackageRequireMultiXtra(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', ('4', '2.6', '8'))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '2.6', '8', '4', 'i386')
        xpo.addRequires('zap', 'EQ', ('2', '1.3', '4'))
        self.xsack.addPackage(xpo)
        
        xpo2 = FakePackage('zap', '1.3', '4', '2', 'i386')
        self.xsack.addPackage(xpo2)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo, xpo2))
        
    def testInstallSinglePackageRequireInstalledMultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1', '3', None, 'i386')
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)
        
        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, ipo))

    def testInstallSinglePackageRequireXtra1MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)
        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo))

    def testInstallSinglePackageRequireXtra2_64MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'x86_64')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)
        xpo64 = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo64)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo64))

    def testInstallSinglePackageRequireXtra2_32MultiLib(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('zip', '1', '3', None, 'i386')
        self.xsack.addPackage(xpo)
        xpo64 = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo64)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo))

    def testUpdateSinglePackage(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po,))

    def testUpdateForDependency(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        po.addRequires('zip', 'EQ', ('0', '2', '1'))
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        self.xsack.addPackage(updatepo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, updatepo))

    def testUpdateSplitPackage(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        po.addRequires('libzip', 'EQ', ('0', '2', '1'))
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        installedpo.addProvides('libzip', 'EQ', ('0', '1', '1'))
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        updatepo.addRequires('zip-libs', 'EQ', ('0', '2', '1'))
        self.xsack.addPackage(updatepo)
        updatepo2 = FakePackage('zip-libs', '2', '1', '0', 'i386')
        updatepo2.addProvides('libzip', 'EQ', ('0', '2', '1'))
        self.xsack.addPackage(updatepo2)

        self.assertEquals('ok', *self.resolveCode())
        #self.assertResult((po, updatepo, updatepo2)) # XXX obsolete needed?
        self.assertResult((po, installedpo, updatepo2))

    def testUpdateSinglePackageNewRequires(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        self.rpmdb.addPackage(ipo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addUpdate(po, oldpo=ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.xsack.addPackage(xpo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo))

    def testUpdateSinglePackageOldRequires(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.rpmdb.addPackage(xpo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        po.addRequires('zip', None, (None, None, None))
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo))

    def testUpdateSinglePackageOldRequiresGone(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('zip', '1', '3', None, 'x86_64')
        self.rpmdb.addPackage(xpo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, xpo))

    def testUpdateSinglePackageObsoletesOldRequirement(self):
        ipo = self.FakeInstPkg('zsh', '1', '1', None, 'i386')
        ipo.addRequires('zip', None, (None, None, None))
        self.rpmdb.addPackage(ipo)

        opo = FakePackage('zip', '1', '1', None, 'i386')
        self.rpmdb.addPackage(opo)

        po = FakePackage('zsh', '1', '3', None, 'i386')
        ipo.addObsoletes('zip', None, (None, None, None))

        self.tsInfo.addUpdate(po, oldpo=ipo)

        self.tsInfo.addObsoleting(po, opo)
        self.tsInfo.addObsoleted(opo, po)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po,))

    def testUpdateForConflict(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        po.addConflicts('zip', 'LE', ('0', '1', '1'))
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        self.xsack.addPackage(updatepo)

        if testbase.new_behavior:
            self.assertEquals('ok', *self.resolveCode())
            self.assertResult((po, updatepo))
        else:
            self.assertEquals('err', *self.resolveCode())

    def testUpdateForConflict2(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        installedpo.addConflicts('zsh', 'LE', ('0', '1', '1'))
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        self.xsack.addPackage(updatepo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, updatepo))

    def testUpdateForConflictProvide(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        po.addConflicts('zippy', 'LE', ('0', '1', '1'))
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        installedpo.addProvides('zippy', 'EQ', ('0', '1', '1'))
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        self.xsack.addPackage(updatepo)

        if testbase.new_behavior:
            self.assertEquals('ok', *self.resolveCode())
            self.assertResult((po, updatepo))
        else:
            self.assertEquals('err', *self.resolveCode())

    def testUpdateForConflictProvide2(self):
        po = FakePackage('zsh', '1', '1', '0', 'i386')
        po.addProvides('zippy', 'EQ', ('0', '2', '1'))
        self.tsInfo.addInstall(po)

        installedpo = FakePackage('zip', '1', '1', '0', 'i386')
        installedpo.addConflicts('zippy', 'GT', ('0', '1', '1'))
        installedpo.addConflicts('zippy', 'LT', ('0', '1', '1'))
        self.rpmdb.addPackage(installedpo)

        updatepo = FakePackage('zip', '2', '1', '0', 'i386')
        updatepo.addConflicts('zippy', 'GT', ('0', '2', '1'))
        updatepo.addConflicts('zippy', 'LT', ('0', '2', '1'))
        self.xsack.addPackage(updatepo)

        self.assertEquals('ok', *self.resolveCode())
        self.assertResult((po, updatepo))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DepsolveTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")
