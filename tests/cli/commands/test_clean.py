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

from __future__ import absolute_import
from __future__ import unicode_literals
from tests.support import mock

import dnf.const
import dnf.cli.commands.clean as clean
import hawkey
import tests.support


class CleanTest(tests.support.TestCase):
    def test_clean_binary_cache(self):
        base = tests.support.MockBase('main')
        with mock.patch('os.access', return_value=True) as access,\
             mock.patch('dnf.cli.commands.clean._clean_filelist'):
            clean._clean_binary_cache(base.repos, base.conf.cachedir)
        self.assertEqual(len(access.call_args_list), 5)
        fname = access.call_args_list[0][0][0]
        assert fname.startswith(dnf.const.TMPDIR)
        assert fname.endswith(hawkey.SYSTEM_REPO_NAME + '.solv')
        fname = access.call_args_list[1][0][0]
        assert fname.endswith('main.solv')
        fname = access.call_args_list[2][0][0]
        assert fname.endswith('main-filenames.solvx')

    def test_clean_files_local(self):
        """Do not delete files from a local repo."""
        base = tests.support.MockBase("main")
        repo = base.repos['main']
        repo.baseurl = ['file:///dnf-bad-test']
        repo.basecachedir = '/tmp/dnf-bad-test'
        with mock.patch('dnf.cli.commands.clean._clean_filelist'),\
             mock.patch('os.path.exists', return_value=True) as exists_mock:
            dnf.cli.commands.clean._clean_files(base.repos, ['rpm'], 'pkgdir',
                                                'package')
        # local repo is not even checked for directory existence:
        self.assertIsNone(exists_mock.call_args)
