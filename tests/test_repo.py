import unittest
import mock

from dnf.yum import yumRepo

class RepoTest(unittest.TestCase):
    def test_metadata_current(self):
        repo = yumRepo.YumRepository("myid")
        self.assertFalse(repo.metadataCurrent())
        repo._metadataCurrent = True		# override the cached value
        self.assertTrue(repo.metadataCurrent())
        repo.metadata_force_expire()
        self.assertFalse(repo.metadataCurrent())

    @mock.patch("time.time", return_value = 100)
    def test_metadata_expire_in(self, unused_time):
        repo = yumRepo.YumRepository("myid")
        repo.metadata_expire = 200
        with mock.patch('dnf.util.file_timestamp', return_value=20):
            self.assertEqual(repo.metadata_expire_in(), (True, 120))
