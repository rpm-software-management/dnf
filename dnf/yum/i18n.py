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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from __future__ import print_function
from __future__ import unicode_literals
from dnf.pycomp import is_py2str_py3bytes, unicode, basestring, to_ord


def to_utf8(obj, errors='replace'):
    '''convert 'unicode' to an encoded utf-8 byte string '''
    if isinstance(obj, unicode):
        obj = obj.encode('utf-8', errors)
    return obj

def to_str(obj):
    """ Convert something to a string, if it isn't one. """
    # NOTE: unicode counts as a string just fine. We just want objects to call
    # their __str__ methods.
    if not isinstance(obj, basestring):
        obj = str(obj)
    return obj
