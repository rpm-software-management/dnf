from dnf.rpmUtils.connection import RpmConnection
import inspect
import unittest

class TestConnection(unittest.TestCase):
    def test_sanity(self):
        rpm = RpmConnection('/')
        ts = rpm.readonly_ts
        self.assertTrue(inspect.isbuiltin(ts.clean))
