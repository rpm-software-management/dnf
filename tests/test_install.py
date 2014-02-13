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
from tests import support
import dnf.exceptions
import itertools

class InstallMultilibAll(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase('main', 'updates')
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
        lotus, = dnf.subject.Subject('lotus-3-16.i686').get_best_query(self.yumbase.sack)
        new_set = self.yumbase.sack.query().installed() + [lotus]
        self.assertResult(self.yumbase, new_set)

    def test_install_local(self):
        cnt = self.yumbase.install_local(support.TOUR_50_PKG_PATH)
        self.assertEqual(cnt, 1)

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.yumbase.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16.i686').get_best_query(self.yumbase.sack),
            dnf.subject.Subject('lotus-3-16.x86_64').get_best_query(self.yumbase.sack))

        self.yumbase.install('lotus', reponame='main')
        self.assertResult(self.yumbase, result)

        assert dnf.subject.Subject('lotus-3-17.i686').get_best_query(self.yumbase.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')

    def test_install_src_fails(self):
        self.yumbase.install("pepper-20-0.src")
        re = 'will not install a source rpm'
        self.assertRaisesRegexp(dnf.exceptions.Error, re,
                                self.yumbase.resolve)

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

class MultilibBest(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase('main', 'updates')
        self.installed = self.yumbase.sack.query().installed().run()
        self.assertEqual(self.yumbase.conf.multilib_policy, "best")

    def test_non_existent(self):
        """ Installing a nonexistent package is a void operation. """
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.yumbase.install('not-available')
        self.assertEqual(context.exception.pkg_spec, 'not-available')
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

        new_package, = dnf.subject.Subject('lotus-3-17.x86_64').get_best_query(self.yumbase.sack)
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

    def test_install_by_cmp_provides(self):
        """Test the package to be installed can be specified by as provide with
        "<=>".
        """
        self.yumbase.install('splendid > 2.0')
        self.assertGreater(self.yumbase._goal.req_length(), 0)
        trampoline = self.yumbase.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.yumbase, new_set)

    def test_install_by_filename_glob(self):
        self.yumbase.install("/*/be/there")
        (installed, _) = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

        self.yumbase.reset(goal=True)
        self.yumbase.install("*/there")
        (installed, _) = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

    def test_install_glob(self):
        self.yumbase.install("mrkite*")
        q = self.yumbase.sack.query().available().filter(name="mrkite*")
        new_set = self.installed + q.run()
        installed, removed = self.installed_removed(self.yumbase)
        self.assertItemsEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.yumbase.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16.x86_64').get_best_query(self.yumbase.sack))

        self.yumbase.install('lotus', reponame='main')
        self.assertResult(self.yumbase, result)

        assert dnf.subject.Subject('lotus-3-17.i686').get_best_query(self.yumbase.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')
