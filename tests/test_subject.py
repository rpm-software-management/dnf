# Copyright (C) 2015  Red Hat, Inc.
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
from tests import support
import dnf.exceptions

class SubjectTest(support.TestCase):
    def setUp(self):
        self.base = support.MockBase('main', 'third_party')
        pkg = self.base.sack.query().filter(name='lotus', arch='x86_64')[0]
        self.base.sack.add_excludes([pkg])

    def test_best_selectors_no_glob(self):
        subj = dnf.subject.Subject('pepper')
        sltrs = subj._get_best_selectors(self.base.sack)
        self.assertEqual(len(sltrs), 1)

    def test_best_selectors_glob(self):
        subj = dnf.subject.Subject('l*')
        sltrs = subj._get_best_selectors(self.base.sack)
        q = self.base.sack.query().filter(name__glob='l*')
        self.assertEqual(len(sltrs), len(set(map(lambda p: p.name, q))))

    def test_best_selectors_arch(self):
        subj = dnf.subject.Subject('l*.x86_64')
        sltrs = subj._get_best_selectors(self.base.sack)
        q = self.base.sack.query().filter(name__glob='l*', arch__eq='x86_64')
        self.assertEqual(len(sltrs), len(set(map(lambda p: p.name, q))))
        for sltr in sltrs:
            for pkg in sltr.matches():
                self.assertEqual(pkg.arch, 'x86_64')

    def test_best_selectors_ver(self):
        subj = dnf.subject.Subject('*-1-1')
        sltrs = subj._get_best_selectors(self.base.sack)
        for sltr in sltrs:
            for pkg in sltr.matches():
                self.assertEqual(pkg.evr, '1-1')
