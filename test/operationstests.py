from testbase import *
import simpleobsoletestests

# Obsolete for conflict
class ComplicatedTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        simpleobsoletestests.SimpleObsoletesTests.buildPkgs(pkgs)
        # conflicts
        pkgs.conflicts = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        pkgs.conflicts.addConflicts('zsh', 'EQ', ('0', '1', '1'))

    def testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.conflicts])
        if new_behavior:
            self.assert_(res=='ok', msg)
            self.assertResult((p.obsoletes_i386, p.conflicts))

class CombinedUpdateObsoletesTest(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.k_1 = FakePackage('k', '3.5')
        pkgs.kdevel_1 = FakePackage('k-devel', '3.5')
        pkgs.kdevel_1.addRequires('k')
        pkgs.klibs_1_i386 = FakePackage('klibs', '3.5', arch='i386')
        pkgs.klibs_1_x86_64 = FakePackage('klibs', '3.5', arch='x86_64')
        pkgs.k_2 = FakePackage('k', '3.5', '2')
        pkgs.kdevel_2 = FakePackage('k-devel', '3.5', '2')
        pkgs.kdevel_2.addRequires('k')
        pkgs.klibs_2_i386 = FakePackage('klibs', '3.5', '2', arch='i386')
        pkgs.klibs_2_i386.addObsoletes('klibs', 'LT', (None, '3.5', '2'))
        pkgs.klibs_2_i386.addObsoletes('k', 'LT', (None, '3.5', '2'))
        pkgs.klibs_2_x86_64 = FakePackage('klibs', '3.5', '2', arch='x86_64')
        pkgs.klibs_2_x86_64.addObsoletes('klibs', 'LT', (None, '3.5', '2'))
        pkgs.klibs_2_x86_64.addObsoletes('k', 'LT', (None, '3.5', '2'))

    def testSelfObsolete(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.klibs_1_x86_64], [p.klibs_2_i386, p.klibs_2_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.klibs_2_x86_64,))

    def testPackageSplitWithObsoleteAndRequiresForUpdate(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.k_1, p.kdevel_1, p.klibs_1_x86_64],
                                     [p.k_2, p.kdevel_2, p.klibs_2_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.k_2, p.kdevel_2, p.klibs_2_x86_64,))



class ComplicatedObsoletesTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.installed = FakePackage('foo', '1.4', '1')
        pkgs.obsoletecircle = FakePackage('foo', '1.4', '1')
        pkgs.obsoletecircle.addObsoletes('baz')
        pkgs.obsoletes = FakePackage('bar', '1.2', '1')
        pkgs.obsoletes.addObsoletes('foo')
        pkgs.obsoletes2 = FakePackage('baz', '1.8', '1')
        pkgs.obsoletes2.addObsoletes('bar')

    def testObsoleteChain(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes2,))
        else:
            self.assertResult((p.obsoletes,))
    def testObsoleteChainNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes], [p.obsoletes2])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes2,))

    def testObsoleteCircle(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletecircle], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletecircle,))
        else:
            self.assertResult((p.obsoletes,))
    def testObsoleteCircleNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes], [p.obsoletecircle, p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes,))
        else:
            self.assertResult((p.obsoletes2,))
    def testObsoleteCircleNextNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes2], [p.obsoletecircle, p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes2,))
        else:
            self.assertResult((p.obsoletecircle,))
    def testObsoleteCircleNextNextNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletecircle], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletecircle,))
        else:
            self.assertResult((p.obsoletes,))
    # continue endlessly
    
class KernelTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.inst = []
        pkgs.inst.append(FakePackage('kernel', '2.6.23.8', '63',arch='i686'))
        pkgs.inst.append(FakePackage('kernel', '2.6.23.1', '49',arch='i686'))
        pkgs.avail = []
        pkgs.avail.append(FakePackage('kernel', '2.6.23.8', '63',arch='i686'))
        pkgs.avail.append(FakePackage('kernel', '2.6.23.8', '63',arch='i586'))
        pkgs.avail.append(FakePackage('kernel', '2.6.23.1', '49',arch='i686'))
        pkgs.avail.append(FakePackage('kernel', '2.6.23.1', '49',arch='i586'))
        pkgs.avail.append(FakePackage('kernel', '2.6.23.1', '42',arch='i686'))
        pkgs.avail.append(FakePackage('kernel', '2.6.23.1', '42',arch='i586'))
    
    def testKernelInstall(self):
        p = self.pkgs
        res, msg = self.runOperation(['install','kernel'], p.inst, p.avail)
        self.assertResult(p.inst)
