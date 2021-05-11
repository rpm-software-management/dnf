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
import argparse
import dnf
import dnf.callback
import dnf.const
import dnf.pycomp
import errno
import functools
import hawkey
import itertools
import locale
import logging
import os
import pwd
import shutil
import sys
import tempfile
import time
import libdnf.repo
import libdnf.transaction

logger = logging.getLogger('dnf')

MAIN_PROG = argparse.ArgumentParser().prog if argparse.ArgumentParser().prog == "yum" else "dnf"
MAIN_PROG_UPPER = MAIN_PROG.upper()

"""DNF Utilities."""


def _parse_specs(namespace, values):
    """
    Categorize :param values list into packages, groups and filenames

    :param namespace: argparse.Namespace, where specs will be stored
    :param values: list of specs, whether packages ('foo') or groups/modules ('@bar')
                   or filenames ('*.rmp', 'http://*', ...)

    To access packages use: specs.pkg_specs,
    to access groups use: specs.grp_specs,
    to access filenames use: specs.filenames
    """

    setattr(namespace, "filenames", [])
    setattr(namespace, "grp_specs", [])
    setattr(namespace, "pkg_specs", [])
    tmp_set = set()
    for value in values:
        if value in tmp_set:
            continue
        tmp_set.add(value)
        schemes = dnf.pycomp.urlparse.urlparse(value)[0]
        if value.endswith('.rpm'):
            namespace.filenames.append(value)
        elif schemes and schemes in ('http', 'ftp', 'file', 'https'):
            namespace.filenames.append(value)
        elif value.startswith('@'):
            namespace.grp_specs.append(value[1:])
        else:
            namespace.pkg_specs.append(value)


def _urlopen_progress(url, conf, progress=None):
    if progress is None:
        progress = dnf.callback.NullDownloadProgress()
    pload = dnf.repo.RemoteRPMPayload(url, conf, progress)
    est_remote_size = sum([pload.download_size])
    progress.start(1, est_remote_size)
    targets = [pload._librepo_target()]
    try:
        libdnf.repo.PackageTarget.downloadPackages(libdnf.repo.VectorPPackageTarget(targets), True)
    except RuntimeError as e:
        if conf.strict:
            raise IOError(str(e))
        logger.error(str(e))
    return pload.local_path

def _urlopen(url, conf=None, repo=None, mode='w+b', **kwargs):
    """
    Open the specified absolute url, return a file object
    which respects proxy setting even for non-repo downloads
    """
    if PY3 and 'b' not in mode:
        kwargs.setdefault('encoding', 'utf-8')
    fo = tempfile.NamedTemporaryFile(mode, **kwargs)

    try:
        if repo:
            repo._repo.downloadUrl(url, fo.fileno())
        else:
            libdnf.repo.Downloader.downloadURL(conf._config if conf else None, url, fo.fileno())
    except RuntimeError as e:
        raise IOError(str(e))

    fo.seek(0)
    return fo

def rtrim(s, r):
    if s.endswith(r):
        s = s[:-len(r)]
    return s


def am_i_root():
    # used by ansible (lib/ansible/modules/packaging/os/dnf.py)
    return os.geteuid() == 0

def clear_dir(path):
    """Remove all files and dirs under `path`

    Also see rm_rf()

    """
    for entry in os.listdir(path):
        contained_path = os.path.join(path, entry)
        rm_rf(contained_path)

def ensure_dir(dname):
    # used by ansible (lib/ansible/modules/packaging/os/dnf.py)
    try:
        os.makedirs(dname, mode=0o755)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(dname):
            raise e


def split_path(path):
    """
    Split path by path separators.
    Use os.path.join() to join the path back to string.
    """
    result = []

    head = path
    while True:
        head, tail = os.path.split(head)
        if not tail:
            if head or not result:
                # if not result: make sure result is [""] so os.path.join(*result) can be called
                result.insert(0, head)
            break
        result.insert(0, tail)

    return result


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
    try:
        return pwd.getpwuid(os.geteuid())[0]
    except KeyError:
        return "UID: %s" % os.geteuid()

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
    return functools.reduce(splitter, iterable, ([], []))

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
        ps_folder = "/sys/class/power_supply"
        ac_nodes = [node for node in os.listdir(ps_folder) if node.startswith("AC")]
        if len(ac_nodes) > 0:
            ac_node = ac_nodes[0]
            with open("{}/{}/online".format(ps_folder, ac_node)) as ac_status:
                data = ac_status.read()
                return int(data) == 1
        return None
    except (IOError, ValueError):
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


def _log_rpm_trans_with_swdb(rpm_transaction, swdb_transaction):
    logger.debug("Logging transaction elements")
    for rpm_el in rpm_transaction:
        tsi = rpm_el.Key()
        tsi_state = None
        if tsi is not None:
            tsi_state = tsi.state
        msg = "RPM element: '{}', Key(): '{}', Key state: '{}', Failed() '{}': ".format(
            _te_nevra(rpm_el), tsi, tsi_state, rpm_el.Failed())
        logger.debug(msg)
    for tsi in swdb_transaction:
        msg = "SWDB element: '{}', State: '{}', Action: '{}', From repo: '{}', Reason: '{}', " \
              "Get reason: '{}'".format(str(tsi), tsi.state, tsi.action, tsi.from_repo, tsi.reason,
                                        tsi.get_reason())
        logger.debug(msg)


def _sync_rpm_trans_with_swdb(rpm_transaction, swdb_transaction):
    revert_actions = {libdnf.transaction.TransactionItemAction_DOWNGRADED,
                      libdnf.transaction.TransactionItemAction_OBSOLETED,
                      libdnf.transaction.TransactionItemAction_REMOVE,
                      libdnf.transaction.TransactionItemAction_UPGRADED,
                      libdnf.transaction.TransactionItemAction_REINSTALLED}
    cached_tsi = [tsi for tsi in swdb_transaction]
    el_not_found = False
    error = False
    for rpm_el in rpm_transaction:
        te_nevra = _te_nevra(rpm_el)
        tsi = rpm_el.Key()
        if tsi is None or not hasattr(tsi, "pkg"):
            for tsi_candidate in cached_tsi:
                if tsi_candidate.state != libdnf.transaction.TransactionItemState_UNKNOWN:
                    continue
                if tsi_candidate.action not in revert_actions:
                    continue
                if str(tsi_candidate) == te_nevra:
                    tsi = tsi_candidate
                    break
        if tsi is None or not hasattr(tsi, "pkg"):
            logger.critical(_("TransactionItem not found for key: {}").format(te_nevra))
            el_not_found = True
            continue
        if rpm_el.Failed():
            tsi.state = libdnf.transaction.TransactionItemState_ERROR
            error = True
        else:
            tsi.state = libdnf.transaction.TransactionItemState_DONE
    for tsi in cached_tsi:
        if tsi.state == libdnf.transaction.TransactionItemState_UNKNOWN:
            logger.critical(_("TransactionSWDBItem not found for key: {}").format(str(tsi)))
            el_not_found = True
    if error:
        logger.debug(_('Errors occurred during transaction.'))
    if el_not_found:
        _log_rpm_trans_with_swdb(rpm_transaction, cached_tsi)


class tmpdir(object):
    # used by subscription-manager (src/dnf-plugins/product-id.py)
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


def _make_lists(transaction):
    b = Bunch({
        'downgraded': [],
        'erased': [],
        'erased_clean': [],
        'erased_dep': [],
        'installed': [],
        'installed_group': [],
        'installed_dep': [],
        'installed_weak': [],
        'reinstalled': [],
        'upgraded': [],
        'failed': [],
    })

    for tsi in transaction:
        if tsi.state == libdnf.transaction.TransactionItemState_ERROR:
            b.failed.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_DOWNGRADE:
            b.downgraded.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_INSTALL:
            if tsi.reason == libdnf.transaction.TransactionItemReason_GROUP:
                b.installed_group.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_DEPENDENCY:
                b.installed_dep.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_WEAK_DEPENDENCY:
                b.installed_weak.append(tsi)
            else:
                # TransactionItemReason_USER
                b.installed.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_REINSTALL:
            b.reinstalled.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_REMOVE:
            if tsi.reason == libdnf.transaction.TransactionItemReason_CLEAN:
                b.erased_clean.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_DEPENDENCY:
                b.erased_dep.append(tsi)
            else:
                b.erased.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_UPGRADE:
            b.upgraded.append(tsi)

    return b


def _post_transaction_output(base, transaction, action_callback):
    """Returns a human-readable summary of the results of the
    transaction.

    :param action_callback: function generating output for specific action. It
       takes two parameters - action as a string and list of affected packages for
       this action
    :return: a list of lines containing a human-readable summary of the
       results of the transaction
    """
    def _tsi_or_pkg_nevra_cmp(item1, item2):
        """Compares two transaction items or packages by nevra.
           Used as a fallback when tsi does not contain package object.
        """
        ret = (item1.name > item2.name) - (item1.name < item2.name)
        if ret != 0:
            return ret
        nevra1 = hawkey.NEVRA(name=item1.name, epoch=item1.epoch, version=item1.version,
                              release=item1.release, arch=item1.arch)
        nevra2 = hawkey.NEVRA(name=item2.name, epoch=item2.epoch, version=item2.version,
                              release=item2.release, arch=item2.arch)
        ret = nevra1.evr_cmp(nevra2, base.sack)
        if ret != 0:
            return ret
        return (item1.arch > item2.arch) - (item1.arch < item2.arch)

    list_bunch = dnf.util._make_lists(transaction)

    skipped_conflicts, skipped_broken = base._skipped_packages(
        report_problems=False, transaction=transaction)
    skipped = skipped_conflicts.union(skipped_broken)

    out = []
    for (action, tsis) in [(_('Upgraded'), list_bunch.upgraded),
                           (_('Downgraded'), list_bunch.downgraded),
                           (_('Installed'), list_bunch.installed +
                            list_bunch.installed_group +
                            list_bunch.installed_weak +
                            list_bunch.installed_dep),
                           (_('Reinstalled'), list_bunch.reinstalled),
                           (_('Skipped'), skipped),
                           (_('Removed'), list_bunch.erased +
                               list_bunch.erased_dep +
                               list_bunch.erased_clean),
                           (_('Failed'), list_bunch.failed)]:
        out.extend(action_callback(
            action, sorted(tsis, key=functools.cmp_to_key(_tsi_or_pkg_nevra_cmp))))

    return out


def _name_unset_wrapper(input_name):
    # returns <name-unset> for everything that evaluates to False (None, empty..)
    return input_name if input_name else _("<name-unset>")
