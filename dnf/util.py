# util.py
# Basic dnf utils.
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
from __future__ import absolute_import
from __future__ import unicode_literals

from .pycomp import PY3, basestring
from dnf.i18n import _, ucd
from functools import reduce
import dnf
import dnf.const
import dnf.pycomp
import itertools
import librepo
import locale
import logging
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time

logger = logging.getLogger('dnf')

"""DNF Utilities."""


def _non_repo_handle(conf=None):
    handle = librepo.Handle()
    handle.useragent = dnf.const.USER_AGENT
    # see dnf.repo.Repo._handle_new_remote() how to pass
    if conf:
        handle.maxspeed = conf.throttle if type(conf.throttle) is int \
            else int(conf.bandwidth * conf.throttle)
        handle.proxy = conf.proxy
        handle.proxyuserpwd = dnf.repo._user_pass_str(conf.proxy_username,
                                                      conf.proxy_password)
        handle.sslverifypeer = handle.sslverifyhost = conf.sslverify
    return handle


def _urlopen_progress(url, conf):
    handle = _non_repo_handle(conf)
    handle.repotype = librepo.LR_YUMREPO
    handle.setopt(librepo.LRO_URLS, os.path.dirname(url))
    progress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)
    pload = dnf.repo.RemoteRPMPayload(url, conf, handle, progress)
    if os.path.exists(pload.local_path):
        return pload.local_path
    est_remote_size = sum([pload.download_size])
    progress.start(1, est_remote_size)
    targets = [pload._librepo_target()]
    try:
        librepo.download_packages(targets, failfast=True)
    except librepo.LibrepoException as e:
        if conf.strict:
            raise IOError(e.args[1])
        logger.error(e.args[1])
    return pload.local_path

def _urlopen(url, conf=None, repo=None, mode='w+b', **kwargs):
    """
    Open the specified absolute url, return a file object
    which respects proxy setting even for non-repo downloads
    """
    if PY3 and 'b' not in mode:
        kwargs.setdefault('encoding', 'utf-8')
    fo = tempfile.NamedTemporaryFile(mode, **kwargs)
    if repo:
        handle = repo._get_handle()
    else:
        handle = _non_repo_handle(conf)
    try:
        librepo.download_url(url, fo.fileno(), handle)
    except librepo.LibrepoException as e:
        raise IOError(e.args[1])
    fo.seek(0)
    return fo

def rtrim(s, r):
    if s.endswith(r):
        s = s[:-len(r)]
    return s


def am_i_root():
    return os.geteuid() == 0

def clear_dir(path):
    """Remove all files and dirs under `path`

    Also see rm_rf()

    """
    for entry in os.listdir(path):
        contained_path = os.path.join(path, entry)
        rm_rf(contained_path)

def ensure_dir(dname):
    try:
        os.makedirs(dname, mode=0o755)
    except OSError as e:
        if e.errno != os.errno.EEXIST or not os.path.isdir(dname):
            raise e

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


def first_not_none(iterable):
    it = iter(iterable)
    try:
        return next(item for item in it if item is not None)
    except StopIteration:
        return None


def file_age(fn):
    return time.time() - file_timestamp(fn)

def file_timestamp(fn):
    return os.stat(fn).st_mtime

def get_effective_login():
    return pwd.getpwuid(os.geteuid())[0]

def get_in(dct, keys, not_found):
    """Like dict.get() for nested dicts."""
    for k in keys:
        dct = dct.get(k)
        if dct is None:
            return not_found
    return dct

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
    if is_string_type(pattern):
        pattern = [pattern]
    return (isinstance(pattern, list) and any(set(p) & set("*[?") for p in pattern))

def is_string_type(obj):
    if PY3:
        return isinstance(obj, str)
    else:
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

def normalize_time(timestamp):
    """Convert time into locale aware datetime string object."""
    t = time.strftime("%c", time.localtime(timestamp))
    if not dnf.pycomp.PY3:
        current_locale_setting = locale.getlocale()[1]
        if current_locale_setting:
            t = t.decode(current_locale_setting)
    return t

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


def on_metered_connection():
    """Decide whether we are on metered connection.

    Returns:
      True: if on metered connection
      False: if not
      None: if it can not be decided
    """
    try:
        import dbus
    except ImportError:
        return None
    try:
        bus = dbus.SystemBus()
        proxy = bus.get_object("org.freedesktop.NetworkManager",
                               "/org/freedesktop/NetworkManager")
        iface = dbus.Interface(proxy, "org.freedesktop.DBus.Properties")
        metered = iface.Get("org.freedesktop.NetworkManager", "Metered")
    except dbus.DBusException:
        return None
    if metered == 0: # NM_METERED_UNKNOWN
        return None
    elif metered in (1, 3): # NM_METERED_YES, NM_METERED_GUESS_YES
        return True
    elif metered in (2, 4): # NM_METERED_NO, NM_METERED_GUESS_NO
        return False
    else: # Something undocumented (at least at this moment)
        raise ValueError("Unknown value for metered property: %r", metered)

def partition(pred, iterable):
    """Use a predicate to partition entries into false entries and true entries.

    Credit: Python library itertools' documentation.

    """
    t1, t2 = itertools.tee(iterable)
    return dnf.pycomp.filterfalse(pred, t1), filter(pred, t2)

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


def touch(path, no_create=False):
    """Create an empty file if it doesn't exist or bump it's timestamps.

    If no_create is True only bumps the timestamps.
    """
    if no_create or os.access(path, os.F_OK):
        return os.utime(path, None)
    with open(path, 'a'):
        pass


def _terminal_messenger(tp='write', msg="", out=sys.stdout):
    try:
        if tp == 'write':
            out.write(msg)
        elif tp == 'flush':
            out.flush()
        elif tp == 'write_flush':
            out.write(msg)
            out.flush()
        elif tp == 'print':
            print(msg, file=out)
        else:
            raise ValueError('Unsupported type: ' + tp)
    except IOError as e:
        logger.critical('{}: {}'.format(type(e).__name__, ucd(e)))
        pass


def _format_resolve_problems(resolve_problems):
    """
    Format string about problems in resolve

    :param resolve_problems: list with list of strings (output of goal.problem_rules())
    :return: string
    """
    msg = ""
    count_problems = (len(resolve_problems) > 1)
    for i, rs in enumerate(resolve_problems, start=1):
        if count_problems:
            msg += "\n " + _("Problem") + " %d: " % i
        else:
            msg += "\n " + _("Problem") + ": "
        msg += "\n  - ".join(rs)
    return msg


def _te_nevra(te):
    nevra = te.N() + '-'
    if te.E() is not None and te.E() != '0':
        nevra += te.E() + ':'
    return nevra + te.V() + '-' + te.R() + '.' + te.A()


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


class MultiCallList(list):
    def __init__(self, iterable):
        super(MultiCallList, self).__init__()
        self.extend(iterable)

    def __getattr__(self, what):
        def fn(*args, **kwargs):
            def call_what(v):
                method = getattr(v, what)
                return method(*args, **kwargs)
            return list(map(call_what, self))
        return fn

    def __setattr__(self, what, val):
        def setter(item):
            setattr(item, what, val)
        return list(map(setter, self))
