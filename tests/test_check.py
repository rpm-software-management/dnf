# -*- coding: utf-8 -*-

# Copyright (C) 2016-2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, see
# <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import dnf.cli.commands.check
import dnf.pycomp

import tests.support


EXPECTED_DUPLICATES_FORMAT = """\
dup-1-0.noarch is a duplicate with dup-2-0.noarch
dup-1-0.noarch is a duplicate with dup-3-0.noarch
"""

EXPECTED_OBSOLETED_FORMAT = """\
test-1-0.noarch is obsoleted by obs-3-0.noarch
"""


class CheckDuplicatesTest(tests.support.DnfBaseTestCase):

    REPOS = []
    BASE_CLI = True
    CLI = "stub"

    def test_duplicates(self):
        self.cmd = dnf.cli.commands.check.CheckCommand(self.cli)
        tests.support.command_configure(self.cmd, ['--duplicates'])
        with tests.support.patch_std_streams() as (stdout, _):
            with self.assertRaises(dnf.exceptions.Error) as ctx:
                self.cmd.run()
            self.assertEqual(str(ctx.exception),
                             'Check discovered 2 problem(s)')
        self.assertEqual(stdout.getvalue(), EXPECTED_DUPLICATES_FORMAT)

    def test_obsoleted(self):
        self.cmd = dnf.cli.commands.check.CheckCommand(self.cli)
        tests.support.command_configure(self.cmd, ['--obsoleted'])
        with tests.support.patch_std_streams() as (stdout, _):
            with self.assertRaises(dnf.exceptions.Error) as ctx:
                self.cmd.run()
            self.assertEqual(str(ctx.exception),
                             'Check discovered 1 problem(s)')
        self.assertEqual(stdout.getvalue(), EXPECTED_OBSOLETED_FORMAT)
