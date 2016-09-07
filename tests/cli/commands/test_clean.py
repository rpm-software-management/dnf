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
from __future__ import unicode_literals
from io import StringIO
from tests import support
from tests.support import mock

import dnf.cli.cli
import dnf.cli.commands.clean as clean
import os
import tests.support


def _run(cli, args):
    with mock.patch('sys.stdout', new_callable=StringIO) as stdout, \
         mock.patch('dnf.rpm.detect_releasever', return_value=69):
        cli.configure(['clean', '--config', '/dev/null'] + args)
        cli.run()

class CleanTest(tests.support.TestCase):
    def setUp(self):
        conf = dnf.conf.Conf()
        base = support.Base(conf)
        base.repos.add(support.MockRepo('main', conf))
        base.conf.reposdir = '/dev/null'
        base.conf.plugins = False
        base.output = support.MockOutput()

        repo = base.repos['main']
        repo.baseurl = ['http:///dnf-test']
        repo.basecachedir = base.conf.cachedir

        walk = [
            (
                repo.basecachedir,
                [os.path.basename(repo._cachedir)],
                [repo.id + '.solv'],
            ),
            (repo._cachedir, ['repodata', 'packages'], ['metalink.xml']),
            (repo._cachedir + '/repodata', [], ['foo.xml', 'bar.xml.bz2']),
            (repo._cachedir + '/packages', [], ['foo.rpm']),
        ]
        os.walk = self.walk = mock.Mock(return_value=walk)
        self.base = base
        self.cli = dnf.cli.cli.Cli(base)

    def test_run(self):
        with mock.patch('dnf.cli.commands.clean._clean') as _clean:
            for args in [['all'],
                         ['metadata'],
                         ['metadata', 'packages'],
                         ['metadata', 'packages', 'expire-cache'],
                         ['dbcache'],
                         ['expire-cache']]:
                _run(self.cli, args)

        calls = [call[0] for call in _clean.call_args_list]
        counts = (5, 4, 5, 5, 1, 0)
        for call, count in zip(calls, counts):
            files = list(call[1])
            assert len(files) == count

    def test_walk_once(self):
        _run(self.cli, ['all'])
        assert len(self.walk.call_args_list) == 1

    def test_clean_local_repo(self):
        cachedir = self.base.conf.cachedir
        repo = self.base.repos['main']
        repo.baseurl = ['file:///localrepo']

        _run(self.cli, ['all'])

        # Make sure we never looked outside the base cachedir
        dirs = [call[0][0] for call in self.walk.call_args_list]
        assert all(d == cachedir for d in dirs)
