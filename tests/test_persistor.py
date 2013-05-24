# Copyright (C) 2013  Red Hat, Inc.
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
import dnf.persistor
import tempfile
import tests.support

IDS = set(['one', 'two', 'three'])

class PersistorTest(tests.support.TestCase):
    def setUp(self):
        self.persistdir = tempfile.mkdtemp(prefix="dnf-repotest-")

    def tearDown(self):
        dnf.util.rm_rf(self.persistdir)

    def test_expired_repos(self):
        prst = dnf.persistor.Persistor(self.persistdir)
        self.assertLength(prst.get_expired_repos(), 0)
        prst.set_expired_repos(IDS)
        self.assertEqual(prst.get_expired_repos(), IDS)

        prst = dnf.persistor.Persistor(self.persistdir)
        self.assertEqual(prst.get_expired_repos(), IDS)
