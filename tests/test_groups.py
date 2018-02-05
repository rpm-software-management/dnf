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

from hawkey import SwdbReason, SwdbPkg, SwdbItem

import dnf.comps
import dnf.util

import tests.support
from tests.support import mock


class EmptyPersistorTest(tests.support.ResultTestCase):
    """Test group operations with empty persistor."""

    REPOS = ['main']
    COMPS = True
    COMPS_SEED_PERSISTOR = False

    def test_group_install_exclude(self):
        grp = self.comps.group_by_pattern('somerset')
        cnt = self.base.group_install(grp.id, ('optional',), exclude=('lotus',))
        self.assertEqual(cnt, 0)

    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_group_install_locale(self, _unused):
        grp = self.comps.group_by_pattern('Kritick\xe1 cesta (Z\xe1klad)')
        cnt = self.base.group_install(grp.id, ('mandatory',))
        self.assertEqual(cnt, 2)

    def test_group_install_exclude_glob(self):
        grp = self.comps.group_by_pattern('somerset')
        cnt = self.base.group_install(grp.id, ('optional',), exclude=('lo*',))
        self.assertEqual(cnt, 0)

    def test_group_install_exclude_notexist(self):
        grp = self.comps.group_by_pattern('somerset')
        cnt = self.base.group_install(grp.id, ('optional',), exclude=('x*',))
        self.assertEqual(cnt, 1)

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
    COMPS_SEED_PERSISTOR = True

    def _install_test_env(self):
        """Env installation itself does not handle packages. We need to handle
           them manually for proper functionality of env remove"""

        env = self.persistor.environment('sugar-desktop-environment')
        self.base.environment_install(env.name_id, ('mandatory',))
        self.persistor.commit()
        groups = env.get_group_list()
        for group in groups:
            _group = self.persistor.group(group)
            for pkg in _group.get_full_list():
                swdb_pkg = SwdbPkg.new(pkg, 0, "0", "0", "x86_64", "", "", SwdbItem.RPM)
                pid = self.history.add_package(swdb_pkg)
                self.history.swdb.trans_data_beg(1, pid, SwdbReason.GROUP, "Installed", False)

    def _install_test_group(self):
        """Group installation itself does not handle packages. We need to
           handle them manually for proper functionality of group remove"""

        group = self.persistor.group('somerset')

        self.base.group_install(group.name_id, ('mandatory',))
        self.persistor.commit()

        for pkg in group.get_full_list():
            swdb_pkg = SwdbPkg.new(pkg, 0, "20", "0", "x86_64", "", "", SwdbItem.RPM)
            pid = self.history.add_package(swdb_pkg)
            self.history.swdb.trans_data_beg(1, pid, SwdbReason.GROUP, "Installed", False)

        self.base.reset(goal=True)

    def test_env_group_remove(self):
        self._install_test_env()
        cnt = self.base.env_group_remove(["sugar-desktop-environment"])
        self.persistor.commit()
        self.assertEqual(3, cnt)
        with tests.support.mock.patch('logging.Logger.error'):
            self.assertRaises(dnf.exceptions.Error,
                              self.base.env_group_remove,
                              ['nonexistent'])

    def test_environment_remove(self):
        self._install_test_env()
        env_id = self.persistor.environment('sugar-desktop-environment')
        self.assertEqual(env_id.name_id, 'sugar-desktop-environment')
        self.assertTrue(env_id.installed)
        self.assertGreater(self.base.environment_remove(env_id), 0)
        self.persistor.commit()
        p_env = self.persistor.environment(env_id)
        self.assertFalse(p_env.installed)
        peppers = self.persistor.group('Peppers')
        somerset = self.persistor.group('somerset')
        self.assertFalse(peppers.installed)
        self.assertFalse(somerset.installed)

    def test_env_upgrade(self):
        self._install_test_env()
        cnt = self.base.environment_upgrade("sugar-desktop-environment")
        self.assertEqual(5, cnt)
        peppers = self.persistor.group('Peppers')
        somerset = self.persistor.group('somerset')
        self.assertTrue(peppers.installed)
        self.assertTrue(somerset.installed)

    def test_group_install(self):
        grp = self.base.comps.group_by_pattern('Base')
        self.assertEqual(self.base.group_install(grp.id, ('mandatory',)), 2)
        self.persistor.commit()
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertEmpty(removed)
        p_grp = self.persistor.group('base')
        self.assertTrue(p_grp.installed)

    """
    this should be reconsidered once relengs document comps
    def test_group_install_broken(self):
        grp = self.base.comps.group_by_pattern('Broken Group')
        p_grp = self.persistor.group('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertRaises(dnf.exceptions.MarkingError,
                          self.base.group_install, grp.id,
                          ('mandatory', 'default'))
        p_grp = self.persistor.group('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertEqual(self.base.group_install(grp.id,
                                                 ('mandatory', 'default'),
                                                 strict=False), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertLength(inst, 1)
        self.assertEmpty(removed)
        p_grp = self.persistor.group('broken-group')
        self.assertTrue(p_grp.installed)
    """

    def test_group_remove(self):
        self._install_test_group()

        p_grp = self.persistor.group('somerset')
        self.assertGreater(self.base.group_remove(p_grp.name_id), 0)
        self.persistor.commit()

        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertCountEqual([pkg.name for pkg in removed], ('pepper',))

        p_grp = self.persistor.group(p_grp.name_id)
        self.assertFalse(p_grp.installed)


class EnvironmentInstallTest(tests.support.ResultTestCase):
    """Set up a test where sugar is considered not installed."""

    REPOS = ['main']
    COMPS = True
    COMPS_SEED_PERSISTOR = True

    def test_environment_install(self):
        env = self.comps.environment_by_pattern("sugar-desktop-environment")
        self.base.environment_install(env.id, ('mandatory',))
        self.persistor.commit()
        installed, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(operator.attrgetter('name'), installed),
                              ('trampoline', 'lotus'))

        p_env = self.persistor.environment('sugar-desktop-environment')
        self.assertCountEqual(p_env.get_group_list(), ('somerset', 'Peppers'))
        self.assertTrue(p_env.installed)

        peppers = self.persistor.group('Peppers')
        somerset = self.persistor.group('somerset')
        self.assertTrue(all((peppers.installed, somerset.installed)))
