#!/usr/bin/python -t
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
#
# Copyright 2009 Red Hat
#
# James Antill <james@fedoraproject.org>

import time
import os, os.path
import glob
from weakref import proxy as weakref

from sqlutils import sqlite, executeSQL, sql_esc_glob
import yum.misc as misc
import yum.constants
from yum.constants import *
from yum.packages import YumInstalledPackage, YumAvailablePackage, PackageObject
from yum.i18n import to_unicode, to_utf8

from rpmUtils.arch import getBaseArch

_history_dir = '/var/lib/yum/history'

# NOTE: That we don't list TS_FAILED, because pkgs shouldn't go into the
#       transaction with that. And if they come out with that we don't want to
#       match them to anything anyway.
_stcode2sttxt = {TS_UPDATE : 'Update',
                 TS_UPDATED : 'Updated', 
                 TS_ERASE: 'Erase',
                 TS_INSTALL: 'Install', 
                 TS_TRUEINSTALL : 'True-Install',
                 TS_OBSOLETED: 'Obsoleted',
                 TS_OBSOLETING: 'Obsoleting'}

_sttxt2stcode = {'Update' : TS_UPDATE,
                 'Updated' : TS_UPDATED, 
                 'Erase' : TS_ERASE,
                 'Install' : TS_INSTALL, 
                 'True-Install' : TS_TRUEINSTALL,
                 'Dep-Install' : TS_INSTALL,
                 'Reinstall' : TS_INSTALL, # Broken
                 'Downgrade' : TS_INSTALL, # Broken
                 'Downgraded' : TS_INSTALL, # Broken
                 'Obsoleted' : TS_OBSOLETED,
                 'Obsoleting' : TS_OBSOLETING}

# ---- horrible Copy and paste from sqlitesack ----

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
        if yum.misc.re_full_search_needed(pat):
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
# ---- horrible Copy and paste from sqlitesack ----

class YumHistoryPackage(PackageObject):

    def __init__(self, name, arch, epoch, version, release, checksum=None):
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
            self._checksums = [(chk[0], chk[1], 0)] # (type, checksum, id(0,1))
        # Needed for equality comparisons in PackageObject
        self.repoid = "<history>"

class YumHistoryPackageState(YumHistoryPackage):
    def __init__(self, name,arch, epoch,version,release, state, checksum=None):
        YumHistoryPackage.__init__(self, name,arch, epoch,version,release,
                                   checksum)
        self.done  = None
        self.state = state

        self.repoid = '<history>'


class YumHistoryRpmdbProblem(PackageObject):
    """ Class representing an rpmdb problem that existed at the time of the
        transaction. """

    def __init__(self, history, rpid, problem, text):
        self._history = weakref(history)

        self.rpid = rpid
        self.problem = problem
        self.text = text

        self._loaded_P = None

    def __cmp__(self, other):
        if other is None:
            return 1
        ret = cmp(self.problem, other.problem)
        if ret: return -ret
        ret = cmp(self.rpid, other.rpid)
        return ret

    def _getProbPkgs(self):
        if self._loaded_P is None:
            self._loaded_P = sorted(self._history._old_prob_pkgs(self.rpid))
        return self._loaded_P

    packages = property(fget=lambda self: self._getProbPkgs())


class YumHistoryTransaction:
    """ Holder for a history transaction. """

    def __init__(self, history, row):
        self._history = weakref(history)

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

    def __cmp__(self, other):
        if other is None:
            return 1
        ret = cmp(self.beg_timestamp, other.beg_timestamp)
        if ret: return -ret
        ret = cmp(self.end_timestamp, other.end_timestamp)
        if ret: return ret
        ret = cmp(self.tid, other.tid)
        return -ret

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
        #  Arch is needed so multilib. works, dito. getBaseArch() -- (so .i586
        # => .i686 moves are seen)
        return (pkg.name, getBaseArch(pkg.arch), state)

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
                                      pkg.epoch,pkg.version,pkg.release, state)
        npkg._checksums = pkg._checksums
        npkg.done = pkg.done
        if _sttxt2stcode[npkg.state] in TS_INSTALL_STATES:
            npkg.state_installed = True
        if _sttxt2stcode[npkg.state] in TS_REMOVE_STATES:
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
        if self.end_timestamp < obj.end_timestamp:
            self.end_timestamp    = obj.end_timestamp
            self.end_rpmdbversion = obj.end_rpmdbversion


class YumHistory:
    """ API for accessing the history sqlite data. """

    def __init__(self, root='/', db_path=_history_dir):
        self._conn = None
        
        self.conf = yum.misc.GenericHolder()
        if not os.path.normpath(db_path).startswith(root):
            self.conf.db_path  = os.path.normpath(root + '/' + db_path)
        else:
            self.conf.db_path = os.path.normpath('/' + db_path)
        self.conf.writable = False
        self.conf.readable = True

        if not os.path.exists(self.conf.db_path):
            try:
                os.makedirs(self.conf.db_path)
            except (IOError, OSError), e:
                # some sort of useful thing here? A warning?
                return
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
                map(int, pieces)
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
            except (IOError, OSError), e:
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

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _pkgtup2pid(self, pkgtup, checksum=None):
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
        
        (n,a,e,v,r) = pkgtup
        (n,a,e,v,r) = (to_unicode(n),to_unicode(a),
                       to_unicode(e),to_unicode(v),to_unicode(r))
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
    def _apkg2pid(self, po):
        csum = po.returnIdSum()
        if csum is not None:
            csum = "%s:%s" % (str(csum[0]), str(csum[1]))
        return self._pkgtup2pid(po.pkgtup, csum)
    def _ipkg2pid(self, po):
        csum = None
        yumdb = po.yumdb_info
        if 'checksum_type' in yumdb and 'checksum_data' in yumdb:
            csum = "%s:%s" % (yumdb.checksum_type, yumdb.checksum_data)
        return self._pkgtup2pid(po.pkgtup, csum)
    def pkg2pid(self, po):
        if isinstance(po, YumInstalledPackage):
            return self._ipkg2pid(po)
        if isinstance(po, YumAvailablePackage):
            return self._apkg2pid(po)
        return self._pkgtup2pid(po.pkgtup, None)

    @staticmethod
    def txmbr2state(txmbr):
        state = None
        if txmbr.output_state in (TS_INSTALL, TS_TRUEINSTALL):
            if txmbr.reinstall:
                state = 'Reinstall'
            elif txmbr.downgrades:
                state = 'Downgrade'
        if txmbr.output_state == TS_ERASE:
            if txmbr.downgraded_by:
                state = 'Downgraded'
        if state is None:
            state = _stcode2sttxt.get(txmbr.output_state)
            if state == 'Install' and txmbr.isDep:
                state = 'Dep-Install'
        return state

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
        # unicode(problem) doesn't work in python 2.4.x ... *sigh*.
        uproblem = to_unicode(problem.__str__())
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
                         VALUES (?, ?)""", (self._tid, to_unicode(cmdline)))
        return cur.lastrowid

    def beg(self, rpmdb_version, using_pkgs, txmbrs, skip_packages=[],
            rpmdb_problems=[], cmdline=None):
        cur = self._get_cursor()
        if cur is None:
            return
        res = executeSQL(cur,
                         """INSERT INTO trans_beg
                            (timestamp, rpmdb_version, loginuid)
                            VALUES (?, ?, ?)""", (int(time.time()),
                                                    str(rpmdb_version),
                                                    yum.misc.getloginuid()))
        self._tid = cur.lastrowid

        for pkg in using_pkgs:
            pid = self._ipkg2pid(pkg)
            self.trans_with_pid(pid)
        
        for txmbr in txmbrs:
            pid   = self.pkg2pid(txmbr.po)
            state = self.txmbr2state(txmbr)
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
            error = to_unicode(error)
            executeSQL(cur,
                       """INSERT INTO trans_error
                          (tid, msg) VALUES (?, ?)""", (self._tid, error))
        self._commit()

    def log_scriptlet_output(self, data, msg):
        """ Note that data can be either a real pkg. ... or not. """
        if msg is None or not hasattr(self, '_tid'):
            return # Not configured to run

        cur = self._get_cursor()
        if cur is None:
            return # Should never happen, due to above
        for error in msg.splitlines():
            error = to_unicode(error)
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
                os.makedirs(tid_dir, mode=0700)
            except (IOError, OSError), e:
                # emit a warning/raise an exception?
                return False
        
        # cleanup dataname
        safename = dataname.replace('/', '_')
        data_fn = tid_dir + '/' + safename
        try:
            # open file in append
            fo = open(data_fn, 'w+')
            # write data
            fo.write(to_utf8(data))
            # flush data
            fo.flush()
            fo.close()
        except (IOError, OSError), e:
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
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5])
            ret.append(obj)
        return ret
    def _old_data_pkgs(self, tid):
        cur = self._get_cursor()
        executeSQL(cur,
                   """SELECT name, arch, epoch, version, release,
                             checksum, done, state
                      FROM trans_data_pkgs JOIN pkgtups USING(pkgtupid)
                      WHERE tid = ?
                      ORDER BY name ASC, epoch ASC, state DESC""", (tid,))
        ret = []
        for row in cur:
            obj = YumHistoryPackageState(row[0],row[1],row[2],row[3],row[4],
                                         row[7], row[5])
            obj.done     = row[6] == 'TRUE'
            obj.state_installed = None
            if _sttxt2stcode[obj.state] in TS_INSTALL_STATES:
                obj.state_installed = True
            if _sttxt2stcode[obj.state] in TS_REMOVE_STATES:
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
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5])
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
            obj = YumHistoryPackage(row[0],row[1],row[2],row[3],row[4], row[5])
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
        if tids and len(tids) <= yum.constants.PATTERNS_INDEXED_MAX:
            params = tids = list(set(tids))
            sql += " WHERE tid IN (%s)" % ", ".join(['?'] * len(tids))
        sql += " ORDER BY beg_ts DESC, tid ASC"
        if limit is not None:
            sql += " LIMIT " + str(limit)
        executeSQL(cur, sql, params)
        ret = []
        tid2obj = {}
        for row in cur:
            if tids and len(tids) > yum.constants.PATTERNS_INDEXED_MAX:
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
        params = tid2obj.keys()
        if len(params) > yum.constants.PATTERNS_INDEXED_MAX:
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
            for npatterns in yum.misc.seq_max_split(patterns, pat_max):
                data = _setupHistorySearchSQL(npatterns, ignore_case)
                (need_full, nps, fields, names) = data
                assert nps
                for row in self._yieldSQLDataList(nps, fields, ignore_case):
                    pkgtupids.add(row[0])

        sql =  """SELECT tid FROM trans_data_pkgs WHERE pkgtupid IN """
        sql += "(%s)" % ",".join(['?'] * len(pkgtupids))
        params = list(pkgtupids)
        tids = set()
        if len(params) > yum.constants.PATTERNS_INDEXED_MAX:
            executeSQL(cur, """SELECT tid FROM trans_data_pkgs""")
            for row in cur:
                if row[0] in params:
                    tids.add(row[0])
            return tids
        if not params:
            return tids
        executeSQL(cur, sql, params)
        for row in cur:
            tids.add(row[0])
        return tids

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
            fo = os.open(self._db_file, os.O_CREAT, 0600)
            os.close(fo)
                
        cur = self._get_cursor()
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
        self._commit()

# Pasted from sqlitesack
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
