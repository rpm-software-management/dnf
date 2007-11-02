from testbase import *


class SimpleUpdateTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        # installed
        pkgs.installed_i386 = FakePackage('zsh', '1', '1', '0', 'i386')
        pkgs.installed_x86_64 = FakePackage('zsh', '1', '1', '0', 'x86_64')
        pkgs.installed_noarch = FakePackage('zsh', '1', '1', '0', 'noarch')
        # updates
        pkgs.update_i386 = FakePackage('zsh', '2', '1', '0', 'i386')
        pkgs.update_x86_64 = FakePackage('zsh', '2', '1', '0', 'x86_64')
        pkgs.update_noarch = FakePackage('zsh', '2', '1', '0', 'noarch')
        # requires update
        pkgs.requires_update = FakePackage('zsh-utils', '2', '1', '0', 'noarch')
        pkgs.requires_update.addRequires('zsh', 'EQ', ('0', '2', '1'))

    def testUpdatei386ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386,))
    def testUpdatei386ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.requires_update))
    def testUpdatei386ToMultilibForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.update_x86_64, p.requires_update], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.update_x86_64, p.requires_update))

    def testUpdatex86_64ToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64,))
    def testUpdatex86_64ToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_x86_64], 
                                     [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64, p.requires_update))

    def testUpdateMultilibToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.update_x86_64))
    def testUpdateMultilibToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.update_x86_64,  p.requires_update))

    def testUpdatei386Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch,))
    def testUpdatei386TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_noarch, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch, p.requires_update))

    def testUpdateMultilibTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch,))
    def testUpdateMultilibTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_noarch, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch, p.requires_update))

    def testUpdatenoarchToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_x86_64,), (p.update_i386,)) # ?
        else:
            self.assertResult((p.update_i386, p.update_x86_64))
    def testUpdatenoarchToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64, p.requires_update), (p.update_i386,))
    def testUpdatenoarchToMultilibForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch, p.update_x86_64, p.requires_update], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_i386, p.update_x86_64, p.requires_update)) # ?
        else:
            self.assertResult((p.update_i386, p.update_x86_64, p.requires_update))

class SimpleObsoleteTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        # installed
        pkgs.installed_i386 = FakePackage('zsh', '1', '1', '0', 'i386')
        pkgs.installed_x86_64 = FakePackage('zsh', '1', '1', '0', 'x86_64')
        pkgs.installed_noarch = FakePackage('zsh', '1', '1', '0', 'noarch')
        # obsoletes
        pkgs.obsoletes_i386 = FakePackage('zsh-ng', '0.3', '1', '0', 'i386')
        pkgs.obsoletes_i386.addObsoletes('zsh', None, (None, None, None))
        pkgs.obsoletes_i386.addProvides('zzz')
        pkgs.obsoletes_x86_64 = FakePackage('zsh-ng', '0.3', '1', '0', 'x86_64')
        pkgs.obsoletes_x86_64.addObsoletes('zsh', None, (None, None, None))
        pkgs.obsoletes_x86_64.addProvides('zzz')
        pkgs.obsoletes_noarch = FakePackage('zsh-ng', '0.3', '1', '0', 'noarch')
        pkgs.obsoletes_noarch.addObsoletes('zsh', None, (None, None, None))
        pkgs.obsoletes_noarch.addProvides('zzz')
        # requires obsoletes
        pkgs.requires_obsoletes = FakePackage('superzippy', '3.5', '3', '0', 'noarch')
        pkgs.requires_obsoletes.addRequires('zzz')


    def testObsoletenoarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes_x86_64,), (p.obsoletes_i386,))
        else:
            self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64))
    def testObsoletenoarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_noarch], 
                                     [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes), (p.obsoletes_i386,))
    def testObsoletenoarchToMultiarchForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch, p.obsoletes_x86_64, p.requires_obsoletes], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==0, msg)
        #self.assertResult((p.obsoletes_x86_64,)) # yes, this would be nice - but also wrong
        self.assertResult((p.installed_noarch, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoletei386ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoletei386ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.requires_obsoletes))
    def testObsoletei386ToMultiarchForDependencyFix(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.obsoletes_x86_64, p.requires_obsoletes], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res==0, msg)
        #self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes)) # yes, this would be nice - but also wrong
        self.assertResult((p.installed_i386, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoletex86_64ToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoletex86_64ToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoleteMultiarchToMultiarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64))
    def testObsoleteMultiarchToMultiarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], 
                                     [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.obsoletes_x86_64, p.requires_obsoletes))

    def testObsoleteMultiarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch,))
    def testObsoleteMultiarchTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_noarch, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch, p.requires_obsoletes))

# Obsolete for conflict
class ComplicatedTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        SimpleObsoleteTests.buildPkgs(pkgs)
        # conflicts
        pkgs.conflicts = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        pkgs.conflicts.addConflicts('zsh', 'EQ', ('0', '1', '1'))

    def testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.conflicts])
        if new_behavior:
            self.assert_(res=='ok', msg)
            self.assertResult((p.obsoletes_i386, p.conflicts))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SimpleUpdateTests))
    suite.addTest(unittest.makeSuite(SimpleObsoleteTests))
    suite.addTest(unittest.makeSuite(ComplicatedTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

