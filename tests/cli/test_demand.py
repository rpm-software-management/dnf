# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

import dnf.cli.demand

import tests.support


class DemandTest(tests.support.TestCase):

    def test_bool_default(self):
        demands = dnf.cli.demand.DemandSheet()
        demands.resolving = True
        self.assertTrue(demands.resolving)
        demands.resolving = True
        self.assertTrue(demands.resolving)
        with self.assertRaises(AttributeError):
            demands.resolving = False

    def test_default(self):
        demands = dnf.cli.demand.DemandSheet()
        self.assertFalse(demands.resolving)
        self.assertFalse(demands.sack_activation)
        self.assertFalse(demands.root_user)
        self.assertEqual(demands.success_exit_status, 0)

    def test_independence(self):
        d1 = dnf.cli.demand.DemandSheet()
        d1.resolving = True
        d2 = dnf.cli.demand.DemandSheet()
        self.assertTrue(d1.resolving)
        self.assertFalse(d2.resolving)
