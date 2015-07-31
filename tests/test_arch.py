# Copyright (C) 2012-2014  Red Hat, Inc.
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

import dnf.arch
import tests.support


class FunctionsTest(tests.support.TestCase):

    def test_basearch(self):
        fn = dnf.arch.basearch
        self.assertEqual(fn('armv6hl'), 'armhfp')
        self.assertEqual(fn('armv7hl'), 'armhfp')
        self.assertEqual(fn('i686'), 'i386')
        self.assertEqual(fn('noarch'), 'noarch')
        self.assertEqual(fn('ppc64iseries'), 'ppc64')
        self.assertEqual(fn('sparc64v'), 'sparc64')
        self.assertEqual(fn('x86_64'), 'x86_64')

    def test_is_valid_arch(self):
        self.assertTrue(dnf.arch.is_valid_arch("i386"))
        self.assertTrue(dnf.arch.is_valid_arch("i686"))
        self.assertTrue(dnf.arch.is_valid_arch("x86_64"))
        self.assertFalse(dnf.arch.is_valid_arch("armhfp"))
        self.assertFalse(dnf.arch.is_valid_arch("foo"))

    def test_is_valid_basearch(self):
        self.assertTrue(dnf.arch.is_valid_basearch("i386"))
        self.assertFalse(dnf.arch.is_valid_basearch("i686"))
        self.assertTrue(dnf.arch.is_valid_basearch("x86_64"))
        self.assertTrue(dnf.arch.is_valid_basearch("armhfp"))
        self.assertFalse(dnf.arch.is_valid_basearch("foo"))


class ArchTest(tests.support.TestCase):

    def test_src(self):
        a = dnf.arch.Arch("src")
        self.assertEqual(a.arches, ["src", "nosrc"])
        self.assertEqual(a.native_arches, ["src", "nosrc"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, True)

    def test_noarch(self):
        a = dnf.arch.Arch("noarch")
        self.assertEqual(a.arches, ["noarch"])
        self.assertEqual(a.native_arches, ["noarch"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, True)
        self.assertEqual(a.is_source, False)

    def test_i386(self):
        a = dnf.arch.Arch("i386")
        self.assertEqual(a.arches, ["i386", "noarch"])
        self.assertEqual(a.native_arches, ["i386"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_i686(self):
        a = dnf.arch.Arch("i686")
        self.assertEqual(a.arches, ["i686", "i586", "i486", "i386", "noarch"])
        self.assertEqual(a.native_arches, ["i686", "i586", "i486", "i386"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_i686_all(self):
        a = dnf.arch.Arch("i686", just_compatible=False)
        self.assertEqual(a.arches, ["athlon", "geode", "i686", "i586", "i486", "i386", "noarch"])
        self.assertEqual(a.native_arches, ["athlon", "geode", "i686", "i586", "i486", "i386"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_x86_64(self):
        a = dnf.arch.Arch("x86_64")
        self.assertEqual(a.arches, ["x86_64", "athlon", "i686", "i586", "i486", "i386", "noarch"])
        self.assertEqual(a.native_arches, ["x86_64"])
        self.assertEqual(a.multilib_arches, ["athlon", "i686", "i586", "i486", "i386"])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, True)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_x86_64_all(self):
        a = dnf.arch.Arch("x86_64", just_compatible=False)
        self.assertEqual(a.arches, ["amd64", "ia32e", "x86_64", "athlon", "geode", "i686", "i586", "i486", "i386", "noarch"])
        self.assertEqual(a.native_arches, ["amd64", "ia32e", "x86_64"])
        self.assertEqual(a.multilib_arches, ["athlon", "geode", "i686", "i586", "i486", "i386"])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, True)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_armhfp(self):
        a = dnf.arch.Arch("armhfp", basearch=True)
        self.assertEqual(a.arches, ["armv7hnl", "armv7hl", "armv6hl", "noarch"])
        self.assertEqual(a.native_arches, ["armv7hnl", "armv7hl", "armv6hl"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparc(self):
        a = dnf.arch.Arch("sparc")
        self.assertEqual(a.arches, ["sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparc"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparcv8(self):
        a = dnf.arch.Arch("sparcv8")
        self.assertEqual(a.arches, ["sparcv8", "sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparcv8", "sparc"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparcv9(self):
        a = dnf.arch.Arch("sparcv9")
        self.assertEqual(a.arches, ["sparcv9", "sparcv8", "sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparcv9", "sparcv8", "sparc"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparcv9v(self):
        a = dnf.arch.Arch("sparcv9v")
        self.assertEqual(a.arches, ["sparcv9v", "sparcv9", "sparcv8", "sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparcv9v", "sparcv9", "sparcv8", "sparc"])
        self.assertEqual(a.multilib_arches, [])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, False)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparc64(self):
        a = dnf.arch.Arch("sparc64")
        self.assertEqual(a.arches, ["sparc64", "sparcv9", "sparcv8", "sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparc64"])
        self.assertEqual(a.multilib_arches, ["sparcv9", "sparcv8", "sparc"])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, True)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_sparc64v(self):
        a = dnf.arch.Arch("sparc64v")
        self.assertEqual(a.arches, ["sparc64v", "sparc64", "sparcv9v", "sparcv9", "sparcv8", "sparc", "noarch"])
        self.assertEqual(a.native_arches, ["sparc64v", "sparc64"])
        self.assertEqual(a.multilib_arches, ["sparcv9v", "sparcv9", "sparcv8", "sparc"])
        self.assertEqual(a.noarch_arches, ["noarch"])
        self.assertEqual(a.source_arches, ["src", "nosrc"])
        self.assertEqual(a.is_multilib, True)
        self.assertEqual(a.is_noarch, False)
        self.assertEqual(a.is_source, False)

    def test_cmp(self):
        a_i386 = dnf.arch.Arch("i386")
        a_i686 = dnf.arch.Arch("i686")
        a_x86_64 = dnf.arch.Arch("x86_64")
        a_ppc64 = dnf.arch.Arch("ppc64")

        self.assertTrue(a_i386 == a_i386)

        self.assertFalse(a_i386 > a_i386)
        self.assertFalse(a_i386 < a_i386)

        self.assertTrue(a_i386 >= a_i386)
        self.assertTrue(a_i386 <= a_i386)

        self.assertTrue(a_i386 < a_i686)
        self.assertTrue(a_i686 > a_i386)

        self.assertTrue(a_i386 <= a_i686)
        self.assertTrue(a_i686 >= a_i386)

        self.assertTrue(a_i386 < a_x86_64)
        self.assertTrue(a_x86_64 > a_i386)

        self.assertTrue(a_i386 <= a_x86_64)
        self.assertTrue(a_x86_64 >= a_i386)

        self.assertTrue(a_x86_64 != a_ppc64)
        self.assertRaises(ValueError, a_x86_64.__lt__, a_ppc64)
        self.assertRaises(ValueError, a_x86_64.__gt__, a_ppc64)
