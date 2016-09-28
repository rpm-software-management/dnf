# Copyright (C) 2012-2016 Red Hat, Inc.
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

import dnf.rpm
import tests.support


class ArchTest(tests.support.TestCase):

    def test_basearch(self):
        fn = dnf.rpm.basearch
        self.assertEqual(fn('armv6hl'), 'armhfp')
        self.assertEqual(fn('armv7hl'), 'armhfp')
        self.assertEqual(fn('armv8l'), 'armhfp')
        self.assertEqual(fn('i686'), 'i386')
        self.assertEqual(fn('noarch'), 'noarch')
        self.assertEqual(fn('ppc64iseries'), 'ppc64')
        self.assertEqual(fn('sparc64v'), 'sparc')
        self.assertEqual(fn('x86_64'), 'x86_64')
