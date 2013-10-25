# Copyright (C) 2012-2013  Red Hat, Inc.
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
import dnf.exceptions
import dnf.queries
import hawkey

class InstallMultilibAll(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main")
        self.yumbase.conf.multilib_policy = "all"

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        cnt = self.yumbase.install("not-available")
        self.assertEqual(cnt, 0)
        installed_pkgs = self.yumbase.sack.query().installed().run()
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        self.yumbase.install("mrkite")
        available = self.yumbase.sack.query().available()
        expected = available.filter(name=["mrkite", "trampoline"]).run()
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = self.yumbase.sack.query().installed() + expected
        self.assertResult(self.yumbase, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.yumbase.install("henry(the_horse)")
        self.assertGreater(self.yumbase._goal.req_length(), 0)

    def test_install_by_filename(self):
        self.yumbase.install("/usr/lib64/liblot*")
        inst, _ = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, inst), ['lotus-3-16.x86_64'])

    def test_install_nevra(self):
        self.yumbase.install("lotus-3-16.i686")
        available = self.yumbase.sack.query().available()
        lotus = available.filter(name="lotus", arch="i686")[0]
        new_set = self.yumbase.sack.query().installed() + [lotus]
        self.assertResult(self.yumbase, new_set)

    def test_install_local(self):
        cnt = self.yumbase.install_local(support.TOUR_50_PKG_PATH)
        self.assertEqual(cnt, 1)

    def test_install_src_fails(self):
        self.yumbase.install("pepper-20-0.src")
        re = 'will not install a source rpm'
        self.assertRaisesRegexp(dnf.exceptions.Error, re,
                                self.yumbase.build_transaction)

class MultilibAllMainRepo(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main")
        self.installed = self.yumbase.sack.query().installed().run()
        self.yumbase.conf.multilib_policy = "all"

    def test_install(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        cnt = self.yumbase.install("lotus")
        self.assertEqual(cnt, 2)
        q = self.yumbase.sack.query().available().filter(name="lotus")
        new_set = self.installed + q.run()
        self.assertResult(self.yumbase, new_set)

class MultilibBestMainRepo(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main")
        self.installed = self.yumbase.sack.query().installed().run()
        self.assertEqual(self.yumbase.conf.multilib_policy, "best")

    def test_non_existent(self):
        """ Installing a nonexistent package is a void operation. """
        self.assertRaises(dnf.exceptions.PackageNotFoundError,
                          self.yumbase.install, "not-available")
        installed_pkgs = self.yumbase.sack.query().installed().run()
        self.assertResult(self.yumbase, installed_pkgs)

    def test_not_available(self):
        """ Installing a unavailable package is a void operation. """
        cnt = self.yumbase.install("hole")
        self.assertEqual(cnt, 1)
        installed_pkgs = self.yumbase.sack.query().installed().run()
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Installing a package existing in multiple architectures only
            installs the one for our arch.
        """
        cnt = self.yumbase.install("lotus")
        self.assertEqual(cnt, 1)

        new_package = hawkey.Query(self.yumbase.sack).\
            filter(name="lotus", arch="x86_64", reponame="main")[0]
        new_set = self.installed + [new_package]
        self.assertResult(self.yumbase, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.yumbase.install("henry(the_horse)")
        self.assertGreater(self.yumbase._goal.req_length(), 0)
        trampoline = self.yumbase.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.yumbase, new_set)

    def test_install_glob(self):
        self.yumbase.install("mrkite*")
        q = self.yumbase.sack.query().available().filter(name="mrkite*")
        new_set = self.installed + q.run()
        installed, removed = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])
