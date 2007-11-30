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

    # noarch to X

    def testUpdatenoarchTonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_noarch,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch,))
    def testUpdatenoarchTonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_noarch, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch, p.requires_update))

    def testUpdatenoarchToi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_i386,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386,))
    def testUpdatenoarchToi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_i386, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.requires_update))

    def testUpdatenoarchTox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_x86_64,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64,))
    def testUpdatenoarchTox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64, p.requires_update))

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

    # i386 to X

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

    def testUpdatei386Toi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386,))
    def testUpdatei386Toi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_i386, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.requires_update))

    def testUpdatei386Tox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386], [p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64,))
    def testUpdatei386Tox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386], [p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64, p.requires_update))

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

    # x86_64 to X

    def testUpdatex86_64Tonoarch(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.update_noarch,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch,))
    def testUpdatex86_64TonoarchForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_x86_64],
                                     [p.update_noarch, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_noarch, p.requires_update))

    def testUpdatex86_64Toi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.update_i386,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386,))
    def testUpdatex86_64Toi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_x86_64],
                                     [p.update_i386, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_i386, p.requires_update))

    def testUpdatex86_64Tox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_x86_64], [p.update_x86_64,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64,))
    def testUpdatex86_64Tox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_x86_64],
                                     [p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update_x86_64, p.requires_update))

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

    # multilib to X

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

    def testUpdateMultilibToi386(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_i386])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_i386, p.installed_x86_64))
            # self.assertResult((p.update_i386,)) # XXX is this right?
        else:
            self.assertResult((p.update_i386, p.installed_x86_64))
    def testUpdateMultilibToi386ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_i386, p.requires_update])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_i386, p.installed_x86_64, p.requires_update))
            # self.assertResult((p.update_i386, p.requires_update)) # XXX is this right?
        else:
            self.assertResult((p.update_i386, p.installed_x86_64, p.requires_update))

    def testUpdateMultilibTox86_64(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_i386, p.installed_x86_64], [p.update_x86_64])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_x86_64, p.installed_i386))
            # self.assertResult((p.update_x86_64,)) # XXX is this right?
        else:
            self.assertResult((p.update_x86_64, p.installed_i386))
    def testUpdateMultilibTox86_64ForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_i386, p.installed_x86_64], [p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.update_x86_64, p.installed_i386, p.requires_update))
            # self.assertResult((p.update_x86_64, p.requires_update)) # XXX is this right?
        else:
            self.assertResult((p.update_x86_64, p.installed_i386, p.requires_update))

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
