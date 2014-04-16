# Copyright (C) 2012-2013  Red Hat, Inc.
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

import io
import dnf.repo
import dnf.sack
import dnf.exceptions
import itertools

class SackTest(support.TestCase):
    def test_rpmdb_version(self):
        base = support.MockBase()
        sack = base.sack
        yumdb = mock.MagicMock()
        version = base.sack.rpmdb_version(yumdb)
        self.assertEqual(version._num, support.TOTAL_RPMDB_COUNT)
        self.assertEqual(version._chksum.hexdigest(), support.RPMDB_CHECKSUM)

    def test_setup_excludes(self):
        base = support.MockBase()
        base.conf.exclude=['pepper']
        base._setup_excludes()
        peppers = base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 0)

        base = support.MockBase()
        base.conf.disable_excludes = ['all']
        base.conf.exclude=['pepper']
        base._setup_excludes()
        peppers = base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 1)

        base = support.MockBase('main')
        base.repos['main'].exclude=['pepp*']
        base._setup_excludes()
        peppers = base.sack.query().filter(name='pepper', reponame='main')
        self.assertLength(peppers, 0)

    def test_add_repo_to_sack(self):
        def raiser():
            raise dnf.exceptions.RepoError()

        base = support.MockBase()
        r = support.MockRepo('bag', None)
        r.enable()
        base._repos.add(r)
        r.load = mock.Mock(side_effect=raiser)
        r.skip_if_unavailable = False
        self.assertRaises(dnf.exceptions.RepoError,
                          base._add_repo_to_sack, "bag")
        self.assertTrue(r.enabled)
        r.skip_if_unavailable = True
        base._add_repo_to_sack("bag")
        self.assertFalse(r.enabled)

class SusetagsTest(support.TestCase):
    def susetags_test(self):
        buf = io.StringIO()
        base = support.MockBase("main")
        base.sack.susetags_for_repo(buf, "main")
        buf.seek(0)

        def nonmatch(line):
            return not line.startswith('=Pkg: pepper 20 0 x86_64')
        pepper = itertools.dropwhile(nonmatch, buf.readlines())
        pepper = [dnf.util.first(pepper)] + list(itertools.takewhile(
                lambda x: not x.startswith("=Pkg: "), pepper))
        self.assertItemsEqual(pepper,
                              ['=Pkg: pepper 20 0 x86_64\n',
                               '=Prv: pepper = 20-0\n',
                               '=Req: librita >= 1-0\n'])
