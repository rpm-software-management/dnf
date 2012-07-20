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
import hawkey

class Remove(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base()

    def test_not_installed(self):
        """ Removing a not-installed package is a void operation. """
        ret = self.yumbase.remove(pattern="mrkite")
        self.assertEqual(ret, [])
        installed_pkgs = dnf.queries.installed_by_name(self.yumbase.sack, None)
        self.assertResult(self.yumbase, installed_pkgs)

    def test_remove(self):
        """ Simple remove. """
        ret = self.yumbase.remove(pattern="pepper")
        pepper = dnf.queries.installed_by_name(self.yumbase.sack, "pepper")
        self.assertEqual([txmbr.po for txmbr in ret], pepper)
        self.assertResult(self.yumbase,
                          base.installed_but(self.yumbase.sack, "pepper"))

    def test_remove_depended(self):
        """ Remove a lib that some other package depends on. """
        ret = self.yumbase.remove(pattern="librita")
        # we should end up with nothing in this case:
        new_set = base.installed_but(self.yumbase.sack, "librita", "pepper")
        self.assertResult(self.yumbase, new_set)
