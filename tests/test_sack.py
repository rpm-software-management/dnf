# Copyright (C) 2012  Red Hat, Inc.
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

import dnf.sack
import hawkey.test
import base
import mock
import unittest

class Sack(unittest.TestCase):
    def test_ensure_filelists(self):
        sack = dnf.sack.Sack(cachedir=hawkey.test.UNITTEST_DIR)
        sack.load_filelists = mock.Mock()
        sack.write_filelists = mock.Mock()
        # try calling the
        mock_attrs = {"listEnabled.return_value" : []}
        repos = mock.Mock(**mock_attrs)
        sack.ensure_filelists(repos)
        self.assertEqual(sack.load_filelists.call_count, 1)
        self.assertEqual(sack.write_filelists.call_count, 1)

    def test_rpmdb_version(self):
        yumbase = base.mock_yum_base()
        sack = yumbase.sack
        yumdb = mock.MagicMock()
        version = yumbase.sack.rpmdb_version(yumdb)
        self.assertEqual(version._num, base.TOTAL_RPMDB_COUNT)
        self.assertEqual(version._chksum.hexdigest(),
                         "6034f87b90f13af4fdf2e8bded72d37e5d00f0ca")
