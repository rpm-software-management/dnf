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

from dnf.i18n import ucd, _
import time
import os
from dnf.yum import misc
from hawkey import Swdb, SwdbPkg, SwdbItem, convert_reason
from .swdb_transformer import transformSwdb
from .addondata import AddonData
from .group import GroupPersistor
from dnf.util import logger


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

    def _createdb(self, input_dir):
        """ Create SWDB database if necessary and perform transformation """
        if not self._swdb.exist():
            dbdir = os.path.dirname(self.path)
            if not os.path.exists(dbdir):
                os.makedirs(dbdir)
            self._swdb.create_db()
            # transformation may only run on empty database
            output_file = self._swdb.get_path()
            transformSwdb(input_dir, output_file)

    def _initSwdb(self, input_dir):
        """ Create SWDB object and create database if necessary """
        self._swdb = Swdb.new(self.path, self.releasever)
        self._createdb(input_dir)

    @property
    def swdb(self):
        """ Lazy initialize Swdb object """
        if not self._swdb:
            dbdir = os.path.join(self._root, self._db_dir)
            self._initSwdb(dbdir)
        return self._swdb

    def transform(self, input_dir):
        """ Interface for database transformation """
        if not self._swdb:
            self._initSwdb(input_dir)
        else:
            logger.error(_('Error: database is already initialized'))

    def group_active(self):
        return self._group is not None

    def reset_group(self):
        self._group = GroupPersistor(self.swdb)

    def close(self):
        if not self._swdb:
            return
        return self.swdb.close()

    def add_package(self, pkg):
        return self.swdb.add_package(pkg)

    def update_package_data(self, pid, tid, package_data):
        """ Update Swdb.PkgData for package with pid identifier in transaction tid
            This method must be called after package data initialization using method `beg`
        """
        return self.swdb.update_package_data(pid, tid, package_data)

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
            int(time.time()),
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
            for (pkg, state, obsoleting) in tsi._history_iterator():
                pid = self.pkg2pid(pkg)
                self.swdb.trans_data_beg(
                    tid,
                    pid,
                    convert_reason(tsi.reason),
                    state,
                    obsoleting)
        return tid

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
            int(time.time()),
            str(end_rpmdb_version),
            return_code
        )
        if errors is not None:
            self._log_errors(errors)
        del self._tid

    def _update_ipkg_data(self, ipkg, pkg_data):
        """ Save all the data for yumdb for this installed pkg, assumes
            there is no data currently. """
        pid = self.pkg2pid(ipkg)
        if pid and self._tid:
            # FIXME: resolve installonly
            return self.update_package_data(pid, self._tid, pkg_data)
        return False

    def sync_alldb(self, ipkg, pkg_data):
        """ Sync. yumdb for this installed pkg. """
        return self._update_ipkg_data(ipkg, pkg_data)

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
