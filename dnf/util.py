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
from __future__ import absolute_import
from __future__ import unicode_literals

from .pycomp import PY3, basestring
from functools import reduce

import dnf.const
import dnf.pycomp
import hawkey
import itertools
import librepo
import os
import shutil
import subprocess
import tempfile
import time

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
        os.makedirs(dname, mode=0o755)

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
        return next(it)
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

def insert_if(item, iterable, condition):
    """Insert an item into an iterable by a condition."""
    for original_item in iterable:
        if condition(original_item):
            yield item
        yield original_item

def is_exhausted(iterator):
    """Test whether an iterator is exhausted."""
    try:
        next(iterator)
    except StopIteration:
        return True
    else:
        return False

def is_glob_pattern(pattern):
    return set(pattern) & set("*[?")

def is_string_type(obj):
    return isinstance(obj, basestring)

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

def log_method_call(log_call):
    def wrapper(fn):
        def new_func(*args, **kwargs):
            name = '%s.%s' % (args[0].__class__.__name__, fn.__name__)
            log_call('Call: %s: %s, %s', name, args[1:], kwargs)
            return fn(*args, **kwargs)
        return new_func
    return wrapper

def mapall(fn, *seq):
    """Like functools.map(), but return a list instead of an iterator.

    This means all side effects of fn take place even without iterating the
    result.

    """
    return list(map(fn, *seq))

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

def partition(pred, iterable):
    """Use a predicate to partition entries into false entries and true entries.

    Credit: Python library itertools' documentation.

    """
    t1, t2 = itertools.tee(iterable)
    return dnf.pycomp.filterfalse(pred, t1), filter(pred, t2)

def reason_name(reason):
    if reason == hawkey.REASON_DEP:
        return "dep"
    if reason == hawkey.REASON_USER:
        return "user"
    raise ValueError("Unknown reason %d" % reason)

def rm_rf(path):
    try:
        shutil.rmtree(path)
    except OSError:
        pass

def split_by(iterable, condition):
    """Split an iterable into tuples by a condition.

    Inserts a separator before each item which meets the condition and then
    cuts the iterable by these separators.

    """
    separator = object()  # A unique object.
    # Create a function returning tuple of objects before the separator.
    def next_subsequence(it):
        return tuple(itertools.takewhile(lambda e: e != separator, it))

    # Mark each place where the condition is met by the separator.
    marked = insert_if(separator, iterable, condition)

    # The 1st subsequence may be empty if the 1st item meets the condition.
    yield next_subsequence(marked)

    while True:
        subsequence = next_subsequence(marked)
        if not subsequence:
            break
        yield subsequence

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

default_handle = librepo.Handle()
default_handle.useragent = dnf.const.USER_AGENT

def urlopen(absurl, repo=None, **kwargs):
    """Open the specified absolute url, return a file object.

    repo -- Use this repo-specific config (proxies, certs)
    kwargs -- These are passed to TemporaryFile
    """
    if PY3:
        kwargs['mode'] = 'w+'
        kwargs['encoding'] = 'utf-8'
    fo = tempfile.NamedTemporaryFile(**kwargs)
    handle = default_handle
    if repo:
        handle = repo.get_handle()
    try:
        librepo.download_url(absurl, fo.fileno(), handle)
    except librepo.LibrepoException as e:
        raise IOError(e.args[1])
    fo.seek(0)
    return fo
