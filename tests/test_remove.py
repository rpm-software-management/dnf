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
from tests import support
import dnf.cli.commands
import itertools

class Remove(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase()
        self.allow_erasing = True

    def test_not_installed(self):
        """ Removing a not-installed package is a void operation. """
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as context:
            self.base.remove('mrkite')
        self.assertEqual(context.exception.pkg_spec, 'mrkite')
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_remove(self):
        """ Simple remove. """
        ret = self.base.remove("pepper")
        self.assertResult(self.base,
                          support.installed_but(self.base.sack, "pepper"))

    def test_remove_dependent(self):
        """ Remove a lib that some other package depends on. """
        ret = self.base.remove("librita")
        # we should end up with nothing in this case:
        new_set = support.installed_but(self.base.sack, "librita", "pepper")
        self.assertResult(self.base, new_set)

    def test_remove_nevra(self):
        ret = self.base.remove("pepper-20-0.x86_64")
        pepper = self.base.sack.query().installed().filter(name="pepper")
        (installed, removed) = self.installed_removed(self.base)
        self.assertLength(installed, 0)
        self.assertCountEqual(removed, pepper.run())

    def test_remove_glob(self):
        """ Test that weird input combinations with globs work. """
        ret = self.base.remove("*.i686")
        self.assertEqual(ret, 1)

    def test_remove_provides(self):
        """Remove uses provides too."""
        self.assertEqual(1, self.base.remove('parking'))
