from testbase import *

import rpmUtils.arch

class SimpleUpdateTests(OperationsTests):

    """This test suite runs three different type of tests - for all possible
    combinations of arches installed and available as update.

    1. Update: as done with "yum update"
    2. UpdateForDependency: pkgs.requires_update requires a new version of the
       already installed pkg(s)
    3. UpdateForDependency2: A requirement of the installed pkg(s) is removed during
       an update. Yum tries to update these packages to resolve the situation.
    """

    @staticmethod
    def buildPkgs(pkgs, *args):
        # installed
        pkgs.installed_i386 = FakePackage('zsh', '1', '1', '0', 'i386')
        pkgs.installed_i386.addRequires('bar', 'EQ', ('0', '1', '1'))
        pkgs.installed_x86_64 = FakePackage('zsh', '1', '1', '0', 'x86_64')
        pkgs.installed_x86_64.addRequires('bar', 'EQ', ('0', '1', '1'))
        pkgs.installed_noarch = FakePackage('zsh', '1', '1', '0', 'noarch')
        pkgs.installed_noarch.addRequires('bar', 'EQ', ('0', '1', '1'))
        # updates
        pkgs.update_i386 = FakePackage('zsh', '2', '1', '0', 'i386')
        pkgs.update_x86_64 = FakePackage('zsh', '2', '1', '0', 'x86_64')
        pkgs.update_noarch = FakePackage('zsh', '2', '1', '0', 'noarch')
        # requires update (UpdateForDependency tests)
        pkgs.requires_update = FakePackage('zsh-utils', '2', '1', '0', 'noarch')
        pkgs.requires_update.addRequires('zsh', 'EQ', ('0', '2', '1'))
        # removed requirement due to update (UpdateForDependency2 tests)
        pkgs.required = FakePackage('bar', '1', '1', '0')
        pkgs.required_updated = FakePackage('bar', version='2')

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
    def testUpdatenoarchTonoarchForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_noarch],
                                     [p.required_updated, p.update_noarch,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_noarch,))

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
    def testUpdatenoarchToi386ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_noarch],
                                     [p.required_updated, p.update_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_i386))

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
    def testUpdatenoarchTox86_64ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_noarch],
                                     [p.required_updated, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_x86_64))

    def testUpdatenoarchToMultilib(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed_noarch], [p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        if True or new_behavior: # We update from .noarch to just the .x86_64
            self.assertResult((p.update_x86_64,), (p.update_i386,)) # ?
        else: # Updates to both...
            self.assertResult((p.update_i386, p.update_x86_64))
    def testUpdatenoarchToMultilibForDependencyRev(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_x86_64, p.update_i386, p.requires_update])
        self.assert_(res=='ok', msg)
        if self.canonArch == 'x86_64':
            self.assertResult((p.update_x86_64, p.requires_update))
        else:
            self.assertResult((p.update_i386, p.requires_update))
    def testUpdatenoarchToMultilibForDependency(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'zsh-utils'], [p.installed_noarch], [p.update_i386, p.update_x86_64, p.requires_update])
        self.assert_(res=='ok', msg)
        if self.canonArch == 'x86_64':
            self.assertResult((p.update_x86_64, p.requires_update))
        else:
            self.assertResult((p.update_i386, p.requires_update))
    def testUpdatenoarchToMultilibForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_noarch],
                                     [p.required_updated, p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_x86_64), (p.update_i386,))

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
    def testUpdatei386TonoarchForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386],
                                     [p.required_updated, p.update_noarch,])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_noarch,))

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
    def testUpdatei386Toi386ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386],
                                     [p.required_updated, p.update_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_i386))

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
    def testUpdatei386Tox86_64ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386],
                                     [p.required_updated, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_x86_64))

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
    def testUpdatei386ToMultilibForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386],
                                     [p.required_updated, p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_i386))

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
    def testUpdatex86_64TonoarchForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_x86_64],
                                     [p.required_updated, p.update_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_noarch))

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
    def testUpdatex86_64Toi386ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_x86_64],
                                     [p.required_updated, p.update_i386])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_i386))

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
    def testUpdatex86_64Tox86_64ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_x86_64],
                                     [p.required_updated, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_x86_64))

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
    def testUpdatex86_64ToMultilibForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_x86_64],
                                     [p.required_updated, p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_x86_64))

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
    def testUpdateMultilibTonoarchForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386, p.installed_x86_64],
                                     [p.required_updated, p.update_noarch])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_noarch))

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
    def testUpdateMultilibToi386ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386, p.installed_x86_64],
                                     [p.required_updated, p.update_i386])
        self.assert_(res=='err', msg)
        self.assertResult((p.required_updated, p.update_i386, p.installed_x86_64))

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
    def testUpdateMultilibTox86_64ForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386, p.installed_x86_64],
                                     [p.required_updated, p.update_x86_64])
        self.assert_(res=='err', msg)
        self.assertResult((p.required_updated, p.update_x86_64, p.installed_i386))

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
    def testUpdateMultilibToMultilibForDependency2(self):
        p = self.pkgs
        res, msg = self.runOperation(['update', 'bar'], [p.required, p.installed_i386, p.installed_x86_64],
                                     [p.required_updated, p.update_i386, p.update_x86_64])
        self.assert_(res=='ok', msg)
        self.assertResult((p.required_updated, p.update_i386, p.update_x86_64))

    def testUpdateNotLatestDep(self):
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo11.addRequires('bar', 'EQ', ('0', '1', '1'))
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo12.addRequires('bar', 'EQ', ('0', '1', '2'))
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar21 = FakePackage('bar', '2', '1', '0', 'i386')
        res, msg = self.runOperation(['install', 'foo'], [foo11, bar11], [foo12, bar12, bar21])
        self.assert_(res=='ok', msg)
        self.assertResult((foo12, bar12))

    def testUpdateBadMultiInstall1(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')

        res, msg = self.runOperation(['install', 'foo'],
                                     [foo11, foo12, foo13],
                                     [foo20])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,))

    def testUpdateBadMultiInstall2(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')

        res, msg = self.runOperation(['update', 'foo'],
                                     [foo11, foo12, foo13],
                                     [foo20])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,))

    def testUpdateBadMultiInstall3(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')

        res, msg = self.runOperation(['update'],
                                     [foo11, foo12, foo13],
                                     [foo20])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,))

    def testUpdateBadMultiInstall4(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar12.addRequires('foo', 'EQ', ('0', '2', '0'))

        res, msg = self.runOperation(['update', 'bar'],
                                     [foo11, foo12, foo13, bar11],
                                     [foo20, bar12])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,bar12))

    def testUpdateBadMultiInstall5(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar12.addRequires('foo', 'EQ', ('0', '2', '0'))

        res, msg = self.runOperation(['update'],
                                     [foo11, foo12, foo13, bar11],
                                     [foo20, bar12])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,bar12))

    def testUpdateBadMultiInstall6(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar12.addObsoletes('foo', None, (None, None, None))

        res, msg = self.runOperation(['update'],
                                     [foo11, foo12, foo13, bar11],
                                     [foo20, bar12])
        self.assert_(res=='ok', msg)
        self.assertResult((bar12,))

    def testUpdateBadMultiInstall7(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar12.addRequires('foo', 'EQ', ('0', '2', '0'))

        res, msg = self.runOperation(['update', '*'],
                                     [foo11, foo12, foo13, bar11],
                                     [foo20, bar12])
        self.assert_(res=='ok', msg)
        self.assertResult((foo20,bar12))

    def testUpdateBadMultiInstall8(self):
        # This is a bug, but we shouldn't die too badly on it...
        foo11 = FakePackage('foo', '1', '1', '0', 'i386')
        foo12 = FakePackage('foo', '1', '2', '0', 'i386')
        foo13 = FakePackage('foo', '1', '3', '0', 'i386')
        foo20 = FakePackage('foo', '2', '0', '0', 'i386')
        bar11 = FakePackage('bar', '1', '1', '0', 'i386')
        bar12 = FakePackage('bar', '1', '2', '0', 'i386')
        bar12.addObsoletes('foo', None, (None, None, None))

        res, msg = self.runOperation(['update', '*'],
                                     [foo11, foo12, foo13, bar11],
                                     [foo20, bar12])
        self.assert_(res=='ok', msg)
        self.assertResult((bar12,))
