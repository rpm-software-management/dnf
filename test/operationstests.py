import unittest

from depsolvetests import FakePackage, FakeRepo, FakeConf
from yum.constants import TS_INSTALL_STATES, TS_REMOVE_STATES
from cli import YumBaseCli
from yum import packageSack

class Container(object):
    pass

class OperationsTests(unittest.TestCase):

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self.pkgs = Container()
        # installed
        self.pkgs.ii386 = FakePackage('zsh', '1', '1', '0', 'i386')
        self.pkgs.ix86_64 = FakePackage('zsh', '1', '1', '0', 'x86_64')
        self.pkgs.inoarch = FakePackage('zsh', '1', '1', '0', 'noarch')
        # updates
        self.pkgs.ui386 = FakePackage('zsh', '2', '1', '0', 'i386')
        self.pkgs.ux86_64 = FakePackage('zsh', '2', '1', '0', 'x86_64')
        self.pkgs.unoarch = FakePackage('zsh', '2', '1', '0', 'noarch')
        # requires update
        self.pkgs.ru = FakePackage('zsh-utils', '2', '1', '0', 'noarch')
        self.pkgs.ru.addRequires('zsh', 'EQ', ('0', '2', '1'))
        # obsoletes
        self.pkgs.oi386 = FakePackage('zsh-ng', '0.3', '1', '0', 'i386')
        self.pkgs.oi386.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.oi386.addProvides('zzz')
        self.pkgs.ox86_64 = FakePackage('zsh-ng', '0.3', '1', '0', 'x86_64')
        self.pkgs.ox86_64.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.ox86_64.addProvides('zzz')
        self.pkgs.onoarch = FakePackage('zsh-ng', '0.3', '1', '0', 'noarch')
        self.pkgs.onoarch.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.onoarch.addProvides('zzz')
        # requires obsoletes
        self.pkgs.ro = FakePackage('superzippy', '3.5', '3', '0', 'noarch')
        self.pkgs.ro.addRequires('zzz')
        # conflicts
        self.pkgs.conflict = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        self.pkgs.conflict.addConflicts('zsh', 'EQ', ('0', '1', '1'))


    def runOperation(self, args, installed=[], available=[]):
        depsolver = YumBaseCli()
        depsolver.rpmdb  = packageSack.PackageSack()
        depsolver._pkgSack  = packageSack.PackageSack()
        depsolver.repo = FakeRepo("installed")
        depsolver.conf = FakeConf()
        depsolver.doLoggingSetup(-1, -1)
        self.depsolver = depsolver

        for po in installed:
            po.repoid = po.repo.id = "installed"
            self.depsolver.rpmdb.addPackage(po)
        for po in available:
            self.depsolver._pkgSack.addPackage(po)

        self.depsolver.basecmd = args[0]
        self.depsolver.extcmds = args[1:]
        res, msg = self.depsolver.doCommands()
        if res!=2:
            return res, msg
        return self.depsolver.buildTransaction()

    def assertResult(self, pkgs, optional_pkgs=[], check_multilib_versions=True):
        errors = ["assertResult:\n"]
        pkgs = set(pkgs)
        optional_pkgs = set(optional_pkgs)
        installed = set()

        for pkg in self.depsolver.rpmdb:
            # got removed
            if self.depsolver.tsInfo.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES):
                if pkg in pkgs:
                    errors.append("Package %s got removed!\n" % pkg)
            else: # still installed
                installed.add(pkg)
                if pkg not in pkgs and pkg not in optional_pkgs:
                    errors.append("Package %s didn't got removed!\n" % pkg)

        for txmbr in self.depsolver.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            installed.add(txmbr.po)
            if txmbr.po not in pkgs and txmbr.po not in optional_pkgs:
                errors.append("Package %s got installed!\n" % txmbr.po)
        for pkg in pkgs - installed:
            errors.append("Package %s didn't got installed!\n" % pkg)

        if len(errors) > 1:
            self.fail("".join(errors))

    #######################################################################
    ### Tests #############################################################
    #######################################################################

    def testUpdatei386ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.ui386,))
    def testUpdatei386ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        self.assertResult((p.ii386, p.ux86_64, p.ru))
        #self.assertResult((p.ui386, p.ru))

    def testUpdatex86_64ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ix86_64], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.ux86_64,))
    def testUpdatex86_64ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ix86_64], 
                                     [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        self.assertResult((p.ux86_64, p.ru))

    def testUpdateMultilibToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.ui386, p.ux86_64))
    def testUpdateMultilibToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386, p.ix86_64], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        #self.assertResult((p.ui386, p.ux86_64,  p.ru))
        self.assertResult((p.ii386, p.ux86_64,  p.ru))

    def testUpdatei386Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.unoarch])
        self.assert_(res==2, msg)
        self.assertResult((p.unoarch,))
    def testUpdatei386TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386], [p.unoarch, p.ru])
        self.assert_(res==2, msg)
        #self.assertResult((p.unoarch, p.ru))
        self.assertResult((p.ii386, p.unoarch, p.ru))

    def testUpdateMultilibTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.unoarch])
        self.assert_(res==2, msg)
        #self.assertResult((p.unoarch,))
        self.assertResult((p.unoarch, p.ix86_64))
    def testUpdateMultilibTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386, p.ix86_64], [p.unoarch, p.ru])
        self.assert_(res==2, msg)
        #self.assertResult((p.unoarch, p.ru))
        self.assertResult((p.ii386, p.ix86_64, p.unoarch, p.ru))

    def testUpdatenoarchToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.inoarch], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.ui386, p.ux86_64))
        # self.assertResult((p.ux86_64)) # ???
    def testUpdatenoarchToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.inoarch], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        # self.assertResult((p.ui386, p.ux86_64, p.ru))
        # self.assertResult((p.ux86_64, p.ru))
        self.assertResult((p.inoarch, p.ux86_64, p.ru))

    # obsoletes

    def testObsoletenoarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.inoarch], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        #self.assertResult((p.ox86_64,))
        self.assertResult((p.oi386, p.ox86_64))
    def testObsoletenoarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.inoarch], 
                                     [p.oi386, p.ox86_64, p.ro])
        self.assert_(res==2, msg)
        #self.assertResult((p.ox86_64, p.ro))
        self.assertResult((p.inoarch, p.ox86_64, p.ro))

    def testObsoletei386ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.oi386,))
    def testObsoletei386ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.ii386], [p.oi386, p.ox86_64, p.ro])
        self.assert_(res==2, msg)
        #self.assertResult((p.ox86_64, p.ro))
        self.assertResult((p.ii386, p.ox86_64, p.ro))

    def testObsoletex86_64ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ix86_64], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.ox86_64,))
    def testObsoletex86_64ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.ix86_64], [p.oi386, p.ox86_64, p.ro])
        self.assert_(res==2, msg)
        #self.assertResult((p.ox86_64, p.ro))
        self.assertResult((p.ix86_64, p.ox86_64, p.ro))

    def testObsoleteMultiarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.oi386, p.ox86_64))
    def testObsoleteMultiarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.ii386, p.ix86_64], [p.oi386, p.ox86_64, p.ro])
        self.assert_(res==2, msg)
        #self.assertResult((p.oi386, p.ox86_64, p.ro))
        self.assertResult((p.ii386, p.ix86_64, p.ox86_64, p.ro))

    def testObsoleteMultiarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.onoarch])
        self.assert_(res==2, msg)
        self.assertResult((p.onoarch,))
    def testObsoleteMultiarchTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.ii386, p.ix86_64], [p.onoarch, p.ro])
        self.assert_(res==2, msg)
        #self.assertResult((p.onoarch, p.ro))
        self.assertResult((p.ii386, p.ix86_64, p.onoarch, p.ro))

    # Obsolete for conflict

    def _XXX_testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.ii386], [p.oi386, p.ox86_64, p.conflict])
        self.assert_(res==2, msg)
        self.assertResult((p.oi386, p.conflict))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OperationsTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

