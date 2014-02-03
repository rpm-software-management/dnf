# -*- coding: utf-8 -*-
#
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
try:
    from unittest import mock
except ImportError:
    from tests import mock
import locale
import unittest
import dnf.i18n
import os
import sys
from dnf.pycomp import PY3
from tests.support import PycompTestCase

UC_TEXT          = u'Šířka' # means 'Width' in Czech
UC_TEXT_OSERROR  = u'Soubor již existuje' # 'File already exists'
STR_TEXT_OSERROR = 'Soubor již existuje'

@mock.patch('locale.setlocale')
class TestLocale(PycompTestCase):
    def test_setup_locale(self, mock_setlocale):
        dnf.i18n.setup_locale()
        self.assertTrue(2 <= mock_setlocale.call_count <= 3)

class TestStdout(PycompTestCase):
    def test_setup_stdout(self):
        # No stdout output can be seen when sys.stdout is patched, debug msgs,
        # etc. included.
        with mock.patch('sys.stdout', spec=('write',)):
            retval = dnf.i18n.setup_stdout()
            self.assertFalse(retval)
        with mock.patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = None
            retval = dnf.i18n.setup_stdout()
            self.assertFalse(retval)
        with mock.patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = 'UTF-8'
            retval = dnf.i18n.setup_stdout()
            self.assertTrue(retval)
        with mock.patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = 'ISO-8859-2'
            retval = dnf.i18n.setup_stdout()
            self.assertFalse(retval)

    def test_stream(self):
        fileobj = dnf.pycomp.StringIO()
        stream = dnf.i18n.UnicodeStream(fileobj, "ISO-8859-2")
        stream.write(UC_TEXT)
        output = fileobj.getvalue()
        self.assertEqual(output, u'\u0160\xed\u0159ka')
        self.assertEqual(len(output), len(UC_TEXT))

class TestInput(PycompTestCase):
    @unittest.skipIf(PY3, "builtin input accepts unicode and bytes")
    def test_assumption(self):
        """ Test that raw_input() always fails on a unicode string with accented
            characters. If this is not the case we might not need i18n.input()
            as a raw_input() wrapper.
         """
        if sys.stdout.isatty():
            # Only works when stdout is a terminal (and not captured in some
            # way, for instance when nosetests is run without the -s switch).
            self.assertRaises(UnicodeEncodeError, raw_input, UC_TEXT)

    @unittest.skipIf(PY3, "in python3 there's no conversion in dnf.i18n.input")
    @mock.patch('sys.stdout')
    @mock.patch('__builtin__.raw_input', lambda x: x)
    def test_input(self, stdout):
        stdout.encoding = None
        s = dnf.i18n.ucd_input(UC_TEXT)
        self.assertEqual(s, UC_TEXT.encode('utf8'))

        stdout.encoding = 'iso-8859-2'
        s = dnf.i18n.ucd_input(UC_TEXT)
        self.assertEqual(s, UC_TEXT.encode('iso-8859-2'))

        self.assertRaises(TypeError, dnf.i18n.ucd_input, "string")

class TestConversion(PycompTestCase):
    @mock.patch('dnf.i18n._guess_encoding', return_value='utf-8')
    def test_ucd(self, _unused):
        s = UC_TEXT.encode('utf8')
        # the assumption is this string can't be simply converted back to
        # unicode:
        u = dnf.i18n.ucd(s)
        self.assertEqual(u, UC_TEXT)
        # test a sample OSError, typically constructed with an error code and a
        # utf-8 encoded string:
        obj = OSError(17, 'Soubor již existuje')
        if not PY3:
            # in Python 3 string already in unicode
            # direct decode fails:
            self.assertRaises(UnicodeDecodeError, unicode, s)
            self.assertRaises(UnicodeDecodeError, unicode, obj)
        expected = u"[Errno 17] %s" % UC_TEXT_OSERROR
        self.assertEqual(dnf.i18n.ucd(obj), expected)
        # ucd() should return unicode unmodified
        self.assertEqual(dnf.i18n.ucd(expected), expected)
