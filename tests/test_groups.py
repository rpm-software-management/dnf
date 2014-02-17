# Copyright (C) 2012-2014  Red Hat, Inc.
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
from tests import support
import operator
import dnf.util

class SelectGroupTest(support.ResultTestCase):

    ENABLED_REPONAME = 'main'

    DISABLED_REPONAME = 'broken_deps'

    def setUp(self):
        self.base = support.MockBase(self.ENABLED_REPONAME)
        self.base.read_mock_comps(support.COMPS_PATH)

    def test_install(self):
        comps = self.base.comps
        grp = dnf.util.first(comps.groups_by_pattern("Solid Ground"))
        self.assertEqual(self.base.select_group(grp), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertItemsEqual([pkg.name for pkg in inst], ("trampoline",))
        self.assertLength(removed, 0)

    def test_install_reponame_disabled(self):
        """Test whether packages are not installed if selected repo is disabled."""
        comps = self.base.comps
        grp = dnf.util.first(comps.groups_by_pattern('Solid Ground'))

        count = self.base.select_group(grp, reponame=self.DISABLED_REPONAME)

        self.assertEqual(count, 0)
        installed, removed = self.installed_removed(self.base)
        self.assertItemsEqual(installed, ())
        self.assertItemsEqual(removed, ())

    def test_install_reponame_enabled(self):
        """Test whether packages are installed if selected repo is enabled."""
        comps = self.base.comps
        grp = dnf.util.first(comps.groups_by_pattern('Solid Ground'))

        count = self.base.select_group(grp, reponame=self.ENABLED_REPONAME)

        self.assertEqual(count, 1)
        installed, removed = self.installed_removed(self.base)
        self.assertItemsEqual(
            installed,
            dnf.subject.Subject('trampoline').get_best_query(self.base.sack).filter(reponame=self.ENABLED_REPONAME))
        self.assertItemsEqual(removed, ())

    def test_group_remove(self):
        self.assertEqual(self.base.group_remove('Solid Ground'), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertLength(inst, 0)
        self.assertItemsEqual([pkg.name for pkg in removed], ('pepper',))

    def test_environment_list(self):
        l = self.base._environment_list(['sugar*'])
        self.assertLength(l, 1)
        self.assertEqual(l[0].name, 'Sugar Desktop Environment')
