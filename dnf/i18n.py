# i18n.py
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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

from __future__ import print_function
from __future__ import unicode_literals
from dnf.pycomp import unicode

import dnf
import locale
import os
import signal
import sys
import unicodedata

"""
Centralize i18n stuff here. Must be unittested.
"""

class UnicodeStream(object):
    def __init__(self, stream, encoding):
        self.stream = stream
        self.encoding = encoding

    def write(self, s):
        if not isinstance(s, str):
            s = (s.decode(self.encoding, 'replace') if dnf.pycomp.PY3 else
                 s.encode(self.encoding, 'replace'))
        try:
            self.stream.write(s)
        except UnicodeEncodeError:
            s_bytes = s.encode(self.stream.encoding, 'backslashreplace')
            if hasattr(self.stream, 'buffer'):
                self.stream.buffer.write(s_bytes)
            else:
                s = s_bytes.decode(self.stream.encoding, 'ignore')
                self.stream.write(s)


    def __getattr__(self, name):
        return getattr(self.stream, name)

def _full_ucd_support(encoding):
    """Return true if encoding can express any Unicode character.

    Even if an encoding can express all accented letters in the given language,
    we can't generally settle for it in DNF since sometimes we output special
    characters like the registered trademark symbol (U+00AE) and surprisingly
    many national non-unicode encodings, including e.g. ASCII and ISO-8859-2,
    don't contain it.

    """
    if encoding is None:
        return False
    lower = encoding.lower()
    if lower.startswith('utf-') or lower.startswith('utf_'):
        return True
    return False

def _guess_encoding():
    """ Take the best shot at the current system's string encoding. """
    encoding = locale.getpreferredencoding(False)
    return 'utf-8' if encoding.startswith("ANSI") else encoding

def setup_locale():
    try:
        dnf.pycomp.setlocale(locale.LC_ALL, '')
    except locale.Error:
        # default to C.UTF-8 or C locale if we got a failure.
        try:
            dnf.pycomp.setlocale(locale.LC_ALL, 'C.UTF-8')
            os.environ['LC_ALL'] = 'C.UTF-8'
        except locale.Error:
            dnf.pycomp.setlocale(locale.LC_ALL, 'C')
            os.environ['LC_ALL'] = 'C'
        print('Failed to set locale, defaulting to {}'.format(os.environ['LC_ALL']),
              file=sys.stderr)

def setup_stdout():
    """ Check that stdout is of suitable encoding and handle the situation if
        not.

        Returns True if stdout was of suitable encoding already and no changes
        were needed.
    """
    stdout = sys.stdout
    if not stdout.isatty():
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        encoding = stdout.encoding
    except AttributeError:
        encoding = None
    if not _full_ucd_support(encoding):
        sys.stdout = UnicodeStream(stdout, _guess_encoding())
        return False
    return True


def ucd_input(ucstring):
    # :api, deprecated in 2.0.0, will be erased when python2 is abandoned
    """ It uses print instead of passing the prompt to raw_input.

        raw_input doesn't encode the passed string and the output
        goes into stderr
    """
    print(ucstring, end='')
    return dnf.pycomp.raw_input()


def ucd(obj):
    # :api, deprecated in 2.0.0, will be erased when python2 is abandoned
    """ Like the builtin unicode() but tries to use a reasonable encoding. """
    if dnf.pycomp.PY3:
        if dnf.pycomp.is_py3bytes(obj):
            return str(obj, _guess_encoding(), errors='ignore')
        elif isinstance(obj, str):
            return obj
        return str(obj)
    else:
        if isinstance(obj, dnf.pycomp.unicode):
            return obj
        if hasattr(obj, '__unicode__'):
            # see the doc for the unicode() built-in. The logic here is: if obj
            # implements __unicode__, let it take a crack at it, but handle the
            # situation if it fails:
            try:
                return dnf.pycomp.unicode(obj)
            except UnicodeError:
                pass
        return dnf.pycomp.unicode(str(obj), _guess_encoding(), errors='ignore')


# functions for formatting output according to terminal width,
# They should be used instead of build-in functions to count on different
# widths of Unicode characters

def _exact_width_char(uchar):
    return 2 if unicodedata.east_asian_width(uchar) in ('W', 'F') else 1


def chop_str(msg, chop=None):
    """ Return the textual width of a Unicode string, chopping it to
        a specified value. This is what you want to use instead of %.*s, as it
        does the "right" thing with regard to different Unicode character width
        Eg. "%.*s" % (10, msg)   <= becomes => "%s" % (chop_str(msg, 10)) """

    if chop is None:
        return exact_width(msg), msg

    width = 0
    chopped_msg = ""
    for char in msg:
        char_width = _exact_width_char(char)
        if width + char_width > chop:
            break
        chopped_msg += char
        width += char_width
    return width, chopped_msg


def exact_width(msg):
    """ Calculates width of char at terminal screen
        (Asian char counts for two) """
    return sum(_exact_width_char(c) for c in msg)


def fill_exact_width(msg, fill, chop=None, left=True, prefix='', suffix=''):
    """ Expand a msg to a specified "width" or chop to same.
        Expansion can be left or right. This is what you want to use instead of
        %*.*s, as it does the "right" thing with regard to different Unicode
        character width.
        prefix and suffix should be used for "invisible" bytes, like
        highlighting.

        Examples:

        ``"%-*.*s" % (10, 20, msg)`` becomes
            ``"%s" % (fill_exact_width(msg, 10, 20))``.

        ``"%20.10s" % (msg)`` becomes
            ``"%s" % (fill_exact_width(msg, 20, 10, left=False))``.

        ``"%s%.10s%s" % (pre, msg, suf)`` becomes
            ``"%s" % (fill_exact_width(msg, 0, 10, prefix=pre, suffix=suf))``.
        """
    width, msg = chop_str(msg, chop)

    if width >= fill:
        if prefix or suffix:
            msg = ''.join([prefix, msg, suffix])
    else:
        extra = " " * (fill - width)
        if left:
            msg = ''.join([prefix, msg, suffix, extra])
        else:
            msg = ''.join([extra, prefix, msg, suffix])

    return msg


def textwrap_fill(text, width=70, initial_indent='', subsequent_indent=''):
    """ Works like we want textwrap.wrap() to work, uses Unicode strings
        and doesn't screw up lists/blocks/etc. """

    def _indent_at_beg(line):
        count = 0
        byte = 'X'
        for byte in line:
            if byte != ' ':
                break
            count += 1
        if byte not in ("-", "*", ".", "o", '\xe2'):
            return count, 0
        list_chr = chop_str(line[count:], 1)[1]
        if list_chr in ("-", "*", ".", "o",
                        "\u2022", "\u2023", "\u2218"):
            nxt = _indent_at_beg(line[count+len(list_chr):])
            nxt = nxt[1] or nxt[0]
            if nxt:
                return count, count + 1 + nxt
        return count, 0

    text = text.rstrip('\n')
    lines = text.replace('\t', ' ' * 8).split('\n')

    ret = []
    indent = initial_indent
    wrap_last = False
    csab = 0
    cspc_indent = 0
    for line in lines:
        line = line.rstrip(' ')
        (lsab, lspc_indent) = (csab, cspc_indent)
        (csab, cspc_indent) = _indent_at_beg(line)
        force_nl = False # We want to stop wrapping under "certain" conditions:
        if wrap_last and cspc_indent:        # if line starts a list or
            force_nl = True
        if wrap_last and csab == len(line):  # is empty line
            force_nl = True
        # if line doesn't continue a list and is "block indented"
        if wrap_last and not lspc_indent:
            if csab >= 4 and csab != lsab:
                force_nl = True
        if force_nl:
            ret.append(indent.rstrip(' '))
            indent = subsequent_indent
            wrap_last = False
        if csab == len(line):  # empty line, remove spaces to make it easier.
            line = ''
        if wrap_last:
            line = line.lstrip(' ')
            cspc_indent = lspc_indent

        if exact_width(indent + line) <= width:
            wrap_last = False
            ret.append(indent + line)
            indent = subsequent_indent
            continue

        wrap_last = True
        words = line.split(' ')
        line = indent
        spcs = cspc_indent
        if not spcs and csab >= 4:
            spcs = csab
        for word in words:
            if (width < exact_width(line + word)) and \
               (exact_width(line) > exact_width(subsequent_indent)):
                ret.append(line.rstrip(' '))
                line = subsequent_indent + ' ' * spcs
            line += word
            line += ' '
        indent = line.rstrip(' ') + ' '
    if wrap_last:
        ret.append(indent.rstrip(' '))

    return '\n'.join(ret)


def select_short_long(width, msg_short, msg_long):
    """ Automatically selects the short (abbreviated) or long (full) message
        depending on whether we have enough screen space to display the full
        message or not. If a caller by mistake passes a long string as
        msg_short and a short string as a msg_long this function recognizes
        the mistake and swaps the arguments. This function is especially useful
        in the i18n context when you cannot predict how long are the translated
        messages.

        Limitations:

        1. If msg_short is longer than width you will still get an overflow.
           This function does not abbreviate the string.
        2. You are not obliged to provide an actually abbreviated string, it is
           perfectly correct to pass the same string twice if you don't want
           any abbreviation. However, if you provide two different strings but
           having the same width this function is unable to recognize which one
           is correct and you should assume that it is unpredictable which one
           is returned.

       Example:

       ``select_short_long (10, _("Repo"), _("Repository"))``

       will return "Repository" in English but the results in other languages
       may be different. """
    width_short = exact_width(msg_short)
    width_long = exact_width(msg_long)
    # If we have two strings of the same width:
    if width_short == width_long:
        return msg_long
    # If the short string is wider than the long string:
    elif width_short > width_long:
        return msg_short if width_short <= width else msg_long
    # The regular case:
    else:
        return msg_long if width_long <= width else msg_short


def translation(name):
    # :api, deprecated in 2.0.0, will be erased when python2 is abandoned
    """ Easy gettext translations setup based on given domain name """

    setup_locale()
    def ucd_wrapper(fnc):
        return lambda *w: ucd(fnc(*w))
    t = dnf.pycomp.gettext.translation(name, fallback=True)
    return map(ucd_wrapper, dnf.pycomp.gettext_setup(t))


def pgettext(context, message):
    result = _(context + chr(4) + message)
    if "\004" in result:
        return message
    else:
        return result

# setup translations
_, P_ = translation("dnf")
C_ = pgettext
