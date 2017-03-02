# Copyright (C) 2012-2016 Red Hat, Inc.
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
from tests import support

import dnf.comps
import dnf.util
import operator
import warnings


class EmptyPersistorTest(support.ResultTestCase):
    """Test group operations with empty persistor."""

    def setUp(self):
        self.base = support.MockBase('main')
        self.base.read_mock_comps(False)
        self.base.init_sack()

    def test_group_install_exclude(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
        cnt = self.base.group_install(grp.id, ('optional',), exclude=('lotus',))
        self.assertEqual(cnt, 0)

    @support.mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_group_install_locale(self, _unused):
        comps = self.base.comps
        grp = comps.group_by_pattern('Kritick\xe1 cesta (Z\xe1klad)')
        cnt = self.base.group_install(grp.id, ('mandatory',))
        self.assertEqual(cnt, 2)

    def test_group_install_exclude_glob(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
        cnt = self.base.group_install(grp.id, ('optional',), exclude=('lo*',))
        self.assertEqual(cnt, 0)

    def test_group_install_exclude_notexist(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
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

class PresetPersistorTest(support.ResultTestCase):
    """Test group operations with some data in the persistor."""

    def setUp(self):
        self.base = support.MockBase("main")
        self.prst = self.base.history.activate_group()
        self.base.read_mock_comps()
        self.base.init_sack()

    def _install_test_env(self):
        """Env installation itself does not handle packages. We need to handle
           them manually for proper functionality of env remove"""
        history = self.base.history
        self.base.environment_install(
            'sugar-desktop-environment',
            ('mandatory',))
        self.prst.commit()
        env = self.prst.environment('sugar-desktop-environment')
        groups = env.get_group_list()
        for group in groups:
            _group = self.prst.group(group)
            for pkg in _group.get_full_list():
                swdb_pkg = history.package()
                swdb_pkg.name = pkg
                pid = history.add_package(swdb_pkg)
                history.swdb.trans_data_beg(1, pid, "group", "Installed")

    def _install_test_group(self):
        """Group installation itself does not handle packages. We need to
           handle them manually for proper functionality of group remove"""
        history = self.base.history
        self.base.group_install('somerset', ('mandatory',))
        self.prst.commit()
        group = self.prst.group('somerset')
        for pkg in group.get_full_list():
            swdb_pkg = history.package()
            swdb_pkg.name = pkg
            pid = history.add_package(swdb_pkg)
            history.swdb.trans_data_beg(1, pid, "group", "Installed")

    def test_env_group_remove(self):
        self._install_test_env()
        cnt = self.base.env_group_remove(["sugar-desktop-environment"])
        self.prst.commit()
        self.assertEqual(3, cnt)
        with support.mock.patch('logging.Logger.error') as log:
            self.assertRaises(dnf.exceptions.Error,
                              self.base.env_group_remove,
                              ['nonexistent'])

    def test_environment_remove(self):
        self._install_test_env()
        env_id = self.prst.environment('sugar-desktop-environment')
        self.assertEqual(env_id.name_id, 'sugar-desktop-environment')
        self.assertTrue(env_id.is_installed())
        self.assertGreater(self.base.environment_remove(env_id), 0)
        self.prst.commit()
        p_env = self.prst.environment(env_id)
        self.assertFalse(p_env.is_installed())
        peppers = self.prst.group('Peppers')
        somerset = self.prst.group('somerset')
        self.assertFalse(peppers.is_installed)
        self.assertFalse(somerset.is_installed)

    def test_env_upgrade(self):
        self._install_test_env()
        cnt = self.base.environment_upgrade("sugar-desktop-environment")
        self.assertEqual(5, cnt)
        peppers = self.prst.group('Peppers')
        somerset = self.prst.group('somerset')
        self.assertTrue(peppers.is_installed)
        self.assertTrue(somerset.is_installed)

    def test_group_install(self):
        grp = self.base.comps.group_by_pattern('Base')
        p_grp = self.prst.group('base')
        self.assertEqual(self.base.group_install(grp.id, ('mandatory',)), 2)
        self.prst.commit()
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertEmpty(removed)
        p_grp = self.prst.group('base')
        self.assertTrue(p_grp.is_installed)

    """
    this should be reconsidered once relengs document comps
    def test_group_install_broken(self):
        prst = self.base._group_persistor
        grp = self.base.comps.group_by_pattern('Broken Group')
        p_grp = prst.group('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertRaises(dnf.exceptions.MarkingError,
                          self.base.group_install, grp.id,
                          ('mandatory', 'default'))
        p_grp = prst.group('broken-group')
        self.assertFalse(p_grp.installed)

        self.assertEqual(self.base.group_install(grp.id,
                                                 ('mandatory', 'default'),
                                                 strict=False), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertLength(inst, 1)
        self.assertEmpty(removed)
        p_grp = prst.group('broken-group')
        self.assertTrue(p_grp.installed)
    """

    def test_group_remove(self):
        self._install_test_group()
        self.assertGreater(self.base.group_remove("somerset"), 0)
        self.prst.commit()
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertCountEqual([pkg.name for pkg in removed], ('pepper',))
        p_grp = self.prst.group('somerset')
        self.assertFalse(p_grp.is_installed)


class EnvironmentInstallTest(support.ResultTestCase):
    def setUp(self):
        """Set up a test where sugar is considered not installed."""
        self.base = support.MockBase("main")
        self.base.init_sack()
        self.base.read_mock_comps()
        self.prst = self.base.history.activate_group()

    def test_environment_install(self):
        comps = self.base.comps
        env = comps.environment_by_pattern("sugar-desktop-environment")
        self.base.environment_install(env.id, ('mandatory',))
        self.prst.commit()
        installed, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(operator.attrgetter('name'), installed),
                              ('trampoline', 'lotus'))

        p_env = self.prst.environment('sugar-desktop-environment')
        self.assertCountEqual(p_env.get_group_list(), ('somerset', 'Peppers'))
        self.assertTrue(p_env.is_installed())

        peppers = self.prst.group('Peppers')
        somerset = self.prst.group('somerset')
        self.assertTrue(all((peppers.is_installed, somerset.is_installed)))
