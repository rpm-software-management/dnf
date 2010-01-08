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
        if True or new_behavior:
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
            self.assertResult((p.obsoletes2,))
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
            self.assertResult((p.obsoletes2,))
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
    
    def testKernelInstall1(self):
        p = self.pkgs
        res, msg = self.runOperation(['install','kernel'], p.inst, p.avail)
        self.assertResult(p.inst)

    def testKernelInstall2(self):
        p = self.pkgs
        res, msg = self.runOperation(['install','kernel-2.6.23.1-42'], p.inst, p.avail)
        self.assertResult(p.inst + [ p.avail[4] ] )

    def testKernelInstall3(self):
        p = self.pkgs
        res, msg = self.runOperation(['install','kernel-2.6.23.8'], p.inst, p.avail)
        self.assertResult(p.inst)

class MultiLibTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.inst = []
        pkgs.i_foo_1_12_x = FakePackage('foo', '1', '12',arch='x86_64')
        pkgs.i_wbar_1_12_i = FakePackage('wbar', '1', '12', arch='i586')
        pkgs.inst.append(pkgs.i_foo_1_12_x)
        pkgs.inst.append(pkgs.i_wbar_1_12_i)

        pkgs.avail = []
        pkgs.a_foo_0_2_x = FakePackage('foo', '0',  '2', arch='x86_64')
        pkgs.a_foo_0_2_i = FakePackage('foo', '0',  '2', arch='i686')
        pkgs.a_foo_1_12_x = FakePackage('foo', '1', '12', arch='x86_64')
        pkgs.a_foo_1_12_i = FakePackage('foo', '1', '12', arch='i686')
        pkgs.a_foo_2_22_x = FakePackage('foo', '2', '22', arch='x86_64')
        pkgs.a_foo_2_22_i = FakePackage('foo', '2', '22', arch='i686')
        pkgs.a_bar_1_12_x = FakePackage('bar', '1', '12', arch='x86_64')
        pkgs.a_bar_1_12_i = FakePackage('bar', '1', '12', arch='i686')
        pkgs.a_bar_2_22_x = FakePackage('bar', '2', '22', arch='x86_64')
        pkgs.a_bar_2_22_i = FakePackage('bar', '2', '22', arch='i686')

        # ibar is .i?86 older
        pkgs.a_ibar_2_22_x = FakePackage('ibar', '2', '22', arch='x86_64')
        pkgs.a_ibar_1_12_i = FakePackage('ibar', '1', '12', arch='i686')

        # xbar is .x86_64 older
        pkgs.a_xbar_1_12_x = FakePackage('xbar', '1', '12', arch='x86_64')
        pkgs.a_xbar_2_22_i = FakePackage('xbar', '2', '22', arch='i686')

        # wbar is arch changing update/downgrade
        pkgs.a_wbar_0_2_i = FakePackage('wbar', '0', '2', arch='i386')
        pkgs.a_wbar_2_22_i = FakePackage('wbar', '2', '22', arch='i686')

        for i in ('a_foo_0_2', 'a_foo_1_12', 'a_foo_2_22',
                  'a_bar_1_12', 'a_bar_2_22'):
            pkgs.avail.append(getattr(pkgs, i + '_x'))
            pkgs.avail.append(getattr(pkgs, i + '_i'))
        pkgs.avail.append(pkgs.a_ibar_2_22_x)
        pkgs.avail.append(pkgs.a_ibar_1_12_i)
        pkgs.avail.append(pkgs.a_xbar_1_12_x)
        pkgs.avail.append(pkgs.a_xbar_2_22_i)
        pkgs.avail.append(pkgs.a_wbar_0_2_i)
        pkgs.avail.append(pkgs.a_wbar_2_22_i)
    
    def testBestInstall1(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_bar_2_22_x)
        res, msg = self.runOperation(['install', 'bar'], p.inst, p.avail)
        self.assertResult(ninst)

    def testBestInstall2(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_bar_1_12_x)
        res, msg = self.runOperation(['install', 'bar-1'], p.inst, p.avail)
        self.assertResult(ninst)

    def testAllInstall1(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_bar_2_22_x)
        ninst.append(p.a_bar_2_22_i)
        res, msg = self.runOperation(['install', 'bar'], p.inst, p.avail,
                                     {'multilib_policy' : 'all'})
        self.assertResult(ninst)

    def testAllInstall2(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_bar_1_12_x)
        ninst.append(p.a_bar_1_12_i)
        res, msg = self.runOperation(['install', 'bar-1'], p.inst, p.avail,
                                     {'multilib_policy' : 'all'})
        self.assertResult(ninst)

    def testAllInstall3(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_ibar_2_22_x)
        res, msg = self.runOperation(['install', 'ibar'], p.inst, p.avail,
                                     {'multilib_policy' : 'all'})
        self.assertResult(ninst)

    def testAllInstall4(self):
        p = self.pkgs
        ninst = p.inst[:]
        ninst.append(p.a_xbar_2_22_i)
        res, msg = self.runOperation(['install', 'xbar'], p.inst, p.avail,
                                     {'multilib_policy' : 'all'})
        self.assertResult(ninst)

    def testDowngrade1(self):
        p = self.pkgs
        ninst = [p.i_foo_1_12_x, p.a_wbar_0_2_i]
        res, msg = self.runOperation(['downgrade', 'wbar'], p.inst, p.avail)
        self.assertResult(ninst)

    def testDowngrade2(self):
        p = self.pkgs
        oinst = [p.i_foo_1_12_x, p.a_wbar_2_22_i]
        ninst = [p.i_foo_1_12_x, p.i_wbar_1_12_i]
        p.avail.append(p.i_wbar_1_12_i)
        res, msg = self.runOperation(['downgrade', 'wbar'], oinst, p.avail)
        self.assertResult(ninst)

    def testDowngrade3(self):
        p = self.pkgs
        oinst = [p.i_foo_1_12_x, p.a_wbar_2_22_i]
        ninst = [p.i_foo_1_12_x, p.a_wbar_0_2_i]
        res, msg = self.runOperation(['downgrade', 'wbar'], oinst, p.avail)
        self.assertResult(ninst)

    def testDowngrade4(self):
        p = self.pkgs
        oinst = p.inst[:] + [p.a_ibar_2_22_x]
        p.a_ibar_1_12_i.arch = 'noarch'
        ninst = p.inst[:] + [p.a_ibar_1_12_i]
        res, msg = self.runOperation(['downgrade', 'ibar'], oinst, p.avail)
        self.assertResult(ninst)

    def testDowngrade5(self):
        p = self.pkgs
        ninst = p.inst[:] + [p.a_xbar_1_12_x]
        p.a_xbar_2_22_i.arch = 'noarch'
        oinst = p.inst[:] + [p.a_xbar_2_22_i]
        res, msg = self.runOperation(['downgrade', 'xbar'], oinst, p.avail)
        self.assertResult(ninst)
