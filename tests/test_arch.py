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
from tests import support

import unittest
import dnf.rpmUtils.arch

class Arch(support.TestCase):

    def test_basearch(self):
        arches = [
            ('alpha', 'alpha'),
            ('alphaev4', 'alpha'),
            ('alphaev45', 'alpha'),
            ('alphaev5', 'alpha'),
            ('alphaev56', 'alpha'),
            ('alphaev6', 'alpha'),
            ('alphaev67', 'alpha'),
            ('alphaev68', 'alpha'),
            ('alphaev7', 'alpha'),
            ('alphapca56', 'alpha'),
            ('amd64', 'x86_64'),
            ('aarch64', 'aarch64'),
            ('armv5tejl', 'arm'),
            ('armv5tel', 'arm'),
            ('armv6l', 'arm'),
            ('armv7hl', 'armhfp'),
            ('armv7hnl', 'armhfp'),
            ('armv7l', 'arm'),
            ('athlon', 'i386'),
            ('geode', 'i386'),
            ('i386', 'i386'),
            ('i486', 'i386'),
            ('i586', 'i386'),
            ('i686', 'i386'),
            ('ia32e', 'x86_64'),
            ('ia64', 'ia64'),
            ('ppc', 'ppc'),
            ('ppc64', 'ppc64'),
            ('ppc64le', 'ppc64le'),
            ('ppc64iseries', 'ppc64'),
            ('ppc64p7', 'ppc64'),
            ('ppc64pseries', 'ppc64'),
            ('s390', 's390'),
            ('s390x', 's390x'),
            ('sh3', 'sh3'),
            ('sh4', 'sh4'),
            ('sh4a', 'sh4'),
            ('sparc', 'sparc'),
            ('sparc64', 'sparc'),
            ('sparc64v', 'sparc'),
            ('sparcv8', 'sparc'),
            ('sparcv9', 'sparc'),
            ('sparcv9v', 'sparc'),
            ('x86_64', 'x86_64'),
        ]
        for arch, basearch in arches:
            self.assertEqual(dnf.rpmUtils.arch.getBaseArch(arch), basearch)

    def test_is_multilib(self):
        arches = [
            ('alpha', False),
            ('alphaev4', False),
            ('alphaev45', False),
            ('alphaev5', False),
            ('alphaev56', False),
            ('alphaev6', False),
            ('alphaev67', False),
            ('alphaev68', False),
            ('alphaev7', False),
            ('alphapca56', False),
            ('amd64', True),
            ('aarch64', False),
            ('armv5tejl', False),
            ('armv5tel', False),
            ('armv6l', False),
            ('armv7hl', False),
            ('armv7hnl', False),
            ('armv7l', False),
            ('athlon', False),
            ('geode', False),
            ('i386', False),
            ('i486', False),
            ('i586', False),
            ('i686', False),
            ('ia32e', True),
            ('ia64', False),
            ('ppc', False),
            ('ppc64', True),
            ('ppc64le', False),
            ('ppc64iseries', True),
            ('ppc64p7', True),
            ('ppc64pseries', True),
            ('s390', False),
            ('s390x', True),
            ('sh3', False),
            ('sh4', False),
            ('sh4a', False),
            ('sparc', False),
            ('sparc64', True),
            ('sparc64v', True),
            ('sparcv8', False),
            ('sparcv9', False),
            ('sparcv9v', False),
            ('x86_64', True),
        ]
        for arch, multilib in arches:
            self.assertEqual(bool(dnf.rpmUtils.arch.isMultiLibArch(arch)), multilib, msg="Arch: %s" % arch)

    def test_multilib_arches(self):
        arches = {
            'amd64': ('athlon', 'x86_64', 'athlon'),
            'ia32e': ('athlon', 'x86_64', 'athlon'),
            'ppc64': ('ppc', 'ppc64', 'ppc64'),
            'ppc64iseries': ('ppc', 'ppc64', 'ppc64'),
            'ppc64p7': ('ppc', 'ppc64', 'ppc64'),
            'ppc64pseries': ('ppc', 'ppc64', 'ppc64'),
            's390x': ('s390', 's390x', 's390'),
            'sparc64': ('sparcv9', 'sparcv9', 'sparc64'),
            'sparc64v': ('sparcv9v', 'sparcv9v', 'sparc64v'),
            'x86_64': ('athlon', 'x86_64', 'athlon'),
        }
        for arch in sorted(dnf.rpmUtils.arch.arches):
            multilib = dnf.rpmUtils.arch.multilibArches.get(arch)
            self.assertEqual(multilib, arches.get(arch), msg="Arch: %s" % arch)
