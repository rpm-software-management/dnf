# util.py
# Basic dnf utils.
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

import hawkey
import os
import time
import types

def am_i_root():
    return os.geteuid() == 0

def first(iterable):
    """ Returns the first item from an iterable or None if it has no elements. """
    it = iter(iterable)
    try:
        return it.next()
    except StopIteration:
        return None

def file_timestamp(fn):
    return os.stat(fn).st_mtime

def is_string_type(obj):
    return type(obj) in types.StringTypes

def lazyattr(attrname):
    """ Decorator to get lazy attribute initialization.

        Composes with @property. Force reinitialization by deleting the
        <attrname>.
     """
    def get_decorated(fn):
        def cached_getter(obj):
            try:
                return getattr(obj, attrname)
            except AttributeError:
                val = fn(obj)
                setattr(obj, attrname, val)
                return val
        return cached_getter
    return get_decorated

def reason_name(reason):
    if reason == hawkey.REASON_DEP:
        return "dep"
    if reason == hawkey.REASON_USER:
        return "user"
    raise ValueError, "Unknown reason %d" % reason

def strip_prefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix):]
    return None

def timed(fn):
    """ Decorator, prints out the ms a function took to complete.

        Used for debugging.
    """
    def decorated(*args, **kwargs):
        start = time.time()
        retval = fn(*args, **kwargs)
        length = time.time() - start
        print "%s took %.02f ms" % (fn.__name__, length * 1000)
        return retval
    return decorated
