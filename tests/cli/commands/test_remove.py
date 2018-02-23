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
from __future__ import unicode_literals

import logging

import dnf.cli.commands.remove
from dnf.cli.option_parser import OptionParser

import tests.support
from tests.support import mock


class RemoveCommandTest(tests.support.ResultTestCase):
    """Tests of ``dnf.cli.commands.EraseCommand`` class."""

    REPOS = []
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        super(RemoveCommandTest, self).setUp()
        self.cmd = dnf.cli.commands.remove.RemoveCommand(self.base.mock_cli())

    def test_configure(self):
        parser = OptionParser()
        parser.parse_main_args(['autoremove', '-y'])
        parser.parse_command_args(self.cmd, ['autoremove', '-y'])
        self.cmd.configure()
        self.assertTrue(self.cmd.cli.demands.allow_erasing)

    @mock.patch('dnf.cli.commands.remove._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, tests.support.command_run, self.cmd,
                              ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())
