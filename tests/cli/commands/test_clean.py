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
from tests import support
from tests.support import mock

import dnf.cli.commands.clean as clean
import os
import tests.support


class CleanTest(tests.support.TestCase):
    def setUp(self):
        base = support.MockBase("main")
        base.output = mock.MagicMock()

        repo = base.repos['main']
        repo.baseurl = ['http:///dnf-test']
        repo.basecachedir = base.conf.cachedir

        walk = [
            (
                repo.basecachedir,
                [os.path.basename(repo.cachedir)],
                [repo.id + '.solv'],
            ),
            (repo.cachedir, ['repodata', 'packages'], ['metalink.xml']),
            (repo.cachedir + '/repodata', [], ['foo.xml', 'bar.xml.bz2']),
            (repo.cachedir + '/packages', [], ['foo.rpm']),
        ]
        os.walk = self.walk = mock.Mock(return_value=walk)
        self.base = base
        self.cmd = clean.CleanCommand(base.mock_cli())

    def test_run(self):
        with mock.patch('dnf.cli.commands.clean._clean') as _clean:
            self.cmd.run(['all'])
            self.cmd.run(['metadata'])
            self.cmd.run(['metadata', 'packages'])
            self.cmd.run(['metadata', 'packages', 'expire-cache'])
            self.cmd.run(['dbcache'])
            self.cmd.run(['expire-cache'])

        calls = [call[0] for call in _clean.call_args_list]
        counts = (5, 4, 5, 5, 1, 0)
        for call, count in zip(calls, counts):
            files = list(call[1])
            assert len(files) == count

    def test_walk_once(self):
        self.cmd.run(['all'])
        assert len(self.walk.call_args_list) == 1

    def test_clean_local_repo(self):
        cachedir = self.base.conf.cachedir
        repo = self.base.repos['main']
        repo.baseurl = ['file:///localrepo']

        self.cmd.run(['all'])

        # Make sure we never looked outside the base cachedir
        dirs = [call[0][0] for call in self.walk.call_args_list]
        assert all(d == cachedir for d in dirs)
