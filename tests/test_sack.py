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
import hawkey
import hawkey.test
import base
import mock
import unittest

class Sack(base.TestCase):
    def test_rpmdb_version(self):
        yumbase = base.MockYumBase()
        sack = yumbase.sack
        yumdb = mock.MagicMock()
        version = yumbase.sack.rpmdb_version(yumdb)
        self.assertEqual(version._num, base.TOTAL_RPMDB_COUNT)
        self.assertEqual(version._chksum.hexdigest(),
                         '7229c365cd8a7eea755d0495a8216226f705d161')

    def test_configuration(self):
        yumbase = base.MockYumBase()
        yumbase.conf.exclude=['pepper']
        # configure() gets called through here:
        sack = yumbase.sack
        peppers = hawkey.Query(sack).filter(name='pepper').run()
        self.assertLength(peppers, 0)
