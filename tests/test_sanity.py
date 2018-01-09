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

import os
import sys

import tests.support


class Sanity(tests.support.TestCase):
    def test_sanity(self):
        assert(os.access(tests.support.repo("@System.repo"), os.R_OK))
        sack = tests.support.mock_sack()
        assert(sack)
        self.assertEqual(len(sack), tests.support.SYSTEM_NSOLVABLES)

        sack2 = tests.support.MockBase("main", "updates").sack
        self.assertEqual(len(sack2), tests.support.TOTAL_NSOLVABLES)

    def test_toplevel(self):
        self.assertIn(tests.support.dnf_toplevel(), sys.path)
