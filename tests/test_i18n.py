# -*- coding: utf-8 -*-

import mock
import unittest
import dnf.i18n
import sys

UC_TEXT=u'Šířka' # means 'Width' in Czech

@mock.patch('locale.setlocale')
class TestLocale(unittest.TestCase):
    def test_setup_locale(self, mock_setlocale):
        dnf.i18n.setup_locale()
        self.assertTrue(2 <= mock_setlocale.call_count <= 3)

class TestStdout(unittest.TestCase):
    def test_setup_stdout(self):
        # No stdout output can be seen when sys.stdout is patched, debug msgs,
        # etc. included.
        with mock.patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = None
            retval = dnf.i18n.setup_stdout()
            self.assertFalse(retval)
        with mock.patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = 'UTF-8'
            retval = dnf.i18n.setup_stdout()
            self.assertTrue(retval)

    def test_stream(self):
        fileobj = mock.Mock()
        fileobj.encoding = None
        stream = dnf.i18n.UnicodeStream(fileobj, "ISO-8859-2")
        stream.write(UC_TEXT)
        output = fileobj.write.call_args[0][0]
        self.assertEqual(output, '\xa9\xed\xf8ka')
        self.assertEqual(len(output), len(UC_TEXT))
