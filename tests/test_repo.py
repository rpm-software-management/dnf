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
