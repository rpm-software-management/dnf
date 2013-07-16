# util.py
# Basic dnf utils.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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
import dnf.const
import hawkey
import os
import shutil
import subprocess
import tempfile
import time
import types

"""DNF Utilities.

Generally these are not a part of the public DNF API.

"""

def am_i_root():
    return os.geteuid() == 0

def ensure_dir(dname):
    if os.path.exists(dname):
        if not os.path.isdir(dname):
            raise IOError("%s is not a directory" % dname)
    else:
        os.makedirs(dname, mode=0755)

def empty(iterable):
    try:
        l = len(iterable)
    except TypeError:
        l = len(list(iterable))
    return l == 0

def first(iterable):
    """Returns the first item from an iterable or None if it has no elements."""
    it = iter(iterable)
    try:
        return it.next()
    except StopIteration:
        return None

def file_age(fn):
    return time.time() - file_timestamp(fn)

def file_timestamp(fn):
    return os.stat(fn).st_mtime

def group_by_filter(fn, iterable):
    def splitter(acc, item):
        acc[not bool(fn(item))].append(item)
        return acc
    return reduce(splitter, iterable, ([], []))

def is_glob_pattern(pattern):
    return set(pattern) & set("*[?")

def is_string_type(obj):
    return type(obj) in types.StringTypes

def lazyattr(attrname):
    """Decorator to get lazy attribute initialization.

    Composes with @property. Force reinitialization by deleting the <attrname>.
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

def on_ac_power():
    """Decide whether we are on line power.

    Returns True if we are on line power, False if not, None if it can not be
    decided.

    """
    try:
        ret = subprocess.call('/usr/bin/on_ac_power')
        return not ret
    except OSError:
        return None

def reason_name(reason):
    if reason == hawkey.REASON_DEP:
        return "dep"
    if reason == hawkey.REASON_USER:
        return "user"
    raise ValueError, "Unknown reason %d" % reason

def rm_rf(path):
    try:
        shutil.rmtree(path)
    except OSError:
        pass

def strip_prefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix):]
    return None

def timed(fn):
    """Decorator, prints out the ms a function took to complete.

    Used for debugging.

    """
    def decorated(*args, **kwargs):
        start = time.time()
        retval = fn(*args, **kwargs)
        length = time.time() - start
        print("%s took %.02f ms" % (fn.__name__, length * 1000))
        return retval
    return decorated

def touch(path, no_create=False):
    """Create an empty file if it doesn't exist or bump it's timestamps.

    If no_create is True only bumps the timestamps.
    """
    if no_create or os.access(path, os.F_OK):
        return os.utime(path, None)
    with open(path, 'a'):
        pass

def user_run_dir():
    uid = str(os.getuid())
    return os.path.join(dnf.const.USER_RUNDIR, uid, dnf.const.PROGRAM_NAME)

class tmpdir(object):
    def __init__(self):
        prefix = '%s-' % dnf.const.PREFIX
        self.path = tempfile.mkdtemp(prefix=prefix)

    def __enter__(self):
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        rm_rf(self.path)

class Bunch(dict):
    """Dictionary with attribute accessing syntax.

    In DNF, prefer using this over dnf.yum.misc.GenericHolder.

    Credit: Alex Martelli, Doug Hudgeon

    """
    def __init__(self, *args, **kwds):
         super(Bunch, self).__init__(*args, **kwds)
         self.__dict__ = self

    def __hash__(self):
        return id(self)
