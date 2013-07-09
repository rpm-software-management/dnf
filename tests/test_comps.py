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
import dnf.comps
import dnf.yum.comps
import dnf.util
import libcomps

TRANSLATION=u"""Tato skupina zahrnuje nejmenší možnou množinu balíčků. Je vhodná například na instalace malých routerů nebo firewallů."""

class CompsTest(support.TestCase):
    def setUp(self):
        comps = dnf.comps.Comps()
        comps.add_from_xml_filename(support.COMPS_PATH)
        self.comps = comps

    def test_by_pattern(self):
        comps = self.comps
        self.assertLength(comps.groups_by_pattern('Base'), 1)
        self.assertLength(comps.groups_by_pattern('*'), 2)
        self.assertLength(comps.groups_by_pattern('Base, Solid*'), 2)

    def test_compile(self):
        yumbase = support.MockYumBase("main")
        sack = yumbase.sack

        comps = self.comps
        groups = comps.groups
        self.assertLength(groups, 2)
        comps.compile(sack.query().installed())
        # ensure even groups obtained before compile() have the property set:
        self.assertTrue(groups[0].installed)
        self.assertFalse(groups[1].installed)

    def test_iteration(self):
        comps = self.comps
        self.assertEqual([g.name for g in comps.groups_iter],
                         ['Base', 'Solid Ground'])
        self.assertEqual([c.name for c in comps.categories_iter],
                         ['Base System'])
        g = dnf.util.first(comps.groups_iter)
        self.assertEqual(g.desc_by_lang['cs'], TRANSLATION)

    def test_packages(self):
        comps = self.comps
        group = dnf.util.first(comps.groups_iter)
        self.assertSequenceEqual([pkg.name for pkg in group.packages],
                                 (u'pepper', u'tour'))
        self.assertSequenceEqual([pkg.name for pkg in group.mandatory_packages],
                                 (u'pepper', u'tour'))

    def test_size(self):
        comps = self.comps
        self.assertLength(comps, 3)
        self.assertLength(comps.groups, 2)
        self.assertLength(comps.categories, 1)
        self.assertLength(comps.environments, 0)

class LibcompsTest(support.TestCase):

    """Sanity tests of the Libcomps library."""

    @support.skip
    def test_environment_parse(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
   <id>somerset</id>
   <default>true</default>
   <uservisible>true</uservisible>
   <display_order>1024</display_order>
   <name>Solid Ground</name>
   <description>--</description>
    <packagelist>
      <packagereq type="mandatory">pepper</packagereq>
      <packagereq type="mandatory">trampoline</packagereq>
    </packagelist>
  </group>
  <environment>
    <id>minimal</id>
    <name>Min install</name>
    <description>Basic functionality.</description>
    <display_order>5</display_order>
    <grouplist>
      <groupid>somerset</groupid>
    </grouplist>
  </environment>
</comps>
"""
        errors = libcomps.Comps().fromxml_str(xml)
        self.assertLength(errors, 0)

    def test_segv(self):
        c1 = libcomps.Comps()
        c2 = libcomps.Comps()
        c2.fromxml_f(support.COMPS_PATH)
        c = c1 + c2 # sigsegved here

    def test_segv2(self):
        c1 = libcomps.Comps()
        c1.fromxml_f(support.COMPS_PATH)

        c2 = libcomps.Comps()
        c2.fromxml_f(support.COMPS_PATH)

        c = c1 + c2
        x = c.groups[0].packages[0].name
