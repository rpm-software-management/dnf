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

import dnf.util
import warnings

class GroupTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base.read_mock_comps(support.COMPS_PATH)

    def test_environment_list(self):
        env_inst, env_avail = self.base._environment_list(['sugar*'])
        self.assertLength(env_inst, 1)
        self.assertLength(env_avail, 0)
        self.assertEqual(env_inst[0].name, 'Sugar Desktop Environment')

    def test_environment_remove(self):
        comps = self.base.comps
        env = comps.environment_by_pattern("sugar-desktop-environment")
        self.assertEqual(self.base.environment_remove(env), 1)
        self.assertEmpty(comps._installed_groups)
        self.assertEmpty(comps._installed_environments)

    def test_install(self):
        comps = self.base.comps
        grp = dnf.util.first(comps.groups_by_pattern("Solid Ground"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.assertEqual(self.base.select_group(grp), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertItemsEqual([pkg.name for pkg in inst], ("trampoline",))
        self.assertLength(removed, 0)

    def test_group_install(self):
        comps = self.base.comps
        installed_groups = self.base.comps._installed_groups
        grp = comps.group_by_pattern("Solid Ground")
        self.assertNotIn(grp.id, installed_groups)

        self.assertEqual(self.base.group_install(grp, ('mandatory',)), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertItemsEqual([pkg.name for pkg in inst], ("trampoline",))
        self.assertLength(removed, 0)
        # does not contain the already installed 'pepper':
        self.assertEqual(installed_groups[grp.id], ['trampoline'])

    def test_group_install_exclude(self):
        comps = self.base.comps
        installed_groups = self.base.comps._installed_groups
        grp = dnf.util.first(comps.groups_by_pattern('somerset'))

        cnt = self.base.group_install(grp, ('optional',), exclude=('lotus',))
        self.assertEqual(cnt, 0)

    def test_group_remove(self):
        grp = self.base.comps.group_by_pattern('Base')
        self.assertIn(grp.id, self.base.comps._installed_groups)

        self.assertEqual(self.base.group_remove(grp), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertLength(inst, 0)
        self.assertItemsEqual([pkg.name for pkg in removed], ('pepper',))
        self.assertNotIn(grp.id, self.base.comps._installed_groups)

class EnvironmentInstallTest(support.ResultTestCase):
    def setUp(self):
        """Set up a test where sugar is considered not installed."""
        self.base = support.MockBase("main")
        self.base.read_mock_comps(support.COMPS_PATH)
        comps = self.base.comps
        comps._installed_environments.pop('sugar-desktop-environment')

    def test_environment_install(self):
        comps = self.base.comps
        original_groups = set(comps._installed_groups.keys())
        env = comps.environment_by_pattern("sugar-desktop-environment")
        self.base.environment_install(env, ('mandatory',))
        new_groups = set(comps._installed_groups.keys()) - original_groups
        self.assertIn('somerset', new_groups)
        self.assertIn('Peppers', new_groups)
        self.assertIn('sugar-desktop-environment', comps._installed_environments)
