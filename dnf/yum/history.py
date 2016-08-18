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
import gi
gi.require_version("Hif", "3.0")
from gi.repository import Hif
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

        val = pkg._history.swdb.get_pkg_attr(pkg, attr)
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
        self.pid = 0
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
        pid = self._history.pkg2pid(self.pkgtup)
        val = self._history.swdb.get_pkg_attr(pid, attr)
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
            self._loaded_TW = sorted(self._history.swdb.get_packages_by_tid(self.tid))
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
            self._loaded_CMD = ucd(self._history.swdb.trans_cmdline(self.tid))
        return self._loaded_CMD

    cmdline = property(fget=lambda self: self._getCmdline())

    def _getErrors(self):
        if self._loaded_ER is None:
            self._loaded_ER = self._history.swdb.load_error(self.tid)
        return self._loaded_ER
    def _getOutput(self):
        if self._loaded_OT is None:
            self._loaded_OT = self._history.swdb.load_output(self.tid)
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
                if pkg.pid in filt:
                    continue
                filt.add(pkg.pid)
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
        self.swdb = Hif.Swdb()
        if not self.swdb.exist():
            self.swdb.create_db()
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

    def _pkgtup2pid(self, pkgtup, checksum="", checksum_type="", create=True):
        pkgtup = map(ucd, pkgtup)
        (n,a,e,v,r) = pkgtup
        return self.swdb.get_pid_by_nevracht(n,str(e),str(v),str(r),a,checksum,checksum_type,"rpm",create)

    def _apkg2pid(self, po, create=True):
        csum = po.returnIdSum()
        csum_type = None
        if csum is not None:
            csum_type = csum[0]
            csum = csum[1]
        else:
            csum = ""
            csum_type = ""
        return self._pkgtup2pid(po.pkgtup, csum, csum_type, create)
    def _ipkg2pid(self, po, create=True):
        csum = None
        csum_type = None
        yumdb = self.yumdb.get_package(po)
        if 'checksum_type' in yumdb and 'checksum_data' in yumdb:
            csum_type = yumdb.checksum_type
            csum = yumdb.checksum_data
        else:
            csum = ""
            csum_type = ""
        return self._pkgtup2pid(po.pkgtup, csum, csum_type, create)
    def _hpkg2pid(self, po, create=False):
        return self._apkg2pid(po, create)
    def pkg2pid(self, po, create=True):
        if isinstance(po, YumHistoryPackage):
            return self._hpkg2pid(po, create)
        if po._from_system:
            return self._ipkg2pid(po, create)
        return self._apkg2pid(po, create)

    def trans_data_pid_end(self, pid, state):
        if not hasattr(self, '_tid') or state is None:
            return
        self.swdb.trans_data_pid_end(pid, self._tid, state)

    def beg(self, rpmdb_version, using_pkgs, tsis, skip_packages=[],
            rpmdb_problems=[], cmdline=None):
        if cmdline:
            self._tid = self.swdb.trans_beg(str(int(time.time())),str(rpmdb_version),cmdline,str(misc.getloginuid()),self.releasever)
        else:
            self._tid = self.swdb.trans_beg(str(int(time.time())),str(rpmdb_version),"",str(misc.getloginuid()),self.releasever)

        for tsi in tsis:
            for (pkg, state) in tsi._history_iterator():
                pid   = self.pkg2pid(pkg)
                yumdb_info = self.yumdb.get_package(pkg)
                self.swdb.trans_data_beg(self._tid, pid,(yumdb_info.get("reason") or "unknown") ,state)

    def _log_errors(self, errors):
        for error in errors:
            error = ucd(error)
            self.swdb.log_error(self._tid, error)

    def log_scriptlet_output(self, msg):
        if msg is None or not hasattr(self, '_tid'):
            return # Not configured to run
        for error in msg.splitlines():
            error = ucd(error)
            self.swdb.log_output(self._tid, error)

    def end(self, rpmdb_version, return_code, errors=None):
        assert return_code or not errors
        if not hasattr(self, '_tid'):
            return # Failed at beg() time
        self.swdb.trans_end(self._tid, str(int(time.time())), return_code)
        #self._commit()
        if not return_code:
            #  Simple hack, if the transaction finished. Note that this
            # catches the erase cases (as we still don't get pkgtups for them),
            # Eg. Updated elements.

            self.swdb.trans_data_end(self._tid)
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
        if cur is None:
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
        if cur is None:
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
        if cur is None:
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
        print("----------")
        print(len(ret))
        tid_list = list(tids)
        print(len(self.swdb.trans_old(tid_list,(limit or 0),complete_transactions_only)))
        print("----------")
        return self.swdb.trans_old(list(tids),(limit or 0),complete_transactions_only)

    def last(self, complete_transactions_only=True):
        """ This is the last full transaction. So any incomplete transactions
            do not count, by default. """
        ret = self.old([], 1, complete_transactions_only)
        if not ret:
            return None
        assert len(ret) == 1
        return ret[0]

    def _save_rpmdb(self, ipkg):
        """ Save all the data for rpmdb for this installed pkg, assumes
            there is no data currently. """
        pid = self.pkg2pid(ipkg, create=False)
        if pid:
            if not self.swdb.log_rpm_data( pid, str((getattr(ipkg, "buildtime" , None) or '')),
                                                str((getattr(ipkg, "buildhost" , None) or '')),
                                                str((getattr(ipkg, "license" , None) or '')),
                                                str((getattr(ipkg, "packager" , None) or '')),
                                                str((getattr(ipkg, "size" , None) or '')),
                                                str((getattr(ipkg, "sourcerpm" , None) or '')),
                                                str((getattr(ipkg, "url" , None) or '')),
                                                str((getattr(ipkg, "vendor" , None) or '')),
                                                str((getattr(ipkg, "committer" , None) or '')),
                                                str((getattr(ipkg, "committime" , None) or ''))):
                return True
        print("PID problem in _save_yumdb, rollback!")
        return False

    def _save_yumdb(self, ipkg):
        """ Save all the data for yumdb for this installed pkg, assumes
            there is no data currently. """
        yumdb_info = self.yumdb.get_package(ipkg)
        pid = self.pkg2pid(ipkg, create=False)
        if pid:
            #FIXME: resolve installonly
            tmp_instalonly = ""
            self.swdb.log_package_data(pid, (yumdb_info.get("from_repo") or ''),
                (yumdb_info.get("from_repo_revision") or ''),
                (yumdb_info.get("from_repo_timestamp") or ''), (yumdb_info.get("installed_by") or ''),
                (yumdb_info.get("changed_by") or ''), tmp_instalonly, "")
            return True
        else:
            print("PID problem in _save_yumdb, rollback!")
            return False

    def sync_alldb(self, ipkg):
        """ Sync. all the data for rpmdb/yumdb for this installed pkg. """
        if not (self._save_rpmdb(ipkg) and
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
        if cur is None:
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

    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        return self.swdb.search(patterns)
