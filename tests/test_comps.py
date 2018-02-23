# -*- coding: utf-8 -*-

# Copyright (C) 2013-2018 Red Hat, Inc.
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
from __future__ import print_function
from __future__ import unicode_literals

import operator

import libcomps
import libdnf.swdb

import dnf.comps
import dnf.exceptions
import dnf.persistor
import dnf.util

import tests.support
from tests.support import mock


TRANSLATION = u"""Tato skupina zahrnuje nejmenší možnou množinu balíčků. Je vhodná například na instalace malých routerů nebo firewallů."""


class LangsTest(tests.support.TestCase):
    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_get(self, _unused):
        langs = dnf.comps._Langs().get()
        self.assertEqual(langs, ['cs_CZ.UTF-8', 'cs_CZ', 'cs.UTF-8', 'cs', 'C'])


class CompsTest(tests.support.TestCase):
    def setUp(self):
        comps = dnf.comps.Comps()
        comps._add_from_xml_filename(tests.support.COMPS_PATH)
        self.comps = comps

    def test_by_pattern(self):
        comps = self.comps
        self.assertLength(comps.groups_by_pattern('Base'), 1)
        self.assertLength(comps.groups_by_pattern('*'), tests.support.TOTAL_GROUPS)
        self.assertLength(comps.groups_by_pattern('Solid*'), 1)

        group = dnf.util.first(comps.groups_by_pattern('Base'))
        self.assertIsInstance(group, dnf.comps.Group)

    def test_categories(self):
        cat = self.comps.categories[0]
        self.assertEqual(cat.name_by_lang['cs'], u'Základ systému')
        self.assertEqual(cat.desc_by_lang['de'],
                         u'Verschiedene Kernstücke des Systems.')
        self.assertCountEqual((id_.name for id_ in cat.group_ids),
                              ('base', ))
        self.assertCountEqual((id_.default for id_ in cat.group_ids),
                              (False, ))
        self.assertTrue(all(isinstance(grp, dnf.comps.Group)
                            for grp in cat.groups_iter()))

    def test_environments(self):
        env = self.comps.environments[0]
        self.assertEqual(env.name_by_lang['cs'], u'Prostředí Sugar')
        self.assertEqual(env.desc_by_lang['de'],

                         u'Eine Software-Spielwiese zum Lernen des Lernens.')
        self.assertCountEqual((id_.name for id_ in env.group_ids),
                              ('somerset', 'Peppers'))
        self.assertEqual(2, len(env.mandatory_groups))
        self.assertTrue(all(isinstance(grp, dnf.comps.Group)
                            for grp in env.mandatory_groups))
        self.assertCountEqual((id_.default for id_ in env.group_ids),
                              (True, False))
        self.assertCountEqual((id_.name for id_ in env.option_ids),
                              ('base',))
        self.assertEqual(1, len(env.optional_groups))
        self.assertTrue(all(isinstance(grp, dnf.comps.Group)
                            for grp in env.optional_groups))
        self.assertTrue(all(isinstance(grp, dnf.comps.Group)
                            for grp in env.groups_iter()))

    def test_groups(self):
        g = self.comps.group_by_pattern('base')
        self.assertTrue(g.visible)
        g = self.comps.group_by_pattern('somerset')
        self.assertFalse(g.visible)

    def test_group_packages(self):
        g = self.comps.group_by_pattern('base')
        self.assertCountEqual(map(operator.attrgetter('name'), g.packages_iter()),
                              ('tour', 'pepper'))

    def test_iteration(self):
        comps = self.comps
        self.assertEqual([g.name for g in comps.groups_iter()],
                         ['Base', 'Solid Ground', "Pepper's", "Broken Group"])
        self.assertEqual([c.name for c in comps.categories_iter()],
                         ['Base System'])
        g = dnf.util.first(comps.groups_iter())
        self.assertEqual(g.desc_by_lang['cs'], TRANSLATION)

    def test_group_display_order(self):
        self.assertEqual([g.name for g in self.comps.groups],
                         ["Pepper's", 'Base', 'Solid Ground', 'Broken Group'])

    def test_packages(self):
        comps = self.comps
        group = dnf.util.first(comps.groups_iter())
        self.assertSequenceEqual([pkg.name for pkg in group.packages],
                                 (u'pepper', u'tour'))
        self.assertSequenceEqual([pkg.name for pkg in group.mandatory_packages],
                                 (u'pepper', u'tour'))

    def test_size(self):
        comps = self.comps
        self.assertLength(comps, 6)
        self.assertLength(comps.groups, tests.support.TOTAL_GROUPS)
        self.assertLength(comps.categories, 1)
        self.assertLength(comps.environments, 1)

    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_ui_name(self, _unused):
        comps = self.comps
        group = dnf.util.first(comps.groups_by_pattern('base'))
        self.assertEqual(group.ui_name, u'Kritická cesta (Základ)')

    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_ui_desc(self, _unused):
        comps = self.comps
        env = dnf.util.first(comps.environments_by_pattern('sugar-*'))
        self.assertEqual(env.ui_description, u'Software pro výuku o vyučování.')


class PackageTest(tests.support.TestCase):
    def test_instance(self):
        lc_pkg = libcomps.Package('weather', libcomps.PACKAGE_TYPE_OPTIONAL)
        pkg = dnf.comps.Package(lc_pkg)
        self.assertEqual(pkg.name, 'weather')
        self.assertEqual(pkg.option_type, dnf.comps.OPTIONAL)


class TestTransactionBunch(tests.support.TestCase):

    def test_adding(self):
        t1 = dnf.comps.TransactionBunch()
        t1.install = {'right'}
        t1.upgrade = {'tour'}
        t1.remove = {'pepper'}
        t2 = dnf.comps.TransactionBunch()
        t2.install = {'pepper'}
        t2.upgrade = {'right'}
        t1 += t2
        self.assertTransEqual(t1.install, ('right', 'pepper'))
        self.assertTransEqual(t1.upgrade, ('tour', 'right'))
        self.assertEmpty(t1.remove)


class SolverGroupTest(tests.support.DnfBaseTestCase):

    REPOS = []
    COMPS = True
    COMPS_SOLVER = True

    def test_install(self):
        group_id = 'base'
        trans = self.solver._group_install(group_id, dnf.comps.MANDATORY)
        self.assertLength(trans.install, 2)
        self._swdb_commit()

        swdb_group = self.history.group.get(group_id)
        self.assertCountEqual([i.getName() for i in swdb_group.getPackages()], ['pepper', 'tour'])
        self.assertEqual(swdb_group.getPackageTypes(), dnf.comps.MANDATORY)

    def test_removable_pkg(self):
        comps_group = self.comps.group_by_pattern('base')
        self.solver._group_install(comps_group.id, dnf.comps.MANDATORY, [])

        tsis = []

        pkg1 = self.base.sack.query().filter(name="pepper", epoch=0, version="20", release="0", arch="x86_64")[0]
        self.history.rpm.add_install(pkg1, reason=libdnf.swdb.TransactionItemReason_GROUP)

        pkg3 = self.base.sack.query().filter(name="tour", version="5", release="0", arch="noarch")[0]
        self.history.rpm.add_install(pkg3, reason=libdnf.swdb.TransactionItemReason_GROUP)

        group_id = "dupl"
        swdb_group = self.history.group.new(group_id, group_id, group_id, dnf.comps.DEFAULT)
        swdb_group.addPackage("tour", True, dnf.comps.MANDATORY)
        self.history.group.install(swdb_group)
        self._swdb_commit(tsis)

        # pepper is in single group with reason "group"
        self.assertTrue(self.solver._removable_pkg('pepper'))
        # right's reason is "dep"
        self.assertFalse(self.solver._removable_pkg('right'))
        # tour appears in more than one group
        self.assertFalse(self.solver._removable_pkg('tour'))

        swdb_group = self.history.group.get(group_id)
        self.history.group.remove(swdb_group)

        # tour appears only in one group now
        self.assertTrue(self.solver._removable_pkg('tour'))

    def test_remove(self):
        grp = self.comps.group_by_pattern('base')
        self.solver._group_install(grp.id, dnf.comps.MANDATORY, [])

        grps = self.history.group.search_by_pattern('base')
        for grp in grps:
            self.solver._group_remove(grp)

        # need to load groups again - loaded object is stays the same
        grps = self.history.group.search_by_pattern('base')
        for grp in grps:
            self.assertFalse(grp.installed)

    def test_upgrade(self):
        # setup of the "current state"
        group_id = 'base'

        swdb_group = self.history.group.new(group_id, group_id, group_id, dnf.comps.MANDATORY)
        for pkg_name in ['pepper', 'handerson']:
            swdb_group.addPackage(pkg_name, True, dnf.comps.MANDATORY)
        self.history.group.install(swdb_group)
        self._swdb_commit()

        swdb_group = self.history.group.get(group_id)
        self.assertCountEqual([i.getName() for i in swdb_group.getPackages()], ('handerson', 'pepper'))

        comps_group = self.comps.group_by_pattern(group_id)

        trans = self.solver._group_upgrade(group_id)
        self.assertTransEqual(trans.install, ('tour',))
        self.assertTransEqual(trans.remove, ('handerson',))
        self.assertTransEqual(trans.upgrade, ('pepper',))
        self._swdb_commit()

        swdb_group = self.history.group.get(group_id)
        self.assertCountEqual([i.getName() for i in swdb_group.getPackages()], ('tour', 'pepper'))

class SolverEnvironmentTest(tests.support.DnfBaseTestCase):

    REPOS = []
    COMPS = True
    COMPS_SOLVER = True

    def test_install(self):
        env_id = 'sugar-desktop-environment'
        env = self.comps._environment_by_id(env_id)
        trans = self.solver._environment_install(env_id, dnf.comps.MANDATORY, [])
        self._swdb_commit()

        self.assertCountEqual([pkg.name for pkg in trans.install], ('pepper', 'trampoline', 'hole', 'lotus'))

        sugar = self.history.env.get(env_id)
        self.assertCountEqual([i.getGroupId() for i in sugar.getGroups()], ('Peppers', 'somerset', 'base'))

        somerset = self.history.group.get('somerset')
        self.assertIsNotNone(somerset)
        self.assertEqual(somerset.getPackageTypes(), dnf.comps.MANDATORY)

        base = self.history.group.get('base')
        self.assertEqual(base, None)

    def test_remove(self):
        env_id = 'sugar-desktop-environment'
        comps_env = self.comps.environment_by_pattern(env_id)

        self.solver._environment_install(comps_env.id, dnf.comps.MANDATORY, [])
        self._swdb_commit()

        swdb_env = self.history.env.get(comps_env.id)
        self.assertEqual(swdb_env.getPackageTypes(), dnf.comps.MANDATORY)
        group_ids = [i.getGroupId() for i in swdb_env.getGroups()]

        self.solver._environment_remove(comps_env.id)
        self._swdb_commit()

        swdb_env = self.history.env.get(comps_env.id)
        # if swdb_env is None, then it's removed
        self.assertIsNone(swdb_env)
        # test if also all groups were removed
        for group_id in group_ids:
            swdb_group = self.history.group.get(group_id)
            self.assertIsNone(swdb_group)

        # install it again with different pkg_types
        self.solver._environment_install(comps_env.id, dnf.comps.OPTIONAL, [])
        self._swdb_commit()

        swdb_env = self.history.env.get(comps_env.id)
        self.assertIsNotNone(swdb_env)
        self.assertEqual(swdb_env.getPackageTypes(), dnf.comps.OPTIONAL)

        group_ids = [i.getGroupId() for i in swdb_env.getGroups()]
        self.assertTrue(len(group_ids))
        for group_id in group_ids:
            swdb_group = self.history.group.get(group_id)
            if group_id == "base" and swdb_group is None:
                continue
            self.assertEqual(swdb_group.getPackageTypes(), dnf.comps.OPTIONAL)

    def test_upgrade(self):
        """Upgrade environment, the one group it knows is no longer installed."""
        env_id = "sugar-desktop-environment"
        comps_env = self.comps.environment_by_pattern(env_id)

        self.solver._environment_install(comps_env.id, dnf.comps.ALL_TYPES, [])
        self._swdb_commit()

        swdb_env = self.history.env.get(comps_env.id)
        self.assertNotEqual(swdb_env, None)

        # create a new transaction item for group Peppers with no packages
        self._swdb_commit()
        swdb_group = self.history.group.get('Peppers')
        swdb_group = self.history.group.new(swdb_group.getGroupId(), swdb_group.getName(), swdb_group.getTranslatedName(), swdb_group.getPackageTypes())
        self.history.group.install(swdb_group)
        self._swdb_commit()

        trans = self.solver._environment_upgrade(comps_env.id)
        self._swdb_commit()
        self.assertTransEqual(trans.install, ('hole', 'lotus'))
        self.assertTransEqual(trans.upgrade, ('pepper', 'trampoline', 'lotus'))
        self.assertEmpty(trans.remove)
