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


class GitMetapackageObsoletesTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        # installed
        pkgs.installed = FakePackage('git-core', '1.5.4.2', '1', '0', 'x86_64')
        pkgs.metapackage = FakePackage('git', '1.5.4.2', '1', '0', 'x86_64')
        # obsoletes
        pkgs.new_git = FakePackage('git', '1.5.4.4', '1', '0', 'x86_64')
        pkgs.new_git.addObsoletes('git-core', LE, ('0', '1.5.4.3', '1'))
        pkgs.new_git.addProvides('git-core', EQ, ('0', '1.5.4', '1'))

        pkgs.git_all = FakePackage('git-all', '1.5.4', '1', '0', 'x86_64')
        pkgs.git_all.addObsoletes('git', LE, ('0', '1.5.4.3', '1'))


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
