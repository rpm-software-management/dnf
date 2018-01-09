# -*- coding: utf-8 -*-

# Copyright (C) 2015-2018 Red Hat, Inc.
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

import dnf

import tests.support


class DowngradeTo(tests.support.ResultTestCase):

    def setUp(self):
        self.base = tests.support.MockBase('main', 'old_versions')

    def test_downgrade_to_lowest(self):
        with tests.support.mock.patch('logging.Logger.warning'):
            with self.assertRaises(dnf.exceptions.PackagesNotInstalledError):
                self.base.downgrade_to('hole')
        self.assertResult(self.base, self.base._sack.query().installed())

    def test_downgrade_to_name(self):
        self.base.downgrade_to('tour')
        (installed, removed) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('tour-4.9-1.noarch',))
        self.assertCountEqual(map(str, removed),
                              ('tour-5-0.noarch',))

    def test_downgrade_to_wildcard_name(self):
        self.base.downgrade_to('tour*')
        (installed, removed) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('tour-4.9-1.noarch',))
        self.assertCountEqual(map(str, removed),
                              ('tour-5-0.noarch',))

    def test_downgrade_to_version(self):
        self.base.downgrade_to('tour-4.6')
        (installed, removed) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('tour-4.6-1.noarch',))
        self.assertCountEqual(map(str, removed),
                              ('tour-5-0.noarch',))
