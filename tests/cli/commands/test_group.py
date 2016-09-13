# Copyright (C) 2014-2016 Red Hat, Inc.
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
from dnf.cli.option_parser import OptionParser

import dnf.cli.commands.group as group
import dnf.comps
import dnf.exceptions


class GroupCommandStaticTest(support.TestCase):

    def test_canonical(self):
        cmd = group.GroupCommand(support.mock.MagicMock())

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
        cmd = group.GroupCommand(support.mock.MagicMock())
        cmd.base.conf = dnf.conf.Conf()
        support.command_run(cmd, ['install', '--with-optional', 'crack'])
        cmd.base.env_group_install.assert_called_with(
            ['crack'], ('mandatory', 'default', 'optional'),
            cmd.base.conf.strict)
        support.command_run(cmd, ['install', 'crack'])
        cmd.base.env_group_install.assert_called_with(
            ['crack'], ('mandatory', 'default'), cmd.base.conf.strict)


class GroupCommandTest(support.TestCase):
    def setUp(self):
        base = support.MockBase("main")
        base.read_mock_comps()
        base.init_sack()
        self.cmd = group.GroupCommand(base.mock_cli())
        self.parser = OptionParser()

    def test_environment_list(self):
        env_inst, env_avail = self.cmd._environment_lists(['sugar*'])
        self.assertLength(env_inst, 1)
        self.assertLength(env_avail, 0)
        self.assertEqual(env_inst[0].name, 'Sugar Desktop Environment')

    def test_configure(self):
        support.command_configure(self.cmd, ['remove', 'crack'])
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
