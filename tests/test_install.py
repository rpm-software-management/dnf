# Copyright (C) 2012  Red Hat, Inc.
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

import base
import dnf.queries
from dnf.queries import available_by_name
import hawkey

class InstallMultilibAll(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.MockYumBase("main")
        self.yumbase.conf.multilib_policy = "all"

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install(pattern="not-available")
        installed_pkgs = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(len(tsinfo), 0)
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        self.yumbase.install(pattern="mrkite")
        expected = available_by_name(self.yumbase.sack, ["mrkite", "trampoline"])
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = dnf.queries.installed(self.yumbase.sack) + expected
        self.assertResult(self.yumbase, new_set)

class MultilibAllMainRepo(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.MockYumBase("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.yumbase.conf.multilib_policy = "all"

    def test_reinstall_existing(self):
        """ Do not try installing an already present package. """
        self.yumbase.install(pattern="pepper")
        self.assertResult(self.yumbase, self.installed)

    def test_install(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        tsinfo = self.yumbase.install(pattern="lotus")
        arches = [txmbr.po.arch for txmbr in tsinfo]
        self.assertItemsEqual(arches, ['x86_64', 'i686'])
        new_set = self.installed + available_by_name(self.yumbase.sack, "lotus")
        self.assertResult(self.yumbase, new_set)

class MultilibBestMainRepo(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.MockYumBase("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(self.yumbase.conf.multilib_policy, "best")

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install(pattern="not-available")
        # no query is run and so yumbase can not now it will later yield an
        # empty set:
        self.assertEqual(len(tsinfo), 1)
        self.assertResult(self.yumbase, self.installed)

    def test_install(self):
        """ Installing a package existing in multiple architectures only
            installs the one for our arch.
        """
        tsinfo = self.yumbase.install(pattern="lotus")
        self.assertEqual(len(tsinfo), 1)

        new_package = hawkey.Query(self.yumbase.sack).\
            filter(name="lotus", arch="x86_64", repo="main")[0]
        new_set = self.installed + [new_package]
        self.assertResult(self.yumbase, new_set)
