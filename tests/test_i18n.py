# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import sys
import unittest

import dnf.i18n
from dnf.pycomp import PY3
from dnf.i18n import fill_exact_width, textwrap_fill

import tests.support
from tests.support import mock


UC_TEXT = 'Šířka'  # means 'Width' in Czech
UC_TEXT_OSERROR = 'Soubor již existuje'  # 'File already exists'
STR_TEXT_OSERROR = 'Soubor již existuje'


@mock.patch('locale.setlocale')
class TestLocale(tests.support.TestCase):
    def test_setup_locale(self, mock_setlocale):
        dnf.i18n.setup_locale()
        self.assertTrue(1 <= mock_setlocale.call_count <= 2)


class TestStdout(tests.support.TestCase):
    def test_setup_stdout(self):
        # No stdout output can be seen when sys.stdout is patched, debug msgs,
        # etc. included.
        with mock.patch('sys.stdout', spec=('write', 'isatty')):
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
        self.assertEqual(output, u'\u0160\xed\u0159ka' if PY3 else b'\xa9\xed\xf8ka')
        self.assertEqual(len(output), len(UC_TEXT))


class TestInput(tests.support.TestCase):
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


class TestConversion(tests.support.TestCase):
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
        expected = u"[Errno 17] %s" % UC_TEXT_OSERROR
        self.assertEqual(dnf.i18n.ucd(obj), expected)
        # ucd() should return unicode unmodified
        self.assertEqual(dnf.i18n.ucd(expected), expected)

    def test_download_error_unicode(self):
        err_map = {"e1": ["x", "y"]}
        err = dnf.exceptions.DownloadError(err_map)
        self.assertEqual("e1: x\ne1: y", str(err))
        self.assertEqual("e1: x\ne1: y", dnf.i18n.ucd(err))

    @mock.patch('locale.getpreferredencoding', return_value='ANSI_X3.4-1968')
    def test_ucd_acii(self, _unused):
        s = UC_TEXT.encode('utf8')
        # ascii coding overridden by utf8
        u = dnf.i18n.ucd(s)
        self.assertEqual(u, UC_TEXT)

    @mock.patch('dnf.i18n._guess_encoding', return_value='utf-8')
    def test_ucd_skip(self, _unused):
        s = UC_TEXT.encode('iso-8859-2')
        # not decoded chars are skipped
        u = dnf.i18n.ucd(s)
        self.assertEqual(u, "ka")


class TestFormatedOutput(tests.support.TestCase):
    def test_fill_exact_width(self):
        msg = "message"
        pre = "<"
        suf = ">"
        self.assertEqual("%-*.*s" % (5, 10, msg), fill_exact_width(msg, 5, 10))
        self.assertEqual("重uř ", fill_exact_width("重uř", 5, 10))
        self.assertEqual("%10.5s" % msg,
                         fill_exact_width(msg, 10, 5, left=False))
        self.assertEqual("%s%.5s%s" % (pre, msg, suf),
                         fill_exact_width(msg, 0, 5, prefix=pre, suffix=suf))

    def test_exact_width(self):
        self.assertEqual(dnf.i18n.exact_width("重uř"), 4)

    def test_textwrap_fill(self):
        msg = "12345 67890"
        one_line = textwrap_fill(msg, 12)
        self.assertEqual(one_line, "12345 67890")
        two_lines = textwrap_fill(msg, 7, subsequent_indent=">>")
        self.assertEqual(two_lines,
                         "12345\n>>67890")
        asian_msg = "重重 uř"
        self.assertEqual(textwrap_fill(asian_msg, 7), asian_msg)
        asian_two_lines = textwrap_fill("重重\nuř", 5, subsequent_indent=">>")
        self.assertEqual(asian_two_lines, "重重\n>>uř")
