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
import dnf.exceptions
import itertools
import logging

class CommonTest(support.ResultTestCase):

    """Tests common to any 'multilib_policy' and 'best'.

    The test fixture consists of a dnf.Base instance that:

    - contains a package "lotus-3-17.x86_64" (The package can be installed.)
    - contains a package "lotus-3-17.i686" (The package can be installed.)
    - contains a package "trampoline-2.1-1.noarch" that contains
      "/all/be/there", provides "splendid > 2.0" and "php(a/b)" (The package
      can be installed.)
    - contains a package "mrkite-2-0.x86_64" (The package can be installed
      together with the package "trampoline".)
    - contains a package "mrkite-k-h-1-1.x86_64" (The package can be
      installed.)
    - contains a package "pepper-20-0.src"
    - contains a package "pepper-20-2.x86_64" (The package cannot be
      installed.)
    - contains a package "librita-1-1.x86_64" (The package is already
      installed.)
    - contains a package "hole-1-2.x86_64" (The package can be installed as an
      upgrade.)

    """

    def setUp(self):
        self.base = support.MockBase('main', 'third_party', 'broken_deps')

    def test_install_arch_glob(self):
        """Test that the pkg specification can contain an architecture glob."""
        self.base.install("lotus.*6*")
        installed = self.installed_removed(self.base)[0]
        self.assertCountEqual(map(str, installed),
                              ['lotus-3-17.i686',
                               'lotus-3-17.x86_64'])

    def test_install_filename_glob(self):
        """Test that the pkg to be installed can be specified by fname glob."""
        self.base.install("*/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('trampoline-2.1-1.noarch',))

        self.base.install("/all/*/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('trampoline-2.1-1.noarch',))

    def test_install_name(self):
        """Test that the package to be installed can be specified by name."""
        self.base.install("mrkite")
        available = self.base.sack.query().available()
        expected = available.filter(name=["mrkite", "trampoline"]).run()
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = self.base.sack.query().installed() + expected
        self.assertResult(self.base, new_set)

    def test_install_name_glob(self):
        """Test that the pkg to be installed can be specified by name glob."""
        self.base.install("mrkite*")
        installed = self.installed_removed(self.base)[0]
        self.assertCountEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])

    def test_install_name_glob_exclude(self):
        """Test that glob excludes play well with glob installs."""
        subj_ex = dnf.subject.Subject('*-1')
        pkgs_ex = subj_ex.get_best_query(self.base.sack)
        self.base.sack.add_excludes(pkgs_ex)

        self.base.install('mrkite*')
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'trampoline-2.1-1.noarch'])

    def test_install_nevra(self):
        """Test that the package to be installed can be specified by NEVRA."""
        self.base.install("lotus-3-17.i686")
        lotus, = dnf.subject.Subject('lotus-3-17.i686') \
                     .get_best_query(self.base.sack)
        new_set = self.base.sack.query().installed() + [lotus]
        self.assertResult(self.base, new_set)

    def test_install_provide_slash(self):
        self.base.install("php(a/b)")
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ('trampoline-2.1-1.noarch',))

    def test_install_provide_version(self):
        """Test that the pkg to be installed can be spec. by provide ver."""
        self.base.install('splendid > 2.0')
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.base.sack.query().installed() + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_package_install_conflict(self):
        """Test that a conflicting package cannot be installed."""
        p = self.base.sack.query().available().filter(
            nevra='pepper-20-2.x86_64')[0]
        self.assertEqual(1, self.base.package_install(p))
        with self.assertRaises(dnf.exceptions.DepsolveError):
            self.base.resolve()

    def test_package_install_installed(self):
        """Test that nothing changes if an installed package matches."""
        p = self.base.sack.query().available()._nevra("librita-1-1.x86_64")[0]
        with support.mock.patch('logging.Logger.warning') as warn:
            self.base.package_install(p)
        self.base.resolve()
        self.assertEmpty(self.base._goal.list_reinstalls())

        self.base.package_reinstall(p)
        self.base.resolve()
        self.assertLength(self.base._goal.list_reinstalls(), 1)

    def test_package_install_upgrade(self):
        """Test that the pkg to be installed can be an upgrade."""
        p = self.base.sack.query().available().filter(
            nevra='hole-1-2.x86_64')[0]
        self.assertEqual(1, self.base.package_install(p))
        installed, removed = self.installed_removed(self.base)
        self.assertIn(p, installed)
        self.assertGreaterEqual(
            removed,
            set(self.base.sack.query().installed().filter(name='hole')))

    def test_pkg_install_installable(self):
        """Test that the package to be installed can be a package instance."""
        p = self.base.sack.query().available().filter(
            nevra='lotus-3-17.x86_64')[0]
        self.assertEqual(1, self.base.package_install(p))
        self.base.resolve()
        self.assertEqual(1, len(self.base._goal.list_installs()))

    def test_pkg_install_installonly(self):
        """Test that installonly packages are installed, not upgraded."""
        self.base.conf.installonlypkgs.append('hole')
        p = self.base.sack.query().available().filter(
            nevra='hole-1-2.x86_64')[0]
        self.assertEqual(1, self.base.package_install(p))
        installed, removed = self.installed_removed(self.base)
        self.assertIn(p, installed)
        self.assertFalse(
            set(removed) &
            set(self.base.sack.query().installed().filter(name='hole')))

class MultilibAllTest(support.ResultTestCase):

    """Tests for multilib_policy='all'.

    The test fixture consists of a dnf.Base instance that:

    - has conf.multilib_policy == "all"
    - has conf.best == False
    - contains a package "pepper-20-2" (The package cannot be installed.)
    - contains a package "lotus-3-16.x86_64" that contains "/usr/lib*/liblot*"
      in a "main" repository (The package can be installed.)
    - contains a package "lotus-3-16.i686" that contains "/usr/lib*/liblot*" in
      the "main" repository (The package can be installed.)
    - contains a package "librita-1-1.x86_64" (The package is already
      installed.)
    - contains a package "hole-1-2.x86_64" (The package can be installed as an
      upgrade.)
    - contains a package "pepper-20-0.src"
    - contains a package "pepper-20-0.x86_64" (The package is already
      installed.)
    - contains nothing that matches "not-available"
    - contains a package that provides "henry(the_horse)" (The package can be
      installed.)
    - contains a package "lotus-3-17.x86_64" not in a "main" repository (The
      package can be installed.)
    - contains a package "lotus-3-17.i686" not in the "main" repository (The
      package can be installed.)

    """

    def setUp(self):
        self.base = support.MockBase('main', 'third_party', 'broken_deps')
        self.base.conf.multilib_policy = "all"
        assert self.base.conf.best == False

    def test_install_conflict(self):
        """Test that the exception is raised if the package conflicts."""
        self.base.install('pepper-20-2')
        with self.assertRaises(dnf.exceptions.DepsolveError):
            self.base.resolve()

    def test_install_filename(self):
        """Test that the pkg to be installed can be specified by filename."""
        self.base.install("/usr/lib*/liblot*")
        inst, _ = self.installed_removed(self.base)
        self.assertCountEqual(
            map(str, inst), ['lotus-3-16.x86_64', 'lotus-3-16.i686'])

    def test_install_installed(self):
        """Test that nothing changes if an installed package matches."""
        stdout = dnf.pycomp.StringIO()
        with support.wiretap_logs('dnf', logging.WARNING, stdout):
            self.base.install('librita')
        self.assertEqual(self.base._goal.req_length(), 0)
        self.assertIn(
            'Package librita-1-1.x86_64 is already installed, skipping.',
            stdout.getvalue())

    def test_install_installonly(self):
        """Test that installonly packages are installed, not upgraded."""
        self.base.conf.installonlypkgs.append('hole')
        self.base.install('hole-1-2')
        installed, removed = self.installed_removed(self.base)
        self.assertGreaterEqual(
            installed,
            set(self.base.sack.query().available()._nevra('hole-1-2.x86_64')))
        self.assertEmpty(removed)

    def test_install_multilib(self):
        """Test that pkgs for all architectures are installed if available."""
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 2)
        installed = self.installed_removed(self.base)[0]
        self.assertLessEqual(
            set(installed),
            set(self.base.sack.query().available().filter(name='lotus')))

    def test_install_name_choice(self):
        """Test that the matching pkg that can be installed is installed."""
        # Don't install the SRPM.
        self.base.sack.add_excludes(
            dnf.subject.Subject('pepper.src').get_best_query(self.base.sack))

        stdout = dnf.pycomp.StringIO()
        with support.wiretap_logs('dnf', logging.WARNING, stdout):
            self.base.install('pepper')
        self.assertEqual(self.base._goal.req_length(), 0)
        self.assertIn(
            'Package pepper-20-0.x86_64 is already installed, skipping.',
            stdout.getvalue())

    def test_install_nonexistent(self):
        """Test that the exception is raised if no package matches."""
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.install('not-available')
        self.assertEqual(context.exception.pkg_spec, 'not-available')
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install_provide(self):
        """Test that the pkg to be installed can be specified by provide."""
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16').get_best_query(self.base.sack))

        self.base.install('lotus', reponame='main')
        self.assertResult(self.base, result)

        assert dnf.subject.Subject('lotus-3-17').get_best_query(self.base.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')

    def test_install_upgrade(self):
        """Test that the pkg to be installed can be an upgrade."""
        self.base.install('hole-1-2')
        installed, removed = self.installed_removed(self.base)
        self.assertGreaterEqual(
            installed,
            set(self.base.sack.query().available()._nevra('hole-1-2.x86_64')))
        self.assertGreaterEqual(
            removed,
            set(self.base.sack.query().installed().filter(name='hole')))

class MultilibBestTest(support.ResultTestCase):

    """Tests for multilib_policy='best'.

    The test fixture consists of a dnf.Base instance that:

    - has conf.multilib_policy == "best"
    - has conf.best == False
    - contains a package "pepper-20-2" (The package cannot be installed.)
    - contains a package "lotus-3-16.x86_64" that contains "/usr/lib*/liblot*"
      in a "main" repository (The package can be installed.)
    - contains a package "lotus-3-16.i686" that contains "/usr/lib*/liblot*"
      in the "main" repository (The package can be installed.)
    - contains nothing that matches "/not/exist/"
    - contains a package "librita-1-1.x86_64" (The package is already
      installed.)
    - contains a package "hole-1-2.x86_64" (The package can be installed as an
      upgrade.)
    - contains a package "lotus-3-17.x86_64" not in the "main" repository (The
      package can be installed.)
    - contains a package "pepper-20-0.src"
    - contains a package "pepper-20-0.x86_64" (The package is already
      installed.)
    - contains nothing that matches "not-available"
    - contains a package "trampoline" that provides "henry(the_horse)" (The
      package can be installed.)
    - contains a package "lotus-3-17.i686" not in the "main" repository (The
      package can be installed.)
    - contains a package "hole-1-1.x86_64" (The package is already installed
      and is not available.)

    """

    def setUp(self):
        self.base = support.MockBase('main', 'third_party', 'broken_deps')
        self.installed = self.base.sack.query().installed().run()
        self.assertEqual(self.base.conf.multilib_policy, "best")
        assert self.base.conf.best == False

    def test_install_conflict(self):
        """Test that the exception is raised if the package conflicts."""
        self.base.install('pepper-20-2')
        with self.assertRaises(dnf.exceptions.DepsolveError):
            self.base.resolve()

    def test_install_filename(self):
        """Test that the pkg to be installed can be specified by filename."""
        self.base.install("/usr/lib*/liblot*")
        inst, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(str, inst), ['lotus-3-16.x86_64'])

        self.assertRaises(dnf.exceptions.MarkingError,
                          self.base.install, "/not/exist/")

    def test_install_installed(self):
        """Test that nothing changes if an installed package matches."""
        stdout = dnf.pycomp.StringIO()
        with support.wiretap_logs('dnf', logging.WARNING, stdout):
            self.base.install('librita')
        installed, removed = self.installed_removed(self.base)
        self.assertEmpty(installed)
        self.assertEmpty(removed)
        self.assertIn(
            'Package librita-1-1.x86_64 is already installed, skipping.',
            stdout.getvalue())

    def test_install_installonly(self):
        """Test that installonly packages are installed, not upgraded."""
        self.base.conf.installonlypkgs.append('hole')
        self.base.install('hole-1-2')
        installed, removed = self.installed_removed(self.base)
        self.assertGreaterEqual(
            installed,
            set(self.base.sack.query().available()._nevra('hole-1-2.x86_64')))
        self.assertEmpty(removed)

    def test_install_multilib(self):
        """Test that a pkg for only one architecture are installed."""
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 1)

        new_package, = dnf.subject.Subject('lotus-3-17.x86_64') \
                           .get_best_query(self.base.sack)
        new_set = self.installed + [new_package]
        self.assertResult(self.base, new_set)

    def test_install_name_choice(self):
        """Test that the matching pkg that can be installed is installed."""
        # Don't install the SRPM.
        self.base.sack.add_excludes(
            dnf.subject.Subject('pepper.src').get_best_query(self.base.sack))

        stdout = dnf.pycomp.StringIO()
        with support.wiretap_logs('dnf', logging.WARNING, stdout):
            self.base.install('pepper')
        installed, removed = self.installed_removed(self.base)
        self.assertEmpty(installed | removed)
        self.assertIn(
            'Package pepper-20-0.x86_64 is already installed, skipping.',
            stdout.getvalue())

    def test_install_nonexistent(self):
        """Test that the exception is raised if no package matches."""
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.install('not-available')
        self.assertEqual(context.exception.pkg_spec, 'not-available')
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install_provide(self):
        """Test that the pkg to be installed can be specified by provide."""
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_install_reponame(self):
        """Test whether packages are filtered by the reponame."""
        result = itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus-3-16.x86_64')
            .get_best_query(self.base.sack))

        self.base.install('lotus', reponame='main')
        self.assertResult(self.base, result)

        assert dnf.subject.Subject('lotus-3-17.x86_64') \
               .get_best_query(self.base.sack), \
               ('the base must contain packages a package in another repo '
                'which matches the pattern but is preferred, otherwise the '
                'test makes no sense')

    def test_install_unavailable(self):
        """Test that nothing changes if an unavailable package matches."""
        stdout = dnf.pycomp.StringIO()
        with support.wiretap_logs('dnf', logging.WARNING, stdout):
            cnt = self.base.install('hole')
        self.assertEqual(cnt, 1)
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)
        self.assertIn(
            'Package hole-1-1.x86_64 is already installed, skipping.',
            stdout.getvalue())

    def test_install_upgrade(self):
        """Test that the pkg to be installed can be an upgrade."""
        self.base.install('hole-1-2')
        installed, removed = self.installed_removed(self.base)
        self.assertGreaterEqual(
            installed,
            set(self.base.sack.query().available()._nevra('hole-1-2.x86_64')))
        self.assertGreaterEqual(
            removed,
            set(self.base.sack.query().installed().filter(name='hole')))

class BestTrueTest(support.ResultTestCase):

    """Tests for best=True.

    The test fixture consists of a dnf.Base instance that:

    - has conf.best == True
    - contains a package "pepper-20-2" (The package cannot be installed.)

    """

    def setUp(self):
        self.base = support.MockBase('broken_deps')
        self.base.conf.best = True

    def test_install_name_choice(self):
        """Test that the latest version of the matching pkg is installed."""
        with support.mock.patch('logging.Logger.warning') as warn:
            self.base.install('pepper')
        with self.assertRaises(dnf.exceptions.DepsolveError):
            self.base.resolve()
