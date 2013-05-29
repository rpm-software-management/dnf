# conf.py
# Persistence data container.
#
# Copyright (C) 2013  Red Hat, Inc.
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

# The current implementation is storing to files in persistdir. Do not depend on
# specific files existing, instead use the Persistor's API. The underlying
# implementation can change, e.g. for one general file with a serialized dict of
# data etc.

from __future__ import absolute_import
import dnf.util
import logging
import os
import shelve

class Persistor(object):
    def __init__(self, cachedir):
        self.cachedir = cachedir
        self.logger = logging.getLogger("dnf")

    def _expired_repos(self):
        dnf.util.ensure_dir(self.cachedir)
        path = os.path.join(self.cachedir, "expired_repos")
        return shelve.open(path)

    @property
    def _last_makecache_path(self):
        return os.path.join(self.cachedir, "last_makecache")

    def get_expired_repos(self):
        shelf = self._expired_repos()
        exp = shelf.get('expired_repos', set())
        shelf.close()
        return exp

    def reset_last_makecache(self):
        try:
            dnf.util.touch(self._last_makecache_path)
            return True
        except IOError:
            self.logger.info("Failed storing last makecache time.")
            return False

    def set_expired_repos(self, expired_iterable):
        set_expired = set(expired_iterable)
        shelf = self._expired_repos()
        shelf['expired_repos'] = set_expired
        shelf.close()

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            self.logger.info("Failed determining last makecache time.")
            return None
