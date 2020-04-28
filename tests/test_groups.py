# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import operator

import libdnf.transaction

import dnf.comps
import dnf.util

import tests.support
from tests.support import mock


class EmptyPersistorTest(tests.support.ResultTestCase):
    """Test group operations with empty persistor."""

    REPOS = ['main']
    COMPS = True

    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_group_install_locale(self, _unused):
        grp = self.comps.group_by_pattern('Kritick\xe1 cesta (Z\xe1klad)')
        cnt = self.base.group_install(grp.id, ('mandatory',))
        self.assertEqual(cnt, 2)

    def test_finalize_comps_trans(self):
        trans = dnf.comps.TransactionBunch()
        trans.install = ('trampoline',)
        self.assertGreater(self.base._add_comps_trans(trans), 0)
        self.base._finalize_comps_trans()
        self.assertIn('trampoline', self.base._goal.group_members)
        (installed, removed) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed), ('trampoline-2.1-1.noarch',))
        self.assertEmpty(removed)


class PresetPersistorTest(tests.support.ResultTestCase):
    """Test group operations with some data in the persistor."""

    REPOS = ['main']
    COMPS = True
    COMPS_SEED_HISTORY = True

    def _install_test_env(self):
        """Env installation itself does not handle packages. We need to handle
           them manually for proper functionality of env remove"""

        env_id = 'sugar-desktop-environment'
        comps_env = self.comps._environment_by_id(env_id)
        self.base.environment_install(comps_env.id, ('mandatory',))
        self._swdb_commit()

        swdb_env = self.history.env.get(comps_env.id)
        self.assertIsNotNone(swdb_env)

        for comps_group in comps_env.mandatory_groups:
            swdb_group = self.history.group.get(comps_group.id)
            self.assertIsNotNone(swdb_group)

        tsis = []
        seen_pkgs = set()
        for swdb_env_group in swdb_env.getGroups():
            swdb_group = self.history.group.get(swdb_env_group.getGroupId())
            if not swdb_group:
                continue
            for swdb_pkg in swdb_group.getPackages():
                swdb_pkg.setInstalled(True)
                pkgs = self.base.sack.query().filter(name=swdb_pkg.getName(), arch="x86_64").run()
                if not pkgs:
                    continue
                pkg = pkgs[0]
                if pkg in seen_pkgs:
                    # prevent RPMs from being twice in a transaction and triggering unique constraint error
                    continue
                seen_pkgs.add(pkg)
                pkg._force_swdb_repoid = "main"
                self.history.rpm.add_install(pkg, reason=libdnf.transaction.TransactionItemReason_GROUP)
#                tsi = dnf.transaction.TransactionItem(
#                    dnf.transaction.INSTALL,
#                    installed=pkg,
#                    reason=libdnf.transaction.TransactionItemReason_GROUP
#                )
#                tsis.append(tsi)

        self._swdb_commit(tsis)

    def _install_test_group(self):
        """Group installation itself does not handle packages. We need to
           handle them manually for proper functionality of group remove"""
        group_id = 'somerset'
        self.base.group_install(group_id, ('mandatory',))
        swdb_group = self.history.group._installed[group_id]
        tsis = []
        for swdb_pkg in swdb_group.getPackages():
            swdb_pkg.setInstalled(True)
            pkgs = self.base.sack.query().filter(name=swdb_pkg.getName(), arch="x86_64").run()
            if not pkgs:
                continue
            pkg = pkgs[0]
            pkg._force_swdb_repoid = "main"
            self.history.rpm.add_install(pkg, reason=libdnf.transaction.TransactionItemReason_GROUP)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_GROUP
#            )
#            tsis.append(tsi)

        self._swdb_commit(tsis)
        self.base.reset(goal=True)

    def test_env_group_remove(self):
        self._install_test_env()
        env_id = 'sugar-desktop-environment'
        pkg_count = self.base.env_group_remove([env_id])
        self._swdb_commit()
        self.assertEqual(3, pkg_count)
        with tests.support.mock.patch('logging.Logger.error'):
            self.assertRaises(dnf.exceptions.Error,
                              self.base.env_group_remove,
                              ['nonexistent'])

    def test_environment_remove(self):
        self._install_test_env()
        env_id = 'sugar-desktop-environment'
        swdb_env = self.history.env.get(env_id)
        self.assertIsNotNone(swdb_env)
        self.assertEqual(swdb_env.getEnvironmentId(), 'sugar-desktop-environment')

        removed_pkg_count = self.base.environment_remove(env_id)
        self.assertGreater(removed_pkg_count, 0)
        self._swdb_commit()

        swdb_env = self.history.env.get(env_id)
        self.assertIsNone(swdb_env)

        peppers = self.history.group.get('Peppers')
        self.assertIsNone(peppers)

        somerset = self.history.group.get('somerset')
        self.assertIsNone(somerset)

    def test_env_upgrade(self):
        self._install_test_env()
        cnt = self.base.environment_upgrade("sugar-desktop-environment")
        self.assertEqual(5, cnt)

        peppers = self.history.group.get('Peppers')
        self.assertIsNotNone(peppers)

        somerset = self.history.group.get('somerset')
        self.assertIsNotNone(somerset)

    def test_group_install(self):
        comps_group = self.base.comps.group_by_pattern('Base')
        pkg_count = self.base.group_install(comps_group.id, ('mandatory',))
        self.assertEqual(pkg_count, 2)
        self._swdb_commit()

        installed, removed = self.installed_removed(self.base)
        self.assertEmpty(installed)
        self.assertEmpty(removed)
        swdb_group = self.history.group.get(comps_group.id)
        self.assertIsNotNone(swdb_group)

    def test_group_remove(self):
        self._install_test_group()
        group_id = 'somerset'

        pkgs_removed = self.base.group_remove(group_id)
        self.assertGreater(pkgs_removed, 0)

        self._swdb_begin()
        installed, removed = self.installed_removed(self.base)
        self.assertEmpty(installed)
        self.assertCountEqual([pkg.name for pkg in removed], ('pepper',))
        self._swdb_end()


class ProblemGroupTest(tests.support.ResultTestCase):
    """Test some cases involving problems in groups: packages that
    don't exist, and packages that exist but cannot be installed. The
    "broken" group lists three packages. "meaning-of-life", explicitly
    'default', does not exist. "lotus", implicitly 'mandatory' (no
    explicit type), exists and is installable. "brokendeps",
    explicitly 'optional', exists but has broken dependencies. See
    https://bugzilla.redhat.com/show_bug.cgi?id=1292892,
    https://bugzilla.redhat.com/show_bug.cgi?id=1337731,
    https://bugzilla.redhat.com/show_bug.cgi?id=1427365, and
    https://bugzilla.redhat.com/show_bug.cgi?id=1461539 for some of
    the background on this.
    """

    REPOS = ['main', 'broken_group']
    COMPS = True
    COMPS_SEED_PERSISTOR = True

    def test_group_install_broken_mandatory(self):
        """Here we will test installing the group with only mandatory
        packages. We expect this to succeed, leaving out the
        non-existent 'meaning-of-life': it should also log a warning,
        but we don't test that.
        """
        comps_group = self.base.comps.group_by_pattern('Broken Group')
        swdb_group = self.history.group.get(comps_group.id)
        self.assertIsNone(swdb_group)

        cnt = self.base.group_install(comps_group.id, ('mandatory'))
        self._swdb_commit()
        self.base.resolve()
        # this counts packages *listed* in the group, so 2
        self.assertEqual(cnt, 2)

        inst, removed = self.installed_removed(self.base)
        # the above should work, but only 'lotus' actually installed
        self.assertLength(inst, 1)
        self.assertEmpty(removed)

    def test_group_install_broken_default(self):
        """Here we will test installing the group with only mandatory
        and default packages. Again we expect this to succeed: the new
        factor is an entry pulling in librita if no-such-package is
        also included or installed. We expect this not to actually
        pull in librita (as no-such-package obviously *isn't* there),
        but also not to cause a fatal error.
        """
        comps_group = self.base.comps.group_by_pattern('Broken Group')
        swdb_group = self.history.group.get(comps_group.id)
        self.assertIsNone(swdb_group)

        cnt = self.base.group_install(comps_group.id, ('mandatory', 'default'))
        self._swdb_commit()
        self.base.resolve()
        # this counts packages *listed* in the group, so 3
        self.assertEqual(cnt, 3)

        inst, removed = self.installed_removed(self.base)
        # the above should work, but only 'lotus' actually installed
        self.assertLength(inst, 1)
        self.assertEmpty(removed)

    def test_group_install_broken_optional(self):
        """Here we test installing the group with optional packages
        included. We expect this to fail, as a package that exists but
        has broken dependencies is now included.
        """
        comps_group = self.base.comps.group_by_pattern('Broken Group')
        swdb_group = self.history.group.get(comps_group.id)
        self.assertIsNone(swdb_group)

        cnt = self.base.group_install(comps_group.id, ('mandatory', 'default', 'optional'))
        self.assertEqual(cnt, 4)

        self._swdb_commit()
        # this should fail, as optional 'brokendeps' is now pulled in
        self.assertRaises(dnf.exceptions.DepsolveError, self.base.resolve)

    def test_group_install_broken_optional_nonstrict(self):
        """Here we test installing the group with optional packages
        included, but with strict=False. We expect this to succeed,
        skipping the package with broken dependencies.
        """
        comps_group = self.base.comps.group_by_pattern('Broken Group')
        swdb_group = self.history.group.get(comps_group.id)
        self.assertIsNone(swdb_group)

        cnt = self.base.group_install(comps_group.id, ('mandatory', 'default', 'optional'),
                                      strict=False)
        self._swdb_commit()
        self.base.resolve()
        self.assertEqual(cnt, 4)

        inst, removed = self.installed_removed(self.base)
        # the above should work, but only 'lotus' actually installed
        self.assertLength(inst, 1)
        self.assertEmpty(removed)

    def test_group_install_missing_name(self):
        comps_group = self.base.comps.group_by_pattern('missing-name-group')

        cnt = self.base.group_install(comps_group.id, ('mandatory', 'default', 'optional'),
                                      strict=False)
        self._swdb_commit()
        self.base.resolve()
        self.assertEqual(cnt, 1)


class EnvironmentInstallTest(tests.support.ResultTestCase):
    """Set up a test where sugar is considered not installed."""

    REPOS = ['main']
    COMPS = True
    COMPS_SEED_HISTORY = True

    def test_environment_install(self):
        env_id = 'sugar-desktop-environment'
        comps_env = self.comps.environment_by_pattern(env_id)
        self.base.environment_install(comps_env.id, ('mandatory',))
        self._swdb_commit()

        installed, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(operator.attrgetter('name'), installed),
                              ('trampoline', 'lotus'))

        swdb_env = self.history.env.get(env_id)
        self.assertCountEqual([i.getGroupId() for i in swdb_env.getGroups()], ('somerset', 'Peppers', 'base'))

        peppers = self.history.group.get('Peppers')
        self.assertIsNotNone(peppers)

        somerset = self.history.group.get('somerset')
        self.assertIsNotNone(somerset)

        base = self.history.group.get('base')
        self.assertIsNone(base)
