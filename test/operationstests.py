import unittest
import testbase

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
        self.pkgs.installed_i386 = FakePackage('zsh', '1', '1', '0', 'i386')
        self.pkgs.installed_x86_64 = FakePackage('zsh', '1', '1', '0', 'x86_64')
        self.pkgs.installed_noarch = FakePackage('zsh', '1', '1', '0', 'noarch')
        # updates
        self.pkgs.update_i386 = FakePackage('zsh', '2', '1', '0', 'i386')
        self.pkgs.update_x86_64 = FakePackage('zsh', '2', '1', '0', 'x86_64')
        self.pkgs.update_noarch = FakePackage('zsh', '2', '1', '0', 'noarch')
        # requires update
        self.pkgs.requires_update = FakePackage('zsh-utils', '2', '1', '0', 'noarch')
        self.pkgs.requires_update.addRequires('zsh', 'EQ', ('0', '2', '1'))
        # obsoletes
        self.pkgs.obsoletes_i386 = FakePackage('zsh-ng', '0.3', '1', '0', 'i386')
        self.pkgs.obsoletes_i386.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.obsoletes_i386.addProvides('zzz')
        self.pkgs.obsoletes_x86_64 = FakePackage('zsh-ng', '0.3', '1', '0', 'x86_64')
        self.pkgs.obsoletes_x86_64.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.obsoletes_x86_64.addProvides('zzz')
        self.pkgs.obsoletes_noarch = FakePackage('zsh-ng', '0.3', '1', '0', 'noarch')
        self.pkgs.obsoletes_noarch.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.obsoletes_noarch.addProvides('zzz')
        # requires obsoletes
        self.pkgs.requires_obsoletes = FakePackage('superzippy', '3.5', '3', '0', 'noarch')
        self.pkgs.requires_obsoletes.addRequires('zzz')
        # conflicts
        self.pkgs.conflicts = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        self.pkgs.conflicts.addConflicts('zsh', 'EQ', ('0', '1', '1'))


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
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.update_i386,))
    def testUpdatei386ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_i386, p.requires_update))
        else:
            self.assertResult((p.installed_i386, p.update_x86_64, p.requires_update))
    def testUpdatei386ToMultilibForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.update_x86_64, p.requires_update], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.update_i386, p.update_x86_64, p.requires_update))

    def testUpdatex86_64ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.update_x86_64,))
    def testUpdatex86_64ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_x86_64], 
                                     [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res==2, msg)
        self.assertResult((p.update_x86_64, p.requires_update))

    def testUpdateMultilibToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.update_i386, p.update_x86_64))
    def testUpdateMultilibToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_i386, p.update_x86_64,  p.requires_update))
        else:
            self.assertResult((p.installed_i386, p.update_x86_64,  p.requires_update))

    def testUpdatei386Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_noarch])
        self.assert_(res==2, msg)
        self.assertResult((p.update_noarch,))
    def testUpdatei386TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_noarch, p.requires_update])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_noarch, p.requires_update))
        else:
            self.assertResult((p.installed_i386, p.update_noarch, p.requires_update))

    def testUpdateMultilibTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_noarch])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_noarch,))
        else:
            self.assertResult((p.update_noarch, p.installed_x86_64))
    def testUpdateMultilibTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_noarch, p.requires_update])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_noarch, p.requires_update))
        else:
            self.assertResult((p.installed_i386, p.installed_x86_64, p.update_noarch, p.requires_update))

    def testUpdatenoarchToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_x86_64,), (p.update_i386,)) # ?
        else:
            self.assertResult((p.update_i386, p.update_x86_64))
    def testUpdatenoarchToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_x86_64, p.requires_update), (p.update_i386,))
        else:
            self.assertResult((p.installed_noarch, p.update_x86_64, p.requires_update))
    def testUpdatenoarchToMultilibForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch, p.update_x86_64, p.requires_update], [p.update_i386, p.update_x86_64])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.update_i386, p.update_x86_64, p.requires_update)) # ?
        else:
            self.assertResult((p.update_i386, p.update_x86_64, p.requires_update))

    ###################################################
    ###   Obsoletes   #################################
    ###################################################

    def testObsoletenoarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_x86_64,), (p.obsoletes_i386,))
        else:
            self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64))
    def testObsoletenoarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_noarch], 
                                     [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes), (p.obsoletes_i386,))
        else:
            self.assertResult((p.installed_noarch, p.obsoletes_x86_64, p.requires_obsoletes))
    def testObsoletenoarchToMultiarchForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch, p.obsoletes_x86_64, p.requires_obsoletes], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==0, msg)
        #self.assertResult((p.obsoletes_x86_64,)) # yes, this would be nice - but also wrong
        self.assertResult((p.installed_noarch, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoletei386ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoletei386ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_i386, p.requires_obsoletes))
        else:
            self.assertResult((p.installed_i386, p.obsoletes_x86_64, p.requires_obsoletes))
    def testObsoletei386ToMultiarchForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.obsoletes_x86_64, p.requires_obsoletes], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==0, msg)
        #self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes)) # yes, this would be nice - but also wrong
        self.assertResult((p.installed_i386, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoletex86_64ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoletex86_64ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes))
        else:
            self.assertResult((p.installed_x86_64, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoleteMultiarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==2, msg)
        self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64))
    def testObsoleteMultiarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes))
        else:
            self.assertResult((p.installed_i386, p.installed_x86_64, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoleteMultiarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_noarch])
        self.assert_(res==2, msg)
        self.assertResult((p.obsoletes_noarch,))
    def testObsoleteMultiarchTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_noarch, p.requires_obsoletes])
        self.assert_(res==2, msg)
        if testbase.new_behavior:
            self.assertResult((p.obsoletes_noarch, p.requires_obsoletes))
        else:
            self.assertResult((p.installed_i386, p.installed_x86_64, p.obsoletes_noarch, p.requires_obsoletes))

    # Obsolete for conflict

    def testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.conflicts])
        if testbase.new_behavior:
            self.assert_(res==2, msg)
            self.assertResult((p.obsoletes_i386, p.conflicts))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OperationsTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

