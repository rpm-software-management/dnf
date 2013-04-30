# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
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
from tests import support
import dnf.yum.comps

TRANSLATION="""Tato skupina zahrnuje nejmenší možnou množinu balíčků. Je vhodná například na instalace malých routerů nebo firewallů."""

class CompsTest(support.TestCase):
    # Also see test_base.py:CompsTest

    def test_comps(self):
        comps = dnf.yum.comps.Comps()
        comps.add(support.COMPS_PATH)
        self.assertEqual([g.name for g in comps.groups],
                         ['Base', 'Solid Ground'])
        self.assertEqual([c.name for c in comps.categories],
                         ['Base System'])
        g = comps.groups[0]
        self.assertEqual(g.translated_description['cs'], TRANSLATION)

    def test_compile(self):
        yumbase = support.MockYumBase("main")
        sack = yumbase.sack

        comps = dnf.yum.comps.Comps()
        comps.add(support.COMPS_PATH)
        groups = comps.groups
        self.assertLength(groups, 2)

        comps.compile(sack.query().installed())
        self.assertTrue(groups[0].installed)
        self.assertFalse(groups[1].installed)
