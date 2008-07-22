#!/usr/bin/python -tt
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

def dummy_wrapper(str):
    '''
    Dummy Translation wrapper, just returning the same string.
    '''
    return str

try: 
    '''
    Setup the yum translation domain and make _() translation wrapper
    available.
    using ugettext to make sure translated strings are in Unicode.
    '''
    import gettext
    t = gettext.translation('yum', fallback=True)
    _ = t.ugettext
except:
    '''
    Something went wrong so we make a dummy _() wrapper there is just
    returning the same text
    '''
    _ = dummy_wrapper
