# Copyright (C) 2012-2014  Red Hat, Inc.
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
from tests import support
from tests.support import mock

import dnf.cli.output
import dnf.transaction
import io
import unittest

INFOOUTPUT_OUTPUT="""\
Name        : tour
Arch        : noarch
Epoch       : 0
Version     : 5
Release     : 0
Size        : 0.0  
Repo        : None
Summary     : A summary of the package.
URL         : http://example.com
License     : GPL+
Description : 

"""

LIST_TRANSACTION_OUTPUT=u"""
================================================================================
 Package           Arch              Version           Repository          Size
================================================================================
Upgrading:
 pepper            x86_64            20-1              updates              0  
     replacing  hole.x86_64 1-1

Transaction Summary
================================================================================
Upgrade  1 Package
"""

class OutputTest(support.TestCase):
    @staticmethod
    def _keyboard_interrupt(*ignored):
        raise KeyboardInterrupt

    @staticmethod
    def _eof_error(*ignored):
        raise EOFError

    def setUp(self):
        self.base = support.MockBase('updates')
        self.output = dnf.cli.output.Output(self.base, self.base.conf)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output.P_', dnf.pycomp.NullTranslations().ungettext)
    @mock.patch('dnf.cli.output._term_width', return_value=80)
    def test_list_transaction(self, _term_width):
        sack = self.base.sack
        q = sack.query().filter(name='pepper')
        i = q.installed()[0]
        u = q.available()[0]
        obs = sack.query().filter(name='hole').installed()[0]

        transaction = dnf.transaction.Transaction()
        transaction.add_upgrade(u, i, [obs])
        self.assertEqual(self.output.list_transaction(transaction),
                         LIST_TRANSACTION_OUTPUT)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.i18n.ucd_input')
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
    @mock.patch('dnf.i18n.ucd_input')
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
        with mock.patch('dnf.i18n.ucd_input', input_fnc):
            self.assertFalse(self.output.userconfirm())
        self.assertEqual(input_fnc.called, 3)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_infoOutput_with_none_description(self):
        pkg = support.MockPackage('tour-5-0.noarch')
        pkg.from_system = False
        pkg.size = 0
        pkg.pkgid = None
        pkg.repoid = None
        pkg.e = pkg.epoch
        pkg.v = pkg.version
        pkg.r = pkg.release
        pkg.summary = 'A summary of the package.'
        pkg.url = 'http://example.com'
        pkg.license = 'GPL+'
        pkg.description = None

        with mock.patch('sys.stdout') as stdout:
            self.output.infoOutput(pkg)
        written = ''.join([mc[1][0] for mc in stdout.method_calls
                          if mc[0] == 'write'])
        self.assertEqual(written, INFOOUTPUT_OUTPUT)

PKGS_IN_GROUPS_OUTPUT = u"""\

Group: Pepper's
 Mandatory Packages:
   hole
   lotus
"""

PKGS_IN_GROUPS_VERBOSE_OUTPUT = u"""\

Group: Pepper's
 Group-Id: Peppers
 Mandatory Packages:
   hole-1-1.x86_64                                                       @System
   lotus-3-16.i686                                                       main   
"""

class GroupOutputTest(unittest.TestCase):
    def setUp(self):
        base = support.MockBase('main')
        base.read_mock_comps()
        output = dnf.cli.output.Output(base, base.conf)

        self.base = base
        self.output = output

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._term_width', return_value=80)
    def test_group_info(self, _term_width):
        group = self.base.comps.group_by_pattern('Peppers')
        with support.patch_std_streams() as (stdout, stderr):
            self.output.displayPkgsInGroups(group)
        self.assertEqual(stdout.getvalue(), PKGS_IN_GROUPS_OUTPUT)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._term_width', return_value=80)
    def test_group_verbose_info(self, _term_width):
        group = self.base.comps.group_by_pattern('Peppers')
        self.output.conf.verbose = True
        with support.patch_std_streams() as (stdout, stderr):
            self.output.displayPkgsInGroups(group)
        self.assertEqual(stdout.getvalue(), PKGS_IN_GROUPS_VERBOSE_OUTPUT)

class TermTest(unittest.TestCase):

    """Tests of ```dnf.cli.output.Term``` class."""

    def test_mode_tty(self):
        """Test whether all modes are properly set if the stream is a tty.

        It also ensures that all the values are unicode strings.

        """
        tty = mock.create_autospec(io.IOBase)
        tty.isatty.return_value = True

        tigetstr = lambda name: '<cap_%(name)s>' % locals()
        with mock.patch('curses.tigetstr', autospec=True, side_effect=tigetstr):
            term = dnf.cli.output.Term(tty)

        self.assertEqual(term.MODE,
                         {u'blink': tigetstr(u'blink'),
                          u'bold': tigetstr(u'bold'),
                          u'dim': tigetstr(u'dim'),
                          u'normal': tigetstr(u'sgr0'),
                          u'reverse': tigetstr(u'rev'),
                          u'underline': tigetstr(u'smul')})

    def test_mode_tty_incapable(self):
        """Test whether modes correct if the stream is an incapable tty.

        It also ensures that all the values are unicode strings.

        """
        tty = mock.create_autospec(io.IOBase)
        tty.isatty.return_value = True

        with mock.patch('curses.tigetstr', autospec=True, return_value=None):
            term = dnf.cli.output.Term(tty)

        self.assertEqual(term.MODE,
                         {u'blink': u'',
                          u'bold': u'',
                          u'dim': u'',
                          u'normal': u'',
                          u'reverse': u'',
                          u'underline': u''})

    def test_mode_nontty(self):
        """Test whether all modes are properly set if the stream is not a tty.

        It also ensures that all the values are unicode strings.

        """
        nontty = mock.create_autospec(io.IOBase)
        nontty.isatty.return_value = False

        term = dnf.cli.output.Term(nontty)

        self.assertEqual(term.MODE,
                         {u'blink': u'',
                          u'bold': u'',
                          u'dim': u'',
                          u'normal': u'',
                          u'reverse': u'',
                          u'underline': u''})
