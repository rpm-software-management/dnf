# i18n.py
#
# Copyright (C) 2012  Red Hat, Inc.
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

import locale
import sys

"""
Centralize i18n stuff here. Must be unittested.
"""

class UnicodeStream(object):
    def __init__(self, stream, encoding):
        self.stream = stream
        self.encoding = encoding

    def write(self, s):
        if isinstance(s, unicode):
            s = s.encode(self.encoding, 'replace')
        self.stream.write(s)

    def __getattr__(self, name):
        return getattr(self.stream, name)

def setup_locale():
    try:
        locale.setlocale(locale.LC_ALL, '')
        # set time to C so that we output sane things in the logs (#433091)
        locale.setlocale(locale.LC_TIME, 'C')
    except locale.Error, e:
        # default to C locale if we get a failure.
        print >> sys.stderr, 'Failed to set locale, defaulting to C'
        os.environ['LC_ALL'] = 'C'
        locale.setlocale(locale.LC_ALL, 'C')

def setup_stdout():
    """ Check that stdout is of suitable encoding and handle the situation if
        not.

        Returns True if stdout was of suitable encoding already and no chagnes
        were needed.
    """
    if sys.stdout.encoding is None:
        sys.stdout = UnicodeStream(sys.stdout, locale.getpreferredencoding())
        return False
    return True

def input(ucstring):
    """ Take input from user.

        What the raw_input() builitn does, but encode the prompt first
        (raw_input() won't check sys.stdout.encoding as e.g. print does, see
        test_i18n.TestInput.test_assumption()).
    """
    if not isinstance(ucstring, unicode):
        raise TypeError("input() accepts Unicode strings")
    enc = sys.stdout.encoding if sys.stdout.encoding else 'utf8'
    s = ucstring.encode(enc, 'strict')
    return raw_input(s)
