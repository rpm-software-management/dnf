# Copyright (C) 2012-2016 Red Hat, Inc.
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

import dnf.exceptions
import dnf.repo
import dnf.sack

class SackTest(support.TestCase):
    def test_rpmdb_version(self):
        base = support.MockBase()
        sack = base.sack
        yumdb = mock.MagicMock()
        version = base.sack._rpmdb_version(yumdb)
        self.assertEqual(version._num, support.TOTAL_RPMDB_COUNT)
        self.assertEqual(version._chksum.hexdigest(), support.RPMDB_CHECKSUM)

    def test_setup_excludes_includes(self):
        base = support.MockBase()
        base.conf.excludepkgs=['pepper']
        base._setup_excludes_includes()
        peppers = base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 0)

        base = support.MockBase()
        base.conf.exclude=['pepper']
        base._setup_excludes_includes()
        peppers = base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 0)

        base = support.MockBase()
        base.conf.disable_excludes = ['all']
        base.conf.excludepkgs=['pepper']
        base._setup_excludes_includes()
        peppers = base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 1)

        base = support.MockBase('main')
        base.repos['main'].excludepkgs=['pepp*']
        base._setup_excludes_includes()
        peppers = base.sack.query().filter(name='pepper', reponame='main')
        self.assertLength(peppers, 0)

        base = support.MockBase()
        base.conf.excludepkgs = ['*.i?86']
        base.conf.includepkgs = ['lib*']
        base._setup_excludes_includes()
        peppers = base.sack.query().filter().run()
        self.assertLength(peppers, 1)
        self.assertEqual(str(peppers[0]), "librita-1-1.x86_64")

    @mock.patch('dnf.sack._build_sack', lambda x: mock.Mock())
    @mock.patch('dnf.goal.Goal', lambda x: mock.Mock())
    def test_fill_sack(self):
        def raiser():
            raise dnf.exceptions.RepoError()

        base = support.MockBase()
        r = support.MockRepo('bag', base.conf)
        r.enable()
        base._repos.add(r)
        r.load = mock.Mock(side_effect=raiser)
        r.skip_if_unavailable = False
        self.assertRaises(dnf.exceptions.RepoError,
                          base.fill_sack, load_system_repo=False)
        self.assertTrue(r.enabled)
        self.assertTrue(r._check_config_file_age)
        r.skip_if_unavailable = True
        base.fill_sack(load_system_repo=False)
        self.assertFalse(r.enabled)
