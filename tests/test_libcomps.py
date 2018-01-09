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

import libcomps

import tests.support


class LibcompsTest(tests.support.TestCase):

    """Sanity tests of the Libcomps library."""

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
        comps = libcomps.Comps()
        ret = comps.fromxml_str(xml)
        self.assertGreaterEqual(ret, 0)

    def test_segv(self):
        c1 = libcomps.Comps()
        c2 = libcomps.Comps()
        c2.fromxml_f(tests.support.COMPS_PATH)
        c1 + c2  # sigsegved here

    def test_segv2(self):
        c1 = libcomps.Comps()
        c1.fromxml_f(tests.support.COMPS_PATH)

        c2 = libcomps.Comps()
        c2.fromxml_f(tests.support.COMPS_PATH)

        c = c1 + c2
        c.groups[0].packages[0].name
