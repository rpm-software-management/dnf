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

import libdnf.swdb

import dnf.cli.output
import dnf.const
import dnf.transaction

import tests.support
from tests.support import mock


INFOOUTPUT_OUTPUT = """\
Name         : tour
Epoch        : 1
Version      : 5
Release      : 0
Arch         : noarch
Size         : 0.0  
Source       : tour.src.rpm
Repo         : None
Summary      : A summary of the package.
URL          : http://example.com
License      : GPL+
Description  : 
"""

LIST_TRANSACTION_OUTPUT = u"""\
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


class OutputFunctionsTest(tests.support.TestCase):
    def test_make_lists(self):
        return
        goal = mock.Mock(get_reason=lambda x: libdnf.swdb.TransactionItemReason_USER)
        ts = dnf.transaction.Transaction()
#        ts = dnf.db.history.
        ts.add_install('pepper-3', [])
        ts.add_install('pepper-2', [])
        lists = dnf.cli.output._make_lists(ts, goal)
        self.assertEmpty(lists.erased)
        self.assertEqual([tsi._active for tsi in lists.installed],
                         ['pepper-2', 'pepper-3'])

    def test_spread(self):
        fun = dnf.cli.output._spread_in_columns
        self.assertEqual(fun(3, "tour", list(range(3))),
                         [('tour', 0, 1), ('', 2, '')])
        self.assertEqual(fun(3, "tour", ()), [('tour', '', '')])
        self.assertEqual(fun(5, "tour", list(range(8))),
                         [('tour', 0, 1, 2, 3), ('', 4, 5, 6, 7)])


class OutputTest(tests.support.DnfBaseTestCase):

    REPOS = ['updates']

    @staticmethod
    def _keyboard_interrupt(*ignored):
        raise KeyboardInterrupt

    @staticmethod
    def _eof_error(*ignored):
        raise EOFError

    def setUp(self):
        super(OutputTest, self).setUp()
        self.output = dnf.cli.output.Output(self.base, self.base.conf)

    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_col_widths(self, _real_term_width):
        rows = (('pep', 'per', 'row',
                 '', 'lon', 'e'))
        self.assertCountEqual(self.output._col_widths(rows), (-38, -37, -1))

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output.P_', dnf.pycomp.NullTranslations().ungettext)
    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_list_transaction(self, _real_term_width):
        return
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
        INPUT = ['haha', 'dada', 'n']

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
    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_infoOutput_with_none_description(self, _real_term_width):
        pkg = tests.support.MockPackage('tour-5-0.noarch')
        pkg._from_system = False
        pkg._size = 0
        pkg._pkgid = None
        pkg.repoid = None
        pkg.e = pkg.epoch = 1
        pkg.v = pkg.version
        pkg.r = pkg.release
        pkg.sourcerpm = 'tour.src.rpm'
        pkg.summary = 'A summary of the package.'
        pkg.url = 'http://example.com'
        pkg.license = 'GPL+'
        pkg.description = None

        with mock.patch('sys.stdout') as stdout:
            print(self.output.infoOutput(pkg))
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

GROUPS_IN_ENVIRONMENT_OUTPUT = """\
Environment Group: Sugar Desktop Environment
 Description: A software playground for learning about learning.
 Mandatory Groups:
   Pepper's
   Solid Ground
 Optional Groups:
   Base
"""


class GroupOutputTest(tests.support.DnfBaseTestCase):

    REPOS = ['main']
    COMPS = True

    def setUp(self):
        super(GroupOutputTest, self).setUp()
        self.output = dnf.cli.output.Output(self.base, self.base.conf)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_group_info(self, _real_term_width):
        group = self.base.comps.group_by_pattern('Peppers')
        with tests.support.patch_std_streams() as (stdout, stderr):
            self.output.display_pkgs_in_groups(group)
        self.assertEqual(stdout.getvalue(), PKGS_IN_GROUPS_OUTPUT)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_group_verbose_info(self, _real_term_width):
        group = self.base.comps.group_by_pattern('Peppers')
        self.base.set_debuglevel(dnf.const.VERBOSE_LEVEL)
        with tests.support.patch_std_streams() as (stdout, stderr):
            self.output.display_pkgs_in_groups(group)
        self.assertEqual(stdout.getvalue(), PKGS_IN_GROUPS_VERBOSE_OUTPUT)

    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test_environment_info(self, _real_term_width):
        env = self.base.comps.environments[0]
        with tests.support.patch_std_streams() as (stdout, stderr):
            self.output.display_groups_in_environment(env)
        self.assertEqual(stdout.getvalue(), GROUPS_IN_ENVIRONMENT_OUTPUT)
