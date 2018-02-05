# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import tests.support


class ProvidesTest(tests.support.DnfBaseTestCase):

    REPOS = ['main']

    def test_file(self):
        self.assertLength(self.base.provides("*ais*smile")[0], 1)
        self.assertLength(self.base.provides("/raised/smile")[0], 1)

    def test_name(self):
        self.assertLength(self.base.provides("henry(the_horse)")[0], 1)
        self.assertLength(self.base.provides("lotus")[0], 2)

    def test_glob(self):
        self.assertLength(self.base.provides("henry(*)")[0], 1)
        self.assertEqual(set(self.base.provides("dup*")[0]), set(self.base.provides('dup')[0]))
        self.assertEqual(set(self.base.provides(["dup*"])[0]), set(self.base.provides('dup')[0]))
