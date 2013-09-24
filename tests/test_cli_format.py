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

from dnf.cli.format import format_time, format_number
import unittest
from tests.support import PycompTestCase

class FormatTest(PycompTestCase):
    def test_format_time(self):
        self.assertEquals(format_time(None), '--:--')
        self.assertEquals(format_time(-1), '--:--')
        self.assertEquals(format_time(12*60+34), '12:34')
        self.assertEquals(format_time(12*3600+34*60+56), '754:56')
        self.assertEquals(format_time(12*3600+34*60+56, use_hours=True), '12:34:56')
    def test_format_number(self):
        self.assertEquals(format_number(None), '0.0  ')
        self.assertEquals(format_number(-1), '-1  ')
        self.assertEquals(format_number(1.0), '1.0  ')
        self.assertEquals(format_number(999.0), '999  ')
        self.assertEquals(format_number(1000.0), '1.0 k')
        self.assertEquals(format_number(1 << 20), '1.0 M')
        self.assertEquals(format_number(1 << 30), '1.0 G')
        self.assertEquals(format_number(1e6, SI=1), '1.0 M')
        self.assertEquals(format_number(1e9, SI=1), '1.0 G')

