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
import dnf.exceptions
import itertools

class InstallMultilib(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase('main', 'third_party')
        self.base.conf.multilib_policy = "all"

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        cnt = self.base.install("not-available")
        self.assertEqual(cnt, 0)
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        self.base.install("mrkite")
        available = self.base.sack.query().available()
        expected = available.filter(name=["mrkite", "trampoline"]).run()
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = self.base.sack.query().installed() + expected
        self.assertResult(self.base, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)

    def test_install_by_filename(self):
        self.base.install("/usr/lib64/liblot*")
        inst, _ = self.installed_removed(self.base)
        self.assertItemsEqual(map(str, inst), ['lotus-3-16.x86_64'])

    def test_install_nevra(self):
        self.base.install("lotus-3-16.i686")
        lotus, = dnf.subject.Subject('lotus-3-16.i686').get_best_query(self.base.sack)
        new_set = self.base.sack.query().installed() + [lotus]
        self.assertResult(self.base, new_set)

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16.i686').get_best_query(self.base.sack),
            dnf.subject.Subject('lotus-3-16.x86_64').get_best_query(self.base.sack))

        self.base.install('lotus', reponame='main')
        self.assertResult(self.base, result)

        assert dnf.subject.Subject('lotus-3-17.i686').get_best_query(self.base.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')

    @support.mock.patch('dnf.transaction._', dnf.pycomp.NullTranslations().ugettext)
    def test_install_src_fails(self):
        self.base.install("pepper-20-0.src")
        re = 'Will not install a source rpm'
        self.assertRaisesRegexp(dnf.exceptions.Error, re,
                                self.base.resolve)

class MultilibAllMainRepo(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.installed = self.base.sack.query().installed().run()
        self.base.conf.multilib_policy = "all"

    def test_install(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 2)
        q = self.base.sack.query().available().filter(name="lotus")
        new_set = self.installed + q.run()
        self.assertResult(self.base, new_set)

class MultilibBest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase('main', 'third_party')
        self.installed = self.base.sack.query().installed().run()
        self.assertEqual(self.base.conf.multilib_policy, "best")

    def test_non_existent(self):
        """ Installing a nonexistent package is a void operation. """
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.install('not-available')
        self.assertEqual(context.exception.pkg_spec, 'not-available')
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_not_available(self):
        """ Installing a unavailable package is a void operation. """
        cnt = self.base.install("hole")
        self.assertEqual(cnt, 1)
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install(self):
        """ Installing a package existing in multiple architectures only
            installs the one for our arch.
        """
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 1)

        new_package, = dnf.subject.Subject('lotus-3-17.x86_64').get_best_query(self.base.sack)
        new_set = self.installed + [new_package]
        self.assertResult(self.base, new_set)

    def test_install_by_provides(self):
        """ Test the package to be installed can be specified by provide. """
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_install_by_cmp_provides(self):
        """Test the package to be installed can be specified by as provide with
        "<=>".
        """
        self.base.install('splendid > 2.0')
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_install_by_filename_glob(self):
        self.base.install("/*/be/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertItemsEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

        self.base.reset(goal=True)
        self.base.install("*/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertItemsEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

    def test_install_glob(self):
        self.base.install("mrkite*")
        q = self.base.sack.query().available().filter(name="mrkite*")
        new_set = self.installed + q.run()
        installed, removed = self.installed_removed(self.base)
        self.assertItemsEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])

    def test_install_glob_arch(self):
        self.base.install("lotus.*6*")
        installed, removed = self.installed_removed(self.base)
        self.assertItemsEqual(map(str, installed),
                              ['lotus-3-17.i686',
                               'lotus-3-17.x86_64'])

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16.x86_64').get_best_query(self.base.sack))

        self.base.install('lotus', reponame='main')
        self.assertResult(self.base, result)

        assert dnf.subject.Subject('lotus-3-17.i686').get_best_query(self.base.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')
