# i18n.py
#
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

from __future__ import print_function
from __future__ import unicode_literals
from dnf.pycomp import PY3, is_py3bytes, unicode, setlocale
import gettext
import locale
import os
import sys

"""
Centralize i18n stuff here. Must be unittested.
"""

class UnicodeStream(object):
    def __init__(self, stream, encoding):
        self.stream = stream
        self.encoding = encoding

    def write(self, s):
        if not isinstance(s, str):
            s = (s.decode(self.encoding, 'replace') if PY3 else
                 s.encode(self.encoding, 'replace'))
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
    return locale.getpreferredencoding()

def setup_locale():
    try:
        setlocale(locale.LC_ALL, '')
        # set time to C so that we output sane things in the logs (#433091)
        setlocale(locale.LC_TIME, 'C')
    except locale.Error as e:
        # default to C locale if we get a failure.
        print('Failed to set locale, defaulting to C', file=sys.stderr)
        os.environ['LC_ALL'] = 'C'
        setlocale(locale.LC_ALL, 'C')

def setup_stdout():
    """ Check that stdout is of suitable encoding and handle the situation if
        not.

        Returns True if stdout was of suitable encoding already and no changes
        were needed.
    """
    stdout = sys.stdout
    try:
        encoding = stdout.encoding
    except AttributeError:
        encoding = None
    if not _full_ucd_support(encoding):
        sys.stdout = UnicodeStream(stdout, _guess_encoding())
        return False
    return True

def ucd_input(ucstring):
    """ Take input from user.

        What the raw_input() built-in does, but encode the prompt first
        (raw_input() won't check sys.stdout.encoding as e.g. print does, see
        test_i18n.TestInput.test_assumption()).
    """
    if not isinstance(ucstring, unicode):
        raise TypeError("input() accepts Unicode strings")
    if PY3:
        return input(ucstring)
    enc = sys.stdout.encoding if sys.stdout.encoding else 'utf8'
    s = ucstring.encode(enc, 'strict')
    return raw_input(s)

def ucd(obj):
    """ Like the builtin unicode() but tries to use a reasonable encoding. """
    if PY3:
        if is_py3bytes(obj):
            return str(obj, _guess_encoding())
        elif isinstance(obj, str):
            return obj
        return str(obj)
    else:
        if isinstance(obj, unicode):
            return obj
        if hasattr(obj, '__unicode__'):
            # see the doc for the unicode() built-in. The logic here is: if obj
            # implements __unicode__, let it take a crack at it, but handle the
            # situation if it fails:
            try:
                return unicode(obj)
            except UnicodeError:
                pass
        return unicode(str(obj), _guess_encoding())


def fill_exact_width(msg, width):
    return "%-*.*s" % (width, width, msg)


# setup translation
t = gettext.translation('dnf', fallback=True)
_ = t.ugettext
P_ = t.ungettext
