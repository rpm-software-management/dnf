# callbacks.py
# Abstract interfaces to communicate progress on tasks.
#
# Copyright (C) 2014-2015  Red Hat, Inc.
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
from __future__ import unicode_literals
from dnf.i18n import _
import dnf.yum.rpmtrans
import sys

PKG_CLEANUP = dnf.yum.rpmtrans.TransactionDisplay.PKG_CLEANUP  # :api
PKG_DOWNGRADE = dnf.yum.rpmtrans.TransactionDisplay.PKG_DOWNGRADE  # :api
PKG_INSTALL = dnf.yum.rpmtrans.TransactionDisplay.PKG_INSTALL  # :api
PKG_OBSOLETE = dnf.yum.rpmtrans.TransactionDisplay.PKG_OBSOLETE  # :api
PKG_REINSTALL = dnf.yum.rpmtrans.TransactionDisplay.PKG_REINSTALL  # :api
PKG_REMOVE = dnf.yum.rpmtrans.TransactionDisplay.PKG_ERASE  # :api
PKG_UPGRADE = dnf.yum.rpmtrans.TransactionDisplay.PKG_UPGRADE  # :api
PKG_VERIFY = dnf.yum.rpmtrans.TransactionDisplay.PKG_VERIFY  # :api

STATUS_OK = None # :api
STATUS_FAILED = 1 # :api
STATUS_ALREADY_EXISTS = 2 # :api
STATUS_MIRROR = 3  # :api
STATUS_DRPM = 4    # :api

TRANS_POST = dnf.yum.rpmtrans.TransactionDisplay.TRANS_POST  # :api


class KeyImport(object):
    def confirm(self, _keyinfo):
        """Ask the user if the key should be imported."""
        return False


class Payload(object):
    # :api

    def __init__(self, progress):
        self.progress = progress

    def __str__(self):
        """Nice, human-readable representation. :api"""
        pass

    @property
    def download_size(self):
        """Total size of the download. :api"""
        pass


class DownloadProgress(object):
    # :api

    def end(self, payload, status, msg):
        """Communicate the information that `payload` has finished downloading.

        :api, `status` is a constant denoting the type of outcome, `err_msg` is an
        error message in case the outcome was an error.

        """
        pass

    def message(self, msg):
        pass

    def progress(self, payload, done):
        """Update the progress display. :api

        `payload` is the payload this call reports progress for, `done` is how
        many bytes of this payload are already downloaded.

        """

        pass

    def start(self, total_files, total_size):
        """Start new progress metering. :api

        `total_files` the number of files that will be downloaded,
        `total_size` total size of all files.

        """

        pass


class NullDownloadProgress(DownloadProgress):
    pass


class Depsolve(object):
    def start(self):
        pass

    def pkg_added(self, pkg, mode):
        pass

    def end(self):
        pass

# :deprecated in 1.1.0, eligible for dropping in 2.0
# de facto API - never documented but used by Anaconda thanks to us
class LoggingTransactionDisplay(dnf.yum.rpmtrans.LoggingTransactionDisplay):

    def __init__(self):
        super(LoggingTransactionDisplay, self).__init__()
        self.action = {self.PKG_CLEANUP: _('Cleanup'),
                       self.PKG_DOWNGRADE: _('Downgrading'),
                       self.PKG_ERASE: _('Erasing'),
                       self.PKG_INSTALL: _('Installing'),
                       self.PKG_OBSOLETE: _('Obsoleting'),
                       self.PKG_REINSTALL: _('Reinstalling'),
                       self.PKG_UPGRADE: _('Upgrading'),
                       self.PKG_VERIFY: _('Verifying')}

    def error(self, message):
        super(LoggingTransactionDisplay, self).error(message)
        # Compatibility: Originally, "error" was "errorlog". Let's call it in
        # case somebody overrides it.
        self.errorlog(message)

    def errorlog(self, msg):
        # Compatibility: Originally, "error" was "errorlog". Let's define it in
        # case somebody extends it.
        print(msg, file=sys.stderr)

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # Compatibility: Originally, "progress" was "event". Let's define it in
        # case somebody extends it.
        pass

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        super(LoggingTransactionDisplay, self).progress(
            package, action, ti_done, ti_total, ts_done, ts_total)
        # Compatibility: Originally, "progress" was "event". Let's call it in
        # case somebody overrides it.
        self.event(package, action, ti_done, ti_total, ts_done, ts_total)


TransactionProgress = dnf.yum.rpmtrans.TransactionDisplay  # :api
