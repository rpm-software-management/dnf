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
from dnf.queries import available_by_name
from tests import support
import dnf.queries
import hawkey

class InstallMultilibAll(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.yumbase.conf.multilib_policy = "all"

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install("not-available")
        installed_pkgs = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(len(tsinfo), 0)
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        self.yumbase.install("mrkite")
        expected = available_by_name(self.yumbase.sack, ["mrkite", "trampoline"])
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = dnf.queries.installed(self.yumbase.sack) + expected
        self.assertResult(self.yumbase, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.yumbase.install("henry(the_horse)")
        self.assertGreater(len(self.yumbase.tsInfo), 0)

    def test_install_by_filename(self):
        self.yumbase.install("/usr/lib64/liblot*")
        inst, _ = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, inst), ['lotus-3-16.x86_64'])

    def test_install_nevra(self):
        self.yumbase.install("lotus-3-16.i686")
        available = available_by_name(self.yumbase.sack, "lotus", get_query=True)
        lotus = available.filter(arch="i686")[0]
        new_set = dnf.queries.installed(self.yumbase.sack) + [lotus]
        self.assertResult(self.yumbase, new_set)

    def test_install_local(self):
        txmbrs = self.yumbase.install_local(support.TOUR_50_PKG_PATH)
        self.assertLength(txmbrs, 1)

    def test_install_src_fails(self):
        self.yumbase.install("pepper-20-0.src")
        (code, string) = self.yumbase.buildTransaction()
        self.assertEqual(code, 0)
        self.assertRegexpMatches(string[0], "will not install a source rpm")

class MultilibAllMainRepo(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.yumbase.conf.multilib_policy = "all"

    def test_install(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        tsinfo = self.yumbase.install("lotus")
        arches = [txmbr.po.arch for txmbr in tsinfo]
        self.assertItemsEqual(arches, ['x86_64', 'i686'])
        new_set = self.installed + available_by_name(self.yumbase.sack, "lotus")
        self.assertResult(self.yumbase, new_set)

class MultilibBestMainRepo(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(self.yumbase.conf.multilib_policy, "best")

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install("not-available")
        self.assertEqual(len(tsinfo), 0)
        self.assertResult(self.yumbase, self.installed)

    def test_install(self):
        """ Installing a package existing in multiple architectures only
            installs the one for our arch.
        """
        tsinfo = self.yumbase.install("lotus")
        self.assertEqual(len(tsinfo), 1)

        new_package = hawkey.Query(self.yumbase.sack).\
            filter(name="lotus", arch="x86_64", reponame="main")[0]
        new_set = self.installed + [new_package]
        self.assertResult(self.yumbase, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.yumbase.install("henry(the_horse)")
        self.assertGreater(len(self.yumbase.tsInfo), 0)
        trampoline = available_by_name(self.yumbase.sack, "trampoline")
        new_set = self.installed + trampoline
        self.assertResult(self.yumbase, new_set)

    def test_install_glob(self):
        self.yumbase.install("mrkite*")
        new_set = self.installed + available_by_name(self.yumbase.sack, "mrkite*")
        installed, removed = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])
