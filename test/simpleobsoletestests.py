from testbase import *

class SimpleObsoletesTests(OperationsTests):

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

    # noarch to X

    def testObsoletenoarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.obsoletes_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch,))
    def testObsoletenoarchTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_noarch],
                                     [p.obsoletes_noarch, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch, p.requires_obsoletes))

    def testObsoletenoarchToi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.obsoletes_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoletenoarchToi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_noarch],
                                     [p.obsoletes_i386, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.requires_obsoletes))

    def testObsoletenoarchTox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoletenoarchTox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_noarch],
                                     [p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes))

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

    # i386 to X

    def testObsoletei386Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.obsoletes_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch,))
    def testObsoletei386TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386], [p.obsoletes_noarch, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch, p.requires_obsoletes))

    def testObsoletei386Toi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.obsoletes_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoletei386Toi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386], [p.obsoletes_i386, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.requires_obsoletes))

    def testObsoletei386Tox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoletei386Tox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386], [p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes))


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

    # x86_64 to X

    def testObsoletex86_64Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.obsoletes_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch,))
    def testObsoletex86_64TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_x86_64], [p.obsoletes_noarch, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch, p.requires_obsoletes))

    def testObsoletex86_64Toi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.obsoletes_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoletex86_64Toi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_x86_64], [p.obsoletes_i386, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.requires_obsoletes))

    def testObsoletex86_64Tox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoletex86_64Tox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_x86_64], [p.obsoletes_x86_64, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64, p.requires_obsoletes))

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

    # multiarch to X

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

    def testObsoleteMultiarchToi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386,))
    def testObsoleteMultiarchToi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_i386, p.requires_obsoletes])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_i386, p.requires_obsoletes))

    def testObsoleteMultiarchTox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_x86_64,))
    def testObsoleteMultiarchTox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'superzippy'], [p.installed_i386, p.installed_x86_64], [p.obsoletes_x86_64, p.requires_obsoletes])
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


    def testInstallObsoletenoarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-ng'], [p.installed_noarch], [p.obsoletes_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes_noarch,))

    def _MultiObsHelper(self):
        ret = {'zsh'  : FakePackage('zsh', '1', '1', '0', 'noarch'),
               'ksh'  : FakePackage('ksh', '1', '1', '0', 'noarch'),
               'nash' : FakePackage('nash', '1', '1', '0', 'noarch')}
        ret['pi'] = [ret['zsh'], ret['ksh'], ret['nash']]
              
        ret['fish'] = FakePackage('fish', '0.1', '1', '0', 'noarch')
        ret['fish'].addObsoletes('zsh', None, (None, None, None))
        ret['bigfish'] = FakePackage('bigfish', '0.2', '1', '0', 'noarch')
        ret['bigfish'].addObsoletes('zsh', None, (None, None, None))
        ret['bigfish'].addObsoletes('ksh', None, (None, None, None))
        ret['shark'] = FakePackage('shark', '0.3', '1', '0', 'noarch')
        ret['shark'].addObsoletes('zsh', None, (None, None, None))
        ret['shark'].addObsoletes('ksh', None, (None, None, None))
        ret['shark'].addObsoletes('nash', None, (None, None, None))

        ret['po'] = [ret['fish'], ret['bigfish'], ret['shark']]
        return ret

    def testMultiObs1(self):
        pkgs = self._MultiObsHelper()
        res, msg = self.runOperation(['install', 'fish'],
                                     pkgs['pi'], pkgs['po'])
        self.assert_(res=='ok', msg)
        self.assertResult((pkgs['ksh'],pkgs['nash'],pkgs['fish'],))

    def testMultiObs2(self):
        pkgs = self._MultiObsHelper()
        res, msg = self.runOperation(['install', 'bigfish'],
                                     pkgs['pi'], pkgs['po'])
        self.assert_(res=='ok', msg)
        self.assertResult((pkgs['nash'],pkgs['bigfish'],))

    def testMultiObs3(self):
        pkgs = self._MultiObsHelper()
        res, msg = self.runOperation(['install', 'shark'],
                                     pkgs['pi'], pkgs['po'])
        self.assert_(res=='ok', msg)
        self.assertResult((pkgs['shark'],))

    def testMultiObs4(self):
        # This tests update...
        pkgs = self._MultiObsHelper()
        oldshark = FakePackage('shark', '0.1', '1', '0', 'noarch')

        res, msg = self.runOperation(['update', 'shark'],
                                     pkgs['pi'] + [oldshark], pkgs['po'])
        self.assert_(res=='ok', msg)
        self.assertResult((pkgs['shark'],))

    def testMultiObs5(self):
        # This tests update of the to be obsoleted pkg...
        pkgs = self._MultiObsHelper()
        oldshark = FakePackage('shark', '0.1', '1', '0', 'noarch')

        res, msg = self.runOperation(['update', 'nash'],
                                     pkgs['pi'] + [oldshark], pkgs['po'])
        self.assert_(res=='ok', msg)
        self.assertResult((pkgs['shark'],))

    # NOTE: Do we really want to remove the old kernel-xen? ... not 100% sure
    def testMultiObsKern1(self):
        # kernel + kernel-xen installed, and update kernel obsoletes kernel-xen
        okern1    = FakePackage('kernel',     '0.1', '1', '0', 'noarch')
        okern2    = FakePackage('kernel',     '0.2', '1', '0', 'noarch')
        okernxen1 = FakePackage('kernel-xen', '0.1', '1', '0', 'noarch')
        okernxen2 = FakePackage('kernel-xen', '0.2', '1', '0', 'noarch')
        nkern     = FakePackage('kernel',     '0.8', '1', '0', 'noarch')
        nkern.addObsoletes('kernel-xen', None, (None, None, None))

        res, msg = self.runOperation(['update', 'kernel'],
                                     [okern1, okernxen1,
                                      okern2, okernxen2], [nkern])
        self.assert_(res=='ok', msg)
        self.assertResult((okern1,okern2,nkern,))

    def testMultiObsKern2(self):
        # kernel + kernel-xen installed, and update kernel obsoletes kernel-xen
        okern1    = FakePackage('kernel',     '0.1', '1', '0', 'noarch')
        okern2    = FakePackage('kernel',     '0.2', '1', '0', 'noarch')
        okernxen1 = FakePackage('kernel-xen', '0.1', '1', '0', 'noarch')
        okernxen2 = FakePackage('kernel-xen', '0.2', '1', '0', 'noarch')
        nkern     = FakePackage('kernel',     '0.8', '1', '0', 'noarch')
        nkern.addObsoletes('kernel-xen', None, (None, None, None))

        res, msg = self.runOperation(['update', 'kernel-xen'],
                                     [okern1, okernxen1,
                                      okern2, okernxen2], [nkern])
        self.assert_(res=='ok', msg)
        self.assertResult((okern1,okern2,nkern,))

    def testMultiObsKern3(self):
        # kernel + kernel-xen installed, and update kernel obsoletes kernel-xen
        okern1    = FakePackage('kernel',     '0.1', '1', '0', 'noarch')
        okern2    = FakePackage('kernel',     '0.2', '1', '0', 'noarch')
        okernxen1 = FakePackage('kernel-xen', '0.1', '1', '0', 'noarch')
        okernxen2 = FakePackage('kernel-xen', '0.2', '1', '0', 'noarch')
        nkern     = FakePackage('kernel',     '0.8', '1', '0', 'noarch')
        nkern.addObsoletes('kernel-xen', None, (None, None, None))

        res, msg = self.runOperation(['update'],
                                     [okern1, okernxen1,
                                      okern2, okernxen2], [nkern])
        self.assert_(res=='ok', msg)
        self.assertResult((okern1,okern2,nkern,))


class GitMetapackageObsoletesTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        # installed
        pkgs.installed = FakePackage('git-core', '1.5.4.2', '1', '0', 'x86_64')
        pkgs.metapackage = FakePackage('git', '1.5.4.2', '1', '0', 'x86_64')
        # obsoletes
        pkgs.new_git = FakePackage('git', '1.5.4.4', '1', '0', 'x86_64')
        pkgs.new_git.addObsoletes('git-core', 'LE', ('0', '1.5.4.3', '1'))
        pkgs.new_git.addProvides('git-core', 'EQ', ('0', '1.5.4', '1'))

        pkgs.git_all = FakePackage('git-all', '1.5.4', '1', '0', 'x86_64')
        pkgs.git_all.addObsoletes('git', 'LE', ('0', '1.5.4.3', '1'))


    def testGitMetapackageOnlyCoreInstalled(self):
        # Fedora had a package named 'git', which was a metapackage requiring
        # all other git rpms. Most people wanted 'git-core' when they asked for
        # git, so we renamed them.
        # git-core became git, and provided git-core = version while obsoleting
        # git-core < version
        # git became git-all, obsoleting git < version

        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed],
                [p.new_git, p.git_all])
        self.assert_(res=='ok', msg)
        self.assertResult((p.new_git,))

    def testGitMetapackageRenameMetapackageAndCoreInstalled(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed, p.metapackage],
                [p.new_git, p.git_all])
        self.assert_(res=='ok', msg)
        self.assertResult((p.new_git, p.git_all))
