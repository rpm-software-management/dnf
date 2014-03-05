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
from tests import mock
from tests import support

import dnf.callback
import dnf.drpm
import dnf.repo
import dnf.util
import dnf.exceptions
import iniparse.compat
import io
import librepo
import os
import tempfile
import unittest
from dnf.pycomp import unicode

REPOS = "%s/tests/repos" % support.dnf_toplevel()
BASEURL = "file://%s/rpm" % REPOS
TOUR_CHKSUM = """\
ce77c1e5694b037b6687cf0ab812ca60431ec0b65116abbb7b82684f0b092d62"""

class RepoIdInvalidTest(unittest.TestCase):

    def test(self):
        """Test repo_id_invalid with a good repo ID."""
        index = dnf.repo.repo_id_invalid('R_e-p.o:i3d')
        self.assertIsNone(index)

    def test_invalid(self):
        """Test repo_id_invalid with a repo ID with an invalid character."""
        index = dnf.repo.repo_id_invalid('R_e-p.o/:i3d')
        self.assertEqual(index, 7)

class RepoTestMixin(object):
    """Test the logic of dnf.repo.Repo.

    There is one cache directory for the entire TestCase, but each individual
    test cleans up the cache after itself.

    We only test sync from a local dir. Testing all sorts of remote downloads
    from mirrorlists etc. is up to librepo.

    """
    TMP_CACHEDIR = None

    @classmethod
    def setUpClass(cls):
         cls.TMP_CACHEDIR = tempfile.mkdtemp(prefix="dnf-repotest-")

    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(cls.TMP_CACHEDIR)

    def build_repo(self, id_, name=None):
        repo = dnf.repo.Repo(id_, self.TMP_CACHEDIR)
        repo.baseurl = [BASEURL]
        repo.name = id_ if name is None else name
        return repo

    def tearDown(self):
        repo_path = os.path.join(self.TMP_CACHEDIR, "r")
        dnf.util.rm_rf(repo_path)

class HandleTest(support.TestCase):
    def test_useragent(self):
        h = dnf.repo._Handle(False, 0)
        self.assertTrue(h.useragent.startswith("dnf/"))
        self.assertEqual(h.maxmirrortries, 0)

    def test_substs(self):
        subst_dct = {'version': '69'}
        h = dnf.repo._Handle.new_local(subst_dct, False, 1, '/')
        self.assertItemsEqual(h.varsub, [('version', '69'),])

class MetadataTest(support.TestCase):
    def setUp(self):
        result = mock.Mock(spec=['yum_repo', 'yum_repomd'])
        result.yum_repo = {'primary': support.NONEXISTENT_FILE}
        handle = mock.Mock(spec=['mirrors'])
        handle.mirrors = []
        self.md = dnf.repo.Metadata(result, handle)

    def test_file_timestamp(self):
        self.assertRaises(dnf.exceptions.MetadataError,
                          self.md.file_timestamp, 'primary')

class RepoTest(RepoTestMixin, support.TestCase):
    """Test the logic of dnf.repo.Repo.

    There is one cache directory for the entire TestCase, but each individual
    test cleans up the cache after itself.

    We only test sync from a local dir. Testing all sorts of remote downloads
    from mirrorlists etc. is up to librepo.

    """

    def setUp(self):
        self.repo = self.build_repo('r', 'r for riot')

    def test_cachedir(self):
        self.assertEqual(self.repo.cachedir,
                         os.path.join(self.TMP_CACHEDIR, self.repo.id))

    def test_dump(self):
        dump = self.repo.dump()
        f = io.StringIO(unicode(dump))
        parser = iniparse.compat.ConfigParser()
        parser.readfp(f)
        self.assertIn('r', parser.sections())
        opts = parser.options('r')
        self.assertIn('bandwidth', opts)
        self.assertIn('gpgkey', opts)
        self.assertEqual(parser.get('r', 'timeout'), '30.0')

    def test_cost(self):
        """Test the cost is passed down to the hawkey repo instance."""
        repo2 = dnf.repo.Repo("r2", self.TMP_CACHEDIR)
        repo2.baseurl = [BASEURL]
        repo2.name = "r2 repo"
        self.repo.cost = 500
        repo2.cost = 700

        base = support.MockBase()
        base.init_sack()
        base.repos.add(self.repo)
        base.repos.add(repo2)
        base._add_repo_to_sack('r')
        base._add_repo_to_sack('r2')
        self.assertEqual(500, self.repo.hawkey_repo.cost)
        self.assertEqual(700, repo2.hawkey_repo.cost)

    def test_expire_cache(self):
        self.repo.load()
        # the second time we only hit the cache:
        del self.repo
        self.repo = dnf.repo.Repo("r", self.TMP_CACHEDIR)
        self.repo.baseurl = [BASEURL]
        self.repo.md_expire_cache()
        self.assertTrue(self.repo.load())

    def test_gpgcheck(self):
        self.repo.gpgcheck = True
        self.assertTrue(self.repo.load())

    @mock.patch('dnf.repo.Repo.local', False)
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
        self.repo = dnf.repo.Repo("r", self.TMP_CACHEDIR)
        self.assertFalse(self.repo.load())
        self.assertIsNotNone(self.repo.metadata)

    def test_load(self):
        repo = self.repo
        self.assertIsNone(repo.metadata)
        self.assertTrue(repo.load())
        self.assertIsNotNone(repo.metadata)
        repomd = os.path.join(self.TMP_CACHEDIR, "r/repodata/repomd.xml")
        self.assertTrue(os.path.isfile(repomd))
        self.assertTrue(repo.metadata.fresh)

    def test_load_badconf(self):
        self.repo.baseurl = []
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)

    def test_metadata_expire_in(self):
        repo = self.repo
        self.assertEqual(repo.metadata_expire_in(), (False, 0))
        repo.load()
        (has, time) = repo.metadata_expire_in()
        self.assertTrue(has)
        self.assertGreater(time, 0)

        repo.metadata_expire = 'never'
        self.assertEqual(repo.metadata_expire_in(), (True, None))

    def test_md_only_cached(self):
        self.repo.md_only_cached = True
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)
        self.repo.md_try_cache()
        self.repo.load()
        del self.repo
        self.setUp() # get a new repo
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load())
        self.assertFalse(self.repo.metadata.fresh)

        # try again with a quickly expiring cache
        del self.repo
        self.setUp()
        self.repo.metadata_expire = 0
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load())

    def test_pkgdir(self):
        self.assertRegexpMatches(self.repo.pkgdir, '/.*tests/repos/rpm')
        self.repo.mirrorlist = 'http://anything'
        self.assertTrue(self.repo.pkgdir.startswith(self.TMP_CACHEDIR))

    def test_progress_cb(self):
        m = mock.Mock()
        self.repo.set_progress_bar(m)
        self.repo.load()
        self.assertTrue(m.start.called)
        self.assertTrue(m.progress.called)
        self.assertTrue(m.end.called)

    @mock.patch('librepo.Handle.setopt')
    def test_repo_gpgcheck(self, setopt):
        """Test repo_gpgcheck option works."""
        self.repo.repo_gpgcheck = False
        handle = self.repo._handle_new_remote("/bag")
        setopt.assert_any_call(librepo.LRO_GPGCHECK, False)

        self.repo.repo_gpgcheck = True
        handle = self.repo._handle_new_remote("/bag")
        setopt.assert_any_call(librepo.LRO_GPGCHECK, True)

    def test_reset_metadata_expired(self):
        repo = self.repo
        repo.load()
        repo.metadata_expire = 0
        repo._reset_metadata_expired()
        self.assertTrue(repo.metadata.expired)
        repo.metadata_expire = 'never'
        repo._reset_metadata_expired()
        self.assertFalse(repo.metadata.expired)

    def test_valid(self):
        self.assertIsNone(self.repo.valid())

        repo = dnf.repo.Repo('r', None)
        self.assertRegexpMatches(repo.valid(), 'no mirror or baseurl')

    def test_handle_new_pkg_download(self):
        """Ensure mirrors are never resolved for package download."""
        repo = self.repo
        repo.mirrorlist = 'http://anything'
        repo.metadata = mock.Mock()
        repo.metadata.mirrors = ['resolved']
        h = repo._handle_new_pkg_download()
        self.assertIsNone(h.mirrorlist)

    def test_throttle(self):
        self.repo.throttle = '50%'
        self.repo.bandwidth = '10M'
        self.assertEquals(self.repo.throttle, 0.5)
        self.assertEquals(self.repo.bandwidth, 10 << 20)
        opts = {}
        with mock.patch('librepo.Handle.setopt', opts.__setitem__):
            self.repo.get_handle()
        self.assertEquals(opts[librepo.LRO_MAXSPEED], 5 << 20)

class LocalRepoTest(support.TestCase):
    def setUp(self):
        # directly loads the repo as created by createrepo
        self.repo = dnf.repo.Repo("rpm", REPOS)
        self.repo.name = "r for riot"

    def test_mirrors(self):
        self.repo.md_only_cached = True
        self.assertFalse(self.repo.load()) # got a cache
        self.assertLength(self.repo.metadata.mirrors, 4)
        self.assertEqual(self.repo.metadata.mirrors[0], 'http://many/x86_64')

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
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
        self.assertFalse(self.repo.metadata.expired)
        reset_age_m.assert_called()

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_lame_hashes(self, new_remote_m, reset_age_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        new_remote_m().metalink = \
            {'hashes': [('md5', 'fcf04ce803b3e15cbef6ea6f12ed4533'),
                        ('sha1', '3731498f6b7b96316590205a4d7a2add484471e0')]}
        self.repo._try_cache()
        self.assertFalse(self.repo._try_revive())

    @mock.patch.object(dnf.repo.Metadata, 'reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
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

    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_404(self, new_remote_m):
        self.repo.md_expire_cache()
        self.repo.metalink = 'http://meh'
        exc = librepo.LibrepoException(10, 'Error HTTP/FTP status code: 404', 404)
        new_remote_m().perform = mock.Mock(side_effect=exc)
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)

class DownloadPayloadsTest(RepoTestMixin, support.TestCase):

    def test_drpm_error(self):
        drpm = dnf.drpm.DeltaInfo(None, None)
        drpm.err = {'step' : ['right']}
        self.assertEqual(dnf.repo.download_payloads([], drpm),
                         {'step' : ['right']})

    def test_empty_transaction(self):
        drpm = dnf.drpm.DeltaInfo(None, None)
        self.assertEqual(dnf.repo.download_payloads([], drpm), {})

    def test_fatal_error(self):
        def raiser(targets, failfast):
            raise librepo.LibrepoException(10, 'hit', 'before')

        drpm = dnf.drpm.DeltaInfo(None, None)
        with mock.patch('librepo.download_packages', side_effect=raiser):
            errors = dnf.repo.download_payloads([], drpm)
        self.assertEqual(errors, {'' : ['hit']})

    # twist Repo to think it's remote:
    @mock.patch('dnf.repo.Repo.local', False)
    def test_remote_download(self):
        progress = dnf.callback.NullDownloadProgress()
        repo = self.build_repo('r', 'r for riot')
        pkg = support.MockPackage("tour-4-4.noarch", repo=repo)
        pkg.downloadsize = 2317
        pkg.chksum = ('sha256', TOUR_CHKSUM)

        pload = dnf.repo.RPMPayload(pkg, progress)
        drpm = dnf.drpm.DeltaInfo(None, None)
        errors = dnf.repo.download_payloads([pload], drpm)
        self.assertLength(errors, 0)
        path = os.path.join(self.TMP_CACHEDIR, 'r/packages/tour-4-4.noarch.rpm')
        self.assertFile(path)

class MDPayloadTest(unittest.TestCase):

    def test_null_progress(self):
        """MDPayload always has some progress attribute."""
        pload = dnf.repo.MDPayload(None)
        pload.start('roll up')
        self.assertIsNotNone(pload.progress)
