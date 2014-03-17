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
# specific files existing, instead use the persistor API. The underlying
# implementation can change, e.g. for one general file with a serialized dict of
# data etc.

from __future__ import absolute_import
from dnf.yum.i18n import _

import dbm
import dnf.util
import errno
import json
import logging
import os

logger = logging.getLogger("dnf")

class GroupPersistor(object):
    def __init__(self, persistdir):
        self.db = os.path.join(persistdir, 'groups.json')
        self.groups = {}
        self._load()

    def _load(self):
        self.groups = {}
        try:
            with open(self.db) as db:
                content = db.read()
                self.groups = json.loads(content)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

    def save(self):
        with open(self.db, 'w') as db:
            json.dump(self.groups, db)

class RepoPersistor(object):
    """Persistent data kept for repositories.

    Is arch/releasever specific and stores to cachedir.

    """

    def __init__(self, cachedir):
        self.cachedir = cachedir
        self.logger = logging.getLogger("dnf")

    def _check_json_db(self):
        json_path = os.path.join(self.cachedir, "expired_repos.json")
        if not os.path.isfile(json_path):
            # inicialize new db
            dnf.util.ensure_dir(self.cachedir)
            self._write_json_data(json_path, [])

    def _get_expired_from_json(self):
        json_path = os.path.join(self.cachedir, "expired_repos.json")
        f = open(json_path, 'r')
        content = f.read()
        f.close()
        if content == "":
            data = []
            self.logger.warning(_("%s is empty file"), "expired_repos.json")
            self._write_json_data(json_path, data)
        else:
            data = json.loads(content)
        return set(data)

    def _write_json_data(self, path, expired_repos):
        f = open(path, 'w')
        json.dump(expired_repos, f)
        f.close()

    @property
    def _last_makecache_path(self):
        return os.path.join(self.cachedir, "last_makecache")

    def get_expired_repos(self):
        self._check_json_db()
        return self._get_expired_from_json()

    def reset_last_makecache(self):
        try:
            dnf.util.touch(self._last_makecache_path)
            return True
        except IOError:
            self.logger.info("Failed storing last makecache time.")
            return False

    def set_expired_repos(self, expired_iterable):
        self._check_json_db()
        json_path = os.path.join(self.cachedir, "expired_repos.json")
        self._write_json_data(json_path, list(set(expired_iterable)))

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            self.logger.info("Failed determining last makecache time.")
            return None
