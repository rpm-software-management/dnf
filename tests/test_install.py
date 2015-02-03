# Copyright (C) 2012-2015  Red Hat, Inc.
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

class MultilibCommonTest(support.ResultTestCase):

    """Tests common to any multilib_policy."""

    def setUp(self):
        self.base = support.MockBase('main', 'third_party')
        self.base.conf.multilib_policy = "all"

    def test_install_nonexistent(self):
        """Test that the exception is raised if no package matches."""
        cnt = self.base.install("not-available")
        self.assertEqual(cnt, 0)
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install_name(self):
        """Test that the package to be installed can be specified by name."""
        self.base.install("mrkite")
        available = self.base.sack.query().available()
        expected = available.filter(name=["mrkite", "trampoline"]).run()
        # ensure sanity of the test (otherwise it would pass no matter what):
        self.assertEqual(len(expected), 2)
        new_set = self.base.sack.query().installed() + expected
        self.assertResult(self.base, new_set)

    def test_pkg_install_installable(self):
        """Test that the package to be installed can be a package instance."""
        self.base = support.MockBase('main', 'multilib')
        p = self.base.sack.query().available().filter(
            nevra="pepper-20-0.i686")[0]
        self.assertEqual(1, self.base.package_install(p))
        self.base.resolve()
        self.assertEqual(1, len(self.base._goal.list_installs()))

    def test_install_provide(self):
        """Test that the pkg to be installed can be specified by provide."""
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)

    def test_install_filename(self):
        """Test that the pkg to be installed can be specified by filename."""
        self.base.install("/usr/lib64/liblot*")
        inst, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(str, inst), ['lotus-3-16.x86_64'])

    def test_install_nevra(self):
        """Test that the package to be installed can be specified by NEVRA."""
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
    def test_install_srpm(self):
        """Test that the exception is raised if a source arch is specified."""
        self.base.install("pepper-20-0.src")
        re = 'Will not install a source rpm'
        self.assertRaisesRegexp(dnf.exceptions.Error, re,
                                self.base.resolve)

class MultilibAllTest(support.ResultTestCase):

    """Tests for multilib_policy='all'."""

    def setUp(self):
        self.base = support.MockBase("main")
        self.installed = self.base.sack.query().installed().run()
        self.base.conf.multilib_policy = "all"

    def test_install_multilib(self):
        """Test that pkgs for all architectures are installed if available."""
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 2)
        q = self.base.sack.query().available().filter(name="lotus")
        new_set = self.installed + q.run()
        self.assertResult(self.base, new_set)

    def test_package_install_installed(self):
        """Test that nothing changes if an installed package matches."""
        p = self.base.sack.query().available().nevra("librita-1-1.x86_64")[0]
        self.base.package_install(p)
        self.base.resolve()
        self.assertEmpty(self.base._goal.list_reinstalls())

        self.base.package_reinstall(p)
        self.base.resolve()
        self.assertLength(self.base._goal.list_reinstalls(), 1)


class MultilibBestTest(support.ResultTestCase):

    """Tests for multilib_policy='best'."""

    def setUp(self):
        self.base = support.MockBase('main', 'third_party')
        self.installed = self.base.sack.query().installed().run()
        self.assertEqual(self.base.conf.multilib_policy, "best")

    def test_install_nonexistent(self):
        """Test that the exception is raised if no package matches."""
        with self.assertRaises(dnf.exceptions.MarkingError) as context:
            self.base.install('not-available')
        self.assertEqual(context.exception.pkg_spec, 'not-available')
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install_unavailable(self):
        """Test that nothing changes if an unavailable package matches."""
        cnt = self.base.install("hole")
        self.assertEqual(cnt, 1)
        installed_pkgs = self.base.sack.query().installed().run()
        self.assertResult(self.base, installed_pkgs)

    def test_install_multilib(self):
        """Test that a pkg for only one architecture are installed."""
        cnt = self.base.install("lotus")
        self.assertEqual(cnt, 1)

        new_package, = dnf.subject.Subject('lotus-3-17.x86_64').get_best_query(self.base.sack)
        new_set = self.installed + [new_package]
        self.assertResult(self.base, new_set)

    def test_install_provide(self):
        """Test that the pkg to be installed can be specified by provide."""
        self.base.install("henry(the_horse)")
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_install_provide_version(self):
        """Test that the pkg to be installed can be spec. by provide ver."""
        self.base.install('splendid > 2.0')
        self.assertGreater(self.base._goal.req_length(), 0)
        trampoline = self.base.sack.query().available().filter(
            name="trampoline")
        new_set = self.installed + trampoline.run()
        self.assertResult(self.base, new_set)

    def test_install_filename(self):
        """Test that the pkg to be installed can be specified by filename."""
        self.base.install("/usr/lib*/liblot*")
        inst, _ = self.installed_removed(self.base)
        self.assertCountEqual(map(str, inst), ['lotus-3-16.x86_64'])

        self.assertRaises(dnf.exceptions.MarkingError,
                          self.base.install, "/not/exist/")

    def test_install_filename_glob(self):
        """Test that the pkg to be installed can be specified by fname glob."""
        self.base.install("/*/be/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

        self.base.reset(goal=True)
        self.base.install("*/there")
        (installed, _) = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed), ('trampoline-2.1-1.noarch',))

    def test_install_name_glob(self):
        """Test that the pkg to be installed can be specified by name glob."""
        self.base.install("mrkite*")
        q = self.base.sack.query().available().filter(name="mrkite*")
        new_set = self.installed + q.run()
        installed, removed = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ['mrkite-2-0.x86_64',
                               'mrkite-k-h-1-1.x86_64',
                               'trampoline-2.1-1.noarch'])

    def test_install_arch_glob(self):
        """Test that the pkg specification can contain an architecture glob."""
        self.base.install("lotus.*6*")
        installed, removed = self.installed_removed(self.base)
        self.assertCountEqual(map(str, installed),
                              ['lotus-3-17.i686',
                               'lotus-3-17.x86_64'])

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
