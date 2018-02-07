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

import libdnf.swdb

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
                tsi = dnf.transaction.TransactionItem(
                    dnf.transaction.INSTALL,
                    installed=pkg,
                    reason=libdnf.swdb.TransactionItemReason_GROUP
                )
                tsis.append(tsi)

        self._swdb_commit(tsis)

    def _install_test_group(self):
        """Group installation itself does not handle packages. We need to
           handle them manually for proper functionality of group remove"""
        group_id = 'somerset'
        self.base.group_install(group_id, ('mandatory',))
        swdb_group = self.history.group.installed[group_id]
        tsis = []
        for swdb_pkg in swdb_group.getPackages():
            swdb_pkg.setInstalled(True)
            pkgs = self.base.sack.query().filter(name=swdb_pkg.getName(), arch="x86_64").run()
            if not pkgs:
                continue
            pkg = pkgs[0]
            pkg._force_swdb_repoid = "main"
            tsi = dnf.transaction.TransactionItem(
                dnf.transaction.INSTALL,
                installed=pkg,
                reason=libdnf.swdb.TransactionItemReason_GROUP
            )
            tsis.append(tsi)

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

    """
    this should be reconsidered once relengs document comps
    def test_group_install_broken(self):
        grp = self.base.comps.group_by_pattern('Broken Group')
        p_grp = self.history.group.get('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertRaises(dnf.exceptions.MarkingError,
                          self.base.group_install, grp.id,
                          ('mandatory', 'default'))
        p_grp = self.history.group.get('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertEqual(self.base.group_install(grp.id,
                                                 ('mandatory', 'default'),
                                                 strict=False), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertLength(inst, 1)
        self.assertEmpty(removed)
        p_grp = self.history.group.get('broken-group')
        self.assertTrue(p_grp.installed)
    """

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
