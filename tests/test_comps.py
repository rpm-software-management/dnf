# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014  Red Hat, Inc.
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
from tests import support
from tests.support import mock

import dnf.comps
import dnf.exceptions
import dnf.persistor
import dnf.util
import libcomps
import operator

TRANSLATION=u"""Tato skupina zahrnuje nejmenší možnou množinu balíčků. Je vhodná například na instalace malých routerů nebo firewallů."""

class LangsTest(support.TestCase):
    @mock.patch('locale.getlocale', return_value=('cs_CZ', 'UTF-8'))
    def test_get(self, _unused):
        langs = dnf.comps._Langs().get()
        self.assertEqual(langs, ['cs_CZ.UTF-8', 'cs_CZ', 'cs.UTF-8', 'cs', 'C'])

class CompsTest(support.TestCase):
    def setUp(self):
        comps = dnf.comps.Comps(support.INSTALLED_GROUPS.copy(),
                                support.INSTALLED_ENVIRONMENTS.copy())
        comps.add_from_xml_filename(support.COMPS_PATH)
        self.comps = comps

    def test_by_pattern(self):
        comps = self.comps
        self.assertLength(comps.groups_by_pattern('Base'), 1)
        self.assertLength(comps.groups_by_pattern('*'), support.TOTAL_GROUPS)
        self.assertLength(comps.groups_by_pattern('Solid*'), 1)

        group = dnf.util.first(comps.groups_by_pattern('Base'))
        self.assertIsInstance(group, dnf.comps.Group)

    def test_installed(self):
        base = support.MockBase("main")
        sack = base.sack

        comps = self.comps
        groups = comps.groups
        self.assertLength(groups, support.TOTAL_GROUPS)
        # ensure even groups obtained before compile() have the property set:
        self.assertTrue(groups[0].installed)
        self.assertFalse(groups[1].installed)

        envs = comps.environments
        self.assertTrue(envs[0].installed)

    def test_environments(self):
        env = self.comps.environments[0]
        self.assertEqual(env.name_by_lang['cs'], u'Prostředí Sugar')
        self.assertEqual(env.desc_by_lang['de'],

                         u'Eine Software-Spielwiese zum Lernen des Lernens.')
        self.assertItemsEqual((id_.name for id_ in env.group_ids),
                              ('somerset', 'Peppers'))
        self.assertItemsEqual((id_.default for id_ in env.group_ids),
                              (True, False))
        self.assertItemsEqual((id_.name for id_ in env.option_ids),
                              ('base',))

        self.assertTrue(all(isinstance(grp, dnf.comps.Group)
                            for grp in env.groups_iter()))

    def test_groups(self):
        g = self.comps.group_by_pattern('base')
        self.assertTrue(g.visible)
        g = self.comps.group_by_pattern('somerset')
        self.assertFalse(g.visible)

    def test_group_packages(self):
        g = self.comps.group_by_pattern('base')
        self.assertItemsEqual(map(operator.attrgetter('name'), g.packages_iter()),
                              ('tour', 'pepper'))

    def test_iteration(self):
        comps = self.comps
        self.assertEqual([g.name for g in comps.groups_iter()],
                         ['Base', 'Solid Ground', "Pepper's"])
        self.assertEqual([c.name for c in comps.categories_iter()],
                         ['Base System'])
        g = dnf.util.first(comps.groups_iter())
        self.assertEqual(g.desc_by_lang['cs'], TRANSLATION)

    def test_packages(self):
        comps = self.comps
        group = dnf.util.first(comps.groups_iter())
        self.assertSequenceEqual([pkg.name for pkg in group.packages],
                                 (u'pepper', u'tour'))
        self.assertSequenceEqual([pkg.name for pkg in group.mandatory_packages],
                                 (u'pepper', u'tour'))

    def test_size(self):
        comps = self.comps
        self.assertLength(comps, 5)
        self.assertLength(comps.groups, support.TOTAL_GROUPS)
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

class PackageTest(support.TestCase):
    def test_instance(self):
        lc_pkg = libcomps.Package('weather', libcomps.PACKAGE_TYPE_OPTIONAL)
        pkg = dnf.comps.Package(lc_pkg)
        self.assertEqual(pkg.name, 'weather')
        self.assertEqual(pkg.option_type, dnf.comps.OPTIONAL)

class MockPersistor(dnf.persistor.GroupPersistor):
    """Empty persistor that doesn't need any I/O."""
    def __init__(self):
        self.db = self._empty_db()

class TestTransactionBunch(support.TestCase):

    def test_adding(self):
        t1 = dnf.comps.TransactionBunch()
        t1.install = {'right'}
        t1.upgrade = {'tour'}
        t1.remove = {'pepper'}
        t2 = dnf.comps.TransactionBunch()
        t2.install = {'pepper'}
        t2.upgrade = {'right'}
        t1 += t2
        self.assertItemsEqual(t1.install, ('right', 'pepper'))
        self.assertItemsEqual(t1.upgrade, ('tour', 'right'))
        self.assertEmpty(t1.remove)


class SolverTestMixin(object):

    def setUp(self):
        comps = dnf.comps.Comps()
        comps.add_from_xml_filename(support.COMPS_PATH)
        self.comps = comps
        self.persistor = MockPersistor()
        self.solver = dnf.comps.Solver(self.persistor)


class SolverGroupTest(SolverTestMixin, support.TestCase):

    def test_install(self):
        grp = self.comps.group_by_pattern('base')
        trans = self.solver.group_install(grp, dnf.comps.MANDATORY, ['right'])
        self.assertLength(trans.install, 2)
        p_grp = self.persistor.group('base')
        self.assertItemsEqual(p_grp.full_list, ['pepper', 'tour'])
        self.assertItemsEqual(p_grp.pkg_exclude, ['right'])
        self.assertEqual(p_grp.pkg_types, dnf.comps.MANDATORY)

    def test_removable_pkg(self):
        p_grp1 = self.persistor.group('base')
        p_grp2 = self.persistor.group('tune')
        p_grp1.full_list.extend(('pepper', 'tour', 'right'))
        p_grp2.full_list.append('tour')
        self.assertTrue(self.solver._removable_pkg('pepper'))
        self.assertFalse(self.solver._removable_pkg('tour'))

    def test_remove(self):
        # setup of the "current state"
        p_grp = self.persistor.group('base')
        p_grp.pkg_types = dnf.comps.MANDATORY
        p_grp.full_list.extend(('pepper', 'tour'))
        p_grp2 = self.persistor.group('tune')
        p_grp2.full_list.append('pepper')

        grp = self.comps.group_by_pattern('base')
        trans = self.solver.group_remove(grp)
        self.assertFalse(p_grp.installed)
        self.assertItemsEqual(trans.remove, ('tour',))

    def test_upgrade(self):
        # setup of the "current state"
        p_grp = self.persistor.group('base')
        p_grp.pkg_types = dnf.comps.MANDATORY
        p_grp.full_list.extend(('pepper', 'handerson'))

        grp = self.comps.group_by_pattern('base')
        trans = self.solver.group_upgrade(grp)
        self.assertItemsEqual(trans.install, ('tour',))
        self.assertItemsEqual(trans.remove, ('handerson',))
        self.assertItemsEqual(trans.upgrade, ('pepper',))
        self.assertItemsEqual(p_grp.full_list, ('tour', 'pepper'))


class SolverEnvironmentTest(SolverTestMixin, support.TestCase):
    ALL_TYPES = dnf.comps.CONDITIONAL | dnf.comps.DEFAULT | \
                dnf.comps.MANDATORY | dnf.comps.OPTIONAL

    def _install(self, env):
        self.comps.environment_by_pattern('sugar-desktop-environment')
        return self.solver.environment_install(env, dnf.comps.MANDATORY,
                                               ('lotus',))

    def test_install(self):
        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        trans = self._install(env)

        self.assertItemsEqual(trans.install, ('pepper', 'trampoline', 'hole'))
        sugar = self.persistor.environment('sugar-desktop-environment')
        self.assertItemsEqual(sugar.full_list, ('Peppers', 'somerset'))
        somerset = self.persistor.group('somerset')
        self.assertTrue(somerset.installed)
        self.assertEqual(somerset.pkg_types, dnf.comps.MANDATORY)
        self.assertItemsEqual(somerset.pkg_exclude, ('lotus',))
        base = self.persistor.group('somerset')
        self.assertTrue(base.installed)

    def test_remove(self):
        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        self._install(env)
        trans = self.solver.environment_remove(env)

        p_env = self.persistor.environment('sugar-desktop-environment')
        self.assertItemsEqual(trans.remove, ('pepper', 'trampoline', 'hole'))
        self.assertFalse(p_env.grp_types)
        self.assertFalse(p_env.pkg_types)

    def test_upgrade(self):
        """Upgrade environment, the one group it knows is no longer installed."""
        p_env = self.persistor.environment('sugar-desktop-environment')
        p_env.full_list.extend(['somerset'])
        p_env.grp_types = self.ALL_TYPES
        p_env.pkg_types = self.ALL_TYPES

        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        trans = self.solver.environment_upgrade(env)
        self.assertItemsEqual(trans.install, ('hole', 'lotus'))
        self.assertEmpty(trans.upgrade)
