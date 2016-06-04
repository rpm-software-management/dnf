# Copyright (C) 2012-2013  Red Hat, Inc.
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

    def test_add_comps_trans(self):
        trans = dnf.comps.TransactionBunch()
        trans.install.add('trampoline')
        self.assertGreater(self.base._add_comps_trans(trans), 0)
        self.assertIn('trampoline', self.base._goal.group_members)
        (installed, removed) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed), ('trampoline-2.1-1.noarch',))
        self.assertEmpty(removed)

        trans = dnf.comps.TransactionBunch()
        trans.install_opt.add('waltz')
        self.assertEqual(self.base._add_comps_trans(trans), 0)


class PresetPersistorTest(support.ResultTestCase):
    """Test group operations with some data in the persistor."""

    def setUp(self):
        self.base = support.MockBase("main")
        self.base.read_mock_comps()
        self.base.init_sack()

    def test_env_group_remove(self):
        cnt = self.base.env_group_remove(["sugar-desktop-environment"])
        self.assertEqual(3, cnt)
        self.assertRaises(dnf.exceptions.Error,
                          self.base.env_group_remove,
                          ['nonexistent'])

    def test_environment_remove(self):
        prst = self.base._group_persistor
        env_ids = prst.environments_by_pattern("sugar-desktop-environment")
        self.assertEqual(env_ids, set(['sugar-desktop-environment']))
        env_id = dnf.util.first(env_ids)
        self.assertGreater(self.base.environment_remove(env_id), 0)
        p_env = prst.environment(env_id)
        self.assertFalse(p_env.installed)
        peppers = prst.group('Peppers')
        somerset = prst.group('somerset')
        self.assertFalse(peppers.installed)
        self.assertFalse(somerset.installed)

    def test_env_upgrade(self):
        prst = self.base._group_persistor
        cnt = self.base.environment_upgrade("sugar-desktop-environment")
        self.assertEqual(4, cnt)
        peppers = prst.group('Peppers')
        somerset = prst.group('somerset')
        self.assertTrue(peppers.installed)
        self.assertTrue(somerset.installed)

    def test_group_install(self):
        prst = self.base._group_persistor
        grp = self.base.comps.group_by_pattern('Base')
        p_grp = prst.group('base')
        self.assertFalse(p_grp.installed)

        self.assertEqual(self.base.group_install(grp.id, ('mandatory',)), 2)
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertEmpty(removed)
        self.assertTrue(p_grp.installed)

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

    def test_group_remove(self):
        prst = self.base._group_persistor
        grp_ids = prst.groups_by_pattern('somerset')
        self.assertEqual(grp_ids, set(['somerset']))
        grp_id = dnf.util.first(grp_ids)
        p_grp = prst.group('somerset')

        self.assertGreater(self.base.group_remove(grp_id), 0)
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertCountEqual([pkg.name for pkg in removed], ('pepper',))
        self.assertFalse(p_grp.installed)


class EnvironmentInstallTest(support.ResultTestCase):
    def setUp(self):
        """Set up a test where sugar is considered not installed."""
        self.base = support.MockBase("main")
        self.base.init_sack()
        self.base.read_mock_comps()
        self.prst = self.base._group_persistor
        p_env = self.prst.environment('sugar-desktop-environment')
        p_env.pkg_types = 0
        p_env.grp_types = 0
        del p_env.full_list[:]
        p_grp = self.prst.group('somerset')
        p_grp.pkg_types = 0
        del p_grp.full_list[:]

    def test_environment_install(self):
        comps = self.base.comps
        env = comps.environment_by_pattern("sugar-desktop-environment")
        self.base.environment_install(env.id, ('mandatory',))
        installed, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(operator.attrgetter('name'), installed),
                              ('trampoline',))

        p_env = self.prst.environment('sugar-desktop-environment')
        self.assertCountEqual(p_env.full_list, ('somerset', 'Peppers'))
        self.assertTrue(p_env.installed)

        peppers = self.prst.group('Peppers')
        somerset = self.prst.group('somerset')
        self.assertTrue(all((peppers.installed, somerset.installed)))


class EmptyPersistorTestDeprecated(support.ResultTestCase):
    """Test group operations with empty persistor."""
    # testing deprecated interface
    # remove in dnf-2.0.0

    def setUp(self):
        self.base = support.MockBase('main')
        self.base.read_mock_comps(False)
        self.base.init_sack()

    def test_group_install_exclude(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cnt = self.base.group_install(grp, ('optional',), exclude=('lotus',))
            self.assertEqual(cnt, 0)

    @support.mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_group_install_locale(self, _unused):
        comps = self.base.comps
        grp = comps.group_by_pattern('Kritick\xe1 cesta (Z\xe1klad)')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cnt = self.base.group_install(grp, ('mandatory',))
            self.assertEqual(cnt, 2)

    def test_group_install_exclude_glob(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cnt = self.base.group_install(grp, ('optional',), exclude=('lo*',))
            self.assertEqual(cnt, 0)

    def test_group_install_exclude_notexist(self):
        comps = self.base.comps
        grp = comps.group_by_pattern('somerset')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cnt = self.base.group_install(grp, ('optional',), exclude=('x*',))
            self.assertEqual(cnt, 1)


class PresetPersistorTestDeprecated(support.ResultTestCase):
    """Test group operations with some data in the persistor."""
    # testing deprecated interface
    # remove in dnf-2.0.0

    def setUp(self):
        self.base = support.MockBase("main")
        self.base.read_mock_comps()
        self.base.init_sack()

    def test_group_install(self):
        prst = self.base._group_persistor
        grp = self.base.comps.group_by_pattern('Base')
        p_grp = prst.group('base')
        self.assertFalse(p_grp.installed)
        with warnings.catch_warnings():
            self.assertEqual(self.base.group_install(grp.id, ('mandatory',)), 2)
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertEmpty(removed)
        self.assertTrue(p_grp.installed)

    def test_group_remove(self):
        prst = self.base._group_persistor
        grp_ids = prst.groups_by_pattern('somerset')
        self.assertEqual(grp_ids, set(['somerset']))
        grp_id = dnf.util.first(grp_ids)
        p_grp = prst.group('somerset')
        with warnings.catch_warnings():
            self.assertGreater(self.base.group_remove(grp_id), 0)
        inst, removed = self.installed_removed(self.base)
        self.assertEmpty(inst)
        self.assertCountEqual([pkg.name for pkg in removed], ('pepper',))
        self.assertFalse(p_grp.installed)
