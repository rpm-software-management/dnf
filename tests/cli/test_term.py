# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

import io

import dnf.cli.term

import tests.support
from tests.support import mock


class TermTest(tests.support.TestCase):

    """Tests of ```dnf.cli.term.Term``` class."""

    def test_mode_tty(self):
        """Test whether all modes are properly set if the stream is a tty.

        It also ensures that all the values are unicode strings.

        """
        tty = mock.create_autospec(io.IOBase)
        tty.isatty.return_value = True

        def tigetstr(name):
            return '<cap_%(name)s>' % locals()

        with mock.patch('curses.tigetstr', autospec=True, side_effect=tigetstr):
            term = dnf.cli.term.Term(tty)

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
            term = dnf.cli.term.Term(tty)

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

        term = dnf.cli.term.Term(nontty)

        self.assertEqual(term.MODE,
                         {u'bold': '\033[1m',
                          u'blink': u'\033[5m',
                          u'dim': u'\033[2m',
                          u'reverse': u'\033[7m',
                          u'underline': u'\033[4m',
                          u'normal': u'\033[0m'})
