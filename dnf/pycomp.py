# pycomp.py
# Python 2 and Python 3 compatibility module
#
# Copyright (C) 2013  Red Hat, Inc.
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

from gettext import NullTranslations
from sys import version_info
from unittest import TestCase

import itertools

if version_info.major >= 3:
    PY3 = True
    basestring = unicode = str
    filterfalse = itertools.filterfalse
    long = int
    NullTranslations.ugettext = NullTranslations.gettext
    NullTranslations.ungettext = NullTranslations.ngettext
    xrange = range
    raw_input = input
    from io import StringIO
    to_ord = lambda i: i
    def is_py2str_py3bytes(o):
        return isinstance(o, bytes)

    def is_py3bytes(o):
        return isinstance(o, bytes)

else:
    from __builtin__ import unicode, basestring, long, xrange, raw_input
    PY3 = False
    from StringIO import StringIO
    filterfalse = itertools.ifilterfalse
    to_ord = lambda i: ord(i)
    def is_py2str_py3bytes(o):
        return isinstance(o, str)

    def is_py3bytes(o):
        return False
