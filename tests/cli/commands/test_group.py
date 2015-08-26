# Copyright (C) 2014 Red Hat, Inc.
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
from dnf.comps import CompsQuery

import dnf.cli.commands.group as group
import dnf.comps
import dnf.exceptions


class GroupCommandStaticTest(support.TestCase):

    def test_canonical(self):
        cmd = group.GroupCommand(None)
        (basecmd, extcmds) = cmd.canonical(['grouplist', 'crack'])
        self.assertEqual(basecmd, 'groups')
        self.assertEqual(extcmds, ['list', 'crack'])

        (_, extcmds) = cmd.canonical(['groups'])
        self.assertEqual(extcmds, ['summary'])

        (_, extcmds) = cmd.canonical(['group', 'info', 'crack'])
        self.assertEqual(extcmds, ['info', 'crack'])

        (_, extcmds) = cmd.canonical(['group', 'update', 'crack'])
        self.assertEqual(extcmds, ['upgrade', 'crack'])

    def test_split_extcmds(self):
        split = group.GroupCommand._split_extcmds(['with-optional', 'crack'])
        self.assertEqual(split, (('mandatory', 'default', 'optional'), ['crack']))
        split = group.GroupCommand._split_extcmds(['crack'])
        self.assertEqual(split, (('mandatory', 'default'), ['crack']))


class GroupCommandTest(support.TestCase):
    def setUp(self):
        base = support.MockBase("main")
        base.read_mock_comps()
        base.init_sack()
        self.cmd = group.GroupCommand(base.mock_cli())

    def test_environment_list(self):
        env_inst, env_avail = self.cmd._environment_lists(['sugar*'])
        self.assertLength(env_inst, 1)
        self.assertLength(env_avail, 0)
        self.assertEqual(env_inst[0].name, 'Sugar Desktop Environment')

    def test_configure(self):
        self.cmd.configure(['remove', 'crack'])
        demands = self.cmd.cli.demands
        self.assertTrue(demands.allow_erasing)
        self.assertFalse(demands.freshest_metadata)


class CompsQueryTest(support.TestCase):

    def setUp(self):
        (self.comps, self.prst) = support.mock_comps(True)

    def test_all(self):
        status_all = CompsQuery.AVAILABLE | CompsQuery.INSTALLED
        kinds_all = CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS
        q = CompsQuery(self.comps, self.prst, kinds_all, status_all)

        res = q.get('sugar*', '*er*')
        self.assertCountEqual(res.environments,
                              ('sugar-desktop-environment',))
        self.assertCountEqual(res.groups, ("Peppers", 'somerset'))

    def test_err(self):
        q = CompsQuery(self.comps, self.prst, CompsQuery.ENVIRONMENTS,
                       CompsQuery.AVAILABLE)
        with self.assertRaises(dnf.exceptions.CompsError):
            q.get('*er*')

    def test_installed(self):
        q = CompsQuery(self.comps, self.prst, CompsQuery.GROUPS,
                       CompsQuery.INSTALLED)
        res = q.get('somerset')
        self.assertEmpty(res.environments)
        self.assertCountEqual(res.groups, ('somerset',))
