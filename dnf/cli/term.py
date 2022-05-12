# Copyright (C) 2013-2014  Red Hat, Inc.
# Terminal routines.
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
import curses
import dnf.pycomp
import fcntl
import re
import struct
import sys
import termios


def _real_term_width(fd=1):
    """ Get the real terminal width """
    try:
        buf = 'abcdefgh'
        buf = fcntl.ioctl(fd, termios.TIOCGWINSZ, buf)
        ret = struct.unpack(b'hhhh', buf)[1]
        return ret
    except IOError:
        return None


def _term_width(fd=1):
    """ Compute terminal width falling to default 80 in case of trouble"""
    tw = _real_term_width(fd=1)
    if not tw:
        return 80
    elif tw < 20:
        return 20
    else:
        return tw


class Term(object):
    """A class to provide some terminal "UI" helpers based on curses."""

    # From initial search for "terminfo and python" got:
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/475116
    # ...it's probably not copyrightable, but if so ASPN says:
    #
    #  Except where otherwise noted, recipes in the Python Cookbook are
    # published under the Python license.

    __enabled = True

    real_columns = property(lambda self: _real_term_width())
    columns = property(lambda self: _term_width())

    __cap_names = {
        'underline' : 'smul',
        'reverse' : 'rev',
        'normal' : 'sgr0',
        }

    __colors = {
        'black' : 0,
        'blue' : 1,
        'green' : 2,
        'cyan' : 3,
        'red' : 4,
        'magenta' : 5,
        'yellow' : 6,
        'white' : 7
        }
    __ansi_colors = {
        'black' : 0,
        'red' : 1,
        'green' : 2,
        'yellow' : 3,
        'blue' : 4,
        'magenta' : 5,
        'cyan' : 6,
        'white' : 7
        }
    __ansi_forced_MODE = {
        'bold' : '\x1b[1m',
        'blink' : '\x1b[5m',
        'dim' : '',
        'reverse' : '\x1b[7m',
        'underline' : '\x1b[4m',
        'normal' : '\x1b(B\x1b[m'
        }
    __ansi_forced_FG_COLOR = {
        'black' : '\x1b[30m',
        'red' : '\x1b[31m',
        'green' : '\x1b[32m',
        'yellow' : '\x1b[33m',
        'blue' : '\x1b[34m',
        'magenta' : '\x1b[35m',
        'cyan' : '\x1b[36m',
        'white' : '\x1b[37m'
        }
    __ansi_forced_BG_COLOR = {
        'black' : '\x1b[40m',
        'red' : '\x1b[41m',
        'green' : '\x1b[42m',
        'yellow' : '\x1b[43m',
        'blue' : '\x1b[44m',
        'magenta' : '\x1b[45m',
        'cyan' : '\x1b[46m',
        'white' : '\x1b[47m'
        }

    def __forced_init(self):
        self.MODE = self.__ansi_forced_MODE
        self.FG_COLOR = self.__ansi_forced_FG_COLOR
        self.BG_COLOR = self.__ansi_forced_BG_COLOR

    def reinit(self, term_stream=None, color='auto'):
        """Reinitializes the :class:`Term`.

        :param term_stream:  the terminal stream that the
           :class:`Term` should be initialized to use.  If
           *term_stream* is not given, :attr:`sys.stdout` is used.
        :param color: when to colorize output.  Valid values are
           'always', 'auto', and 'never'.  'always' will use ANSI codes
           to always colorize output, 'auto' will decide whether do
           colorize depending on the terminal, and 'never' will never
           colorize.
        """
        self.__enabled = True
        self.lines = 24

        if color == 'always':
            self.__forced_init()
            return

        # Output modes:
        self.MODE = {
            'bold' : '',
            'blink' : '',
            'dim' : '',
            'reverse' : '',
            'underline' : '',
            'normal' : ''
            }

        # Colours
        self.FG_COLOR = {
            'black' : '',
            'blue' : '',
            'green' : '',
            'cyan' : '',
            'red' : '',
            'magenta' : '',
            'yellow' : '',
            'white' : ''
            }

        self.BG_COLOR = {
            'black' : '',
            'blue' : '',
            'green' : '',
            'cyan' : '',
            'red' : '',
            'magenta' : '',
            'yellow' : '',
            'white' : ''
            }

        if color == 'never':
            self.__enabled = False
            return
        assert color == 'auto'

        # If the stream isn't a tty, then assume it has no capabilities.
        if not term_stream:
            term_stream = sys.stdout
        if not term_stream.isatty():
            self.__enabled = False
            return

        # Check the terminal type.  If we fail, then assume that the
        # terminal has no capabilities.
        try:
            curses.setupterm(fd=term_stream.fileno())
        except Exception:
            self.__enabled = False
            return
        self._ctigetstr = curses.tigetstr

        self.lines = curses.tigetnum('lines')

        # Look up string capabilities.
        for cap_name in self.MODE:
            mode = cap_name
            if cap_name in self.__cap_names:
                cap_name = self.__cap_names[cap_name]
            self.MODE[mode] = self._tigetstr(cap_name)

        # Colors
        set_fg = self._tigetstr('setf').encode('utf-8')
        if set_fg:
            for (color, val) in self.__colors.items():
                self.FG_COLOR[color] = curses.tparm(set_fg, val).decode() or ''
        set_fg_ansi = self._tigetstr('setaf').encode('utf-8')
        if set_fg_ansi:
            for (color, val) in self.__ansi_colors.items():
                fg_color = curses.tparm(set_fg_ansi, val).decode() or ''
                self.FG_COLOR[color] = fg_color
        set_bg = self._tigetstr('setb').encode('utf-8')
        if set_bg:
            for (color, val) in self.__colors.items():
                self.BG_COLOR[color] = curses.tparm(set_bg, val).decode() or ''
        set_bg_ansi = self._tigetstr('setab').encode('utf-8')
        if set_bg_ansi:
            for (color, val) in self.__ansi_colors.items():
                bg_color = curses.tparm(set_bg_ansi, val).decode() or ''
                self.BG_COLOR[color] = bg_color

    def __init__(self, term_stream=None, color='auto'):
        self.reinit(term_stream, color)

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        cap = self._ctigetstr(cap_name) or ''
        if dnf.pycomp.is_py3bytes(cap):
            cap = cap.decode()
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def color(self, color, s):
        """Colorize string with color"""
        return (self.MODE[color] + str(s) + self.MODE['normal'])

    def bold(self, s):
        """Make string bold."""
        return self.color('bold', s)

    def sub(self, haystack, beg, end, needles, escape=None, ignore_case=False):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        *beg*, and postfix each occurrence with *end*, then return the
        modified string.  For example::

           >>> yt = Term()
           >>> yt.sub('spam and eggs', 'x', 'z', ['and'])
           'spam xandz eggs'

        This is particularly useful for emphasizing certain words
        in output: for example, calling :func:`sub` with *beg* =
        MODE['bold'] and *end* = MODE['normal'] will return a string
        that when printed to the terminal will appear to be *haystack*
        with each occurrence of the strings in *needles* in bold
        face.  Note, however, that the :func:`sub_mode`,
        :func:`sub_bold`, :func:`sub_fg`, and :func:`sub_bg` methods
        provide convenient ways to access this same emphasizing functionality.

        :param haystack: the string to be modified
        :param beg: the string to be prefixed onto matches
        :param end: the string to be postfixed onto matches
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :param escape: a function that accepts a string and returns
           the same string with problematic characters escaped.  By
           default, :func:`re.escape` is used.
        :param ignore_case: whether case should be ignored when
           searching for matches
        :return: *haystack* with *beg* prefixing, and *end*
          postfixing, occurrences of the strings in *needles*
        """
        if not self.__enabled:
            return haystack

        if not escape:
            escape = re.escape

        render = lambda match: beg + match.group() + end
        for needle in needles:
            pat = escape(needle)
            flags = re.I if ignore_case else 0
            haystack = re.sub(pat, render, haystack, flags=flags)
        return haystack

    def sub_norm(self, haystack, beg, needles, **kwds):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        *beg*, and postfix each occurrence with self.MODE['normal'],
        then return the modified string.  If *beg* is an ANSI escape
        code, such as given by self.MODE['bold'], this method will
        return *haystack* with the formatting given by the code only
        applied to the strings in *needles*.

        :param haystack: the string to be modified
        :param beg: the string to be prefixed onto matches
        :param end: the string to be postfixed onto matches
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :return: *haystack* with *beg* prefixing, and self.MODE['normal']
          postfixing, occurrences of the strings in *needles*
        """
        return self.sub(haystack, beg, self.MODE['normal'], needles, **kwds)

    def sub_mode(self, haystack, mode, needles, **kwds):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        self.MODE[*mode*], and postfix each occurrence with
        self.MODE['normal'], then return the modified string.  This
        will return a string that when printed to the terminal will
        appear to be *haystack* with each occurrence of the strings in
        *needles* in the given *mode*.

        :param haystack: the string to be modified
        :param mode: the mode to set the matches to be in.  Valid
           values are given by self.MODE.keys().
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :return: *haystack* with self.MODE[*mode*] prefixing, and
          self.MODE['normal'] postfixing, occurrences of the strings
          in *needles*
        """
        return self.sub_norm(haystack, self.MODE[mode], needles, **kwds)

    def sub_bold(self, haystack, needles, **kwds):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        self.MODE['bold'], and postfix each occurrence with
        self.MODE['normal'], then return the modified string.  This
        will return a string that when printed to the terminal will
        appear to be *haystack* with each occurrence of the strings in
        *needles* in bold face.

        :param haystack: the string to be modified
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :return: *haystack* with self.MODE['bold'] prefixing, and
          self.MODE['normal'] postfixing, occurrences of the strings
          in *needles*
        """
        return self.sub_mode(haystack, 'bold', needles, **kwds)

    def sub_fg(self, haystack, color, needles, **kwds):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        self.FG_COLOR[*color*], and postfix each occurrence with
        self.MODE['normal'], then return the modified string.  This
        will return a string that when printed to the terminal will
        appear to be *haystack* with each occurrence of the strings in
        *needles* in the given color.

        :param haystack: the string to be modified
        :param color: the color to set the matches to be in.  Valid
           values are given by self.FG_COLOR.keys().
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :return: *haystack* with self.FG_COLOR[*color*] prefixing, and
          self.MODE['normal'] postfixing, occurrences of the strings
          in *needles*
        """
        return self.sub_norm(haystack, self.FG_COLOR[color], needles, **kwds)

    def sub_bg(self, haystack, color, needles, **kwds):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        self.BG_COLOR[*color*], and postfix each occurrence with
        self.MODE['normal'], then return the modified string.  This
        will return a string that when printed to the terminal will
        appear to be *haystack* with each occurrence of the strings in
        *needles* highlighted in the given background color.

        :param haystack: the string to be modified
        :param color: the background color to set the matches to be in.  Valid
           values are given by self.BG_COLOR.keys().
        :param needles: a list of strings to add the prefixes and
           postfixes to
        :return: *haystack* with self.BG_COLOR[*color*] prefixing, and
          self.MODE['normal'] postfixing, occurrences of the strings
          in *needles*
        """
        return self.sub_norm(haystack, self.BG_COLOR[color], needles, **kwds)
