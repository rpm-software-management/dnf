import mock
import unittest
import dnf.i18n

@mock.patch('locale.setlocale')
class TestLocale(unittest.TestCase):
    def test_setup_locale(self, mock_setlocale):
        dnf.i18n.setup_locale()
        self.assertTrue(2 <= mock_setlocale.call_count <= 3)
