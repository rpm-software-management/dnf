import unittest

from depsolvetests import FakePackage, FakeRpmSack, FakeRepo, FakeConf
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
        self.pkgs.ox86_64 = FakePackage('zsh-ng', '0.3', '1', '0', 'x86_64')
        self.pkgs.ox86_64.addObsoletes('zsh', None, (None, None, None))
        self.pkgs.onoarch = FakePackage('zsh-ng', '0.3', '1', '0', 'noarch')
        self.pkgs.onoarch.addObsoletes('zsh', None, (None, None, None))
        # conflicts
        self.pkgs.conflict = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        self.pkgs.conflict.addConflicts('zsh', 'EQ', ('0', '1', '1'))


    def runOperation(self, args, installed=[], available=[]):
        depsolver = YumBaseCli()
        depsolver.rpmdb  = FakeRpmSack()
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

    def assertInstalled(self, po, msg=None):
        if (not self.depsolver.tsInfo.getMembersWithState(po.pkgtup, TS_INSTALL_STATES) and # not getting installed
            (not self.depsolver.rpmdb.searchNevra(po.name, po.epoch, po.version, po.release, po.arch) or # not is installed
             self.depsolver.tsInfo.getMembersWithState(po.pkgtup, TS_REMOVE_STATES))): # getting removed
            self.fail("Package %(pkg)s is not installed!" % {'pkg' : str(po)})


    def assertNotInstalled(self, po, msg=None):
        if (self.depsolver.tsInfo.getMembersWithState(po.pkgtup, TS_INSTALL_STATES) or # getting installed
            (self.depsolver.rpmdb.searchNevra(po.name, po.epoch, po.version, po.release, po.arch) and # is installed
             not self.depsolver.tsInfo.getMembersWithState(po.pkgtup, TS_REMOVE_STATES))): # not getting removed
            self.fail((msg or "Package %(pkg)s is installed!") % {'pkg' : str(po)})

    #######################################################################
    ### Tests #############################################################
    #######################################################################

    def testUpdatei386ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ui386)
        self.assertNotInstalled(p.ux86_64)

    def testUpdatei386ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        #self.assertInstalled(p.ui386)
        #self.assertNotInstalled(p.ux86_64)
        self.assertInstalled(p.ux86_64) # XXX
        self.assertInstalled(p.ru)

    def testUpdatex86_64ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ix86_64], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ux86_64)
        self.assertNotInstalled(p.ui386)

    def testUpdatex86_64ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ix86_64], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ux86_64)
        self.assertNotInstalled(p.ui386)
        self.assertInstalled(p.ru)

    def testUpdateMultilibToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ui386)
        self.assertInstalled(p.ux86_64)

    def testUpdateMultilibToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386, p.ix86_64], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ii386)
        self.assertNotInstalled(p.ix86_64)
        self.assertNotInstalled(p.ui386)
        self.assertInstalled(p.ux86_64)
        self.assertInstalled(p.ru)

    def testUpdatei386Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.unoarch])
        self.assert_(res==2, msg)
        self.assertInstalled(p.unoarch)
        self.assertNotInstalled(p.ii386)

    def testUpdatei386TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386], [p.unoarch, p.ru])
        self.assert_(res==2, msg)
        self.assertInstalled(p.unoarch)
        #self.assertNotInstalled(p.ii386) # XXX
        self.assertInstalled(p.ru)

    def testUpdateMultilibTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.unoarch])
        self.assert_(res==2, msg)
        self.assertInstalled(p.unoarch)
        self.assertNotInstalled(p.ii386)
        # self.assertNotInstalled(p.ix86_64) # XXX

    def testUpdateMultilibTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.ii386, p.ix86_64], [p.unoarch, p.ru])
        self.assert_(res==2, msg)
        self.assertInstalled(p.unoarch)
        #self.assertNotInstalled(p.ii386)
        #self.assertNotInstalled(p.ix86_64)
        self.assertInstalled(p.ru)

    def testUpdatenoarchToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.inoarch], [p.ui386, p.ux86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.ui386) # ???
        self.assertInstalled(p.ux86_64)
        self.assertNotInstalled(p.inoarch)

    def testUpdatenoarchToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.inoarch], [p.ui386, p.ux86_64, p.ru])
        self.assert_(res==2, msg)
        self.assertNotInstalled(p.ui386) # ???
        self.assertInstalled(p.ux86_64)
        # self.assertNotInstalled(p.inoarch)
        self.assertInstalled(p.ru)

    # obsoletes

    def testObsoletenoarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.inoarch], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        #self.assertNotInstalled(p.oi386)
        self.assertInstalled(p.ox86_64)
        self.assertNotInstalled(p.inoarch)

    def testObsoletei386ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.oi386)
        #self.assertNotInstalled(p.ox86_64)
        self.assertNotInstalled(p.ii386)

    def testObsoleteMultiarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.oi386, p.ox86_64])
        self.assert_(res==2, msg)
        self.assertInstalled(p.oi386)
        self.assertInstalled(p.ox86_64)
        self.assertNotInstalled(p.ii386)
        self.assertNotInstalled(p.ix86_64)

    def testObsoleteMultiarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.ii386, p.ix86_64], [p.onoarch])
        self.assert_(res==2, msg)
        self.assertInstalled(p.onoarch)
        self.assertNotInstalled(p.ii386)
        self.assertNotInstalled(p.ix86_64)

    # Obsolete for conflict

    def _XXX_testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.ii386], [p.oi386, p.ox86_64, p.conflict])
        self.assert_(res==2, msg)
        self.assertInstalled(p.conflict)
        self.assertInstalled(p.oi386) # XXX ???
        self.assertNotInstalled(p.oi386) # XXX ???
        self.assertInstalled(p.ox86_64)
        self.assertNotInstalled(p.ii386)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OperationsTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

