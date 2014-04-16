# callbacks.py
# Abstract interfaces to communicate progress on tasks.
#
# Copyright (C) 2014  Red Hat, Inc.
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

from __future__ import unicode_literals
import dnf.yum.rpmtrans

STATUS_OK = None # :api
STATUS_FAILED = 1 # :api
STATUS_ALREADY_EXISTS = 2 # :api
STATUS_MIRROR = 3  # :api
STATUS_DRPM = 4    # :api

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

# alias for RPM transaction callback that logs things to a file
LoggingTransactionDisplay = dnf.yum.rpmtrans.LoggingTransactionDisplay
