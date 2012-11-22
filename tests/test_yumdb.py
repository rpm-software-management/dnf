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
import dnf.yum.rpmsack
from dnf.queries import installed_by_name
import mock
import unittest

@mock.patch('os.path.exists', return_value=True)
class TestAdditionalPkgDB(unittest.TestCase):
    def test_instantiate(self, mock_exists):
        yumbase = base.MockYumBase()
        path = yumbase.conf.persistdir + '/yumdb'
        pkgdb = dnf.yum.rpmsack.AdditionalPkgDB(path)
        pkg = installed_by_name(yumbase.sack, "pepper")[0]
        directory = pkgdb._get_dir_name(pkg.pkgtup, pkg.pkgid)
        self.assertEqual("%s/yumdb/p/<nopkgid>-pepper-20-0-x86_64" %
                         yumbase.conf.persistdir,
                         directory)
