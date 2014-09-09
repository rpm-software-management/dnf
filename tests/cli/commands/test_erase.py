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
from __future__ import unicode_literals
from tests import support
from tests.support import mock

import dnf.cli.commands.erase
import logging

class EraseCommandTest(support.ResultTestCase):
    """Tests of ``dnf.cli.commands.EraseCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(EraseCommandTest, self).setUp()
        base = support.BaseCliStub()
        base.init_sack()
        self.cmd = dnf.cli.commands.erase.EraseCommand(base.mock_cli())

    def test_configure(self):
        self.cmd.configure([])
        self.assertTrue(self.cmd.cli.demands.allow_erasing)

    @mock.patch('dnf.cli.commands.erase._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, self.cmd.run,
                              ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())
