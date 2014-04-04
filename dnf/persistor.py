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
from dnf.i18n import _

import collections
import dbm
import dnf.util
import errno
import hashlib
import json
import logging
import os

logger = logging.getLogger("dnf")

def _clone_dct(dct):
    cln = {}
    for (k, v) in dct.items():
        if isinstance(v, list):
            cln[k] = v[:]
        elif isinstance(v, dict):
            cln[k] = _clone_dct(v)
        else:
            cln[k] = v
    return cln

class ClonableDict(collections.MutableMapping):
    """A dict with list values that can be cloned.

    This wraps around an ordinary dict (which only gives a shallow copy).

    """

    def __init__(self, dct):
        self.dct = dct

    def __delitem__(self, key):
        del self.dct[key]

    def __getitem__(self, key):
        return self.dct[key]

    def __iter__(self):
        return iter(self.dct)

    def __len__(self):
        return len(self.dct)

    def __setitem__(self, key, val):
        self.dct[key] = val

    @classmethod
    def wrap_dict(cls, dct):
        groups = cls(dct)
        return groups

    def clone(self):
        cls = self.__class__
        return cls.wrap_dict(_clone_dct(self.dct))

class GroupPersistor(object):
    def __init__(self, persistdir):
        self._dbfile = os.path.join(persistdir, 'groups.json')
        self.db = None
        self._original = None
        self._load()
        self._ensure_sanity()

    @staticmethod
    def _empty_db():
        return ClonableDict({
            'ENVIRONMENTS' : {},
            'GROUPS' : {}
        })

    def _ensure_sanity(self):
        """Make sure the input db is valid."""
        if 'GROUPS' in self.db and 'ENVIRONMENTS' in self.db:
            return
        logger.warning(_('Invalid groups database, clearing.'))
        self.db = self._empty_db()

    def _load(self):
        self.db = self._empty_db()
        try:
            with open(self._dbfile) as db:
                content = db.read()
                self.db = ClonableDict.wrap_dict(json.loads(content))
                self._original = self.db.clone()
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

    @property
    def environments(self):
        return self.db['ENVIRONMENTS']

    @property
    def groups(self):
        return self.db['GROUPS']

    def save(self):
        if self.db == self._original:
            return False
        with open(self._dbfile, 'w') as db:
            json.dump(self.db.dct, db)
        return True

class RepoPersistor(object):
    """Persistent data kept for repositories.

    Is arch/releasever specific and stores to cachedir.

    """

    def __init__(self, cachedir):
        self.cachedir = cachedir

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
            logger.warning(_("%s is empty file"), "expired_repos.json")
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
            logger.info("Failed storing last makecache time.")
            return False

    def set_expired_repos(self, expired_iterable):
        self._check_json_db()
        json_path = os.path.join(self.cachedir, "expired_repos.json")
        self._write_json_data(json_path, list(set(expired_iterable)))

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            logger.info("Failed determining last makecache time.")
            return None
