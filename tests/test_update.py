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
from __future__ import unicode_literals
from tests import support
from tests.support import mock

import dnf
import dnf.util
import hawkey
import itertools
import tests.test_repo

class Update(support.ResultTestCase):
    def test_update(self):
        """ Simple update. """
        base = support.MockBase("updates")
        ret = base.upgrade("pepper")
        new_versions = base.sack.query().upgrades().filter(name="pepper")
        other_installed = base.sack.query().installed().filter(name__neq="pepper")
        expected = other_installed.run() + new_versions.run()
        self.assertResult(base, expected)

    def test_update_not_found(self):
        base = dnf.Base()
        base._sack = support.mock_sack('updates')
        base._goal = goal = mock.create_autospec(hawkey.Goal)

        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            base.upgrade('non-existent')
        self.assertEqual(context.exception.pkg_spec, 'non-existent')
        self.assertEqual(goal.mock_calls, [])

    def test_update_not_installed(self):
        """ Updating an uninstalled package is a void operation. """
        base = support.MockBase("main")
        # no "mrkite" installed:
        base.upgrade("mrkite")
        self.assertResult(base, base.sack.query().installed().run())

    def test_update_all(self):
        """ Update all you can. """
        base = support.MockBase("main", "updates")
        sack = base.sack
        base.upgrade_all()
        expected = support.installed_but(sack, "pepper", "hole", "tour") + \
            list(sack.query().available().nevra("pepper-20-1.x86_64")) + \
            list(sack.query().available().nevra("hole-2-1.x86_64"))
        self.assertResult(base, expected)

    def test_upgrade_all_reponame(self):
        """Test whether only packages in selected repo are upgraded."""
        base = support.MockBase('updates', 'third_party')
        base.init_sack()

        base.upgrade_all('third_party')

        self.assertResult(base, itertools.chain(
            base.sack.query().installed().filter(name__neq='hole'),
            base.sack.query().upgrades().filter(reponame='third_party')))

    def test_upgrade_to_package(self):
        base = support.MockBase()
        pkg = base.add_remote_rpm(support.TOUR_51_PKG_PATH)
        cnt = base.package_upgrade(pkg)
        self.assertEqual(cnt, 1)
        new_pkg = base.sack.query().available().filter(name="tour")[0]
        new_set = support.installed_but(base.sack, "tour") + [new_pkg]
        self.assertResult(base, new_set)

    def test_update_arches(self):
        base = support.MockBase("main", "updates")
        base.upgrade("hole")
        installed, removed = self.installed_removed(base)
        self.assertItemsEqual(map(str, installed), ['hole-2-1.x86_64'])
        self.assertItemsEqual(map(str, removed),
                              ['hole-1-1.x86_64', 'tour-5-0.noarch'])

    def test_upgrade_reponame(self):
        """Test whether only packages in selected repo are upgraded."""
        base = support.MockBase('updates', 'broken_deps')
        base.logger = mock.Mock()

        base.upgrade('*e*', 'broken_deps')

        installed, removed = self.installed_removed(base)
        # Sack contains two upgrades with the same version. Because of that
        # test whether the installed package is one of those packages.
        self.assertLength(installed, 1)
        self.assertIn(
            dnf.util.first(installed),
            base.sack.query().upgrades().filter(name='pepper'))
        self.assertItemsEqual(
            removed,
            base.sack.query().installed().filter(name='pepper'))
        assert dnf.subject.Subject('*e*').get_best_query(base.sack).upgrades().filter(name__neq='pepper', reponame__neq='broken_deps'), \
               ('in another repo, there must be another update matching the '
                'pattern, otherwise the test makes no sense')

    def test_upgrade_reponame_not_in_repo(self):
        """Test whether no packages are upgraded if bad repo is selected."""
        base = support.MockBase('updates', 'broken_deps')

        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            base.upgrade('hole', 'broken_deps')

        self.assertEqual(context.exception.pkg_spec, 'hole')
        self.assertResult(base, base.sack.query().installed())
        assert dnf.subject.Subject('hole').get_best_query(base.sack).upgrades().filter(reponame__neq='broken_deps'), \
               ('in another repo, there must be an update matching the '
                'pattern, otherwise the test makes no sense')

class SkipBroken(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("broken_deps")
        self.sack = self.base.sack

    def test_upgrade_all(self):
        """ upgrade() without parameters upgrade everything it can that has its
            deps in trim. Broken packages are silently skipped.
        """
        self.base.upgrade_all()
        new_set = support.installed_but(self.sack, "pepper").run()
        new_set.extend(self.sack.query().available().nevra("pepper-20-1.x86_64"))
        self.assertResult(self.base, new_set)

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
        base.upgrade("tour")
        (installed, _) = self.installed_removed(base)
        self.assertEqual('r1', dnf.util.first(installed).reponame)
