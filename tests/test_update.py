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
from tests import mock
from tests import support

import dnf
import dnf.util
import hawkey
import tests.test_repo

class Update(support.ResultTestCase):
    def test_update(self):
        """ Simple update. """
        yumbase = support.MockBase("updates")
        ret = yumbase.update("pepper")
        new_versions = yumbase.sack.query().upgrades().filter(name="pepper")
        other_installed = yumbase.sack.query().installed().filter(name__neq="pepper")
        expected = other_installed.run() + new_versions.run()
        self.assertResult(yumbase, expected)

    def test_update_not_found(self):
        base = dnf.Base()
        base._sack = support.mock_sack('updates')
        base._goal = goal = mock.create_autospec(hawkey.Goal)

        self.assertRaises(dnf.exceptions.PackageNotFoundError,
                          base.update, 'non-existent')
        self.assertEqual(goal.mock_calls, [])

    def test_update_not_installed(self):
        """ Updating an uninstalled package is a void operation. """
        yumbase = support.MockBase("main")
        # no "mrkite" installed:
        yumbase.update("mrkite")
        self.assertResult(yumbase, yumbase.sack.query().installed().run())

    def test_update_all(self):
        """ Update all you can. """
        yumbase = support.MockBase("main", "updates")
        sack = yumbase.sack
        yumbase.update_all()
        expected = support.installed_but(sack, "pepper", "hole", "tour") + \
            list(sack.query().available().nevra("pepper-20-1.x86_64")) + \
            list(sack.query().available().nevra("hole-2-1.x86_64"))
        self.assertResult(yumbase, expected)

    def test_update_local(self):
        yumbase = support.MockBase()
        sack = yumbase.sack
        cnt = yumbase.update_local(support.TOUR_51_PKG_PATH)
        self.assertEqual(cnt, 1)
        new_pkg = sack.query().available().filter(name="tour")[0]
        new_set = support.installed_but(yumbase.sack, "tour") + [new_pkg]
        self.assertResult(yumbase, new_set)

    def test_update_arches(self):
        yumbase = support.MockBase("main", "updates")
        yumbase.update("hole")
        installed, removed = self.installed_removed(yumbase)
        self.assertItemsEqual(map(str, installed), ['hole-2-1.x86_64'])
        self.assertItemsEqual(map(str, removed),
                              ['hole-1-1.x86_64', 'tour-5-0.noarch'])

class SkipBroken(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("broken_deps")
        self.sack = self.yumbase.sack

    def test_update_all(self):
        """ update() without parameters update everything it can that has its
            deps in trim. Broken packages are silently skipped.
        """
        self.yumbase.update_all()
        new_set = support.installed_but(self.sack, "pepper").run()
        new_set.extend(self.sack.query().available().nevra("pepper-20-1.x86_64"))
        self.assertResult(self.yumbase, new_set)

class CostUpdate(tests.test_repo.RepoTestMixin, support.ResultTestCase):
    def test_cost(self):
        """Test the repo costs are respected."""
        r1 = self.build_repo('r1')
        r2 = self.build_repo('r2')
        r1.cost = 500
        r2.cost = 700

        base = support.MockBase()
        base.init_sack()
        base.repos.add(r1)
        base.repos.add(r2)
        base._add_repo_to_sack('r1')
        base._add_repo_to_sack('r2')
        base.update("tour")
        (installed, _) = self.installed_removed(base)
        self.assertEqual('r1', dnf.util.first(installed).reponame)
