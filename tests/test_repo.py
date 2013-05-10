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
from tests import mock
from tests import support
import dnf.repo
import dnf.util
import dnf.exceptions
import librepo
import os
import tempfile
import unittest
import ConfigParser
import StringIO

REPOS = "%s/tests/repos" % support.dnf_toplevel()
BASEURL = "file://%s/rpm" % REPOS

class HandleTest(support.TestCase):
    def test_useragent(self):
        h = dnf.repo._Handle(False, 0)
        self.assertTrue(h.useragent.startswith("dnf/"))
        self.assertEqual(h.maxmirrortries, 0)

class RepoTest(support.TestCase):
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

    def test_dump(self):
        dump = self.repo.dump()
        f = StringIO.StringIO(dump)
        parser = ConfigParser.ConfigParser()
        parser.readfp(f)
        self.assertIn('r', parser.sections())
        opts = parser.options('r')
        self.assertIn('bandwidth', opts)
        self.assertIn('gpgkey', opts)
        self.assertEqual(parser.get('r', 'timeout'), '30.0')

    def test_expire_cache(self):
        self.repo.load()
        # the second time we only hit the cache:
        del self.repo
        self.repo = dnf.repo.Repo("r")
        self.repo.basecachedir = self.TMP_CACHEDIR
        self.repo.baseurl = [BASEURL]
        self.repo.md_expire_cache()
        self.assertTrue(self.repo.load())

    def test_get_package(self):
        pkg = support.MockPackage("tour-4-4.noarch", repo=self.repo)
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
        self.assertIsNotNone(self.repo.metadata)

    def test_load(self):
        self.assertIsNone(self.repo.metadata)
        self.assertTrue(self.repo.load())
        self.assertIsNotNone(self.repo.metadata)
        repomd = os.path.join(self.TMP_CACHEDIR, "r/repodata/repomd.xml")
        self.assertTrue(os.path.isfile(repomd))

    def test_load_badconf(self):
        self.repo.baseurl = []
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)

    def test_metadata_expire_in(self):
        self.assertEqual(self.repo.metadata_expire_in(), (False, 0))
        self.repo.load()
        (has, time) = self.repo.metadata_expire_in()
        self.assertTrue(has)
        self.assertGreater(time, 0)

    def test_md_only_cached(self):
        self.repo.md_only_cached = True
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)
        self.repo.md_try_cache()
        self.repo.load()
        del self.repo
        self.setUp() # get a new repo
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load())

        # try again with a quickly expiring cache
        del self.repo
        self.setUp()
        self.repo.metadata_expire = 0
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load())

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

class LocalRepoTest(support.TestCase):
    def setUp(self):
        # directly loads the repo as created by createrepo
        self.repo = dnf.repo.Repo("rpm")
        self.repo.basecachedir = REPOS
        self.repo.name = "r for riot"

    def test_mirrors(self):
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load()) # got a cache
        self.assertLength(self.repo.metadata.mirrors, 4)
        self.assertEqual(self.repo.metadata.mirrors[0], 'http://many/x86_64')

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo._Handle.new_remote')
    def test_reviving(self, new_remote_m, reset_age_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        remote_handle_m = new_remote_m()
        remote_handle_m.metalink = \
            {'hashes': [('md5', 'fcf04ce803b3e15cbef6ea6f12ed4533'),
                        ('sha1', '3731498f6b7b96316590205a4d7a2add484471e0'),
                        ('sha256', '4394be16de62563321f6ea9604513a8a2f6b9ab67898bbed218feeca8e6a7180'),
                        ('sha512', 'e583eeb91874954b24a376176a087462403e518563f9cb3bdc4f7eae792e8d15ac488bc6d3fb632bbf0ac6cf58bf769e94e9773df6605616a28cf2c00adf8e14')]}
        self.assertTrue(self.repo.load())
        self.assertTrue(remote_handle_m.fetchmirrors)
        self.assertEqual(self.repo.sync_strategy, dnf.repo.SYNC_TRY_CACHE)
        reset_age_m.assert_called()

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo._Handle.new_remote')
    def test_reviving_lame_hashes(self, new_remote_m, reset_age_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        new_remote_m().metalink = \
            {'hashes': [('md5', 'fcf04ce803b3e15cbef6ea6f12ed4533'),
                        ('sha1', '3731498f6b7b96316590205a4d7a2add484471e0')]}
        self.repo._try_cache()
        self.assertFalse(self.repo._try_revive())

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo._Handle.new_remote')
    def test_reviving_mismatched_hashes(self, new_remote_m, reset_age_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        new_remote_m().metalink = \
            {'hashes': [('sha256', '4394be16de62563321f6ea9604513a8a2f6b9ab67898bbed218feeca8e6a7180'),
                        ('sha512', 'obviousfail')]}
        # can not do the entire load() here, it would run on after try_revive()
        # failed.
        self.repo._try_cache()
        self.assertFalse(self.repo._try_revive())

    @mock.patch('dnf.repo._Handle.new_remote')
    def test_reviving_404(self, new_remote_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        exc = librepo.LibrepoException(10, 'Error HTTP/FTP status code: 404', 404)
        new_remote_m().perform = mock.Mock(side_effect=exc)
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)
