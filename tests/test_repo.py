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
from dnf.i18n import ucd
from tests import support
from tests.support import mock

import dnf.callback
import dnf.drpm
import dnf.repo
import dnf.util
import dnf.exceptions
import iniparse.compat
import io
import librepo
import os
import re
import tempfile
import unittest

REPOS = "%s/tests/repos" % support.dnf_toplevel()
BASEURL = "file://%s/rpm" % REPOS
TOUR_CHKSUM = """\
ce77c1e5694b037b6687cf0ab812ca60431ec0b65116abbb7b82684f0b092d62"""


class RepoFunctionsTest(unittest.TestCase):
    def test_cachedir_re(self):
        pairs = [
            ('fedora-fe3d2f0c91e9b65c', 'fedora'),
            ('foo-bar-eb0d6f10ccbdafba', 'foo-bar'),
            ('a%^&$b-fe3d2f0c91e9b65c', None),
            ('fedora-91e9b65c', None),
            ('fedora-xe3d2f0c91e9b65c', None),
            ('-fe3d2f0c91e9b65c', None),
            ('fedorafe3d2f0c91e9b65c', None),
        ]
        for filename, expected in pairs:
            match = re.match(dnf.repo._CACHEDIR_RE, filename)
            repoid = match.group('repoid') if match else None
            self.assertEqual(repoid, expected)

    def test_repo_id_invalid(self):
        """Test repo_id_invalid."""
        index = dnf.repo.repo_id_invalid('R_e-p.o:i3d')
        self.assertIsNone(index)
        index = dnf.repo.repo_id_invalid('R_e-p.o/:i3d')
        self.assertEqual(index, 7)

    def test_user_pass_str(self):
        user = 'cap'
        passwd = 'bag'
        self.assertEqual(dnf.repo._user_pass_str(user, passwd), 'cap:bag')
        passwd = 'm:ltr'
        self.assertEqual(dnf.repo._user_pass_str(user, passwd), 'cap:m%3Altr')
        user = None
        self.assertEqual(dnf.repo._user_pass_str(user, passwd), None)


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
        cls.TMP_CACHEDIR = tempfile.mkdtemp(prefix='dnf-repotest-')
        cls.conf = support.FakeConf(cachedir=cls.TMP_CACHEDIR)

    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(cls.TMP_CACHEDIR)

    def build_repo(self, id_, name=None):
        repo = dnf.repo.Repo(id_, self.conf)
        repo.baseurl = [BASEURL]
        repo.name = id_ if name is None else name
        return repo

    def tearDown(self):
        repo_path = os.path.join(self.TMP_CACHEDIR, "r")
        dnf.util.rm_rf(repo_path)


class DownloadErrorsTest(support.TestCase):
    def test_bandwidth_used(self):
        errors = dnf.repo._DownloadErrors()
        pkg1 = support.MockPackage('penny-1-1.noarch')
        pkg1.downloadsize = 10
        pkg2 = support.MockPackage('lane-2-1.noarch')
        pkg2.downloadsize = 1
        pl1 = dnf.repo.RPMPayload(pkg1, None)
        pl2 = dnf.repo.RPMPayload(pkg2, None)
        errors._skipped.add(pl2.pkg)

        self.assertEqual(errors._bandwidth_used(pl1), 10)
        self.assertEqual(errors._bandwidth_used(pl2), 0)


class HandleTest(support.TestCase):
    def test_useragent(self):
        h = dnf.repo._Handle(False, 0)
        self.assertTrue(h.useragent.startswith("dnf/"))
        self.assertEqual(h.maxmirrortries, 0)

    def test_substs(self):
        subst_dct = {'version': '69'}
        h = dnf.repo._Handle._new_local(subst_dct, False, 1, '/')
        self.assertCountEqual(h.varsub, [('version', '69'),])


class MetadataTest(support.TestCase):
    def setUp(self):
        result = mock.Mock(spec=['yum_repo', 'yum_repomd'])
        result.yum_repo = {'primary': support.NONEXISTENT_FILE}
        handle = mock.Mock(spec=['mirrors'])
        handle.mirrors = []
        self.metadata = dnf.repo.Metadata(result, handle)

    def test_file_timestamp(self):
        self.assertRaises(dnf.exceptions.MetadataError,
                          self.metadata._file_timestamp, 'primary')


class RepoTest(RepoTestMixin, support.TestCase):
    """Test the logic of dnf.repo.Repo.

    There is one cache directory for the entire TestCase, but each individual
    test cleans up the cache after itself.

    We only test sync from a local dir. Testing all sorts of remote downloads
    from mirrorlists etc. is up to librepo.

    """

    def setUp(self):
        self.repo = self.build_repo('r', 'r for riot')

    def tearDown(self):
        dnf.util.rm_rf(self.repo._cachedir)

    def test_cachedir(self):
        self.repo.baseurl = ["http://download.repo.org/r"]
        self.assertEqual(self.repo._cachedir,
                         os.path.join(self.TMP_CACHEDIR, 'r-0824b1db602c8695'))

    def test_dump(self):
        dump = self.repo.dump()
        f = io.StringIO(ucd(dump))
        parser = iniparse.compat.ConfigParser()
        parser.readfp(f)
        self.assertIn('r', parser.sections())
        opts = parser.options('r')
        self.assertIn('bandwidth', opts)
        self.assertIn('gpgkey', opts)

    def test_hawkey_repo(self):
        """Test settings get passed down to the hawkey repo instance."""
        r = self.repo
        self.assertEqual(r.cost, 1000)
        self.assertEqual(r._hawkey_repo.cost, 1000)
        r.cost = 300
        self.assertEqual(r.cost, 300)
        self.assertEqual(r._hawkey_repo.cost, 300)

        self.assertEqual(r.priority, 99)
        self.assertEqual(r._hawkey_repo.priority, 99)
        r.priority = 9
        self.assertEqual(r.priority, 9)
        self.assertEqual(r._hawkey_repo.priority, 9)

    def test_expire_cache(self):
        self.repo.load()
        # the second time we only hit the cache:
        del self.repo
        self.repo = dnf.repo.Repo("r", self.conf)
        self.repo.baseurl = [BASEURL]
        self.repo._md_expire_cache()
        self.assertTrue(self.repo.load())

    def test_gpgcheck(self):
        self.repo.gpgcheck = True
        self.assertTrue(self.repo.load())

    @mock.patch('dnf.repo.Repo._local', False)
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
        self.repo = dnf.repo.Repo("r", self.conf)
        self.repo.baseurl = [BASEURL]
        self.assertFalse(self.repo.load())
        self.assertIsNotNone(self.repo.metadata)

    def test_load(self):
        repo = self.repo
        self.assertIsNone(repo.metadata)
        self.assertTrue(repo.load())
        self.assertIsNotNone(repo.metadata)
        repomd = os.path.join(self.repo._cachedir, "repodata/repomd.xml")
        self.assertTrue(os.path.isfile(repomd))
        self.assertTrue(repo.metadata.fresh)

    def test_load_badconf(self):
        self.repo.baseurl = []
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)

    def test_md_lazy(self):
        self.repo.load()
        self.setUp()
        repo = self.repo
        repo._md_expire_cache()
        repo._md_lazy = True
        self.assertFalse(repo.load())

    def test_metadata_expire_in(self):
        repo = self.repo
        self.assertEqual(repo._metadata_expire_in(), (False, 0))
        repo.load()
        (has, time) = repo._metadata_expire_in()
        self.assertTrue(has)
        self.assertGreater(time, 0)

        repo.metadata_expire = 'never'
        self.assertEqual(repo._metadata_expire_in(), (True, None))

    def test_md_only_cached(self):
        self.repo._md_only_cached = True
        self.assertRaises(dnf.exceptions.RepoError, self.repo.load)
        self.repo._sync_strategy = 3
        self.repo.load()
        del self.repo
        self.setUp() # get a new repo
        self.repo._md_only_cached = True
        self.assertFalse(self.repo.load())
        self.assertFalse(self.repo.metadata.fresh)

        # try again with a quickly expiring cache
        del self.repo
        self.setUp()
        self.repo.metadata_expire = 0
        self.repo._md_only_cached = True
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

    def test_repo_cmp(self):
        r1 = self.build_repo('abc', '1. repo')
        r2 = self.build_repo('zzz', '2. repo')
        self.assertLess(r1, r2)

    @mock.patch('librepo.Handle.setopt')
    def test_repo_gpgcheck(self, setopt):
        """Test repo_gpgcheck option works."""
        self.repo.repo_gpgcheck = False
        self.repo._handle_new_remote('/bag')
        setopt.assert_any_call(librepo.LRO_GPGCHECK, False)

        self.repo.repo_gpgcheck = True
        self.repo._handle_new_remote('/bag')
        setopt.assert_any_call(librepo.LRO_GPGCHECK, True)

    def test_reset_metadata_expired(self):
        repo = self.repo
        repo.load()
        repo.metadata_expire = 0
        repo._reset_metadata_expired()
        self.assertTrue(repo._expired)

        # the expired state only resets outside of _reset_metadata_expired():
        repo.metadata_expired = 'never'
        self.assertTrue(repo._expired)
        repo._expired = False
        repo.metadata_expire = 'never'
        repo._reset_metadata_expired()
        self.assertFalse(repo._expired)

    def test_valid(self):
        self.assertIsNone(self.repo._valid())

        repo = dnf.repo.Repo('r', self.conf)
        self.assertRegexpMatches(repo._valid(), 'no mirror or baseurl')

    def test_handle_new_pkg_download(self):
        """Ensure mirrors are never resolved for package download."""
        repo = self.repo
        repo.mirrorlist = 'http://anything'
        repo.metadata = mock.Mock()
        repo.metadata._mirrors = ['resolved']
        h = repo._handle_new_pkg_download()
        self.assertIsNone(h.mirrorlist)

    def test_throttle(self):
        self.repo.throttle = '50%'
        self.repo.bandwidth = '10M'
        self.assertEqual(self.repo.throttle, 0.5)
        self.assertEqual(self.repo.bandwidth, 10 << 20)
        opts = {}
        with mock.patch('librepo.Handle.setopt', opts.__setitem__):
            self.repo._get_handle()
        self.assertEqual(opts[librepo.LRO_MAXSPEED], 5 << 20)


class LocalRepoTest(support.TestCase):
    def setUp(self):
        # directly loads the repo as created by createrepo
        self.conf = support.FakeConf(cachedir=REPOS)
        self.repo = dnf.repo.Repo("rpm", self.conf)
        self.repo.name = "r for riot"

    def test_mirrors(self):
        self.repo._md_only_cached = True
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.assertFalse(self.repo.load())  # got a cache
        self.assertLength(self.repo.metadata._mirrors, 4)
        self.assertEqual(self.repo.metadata._mirrors[0], 'http://many/x86_64')

    @mock.patch.object(dnf.repo.Metadata, '_reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving(self, new_remote_m, reset_age_m):
        self.repo._md_expire_cache()
        self.repo.metalink = 'http://meh'
        remote_handle_m = new_remote_m()
        remote_handle_m.metalink = \
            {'hashes': [('md5', '308d71cc873ef60efa5ef2ba5a97b34a'),
                        ('sha1', 'd5f18c856e765cd88a50dbf1bfaea51de3b5e516'),
                        ('sha256', 'ead48d5c448a481bd66a4413d7be28bd44ce5de1ee59ecb723c78dcf4e441696'),
                        ('sha512', '9a3131485c0c0a3f65bb5f25155e89d2d6b09e74ffdaa1c3339d3874885d160d8b4667a4a83dbd7d2702a5d41a4e1bc5622c4783b77dcf1f69626c68975202ce')]}
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.assertTrue(self.repo.load())
        self.assertTrue(remote_handle_m.fetchmirrors)
        self.assertFalse(self.repo._expired)
        reset_age_m.assert_called_with()

    @mock.patch.object(dnf.repo.Metadata, '_reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_lame_hashes(self, new_remote_m, _):
        self.repo._md_expire_cache()
        self.repo.metalink = 'http://meh'
        new_remote_m().metalink = \
            {'hashes': [('md5', 'fcf04ce803b3e15cbef6ea6f12ed4533'),
                        ('sha1', '3731498f6b7b96316590205a4d7a2add484471e0')]}
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.repo._try_cache()
            self.assertFalse(self.repo._try_revive())

    @mock.patch.object(dnf.repo.Metadata, '_reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_mismatched_hashes(self, new_remote_m, _):
        self.repo._md_expire_cache()
        self.repo.metalink = 'http://meh'
        new_remote_m().metalink = \
            {'hashes': [('sha256', '4394be16de62563321f6ea9604513a8a2f6b9ab67898bbed218feeca8e6a7180'),
                        ('sha512', 'obviousfail')]}
        # can not do the entire load() here, it would run on after try_revive()
        # failed.
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.repo._try_cache()
            self.assertFalse(self.repo._try_revive())

    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_404(self, new_remote_m):
        url = 'http://meh'
        self.repo._md_expire_cache()
        self.repo.metalink = url
        lr_exc = librepo.LibrepoException(
            librepo.LRE_CURL, 'Error HTTP/FTP status code: 404', 'Curl error.')
        exc = dnf.repo._DetailedLibrepoError(lr_exc, url)
        new_remote_m()._perform = mock.Mock(side_effect=exc)
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.assertRaises(dnf.exceptions.RepoError, self.repo.load)

    @mock.patch.object(dnf.repo.Metadata, '_reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_baseurl(self, new_remote_m, reset_age_m):
        self.repo._md_expire_cache()
        self.repo.baseurl = 'http://meh'
        remote_handle_m = new_remote_m()
        remote_handle_m._perform().rpmmd_repo = \
            { 'repomd': REPOS + '/rpm/repodata/repomd.xml'}
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.assertTrue(self.repo.load())
        self.assertTrue(remote_handle_m.fetchmirrors)
        self.assertFalse(self.repo._expired)
        reset_age_m.assert_called_with()

    @mock.patch.object(dnf.repo.Metadata, '_reset_age')
    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_baseurl_mismatched(self, new_remote_m, _):
        self.repo._md_expire_cache()
        self.repo.baseurl = 'http://meh'
        remote_handle_m = new_remote_m()
        remote_handle_m._perform().rpmmd_repo = \
            { 'repomd': '/dev/null'}
        # can not do the entire load() here, it would run on after try_revive()
        # failed.
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.repo._try_cache()
            self.assertFalse(self.repo._try_revive())

    @mock.patch('dnf.repo.Repo._handle_new_remote')
    def test_reviving_baseurl_404(self, new_remote_m):
        url = 'http://meh'
        self.repo._md_expire_cache()
        self.repo.baseurl = url
        lr_exc = librepo.LibrepoException(
            librepo.LRE_CURL, 'Error HTTP/FTP status code: 404', 'Curl error.')
        exc = dnf.repo._DetailedLibrepoError(lr_exc, url)
        new_remote_m()._perform = mock.Mock(side_effect=exc)
        with mock.patch('dnf.repo.Repo._cachedir', REPOS + "/rpm"):
            self.assertRaises(dnf.exceptions.RepoError, self.repo.load)


class DownloadPayloadsTest(RepoTestMixin, support.TestCase):

    def test_drpm_error(self):
        def wait(self):
            self.err['step'] = ['right']

        drpm = dnf.drpm.DeltaInfo(None, None)
        with mock.patch('dnf.drpm.DeltaInfo.wait', wait):
            errs = dnf.repo._download_payloads([], drpm)
        self.assertEqual(errs._recoverable, {'step' : ['right']})
        self.assertEmpty(errs._irrecoverable)

    def test_empty_transaction(self):
        drpm = dnf.drpm.DeltaInfo(None, None)
        errs = dnf.repo._download_payloads([], drpm)
        self.assertEmpty(errs._recoverable)
        self.assertEmpty(errs._irrecoverable)

    def test_fatal_error(self):
        def raiser(_, failfast):
            raise librepo.LibrepoException(10, 'hit', 'before')

        drpm = dnf.drpm.DeltaInfo(None, None)
        with mock.patch('librepo.download_packages', side_effect=raiser):
            errs = dnf.repo._download_payloads([], drpm)
        self.assertEqual(errs._irrecoverable, {'' : ['hit']})
        self.assertEmpty(errs._recoverable)

    # twist Repo to think it's remote:
    @mock.patch('dnf.repo.Repo._local', False)
    def test_remote_download(self):
        progress = dnf.callback.NullDownloadProgress()
        repo = self.build_repo('r', 'r for riot')
        pkg = support.MockPackage("tour-4-4.noarch", repo=repo)
        pkg.downloadsize = 2317
        pkg._chksum = ('sha256', TOUR_CHKSUM)

        pload = dnf.repo.RPMPayload(pkg, progress)
        drpm = dnf.drpm.DeltaInfo(None, None)
        errs = dnf.repo._download_payloads([pload], drpm)
        self.assertEmpty(errs._recoverable)
        self.assertEmpty(errs._irrecoverable)
        path = os.path.join(repo._cachedir, 'packages/tour-4-4.noarch.rpm')
        self.assertFile(path)


class MDPayloadTest(unittest.TestCase):
    def test_null_progress(self):
        """MDPayload always has some progress attribute."""
        pload = dnf.repo.MDPayload(None)
        pload.start('roll up')
        self.assertIsNotNone(pload.progress)


class SavingTest(unittest.TestCase):
    def test_update_saving(self):
        progress = dnf.callback.NullDownloadProgress()

        pkg = support.MockPackage("tour-4-4.noarch")
        pkg.downloadsize = 5
        pload1 = dnf.repo.RPMPayload(pkg, progress)
        pkg = support.MockPackage("magical-4-4.noarch")
        pkg.downloadsize = 8
        pload2 = dnf.drpm.DeltaPayload(None, mock.Mock(downloadsize=5), pkg,
                                       progress)
        saving = (5, 10)
        saving = dnf.repo._update_saving(saving, (pload1, pload2), {})
        self.assertEqual(saving, (15, 23))

    def test_update_saving_with_err(self):
        progress = dnf.callback.NullDownloadProgress()

        pkg = support.MockPackage("magical-4-4.noarch")
        pkg.downloadsize = 8
        pload = dnf.drpm.DeltaPayload(None, mock.Mock(downloadsize=5), pkg,
                                      progress)
        saving = (5, 10)
        saving = dnf.repo._update_saving(saving, (pload,), {pkg:'failed'})
        self.assertEqual(saving, (10, 10))
