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

import dnf
import logging

import tests.support
from tests.support import mock


class MarkCommandTest(tests.support.DnfBaseTestCase):
    """Tests of ``dnf.cli.commands.MarkCommand`` class."""

    REPOS = ["main"]
    CLI = "mock"

    def setUp(self):
        super(MarkCommandTest, self).setUp()
        self.cmd = dnf.cli.commands.mark.MarkCommand(self.cli)

    @mock.patch('dnf.cli.commands.mark._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        tests.support.command_configure(self.cmd, ['install', 'non-existent'])
        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            with self.assertRaises(dnf.cli.CliError):
                self.cmd.run()
        self.assertEqual(stdout.getvalue(),
                         'Error:\nPackage non-existent is not installed.\n')

    @mock.patch('dnf.cli.commands.mark._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run(self):
        """Test whether it fails if the package cannot be found."""

        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            tests.support.command_run(self.cmd, ['install', 'pepper-20-0.x86_64'])
        self.assertEqual(stdout.getvalue(),
                         'pepper-20-0.x86_64 marked as user installed.\npepper-20-0.x86_64 marked as user installed.\n')
