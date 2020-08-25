# persistor.py
# Persistence data container.
#
# Copyright (C) 2013-2020 Red Hat, Inc.
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
# specific files existing, instead use the persistor API. The underlying
# implementation can change, e.g. for one general file with a serialized dict of
# data etc.

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _
import distutils.version
import dnf.util

import errno
import fnmatch
import json
import logging
import os
import re


logger = logging.getLogger("dnf")


class JSONDB(object):

    def _get_json_db(self, json_path, default=None):
        if default is None:
            default = []

        try:
            with open(json_path, 'r') as f:
                result = json.load(f)
        except FileNotFoundError:
            # data on disk not found, use the default value
            result = default
        except Exception:
            # unable to deserialize data on disk, use the default value
            logger.warning(_("%s doesn't have a valid JSON format"), json_path)
            result = default
        return result

    @staticmethod
    def _write_json_db(json_path, content):
        if not os.path.isfile(json_path):
            dnf.util.ensure_dir(os.path.dirname(json_path))
        with open(json_path, 'w') as f:
            json.dump(content, f)


class RepoPersistor(JSONDB):
    """Persistent data kept for repositories.

    Is arch/releasever specific and stores to cachedir.

    """

    def __init__(self, cachedir):
        self.cachedir = cachedir
        self.db_path = os.path.join(self.cachedir, "expired_repos.json")
        self.expired_to_add = set()
        self.reset_last_makecache = False

    @property
    def _last_makecache_path(self):
        return os.path.join(self.cachedir, "last_makecache")

    def get_expired_repos(self):
        return set(self._get_json_db(self.db_path))

    def save(self):
        self._write_json_db(self.db_path, list(self.expired_to_add))
        if self.reset_last_makecache:
            try:
                dnf.util.touch(self._last_makecache_path)
                return True
            except IOError:
                logger.info(_("Failed storing last makecache time."))
                return False

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            logger.info(_("Failed determining last makecache time."))
            return None


class TempfilePersistor(JSONDB):

    def __init__(self, cachedir):
        self.db_path = os.path.join(cachedir, "tempfiles.json")
        self.tempfiles_to_add = set()
        self._empty = False

    def get_saved_tempfiles(self):
        return self._get_json_db(self.db_path)

    def save(self):
        if not self._empty and not self.tempfiles_to_add:
            return
        if self._empty:
            self._write_json_db(self.db_path, [])
            return
        if self.tempfiles_to_add:
            data = set(self._get_json_db(self.db_path))
            data.update(self.tempfiles_to_add)
            self._write_json_db(self.db_path, list(data))

    def empty(self):
        self._empty = True
