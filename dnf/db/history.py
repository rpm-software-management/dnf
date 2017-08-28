# Copyright (C) 2009, 2012-2017  Red Hat, Inc.
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
# Eduard Cuba <ecuba@redhat.com>

from dnf.i18n import ucd
import time
import os
from dnf.yum import misc
from .swdb_transformer import run as transformdb
from .addondata import AddonData
from .group import GroupPersistor
from .types import Swdb, SwdbRpmData, SwdbPkg, SwdbItem, convert_reason


class SwdbInterface(object):

    def __init__(self, db_dir, root='/', releasever="", transform=True):
        self.path = os.path.join(root, db_dir, "swdb.sqlite")
        self.releasever = str(releasever)
        self._group = None
        self._addon_data = None
        self._swdb = None
        self._db_dir = db_dir
        self._root = root
        self._transform = transform

    @property
    def group(self):
        if not self._group:
            self._group = GroupPersistor(self.swdb)
        return self._group

    @property
    def addon_data(self):
        if not self._addon_data:
            self._addon_data = AddonData(self._db_dir, self._root)
        return self._addon_data

    @property
    def swdb(self):
        if not self._swdb:
            self._swdb = Swdb.new(self.path, self.releasever)
            if not self._swdb.exist():
                dbdir = os.path.dirname(self.path)
                if not os.path.exists(dbdir):
                    os.makedirs(dbdir)
                self._swdb.create_db()
                # does nothing when there is nothing to transform
                if self._transform:
                    transformdb(output_file=self._swdb.get_path())
        return self._swdb

    def group_active(self):
        return self._group is not None

    def reset_group(self):
        self._group = GroupPersistor(self.swdb)

    def close(self):
        return self.swdb.close()

    def add_package(self, pkg):
        return self.swdb.add_package(pkg)

    def add_package_data(self, pid, package_data):
        return self.swdb.log_package_data(pid, package_data)

    def reset_db(self):
        return self.swdb.reset_db()

    def get_path(self):
        return self.swdb.get_path()

    def last(self, complete_transactions_only=True):
        return self.swdb.last(complete_transactions_only)

    def set_repo(self, pkg, repo):
        """Set repository for package"""
        return self.swdb.set_repo(str(pkg), repo)

    def checksums(self, packages):
        """Get checksum list of desired packages.
        Returns: List is in format
            [checksum1_type, checksum1_data, checksum2_type, checksum2_data, ...]
        """
        return self.swdb.checksums([str(pkg) for pkg in packages])

    def old(self, tids=[], limit=0, complete_transactions_only=False):
        tids = list(tids)
        if tids and not isinstance(tids[0], int):
            for i, value in enumerate(tids):
                tids[i] = int(value)
        return self.swdb.trans_old(tids, limit, complete_transactions_only)

    def _log_group_trans(self, tid):
        installed = self.group.groups_installed
        removed = self.group.groups_removed
        self.swdb.log_group_trans(tid, installed, removed)

    def set_reason(self, pkg, reason):
        """Set reason for package"""
        return self.swdb.set_reason(str(pkg), reason)

    def package(self, pkg):
        """Get SwdbPackage from package"""
        return self.swdb.package(str(pkg))

    def repo(self, pkg):
        """Get repository of package"""
        return self.swdb.repo(str(pkg))

    def package_data(self, pkg):
        """Get package data for package"""
        return self.swdb.package_data(str(pkg))

    def reason(self, pkg):
        """Get reason for package"""
        return self.swdb.reason(str(pkg))

    def ipkg_to_rpmdata(self, ipkg):
        pid = self.pkg2pid(ipkg, create=False)
        rpmdata = SwdbRpmData.new(
            pid,
            str((getattr(ipkg, "buildtime", None) or '')),
            str((getattr(ipkg, "buildhost", None) or '')),
            str((getattr(ipkg, "license", None) or '')),
            str((getattr(ipkg, "packager", None) or '')),
            str((getattr(ipkg, "size", None) or '')),
            str((getattr(ipkg, "sourcerpm", None) or '')),
            str((getattr(ipkg, "url", None) or '')),
            str((getattr(ipkg, "vendor", None) or '')),
            str((getattr(ipkg, "committer", None) or '')),
            str((getattr(ipkg, "committime", None) or ''))
        )
        return rpmdata

    def ipkg_to_pkg(self, ipkg):
        try:
            csum = ipkg.returnIdSum()
        except AttributeError:
            csum = ('', '')
        pkgtup = map(ucd, ipkg.pkgtup)
        (n, a, e, v, r) = pkgtup
        pkg = SwdbPkg.new(
            n,
            int(e),
            v,
            r,
            a,
            csum[1] or '',
            csum[0] or '',
            SwdbItem.RPM)
        return pkg

    def beg(self, rpmdb_version, using_pkgs, tsis, cmdline=None):
        tid = self.swdb.trans_beg(
            str(int(time.time())),
            str(rpmdb_version),
            cmdline or "",
            str(misc.getloginuid()),
            self.releasever)

        self._tid = tid

        for pkg in using_pkgs:
            pid = self.pkg2pid(pkg)
            self.swdb.trans_with(tid, pid)

        if self.group:
            self._log_group_trans(tid)

        for tsi in tsis:
            for (pkg, state) in tsi._history_iterator():
                pid = self.pkg2pid(pkg)
                self.swdb.trans_data_beg(
                    tid,
                    pid,
                    convert_reason(tsi.reason),
                    state
                )

    def pkg2pid(self, po, create=True):
        if hasattr(po, 'pid') and po.pid:
            return po.pid
        # try to find package in DB by its nevra
        pid = self.swdb.pid_by_nevra(str(po))
        if pid or not create:
            return pid
        # pkg not found in db - create new object
        if not isinstance(po, SwdbPkg):
            po = self.ipkg_to_pkg(po)
        return self.swdb.add_package(po)

    def log_scriptlet_output(self, msg):
        if msg is None or not hasattr(self, '_tid'):
            return  # Not configured to run
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
            return  # Failed at beg() time
        self.swdb.trans_end(
            self._tid,
            str(int(time.time())),
            str(end_rpmdb_version),
            return_code
        )
        if errors is not None:
            self._log_errors(errors)
        del self._tid

    def mark_user_installed(self, pkg, mark):
        """(Un)mark package as user installed"""
        return self.swdb.mark_user_installed(str(pkg), mark)

    def _save_rpmdb(self, ipkg):
        """ Save all the data for rpmdb for this installed pkg, assumes
            there is no data currently. """
        return not self.swdb.add_rpm_data(self.ipkg_to_rpmdata(ipkg))

    def add_pkg_data(self, ipkg, pkg_data):
        """ Save all the data for yumdb for this installed pkg, assumes
            there is no data currently. """
        pid = self.pkg2pid(ipkg, create=False)
        if pid:
            # FIXME: resolve installonly
            return self.swdb.log_package_data(pid, pkg_data)

    def sync_alldb(self, ipkg, pkg_data):
        """ Sync. all the data for rpmdb/yumdb for this installed pkg. """
        return self._save_rpmdb(ipkg) and self.add_pkg_data(ipkg, pkg_data)

    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        return self.swdb.search(patterns)

    def user_installed(self, pkg):
        """Returns True if package is user installed"""
        return self.swdb.user_installed(str(pkg))

    def select_user_installed(self, pkgs):
        """Select user installed packages from list of pkgs"""

        # swdb.select_user_installed returns indexes of user installed packages
        return [pkgs[i] for i in self.swdb.select_user_installed([str(pkg) for pkg in pkgs])]

    def get_packages_by_tid(self, tid):
        if isinstance(tid, list):
            packages = []
            for t in tid:
                packages += self.swdb.get_packages_by_tid(t)
            return packages
        return self.swdb.get_packages_by_tid(tid)

    def trans_cmdline(self, tid):
        if isinstance(tid, list):
            cmdlines = []
            for t in tid:
                cmdlines.append(self.swdb.trans_cmdline(t))
            return cmdlines
        return self.swdb.trans_cmdline(tid)

    def get_erased_reason(self, pkg, first_trans, rollback):
        """Get reason of package before transaction being undone. If package
        is already installed in the system, keep his reason.

        :param pkg: package being installed
        :param first_trans: id of first transaction being undone
        :param rollback: True if transaction is performing a rollback"""
        return self.swdb.get_erased_reason(str(pkg), first_trans, rollback)
