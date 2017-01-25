# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Red Hat, Inc.
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
        comps = dnf.comps.Comps()
        comps._add_from_xml_filename(support.COMPS_PATH)
        self.comps = comps

    def test_by_pattern(self):
        comps = self.comps
        self.assertLength(comps.groups_by_pattern('Base'), 1)
        self.assertLength(comps.groups_by_pattern('*'), support.TOTAL_GROUPS)
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
        self.assertTransEqual(t1.install, ('right', 'pepper'))
        self.assertTransEqual(t1.upgrade, ('tour', 'right'))
        self.assertEmpty(t1.remove)


class SolverTestMixin(object):

    def setUp(self):
        comps = dnf.comps.Comps()
        comps._add_from_xml_filename(support.COMPS_PATH)
        self.comps = comps
        self.base = support.MockBase()
        self.persistor = self.base.history.activate_group()
        self.solver = dnf.comps.Solver(self.persistor, self.comps, support.REASONS.get)


class SolverGroupTest(SolverTestMixin, support.TestCase):

    def test_install(self):
        grp = self.comps.group_by_pattern('base')
        trans = self.solver._group_install(grp.id, dnf.comps.MANDATORY, ['right'])
        self.persistor.commit()
        self.assertLength(trans.install, 2)
        p_grp = self.persistor.group('base')
        self.assertCountEqual(p_grp.get_full_list(), ['pepper', 'tour'])
        self.assertCountEqual(p_grp.get_exclude(), ['right'])
        self.assertEqual(p_grp.pkg_types, dnf.comps.MANDATORY)

    def test_removable_pkg(self):
        p_grp1 = self.persistor.group('base')
        p_grp2 = self.persistor.new_group('tune',
                                          'tune',
                                          'tune',
                                          1,  # installed
                                          dnf.comps.MANDATORY,
                                          0)
        self.persistor.add_group(p_grp2)
        p_grp1.add_package(['pepper', 'tour', 'right'])
        p_grp2.add_package(['tour'])
        self.assertTrue(self.solver._removable_pkg('pepper'))
        # right's reason is "dep"
        self.assertFalse(self.solver._removable_pkg('right'))
        # tour appears in more than one group
        self.assertFalse(self.solver._removable_pkg('tour'))

    def test_remove(self):
        # setup of the "current state"
        p_grp = self.persistor.new_group('base',
                                         'Base',
                                         u'Kritická cesta (Základ)',
                                         1,  # installed
                                         dnf.comps.MANDATORY,
                                         0)
        self.persistor.add_group(p_grp)
        p_grp.add_package(['pepper', 'tour'])

        grps = self.persistor.groups_by_pattern('base')
        for grp in grps:
            trans = self.solver._group_remove(grp)

        # commit changes from transaction
        self.persistor.commit()

        # need to load groups again - loaded object is stays the same
        grps = self.persistor.groups_by_pattern('base')
        for grp in grps:
                self.assertFalse(grp.is_installed)

    def test_upgrade(self):
        # setup of the "current state"
        p_grp = self.persistor.group('base')
        p_grp2 = self.persistor.new_group(p_grp.name_id,
                                          p_grp.name,
                                          p_grp.ui_name,
                                          1,
                                          dnf.comps.MANDATORY,
                                          p_grp.grp_types)
        self.persistor.add_group(p_grp2)
        p_grp2.add_package(['pepper', 'handerson'])
        grp = self.comps.group_by_pattern('base')
        trans = self.solver._group_upgrade(grp.id)
        self.assertTransEqual(trans.install, ('tour',))
        self.assertTransEqual(trans.remove, ('handerson',))
        self.assertTransEqual(trans.upgrade, ('pepper',))
        p_grp = self.persistor.group('base')
        self.assertCountEqual(p_grp.get_full_list(), ('tour', 'pepper'))


class SolverEnvironmentTest(SolverTestMixin, support.TestCase):

    def _install(self, env):
        return self.solver._environment_install(env.id, dnf.comps.MANDATORY,
                                                ('lotus',))

    def test_install(self):
        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        trans = self._install(env)
        self.assertCountEqual([pkg.name for pkg in trans.install],
                              ('pepper', 'trampoline', 'hole'))
        sugar = self.persistor.environment('sugar-desktop-environment')
        self.assertCountEqual(sugar.get_group_list(), ('Peppers', 'somerset'))
        somerset = self.persistor.group('somerset')
        self.assertTrue(somerset.is_installed)
        self.assertEqual(somerset.pkg_types, dnf.comps.MANDATORY)
        self.assertCountEqual(somerset.pkg_exclude, ('lotus',))
        base = self.persistor.group('somerset')
        self.assertTrue(base.is_installed)

    def test_remove(self):
        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        self._install(env)
        self.persistor.commit()
        trans = self.solver._environment_remove(env.id)

        p_env = self.persistor.environment('sugar-desktop-environment')
        self.assertTransEqual(trans.remove, ('pepper', 'trampoline', 'hole'))
        self.assertFalse(p_env.grp_types)
        self.assertFalse(p_env.pkg_types)

    def test_upgrade(self):
        """Upgrade environment, the one group it knows is no longer installed."""
        p_env = self.persistor.environment('sugar-desktop-environment')
        p_env_up = self.persistor.new_env(p_env.name_id,
                                          p_env.name,
                                          p_env.ui_name,
                                          dnf.comps.ALL_TYPES,
                                          dnf.comps.ALL_TYPES)
        p_env_up.add_group(['somerset'])
        env = self.comps.environment_by_pattern('sugar-desktop-environment')
        trans = self.solver._environment_upgrade(env.id)
        self.assertTransEqual(trans.install, ('hole', 'lotus'))
        self.assertEmpty(trans.upgrade)
