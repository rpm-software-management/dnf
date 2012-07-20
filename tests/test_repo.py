# Copyright (C) 2012  Red Hat, Inc.
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

import unittest
import mock

import dnf.yum.yumRepo

class TestedYumRepo(dnf.yum.yumRepo.YumRepository):
    def __init__(self, repoid):
        super(TestedYumRepo, self).__init__(repoid)
        self.basecachedir = "/notmp"

    def _dirSetupMkdir_p(self, dpath):
        # create no directories
        return

class RepoTest(unittest.TestCase):
    def test_metadata_current(self):
        repo = TestedYumRepo("myid")
        self.assertFalse(repo.metadataCurrent())
        repo._metadataCurrent = True		# override the cached value
        self.assertTrue(repo.metadataCurrent())
        repo.metadata_force_expire()
        self.assertFalse(repo.metadataCurrent())

    @mock.patch("time.time", return_value = 100)
    def test_metadata_expire_in(self, unused_time):
        repo = TestedYumRepo("myid")
        repo.metadata_expire = 200
        with mock.patch('dnf.util.file_timestamp', return_value=20):
            self.assertEqual(repo.metadata_expire_in(), (True, 120))

    def test_preload_root(self):
        repo = TestedYumRepo("myid")
        repo.fallback_basecachedir = None # root has no fallback cache
        self.assertFalse(repo._preload_file_from_system_cache("a.filename"))

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch.object(TestedYumRepo, "_preload_file", return_value=True)
    def test_preload(self, unused_method, preload_file_method):
        repo = TestedYumRepo("myid")
        repo.fallback_basecachedir = "/global/cache"
        self.assertEqual(preload_file_method.call_count, 0)
        self.assertTrue(repo._preload_file_from_system_cache("a.filename"))
        # call will happen 5 times, 4 are from dirSetup()
        self.assertEqual(preload_file_method.call_count, 5)
