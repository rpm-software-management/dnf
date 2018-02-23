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

import itertools

import dnf
import dnf.goal
import dnf.util

import tests.support
import tests.test_repo
from tests.support import mock


class Update(tests.support.ResultTestCase):

    REPOS = ['main', 'updates']
    INIT_SACK = True

    def test_update(self):
        """ Simple update. """
        self.base.upgrade("pepper")
        new_versions = self.sack.query().upgrades().filter(name="pepper")
        other_installed = self.sack.query().installed().filter(name__neq="pepper")
        expected = other_installed.run() + new_versions.run()
        self.assertResult(self.base, expected)

    def test_update_not_found(self):
        self.base._sack = tests.support.mock_sack('updates')
        self.base._goal = goal = mock.create_autospec(dnf.goal.Goal)

        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.upgrade('non-existent')
        self.assertEqual(context.exception.pkg_spec, 'non-existent')
        self.assertEqual(goal.mock_calls, [])

    @mock.patch('dnf.base.logger.warning')
    def test_update_not_installed(self, logger):
        """ Updating an uninstalled package is a not valid operation. """
        self.base._goal = goal = mock.create_autospec(dnf.goal.Goal)
        # no "mrkite" installed:
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.upgrade("mrkite")
        self.assertEqual(logger.mock_calls, [
            mock.call(u'Package %s available, but not installed.', u'mrkite')])
        self.assertEqual(context.exception.pkg_spec, 'mrkite')
        self.assertEqual(goal.mock_calls, [])

    def test_package_upgrade_fail(self):
        p = self.sack.query().available().filter(name="mrkite")[0]
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.package_upgrade(p)
        self.assertEqual(context.exception.pkg_spec, 'mrkite')
        self.base.resolve()
        self.assertEmpty(self.base._goal.list_upgrades())

        self.base.history.close()

        p = self.sack.query().available().filter(nevra="librita-1-1.x86_64")[0]
        self.assertEqual(0, self.base.package_upgrade(p))
        self.base.resolve()
        self.assertEmpty(self.base._goal.list_upgrades())

    def test_update_all(self):
        """ Update all you can. """
        self.base.upgrade_all()
        expected = tests.support.installed_but(self.sack, "pepper", "hole", "tour") + \
            list(self.sack.query().available()._nevra("pepper-20-1.x86_64")) + \
            list(self.sack.query().available()._nevra("hole-2-1.x86_64"))
        self.assertResult(self.base, expected)

    def test_upgrade_all_reponame(self):
        """Test whether only packages in selected repo are upgraded."""
        # override base with custom repos
        self.base = tests.support.MockBase('updates', 'third_party')

        self.base.upgrade_all('third_party')

        self.assertResult(self.base, itertools.chain(
            self.sack.query().installed().filter(name__neq='hole'),
            self.sack.query().upgrades().filter(reponame='third_party')))

    def test_upgrade_to_package(self):
        # override base with new object with no repos
        self.base = tests.support.MockBase()
        pkgs = self.base.add_remote_rpms([tests.support.TOUR_51_PKG_PATH])
        cnt = self.base.package_upgrade(pkgs[0])
        self.assertEqual(cnt, 1)
        new_pkg = self.sack.query().available().filter(name="tour")[0]
        new_set = tests.support.installed_but(self.sack, "tour") + [new_pkg]
        self.assertResult(self.base, new_set)

    def test_update_arches(self):
        self.base.upgrade("hole")
        installed, removed = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed), ['hole-2-1.x86_64'])
        self.assertCountEqual(map(str, removed),
                              ['hole-1-1.x86_64', 'tour-5-0.noarch'])

    def test_upgrade_reponame(self):
        """Test whether only packages in selected repo are upgraded."""
        # override base with custom repos
        self.base = tests.support.MockBase('updates', 'broken_deps')

        self.base.upgrade('*e*', 'broken_deps')

        installed, removed = self.installed_removed(self.base)
        # Sack contains two upgrades with the same version. Because of that
        # test whether the installed package is one of those packages.
        self.assertLength(installed, 1)
        self.assertIn(
            dnf.util.first(installed),
            self.sack.query().upgrades().filter(name='pepper'))
        self.assertCountEqual(
            removed,
            self.sack.query().installed().filter(name='pepper'))

        q = dnf.subject.Subject('*e*').get_best_query(self.sack).upgrades()
        q = q.filter(name__neq='pepper', reponame__neq='broken_deps')
        assert q, 'in another repo, there must be another update matching the ' \
            'pattern, otherwise the test makes no sense'

    def test_upgrade_reponame_not_in_repo(self):
        """Test whether no packages are upgraded if bad repo is selected."""
        # override base with custom repos
        self.base = tests.support.MockBase('updates', 'broken_deps')

        self.base.upgrade('hole', 'broken_deps')
        # ensure that no package was upgraded
        installed, removed = self.installed_removed(self.base)
        self.assertLength(installed, 0)
        self.assertLength(removed, 0)

        self.base.history.close()

        self.assertResult(self.base, self.sack.query().installed())
        q = dnf.subject.Subject('hole').get_best_query(self.sack).upgrades()
        q = q.filter(reponame__neq='broken_deps')
        assert q, 'in another repo, there must be an update matching the ' \
            'pattern, otherwise the test makes no sense'


class SkipBroken(tests.support.ResultTestCase):

    REPOS = ['broken_deps']
    INIT_SACK = True

    def test_upgrade_all(self):
        """ upgrade() without parameters upgrade everything it can that has its
            deps in trim. Broken packages are silently skipped.
        """
        self.base.upgrade_all()
        new_set = tests.support.installed_but(self.sack, "pepper").run()
        new_set.extend(self.sack.query().available()._nevra("pepper-20-1.x86_64"))
        self.assertResult(self.base, new_set)


class CostUpdate(tests.test_repo.RepoTestMixin, tests.support.ResultTestCase):

    REPOS = []
    INIT_SACK = True

    def test_cost(self):
        """Test the repo costs are respected."""
        r1 = self.build_repo('r1')
        r2 = self.build_repo('r2')
        r1.cost = 500
        r2.cost = 700

        self.base.repos.add(r1)
        self.base.repos.add(r2)
        self.base._add_repo_to_sack(r1)
        self.base._add_repo_to_sack(r2)
        self.base.upgrade("tour")
        (installed, _) = self.installed_removed(self.base)
        self.assertEqual('r1', dnf.util.first(installed).reponame)
        # TODO:
        self.base.close()
