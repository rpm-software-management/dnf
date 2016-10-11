# Copyright (C) 2009, 2012-2016  Red Hat, Inc.
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
# Edited in 2016 - (SWDB) Eduard Cuba <xcubae00@stud.fit.vutbr.cz>

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _, ucd
import hawkey
import time
import glob
import os

from . import misc as misc
import gi
gi.require_version('Dnf', '1.0')
from gi.repository import Dnf
import dnf
import dnf.exceptions
import dnf.rpm.miscutils
import dnf.i18n
import functools
from dnf.yum import swdb_transformer

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

    def _getTransData(self):
        if self._loaded_TD is None:
            self._loaded_TD = sorted(self._history.get_packages_by_tid(self.tid))
        return self._loaded_TD

    trans_data = property(fget=lambda self: self._getTransData())

    def _getCmdline(self):
        if not self._have_loaded_CMD:
            self._have_loaded_CMD = True
            self._loaded_CMD = ucd(self._history.trans_cmdline(self.tid))
        return self._loaded_CMD

    cmdline = property(fget=lambda self: self._getCmdline())

    def _getErrors(self):
        if self._loaded_ER is None:
            self._loaded_ER = self._history.load_error(self.tid)
        return self._loaded_ER
    def _getOutput(self):
        if self._loaded_OT is None:
            self._loaded_OT = self._history.load_output(self.tid)
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
            for pkg in obj.trans_data:
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
        pkg.state = state
        if pkg.state in dnf.history.INSTALLING_STATES:
            pkg.state_installed = True
        if pkg.state in dnf.history.REMOVING_STATES:
            pkg.state_installed = False
        return pkg
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

class SwdbInterface(object):
    def __init__(self, db_path, root='/', releasever=""):
        self.swdb = Dnf.Swdb.new(db_path, releasever)
        self.releasever = releasever
        self.addon_data = _addondata(db_path, root)
        if not self.swdb.exist():
            self.swdb.create_db()
            swdb_transformer.run(output_file=self.swdb.get_path()) #does nothing when there is nothing to transform

    def close(self):
        self.swdb.close()

    def get_path(self):
        return self.swdb.get_path()

    def last(self):
        return self.swdb.last()

    def package_data(self):
        return Dnf.SwdbPkgData()

    def set_repo(self, nvra, repo):
        self.swdb.set_repo(str(nvra), str(repo))

    def checksums_by_nvras(self, nvras):
        return self.swdb.checksums_by_nvras(nvras)

    def old(self, tids=[], limit=0, complete_transactions_only=False):
        tids = list(tids)
        if tids and type(tids[0]) != type(1):
            for i,value in enumerate(tids):
                tids[i] = int(value)
        return self.swdb.trans_old(tids, limit, complete_transactions_only)

    def _log_group_trans(self, tid,  groups_installed=[], groups_removed=[]):
        self.swdb.log_group_trans(tid, groups_installed, groups_removed)
    def set_reason(self, nvra, reason):
        self.swdb.set_reason(str(nvra), reason)

    def pkg_by_nvra(self, nvra): #XXX not used
        return self.swdb.package_by_nvra(str(nvra))

    def repo_by_nvra(self, nvra):
        return self.swdb.repo_by_nvra(str(nvra))

    def pkg_data_by_nvra(self, nvra):
        return self.swdb.package_data_by_nvra(str(nvra))

    def attr_by_nvra(self, attr, nvra):
        return self.swdb.attr_by_nvra(str(attr), str(nvra))

    def beg(self, rpmdb_version, using_pkgs, tsis, skip_packages=[],
            rpmdb_problems=[], cmdline=None, groups_installed=[], groups_removed=[]):
        if cmdline:
            self._tid = self.swdb.trans_beg(str(int(time.time())),str(rpmdb_version),cmdline,str(misc.getloginuid()),self.releasever)
        else:
            self._tid = self.swdb.trans_beg(str(int(time.time())),str(rpmdb_version),"",str(misc.getloginuid()),self.releasever)

        for tsi in tsis:
            for (pkg, state) in tsi._history_iterator():
                pid   = self.pkg2pid(pkg)
                self.swdb.trans_data_beg(self._tid, pid,str(tsi.reason),state)
        self._log_group_trans(self._tid, groups_installed, groups_removed)

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
        return self._pkgtup2pid(po.pkgtup, "", "", create)
    def _hpkg2pid(self, po, create=False):
        return self._apkg2pid(po, create)
    def pkg2pid(self, po, create=True):
        if isinstance(po, Dnf.SwdbPkg):
            return self._hpkg2pid(po, create)
        if po._from_system:
            return self._ipkg2pid(po, create)
        return self._apkg2pid(po, create)

    def log_scriptlet_output(self, msg):
        if msg is None or not hasattr(self, '_tid'):
            return # Not configured to run
        for error in msg.splitlines():
            error = ucd(error)
            self.swdb.log_output(self._tid, error)

    def trans_data_pid_end(self, pid, state):
        if not hasattr(self, '_tid') or state is None:
            return
        self.swdb.trans_data_pid_end(pid, self._tid, state)

    def _log_errors(self, errors):
        for error in errors:
            error = ucd(error)
            self.swdb.log_error(self._tid, error)

    def end(self, end_rpmdb_version="", return_code=0, errors=None):
        assert return_code or not errors
        if not hasattr(self, '_tid'):
            return # Failed at beg() time
        self.swdb.trans_end(self._tid, str(int(time.time())), str(end_rpmdb_version), return_code)
        if not return_code:
            #  Simple hack, if the transaction finished. Note that this
            # catches the erase cases (as we still don't get pkgtups for them),
            # Eg. Updated elements.

            self.swdb.trans_data_end(self._tid)
        if errors is not None:
            self._log_errors(errors)
        del self._tid

    def mark_user_installed(self, pkg, mark):
        self.swdb.mark_user_installed(str(pkg), mark)

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

    def _save_yumdb(self, ipkg, pkg_data):
        """ Save all the data for yumdb for this installed pkg, assumes
            there is no data currently. """
        pid = self.pkg2pid(ipkg, create=False)
        if pid:
            #FIXME: resolve installonly
            self.swdb.log_package_data(pid, pkg_data)
            return True
        else:
            print("PID problem in _save_yumdb, rollback!")
            return False

    def sync_alldb(self, ipkg, pkg_data):
        """ Sync. all the data for rpmdb/yumdb for this installed pkg. """
        if not (self._save_rpmdb(ipkg) and
                self._save_yumdb(ipkg, pkg_data)):
            self._rollback()
            return False
        return True

    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        return self.swdb.search(patterns)

    def user_installed(self, nvra): #boolean if user installed
        return self.swdb.user_installed(str(nvra))

    def select_user_installed(self, pkgs): #indexes of user installed packages from list
        return self.swdb.select_user_installed(pkgs)

    def get_packages_by_tid(self, tid):
        return self.swdb.get_packages_by_tid(tid)

    def trans_cmdline(self, tid):
        return self.swdb.trans_cmdline(tid)

    def load_error(self, tid):
        return self.swdb.load_error(tid)

    def load_output(self, tid):
        return self.swdb.load_output(tid)

class _addondata(object):
    def __init__(self, db_path, root='/'):
        self.conf = misc.GenericHolder()
        self.conf.writable = False
        self._db_date = time.strftime("%Y-%m-%d")
        if not os.path.normpath(db_path).startswith(root):
            self.conf.db_path  = os.path.normpath(root + '/' + db_path)
        else:
            self.conf.db_path = os.path.normpath('/' + db_path)

        self.conf.addon_path = self.conf.db_path + '/' + self._db_date

    def write(self, dataname, data):
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

    def read(self, tid, item=None):
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
