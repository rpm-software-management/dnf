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

import base
import dnf.yum.history
import hawkey
import mock
import unittest

from dnf.queries import installed_by_name, available_by_name

class TestedHistory(dnf.yum.history.YumHistory):
    @mock.patch("os.path.exists", return_value=True)
    def __init__(self, unused_exists):
        self._db_date = "1962-07-12"
        super(TestedHistory, self).__init__("/does-not-exist", mock.Mock())

    def _create_db_file(self):
        return None

class History(unittest.TestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")
        self.sack = self.yumbase.sack
        self.history = TestedHistory()

    def pkgtup2pid_test(self):
        """ Check pkg2pid() correctly delegates to _*2pid()s. """
        hpkg = dnf.yum.history.YumHistoryPackage("n", "a", "e", "v", "r")
        with mock.patch.object(self.history, "_hpkg2pid") as hpkg2pid:
            self.history.pkg2pid(hpkg)
            hpkg2pid.assert_called_with(hpkg, True)

        ipkg = installed_by_name(self.sack, "pepper")[0]
        with mock.patch.object(self.history, "_ipkg2pid") as ipkg2pid:
            self.history.pkg2pid(ipkg)
            ipkg2pid.assert_called_with(ipkg, True)

        apkg = available_by_name(self.sack, "lotus")[0]
        with mock.patch.object(self.history, "_apkg2pid") as apkg2pid:
            self.history.pkg2pid(apkg)
            apkg2pid.assert_called_with(apkg, True)
