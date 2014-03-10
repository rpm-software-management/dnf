# Copyright (C) 2014  Red Hat, Inc.
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

"""Tests of the CLI entry point."""

from tests.support import mock

import dnf.cli.main
import os
import tempfile
import tests.support

class MainTestCase(tests.support.TestCase):

    """Tests of ``dnf.cli.main.main`` function."""

    @staticmethod
    def create_config():
        """Create a configuration file and return its path."""
        with tempfile.NamedTemporaryFile('wb', delete=False) as file_:
            file_.write(b'[main]\nplugins=0\n')
        return file_.name

    @classmethod
    def setUpClass(cls):
        """Prepare the test fixture."""
        super(MainTestCase, cls).setUpClass()
        cls.config_path = cls.create_config()
        cls.options = ['--config=%s' % cls.config_path]

    @classmethod
    def tearDownClass(cls):
        """Tear down the test fixture."""
        super(MainTestCase, cls).tearDownClass()
        os.remove(cls.config_path)

    def test_logs_traceback(self):
        """Test whether the traceback is logged if an error is raised."""
        error = OSError('test_prints_traceback')

        check_patcher = mock.patch.object(dnf.cli.cli.Cli, 'check',
                                          autospec=True, side_effect=error)
        with check_patcher, tests.support.patch_std_streams() as (out, _err):
            self.run_main(['--verbose'])

        self.assertTracebackIn('%s\n' % error, out.getvalue())

    @classmethod
    def run_main(cls, options=(), command=('repolist',)):
        """Run the given *command* with the given *options*."""
        dnf.cli.main.main(list(options) + cls.options + list(command))
