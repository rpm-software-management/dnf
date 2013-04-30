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
from tests import mock
from tests import support
import dnf.cli.output
import unittest

class OutputTest(unittest.TestCase):
    @staticmethod
    def _keyboard_interrupt(*ignored):
        raise KeyboardInterrupt

    @staticmethod
    def _eof_error(*ignored):
        raise EOFError

    def setUp(self):
        self.output = dnf.cli.output.YumOutput()
        self.output.conf = support.FakeConf()

    @mock.patch('dnf.i18n.input')
    def test_userconfirm(self, input_fnc):
        # with defaultyes==False
        input_fnc.return_value = 'y'
        self.assertTrue(self.output.userconfirm())
        self.assertEqual(input_fnc.call_args, mock.call(u'Is this ok [y/N]: '))

        input_fnc.return_value = 'n'
        self.assertFalse(self.output.userconfirm())

        input_fnc.return_value = ''
        self.assertFalse(self.output.userconfirm())

        input_fnc.side_effect = self._keyboard_interrupt
        input_fnc.return_value = 'y'
        self.assertFalse(self.output.userconfirm())

        input_fnc.side_effect = self._eof_error
        self.assertFalse(self.output.userconfirm())

        # with defaultyes==True
        self.output.conf.defaultyes = True
        input_fnc.side_effect = None
        input_fnc.return_value = ''
        self.assertTrue(self.output.userconfirm())

        input_fnc.side_effect = self._keyboard_interrupt
        input_fnc.return_value = ''
        self.assertFalse(self.output.userconfirm())

        input_fnc.side_effect = self._eof_error
        self.assertTrue(self.output.userconfirm())

    def _to_unicode_mock(str):
        return {'y': 'a', 'yes': 'ano', 'n': 'e', 'no': 'ee'}.get(str, str)

    @mock.patch('dnf.cli.output._', _to_unicode_mock)
    @mock.patch('dnf.i18n.input')
    def test_userconfirm_translated(self, input_fnc):
        input_fnc.return_value = 'ee'
        self.assertFalse(self.output.userconfirm())

        input_fnc.return_value = 'ano'
        self.assertTrue(self.output.userconfirm())

    class _InputGenerator(object):
        INPUT=['haha', 'dada', 'n']

        def __init__(self):
            self.called = 0

        def __call__(self, msg):
            ret = self.INPUT[self.called]
            self.called += 1
            return ret

    def test_userconfirm_bad_input(self):
        input_fnc = self._InputGenerator()
        with mock.patch('dnf.i18n.input', input_fnc):
            self.assertFalse(self.output.userconfirm())
        self.assertEqual(input_fnc.called, 3)
