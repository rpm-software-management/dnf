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

import base
import dnf.repo
import dnf.util
import dnf.yum.Errors
import librepo
import mock
import os
import tempfile
import unittest

BASEURL = "file://%s/tests/repos/rpm" % base.dnf_toplevel()

class RepoTest(base.TestCase):
    """Test the logic of dnf.repo.Repo.

    There is one cache directory for the entire TestCase, but each individual
    test cleans up the cache after itself.

    We only test sync from a local dir. Testing all sorts of remote downloads
    from mirrorlists etc. is up to librepo.

    """
    TMP_CACHEDIR = None

    def setUp(self):
        self.repo = dnf.repo.Repo("r")
        self.repo.basecachedir = self.TMP_CACHEDIR
        self.repo.baseurl = [BASEURL]
        self.repo.name = "r for riot"

    @classmethod
    def setUpClass(cls):
         cls.TMP_CACHEDIR = tempfile.mkdtemp(prefix="dnf-repotest-")

    def tearDown(self):
        repo_path = os.path.join(self.TMP_CACHEDIR, "r")
        dnf.util.rm_rf(repo_path)

    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(cls.TMP_CACHEDIR)

    def test_cachedir(self):
        self.assertEqual(self.repo.cachedir,
                         os.path.join(self.TMP_CACHEDIR, self.repo.id))

    def test_expire_cache(self):
        self.repo.load()
        # the second time we only hit the cache:
        del self.repo
        self.repo = dnf.repo.Repo("r")
        self.repo.basecachedir = self.TMP_CACHEDIR
        self.repo.baseurl = [BASEURL]
        self.repo.expire_cache()
        self.assertTrue(self.repo.load())

    def test_get_package(self):
        pkg = base.MockPackage("tour-4-4.noarch", repo=self.repo)
        path = self.repo.get_package(pkg)
        self.assertFile(path)

    def test_gpgcheck(self):
        self.repo.gpgcheck = True
        self.assertTrue(self.repo.load())

    def test_keep_old_pgks(self):
        dnf.util.ensure_dir(self.repo.pkgdir)
        survivor = os.path.join(self.repo.pkgdir, "survivor")
        dnf.util.touch(survivor)
        # syncing a repo shouldn't clear the pkgdir
        self.repo.load()
        self.assertFile(survivor)

    def test_load_twice(self):
        self.assertTrue(self.repo.load())
        # the second time we only hit the cache:
        del self.repo
        self.repo = dnf.repo.Repo("r")
        self.repo.basecachedir = self.TMP_CACHEDIR
        self.assertFalse(self.repo.load())
        self.assertIsNotNone(self.repo.res)

    def test_load(self):
        self.assertIsNone(self.repo.res)
        self.assertTrue(self.repo.load())
        self.assertIsNotNone(self.repo.res)
        repomd = os.path.join(self.TMP_CACHEDIR, "r/repodata/repomd.xml")
        self.assertTrue(os.path.isfile(repomd))

    def test_load_badconf(self):
        self.repo.baseurl = []
        self.assertRaises(dnf.yum.Errors.RepoError, self.repo.load)

    def test_metadata_expire_in(self):
        self.assertEqual(self.repo.metadata_expire_in(), (False, 0))
        self.repo.load()
        (has, time) = self.repo.metadata_expire_in()
        self.assertTrue(has)
        self.assertGreater(time, 0)

    def test_progress_cb(self):
        m = mock.Mock()
        self.repo.set_progress_bar(m)
        self.repo.load()
        m.begin.assert_called_with("r for riot")
        m.librepo_cb.assert_any_call(mock.ANY, mock.ANY, mock.ANY)
        m.end.assert_called_with()

    @mock.patch('librepo.Handle.setopt')
    def test_repo_gpgcheck(self, setopt):
        """Test repo_gpgcheck option works."""
        self.repo.repo_gpgcheck = False
        handle = self.repo._handle_new_remote("/bag")
        setopt.assert_any_call(librepo.LRO_GPGCHECK, False)

        self.repo.repo_gpgcheck = True
        handle = self.repo._handle_new_remote("/bag")
        setopt.assert_any_call(librepo.LRO_GPGCHECK, True)

    def test_urlgrabber_opts(self):
        opts = self.repo.urlgrabber_opts()
        self.assertIn('keepalive', opts)
        self.assertIn('password', opts)
