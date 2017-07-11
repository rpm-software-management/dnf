# Copyright (C) 2009, 2012-2013  Red Hat, Inc.
#
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
#
# James Antill <james@fedoraproject.org>

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _, ucd
import hawkey
import time
import glob
import os

from .sqlutils import sqlite, executeSQL, sql_esc_glob
from . import misc as misc
import dnf
import dnf.exceptions
import dnf.rpm.miscutils
import dnf.i18n
import functools


#  Cut over for when we should just give up and load everything.
#  The main problem here is not so much SQLite dying (although that happens
# at large values: http://sqlite.org/limits.html#max_variable_number) but that
# but SQLite going really slow when it gets medium sized values (much slower
# than just loading everything and filtering it in python).
PATTERNS_MAX = 8
#  We have another value here because name is indexed and sqlite is _much_
# faster even at large numbers of patterns.
PATTERNS_INDEXED_MAX = 128

def _setupHistorySearchSQL(patterns=None, ignore_case=False):
    """Setup need_full and patterns for _yieldSQLDataList, also see if
       we can get away with just using searchNames(). """

    if patterns is None:
        patterns = []

    fields = ['name', 'sql_nameArch', 'sql_nameVerRelArch',
              'sql_nameVer', 'sql_nameVerRel',
              'sql_envra', 'sql_nevra']
    need_full = False
    for pat in patterns:
        if misc.re_full_search_needed(pat):
            need_full = True
            break

    pat_max = PATTERNS_MAX
    if not need_full:
        fields = ['name']
        pat_max = PATTERNS_INDEXED_MAX
    if len(patterns) > pat_max:
        patterns = []
    if ignore_case:
        patterns = sql_esc_glob(patterns)
    else:
        tmp = []
        need_glob = False
        for pat in patterns:
            if misc.re_glob(pat):
                tmp.append((pat, 'glob'))
                need_glob = True
            else:
                tmp.append((pat, '='))
        if not need_full and not need_glob and patterns:
            return (need_full, patterns, fields, True)
        patterns = tmp
    return (need_full, patterns, fields, False)

class _YumHistPackageYumDB(object):
    """ Class to pretend to be yumdb_info for history packages. """

    def __init__(self, pkg):
        self._pkg = pkg

    _valid_yumdb_keys = set(["command_line",
                             "from_repo", "from_repo_revision",
                             "from_repo_timestamp",
                             "installed_by", "changed_by",
                             "reason", "releasever"])
    def __getattr__(self, attr):
        """ Load yumdb attributes from the history sqlite. """
        pkg = self._pkg
        if attr.startswith('_'):
            raise AttributeError("%s has no yum attribute %s" % (pkg, attr))

        if attr not in self._valid_yumdb_keys:
            raise AttributeError("%s has no yum attribute %s" % (pkg, attr))

        val = pkg._history._load_yumdb_key(pkg, attr)
        if False and val is None:
            raise AttributeError("%s has no yum attribute %s" % (pkg, attr))

        if val is None:
            return None

        val = str(val) or ""
        setattr(self, attr, val)

        return val

    def __contains__(self, attr):
        #  This is faster than __iter__ and it makes things fail in a much more
        # obvious way in weird FS corruption cases like: BZ 593436
        x = self.get(attr)
        return x is not None

    def get(self, attr, default=None):
        """retrieve an add'l data obj"""

        try:
            res = getattr(self, attr)
        except AttributeError:
            return default
        return res

@functools.total_ordering
class YumHistoryPackage(object):

    def __init__(self, name, arch, epoch, version, release, checksum=None,
                 history=None):
        self.name    = name
        self.version = version
        self.release = release
        self.epoch   = epoch
        self.arch    = arch
        self.pkgtup = (self.name, self.arch,
                       self.epoch, self.version, self.release)
        if checksum is None:
            self._checksums = [] # (type, checksum, id(0,1)
        else:
            chk = checksum.split(':')
            self._checksums = [(chk[0], chk[1], 1)] # (type, checksum, id(0,1))
        self.repoid = "<history>"

        self._history = history
        self.yumdb_info = _YumHistPackageYumDB(self)

    _valid_rpmdb_keys = set(["buildtime", "buildhost",
                             "license", "packager",
                             "size", "sourcerpm", "url", "vendor",
                             # ?
                             "committer", "committime"])

    def to_nevra(self):
        return hawkey.NEVRA(self.name, int(self.epoch), self.version,
                            self.release, self.arch)

    def __le__(self, other):
        """Test whether the *self* is less than or equal to the *other*."""
        s = self.to_nevra()
        o = hawkey.NEVRA(other.name, int(other.epoch), other.version,
                         other.release, other.arch)
        if s != o:
            return s < o

        try:
            self_repoid, other_repoid = self.repoid, other.repoid
        except AttributeError:
            return True  # equal

        if self_repoid == other_repoid:
            return True  # equal

        # We want 'installed' to appear over 'abcd' and 'xyz', so boost that
        if self_repoid == 'installed':
            return False  # greater
        if other_repoid == 'installed':
            return True  # less

        return self_repoid < other_repoid  # less or grater

    def __hash__(self):
        return hash(self.pkgtup)

    def __eq__(self, other):
        """ Compare packages for yes/no equality, includes everything in the
            UI package comparison. """
        if not other:
            return False
        if not hasattr(other, 'pkgtup') or self.pkgtup != other.pkgtup:
            return False
        if hasattr(self, 'repoid') and hasattr(other, 'repoid'):
            if self.repoid != other.repoid:
                return False
        return True

    def __getattr__(self, attr):
        """ Load rpmdb attributes from the history sqlite. """
        if attr.startswith('_'):
            raise AttributeError("%s has no attribute %s" % (self, attr))

        if attr not in self._valid_rpmdb_keys:
            raise AttributeError("%s has no attribute %s" % (self, attr))

        val = self._history._load_rpmdb_key(self, attr)
        if False and val is None:
            raise AttributeError("%s has no attribute %s" % (self, attr))

        if val is None:
            return None

        val = str(val) or ""
        setattr(self, attr, val)

        return val

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return ("<%s : %s (%s)>" %
                (self.__class__.__name__, str(self), hex(id(self))))

    def __str__(self):
        return self.ui_envra

    @property
    def envra(self):
        return ('%s:%s-%s-%s.%s' %
                (self.epoch, self.name, self.version, self.release, self.arch))

    @property
    def nevra(self):
        return ('%s-%s:%s-%s.%s' %
                (self.name, self.epoch, self.version, self.release, self.arch))

    @property
    def nvra(self):
        return ('%s-%s-%s.%s' %
                (self.name, self.version, self.release, self.arch))

    def returnIdSum(self):
        for (csumtype, csum, csumid) in self._checksums:
            if csumid:
                return (csumtype, csum)

    @property
    def ui_envra(self):
        if self.epoch == '0':
            return self.nvra
        else:
            return self.envra

    def _ui_from_repo(self):
        """ This reports the repo the package is from, we integrate YUMDB info.
            for RPM packages so a package from "fedora" that is installed has a
            ui_from_repo of "@fedora". Note that, esp. with the --releasever
            option, "fedora" or "rawhide" isn't authoritative.
            So we also check against the current releasever and if it is
            different we also print the YUMDB releasever. This means that
            installing from F12 fedora, while running F12, would report as
            "@fedora/13". """
        if 'from_repo' in self.yumdb_info:
            self._history.releasever
            end = ''
            if (self._history.releasever is not None and
                'releasever' in self.yumdb_info and
                self.yumdb_info.releasever != self._history.releasever):
                end = '/' + self.yumdb_info.releasever
            return '@' + self.yumdb_info.from_repo + end
        return self.repoid
    ui_from_repo = property(fget=lambda self: self._ui_from_repo())

    @property
    def ui_nevra(self):
        if self.epoch == '0':
            return self.nvra
        else:
            return self.nevra


class YumHistoryPackageState(YumHistoryPackage):
    def __init__(self, name,arch, epoch,version,release, state, checksum=None,
                 history=None):
        YumHistoryPackage.__init__(self, name,arch, epoch,version,release,
                                   checksum, history)
        self.done  = None
        self.state = state


class YumHistoryRpmdbProblem(object):
    """ Class representing an rpmdb problem that existed at the time of the
        transaction. """

    def __init__(self, history, rpid, problem, text):
        self._history = history

        self.rpid = rpid
        self.problem = problem
        self.text = text

        self._loaded_P = None

    def __lt__(self, other):
        if other is None:
            return False
        if self.problem == other.problem:
            return self.rpid < other.rpid
        return self.problem > other.problem

    def _getProbPkgs(self):
        if self._loaded_P is None:
            self._loaded_P = sorted(self._history._old_prob_pkgs(self.rpid))
        return self._loaded_P

    packages = property(fget=lambda self: self._getProbPkgs())


class YumHistoryTransaction(object):
    """ Holder for a history transaction. """

    def __init__(self, history, row):
        self._history = history

        self.tid              = row[0]
        self.beg_timestamp    = row[1]
        self.beg_rpmdbversion = row[2]
        self.end_timestamp    = row[3]
        self.end_rpmdbversion = row[4]
        self.loginuid         = row[5]
        self.return_code      = row[6]

        self._loaded_TW = None
        self._loaded_TD = None
        self._loaded_TS = None

        self._loaded_PROB = None

        self._have_loaded_CMD = False # cmdline can validly be None
        self._loaded_CMD = None

        self._loaded_ER = None
        self._loaded_OT = None

        self.altered_lt_rpmdb = None
        self.altered_gt_rpmdb = None

    def __lt__(self, other):
        if other is None:
            return False
        if self.beg_timestamp == other.beg_timestamp:
            if self.end_timestamp == other.end_timestamp:
                return self.tid > other.tid
            else:
                return self.end_timestamp < other.end_timestamp
        else:
            return self.beg_timestamp > other.beg_timestamp

    def _getTransWith(self):
        if self._loaded_TW is None:
            self._loaded_TW = sorted(self._history._old_with_pkgs(self.tid))
        return self._loaded_TW
    def _getTransData(self):
        if self._loaded_TD is None:
            self._loaded_TD = sorted(self._history._old_data_pkgs(self.tid))
        return self._loaded_TD
    def _getTransSkip(self):
        if self._loaded_TS is None:
            self._loaded_TS = sorted(self._history._old_skip_pkgs(self.tid))
        return self._loaded_TS

    trans_with = property(fget=lambda self: self._getTransWith())
    trans_data = property(fget=lambda self: self._getTransData())
    trans_skip = property(fget=lambda self: self._getTransSkip())

    def _getProblems(self):
        if self._loaded_PROB is None:
            self._loaded_PROB = sorted(self._history._old_problems(self.tid))
        return self._loaded_PROB

    rpmdb_problems = property(fget=lambda self: self._getProblems())

    def _getCmdline(self):
        if not self._have_loaded_CMD:
            self._have_loaded_CMD = True
            self._loaded_CMD = self._history._old_cmdline(self.tid)
        return self._loaded_CMD

    cmdline = property(fget=lambda self: self._getCmdline())

    def _getErrors(self):
        if self._loaded_ER is None:
            self._loaded_ER = self._history._load_errors(self.tid)
        return self._loaded_ER
    def _getOutput(self):
        if self._loaded_OT is None:
            self._loaded_OT = self._history._load_output(self.tid)
        return self._loaded_OT

    errors     = property(fget=lambda self: self._getErrors())
    output     = property(fget=lambda self: self._getOutput())

class YumMergedHistoryTransaction(YumHistoryTransaction):
    def __init__(self, obj):
        self._merged_tids = set([obj.tid])
        self._merged_objs = [obj]

        self.beg_timestamp    = obj.beg_timestamp
        self.beg_rpmdbversion = obj.beg_rpmdbversion
        self.end_timestamp    = obj.end_timestamp
        self.end_rpmdbversion = obj.end_rpmdbversion

        self._loaded_TW = None
        self._loaded_TD = None
        #  Hack, this is difficult ... not sure if we want to list everything
        # that was skipped. Just those things which were skipped and then not
        # updated later ... or nothing. Nothing is much easier.
        self._loaded_TS = []

        self._loaded_PROB = None

        self._have_loaded_CMD = False # cmdline can validly be None
        self._loaded_CMD = None

        self._loaded_ER = None
        self._loaded_OT = None

        self.altered_lt_rpmdb = None
        self.altered_gt_rpmdb = None

    def _getAllTids(self):
        return sorted(self._merged_tids)
    tid         = property(fget=lambda self: self._getAllTids())

    def _getLoginUIDs(self):
        ret = set((tid.loginuid for tid in self._merged_objs))
        if len(ret) == 1:
            return list(ret)[0]
        return sorted(ret)
    loginuid    = property(fget=lambda self: self._getLoginUIDs())

    def _getReturnCodes(self):
        ret_codes = set((tid.return_code for tid in self._merged_objs))
        if len(ret_codes) == 1 and 0 in ret_codes:
            return 0
        if 0 in ret_codes:
            ret_codes.remove(0)
        return sorted(ret_codes)
    return_code = property(fget=lambda self: self._getReturnCodes())

    def _getTransWith(self):
        ret = []
        filt = set()
        for obj in self._merged_objs:
            for pkg in obj.trans_with:
                if pkg.pkgtup in filt:
                    continue
                filt.add(pkg.pkgtup)
                ret.append(pkg)
        return sorted(ret)

    # This is the real tricky bit, we want to "merge" so that:
    #     pkgA-1 => pkgA-2
    #     pkgA-2 => pkgA-3
    #     pkgB-1 => pkgB-2
    #     pkgB-2 => pkgB-1
    # ...becomes:
    #     pkgA-1 => pkgA-3
    #     pkgB-1 => pkgB-1 (reinstall)
    # ...note that we just give up if "impossible" things happen, Eg.
    #     pkgA-1 => pkgA-2
    #     pkgA-4 => pkgA-5
    @staticmethod
    def _p2sk(pkg, state=None):
        """ Take a pkg and return the key for it's state lookup. """
        if state is None:
            state = pkg.state
        #  Arch is needed so multilib. works, dito. basearch() -- (so .i586
        # => .i686 moves are seen)
        return (pkg.name, dnf.rpm.basearch(pkg.arch), state)

    @staticmethod
    def _list2dict(pkgs):
        pkgtup2pkg   = {}
        pkgstate2pkg = {}
        for pkg in pkgs:
            key = YumMergedHistoryTransaction._p2sk(pkg)
            pkgtup2pkg[pkg.pkgtup] = pkg
            pkgstate2pkg[key]      = pkg
        return pkgtup2pkg, pkgstate2pkg
    @staticmethod
    def _conv_pkg_state(pkg, state):
        npkg = YumHistoryPackageState(pkg.name, pkg.arch,
                                      pkg.epoch,pkg.version,pkg.release, state,
                                      history=pkg._history)
        npkg._checksums = pkg._checksums
        npkg.done = pkg.done
        if npkg.state in dnf.history.INSTALLING_STATES:
            npkg.state_installed = True
        if npkg.state in dnf.history.REMOVING_STATES:
            npkg.state_installed = False
        return npkg
    @staticmethod
    def _get_pkg(sk, pkgstate2pkg):
        if type(sk) != type((0,1)):
            sk = YumMergedHistoryTransaction._p2sk(sk)
        if sk not in pkgstate2pkg:
            return None
        return pkgstate2pkg[sk]
    def _move_pkg(self, sk, nstate, pkgtup2pkg, pkgstate2pkg):
        xpkg = self._get_pkg(sk, pkgstate2pkg)
        if xpkg is None:
            return
        del pkgstate2pkg[self._p2sk(xpkg)]
        xpkg = self._conv_pkg_state(xpkg, nstate)
        pkgtup2pkg[xpkg.pkgtup] = xpkg
        pkgstate2pkg[self._p2sk(xpkg)] = xpkg

    def _getTransData(self):
        def _get_pkg_f(sk):
            return self._get_pkg(sk, fpkgstate2pkg)
        def _get_pkg_n(sk):
            return self._get_pkg(sk, npkgstate2pkg)
        def _move_pkg_f(sk, nstate):
            self._move_pkg(sk, nstate, fpkgtup2pkg, fpkgstate2pkg)
        def _move_pkg_n(sk, nstate):
            self._move_pkg(sk, nstate, npkgtup2pkg, npkgstate2pkg)
        def _del1_n(pkg):
            del npkgtup2pkg[pkg.pkgtup]
            key = self._p2sk(pkg)
            if key in npkgstate2pkg: # For broken rpmdbv's and installonly
                del npkgstate2pkg[key]
        def _del1_f(pkg):
            del fpkgtup2pkg[pkg.pkgtup]
            key = self._p2sk(pkg)
            if key in fpkgstate2pkg: # For broken rpmdbv's and installonly
                del fpkgstate2pkg[key]
        def _del2(fpkg, npkg):
            assert fpkg.pkgtup == npkg.pkgtup
            _del1_f(fpkg)
            _del1_n(npkg)
        fpkgtup2pkg   = {}
        fpkgstate2pkg = {}
        #  We need to go from oldest to newest here, so we can see what happened
        # in the correct chronological order.
        for obj in self._merged_objs:
            npkgtup2pkg, npkgstate2pkg = self._list2dict(obj.trans_data)

            # Handle Erase => Install, as update/reinstall/downgrade
            for key in list(fpkgstate2pkg.keys()):
                (name, arch, state) = key
                if state not in  ('Obsoleted', 'Erase'):
                    continue
                fpkg = fpkgstate2pkg[key]
                for xstate in ('Install', 'True-Install', 'Dep-Install',
                               'Obsoleting'):
                    npkg = _get_pkg_n(self._p2sk(fpkg, xstate))
                    if npkg is not None:
                        break
                else:
                    continue

                if False: pass
                elif fpkg > npkg:
                    _move_pkg_f(fpkg, 'Downgraded')
                    if xstate != 'Obsoleting':
                        _move_pkg_n(npkg, 'Downgrade')
                elif fpkg < npkg:
                    _move_pkg_f(fpkg, 'Updated')
                    if xstate != 'Obsoleting':
                        _move_pkg_n(npkg, 'Update')
                else:
                    _del1_f(fpkg)
                    if xstate != 'Obsoleting':
                        _move_pkg_n(npkg, 'Reinstall')

            sametups = set(npkgtup2pkg.keys()).intersection(fpkgtup2pkg.keys())
            for pkgtup in sametups:
                if pkgtup not in fpkgtup2pkg or pkgtup not in npkgtup2pkg:
                    continue
                fpkg = fpkgtup2pkg[pkgtup]
                npkg = npkgtup2pkg[pkgtup]
                if False: pass
                elif fpkg.state == 'Reinstall':
                    if npkg.state in ('Reinstall', 'Erase', 'Obsoleted',
                                      'Downgraded', 'Updated'):
                        _del1_f(fpkg)
                elif fpkg.state in ('Obsoleted', 'Erase'):
                    #  Should be covered by above loop which deals with
                    # all goood state changes.
                    good_states = ('Install', 'True-Install', 'Dep-Install',
                                   'Obsoleting')
                    assert npkg.state not in good_states

                elif fpkg.state in ('Install', 'True-Install', 'Dep-Install'):
                    if False: pass
                    elif npkg.state in ('Erase', 'Obsoleted'):
                        _del2(fpkg, npkg)
                    elif npkg.state == 'Updated':
                        _del2(fpkg, npkg)
                        #  Move '*Install' state along to newer pkg. (not for
                        # obsoletes).
                        _move_pkg_n(self._p2sk(fpkg, 'Update'), fpkg.state)
                    elif npkg.state == 'Downgraded':
                        _del2(fpkg, npkg)
                        #  Move '*Install' state along to newer pkg. (not for
                        # obsoletes).
                        _move_pkg_n(self._p2sk(fpkg, 'Downgrade'), fpkg.state)

                elif fpkg.state in ('Downgrade', 'Update', 'Obsoleting'):
                    if False: pass
                    elif npkg.state == 'Reinstall':
                        _del1_n(npkg)
                    elif npkg.state in ('Erase', 'Obsoleted'):
                        _del2(fpkg, npkg)

                        # Move 'Erase'/'Obsoleted' state to orig. pkg.
                        _move_pkg_f(self._p2sk(fpkg, 'Updated'),    npkg.state)
                        _move_pkg_f(self._p2sk(fpkg, 'Downgraded'), npkg.state)

                    elif npkg.state in ('Downgraded', 'Updated'):
                        xfpkg = _get_pkg_f(self._p2sk(fpkg, 'Updated'))
                        if xfpkg is None:
                            xfpkg = _get_pkg_f(self._p2sk(fpkg, 'Downgraded'))
                        if xfpkg is None:
                            if fpkg.state != 'Obsoleting':
                                continue
                            # Was an Install*/Reinstall with Obsoletes
                            xfpkg = fpkg
                        xnpkg = _get_pkg_n(self._p2sk(npkg, 'Update'))
                        if xnpkg is None:
                            xnpkg = _get_pkg_n(self._p2sk(npkg, 'Downgrade'))
                        if xnpkg is None:
                            xnpkg = _get_pkg_n(self._p2sk(npkg, 'Obsoleting'))
                        if xnpkg is None:
                            continue

                        #  Now we have 4 pkgs, f1, f2, n1, n2, and 3 pkgtups
                        # f2.pkgtup == n1.pkgtup. So we need to find out if
                        # f1 => n2 is an Update or a Downgrade.
                        _del2(fpkg, npkg)
                        if xfpkg == xnpkg:
                            nfstate = 'Reinstall'
                            if 'Obsoleting' in (fpkg.state, xnpkg.state):
                                nfstate = 'Obsoleting'
                            if xfpkg != fpkg:
                                _move_pkg_f(xfpkg, nfstate)
                            _del1_n(xnpkg)
                        elif xfpkg < xnpkg:
                            # Update...
                            nfstate = 'Updated'
                            nnstate = 'Update'
                            if 'Obsoleting' in (fpkg.state, xnpkg.state):
                                nnstate = 'Obsoleting'
                            if xfpkg != fpkg:
                                _move_pkg_f(xfpkg, nfstate)
                            _move_pkg_n(xnpkg, nnstate)
                        else:
                            # Downgrade...
                            nfstate = 'Downgraded'
                            nnstate = 'Downgrade'
                            if 'Obsoleting' in (fpkg.state, xnpkg.state):
                                nnstate = 'Obsoleting'
                            if xfpkg != fpkg:
                                _move_pkg_f(xfpkg, nfstate)
                            _move_pkg_n(xnpkg, nnstate)

            for x in npkgtup2pkg:
                fpkgtup2pkg[x] = npkgtup2pkg[x]
            for x in npkgstate2pkg:
                fpkgstate2pkg[x] = npkgstate2pkg[x]
        return sorted(fpkgtup2pkg.values())

    def _getProblems(self):
        probs = set()
        for tid in self._merged_objs:
            for prob in tid.rpmdb_problems:
                probs.add(prob)
        return sorted(probs)

    def _getCmdline(self):
        cmdlines = []
        for tid in self._merged_objs:
            if not tid.cmdline:
                continue
            if cmdlines and cmdlines[-1] == tid.cmdline:
                continue
            cmdlines.append(tid.cmdline)
        if not cmdlines:
            return None
        return cmdlines

    def _getErrors(self):
        ret = []
        for obj in self._merged_objs:
            ret.extend(obj.errors)
        return ret
    def _getOutput(self):
        ret = []
        for obj in self._merged_objs:
            ret.extend(obj.output)
        return ret

    def merge(self, obj):
        if obj.tid in self._merged_tids:
            return # Already done, signal an error?

        self._merged_tids.add(obj.tid)
        self._merged_objs.append(obj)
        # Oldest first...
        self._merged_objs.sort(reverse=True)

        if self.beg_timestamp > obj.beg_timestamp:
            self.beg_timestamp    = obj.beg_timestamp
            self.beg_rpmdbversion = obj.beg_rpmdbversion
        if obj.end_timestamp and self.end_timestamp < obj.end_timestamp:
            self.end_timestamp    = obj.end_timestamp
            self.end_rpmdbversion = obj.end_rpmdbversion


class YumHistory(object):
    """ API for accessing the history sqlite data. """

    def __init__(self, db_path, yumdb, root='/', releasever=None):
        self._conn = None

        self.conf = misc.GenericHolder()
        if not os.path.normpath(db_path).startswith(root):
            self.conf.db_path  = os.path.normpath(root + '/' + db_path)
        else:
            self.conf.db_path = os.path.normpath('/' + db_path)
        self.conf.writable = False
        self.conf.readable = True
        self.yumdb = yumdb

        self.releasever = releasever

        if not os.path.exists(self.conf.db_path):
            try:
                os.makedirs(self.conf.db_path)
            except (IOError, OSError) as e:
                error = dnf.i18n.ucd(e)
                msg = _("Unable to initialize DNF DB history: %s") % error
                raise dnf.exceptions.Error(msg)
            else:
                self.conf.writable = True
        else:
            if os.access(self.conf.db_path, os.W_OK):
                self.conf.writable = True

        DBs = glob.glob('%s/history-*-*-*.sqlite' % self.conf.db_path)
        self._db_file = None
        for d in reversed(sorted(DBs)):
            fname = os.path.basename(d)
            fname = fname[len("history-"):-len(".sqlite")]
            pieces = fname.split('-', 4)
            if len(pieces) != 3:
                continue
            try:
                for piece in pieces:
                    int(piece)
            except ValueError:
                continue

            self._db_date = '%s-%s-%s' % (pieces[0], pieces[1], pieces[2])
            self._db_file = d
            break

        if self._db_file is None:
            self._create_db_file()

        # make an addon path for where we're going to stick
        # random additional history info - probably from plugins and what-not
        self.conf.addon_path = self.conf.db_path + '/' + self._db_date
        if not os.path.exists(self.conf.addon_path):
            try:
                os.makedirs(self.conf.addon_path)
            except (IOError, OSError) as e:
                # some sort of useful thing here? A warning?
                return
        else:
            if os.access(self.conf.addon_path, os.W_OK):
                self.conf.writable = True


    def __del__(self):
        self.close()

    def _get_cursor(self):
        if self._conn is None:
            if not self.conf.readable:
                return None

            try:
                self._conn = sqlite.connect(self._db_file)
            except (sqlite.OperationalError, sqlite.DatabaseError):
                self.conf.readable = False
                return None

            #  Note that this is required due to changing the history DB in the
            # callback for removed txmbrs ... which happens inside the chroot,
            # as against all our other access which is outside the chroot. So
            # we need sqlite to not open the journal.
            #  In theory this sucks, as history could be shared. In reality
            # it's deep yum stuff and there should only be one yum.
            executeSQL(self._conn.cursor(), "PRAGMA locking_mode = EXCLUSIVE")

        return self._conn.cursor()
    def _commit(self):
        return self._conn.commit()
    def _rollback(self):
        return self._conn.rollback()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _pkgtup2pid(self, pkgtup, checksum=None, create=True):
        cur = self._get_cursor()
        executeSQL(cur, """SELECT pkgtupid, checksum FROM pkgtups
                           WHERE name=? AND arch=? AND
                                 epoch=? AND version=? AND release=?""", pkgtup)
        for sql_pkgtupid, sql_checksum in cur:
            if checksum is None and sql_checksum is None:
                return sql_pkgtupid
            if checksum is None:
                continue
            if sql_checksum is None:
                continue
            if checksum == sql_checksum:
                return sql_pkgtupid

        if not create:
            return None

        pkgtup = map(ucd, pkgtup)
        (n,a,e,v,r) = pkgtup
        if checksum is not None:
            res = executeSQL(cur,
                             """INSERT INTO pkgtups
                                (name, arch, epoch, version, release, checksum)
                                VALUES (?, ?, ?, ?, ?, ?)""", (n,a,e,v,r,
                                                               checksum))
        else:
            res = executeSQL(cur,
                             """INSERT INTO pkgtups
                                (name, arch, epoch, version, release)
                                VALUES (?, ?, ?, ?, ?)""", (n,a,e,v,r))
        return cur.lastrowid
    def _apkg2pid(self, po, create=True):
        csum = po.returnIdSum()
        if csum is not None:
            csum = "%s:%s" % (str(csum[0]), str(csum[1]))
        return self._pkgtup2pid(po.pkgtup, csum, create)
    def _ipkg2pid(self, po, create=True):
        csum = None
        yumdb = self.yumdb.get_package(po)
        if 'checksum_type' in yumdb and 'checksum_data' in yumdb:
            csum = "%s:%s" % (yumdb.checksum_type, yumdb.checksum_data)
        return self._pkgtup2pid(po.pkgtup, csum, create)
    def _hpkg2pid(self, po, create=False):
        return self._apkg2pid(po, create)

    def pkg2pid(self, po, create=True):
        if isinstance(po, YumHistoryPackage):
            return self._hpkg2pid(po, create)
        if po._from_system:
            return self._ipkg2pid(po, create)
        return self._apkg2pid(po, create)

    def trans_with_pid(self, pid):
        cur = self._get_cursor()
        if cur is None:
            return None
        res = executeSQL(cur,
                         """INSERT INTO trans_with_pkgs
                         (tid, pkgtupid)
                         VALUES (?, ?)""", (self._tid, pid))
        return cur.lastrowid

    def trans_skip_pid(self, pid):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return None

        res = executeSQL(cur,
                         """INSERT INTO trans_skip_pkgs
                         (tid, pkgtupid)
                         VALUES (?, ?)""", (self._tid, pid))
        return cur.lastrowid

    def trans_data_pid_beg(self, pid, state):
        assert state is not None
        if not hasattr(self, '_tid') or state is None:
            return # Not configured to run
        cur = self._get_cursor()
        if cur is None:
            return # Should never happen, due to above
        res = executeSQL(cur,
                         """INSERT INTO trans_data_pkgs
                         (tid, pkgtupid, state)
                         VALUES (?, ?, ?)""", (self._tid, pid, state))
        return cur.lastrowid
    def trans_data_pid_end(self, pid, state):
        # State can be none here, Eg. TS_FAILED from rpmtrans
        if not hasattr(self, '_tid') or state is None:
            return # Not configured to run

        cur = self._get_cursor()
        if cur is None:
            return # Should never happen, due to above
        res = executeSQL(cur,
                         """UPDATE trans_data_pkgs SET done = ?
                         WHERE tid = ? AND pkgtupid = ? AND state = ?
                         """, ('TRUE', self._tid, pid, state))
        self._commit()

    def _trans_rpmdb_problem(self, problem):
        if not hasattr(self, '_tid'):
            return # Not configured to run
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return None
        # str(problem) doesn't work if problem contains unicode(),
        uproblem = ucd(problem)
        res = executeSQL(cur,
                         """INSERT INTO trans_rpmdb_problems
                         (tid, problem, msg)
                         VALUES (?, ?, ?)""", (self._tid,
                                               problem.problem,
                                               uproblem))
        rpid = cur.lastrowid

        if not rpid:
            return rpid

        pkgs = {}
        pkg = problem.pkg
        pkgs[pkg.pkgtup] = pkg
        if problem.problem == 'conflicts':
            for pkg in problem.conflicts:
                pkgs[pkg.pkgtup] = pkg
        if problem.problem == 'duplicates':
            pkgs[problem.duplicate.pkgtup] = problem.duplicate

        for pkg in pkgs.values():
            pid = self.pkg2pid(pkg)
            if pkg.pkgtup == problem.pkg.pkgtup:
                main = 'TRUE'
            else:
                main = 'FALSE'
            res = executeSQL(cur,
                             """INSERT INTO trans_prob_pkgs
                             (rpid, pkgtupid, main)
                             VALUES (?, ?, ?)""", (rpid, pid, main))

        return rpid

    def _trans_cmdline(self, cmdline):
        if not hasattr(self, '_tid'):
            return # Not configured to run
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return None
        res = executeSQL(cur,
                         """INSERT INTO trans_cmdline
                         (tid, cmdline)
                         VALUES (?, ?)""", (self._tid, ucd(cmdline)))
        return cur.lastrowid

    def beg(self, rpmdb_version, using_pkgs, tsis, skip_packages=[],
            rpmdb_problems=[], cmdline=None):
        cur = self._get_cursor()
        if cur is None:
            return
        res = executeSQL(cur,
                         """INSERT INTO trans_beg
                            (timestamp, rpmdb_version, loginuid)
                            VALUES (?, ?, ?)""", (int(time.time()),
                                                    str(rpmdb_version),
                                                    misc.getloginuid()))
        self._tid = cur.lastrowid

        for pkg in using_pkgs:
            pid = self._ipkg2pid(pkg)
            self.trans_with_pid(pid)

        for tsi in tsis:
            for (pkg, state) in tsi._history_iterator():
                pid   = self.pkg2pid(pkg)
                self.trans_data_pid_beg(pid, state)

        for pkg in skip_packages:
            pid   = self.pkg2pid(pkg)
            self.trans_skip_pid(pid)

        for problem in rpmdb_problems:
            self._trans_rpmdb_problem(problem)

        if cmdline:
            self._trans_cmdline(cmdline)

        self._commit()

    def _log_errors(self, errors):
        cur = self._get_cursor()
        if cur is None:
            return
        for error in errors:
            error = ucd(error)
            executeSQL(cur,
                       """INSERT INTO trans_error
                          (tid, msg) VALUES (?, ?)""", (self._tid, error))
        self._commit()

    def log_scriptlet_output(self, msg):
        if msg is None or not hasattr(self, '_tid'):
            return # Not configured to run

        cur = self._get_cursor()
        if cur is None:
            return # Should never happen, due to above
        for error in msg.splitlines():
            error = ucd(error)
            executeSQL(cur,
                       """INSERT INTO trans_script_stdout
                          (tid, line) VALUES (?, ?)""", (self._tid, error))
        self._commit()

    def _load_errors(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT msg FROM trans_error
                      WHERE tid = ?
                      ORDER BY mid ASC""", (tid,))
        ret = []
        for row in cur:
            ret.append(row[0])
        return ret

    def _load_output(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT line FROM trans_script_stdout
                      WHERE tid = ?
                      ORDER BY lid ASC""", (tid,))
        ret = []
        for row in cur:
            ret.append(row[0])
        return ret

    def end(self, rpmdb_version, return_code, errors=None):
        assert return_code or not errors
        if not hasattr(self, '_tid'):
            return # Failed at beg() time
        cur = self._get_cursor()
        if cur is None:
            return # Should never happen, due to above
        res = executeSQL(cur,
                         """INSERT INTO trans_end
                            (tid, timestamp, rpmdb_version, return_code)
                            VALUES (?, ?, ?, ?)""", (self._tid,int(time.time()),
                                                     str(rpmdb_version),
                                                     return_code))
        self._commit()
        if not return_code:
            #  Simple hack, if the transaction finished. Note that this
            # catches the erase cases (as we still don't get pkgtups for them),
            # Eg. Updated elements.
            executeSQL(cur,
                       """UPDATE trans_data_pkgs SET done = ?
                          WHERE tid = ?""", ('TRUE', self._tid,))
            self._commit()
        if errors is not None:
            self._log_errors(errors)
        del self._tid

    def write_addon_data(self, dataname, data):
        """append data to an arbitrary-named file in the history
           addon_path/transaction id location,
           returns True if write succeeded, False if not"""

        if not hasattr(self, '_tid'):
            # maybe we should raise an exception or a warning here?
            return False

        if not dataname:
            return False

        if not data:
            return False

        # make sure the tid dir exists
        tid_dir = self.conf.addon_path + '/' + str(self._tid)

        if self.conf.writable and not os.path.exists(tid_dir):
            try:
                os.makedirs(tid_dir, mode=0o700)
            except (IOError, OSError) as e:
                # emit a warning/raise an exception?
                return False

        # cleanup dataname
        safename = dataname.replace('/', '_')
        data_fn = tid_dir + '/' + safename
        try:
            # open file in append
            fo = open(data_fn, 'wb+')
            # write data
            fo.write(data.encode('utf-8'))
            # flush data
            fo.flush()
            fo.close()
        except (IOError, OSError) as e:
            return False
        # return
        return True

    def return_addon_data(self, tid, item=None):
        hist_and_tid = self.conf.addon_path + '/' + str(tid) + '/'
        addon_info = glob.glob(hist_and_tid + '*')
        addon_names = [ i.replace(hist_and_tid, '') for i in addon_info ]
        if not item:
            return addon_names

        if item not in addon_names:
            # XXX history needs SOME kind of exception, or warning, I think?
            return None

        fo = open(hist_and_tid + item, 'r')
        data = fo.read()
        fo.close()
        return data

    def _old_with_pkgs(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release, checksum
                      FROM trans_with_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE tid = ?
                      ORDER BY name ASC, epoch ASC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5],
                                    history=self)
            ret.append(obj)
        return ret
    def _old_data_pkgs(self, tid, sort=True):
        cur = self._get_cursor()
        sql = """SELECT name, arch, epoch, version, release,
                        checksum, done, state
                 FROM trans_data_pkgs JOIN pkgtups USING(pkgtupid)
                 WHERE tid = ?"""
        if sort:
            sql = " ".join((sql, "ORDER BY name ASC, epoch ASC, state DESC"))
        executeSQL(cur, sql, (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackageState(row[0],row[1],row[2],row[3],row[4],
                                         row[7], row[5], history=self)
            obj.done     = row[6] == 'TRUE'
            obj.state_installed = None
            if obj.state in dnf.history.INSTALLING_STATES:
                obj.state_installed = True
            if obj.state in dnf.history.REMOVING_STATES:
                obj.state_installed = False
            ret.append(obj)
        return ret
    def _old_skip_pkgs(self, tid):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return []
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release, checksum
                      FROM trans_skip_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE tid = ?
                      ORDER BY name ASC, epoch ASC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5],
                                    history=self)
            ret.append(obj)
        return ret
    def _old_prob_pkgs(self, rpid):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return []
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release, checksum, main
                      FROM trans_prob_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE rpid = ?
                      ORDER BY name ASC, epoch ASC""", (rpid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5],
                                    history=self)
            obj.main = row[6] == 'TRUE'
            ret.append(obj)
        return ret

    def _old_problems(self, tid):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return []
        executeSQL(cur,
                   """SELECT rpid, problem, msg
                      FROM trans_rpmdb_problems
                      WHERE tid = ?
                      ORDER BY problem ASC, rpid ASC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryRpmdbProblem(self, row[0], row[1], row[2])
            ret.append(obj)
        return ret

    def _old_cmdline(self, tid):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_2():
            return None
        executeSQL(cur,
                   """SELECT cmdline
                      FROM trans_cmdline
                      WHERE tid = ?""", (tid,))
        ret = []
        for row in cur:
            return row[0]
        return None

    def old(self, tids=[], limit=None, complete_transactions_only=False):
        """ Return a list of the last transactions, note that this includes
            partial transactions (ones without an end transaction). """
        cur = self._get_cursor()
        if cur is None:
            return []
        sql =  """SELECT tid,
                         trans_beg.timestamp AS beg_ts,
                         trans_beg.rpmdb_version AS beg_rv,
                         trans_end.timestamp AS end_ts,
                         trans_end.rpmdb_version AS end_rv,
                         loginuid, return_code
                  FROM trans_beg JOIN trans_end USING(tid)"""
        # NOTE: sqlite doesn't do OUTER JOINs ... *sigh*. So we have to do it
        #       ourself.
        if not complete_transactions_only:
            sql =  """SELECT tid,
                             trans_beg.timestamp AS beg_ts,
                             trans_beg.rpmdb_version AS beg_rv,
                             NULL, NULL,
                             loginuid, NULL
                      FROM trans_beg"""
        params = None
        if tids and len(tids) <= PATTERNS_INDEXED_MAX:
            params = tids = list(set(tids))
            sql += " WHERE tid IN (%s)" % ", ".join(['?'] * len(tids))
        #  This relies on the fact that the PRIMARY KEY in sqlite will always
        # increase with each transaction. In theory we can use:
        # ORDER BY beg_ts DESC ... except sometimes people do installs with a
        # system clock that is very broken, and using that screws them forever.
        sql += " ORDER BY tid DESC"
        if limit is not None:
            sql += " LIMIT " + str(limit)
        executeSQL(cur, sql, params)
        ret = []
        tid2obj = {}
        for row in cur:
            if tids and len(tids) > PATTERNS_INDEXED_MAX:
                if row[0] not in tids:
                    continue
            obj = YumHistoryTransaction(self, row)
            tid2obj[row[0]] = obj
            ret.append(obj)

        sql =  """SELECT tid,
                         trans_end.timestamp AS end_ts,
                         trans_end.rpmdb_version AS end_rv,
                         return_code
                  FROM trans_end"""
        params = list(tid2obj.keys())
        if len(params) > PATTERNS_INDEXED_MAX:
            executeSQL(cur, sql)
        else:
            sql += " WHERE tid IN (%s)" % ", ".join(['?'] * len(params))
            executeSQL(cur, sql, params)
        for row in cur:
            if row[0] not in tid2obj:
                continue
            tid2obj[row[0]].end_timestamp    = row[1]
            tid2obj[row[0]].end_rpmdbversion = row[2]
            tid2obj[row[0]].return_code      = row[3]

        # Go through backwards, and see if the rpmdb versions match
        las = None
        for obj in reversed(ret):
            cur_rv = obj.beg_rpmdbversion
            las_rv = None
            if las is not None:
                las_rv = las.end_rpmdbversion
            if las_rv is None or cur_rv is None or (las.tid + 1) != obj.tid:
                pass
            elif las_rv != cur_rv:
                obj.altered_lt_rpmdb = True
                las.altered_gt_rpmdb = True
            else:
                obj.altered_lt_rpmdb = False
                las.altered_gt_rpmdb = False
            las = obj

        return ret

    def last(self, complete_transactions_only=True):
        """ This is the last full transaction. So any incomplete transactions
            do not count, by default. """
        ret = self.old([], 1, complete_transactions_only)
        if not ret:
            return None
        assert len(ret) == 1
        return ret[0]

    def _load_anydb_key(self, pkg, db, attr):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_3():
            return None

        pid = self.pkg2pid(pkg, create=False)
        if pid is None:
            return None

        sql = """SELECT %(db)sdb_val FROM pkg_%(db)sdb
                  WHERE pkgtupid=? and %(db)sdb_key=? """ % {'db' : db}
        executeSQL(cur, sql, (pid, attr))
        for row in cur:
            return row[0]

        return None

    def _load_rpmdb_key(self, pkg, attr):
        return self._load_anydb_key(pkg, "rpm", attr)
    def _load_yumdb_key(self, pkg, attr):
        return self._load_anydb_key(pkg, "yum", attr)

    def _save_anydb_key(self, pkg, db, attr, val):
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_3():
            return None

        pid = self.pkg2pid(pkg, create=False)
        if pid is None:
            return None

        sql = """INSERT INTO pkg_%(db)sdb (pkgtupid, %(db)sdb_key, %(db)sdb_val)
                        VALUES (?, ?, ?)""" % {'db' : db}
        executeSQL(cur, sql, (pid, attr, ucd(val)))

        return cur.lastrowid

    def _save_rpmdb(self, ipkg):
        """ Save all the data for rpmdb for this installed pkg, assumes
            there is no data currently. """
        for attr in YumHistoryPackage._valid_rpmdb_keys:
            val = getattr(ipkg, attr, None)
            if val is None:
                continue
            if not self._save_anydb_key(ipkg, "rpm", attr, val):
                return False
        return True

    def _save_yumdb(self, ipkg):
        """ Save all the data for yumdb for this installed pkg, assumes
            there is no data currently. """
        yumdb_info = self.yumdb.get_package(ipkg)
        for attr in _YumHistPackageYumDB._valid_yumdb_keys:
            val = yumdb_info.get(attr)
            if val is None:
                continue
            if not self._save_anydb_key(ipkg, "yum", attr, val):
                return False
        return True

    def _wipe_anydb(self, pkg, db):
        """ Delete all the data for rpmdb/yumdb for this installed pkg. """
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_3():
            return False

        pid = self.pkg2pid(pkg, create=False)
        if pid is None:
            return False

        sql = """DELETE FROM pkg_%(db)sdb WHERE pkgtupid=?""" % {'db' : db}
        executeSQL(cur, sql, (pid,))

        return True

    def sync_alldb(self, ipkg):
        """ Sync. all the data for rpmdb/yumdb for this installed pkg. """
        if not self._wipe_anydb(ipkg, "rpm"):
            return False
        if not (self._wipe_anydb(ipkg, "yum") and
                self._save_rpmdb(ipkg) and
                self._save_yumdb(ipkg)):
            self._rollback()
            return False

        self._commit()
        return True

    def _pkg_stats(self):
        """ Some stats about packages in the DB. """

        ret = {'nevrac' : 0,
               'nevra'  : 0,
               'nevr'   : 0,
               'na'     : 0,
               'rpmdb'  : 0,
               'yumdb'  : 0,
               }
        cur = self._get_cursor()
        if cur is None or not self._update_db_file_3():
            return False

        data = (('nevrac', "COUNT(*)",                      "pkgtups"),
                ('na',     "COUNT(DISTINCT(name || arch))", "pkgtups"),
                ('nevra',"COUNT(DISTINCT(name||version||epoch||release||arch))",
                 "pkgtups"),
                ('nevr',   "COUNT(DISTINCT(name||version||epoch||release))",
                 "pkgtups"),
                ('rpmdb',  "COUNT(DISTINCT(pkgtupid))", "pkg_rpmdb"),
                ('yumdb',  "COUNT(DISTINCT(pkgtupid))", "pkg_yumdb"))

        for key, bsql, esql in data:
            executeSQL(cur, "SELECT %s FROM %s" % (bsql, esql))
            for row in cur:
                ret[key] = row[0]
        return ret

    def _yieldSQLDataList(self, patterns, fields, ignore_case):
        """Yields all the package data for the given params. """

        cur = self._get_cursor()
        qsql = _FULL_PARSE_QUERY_BEG

        pat_sqls = []
        pat_data = []
        for (pattern, rest) in patterns:
            for field in fields:
                if ignore_case:
                    pat_sqls.append("%s LIKE ?%s" % (field, rest))
                else:
                    pat_sqls.append("%s %s ?" % (field, rest))
                pat_data.append(pattern)
        assert pat_sqls

        qsql += " OR ".join(pat_sqls)
        executeSQL(cur, qsql, pat_data)
        for x in cur:
            yield x

    def get_erased_reason(self, pkg, first_trans, rollback):
        """Get reason of package before transaction being undone. If package
        is already installed in the system, keep his reason.

        :param pkg: package being installed
        :param first_trans: id of first transaction being undone
        :param rollback: True if transaction is performing a rollback
        """

        # get transactions of package
        pkg_trans = self.search([pkg.name])

        if not pkg_trans:
            # can't find any transaction with pkg, consider it user installed
            return 'user'

        # check if the transaction was modified since transaction being undone
        if not rollback and max(pkg_trans) > first_trans:
            # modified - if installed, keep its reason
            p = self.yumdb.get_package(pkg)
            if p and p.reason:
                # package installed
                return p.reason

        # package not modified (and assumably not installed)
        # get latest transaction before first one before undone
        latest = 0
        for t in pkg_trans:
            if t > latest and t < first_trans:
                latest = t

        if latest == 0:
            # can't trace origin of package, consider it user installed
            return 'user'

        # latest transaction should install or update the package
        # it was installed before first_trans - thats why we are doing this
        trans_data = self._old_data_pkgs(latest)

        # get installed package from that transaction
        trans_pkg = [p for p in trans_data if p.state_installed and p.name == pkg.name]

        if not trans_pkg:
            # can't find the package, consider it user installed
            return 'user'

        # get yumdb info
        yum_dbinfo = trans_pkg[0].yumdb_info

        return yum_dbinfo.reason or 'user'

    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        # Search packages ... kind of sucks that it's search not list, pkglist?

        cur = self._get_cursor()
        if cur is None:
            return set()

        data = _setupHistorySearchSQL(patterns, ignore_case)
        (need_full, npatterns, fields, names) = data

        ret = []
        pkgtupids = set()

        if npatterns:
            for row in self._yieldSQLDataList(npatterns, fields, ignore_case):
                pkgtupids.add(row[0])
        else:
            # Too many patterns, *sigh*
            pat_max = PATTERNS_MAX
            if not need_full:
                pat_max = PATTERNS_INDEXED_MAX
            for npatterns in misc.seq_max_split(patterns, pat_max):
                data = _setupHistorySearchSQL(npatterns, ignore_case)
                (need_full, nps, fields, names) = data
                assert nps
                for row in self._yieldSQLDataList(nps, fields, ignore_case):
                    pkgtupids.add(row[0])

        sql =  """SELECT tid FROM trans_data_pkgs WHERE pkgtupid IN """
        sql += "(%s)" % ",".join(['?'] * len(pkgtupids))
        params = list(pkgtupids)
        tids = set()
        if len(params) > PATTERNS_INDEXED_MAX:
            executeSQL(cur, """SELECT tid,pkgtupid FROM trans_data_pkgs""")
            for row in cur:
                if row[1] in params:
                    tids.add(row[0])
            return tids
        if not params:
            return tids
        executeSQL(cur, sql, params)
        for row in cur:
            tids.add(row[0])
        return tids

    _update_ops_3 = ['''\
\
 CREATE TABLE pkg_rpmdb (
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups,
     rpmdb_key TEXT NOT NULL,
     rpmdb_val TEXT NOT NULL);
''', '''\
 CREATE INDEX i_pkgkey_rpmdb ON pkg_rpmdb (pkgtupid, rpmdb_key);
''', '''\
 CREATE TABLE pkg_yumdb (
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups,
     yumdb_key TEXT NOT NULL,
     yumdb_val TEXT NOT NULL);
''', '''\
 CREATE INDEX i_pkgkey_yumdb ON pkg_yumdb (pkgtupid, yumdb_key);
''']

# pylint: disable-msg=E0203
    def _update_db_file_3(self):
        """ Update to version 3 of history, rpmdb/yumdb data. """
        if not self._update_db_file_2():
            return False

        if hasattr(self, '_cached_updated_3'):
            return self._cached_updated_3

        cur = self._get_cursor()
        if cur is None:
            return False

        executeSQL(cur, "PRAGMA table_info(pkg_yumdb)")
        #  If we get anything, we're fine. There might be a better way of
        # saying "anything" but this works.
        for ob in cur:
            break
        else:
            for op in self._update_ops_3:
                cur.execute(op)
            self._commit()
        self._cached_updated_3 = True
        return True

    _update_ops_2 = ['''\
\
 CREATE TABLE trans_skip_pkgs (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups);
''', '''\
\
 CREATE TABLE trans_cmdline (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     cmdline TEXT NOT NULL);
''', '''\
\
 CREATE TABLE trans_rpmdb_problems (
     rpid INTEGER PRIMARY KEY,
     tid INTEGER NOT NULL REFERENCES trans_beg,
     problem TEXT NOT NULL, msg TEXT NOT NULL);
''', '''\
\
 CREATE TABLE trans_prob_pkgs (
     rpid INTEGER NOT NULL REFERENCES trans_rpmdb_problems,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups,
     main BOOL NOT NULL DEFAULT FALSE);
''', '''\
\
 CREATE VIEW vtrans_data_pkgs AS
     SELECT tid,name,epoch,version,release,arch,pkgtupid,
            state,done,
            name || '-' || epoch || ':' ||
            version || '-' || release || '.' || arch AS nevra
     FROM trans_data_pkgs JOIN pkgtups USING(pkgtupid)
     ORDER BY name;
''', '''\
\
 CREATE VIEW vtrans_with_pkgs AS
     SELECT tid,name,epoch,version,release,arch,pkgtupid,
            name || '-' || epoch || ':' ||
            version || '-' || release || '.' || arch AS nevra
     FROM trans_with_pkgs JOIN pkgtups USING(pkgtupid)
     ORDER BY name;
''', '''\
\
 CREATE VIEW vtrans_skip_pkgs AS
     SELECT tid,name,epoch,version,release,arch,pkgtupid,
            name || '-' || epoch || ':' ||
            version || '-' || release || '.' || arch AS nevra
     FROM trans_skip_pkgs JOIN pkgtups USING(pkgtupid)
     ORDER BY name;
''', # NOTE: Old versions of sqlite don't like the normal way to do the next
     #       view. So we do it with the select. It's for debugging only, so
     #       no big deal.
'''\
\
 CREATE VIEW vtrans_prob_pkgs2 AS
     SELECT tid,rpid,name,epoch,version,release,arch,pkgtups.pkgtupid,
            main,problem,msg,
            name || '-' || epoch || ':' ||
            version || '-' || release || '.' || arch AS nevra
     FROM (SELECT * FROM trans_prob_pkgs,trans_rpmdb_problems WHERE
           trans_prob_pkgs.rpid=trans_rpmdb_problems.rpid)
           JOIN pkgtups USING(pkgtupid)
     ORDER BY name;
''']

    def _update_db_file_2(self):
        """ Update to version 2 of history, includes trans_skip_pkgs. """
        if not self.conf.writable:
            return False

        if hasattr(self, '_cached_updated_2'):
            return self._cached_updated_2

        cur = self._get_cursor()
        if cur is None:
            return False

        executeSQL(cur, "PRAGMA table_info(trans_skip_pkgs)")
        #  If we get anything, we're fine. There might be a better way of
        # saying "anything" but this works.
        for ob in cur:
            break
        else:
            for op in self._update_ops_2:
                cur.execute(op)
            self._commit()
        self._cached_updated_2 = True
        return True

# pylint: enable-msg=E0203

    def _create_db_file(self):
        """ Create a new history DB file, populating tables etc. """

        self._db_date = time.strftime('%Y-%m-%d')
        _db_file = '%s/%s-%s.%s' % (self.conf.db_path,
                                    'history',
                                    self._db_date,
                                    'sqlite')
        if self._db_file == _db_file:
            os.rename(_db_file, _db_file + '.old')
            # Just in case ... move the journal file too.
            if os.path.exists(_db_file + '-journal'):
                os.rename(_db_file  + '-journal', _db_file + '-journal.old')
        self._db_file = _db_file

        if self.conf.writable and not os.path.exists(self._db_file):
            # make them default to 0600 - sysadmin can change it later
            # if they want
            fo = os.open(self._db_file, os.O_CREAT, 0o600)
            os.close(fo)

        cur = self._get_cursor()
        if cur is None:
            raise IOError(_("Can not create history database at '%s'.") % \
                          self._db_file)

        ops = ['''\
 CREATE TABLE trans_beg (
     tid INTEGER PRIMARY KEY,
     timestamp INTEGER NOT NULL, rpmdb_version TEXT NOT NULL,
     loginuid INTEGER);
''', '''\
 CREATE TABLE trans_end (
     tid INTEGER PRIMARY KEY REFERENCES trans_beg,
     timestamp INTEGER NOT NULL, rpmdb_version TEXT NOT NULL,
     return_code INTEGER NOT NULL);
''', '''\
\
 CREATE TABLE trans_with_pkgs (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups);
''', '''\
\
 CREATE TABLE trans_error (
     mid INTEGER PRIMARY KEY,
     tid INTEGER NOT NULL REFERENCES trans_beg,
     msg TEXT NOT NULL);
''', '''\
 CREATE TABLE trans_script_stdout (
     lid INTEGER PRIMARY KEY,
     tid INTEGER NOT NULL REFERENCES trans_beg,
     line TEXT NOT NULL);
''', '''\
\
 CREATE TABLE trans_data_pkgs (
     tid INTEGER NOT NULL REFERENCES trans_beg,
     pkgtupid INTEGER NOT NULL REFERENCES pkgtups,
     done BOOL NOT NULL DEFAULT FALSE, state TEXT NOT NULL);
''', '''\
\
 CREATE TABLE pkgtups (
     pkgtupid INTEGER PRIMARY KEY,     name TEXT NOT NULL, arch TEXT NOT NULL,
     epoch TEXT NOT NULL, version TEXT NOT NULL, release TEXT NOT NULL,
     checksum TEXT);
''', '''\
 CREATE INDEX i_pkgtup_naevr ON pkgtups (name, arch, epoch, version, release);
''']
        for op in ops:
            cur.execute(op)
        for op in self._update_ops_2:
            cur.execute(op)
        for op in self._update_ops_3:
            cur.execute(op)
        self._commit()

_FULL_PARSE_QUERY_BEG = """
SELECT pkgtupid,name,epoch,version,release,arch,
  name || "." || arch AS sql_nameArch,
  name || "-" || version || "-" || release || "." || arch AS sql_nameVerRelArch,
  name || "-" || version AS sql_nameVer,
  name || "-" || version || "-" || release AS sql_nameVerRel,
  epoch || ":" || name || "-" || version || "-" || release || "." || arch AS sql_envra,
  name || "-" || epoch || ":" || version || "-" || release || "." || arch AS sql_nevra
  FROM pkgtups
  WHERE
"""
