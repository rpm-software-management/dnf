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
from __future__ import unicode_literals

import dnf.comps
import dnf.persistor
import dnf.pycomp
import tempfile
import tests.support

IDS = set(['one', 'two', 'three'])


class ClonableDictTest(tests.support.TestCase):
    def test_clone(self):
        g = dnf.persistor.ClonableDict({})
        g['base'] = ['pepper', 'tour']
        g_c = g.clone()
        self.assertEqual(g, g_c)
        g_c['base'].append('magical')
        self.assertNotEqual(g, g_c)


class GroupPersistorTest(tests.support.TestCase):
    def setUp(self):
        self.persistdir = tempfile.mkdtemp(prefix="dnf-groupprst-test.0.0.5")
        self.prst = dnf.persistor.GroupPersistor(self.persistdir)

    def tearDown(self):
        dnf.util.rm_rf(self.persistdir)

    def test_default(self):
        """Default items are empty."""
        grp = self.prst.group('pepper')
        self.assertEmpty(grp.full_list)
        self.assertEqual(grp.pkg_types, 0)

    def test_prune_db(self):
        prst = self.prst
        grp = prst.group('pepper')
        prst._prune_db()
        self.assertEmpty(prst.db['GROUPS'])

        grp = prst.group('pepper')
        grp.pkg_types = dnf.comps.MANDATORY
        prst._prune_db()
        self.assertLength(prst.db['GROUPS'], 1)

    def test_saving(self):
        prst = self.prst
        grp = prst.group('pepper')
        grp.full_list.extend(['pepper', 'tour'])
        grp.pkg_types = dnf.comps.DEFAULT | dnf.comps.OPTIONAL
        prst.commit()
        self.assertTrue(prst.save())

        prst = dnf.persistor.GroupPersistor(self.persistdir)
        grp = prst.group('pepper')
        self.assertEqual(grp.full_list, ['pepper', 'tour'])
        self.assertEqual(grp.pkg_types, dnf.comps.DEFAULT | dnf.comps.OPTIONAL)

    def test_version(self):
        version = self.prst.db['meta']['version']
        self.assertIsInstance(version, dnf.pycomp.unicode)


class GroupDiffTest(tests.support.TestCase):
    def test_added_removed(self):
        prst1 = dnf.persistor.GroupPersistor(tests.support.NONEXISTENT_FILE)
        prst1.db = prst1._empty_db()
        prst2 = dnf.persistor.GroupPersistor(tests.support.NONEXISTENT_FILE)
        prst2.db = prst1._empty_db()

        prst1.group('kite').full_list.extend(('the', 'show'))
        prst2.environment('pepper').full_list.extend(('stop', 'the', 'show'))

        diff = dnf.persistor._GroupsDiff(prst1.db, prst2.db)
        self.assertEmpty(diff.new_groups)
        self.assertEmpty(diff.removed_environments)
        self.assertCountEqual(diff.removed_groups, ('kite',))
        self.assertCountEqual(diff.new_environments, ('pepper',))

    def test_diff_dcts(self):
        dct1 = {'stop' : [1, 2, 3],
                'the' : {'show' : [1, 2]}}
        dct2 = {'stop' : [1, 2],
                'the' : {'show' : [2]},
                'three' : 8}

        added, removed = dnf.persistor._diff_dcts(dct1, dct2)
        self.assertEqual(added, {'three': 8})
        self.assertEqual(removed, {'the': {'show': set([1])}, 'stop': set([3])})


class RepoPersistorTest(tests.support.TestCase):
    def setUp(self):
        self.persistdir = tempfile.mkdtemp(prefix="dnf-repoprst-test-")
        self.prst = dnf.persistor.RepoPersistor(self.persistdir)

    def tearDown(self):
        dnf.util.rm_rf(self.persistdir)

    def test_expired_repos(self):
        self.assertLength(self.prst.get_expired_repos(), 0)
        self.prst.expired_to_add = IDS
        self.prst.save()
        self.assertEqual(self.prst.get_expired_repos(), IDS)

        prst = dnf.persistor.RepoPersistor(self.persistdir)
        self.assertEqual(prst.get_expired_repos(), IDS)
