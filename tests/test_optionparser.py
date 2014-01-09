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
try:
    from unittest import mock
except ImportError:
    from tests import mock
from tests import support
from dnf.cli.cli import YumOptionParser
import optparse

class OptionParserTest(support.TestCase):
    def setUp(self):
        self.yumbase = support.MockBase()
        output = support.MockOutput()
        self.yumbase.output = output

    def test_simple(self):
        parser = YumOptionParser(self.yumbase)
        self.assertFalse(self.yumbase.conf.assumeyes)
        parser.setupYumConfig(args=['update', '-y'])
        self.assertTrue(self.yumbase.conf.assumeyes)

    def test_nogpgcheck(self):
        parser = YumOptionParser(self.yumbase)
        del self.yumbase.repos
        # this doesn't try to access yumbase.repos:
        parser.setupYumConfig(args=['update', '--nogpgcheck'])

    def test_non_nones2dict(self):
        parser = YumOptionParser(self.yumbase)
        values = parser.parse_args(args=['-y', '--disableplugin=meter,maid'])[0]
        self.assertIsInstance(values, optparse.Values)
        dct = parser._non_nones2dict(values)
        self.assertTrue(dct['assumeyes'])
        self.assertItemsEqual(dct['disableplugins'], ['meter', 'maid'])
