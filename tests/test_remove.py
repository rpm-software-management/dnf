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
import dnf.cli.commands
import hawkey

class Remove(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase()
        erase_cmd = dnf.cli.commands.EraseCommand(self.yumbase.mock_cli())
        erase_cmd.configure()

    def test_not_installed(self):
        """ Removing a not-installed package is a void operation. """
        self.assertRaises(dnf.exceptions.PackagesNotInstalledError,
                          self.yumbase.remove, "mrkite")
        installed_pkgs = self.yumbase.sack.query().installed().run()
        self.assertResult(self.yumbase, installed_pkgs)

    def test_remove(self):
        """ Simple remove. """
        ret = self.yumbase.remove("pepper")
        self.assertResult(self.yumbase,
                          support.installed_but(self.yumbase.sack, "pepper"))

    def test_remove_depended(self):
        """ Remove a lib that some other package depends on. """
        ret = self.yumbase.remove("librita")
        # we should end up with nothing in this case:
        new_set = support.installed_but(self.yumbase.sack, "librita", "pepper")
        self.assertResult(self.yumbase, new_set)

    def test_remove_nevra(self):
        ret = self.yumbase.remove("pepper-20-0.x86_64")
        pepper = self.yumbase.sack.query().installed().filter(name="pepper")
        (installed, removed) = self.installed_removed(self.yumbase)
        self.assertLength(installed, 0)
        self.assertItemsEqual(removed, pepper.run())

    def test_remove_glob(self):
        """ Test that weird input combinations with globs work. """
        ret = self.yumbase.remove("*.i686")
        self.assertEqual(ret, 1)
