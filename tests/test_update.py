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
from dnf.queries import (available_by_name, available_by_nevra, installed,
                         updates_by_name)
from tests import support

class Update(support.ResultTestCase):
    def test_update(self):
        """ Simple update. """
        yumbase = support.MockYumBase("updates")
        ret = yumbase.update("pepper")
        new_versions = updates_by_name(yumbase.sack, "pepper")
        expected = installed(yumbase.sack, get_query=True).filter(name__neq="pepper") + new_versions
        self.assertResult(yumbase, expected)

    def test_update_not_installed(self):
        """ Updating an uninstalled package is a void operation. """
        yumbase = support.MockYumBase("main")
        # no "mrkite" installed:
        yumbase.update("mrkite")
        self.assertResult(yumbase, installed(yumbase.sack))

    def test_update_all(self):
        """ Update all you can. """
        yumbase = support.MockYumBase("main", "updates")
        sack = yumbase.sack
        yumbase.update_all()
        expected = support.installed_but(sack, "pepper", "hole") + \
            list(available_by_nevra(sack, "pepper-20-1.x86_64")) + \
            list(available_by_nevra(sack, "hole-2-1.x86_64"))
        self.assertResult(yumbase, expected)

    def test_update_local(self):
        yumbase = support.MockYumBase()
        sack = yumbase.sack
        cnt = yumbase.update_local(support.TOUR_51_PKG_PATH)
        self.assertEqual(cnt, 1)
        new_pkg = available_by_name(sack, "tour")[0]
        new_set = support.installed_but(yumbase.sack, "tour") + [new_pkg]
        self.assertResult(yumbase, new_set)

    def test_update_arches(self):
        yumbase = support.MockYumBase("main", "updates")
        yumbase.update("hole")
        installed, removed = self.installed_removed(yumbase)
        self.assertItemsEqual(map(str, installed), ['hole-2-1.x86_64'])
        self.assertItemsEqual(map(str, removed), ['hole-1-1.x86_64'])

class SkipBroken(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("broken_deps")
        self.sack = self.yumbase.sack

    def test_update_all(self):
        """ update() without parameters update everything it can that has its
            deps in trim. Broken packages are silently skipped.
        """
        self.yumbase.update_all()
        new_set = support.installed_but(self.sack, "pepper").run()
        new_set.extend(available_by_nevra(self.sack, "pepper-20-1.x86_64"))
        self.assertResult(self.yumbase, new_set)
