# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

import dnf.cli.commands.group as group
import dnf.comps
import dnf.exceptions
from dnf.comps import CompsQuery
from dnf.cli.option_parser import OptionParser

import tests.support


class GroupCommandStaticTest(tests.support.TestCase):

    def test_canonical(self):
        cmd = group.GroupCommand(tests.support.mock.MagicMock())

        for args, out in [
                (['grouplist', 'crack'], ['list', 'crack']),
                (['groups'], ['summary']),
                (['group', 'info', 'crack'], ['info', 'crack']),
                (['group', 'update', 'crack'], ['upgrade', 'crack'])]:
            parser = OptionParser()
            parser.parse_main_args(args)
            parser.parse_command_args(cmd, args)
            cmd._canonical()
            self.assertEqual(cmd.opts.subcmd, out[0])
            self.assertEqual(cmd.opts.args, out[1:])

    def test_split_extcmds(self):
        cmd = group.GroupCommand(tests.support.mock.MagicMock())
        cmd.base.conf = dnf.conf.Conf()
        tests.support.command_run(cmd, ['install', 'crack'])
        cmd.base.env_group_install.assert_called_with(
            ['crack'], ('mandatory', 'default', 'conditional'),
            cmd.base.conf.strict)


class GroupCommandTest(tests.support.DnfBaseTestCase):

    REPOS = ["main"]
    COMPS = True
    INIT_SACK = True

    def setUp(self):
        super(GroupCommandTest, self).setUp()
        self.cmd = group.GroupCommand(self.base.mock_cli())
        self.parser = OptionParser()

    def test_environment_list(self):
        env_inst, env_avail = self.cmd._environment_lists(['sugar*'])
        self.assertLength(env_inst, 0)
        self.assertLength(env_avail, 1)
        self.assertEqual(env_avail[0].name, 'Sugar Desktop Environment')

    def test_configure(self):
        tests.support.command_configure(self.cmd, ['remove', 'crack'])
        demands = self.cmd.cli.demands
        self.assertTrue(demands.allow_erasing)
        self.assertFalse(demands.freshest_metadata)


class CompsQueryTest(tests.support.DnfBaseTestCase):

    REPOS = []
    COMPS = True

    def test_all(self):
        status_all = CompsQuery.AVAILABLE | CompsQuery.INSTALLED
        kinds_all = CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS
        q = CompsQuery(self.comps, self.persistor, kinds_all, status_all)

        res = q.get('sugar*', '*er*')
        self.assertCountEqual(res.environments,
                              ('sugar-desktop-environment',))
        self.assertCountEqual(res.groups, ("Peppers", 'somerset'))

    def test_err(self):
        q = CompsQuery(self.comps, self.persistor, CompsQuery.ENVIRONMENTS,
                       CompsQuery.AVAILABLE)
        with self.assertRaises(dnf.exceptions.CompsError):
            q.get('*er*')

    def test_installed(self):
        q = CompsQuery(self.comps, self.persistor, CompsQuery.GROUPS,
                       CompsQuery.INSTALLED)
        self.base.read_mock_comps(False)
        grp = self.base.comps.group_by_pattern('somerset')
        self.base.group_install(grp.id, ('mandatory',))

        res = q.get('somerset')
        self.assertEmpty(res.environments)
        grp_ids = [grp.name_id for grp in res.groups]
        self.assertCountEqual(grp_ids, ('somerset',))
