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

import dnf.util
import logging
import os

class Persistor(object):
    def __init__(self, persist_dir):
        self.persist_dir = persist_dir
        self.verbose_logger = logging.getLogger("yum.verbose.Base")

    @property
    def _last_makecache_path(self):
        return os.path.join(self.persist_dir, "last_makecache")

    def reset_last_makecache(self):
        try:
            dnf.util.touch(self._last_makecache_path)
            return True
        except IOError:
            self.verbose_logger.info("Failed storing last makecache time.")
            return False

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            self.verbose_logger.info("Failed determining last makecache time.")
            return None
