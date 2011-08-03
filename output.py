#!/usr/bin/python -t

"""Handle actual output from the cli."""

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2005 Duke University 

import sys
import time
import logging
import types
import gettext
import pwd
import rpm

import re # For YumTerm

from weakref import proxy as weakref

from urlgrabber.progress import TextMeter
import urlgrabber.progress
from urlgrabber.grabber import URLGrabError
from yum.misc import prco_tuple_to_string
from yum.i18n import to_str, to_utf8, to_unicode
import yum.misc
from rpmUtils.miscutils import checkSignals, formatRequire
from yum.constants import *

from yum import logginglevels, _, P_
from yum.rpmtrans import RPMBaseCallback
from yum.packageSack import packagesNewestByNameArch
import yum.packages

import yum.history

from yum.i18n import utf8_width, utf8_width_fill, utf8_text_fill

def _term_width():
    """ Simple terminal width, limit to 20 chars. and make 0 == 80. """
    if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
        return 80
    ret = urlgrabber.progress.terminal_width_cached()
    if ret == 0:
        return 80
    if ret < 20:
        return 20
    return ret


class YumTextMeter(TextMeter):
    """A class to display text progress bar output."""

    def update(self, amount_read, now=None):
        """Update the status of the text progress bar

        :param amount_read: the amount of data, in bytes, that has been read
        :param now: the current time in seconds since the epoch.  If
           *now* is not given, the output of :func:`time.time()` will
           be used.
        """
        checkSignals()
        TextMeter.update(self, amount_read, now)

class YumTerm:
    """A class to provide some terminal "UI" helpers based on curses."""

    # From initial search for "terminfo and python" got:
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/475116
    # ...it's probably not copyrightable, but if so ASPN says:
    #
    #  Except where otherwise noted, recipes in the Python Cookbook are
    # published under the Python license.

    __enabled = True

    if hasattr(urlgrabber.progress, 'terminal_width_cached'):
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
        """Reinitializes the :class:`YumTerm`.

        :param term_stream:  the terminal stream that the
           :class:`YumTerm` should be initialized to use.  If
           *term_stream* is not given, :attr:`sys.stdout` is used.
        :param color: when to colorize output.  Valid values are
           'always', 'auto', and 'never'.  'always' will use ANSI codes
           to always colorize output, 'auto' will decide whether do
           colorize depending on the terminal, and 'never' will never
           colorize.
        """
        self.__enabled = True
        if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
            self.columns = 80
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

        # Curses isn't available on all platforms
        try:
            import curses
        except:
            self.__enabled = False
            return

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
        except:
            self.__enabled = False
            return
        self._ctigetstr = curses.tigetstr

        if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
            self.columns = curses.tigetnum('cols')
        self.lines = curses.tigetnum('lines')
        
        # Look up string capabilities.
        for cap_name in self.MODE:
            mode = cap_name
            if cap_name in self.__cap_names:
                cap_name = self.__cap_names[cap_name]
            self.MODE[mode] = self._tigetstr(cap_name) or ''

        # Colors
        set_fg = self._tigetstr('setf')
        if set_fg:
            for (color, val) in self.__colors.items():
                self.FG_COLOR[color] = curses.tparm(set_fg, val) or ''
        set_fg_ansi = self._tigetstr('setaf')
        if set_fg_ansi:
            for (color, val) in self.__ansi_colors.items():
                self.FG_COLOR[color] = curses.tparm(set_fg_ansi, val) or ''
        set_bg = self._tigetstr('setb')
        if set_bg:
            for (color, val) in self.__colors.items():
                self.BG_COLOR[color] = curses.tparm(set_bg, val) or ''
        set_bg_ansi = self._tigetstr('setab')
        if set_bg_ansi:
            for (color, val) in self.__ansi_colors.items():
                self.BG_COLOR[color] = curses.tparm(set_bg_ansi, val) or ''

    def __init__(self, term_stream=None, color='auto'):
        self.reinit(term_stream, color)

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        cap = self._ctigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def sub(self, haystack, beg, end, needles, escape=None, ignore_case=False):
        """Search the string *haystack* for all occurrences of any
        string in the list *needles*.  Prefix each occurrence with
        *beg*, and postfix each occurrence with *end*, then return the
        modified string.  For example::
           
           >>> yt = YumTerm()
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
            if ignore_case:
                pat = re.template(pat, re.I)
            haystack = re.sub(pat, render, haystack)
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



class YumOutput:
    """Main output class for the yum command line."""

    def __init__(self):
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        if hasattr(rpm, "expandMacro"):
            self.i18ndomains = rpm.expandMacro("%_i18ndomains").split(":")
        else:
            self.i18ndomains = ["redhat-dist"]

        self.term = YumTerm()
        self._last_interrupt = None

    
    def printtime(self):
        """Return a string representing the current time in the form::

           Mon dd hh:mm:ss

        :return: a string representing the current time
        """
        months = [_('Jan'), _('Feb'), _('Mar'), _('Apr'), _('May'), _('Jun'),
                  _('Jul'), _('Aug'), _('Sep'), _('Oct'), _('Nov'), _('Dec')]
        now = time.localtime(time.time())
        ret = months[int(time.strftime('%m', now)) - 1] + \
              time.strftime(' %d %T ', now)
        return ret
         
    def failureReport(self, errobj):
        """Perform failure output for failovers from urlgrabber

        :param errobj: :class:`urlgrabber.grabber.CallbackObject`
           containing information about the error
        :raises: *errobj*.exception
        """
        self.logger.error('%s: %s', errobj.url, errobj.exception)
        self.logger.error(_('Trying other mirror.'))
        raise errobj.exception
    
        
    def simpleProgressBar(self, current, total, name=None):
        """Output the current status to the terminal using a simple
        status bar.

        :param current: a number representing the amount of work
           already done
        :param total: a number representing the total amount of work
           to be done
        :param name: a name to label the progress bar with
        """
        progressbar(current, total, name)

    def _highlight(self, highlight):
        hibeg = ''
        hiend = ''
        if not highlight:
            pass
        elif not isinstance(highlight, basestring) or highlight == 'bold':
            hibeg = self.term.MODE['bold']
        elif highlight == 'normal':
            pass # Minor opt.
        else:
            # Turn a string into a specific output: colour, bold, etc.
            for high in highlight.replace(',', ' ').split():
                if False: pass
                elif high == 'normal':
                    hibeg = ''
                elif high in self.term.MODE:
                    hibeg += self.term.MODE[high]
                elif high in self.term.FG_COLOR:
                    hibeg += self.term.FG_COLOR[high]
                elif (high.startswith('fg:') and
                      high[3:] in self.term.FG_COLOR):
                    hibeg += self.term.FG_COLOR[high[3:]]
                elif (high.startswith('bg:') and
                      high[3:] in self.term.BG_COLOR):
                    hibeg += self.term.BG_COLOR[high[3:]]

        if hibeg:
            hiend = self.term.MODE['normal']
        return (hibeg, hiend)

    def _sub_highlight(self, haystack, highlight, needles, **kwds):
        hibeg, hiend = self._highlight(highlight)
        return self.term.sub(haystack, hibeg, hiend, needles, **kwds)

    @staticmethod
    def _calc_columns_spaces_helps(current, data_tups, left):
        """ Spaces left on the current field will help how many pkgs? """
        ret = 0
        for tup in data_tups:
            if left < (tup[0] - current):
                break
            ret += tup[1]
        return ret

    def calcColumns(self, data, columns=None, remainder_column=0,
                    total_width=None, indent=''):
        """Dynamically calculate the widths of the columns that the
        fields in data should be placed into for output.
        
        :param data: a list of dictionaries that represent the data to
           be output.  Each dictionary in the list corresponds to a
           column of output. The keys of the dictionary are the
           lengths of the items to be output, and the value associated
           with a key is the number of items of that length.
        :param columns: a list containing the minimum amount of space
           that must be allocated for each row. This can be used to
           ensure that there is space available in a column if, for
           example, the actual lengths of the items being output
           cannot be given in *data*
        :param remainder_column: number of the column to receive a few
           extra spaces that may remain after other allocation has
           taken place
        :param total_width: the total width of the output.
           self.term.columns is used by default
        :param indent: string that will be prefixed to a line of
           output to create e.g. an indent
        :return: a list of the widths of the columns that the fields
           in data should be placed into for output
        """
        if total_width is None:
            total_width = self.term.columns

        cols = len(data)
        # Convert the data to ascending list of tuples, (field_length, pkgs)
        pdata = data
        data  = [None] * cols # Don't modify the passed in data
        for d in range(0, cols):
            data[d] = sorted(pdata[d].items())

        #  We start allocating 1 char to everything but the last column, and a
        # space between each (again, except for the last column). Because
        # at worst we are better with:
        # |one two three|
        # | four        |
        # ...than:
        # |one two three|
        # |            f|
        # |our          |
        # ...the later being what we get if we pre-allocate the last column, and
        # thus. the space, due to "three" overflowing it's column by 2 chars.
        if columns is None:
            columns = [1] * (cols - 1)
            columns.append(0)

        total_width -= (sum(columns) + (cols - 1) + utf8_width(indent))
        if not columns[-1]:
            total_width += 1
        while total_width > 0:
            # Find which field all the spaces left will help best
            helps = 0
            val   = 0
            for d in xrange(0, cols):
                thelps = self._calc_columns_spaces_helps(columns[d], data[d],
                                                         total_width)
                if not thelps:
                    continue
                #  We prefer to overflow: the last column, and then earlier
                # columns. This is so that in the best case (just overflow the
                # last) ... grep still "works", and then we make it prettier.
                if helps and (d == (cols - 1)) and (thelps / 2) < helps:
                    continue
                if thelps < helps:
                    continue
                helps = thelps
                val   = d

            #  If we found a column to expand, move up to the next level with
            # that column and start again with any remaining space.
            if helps:
                diff = data[val].pop(0)[0] - columns[val]
                if not columns[val] and (val == (cols - 1)):
                    #  If we are going from 0 => N on the last column, take 1
                    # for the space before the column.
                    total_width  -= 1
                columns[val] += diff
                total_width  -= diff
                continue

            overflowed_columns = 0
            for d in xrange(0, cols):
                if not data[d]:
                    continue
                overflowed_columns += 1
            if overflowed_columns:
                #  Split the remaining spaces among each overflowed column
                # equally
                norm = total_width / overflowed_columns
                for d in xrange(0, cols):
                    if not data[d]:
                        continue
                    columns[d] += norm
                    total_width -= norm

            #  Split the remaining spaces among each column equally, except the
            # last one. And put the rest into the remainder column
            cols -= 1
            norm = total_width / cols
            for d in xrange(0, cols):
                columns[d] += norm
            columns[remainder_column] += total_width - (cols * norm)
            total_width = 0

        return columns

    @staticmethod
    def _fmt_column_align_width(width):
        if width < 0:
            return (u"-", -width)
        return (u"", width)

    def _col_data(self, col_data):
        assert len(col_data) == 2 or len(col_data) == 3
        if len(col_data) == 2:
            (val, width) = col_data
            hibeg = hiend = ''
        if len(col_data) == 3:
            (val, width, highlight) = col_data
            (hibeg, hiend) = self._highlight(highlight)
        return (val, width, hibeg, hiend)

    def fmtColumns(self, columns, msg=u'', end=u'', text_width=utf8_width):
        """Return a row of data formatted into a string for output.
        Items can overflow their columns. 

        :param columns: a list of tuples containing the data to
           output.  Each tuple contains first the item to be output,
           then the amount of space allocated for the column, and then
           optionally a type of highlighting for the item
        :param msg: a string to begin the line of output with
        :param end: a string to end the line of output with
        :param text_width: a function to find the width of the items
           in the columns.  This defaults to utf8 but can be changed
           to len() if you know it'll be fine
        :return: a row of data formatted into a string for output
        """
        total_width = len(msg)
        data = []
        for col_data in columns[:-1]:
            (val, width, hibeg, hiend) = self._col_data(col_data)

            if not width: # Don't count this column, invisible text
                msg += u"%s"
                data.append(val)
                continue

            (align, width) = self._fmt_column_align_width(width)
            val_width = text_width(val)
            if val_width <= width:
                #  Don't use utf8_width_fill() because it sucks performance
                # wise for 1,000s of rows. Also allows us to use len(), when
                # we can.
                msg += u"%s%s%s%s "
                if (align == u'-'):
                    data.extend([hibeg, val, " " * (width - val_width), hiend])
                else:
                    data.extend([hibeg, " " * (width - val_width), val, hiend])
            else:
                msg += u"%s%s%s\n" + " " * (total_width + width + 1)
                data.extend([hibeg, val, hiend])
            total_width += width
            total_width += 1
        (val, width, hibeg, hiend) = self._col_data(columns[-1])
        (align, width) = self._fmt_column_align_width(width)
        val = utf8_width_fill(val, width, left=(align == u'-'),
                              prefix=hibeg, suffix=hiend)
        msg += u"%%s%s" % end
        data.append(val)
        return msg % tuple(data)

    def simpleList(self, pkg, ui_overflow=False, indent='', highlight=False,
                   columns=None):
        """Print a package as a line.

        :param pkg: the package to be printed
        :param ui_overflow: unused
        :param indent: string to be prefixed onto the line to provide
           e.g. an indent
        :param highlight: highlighting options for the name of the
           package
        :param colums: tuple containing the space allocated for each
           column of output.  The columns are the package name, version,
           and repository
        """
        if columns is None:
            columns = (-40, -22, -16) # Old default
        ver = pkg.printVer()
        na = '%s%s.%s' % (indent, pkg.name, pkg.arch)
        hi_cols = [highlight, 'normal', 'normal']
        rid = pkg.ui_from_repo
        columns = zip((na, ver, rid), columns, hi_cols)
        print self.fmtColumns(columns, text_width=len)

    def simpleEnvraList(self, pkg, ui_overflow=False,
                        indent='', highlight=False, columns=None):
        """Print a package as a line, with the package itself in envra
        format so it can be passed to list/install/etc. 

        :param pkg: the package to be printed
        :param ui_overflow: unused
        :param indent: string to be prefixed onto the line to provide
           e.g. an indent
        :param highlight: highlighting options for the name of the
           package
        :param colums: tuple containing the space allocated for each
           column of output.  The columns the are the package envra and
           repository
        """
        if columns is None:
            columns = (-63, -16) # Old default
        envra = '%s%s' % (indent, str(pkg))
        hi_cols = [highlight, 'normal', 'normal']
        rid = pkg.ui_from_repo
        columns = zip((envra, rid), columns, hi_cols)
        print self.fmtColumns(columns, text_width=len)

    def fmtKeyValFill(self, key, val):
        """Return a key value pair in the common two column output
        format.

        :param key: the key to be formatted
        :param val: the value associated with *key*
        :return: the key value pair formatted in two columns for output
        """
        val = to_str(val)
        keylen = utf8_width(key)
        cols = self.term.columns
        nxt = ' ' * (keylen - 2) + ': '
        ret = utf8_text_fill(val, width=cols,
                             initial_indent=key, subsequent_indent=nxt)
        if ret.count("\n") > 1 and keylen > (cols / 3):
            # If it's big, redo it again with a smaller subsequent off
            ret = utf8_text_fill(val, width=cols,
                                 initial_indent=key,
                                 subsequent_indent='     ...: ')
        return ret
    
    def fmtSection(self, name, fill='='):
        """Format and return a section header.  The format of the
        header is a line with *name* centred, and *fill* repeated on
        either side to fill an entire line on the terminal.

        :param name: the name of the section
        :param fill: the character to repeat on either side of *name*
          to fill an entire line.  *fill* must be a single character.
        :return: a string formatted to be a section header
        """
        name = to_str(name)
        cols = self.term.columns - 2
        name_len = utf8_width(name)
        if name_len >= (cols - 4):
            beg = end = fill * 2
        else:
            beg = fill * ((cols - name_len) / 2)
            end = fill * (cols - name_len - len(beg))

        return "%s %s %s" % (beg, name, end)

    def _enc(self, s):
        """Get the translated version from specspo and ensure that
        it's actually encoded in UTF-8."""
        s = to_utf8(s)
        if len(s) > 0:
            for d in self.i18ndomains:
                t = gettext.dgettext(d, s)
                if t != s:
                    s = t
                    break
        return to_unicode(s)

    def infoOutput(self, pkg, highlight=False):
        """Print information about the given package.

        :param pkg: the package to print information about 
        :param hightlight: highlighting options for the name of the
           package
        """
        (hibeg, hiend) = self._highlight(highlight)
        print _("Name        : %s%s%s") % (hibeg, to_unicode(pkg.name), hiend)
        print _("Arch        : %s") % to_unicode(pkg.arch)
        if pkg.epoch != "0":
            print _("Epoch       : %s") % to_unicode(pkg.epoch)
        print _("Version     : %s") % to_unicode(pkg.version)
        print _("Release     : %s") % to_unicode(pkg.release)
        print _("Size        : %s") % self.format_number(float(pkg.size))
        print _("Repo        : %s") % to_unicode(pkg.repoid)
        if pkg.repoid == 'installed' and 'from_repo' in pkg.yumdb_info:
            print _("From repo   : %s") % to_unicode(pkg.yumdb_info.from_repo)
        if self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3):
            print _("Committer   : %s") % to_unicode(pkg.committer)
            print _("Committime  : %s") % time.ctime(pkg.committime)
            print _("Buildtime   : %s") % time.ctime(pkg.buildtime)
            if hasattr(pkg, 'installtime'):
                print _("Install time: %s") % time.ctime(pkg.installtime)
            if pkg.repoid == 'installed':
                uid = None
                if 'installed_by' in pkg.yumdb_info:
                    try:
                        uid = int(pkg.yumdb_info.installed_by)
                    except ValueError: # In case int() fails
                        uid = None
                print _("Installed by: %s") % self._pwd_ui_username(uid)
                uid = None
                if 'changed_by' in pkg.yumdb_info:
                    try:
                        uid = int(pkg.yumdb_info.changed_by)
                    except ValueError: # In case int() fails
                        uid = None
                print _("Changed by  : %s") % self._pwd_ui_username(uid)
        print self.fmtKeyValFill(_("Summary     : "), self._enc(pkg.summary))
        if pkg.url:
            print _("URL         : %s") % to_unicode(pkg.url)
        print self.fmtKeyValFill(_("License     : "), to_unicode(pkg.license))
        print self.fmtKeyValFill(_("Description : "),self._enc(pkg.description))
        print ""
    
    def updatesObsoletesList(self, uotup, changetype, columns=None):
        """Print a simple string that explains the relationship
        between the members of an update or obsoletes tuple.

        :param uotup: an update or obsoletes tuple.  The first member
           is the new package, and the second member is the old
           package
        :param changetype: a string indicating what the change between
           the packages is, e.g. 'updates' or 'obsoletes'
        :param columns: a tuple containing information about how to
           format the columns of output.  The absolute value of each
           number in the tuple indicates how much space has been
           allocated for the corresponding column.  If the number is
           negative, the text in the column will be left justified,
           and if it is positive, the text will be right justified.
           The columns of output are the package name, version, and repository
        """
        (changePkg, instPkg) = uotup

        if columns is not None:
            # New style, output all info. for both old/new with old indented
            chi = self.conf.color_update_remote
            if changePkg.repo.id != 'installed' and changePkg.verifyLocalPkg():
                chi = self.conf.color_update_local
            self.simpleList(changePkg, columns=columns, highlight=chi)
            self.simpleList(instPkg,   columns=columns, indent=' ' * 4,
                            highlight=self.conf.color_update_installed)
            return

        # Old style
        c_compact = changePkg.compactPrint()
        i_compact = '%s.%s' % (instPkg.name, instPkg.arch)
        c_repo = changePkg.repoid
        print '%-35.35s [%.12s] %.10s %-20.20s' % (c_compact, c_repo, changetype, i_compact)

    def listPkgs(self, lst, description, outputType, highlight_na={},
                 columns=None, highlight_modes={}):
        """Prints information about the given list of packages.

        :param lst: a list of packages to print information about
        :param description: string describing what the list of
           packages contains, e.g. 'Available Packages'
        :param outputType: The type of information to be printed.
           Current options::
           
              'list' - simple pkg list
              'info' - similar to rpm -qi output
        :param highlight_na: a dictionary containing information about
              packages that should be highlighted in the output.  The
              dictionary keys are (name, arch) tuples for the package,
              and the associated values are the package objects
              themselves.
        :param columns: a tuple containing information about how to
           format the columns of output.  The absolute value of each
           number in the tuple indicates how much space has been
           allocated for the corresponding column.  If the number is
           negative, the text in the column will be left justified,
           and if it is positive, the text will be right justified.
           The columns of output are the package name, version, and
           repository
        :param highlight_modes: dictionary containing information
              about to highlight the packages in *highlight_na*.
              *highlight_modes* should contain the following keys::
                 
                 'not_in' - highlighting used for packages not in *highlight_na*
                 '=' - highlighting used when the package versions are equal
                 '<' - highlighting used when the package has a lower version number
                 '>' - highlighting used when the package has a higher version number
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
        """
        if outputType in ['list', 'info']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print '%s' % description
                for pkg in sorted(lst):
                    key = (pkg.name, pkg.arch)
                    highlight = False
                    if False: pass
                    elif key not in highlight_na:
                        highlight = highlight_modes.get('not in', 'normal')
                    elif pkg.verEQ(highlight_na[key]):
                        highlight = highlight_modes.get('=', 'normal')
                    elif pkg.verLT(highlight_na[key]):
                        highlight = highlight_modes.get('>', 'bold')
                    else:
                        highlight = highlight_modes.get('<', 'normal')

                    if outputType == 'list':
                        self.simpleList(pkg, ui_overflow=True,
                                        highlight=highlight, columns=columns)
                    elif outputType == 'info':
                        self.infoOutput(pkg, highlight=highlight)
                    else:
                        pass
    
            if thingslisted == 0:
                return 1, ['No Packages to list']
            return 0, []
        
    
        
    def userconfirm(self):
        """Get a yes or no from the user, and default to No

        :return: True if the user selects yes, and False if the user
           selects no
        """
        yui = (to_unicode(_('y')), to_unicode(_('yes')))
        nui = (to_unicode(_('n')), to_unicode(_('no')))
        aui = (yui[0], yui[1], nui[0], nui[1])
        while True:
            try:
                choice = raw_input(_('Is this ok [y/N]: '))
            except UnicodeEncodeError:
                raise
            except UnicodeDecodeError:
                raise
            except:
                choice = ''
            choice = to_unicode(choice)
            choice = choice.lower()
            if len(choice) == 0 or choice in aui:
                break
            # If the enlish one letter names don't mix, allow them too
            if u'y' not in aui and u'y' == choice:
                choice = yui[0]
                break
            if u'n' not in aui and u'n' == choice:
                break

        if len(choice) == 0 or choice not in yui:
            return False
        else:            
            return True
    
    def _cli_confirm_gpg_key_import(self, keydict):
        # FIXME what should we be printing here?
        return self.userconfirm()

    def _group_names2aipkgs(self, pkg_names):
        """ Convert pkg_names to installed pkgs or available pkgs, return
            value is a dict on pkg.name returning (apkg, ipkg). """
        ipkgs = self.rpmdb.searchNames(pkg_names)
        apkgs = self.pkgSack.searchNames(pkg_names)
        apkgs = packagesNewestByNameArch(apkgs)

        # This is somewhat similar to doPackageLists()
        pkgs = {}
        for pkg in ipkgs:
            pkgs[(pkg.name, pkg.arch)] = (None, pkg)
        for pkg in apkgs:
            key = (pkg.name, pkg.arch)
            if key not in pkgs:
                pkgs[(pkg.name, pkg.arch)] = (pkg, None)
            elif pkg.verGT(pkgs[key][1]):
                pkgs[(pkg.name, pkg.arch)] = (pkg, pkgs[key][1])

        # Convert (pkg.name, pkg.arch) to pkg.name dict
        ret = {}
        for (apkg, ipkg) in pkgs.itervalues():
            pkg = apkg or ipkg
            ret.setdefault(pkg.name, []).append((apkg, ipkg))
        return ret

    def _calcDataPkgColumns(self, data, pkg_names, pkg_names2pkgs,
                            indent='   '):
        for item in pkg_names:
            if item not in pkg_names2pkgs:
                continue
            for (apkg, ipkg) in pkg_names2pkgs[item]:
                pkg = ipkg or apkg
                envra = utf8_width(str(pkg)) + utf8_width(indent)
                rid = len(pkg.ui_from_repo)
                for (d, v) in (('envra', envra), ('rid', rid)):
                    data[d].setdefault(v, 0)
                    data[d][v] += 1

    def _displayPkgsFromNames(self, pkg_names, verbose, pkg_names2pkgs,
                              indent='   ', columns=None):
        if not verbose:
            for item in sorted(pkg_names):
                print '%s%s' % (indent, item)
        else:
            for item in sorted(pkg_names):
                if item not in pkg_names2pkgs:
                    print '%s%s' % (indent, item)
                    continue
                for (apkg, ipkg) in sorted(pkg_names2pkgs[item],
                                           key=lambda x: x[1] or x[0]):
                    if ipkg and apkg:
                        highlight = self.conf.color_list_installed_older
                    elif apkg:
                        highlight = self.conf.color_list_available_install
                    else:
                        highlight = False
                    self.simpleEnvraList(ipkg or apkg, ui_overflow=True,
                                         indent=indent, highlight=highlight,
                                         columns=columns)
    
    def displayPkgsInGroups(self, group):
        """Output information about the packages in a given group
        
        :param group: a Group object to output information about
        """
        print _('\nGroup: %s') % group.ui_name

        verb = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if verb:
            print _(' Group-Id: %s') % to_unicode(group.groupid)
        pkg_names2pkgs = None
        if verb:
            pkg_names2pkgs = self._group_names2aipkgs(group.packages)
        if group.ui_description:
            print _(' Description: %s') % to_unicode(group.ui_description)
        if group.langonly:
            print _(' Language: %s') % group.langonly

        sections = ((_(' Mandatory Packages:'),   group.mandatory_packages),
                    (_(' Default Packages:'),     group.default_packages),
                    (_(' Optional Packages:'),    group.optional_packages),
                    (_(' Conditional Packages:'), group.conditional_packages))
        columns = None
        if verb:
            data = {'envra' : {}, 'rid' : {}}
            for (section_name, pkg_names) in sections:
                self._calcDataPkgColumns(data, pkg_names, pkg_names2pkgs)
            data = [data['envra'], data['rid']]
            columns = self.calcColumns(data)
            columns = (-columns[0], -columns[1])

        for (section_name, pkg_names) in sections:
            if len(pkg_names) > 0:
                print section_name
                self._displayPkgsFromNames(pkg_names, verb, pkg_names2pkgs,
                                           columns=columns)

    def depListOutput(self, results):
        """Format and output a list of findDeps results

        :param results: a list of package dependency information as
           returned by findDeps
        """
        verb = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        for pkg in sorted(results):
            print _("package: %s") % pkg.compactPrint()
            if len(results[pkg]) == 0:
                print _("  No dependencies for this package")
                continue

            for req in sorted(results[pkg]):
                reqlist = results[pkg][req] 
                print _("  dependency: %s") % prco_tuple_to_string(req)
                if not reqlist:
                    print _("   Unsatisfied dependency")
                    continue
                
                seen = {}
                for po in reversed(sorted(reqlist)):
                    key = (po.name, po.arch)
                    if not verb and key in seen:
                        continue
                    seen[key] = po
                    print "   provider: %s" % po.compactPrint()

    def format_number(self, number, SI=0, space=' '):
        """Return a human-readable metric-like string representation
        of a number.

        :param number: the number to be converted to a human-readable form
        :param SI: If is 0, this function will use the convention
           that 1 kilobyte = 1024 bytes, otherwise, the convention
           that 1 kilobyte = 1000 bytes will be used
        :param space: string that will be placed between the number
           and the SI prefix
        :return: a human-readable metric-like string representation of
           *number*
        """
        symbols = [ ' ', # (none)
                    'k', # kilo
                    'M', # mega
                    'G', # giga
                    'T', # tera
                    'P', # peta
                    'E', # exa
                    'Z', # zetta
                    'Y'] # yotta
    
        if SI: step = 1000.0
        else: step = 1024.0
    
        thresh = 999
        depth = 0
        max_depth = len(symbols) - 1
    
        # we want numbers between 0 and thresh, but don't exceed the length
        # of our list.  In that event, the formatting will be screwed up,
        # but it'll still show the right number.
        while number > thresh and depth < max_depth:
            depth  = depth + 1
            number = number / step
    
        if type(number) == type(1) or type(number) == type(1L):
            format = '%i%s%s'
        elif number < 9.95:
            # must use 9.95 for proper sizing.  For example, 9.99 will be
            # rounded to 10.0 with the .1f format string (which is too long)
            format = '%.1f%s%s'
        else:
            format = '%.0f%s%s'
    
        return(format % (float(number or 0), space, symbols[depth]))

    @staticmethod
    def format_time(seconds, use_hours=0):
        """Return a human-readable string representation of a number
        of seconds.  The string will show seconds, minutes, and
        optionally hours.

        :param seconds: the number of seconds to convert to a
           human-readable form
        :param use_hours: If use_hours is 0, the representation will
           be in minutes and seconds. Otherwise, it will be in hours,
           minutes, and seconds
        :return: a human-readable string representation of *seconds*
        """
        return urlgrabber.progress.format_time(seconds, use_hours)

    def matchcallback(self, po, values, matchfor=None, verbose=None,
                      highlight=None):
        """Output search/provides type callback matches.

        :param po: the package object that matched the search
        :param values: the information associated with *po* that
           matched the search
        :param matchfor: a list of strings to be highlighted in the
           output
        :param verbose: whether to output extra verbose information
        :param highlight: highlighting options for the highlighted matches
        """
        if self.conf.showdupesfromrepos:
            msg = '%s : ' % po
        else:
            msg = '%s.%s : ' % (po.name, po.arch)
        msg = self.fmtKeyValFill(msg, self._enc(po.summary))
        if matchfor:
            if highlight is None:
                highlight = self.conf.color_search_match
            msg = self._sub_highlight(msg, highlight, matchfor,ignore_case=True)
        
        print msg

        if verbose is None:
            verbose = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if not verbose:
            return

        print _("Repo        : %s") % po.ui_from_repo
        done = False
        for item in yum.misc.unique(values):
            item = to_utf8(item)
            if to_utf8(po.name) == item or to_utf8(po.summary) == item:
                continue # Skip double name/summary printing

            if not done:
                print _('Matched from:')
                done = True
            can_overflow = True
            if False: pass
            elif to_utf8(po.description) == item:
                key = _("Description : ")
                item = self._enc(item)
            elif to_utf8(po.url) == item:
                key = _("URL         : %s")
                can_overflow = False
            elif to_utf8(po.license) == item:
                key = _("License     : %s")
                can_overflow = False
            elif item.startswith("/"):
                key = _("Filename    : %s")
                item = self._enc(item)
                can_overflow = False
            else:
                key = _("Other       : ")

            if matchfor:
                item = self._sub_highlight(item, highlight, matchfor,
                                           ignore_case=True)
            if can_overflow:
                print self.fmtKeyValFill(key, to_unicode(item))
            else:
                print key % item
        print '\n\n'

    def matchcallback_verbose(self, po, values, matchfor=None):
        """Output search/provides type callback matches.  This will
        output more information than :func:`matchcallback`.

        :param po: the package object that matched the search
        :param values: the information associated with *po* that
           matched the search
        :param matchfor: a list of strings to be highlighted in the
           output
        """
        return self.matchcallback(po, values, matchfor, verbose=True)
        
    def reportDownloadSize(self, packages, installonly=False):
        """Report the total download size for a set of packages
        
        :param packages: a list of package objects
        :param installonly: whether the transaction consists only of installations
        """
        totsize = 0
        locsize = 0
        insize  = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = int(pkg.size)
                totsize += size
                try:
                    if pkg.verifyLocalPkg():
                        locsize += size
                except:
                    pass

                if not installonly:
                    continue

                try:
                    size = int(pkg.installedsize)
                except:
                    pass
                insize += size
            except:
                error = True
                self.logger.error(_('There was an error calculating total download size'))
                break

        if (not error):
            if locsize:
                self.verbose_logger.log(logginglevels.INFO_1, _("Total size: %s"), 
                                        self.format_number(totsize))
            if locsize != totsize:
                self.verbose_logger.log(logginglevels.INFO_1, _("Total download size: %s"), 
                                        self.format_number(totsize - locsize))
            if installonly:
                self.verbose_logger.log(logginglevels.INFO_1,
                                        _("Installed size: %s"),
                                        self.format_number(insize))

    def reportRemoveSize(self, packages):
        """Report the total size of packages being removed.

        :param packages: a list of package objects
        """
        totsize = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = int(pkg.size)
                totsize += size
            except:
                error = True
                self.logger.error(_('There was an error calculating installed size'))
                break
        if (not error):
            self.verbose_logger.log(logginglevels.INFO_1,
                                    _("Installed size: %s"),
                                    self.format_number(totsize))
            
    def listTransaction(self):
        """Return a string representation of the transaction in an
        easy-to-read format.
        """
        self.tsInfo.makelists(True, True)
        pkglist_lines = []
        data  = {'n' : {}, 'v' : {}, 'r' : {}}
        a_wid = 0 # Arch can't get "that big" ... so always use the max.

        def _add_line(lines, data, a_wid, po, obsoletes=[]):
            (n,a,e,v,r) = po.pkgtup
            evr = po.printVer()
            repoid = po.ui_from_repo
            pkgsize = float(po.size)
            size = self.format_number(pkgsize)

            if a is None: # gpgkeys are weird
                a = 'noarch'

            # none, partial, full?
            if po.repo.id == 'installed':
                hi = self.conf.color_update_installed
            elif po.verifyLocalPkg():
                hi = self.conf.color_update_local
            else:
                hi = self.conf.color_update_remote
            lines.append((n, a, evr, repoid, size, obsoletes, hi))
            #  Create a dict of field_length => number of packages, for
            # each field.
            for (d, v) in (("n",len(n)), ("v",len(evr)), ("r",len(repoid))):
                data[d].setdefault(v, 0)
                data[d][v] += 1
            if a_wid < len(a): # max() is only in 2.5.z
                a_wid = len(a)
            return a_wid

        for (action, pkglist) in [(_('Installing'), self.tsInfo.installed),
                            (_('Updating'), self.tsInfo.updated),
                            (_('Removing'), self.tsInfo.removed),
                            (_('Reinstalling'), self.tsInfo.reinstalled),
                            (_('Downgrading'), self.tsInfo.downgraded),
                            (_('Installing for dependencies'), self.tsInfo.depinstalled),
                            (_('Updating for dependencies'), self.tsInfo.depupdated),
                            (_('Removing for dependencies'), self.tsInfo.depremoved)]:
            lines = []
            for txmbr in pkglist:
                a_wid = _add_line(lines, data, a_wid, txmbr.po, txmbr.obsoletes)

            pkglist_lines.append((action, lines))

        for (action, pkglist) in [(_('Skipped (dependency problems)'),
                                   self.skipped_packages),
                                  (_('Not installed'), self._not_found_i.values()),
                                  (_('Not available'), self._not_found_a.values())]:
            lines = []
            for po in pkglist:
                a_wid = _add_line(lines, data, a_wid, po)

            pkglist_lines.append((action, lines))

        if not data['n']:
            return u''
        else:
            data    = [data['n'],    {}, data['v'], data['r'], {}]
            columns = [1,         a_wid,         1,         1,  5]
            columns = self.calcColumns(data, indent="  ", columns=columns,
                                       remainder_column=2)
            (n_wid, a_wid, v_wid, r_wid, s_wid) = columns
            assert s_wid == 5

            out = [u"""
%s
%s
%s
""" % ('=' * self.term.columns,
       self.fmtColumns(((_('Package'), -n_wid), (_('Arch'), -a_wid),
                        (_('Version'), -v_wid), (_('Repository'), -r_wid),
                        (_('Size'), s_wid)), u" "),
       '=' * self.term.columns)]

        for (action, lines) in pkglist_lines:
            if lines:
                totalmsg = u"%s:\n" % action
            for (n, a, evr, repoid, size, obsoletes, hi) in lines:
                columns = ((n,   -n_wid, hi), (a,      -a_wid),
                           (evr, -v_wid), (repoid, -r_wid), (size, s_wid))
                msg = self.fmtColumns(columns, u" ", u"\n")
                hibeg, hiend = self._highlight(self.conf.color_update_installed)
                for obspo in sorted(obsoletes):
                    appended = _('     replacing  %s%s%s.%s %s\n')
                    appended %= (hibeg, obspo.name, hiend,
                                 obspo.arch, obspo.printVer())
                    msg = msg+appended
                totalmsg = totalmsg + msg
        
            if lines:
                out.append(totalmsg)

        out.append(_("""
Transaction Summary
%s
""") % ('=' * self.term.columns))
        for action, count in (
            (_('Install'), len(self.tsInfo.installed) + len(self.tsInfo.depinstalled)),
            (_('Upgrade'), len(self.tsInfo.updated) + len(self.tsInfo.depupdated)),
            (_('Remove'), len(self.tsInfo.removed) + len(self.tsInfo.depremoved)),
            (_('Reinstall'), len(self.tsInfo.reinstalled)),
            (_('Downgrade'), len(self.tsInfo.downgraded)),
        ):
            if count: out.append('%-9s %5d %s\n' % (
                action, count, P_('Package', 'Packages', count),
            ))
        return ''.join(out)
        
    def postTransactionOutput(self):
        """Returns a human-readable summary of the results of the
        transaction.
        
        :return: a string containing a human-readable summary of the
           results of the transaction
        """
        out = ''
        
        self.tsInfo.makelists()

        #  Works a bit like calcColumns, but we never overflow a column we just
        # have a dynamic number of columns.
        def _fits_in_cols(msgs, num):
            """ Work out how many columns we can use to display stuff, in
                the post trans output. """
            if len(msgs) < num:
                return []

            left = self.term.columns - ((num - 1) + 2)
            if left <= 0:
                return []

            col_lens = [0] * num
            col = 0
            for msg in msgs:
                if len(msg) > col_lens[col]:
                    diff = (len(msg) - col_lens[col])
                    if left <= diff:
                        return []
                    left -= diff
                    col_lens[col] = len(msg)
                col += 1
                col %= len(col_lens)

            for col in range(len(col_lens)):
                col_lens[col] += left / num
                col_lens[col] *= -1
            return col_lens

        for (action, pkglist) in [(_('Removed'), self.tsInfo.removed), 
                                  (_('Dependency Removed'), self.tsInfo.depremoved),
                                  (_('Installed'), self.tsInfo.installed), 
                                  (_('Dependency Installed'), self.tsInfo.depinstalled),
                                  (_('Updated'), self.tsInfo.updated),
                                  (_('Dependency Updated'), self.tsInfo.depupdated),
                                  (_('Skipped (dependency problems)'), self.skipped_packages),
                                  (_('Replaced'), self.tsInfo.obsoleted),
                                  (_('Failed'), self.tsInfo.failed)]:
            msgs = []
            if len(pkglist) > 0:
                out += '\n%s:\n' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg = "%s.%s %s:%s-%s" % (n,a,e,v,r)
                    msgs.append(msg)
                for num in (8, 7, 6, 5, 4, 3, 2):
                    cols = _fits_in_cols(msgs, num)
                    if cols:
                        break
                if not cols:
                    cols = [-(self.term.columns - 2)]
                while msgs:
                    current_msgs = msgs[:len(cols)]
                    out += '  '
                    out += self.fmtColumns(zip(current_msgs, cols), end=u'\n')
                    msgs = msgs[len(cols):]

        return out

    def setupProgressCallbacks(self):
        """Set up the progress callbacks and various 
           output bars based on debug level.
        """
        # if we're below 2 on the debug level we don't need to be outputting
        # progress bars - this is hacky - I'm open to other options
        # One of these is a download
        if self.conf.debuglevel < 2 or not sys.stdout.isatty():
            progressbar = None
            callback = None
        else:
            progressbar = YumTextMeter(fo=sys.stdout)
            callback = CacheProgressCallback()

        # setup our failure report for failover
        freport = (self.failureReport,(),{})
        failure_callback = freport

        # setup callback for CTRL-C's
        interrupt_callback = self.interrupt_callback
        if hasattr(self, 'prerepoconf'):
            self.prerepoconf.progressbar = progressbar
            self.prerepoconf.callback = callback
            self.prerepoconf.failure_callback = failure_callback
            self.prerepoconf.interrupt_callback = interrupt_callback
        else:
            #  Just in case some API user decides to do self.repos before
            # calling us.
            self.repos.setProgressBar(progressbar)
            self.repos.callback = callback
            self.repos.setFailureCallback(failure_callback)
            self.repos.setInterruptCallback(interrupt_callback)

        # setup our depsolve progress callback
        dscb = DepSolveProgressCallBack(weakref(self))
        self.dsCallback = dscb
    
    def setupProgessCallbacks(self):
        """This function is for API purposes only to protect the typo."""
        self.setupProgressCallbacks()
    
    def setupKeyImportCallbacks(self):
        """Set up callbacks to import and confirm gpg public keys."""

        confirm_func = self._cli_confirm_gpg_key_import
        gpg_import_func = self.getKeyForRepo
        gpgca_import_func = self.getCAKeyForRepo
        if hasattr(self, 'prerepoconf'):
            self.prerepoconf.confirm_func = confirm_func
            self.prerepoconf.gpg_import_func = gpg_import_func
            self.prerepoconf.gpgca_import_func = gpgca_import_func
        else:
            self.repos.confirm_func = confirm_func
            self.repos.gpg_import_func = gpg_import_func
            self.repos.gpgca_import_func = gpgca_import_func

    def interrupt_callback(self, cbobj):
        '''Handle CTRL-C's during downloads.  If a CTRL-C occurs a
        URLGrabError will be raised to push the download onto the next
        mirror.  If two CTRL-C's occur in quick succession then yum
        will exit.

        :param cbobj: :class:`urlgrabber.grabber.CallbackObject`
        '''
        delta_exit_chk = 2.0      # Delta between C-c's so we treat as exit
        delta_exit_str = _("two") # Human readable version of above

        now = time.time()

        if not self._last_interrupt:
            hibeg = self.term.MODE['bold']
            hiend = self.term.MODE['normal']
            # For translators: This is output like:
#  Current download cancelled, interrupt (ctrl-c) again within two seconds
# to exit.
            # Where "interupt (ctrl-c) again" and "two" are highlighted.
            msg = _("""
 Current download cancelled, %sinterrupt (ctrl-c) again%s within %s%s%s seconds
to exit.
""") % (hibeg, hiend, hibeg, delta_exit_str, hiend)
            self.verbose_logger.log(logginglevels.INFO_2, msg)
        elif now - self._last_interrupt < delta_exit_chk:
            # Two quick CTRL-C's, quit
            raise KeyboardInterrupt

        # Go to next mirror
        self._last_interrupt = now
        raise URLGrabError(15, _('user interrupt'))

    def download_callback_total_cb(self, remote_pkgs, remote_size,
                                   download_start_timestamp):
        """Outputs summary information about the download process.

        :param remote_pkgs: a list of package objects that were downloaded
        :param remote_size: the total amount of information that was
           downloaded, in bytes
        :param download_start_timestamp: the time when the download
           process started, in seconds since the epoch
        """
        if len(remote_pkgs) <= 1:
            return
        if not hasattr(urlgrabber.progress, 'TerminalLine'):
            return

        tl = urlgrabber.progress.TerminalLine(8)
        self.verbose_logger.log(logginglevels.INFO_2, "-" * tl.rest())
        dl_time = time.time() - download_start_timestamp
        if dl_time <= 0: # This stops divide by zero, among other problems
            dl_time = 0.01
        ui_size = tl.add(' | %5sB' % self.format_number(remote_size))
        ui_time = tl.add(' %9s' % self.format_time(dl_time))
        ui_end  = tl.add(' ' * 5)
        ui_bs   = tl.add(' %5sB/s' % self.format_number(remote_size / dl_time))
        msg = "%s%s%s%s%s" % (utf8_width_fill(_("Total"), tl.rest(), tl.rest()),
                              ui_bs, ui_size, ui_time, ui_end)
        self.verbose_logger.log(logginglevels.INFO_2, msg)

    def _history_uiactions(self, hpkgs):
        actions = set()
        count = 0
        for hpkg in hpkgs:
            st = hpkg.state
            if st == 'True-Install':
                st = 'Install'
            if st == 'Dep-Install': # Mask these at the higher levels
                st = 'Install'
            if st == 'Obsoleted': #  This is just a UI tweak, as we can't have
                                  # just one but we need to count them all.
                st = 'Obsoleting'
            if st in ('Install', 'Update', 'Erase', 'Reinstall', 'Downgrade',
                      'Obsoleting'):
                actions.add(st)
                count += 1
        assert len(actions) <= 6
        if len(actions) > 1:
            large2small = {'Install'      : _('I'),
                           'Obsoleting'   : _('O'),
                           'Erase'        : _('E'),
                           'Reinstall'    : _('R'),
                           'Downgrade'    : _('D'),
                           'Update'       : _('U'),
                           }
            return count, ", ".join([large2small[x] for x in sorted(actions)])

        # So empty transactions work, although that "shouldn't" really happen
        return count, "".join(list(actions))

    def _pwd_ui_username(self, uid, limit=None):
        if type(uid) == type([]):
            return [self._pwd_ui_username(u, limit) for u in uid]

        # loginuid is set to      -1 (0xFFFF_FFFF) on init, in newer kernels.
        # loginuid is set to INT_MAX (0x7FFF_FFFF) on init, in older kernels.
        if uid is None or uid in (0xFFFFFFFF, 0x7FFFFFFF):
            loginid = _("<unset>")
            name = _("System") + " " + loginid
            if limit is not None and len(name) > limit:
                name = loginid
            return to_unicode(name)

        def _safe_split_0(text, *args):
            """ Split gives us a [0] for everything _but_ '', this function
                returns '' in that case. """
            ret = text.split(*args)
            if not ret:
                return ''
            return ret[0]

        try:
            user = pwd.getpwuid(uid)
            fullname = _safe_split_0(user.pw_gecos, ';', 2)
            name = "%s <%s>" % (fullname, user.pw_name)
            if limit is not None and len(name) > limit:
                name = "%s ... <%s>" % (_safe_split_0(fullname), user.pw_name)
                if len(name) > limit:
                    name = "<%s>" % user.pw_name
            return to_unicode(name)
        except KeyError:
            return to_unicode(str(uid))

    @staticmethod
    def _historyRangeRTIDs(old, tid):
        ''' Convert a user "TID" string of 2..4 into: (2, 4). '''
        def str2int(x):
            try:
                if x == 'last' or x.startswith('last-'):
                    tid = old.tid
                    if x.startswith('last-'):
                        off = int(x[len('last-'):])
                        if off <= 0:
                            int("z")
                        tid -= off
                    return tid
                return int(x)
            except ValueError:
                return None

        if '..' not in tid:
            return None
        btid, etid = tid.split('..', 2)
        btid = str2int(btid)
        if btid > old.tid:
            return None
        elif btid <= 0:
            return None
        etid = str2int(etid)
        if etid > old.tid:
            return None

        if btid is None or etid is None:
            return None

        # Have a range ... do a "merged" transaction.
        if btid > etid:
            btid, etid = etid, btid
        return (btid, etid)

    def _historyRangeTIDs(self, rtids):
        ''' Convert a list of ranged tid typles into all the tids needed, Eg.
            [(2,4), (6,8)] == [2, 3, 4, 6, 7, 8]. '''
        tids = set()
        last_end = -1 # This just makes displaying it easier...
        for mtid in sorted(rtids):
            if mtid[0] < last_end:
                self.logger.warn(_('Skipping merged transaction %d to %d, as it overlaps' % (mtid[0], mtid[1])))
                continue # Don't do overlapping
            last_end = mtid[1]
            for num in range(mtid[0], mtid[1] + 1):
                tids.add(num)
        return tids

    def _history_list_transactions(self, extcmds):
        old = self.history.last()
        if old is None:
            self.logger.critical(_('No transactions'))
            return None, None

        tids = set()
        pats = []
        usertids = extcmds[1:]
        printall = False
        if usertids:
            printall = True
            if usertids[0] == 'all':
                usertids.pop(0)
        for tid in usertids:
            try:
                int(tid)
                tids.add(tid)
            except ValueError:
                rtid = self._historyRangeRTIDs(old, tid)
                if rtid:
                    tids.update(self._historyRangeTIDs([rtid]))
                    continue
                pats.append(tid)
        if pats:
            tids.update(self.history.search(pats))

        if not tids and usertids:
            self.logger.critical(_('Bad transaction IDs, or package(s), given'))
            return None, None
        return tids, printall

    def historyListCmd(self, extcmds):
        """Output a list of information about the history of yum
        transactions.

        :param extcmds: list of extra command line arguments
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
        """
        tids, printall = self._history_list_transactions(extcmds)
        if tids is None:
            return 1, ['Failed history list']

        limit = 20
        if printall:
            limit = None

        old_tids = self.history.old(tids, limit=limit)
        done = 0
        if self.conf.history_list_view == 'users':
            uids = [1,2]
        elif self.conf.history_list_view == 'commands':
            uids = [1]
        else:
            assert self.conf.history_list_view == 'single-user-commands'
            uids = set()
            blanks = 0
            for old in old_tids:
                if not printall and done >= limit:
                    break

                done += 1
                if old.cmdline is None:
                    blanks += 1
                uids.add(old.loginuid)
            if len(uids) == 1 and blanks > (done / 2):
                uids.add('blah')

        fmt = "%s | %s | %s | %s | %s"
        if len(uids) == 1:
            name = _("Command line")
        else:
            name = _("Login user")
        print fmt % (utf8_width_fill(_("ID"), 6, 6),
                     utf8_width_fill(name, 24, 24),
                     utf8_width_fill(_("Date and time"), 16, 16),
                     utf8_width_fill(_("Action(s)"), 14, 14),
                     utf8_width_fill(_("Altered"), 7, 7))
        print "-" * 79
        fmt = "%6u | %s | %-16.16s | %s | %4u"
        done = 0
        for old in old_tids:
            if not printall and done >= limit:
                break

            done += 1
            if len(uids) == 1:
                name = old.cmdline or ''
            else:
                name = self._pwd_ui_username(old.loginuid, 24)
            tm = time.strftime("%Y-%m-%d %H:%M",
                               time.localtime(old.beg_timestamp))
            num, uiacts = self._history_uiactions(old.trans_data)
            name   = utf8_width_fill(name,   24, 24)
            uiacts = utf8_width_fill(uiacts, 14, 14)
            rmark = lmark = ' '
            if old.return_code is None:
                rmark = lmark = '*'
            elif old.return_code:
                rmark = lmark = '#'
                # We don't check .errors, because return_code will be non-0
            elif old.output:
                rmark = lmark = 'E'
            elif old.rpmdb_problems:
                rmark = lmark = 'P'
            elif old.trans_skip:
                rmark = lmark = 's'
            if old.altered_lt_rpmdb:
                rmark = '<'
            if old.altered_gt_rpmdb:
                lmark = '>'
            print fmt % (old.tid, name, tm, uiacts, num), "%s%s" % (lmark,rmark)
        lastdbv = self.history.last()
        if lastdbv is None:
            self._rpmdb_warn_checks(warn=False)
        else:
            #  If this is the last transaction, is good and it doesn't
            # match the current rpmdb ... then mark it as bad.
            rpmdbv  = self.rpmdb.simpleVersion(main_only=True)[0]
            if lastdbv.end_rpmdbversion != rpmdbv:
                self._rpmdb_warn_checks()

    def _history_get_transactions(self, extcmds):
        if len(extcmds) < 2:
            self.logger.critical(_('No transaction ID given'))
            return None

        tids = []
        last = None
        for extcmd in extcmds[1:]:
            try:
                if extcmd == 'last' or extcmd.startswith('last-'):
                    if last is None:
                        cto = False
                        last = self.history.last(complete_transactions_only=cto)
                        if last is None:
                            int("z")
                    tid = last.tid
                    if extcmd.startswith('last-'):
                        off = int(extcmd[len('last-'):])
                        if off <= 0:
                            int("z")
                        tid -= off
                    tids.append(str(tid))
                    continue

                if int(extcmd) <= 0:
                    int("z")
                tids.append(extcmd)
            except ValueError:
                self.logger.critical(_('Bad transaction ID given'))
                return None

        old = self.history.old(tids)
        if not old:
            self.logger.critical(_('Not found given transaction ID'))
            return None
        return old
    def _history_get_transaction(self, extcmds):
        old = self._history_get_transactions(extcmds)
        if old is None:
            return None
        if len(old) > 1:
            self.logger.critical(_('Found more than one transaction ID!'))
        return old[0]

    def historyInfoCmd(self, extcmds):
        """Output information about a transaction in history

        :param extcmds: list of extra command line arguments
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
        """
        def str2int(x):
            try:
                return int(x)
            except ValueError:
                return None

        tids = set()
        mtids = set()
        pats = []
        old = self.history.last()
        if old is None:
            self.logger.critical(_('No transactions'))
            return 1, ['Failed history info']

        for tid in extcmds[1:]:
            if self._historyRangeRTIDs(old, tid):
                # Have a range ... do a "merged" transaction.
                mtids.add(self._historyRangeRTIDs(old, tid))
                continue
            elif str2int(tid) is not None:
                tids.add(str2int(tid))
                continue
            pats.append(tid)
        if pats:
            tids.update(self.history.search(pats))
        utids = tids.copy()
        if mtids:
            mtids = sorted(mtids)
            tids.update(self._historyRangeTIDs(mtids))

        if not tids and len(extcmds) < 2:
            old = self.history.last(complete_transactions_only=False)
            if old is not None:
                tids.add(old.tid)
                utids.add(old.tid)

        if not tids:
            self.logger.critical(_('No transaction ID, or package, given'))
            return 1, ['Failed history info']

        lastdbv = self.history.last()
        if lastdbv is not None:
            lasttid = lastdbv.tid
            lastdbv = lastdbv.end_rpmdbversion

        done = False
        bmtid, emtid = -1, -1
        mobj = None
        if mtids:
            bmtid, emtid = mtids.pop(0)
        for tid in self.history.old(tids):
            if lastdbv is not None and tid.tid == lasttid:
                #  If this is the last transaction, is good and it doesn't
                # match the current rpmdb ... then mark it as bad.
                rpmdbv  = self.rpmdb.simpleVersion(main_only=True)[0]
                if lastdbv != rpmdbv:
                    tid.altered_gt_rpmdb = True
            lastdbv = None

            if tid.tid >= bmtid and tid.tid <= emtid:
                if mobj is None:
                    mobj = yum.history.YumMergedHistoryTransaction(tid)
                else:
                    mobj.merge(tid)
            elif mobj is not None:
                if done:
                    print "-" * 79
                done = True

                self._historyInfoCmd(mobj)
                mobj = None
                if mtids:
                    bmtid, emtid = mtids.pop(0)
                    if tid.tid >= bmtid and tid.tid <= emtid:
                        mobj = yum.history.YumMergedHistoryTransaction(tid)

            if tid.tid in utids:
                if done:
                    print "-" * 79
                done = True

                self._historyInfoCmd(tid, pats)

        if mobj is not None:
            if done:
                print "-" * 79

            self._historyInfoCmd(mobj)

    def _hpkg2from_repo(self, hpkg):
        """ Given a pkg, find the ipkg.ui_from_repo ... if none, then
            get an apkg. ... and put a ? in there. """
        if 'from_repo' in hpkg.yumdb_info:
            return hpkg.ui_from_repo

        ipkgs = self.rpmdb.searchPkgTuple(hpkg.pkgtup)
        if not ipkgs:
            apkgs = self.pkgSack.searchPkgTuple(hpkg.pkgtup)
            if not apkgs:
                return '?'
            return '@?' + str(apkgs[0].repoid)

        return ipkgs[0].ui_from_repo

    def _historyInfoCmd(self, old, pats=[]):
        name = self._pwd_ui_username(old.loginuid)

        _pkg_states_installed = {'i' : _('Installed'), 'e' : _('Erased'),
                                 'o' : _('Updated'), 'n' : _('Downgraded')}
        _pkg_states_available = {'i' : _('Installed'), 'e' : _('Not installed'),
                                 'o' : _('Older'), 'n' : _('Newer')}
        # max() only in 2.5.z
        maxlen = sorted([len(x) for x in (_pkg_states_installed.values() +
                                          _pkg_states_available.values())])[-1]
        _pkg_states_installed['maxlen'] = maxlen
        _pkg_states_available['maxlen'] = maxlen
        def _simple_pkg(pkg, prefix_len, was_installed=False, highlight=False,
                        pkg_max_len=0):
            prefix = " " * prefix_len
            if was_installed:
                _pkg_states = _pkg_states_installed
            else:
                _pkg_states = _pkg_states_available
            state  = _pkg_states['i']
            ipkgs = self.rpmdb.searchNames([hpkg.name])
            ipkgs.sort()
            if not ipkgs:
                state  = _pkg_states['e']
            elif hpkg.pkgtup in (ipkg.pkgtup for ipkg in ipkgs):
                pass
            elif ipkgs[-1] > hpkg:
                state  = _pkg_states['o']
            elif ipkgs[0] < hpkg:
                state  = _pkg_states['n']
            else:
                assert False, "Impossible, installed not newer and not older"
            if highlight:
                (hibeg, hiend) = self._highlight('bold')
            else:
                (hibeg, hiend) = self._highlight('normal')
            state = utf8_width_fill(state, _pkg_states['maxlen'])
            print "%s%s%s%s %-*s %s" % (prefix, hibeg, state, hiend,
                                        pkg_max_len, hpkg,
                                        self._hpkg2from_repo(hpkg))

        if type(old.tid) == type([]):
            print _("Transaction ID :"), "%u..%u" % (old.tid[0], old.tid[-1])
        else:
            print _("Transaction ID :"), old.tid
        begtm = time.ctime(old.beg_timestamp)
        print _("Begin time     :"), begtm
        if old.beg_rpmdbversion is not None:
            if old.altered_lt_rpmdb:
                print _("Begin rpmdb    :"), old.beg_rpmdbversion, "**"
            else:
                print _("Begin rpmdb    :"), old.beg_rpmdbversion
        if old.end_timestamp is not None:
            endtm = time.ctime(old.end_timestamp)
            endtms = endtm.split()
            if begtm.startswith(endtms[0]): # Chop uninteresting prefix
                begtms = begtm.split()
                sofar = 0
                for i in range(len(endtms)):
                    if i > len(begtms):
                        break
                    if begtms[i] != endtms[i]:
                        break
                    sofar += len(begtms[i]) + 1
                endtm = (' ' * sofar) + endtm[sofar:]
            diff = old.end_timestamp - old.beg_timestamp
            if diff < 5 * 60:
                diff = _("(%u seconds)") % diff
            elif diff < 5 * 60 * 60:
                diff = _("(%u minutes)") % (diff / 60)
            elif diff < 5 * 60 * 60 * 24:
                diff = _("(%u hours)") % (diff / (60 * 60))
            else:
                diff = _("(%u days)") % (diff / (60 * 60 * 24))
            print _("End time       :"), endtm, diff
        if old.end_rpmdbversion is not None:
            if old.altered_gt_rpmdb:
                print _("End rpmdb      :"), old.end_rpmdbversion, "**"
            else:
                print _("End rpmdb      :"), old.end_rpmdbversion
        if type(name) == type([]):
            for name in name:
                print _("User           :"), name
        else:
            print _("User           :"), name
        if type(old.return_code) == type([]):
            codes = old.return_code
            if codes[0] is None:
                print _("Return-Code    :"), "**", _("Aborted"), "**"
                codes = codes[1:]
            if codes:
                print _("Return-Code    :"), _("Failures:"), ", ".join(codes)
        elif old.return_code is None:
            print _("Return-Code    :"), "**", _("Aborted"), "**"
        elif old.return_code:
            print _("Return-Code    :"), _("Failure:"), old.return_code
        else:
            print _("Return-Code    :"), _("Success")
            
        if old.cmdline is not None:
            if type(old.cmdline) == type([]):
                for cmdline in old.cmdline:
                    print _("Command Line   :"), cmdline
            else:
                print _("Command Line   :"), old.cmdline

        if type(old.tid) != type([]):
            addon_info = self.history.return_addon_data(old.tid)

            # for the ones we create by default - don't display them as there
            default_addons = set(['config-main', 'config-repos', 'saved_tx'])
            non_default = set(addon_info).difference(default_addons)
            if len(non_default) > 0:
                    print _("Additional non-default information stored: %d" 
                                % len(non_default))

        if old.trans_with:
            # This is _possible_, but not common
            print _("Transaction performed with:")
            pkg_max_len = max((len(str(hpkg)) for hpkg in old.trans_with))
        for hpkg in old.trans_with:
            _simple_pkg(hpkg, 4, was_installed=True, pkg_max_len=pkg_max_len)
        print _("Packages Altered:")
        self.historyInfoCmdPkgsAltered(old, pats)

        if old.trans_skip:
            print _("Packages Skipped:")
            pkg_max_len = max((len(str(hpkg)) for hpkg in old.trans_skip))
        for hpkg in old.trans_skip:
            _simple_pkg(hpkg, 4, pkg_max_len=pkg_max_len)

        if old.rpmdb_problems:
            print _("Rpmdb Problems:")
        for prob in old.rpmdb_problems:
            key = "%s%s: " % (" " * 4, prob.problem)
            print self.fmtKeyValFill(key, prob.text)
            if prob.packages:
                pkg_max_len = max((len(str(hpkg)) for hpkg in prob.packages))
            for hpkg in prob.packages:
                _simple_pkg(hpkg, 8, was_installed=True, highlight=hpkg.main,
                            pkg_max_len=pkg_max_len)

        if old.output:
            print _("Scriptlet output:")
            num = 0
            for line in old.output:
                num += 1
                print "%4d" % num, line
        if old.errors:
            print _("Errors:")
            num = 0
            for line in old.errors:
                num += 1
                print "%4d" % num, line

    _history_state2uistate = {'True-Install' : _('Install'),
                              'Install'      : _('Install'),
                              'Dep-Install'  : _('Dep-Install'),
                              'Obsoleted'    : _('Obsoleted'),
                              'Obsoleting'   : _('Obsoleting'),
                              'Erase'        : _('Erase'),
                              'Reinstall'    : _('Reinstall'),
                              'Downgrade'    : _('Downgrade'),
                              'Downgraded'   : _('Downgraded'),
                              'Update'       : _('Update'),
                              'Updated'      : _('Updated'),
                              }
    def historyInfoCmdPkgsAltered(self, old, pats=[]):
        """Print information about how packages are altered in a transaction.

        :param old: the :class:`history.YumHistoryTransaction` to
           print information about
        :param pats: a list of patterns.  Packages that match a patten
           in *pats* will be highlighted in the output
        """
        last = None
        #  Note that these don't use _simple_pkg() because we are showing what
        # happened to them in the transaction ... not the difference between the
        # version in the transaction and now.
        all_uistates = self._history_state2uistate
        maxlen = 0
        pkg_max_len = 0
        for hpkg in old.trans_data:
            uistate = all_uistates.get(hpkg.state, hpkg.state)
            if maxlen < len(uistate):
                maxlen = len(uistate)
            if pkg_max_len < len(str(hpkg)):
                pkg_max_len = len(str(hpkg))

        for hpkg in old.trans_data:
            prefix = " " * 4
            if not hpkg.done:
                prefix = " ** "

            highlight = 'normal'
            if pats:
                x,m,u = yum.packages.parsePackages([hpkg], pats)
                if x or m:
                    highlight = 'bold'
            (hibeg, hiend) = self._highlight(highlight)

            # To chop the name off we need nevra strings, str(pkg) gives envra
            # so we have to do it by hand ... *sigh*.
            cn = hpkg.ui_nevra

            uistate = all_uistates.get(hpkg.state, hpkg.state)
            uistate = utf8_width_fill(uistate, maxlen)
            # Should probably use columns here...
            if False: pass
            elif (last is not None and
                  last.state == 'Updated' and last.name == hpkg.name and
                  hpkg.state == 'Update'):
                ln = len(hpkg.name) + 1
                cn = (" " * ln) + cn[ln:]
            elif (last is not None and
                  last.state == 'Downgrade' and last.name == hpkg.name and
                  hpkg.state == 'Downgraded'):
                ln = len(hpkg.name) + 1
                cn = (" " * ln) + cn[ln:]
            else:
                last = None
                if hpkg.state in ('Updated', 'Downgrade'):
                    last = hpkg
            print "%s%s%s%s %-*s %s" % (prefix, hibeg, uistate, hiend,
                                        pkg_max_len, cn,
                                        self._hpkg2from_repo(hpkg))

    def historySummaryCmd(self, extcmds):
        """Print a summary of transactions in history.

        :param extcmds: list of extra command line arguments
        """
        tids, printall = self._history_list_transactions(extcmds)
        if tids is None:
            return 1, ['Failed history info']

        fmt = "%s | %s | %s | %s"
        print fmt % (utf8_width_fill(_("Login user"), 26, 26),
                     utf8_width_fill(_("Time"), 19, 19),
                     utf8_width_fill(_("Action(s)"), 16, 16),
                     utf8_width_fill(_("Altered"), 8, 8))
        print "-" * 79
        fmt = "%s | %s | %s | %8u"
        data = {'day' : {}, 'week' : {},
                'fortnight' : {}, 'quarter' : {}, 'half' : {}, 
                'year' : {}, 'all' : {}}
        for old in self.history.old(tids):
            name = self._pwd_ui_username(old.loginuid, 26)
            period = 'all'
            now = time.time()
            if False: pass
            elif old.beg_timestamp > (now - (24 * 60 * 60)):
                period = 'day'
            elif old.beg_timestamp > (now - (24 * 60 * 60 *  7)):
                period = 'week'
            elif old.beg_timestamp > (now - (24 * 60 * 60 * 14)):
                period = 'fortnight'
            elif old.beg_timestamp > (now - (24 * 60 * 60 *  7 * 13)):
                period = 'quarter'
            elif old.beg_timestamp > (now - (24 * 60 * 60 *  7 * 26)):
                period = 'half'
            elif old.beg_timestamp > (now - (24 * 60 * 60 * 365)):
                period = 'year'
            data[period].setdefault(name, []).append(old)
        _period2user = {'day'       : _("Last day"),
                        'week'      : _("Last week"),
                        'fortnight' : _("Last 2 weeks"), # US default :p
                        'quarter'   : _("Last 3 months"),
                        'half'      : _("Last 6 months"),
                        'year'      : _("Last year"),
                        'all'       : _("Over a year ago")}
        done = 0
        for period in ('day', 'week', 'fortnight', 'quarter', 'half', 'year',
                       'all'):
            if not data[period]:
                continue
            for name in sorted(data[period]):
                if not printall and done > 19:
                    break
                done += 1

                hpkgs = []
                for old in data[period][name]:
                    hpkgs.extend(old.trans_data)
                count, uiacts = self._history_uiactions(hpkgs)
                uperiod = _period2user[period]
                # Should probably use columns here, esp. for uiacts?
                print fmt % (utf8_width_fill(name, 26, 26),
                             utf8_width_fill(uperiod, 19, 19),
                             utf8_width_fill(uiacts, 16, 16), count)

    def historyAddonInfoCmd(self, extcmds):
        """Print addon information about transaction in history.

        :param extcmds: list of extra command line arguments
        """
        tid = None
        if len(extcmds) > 1:
            tid = extcmds[1]
            if tid == 'last':
                tid = None
        if tid is not None:
            try:
                int(tid)
            except ValueError:
                self.logger.critical(_('Bad transaction ID given'))
                return 1, ['Failed history addon-info']

        if tid is not None:
            old = self.history.old(tids=[tid])
        else:
            old = [self.history.last(complete_transactions_only=False)]
            if old[0] is None:
                self.logger.critical(_('No transaction ID, or package, given'))
                return 1, ['Failed history addon-info']

        if not old:
            self.logger.critical(_('No Transaction %s found') % tid)
            return 1, ['Failed history addon-info']
            
        hist_data = old[0]
        addon_info = self.history.return_addon_data(hist_data.tid)
        if len(extcmds) <= 2:
            print _("Transaction ID:"), hist_data.tid
            print _('Available additional history information:')
            for itemname in self.history.return_addon_data(hist_data.tid):
                print '  %s' % itemname
            print ''
            
            return 0, ['history addon-info']
        
        for item in extcmds[2:]:
            if item in addon_info:
                print '%s:' % item
                print self.history.return_addon_data(hist_data.tid, item)
            else:
                print _('%s: No additional data found by this name') % item

            print ''

    def historyPackageListCmd(self, extcmds):
        """Print a list of information about transactions from history
        that involve the given package or packages.

        :param extcmds: list of extra command line arguments
        """
        tids = self.history.search(extcmds)
        limit = None
        if extcmds and not tids:
            self.logger.critical(_('Bad transaction IDs, or package(s), given'))
            return 1, ['Failed history packages-list']
        if not tids:
            limit = 20

        all_uistates = self._history_state2uistate

        fmt = "%s | %s | %s"
        # REALLY Needs to use columns!
        print fmt % (utf8_width_fill(_("ID"), 6, 6),
                     utf8_width_fill(_("Action(s)"), 14, 14),
                     utf8_width_fill(_("Package"), 53, 53))
        print "-" * 79
        fmt = "%6u | %s | %-50s"
        num = 0
        for old in self.history.old(tids, limit=limit):
            if limit is not None and num and (num +len(old.trans_data)) > limit:
                break
            last = None

            # Copy and paste from list ... uh.
            rmark = lmark = ' '
            if old.return_code is None:
                rmark = lmark = '*'
            elif old.return_code:
                rmark = lmark = '#'
                # We don't check .errors, because return_code will be non-0
            elif old.output:
                rmark = lmark = 'E'
            elif old.rpmdb_problems:
                rmark = lmark = 'P'
            elif old.trans_skip:
                rmark = lmark = 's'
            if old.altered_lt_rpmdb:
                rmark = '<'
            if old.altered_gt_rpmdb:
                lmark = '>'

            for hpkg in old.trans_data: # Find a pkg to go with each cmd...
                if limit is None:
                    x,m,u = yum.packages.parsePackages([hpkg], extcmds)
                    if not x and not m:
                        continue

                uistate = all_uistates.get(hpkg.state, hpkg.state)
                uistate = utf8_width_fill(uistate, 14)

                #  To chop the name off we need nevra strings, str(pkg) gives
                # envra so we have to do it by hand ... *sigh*.
                cn = hpkg.ui_nevra

                # Should probably use columns here...
                if False: pass
                elif (last is not None and
                      last.state == 'Updated' and last.name == hpkg.name and
                      hpkg.state == 'Update'):
                    ln = len(hpkg.name) + 1
                    cn = (" " * ln) + cn[ln:]
                elif (last is not None and
                      last.state == 'Downgrade' and last.name == hpkg.name and
                      hpkg.state == 'Downgraded'):
                    ln = len(hpkg.name) + 1
                    cn = (" " * ln) + cn[ln:]
                else:
                    last = None
                    if hpkg.state in ('Updated', 'Downgrade'):
                        last = hpkg

                num += 1
                print fmt % (old.tid, uistate, cn), "%s%s" % (lmark,rmark)

        # And, again, copy and paste...
        lastdbv = self.history.last()
        if lastdbv is None:
            self._rpmdb_warn_checks(warn=False)
        else:
            #  If this is the last transaction, is good and it doesn't
            # match the current rpmdb ... then mark it as bad.
            rpmdbv  = self.rpmdb.simpleVersion(main_only=True)[0]
            if lastdbv.end_rpmdbversion != rpmdbv:
                self._rpmdb_warn_checks()


class DepSolveProgressCallBack:
    """A class to provide text output callback functions for Dependency Solver callback."""
    
    def __init__(self, ayum=None):
        """requires yum-cli log and errorlog functions as arguments"""
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.loops = 0
        self.ayum = ayum

    def pkgAdded(self, pkgtup, mode):
        """Print information about a package being added to the
        transaction set.

        :param pkgtup: tuple containing the package name, arch,
           version, and repository
        :param mode: a short string indicating why the package is
           being added to the transaction set.

        Valid current values for *mode* are::
        
           i = the package will be installed
           u = the package will be an update
           e = the package will be erased
           r = the package will be reinstalled
           d = the package will be a downgrade
           o = the package will be obsoleting another package
           ud = the package will be updated
           od = the package will be obsoleted
        """
        modedict = { 'i': _('installed'),
                     'u': _('an update'),
                     'e': _('erased'),
                     'r': _('reinstalled'),
                     'd': _('a downgrade'),
                     'o': _('obsoleting'),
                     'ud': _('updated'),
                     'od': _('obsoleted'),}
        (n, a, e, v, r) = pkgtup
        modeterm = modedict[mode]
        self.verbose_logger.log(logginglevels.INFO_2,
            _('---> Package %s.%s %s:%s-%s will be %s'), n, a, e, v, r,
            modeterm)
        
    def start(self):
        """Perform setup at the beginning of the dependency solving
        process.
        """
        self.loops += 1
        
    def tscheck(self):
        """Output a message stating that a transaction check is beginning."""
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Running transaction check'))
        
    def restartLoop(self):
        """Output a message stating that dependency resolution is restarting."""
        self.loops += 1
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Restarting Dependency Resolution with new changes.'))
        self.verbose_logger.debug('---> Loop Number: %d', self.loops)
    
    def end(self):
        """Output a message stating that dependency resolution has finished."""
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Finished Dependency Resolution'))

    
    def procReq(self, name, formatted_req):
        """Output a message stating that the package *formatted_req*
        is being processed as a dependency for the package *name*.

        :param name: the name of the package that *formatted_req* is a
           dependency of
        :param formatted_req: a string representing the package that
           is being processed as a dependency of *name*
        """
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Dependency: %s for package: %s'), formatted_req,
            name)

    def procReqPo(self, po, formatted_req):
        """Output a message stating that the package *formatted_req*
        is being processed as a dependency for the package *po*.

        :param po: the package object that *formatted_req* is a
           dependency of
        :param formatted_req: a string representing the package that
           is being processed as a dependency of *po*
        """
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Dependency: %s for package: %s'), formatted_req,
            po)
    
    def groupRemoveReq(self, po, hits):
        """Output a message stating that the given package will not be
        removed. This method is used during leaf-only group remove
        commands to indicate that the package will be kept.

        :param po: the :class:`yum.packages.PackageObject` that will
           not be removed
        :param hits: unused
        """
        self.verbose_logger.log(logginglevels.INFO_2,
            _('---> Keeping package: %s'), po)

    def unresolved(self, msg):
        """Output a message stating that there is an unresolved
        dependency.

        :param msg: string giving information about the unresolved
        dependency
        """
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Unresolved Dependency: %s'),
            msg)

    def format_missing_requires(self, reqPo, reqTup):
        """Return an error message stating that a package required to
        fulfill a dependency is missing.

        :param reqPo: the package object that has a dependency that
           cannot be fulfilled
        :param reqTup: the name, flags, and version of the package
           needed to fulfil the dependency
        """
        needname, needflags, needversion = reqTup

        yb = self.ayum

        prob_pkg = "%s (%s)" % (reqPo, reqPo.ui_from_repo)
        msg = _('Package: %s') % (prob_pkg,)
        ui_req = formatRequire(needname, needversion, needflags)
        msg += _('\n    Requires: %s') % (ui_req,)
        
        # if DepSolveProgressCallback() is used instead of DepSolveProgressCallback(ayum=<YumBase Object>)
        # then ayum has no value and we can't continue to find details about the missing requirements
        if not yb:
            return msg
        
        def _msg_pkg(action, pkg, needname):
            " Add a package to the message, including any provides matches. "
            msg = _('\n    %s: %s (%s)') % (action, pkg, pkg.ui_from_repo)
            needtup = (needname, None, (None, None, None))
            done = False
            for pkgtup in pkg.matchingPrcos('provides', needtup):
                done = True
                msg += _('\n        %s') % yum.misc.prco_tuple_to_string(pkgtup)
            if not done:
                msg += _('\n        Not found')
            return msg

        def _run_inst_pkg(pkg, msg):
            nevr = (pkg.name, pkg.epoch, pkg.version, pkg.release)
            if nevr in seen_pkgs or (pkg.verEQ(last) and pkg.arch == last.arch):
                return msg

            seen_pkgs.add(nevr)
            action = _('Installed')
            rmed = yb.tsInfo.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES)
            if rmed:
                action = _('Removing')
            msg += _msg_pkg(action, pkg, needname)
            # These should be the only three things we care about:
            relmap = {'updatedby' : _('Updated By'),
                      'downgradedby' : _('Downgraded By'),
                      'obsoletedby' :  _('Obsoleted By'),
                      }
            for txmbr in rmed:
                for (rpkg, rtype) in txmbr.relatedto:
                    if rtype not in relmap:
                        continue
                    nevr = (rpkg.name, rpkg.epoch, rpkg.version, rpkg.release)
                    seen_pkgs.add(nevr)
                    msg += _msg_pkg(relmap[rtype], rpkg, needname)
            return msg

        def _run_avail_pkg(pkg, msg):
            #  We don't want to see installed packages, or N packages of the
            # same version, from different repos.
            nevr = (pkg.name, pkg.epoch, pkg.version, pkg.release)
            if nevr in seen_pkgs or (pkg.verEQ(last) and pkg.arch == last.arch):
                return False, last, msg
            seen_pkgs.add(nevr)
            action = _('Available')
            if yb.tsInfo.getMembersWithState(pkg.pkgtup, TS_INSTALL_STATES):
                action = _('Installing')
            msg += _msg_pkg(action, pkg, needname)
            return True, pkg, msg

        last = None
        seen_pkgs = set()
        for pkg in sorted(yb.rpmdb.getProvides(needname)):
            msg = _run_inst_pkg(pkg, msg)

        available_names = set()
        for pkg in sorted(yb.pkgSack.getProvides(needname)):
            tst, last, msg = _run_avail_pkg(pkg, msg)
            if tst:
                available_names.add(pkg.name)

        last = None
        for pkg in sorted(yb.rpmdb.searchNames(available_names)):
            msg = _run_inst_pkg(pkg, msg)
        last = None
        for pkg in sorted(yb.pkgSack.searchNames(available_names)):
            tst, last, msg = _run_avail_pkg(pkg, msg)
        return msg
    
    def procConflict(self, name, confname):
        """Print a message stating that two packages in the
        transaction conflict.

        :param name: the name of the first package involved in the
           conflict 
        :param confname: the name of the second package involved in
           the conflict
        """
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Conflict: %s conflicts %s'),
                                name, confname)

    def procConflictPo(self, po, confname):
        """Print a message stating that two packages in the
        transaction conflict.

        :param name: the first package object involved in the
           conflict 
        :param confname: the second package object involved in
           the conflict
        """
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Conflict: %s conflicts %s'),
                                po, confname)

    def transactionPopulation(self):
        """Output a message stating that the transaction set is being populated."""

        self.verbose_logger.log(logginglevels.INFO_2, _('--> Populating transaction set '
            'with selected packages. Please wait.'))
    
    def downloadHeader(self, name):
        """Output a message stating that the header for the given
        package is being downloaded.

        :param name: the name of the package
        """
        self.verbose_logger.log(logginglevels.INFO_2, _('---> Downloading header for %s '
            'to pack into transaction set.'), name)
       

class CacheProgressCallback:
    """A class to handle text output callbacks during metadata cache updates."""

    def __init__(self):
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.file_logger = logging.getLogger("yum.filelogging.cli")

    def log(self, level, message):
        """Output a log message.

        :param level: the logging level for the message
        :param message: the message
        """
        self.verbose_logger.log(level, message)

    def errorlog(self, level, message):
        """Output an errorlog message.

        :param level: the logging level for the message
        :param message: the message
        """
        self.logger.log(level, message)

    def filelog(self, level, message):
        """Output a file log message.

        :param level: the logging level for the message
        :param message: the message
        """
        self.file_logger.log(level, message)

    def progressbar(self, current, total, name=None):
        """Output the current status to the terminal using a progress
        status bar.

        :param current: a number representing the amount of work
           already done
        :param total: a number representing the total amount of work
           to be done
        :param name: a name to label the progress bar with
        """
        progressbar(current, total, name)

def _pkgname_ui(ayum, pkgname, ts_states=None):
    """ Get more information on a simple pkgname, if we can. We need to search
        packages that we are dealing with atm. and installed packages (if the
        transaction isn't complete). """
    if ayum is None:
        return pkgname

    if ts_states is None:
        #  Note 'd' is a placeholder for downgrade, and
        # 'r' is a placeholder for reinstall. Neither exist atm.
        ts_states = ('d', 'e', 'i', 'r', 'u', 'od', 'ud')

    matches = []
    def _cond_add(po):
        if matches and matches[0].arch == po.arch and matches[0].verEQ(po):
            return
        matches.append(po)

    for txmbr in ayum.tsInfo.matchNaevr(name=pkgname):
        if txmbr.ts_state not in ts_states:
            continue
        _cond_add(txmbr.po)

    if not matches:
        return pkgname
    fmatch = matches.pop(0)
    if not matches:
        return str(fmatch)

    show_ver  = True
    show_arch = True
    for match in matches:
        if not fmatch.verEQ(match):
            show_ver  = False
        if fmatch.arch != match.arch:
            show_arch = False

    if show_ver: # Multilib. *sigh*
        if fmatch.epoch == '0':
            return '%s-%s-%s' % (fmatch.name, fmatch.version, fmatch.release)
        else:
            return '%s:%s-%s-%s' % (fmatch.epoch, fmatch.name,
                                    fmatch.version, fmatch.release)

    if show_arch:
        return '%s.%s' % (fmatch.name, fmatch.arch)

    return pkgname

class YumCliRPMCallBack(RPMBaseCallback):
    """A Yum specific callback class for RPM operations."""

    width = property(lambda x: _term_width())

    def __init__(self, ayum=None):
        RPMBaseCallback.__init__(self)
        self.lastmsg = to_unicode("")
        self.lastpackage = None # name of last package we looked at
        self.output = logging.getLogger("yum.verbose.cli").isEnabledFor(logginglevels.INFO_2)
        
        # for a progress bar
        self.mark = "#"
        self.marks = 22
        self.ayum = ayum

    #  Installing things have pkg objects passed to the events, so only need to
    # lookup for erased/obsoleted.
    def pkgname_ui(self, pkgname, ts_states=('e', 'od', 'ud', None)):
        """Return more information on a simple pkgname, if possible.

        :param pkgname: the name of the package to find information about
        :param ts_states: a tuple containing the states where the
           package might be found
        """
        return _pkgname_ui(self.ayum, pkgname, ts_states)

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """Output information about an rpm operation.  This may
        include a text progress bar.

        :param package: the package involved in the event
        :param action: the type of action that is taking place.  Valid
           values are given by
           :func:`rpmtrans.RPMBaseCallback.action.keys()`
        :param te_current: a number representing the amount of work
           already done in the current transaction
        :param te_total: a number representing the total amount of work
           to be done in the current transaction
        :param ts_current: the number of the current transaction in
           transaction set
        :param ts_total: the total number of transactions in the
           transaction set
        """
        process = self.action[action]

        if not hasattr(self, '_max_action_wid'):
            wid1 = 0
            for val in self.action.values():
                wid_val = utf8_width(val)
                if wid1 < wid_val:
                    wid1 = wid_val
            self._max_action_wid = wid1
        wid1 = self._max_action_wid
        
        if type(package) not in types.StringTypes:
            pkgname = str(package)
        else:
            pkgname = self.pkgname_ui(package)
            
        self.lastpackage = package
        if te_total == 0:
            percent = 0
        else:
            percent = (te_current*100L)/te_total
        
        if self.output and (sys.stdout.isatty() or te_current == te_total):
            (fmt, wid1, wid2) = self._makefmt(percent, ts_current, ts_total,
                                              progress=sys.stdout.isatty(),
                                              pkgname=pkgname, wid1=wid1)
            msg = fmt % (utf8_width_fill(process, wid1, wid1),
                         utf8_width_fill(pkgname, wid2, wid2))
            if msg != self.lastmsg:
                sys.stdout.write(to_unicode(msg))
                sys.stdout.flush()
                self.lastmsg = msg
            if te_current == te_total:
                print " "

    def scriptout(self, package, msgs):
        """Print messages originating from a package script.

        :param package: unused
        :param msgs: the messages coming from the script
        """
        if msgs:
            sys.stdout.write(to_unicode(msgs))
            sys.stdout.flush()

    def _makefmt(self, percent, ts_current, ts_total, progress = True,
                 pkgname=None, wid1=15):
        l = len(str(ts_total))
        size = "%s.%s" % (l, l)
        fmt_done = "%" + size + "s/%" + size + "s"
        done = fmt_done % (ts_current, ts_total)

        #  This should probably use TerminLine, but we don't want to dep. on
        # that. So we kind do an ok job by hand ... at least it's dynamic now.
        if pkgname is None:
            pnl = 22
        else:
            pnl = utf8_width(pkgname)

        overhead  = (2 * l) + 2 # Length of done, above
        overhead +=  2+ wid1 +2 # Length of begining ("  " action " :")
        overhead +=  1          # Space between pn and done
        overhead +=  2          # Ends for progress
        overhead +=  1          # Space for end
        width = self.width
        if width < overhead:
            width = overhead    # Give up
        width -= overhead
        if pnl > width / 2:
            pnl = width / 2

        marks = self.width - (overhead + pnl)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "[%-" + width + "s]"
        # pnl = str(28 + marks + 1)
        full_pnl = pnl + marks + 1

        if progress and percent == 100: # Don't chop pkg name on 100%
            fmt = "\r  %s: %s   " + done
            wid2 = full_pnl
        elif progress:
            bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            fmt = "\r  %s: %s " + bar + " " + done
            wid2 = pnl
        elif percent == 100:
            fmt = "  %s: %s   " + done
            wid2 = full_pnl
        else:
            bar = fmt_bar % (self.mark * marks, )
            fmt = "  %s: %s " + bar + " " + done
            wid2 = pnl
        return fmt, wid1, wid2


def progressbar(current, total, name=None):
    """Output the current status to the terminal using a simple
    text progress bar consisting of 50 # marks.

    :param current: a number representing the amount of work
       already done
    :param total: a number representing the total amount of work
       to be done
    :param name: a name to label the progress bar with
    """
    """simple progress bar 50 # marks"""
    
    mark = '#'
    if not sys.stdout.isatty():
        return
        
    if current == 0:
        percent = 0 
    else:
        if total != 0:
            percent = float(current) / total
        else:
            percent = 0

    width = _term_width()

    if name is None and current == total:
        name = '-'

    end = ' %d/%d' % (current, total)
    width -= len(end) + 1
    if width < 0:
        width = 0
    if name is None:
        width -= 2
        if width < 0:
            width = 0
        hashbar = mark * int(width * percent)
        output = '\r[%-*s]%s' % (width, hashbar, end)
    elif current == total: # Don't chop name on 100%
        output = '\r%s%s' % (utf8_width_fill(name, width, width), end)
    else:
        width -= 4
        if width < 0:
            width = 0
        nwid = width / 2
        if nwid > utf8_width(name):
            nwid = utf8_width(name)
        width -= nwid
        hashbar = mark * int(width * percent)
        output = '\r%s: [%-*s]%s' % (utf8_width_fill(name, nwid, nwid), width,
                                     hashbar, end)
     
    if current <= total:
        sys.stdout.write(output)

    if current == total:
        sys.stdout.write('\n')

    sys.stdout.flush()
        

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "format_number":
        print ""
        print " Doing format_number tests, right column should align"
        print ""

        x = YumOutput()
        for i in (0, 0.0, 0.1, 1, 1.0, 1.1, 10, 11, 11.1, 100, 111.1,
                  1000, 1111, 1024 * 2, 10000, 11111, 99999, 999999,
                  10**19, 10**20, 10**35):
            out = x.format_number(i)
            print "%36s <%s> %s <%5s>" % (i, out, ' ' * (14 - len(out)), out)

    if len(sys.argv) > 1 and sys.argv[1] == "progress":
        print ""
        print " Doing progress, small name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, "abcd")
            time.sleep(0.1)
        print ""
        print " Doing progress, big name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, "_%s_" % ("123456789 " * 5))
            time.sleep(0.1)
        print ""
        print " Doing progress, no name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100)
            time.sleep(0.1)

    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "rpm-progress"):
        cb = YumCliRPMCallBack()
        cb.output = True
        cb.action["foo"] = "abcd"
        cb.action["bar"] = "_12345678_.end"
        print ""
        print " Doing CB, small proc / small pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("spkg", "foo", i, 100, i, 100)
            time.sleep(0.1)        
        print ""
        print " Doing CB, big proc / big pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("lpkg" + "-=" * 15 + ".end", "bar", i, 100, i, 100)
            time.sleep(0.1)

    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress",
                                             "rpm-progress",
                                             'i18n-rpm-progress'):
        yum.misc.setup_locale()
    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress"):
        print ""
        print " Doing progress, i18n: small name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85'))
            time.sleep(0.1)
        print ""

        print ""
        print " Doing progress, i18n: big name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85' * 5 + ".end"))
            time.sleep(0.1)
        print ""


    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress",
                                             "rpm-progress",
                                             'i18n-rpm-progress'):
        cb = YumCliRPMCallBack()
        cb.output = True
        cb.action["foo"] = to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85')
        cb.action["bar"] = cb.action["foo"] * 5 + ".end"
        print ""
        print " Doing CB, i18n: small proc / small pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("spkg", "foo", i, 100, i, 100)
            time.sleep(0.1)        
        print ""
        print " Doing CB, i18n: big proc / big pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("lpkg" + "-=" * 15 + ".end", "bar", i, 100, i, 100)
            time.sleep(0.1)
        print ""
        
