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
from tests import support
import dnf
import itertools

class Reinstall(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase('main')
        self.base.conf.multilib_policy = 'all'
        self.sack = self.base.sack

    def test_reinstall(self):
        cnt = self.base.reinstall('pepper')
        self.assertEqual(cnt, 1)
        new_set = support.installed_but(self.sack, "pepper")
        available_query = self.sack.query().available()
        new_set += list(available_query.nevra("pepper-20-0.x86_64"))
        self.assertResult(self.base, new_set)

    def test_reinstall_new_reponame_available(self):
        """Test whether it installs packages only from the repository."""
        reinstalled_count = self.base.reinstall('librita', new_reponame='main')

        self.assertEqual(reinstalled_count, 1)
        self.assertResult(self.base, itertools.chain(
            self.sack.query().installed().filter(name__neq='librita'),
            dnf.subject.Subject('librita.i686').get_best_query(self.sack).installed(),
            dnf.subject.Subject('librita').get_best_query(self.sack).available()))

    def test_reinstall_new_reponame_notavailable(self):
        """Test whether it installs packages only from the repository."""
        self.assertRaises(
            dnf.exceptions.PackagesNotAvailableError,
            self.base.reinstall, 'librita', new_reponame='non-main')

    def test_reinstall_new_reponame_neq_available(self):
        """Test whether it installs only packages not from the repository."""
        reinstalled_count = self.base.reinstall('librita', new_reponame_neq='non-main')

        self.assertEqual(reinstalled_count, 1)
        self.assertResult(self.base, itertools.chain(
            self.sack.query().installed().filter(name__neq='librita'),
            dnf.subject.Subject('librita.i686').get_best_query(self.sack).installed(),
            dnf.subject.Subject('librita').get_best_query(self.sack).available()))

    def test_reinstall_new_reponame_neq_notavailable(self):
        """Test whether it installs only packages not from the repository."""
        self.assertRaises(
            dnf.exceptions.PackagesNotAvailableError,
            self.base.reinstall, 'librita', new_reponame_neq='main')

    def test_reinstall_notfound(self):
        """Test whether it fails if the package does not exist."""
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as ctx:
            self.base.reinstall('non-existent')

        self.assertEqual(ctx.exception.pkg_spec, 'non-existent')
        self.assertResult(self.base, self.sack.query().installed())

    def test_reinstall_notinstalled(self):
        """Test whether it fails if the package is not installed."""
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as ctx:
            self.base.reinstall('lotus')

        self.assertEqual(ctx.exception.pkg_spec, 'lotus')
        self.assertResult(self.base, self.sack.query().installed())

    def test_reinstall_notavailable(self):
        """Test whether it fails if the package is not available."""
        with self.assertRaises(dnf.exceptions.PackagesNotAvailableError) as ctx:
            self.base.reinstall('hole')

        self.assertEqual(ctx.exception.pkg_spec, 'hole')
        self.assertItemsEqual(
            ctx.exception.packages,
            dnf.subject.Subject('hole').get_best_query(self.sack).installed())
        self.assertResult(self.base, self.sack.query().installed())

    def test_reinstall_notavailable_available(self):
        """Test whether it does not fail if some packages are available and some not."""
        reinstalled_count = self.base.reinstall('librita')

        self.assertEqual(reinstalled_count, 1)
        self.assertResult(self.base, itertools.chain(
            self.sack.query().installed().filter(name__neq='librita'),
            dnf.subject.Subject('librita.i686').get_best_query(self.sack).installed(),
            dnf.subject.Subject('librita').get_best_query(self.sack).available()))

    def test_reinstall_old_reponame_installed(self):
        """Test whether it reinstalls packages only from the repository."""
        for pkg in self.sack.query().installed().filter(name='librita'):
            self.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.base.yumdb.get_package(pkg).from_repo = 'main'

        reinstalled_count = self.base.reinstall('librita', old_reponame='main')

        self.assertEqual(reinstalled_count, 1)
        self.assertResult(self.base, itertools.chain(
            self.sack.query().installed().filter(name__neq='librita'),
            dnf.subject.Subject('librita.i686').get_best_query(self.sack).installed(),
            dnf.subject.Subject('librita').get_best_query(self.sack).available()))

    def test_reinstall_old_reponame_notinstalled(self):
        """Test whether it reinstalls packages only from the repository."""
        self.assertRaises(
            dnf.exceptions.PackagesNotInstalledError,
            self.base.reinstall, 'librita', old_reponame='non-main')

    def test_reinstall_remove_notavailable(self):
        """Test whether it removes the package which is not available."""
        self.base.reinstall('hole', remove_na=True)

        self.assertResult(
            self.base,
            self.sack.query().installed().filter(name__neq='hole'))
