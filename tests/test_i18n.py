# -*- coding: utf-8 -*-
#
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

class TestInput(unittest.TestCase):
    def test_assumption(self):
        """ Test that raw_input() always fails on a unicode string with accented
            characters. If this is not the case we might not need i18n.input()
            as a raw_input() wrapper.
         """
        if sys.stdout.isatty():
            # Only works when stdout is a terminal (and not captured in some
            # way, for instance when nosetests is run without the -s switch).
            self.assertRaises(UnicodeEncodeError, raw_input, UC_TEXT)

    @mock.patch('sys.stdout')
    @mock.patch('__builtin__.raw_input', lambda x: x)
    def test_input(self, stdout):
        stdout.encoding = None
        s = dnf.i18n.input(UC_TEXT)
        self.assertEqual(s, UC_TEXT.encode('utf8'))

        stdout.encoding = 'iso-8859-2'
        s = dnf.i18n.input(UC_TEXT)
        self.assertEqual(s, UC_TEXT.encode('iso-8859-2'))

        self.assertRaises(TypeError, dnf.i18n.input, "string")
