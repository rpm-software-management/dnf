# persistor.py
# Persistence data container.
#
# Copyright (C) 2013-2016 Red Hat, Inc.
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

import collections
import distutils.version
import dnf.util
import errno
import fnmatch
import json
import logging
import os
import re

logger = logging.getLogger("dnf")


def _by_pattern(pattern, ids, lookup_fn, case_sensitive):
    pattern = dnf.i18n.ucd(pattern)

    exact = {id for id in ids if lookup_fn(id).name == pattern or id == pattern}
    if exact:
        return exact

    if case_sensitive:
        match = re.compile(fnmatch.translate(pattern)).match
    else:
        match = re.compile(fnmatch.translate(pattern), flags=re.I).match

    return {id for id in ids if match(lookup_fn(id).name) or
            match(lookup_fn(id).ui_name) or match(id)}


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


def _diff_dcts(dct1, dct2):
    """Specific kind of diff between the two dicts.

    Namely, differences between values of non-collections are not considered.

    """

    added = {}
    removed = {}
    keys1 = set(dct1.keys())
    keys2 = set(dct2.keys())

    for key in keys2 - keys1:
        added[key] = dct2[key]
    for key in keys1 - keys2:
        removed[key] = dct1[key]
    for key in keys1 & keys2:
        val1 = dct1[key]
        val2 = dct2[key]
        if type(val1) is type(val2) is dict:
            added_dct, removed_dct = _diff_dcts(val1, val2)
            if added_dct:
                added[key] = added_dct
            if removed_dct:
                removed[key] = removed_dct
        elif type(val1) is type(val2) is list:
            set1 = set(val1)
            set2 = set(val2)
            added_set = set2 - set1
            if added_set:
                added[key] = added_set
            removed_set = set1 - set2
            if removed_set:
                removed[key] = removed_set

    return added, removed


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


class _PersistMember(object):
    DEFAULTS = ClonableDict({
        'name' : '',
        'ui_name' : '',
        'full_list' : [],
        'grp_types' : 0,
        'pkg_exclude' : [],
        'pkg_types' : 0,
    })

    @staticmethod
    def default():
        return _PersistMember.DEFAULTS.clone().dct

    def __init__(self, param_dct):
        self.param_dct = param_dct

    @property
    def name(self):
        return self.param_dct['name']

    @name.setter
    def name(self, val):
        self.param_dct['name'] = val

    @property
    def ui_name(self):
        return self.param_dct['ui_name']

    @ui_name.setter
    def ui_name(self, val):
        self.param_dct['ui_name'] = val

    @property
    def pkg_exclude(self):
        return self.param_dct['pkg_exclude']

    @property
    def full_list(self):
        return self.param_dct['full_list']

    @property
    def installed(self):
        return self.grp_types | self.pkg_types != 0

    @property
    def grp_types(self):
        return self.param_dct['grp_types']

    @grp_types.setter
    def grp_types(self, val):
        self.param_dct['grp_types'] = val

    @property
    def pkg_types(self):
        return self.param_dct['pkg_types']

    @pkg_types.setter
    def pkg_types(self, val):
        self.param_dct['pkg_types'] = val


class _GroupsDiff(object):
    def __init__(self, db_old, db_new):
        self.added, self.removed = _diff_dcts(db_old, db_new)

    def _diff_keys(self, what, removing):
        added = set(self.added.get(what, {}).keys())
        removed = set(self.removed.get(what, {}).keys())
        if removing:
            return list(removed - added)
        return list(added-removed)

    def empty(self):
        return not self.new_environments and not self.removed_environments and \
            not self.new_groups and not self.removed_groups

    @property
    def new_environments(self):
        return self._diff_keys('ENVIRONMENTS', False)

    @property
    def removed_environments(self):
        return self._diff_keys('ENVIRONMENTS', True)

    @property
    def new_groups(self):
        return self._diff_keys('GROUPS', False)

    @property
    def removed_groups(self):
        return self._diff_keys('GROUPS', True)

    def added_packages(self, group_id):
        keys = ('GROUPS', group_id, 'full_list')
        return dnf.util.get_in(self.added, keys, set())

    def removed_packages(self, group_id):
        keys = ('GROUPS', group_id, 'full_list')
        return dnf.util.get_in(self.removed, keys, set())


class GroupPersistor(object):

    @staticmethod
    def _empty_db():
        return ClonableDict({
            'ENVIRONMENTS' : {},
            'GROUPS' : {},
            'meta' : {'version' : '0.6.0'}
        })

    def __init__(self, persistdir, comps=None):
        self._commit = False
        self._comps = comps
        self._dbfile = os.path.join(persistdir, 'groups.json')
        self.db = None
        self._original = None
        self._load()
        self._ensure_sanity()

    def _access(self, subdict, id_):
        subdict = self.db[subdict]
        dct = subdict.get(id_)
        if dct is None:
            dct = _PersistMember.default()
            subdict[id_] = dct

        return _PersistMember(dct)

    def _add_missing_entries(self):
        for env_id in self.db['ENVIRONMENTS']:
            env = self.environment(env_id)
            for key in env.DEFAULTS.keys():
                try:
                    getattr(env, key)
                except KeyError:
                    if self._comps:
                        try:
                            comps_env = self._comps._environment_by_id(env_id)
                            if comps_env:
                                value = getattr(comps_env, key)
                                setattr(env, key, value)
                                continue
                        except KeyError:
                            # set default if env is not pressent in comps
                            pass
                    setattr(env, key, env.DEFAULTS[key])
        for grp_id in self.db['GROUPS']:
            grp = self.group(grp_id)
            for key in grp.DEFAULTS.keys():
                try:
                    getattr(grp, key)
                except KeyError:
                    if self._comps:
                        try:
                            comps_grp = self._comps._group_by_id(grp_id)
                            if comps_grp:
                                value = getattr(comps_grp, key)
                                setattr(grp, key, value)
                                continue
                        except KeyError:
                            # set default if grp is not pressent in comps
                            pass
                    setattr(grp, key, grp.DEFAULTS[key])

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
                self._migrate()
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
        self._original = self.db.clone()

    def _migrate(self):
        try:
            version = self.db['meta']['version']
        except KeyError:
            msg = _('Unsupported installed groups database found, resetting.')
            logger.warning(msg)
            self.db = self._empty_db()
            version = self.db['meta']['version']
        else:
            current = self._empty_db()['meta']['version']
            dist = distutils.version.LooseVersion
            if dist(version) < dist(current):
                logger.debug('Migrating group persistor from %s to %s. ',
                             version, current)
                self._add_missing_entries()
                self.db['meta']['version'] = current
                self.commit()
                self.save()

        logger.debug('group persistor md version: %s', version)

    def _prune_db(self):
        for members_dct in (self.db['ENVIRONMENTS'], self.db['GROUPS']):
            del_list = []
            for (id_, memb) in members_dct.items():
                if not _PersistMember(memb).installed:
                    del_list.append(id_)
            for id_ in del_list:
                del members_dct[id_]

    def _rollback(self):
        self.db = self._original.clone()

    def commit(self):
        self._commit = True

    def diff(self):
        return _GroupsDiff(self._original, self.db)

    def environment(self, id_):
        return self._access('ENVIRONMENTS', id_)

    @property
    def environments(self):
        return self.db['ENVIRONMENTS']

    def environments_by_pattern(self, pattern, case_sensitive=False):
        return _by_pattern(pattern, self.environments,
                           self.environment, case_sensitive)

    def update_group_env_installed(self, installed, goal):
        """add to the persistor packages that are already installed or are
           being installed by group transaction"""
        ins = {p.name for p in set(goal.list_installs()).union(set(installed))}
        for g in self.diff().new_groups:
            all_pkgs = set(self.group(g).full_list)
            installed_in_group = list(all_pkgs.intersection(ins))
            self.group(g).param_dct['full_list'] = installed_in_group

    def group(self, id_):
        return self._access('GROUPS', id_)

    @property
    def groups(self):
        return self.db['GROUPS']

    def groups_by_pattern(self, pattern, case_sensitive=False):
        return _by_pattern(pattern, self.groups,
                           self.group, case_sensitive)

    def save(self):
        if not self._commit:
            return False
        self._prune_db()
        if self.db == self._original:
            return False
        logger.debug('group persistor: saving.')
        with open(self._dbfile, 'w') as db:
            json.dump(self.db.dct, db)
        self._commit = False
        return True


class JSONDB(object):

    def _check_json_db(self, json_path):
        if not os.path.isfile(json_path):
            # initialize new db
            dnf.util.ensure_dir(os.path.dirname(json_path))
            self._write_json_db(json_path, [])

    def _get_json_db(self, json_path, default=[]):
        with open(json_path, 'r') as f:
            content = f.read()
        if content == "":
            # empty file is invalid json format
            logger.warning(_("%s is empty file"), json_path)
            self._write_json_db(json_path, default)
        else:
            try:
                default = json.loads(content)
            except ValueError as e:
                logger.warning(e)
        return default

    @staticmethod
    def _write_json_db(json_path, content):
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
        self._check_json_db(self.db_path)
        return set(self._get_json_db(self.db_path))

    def save(self):
        self._check_json_db(self.db_path)
        self._write_json_db(self.db_path, list(self.expired_to_add))
        if self.reset_last_makecache:
            try:
                dnf.util.touch(self._last_makecache_path)
                return True
            except IOError:
                logger.info("Failed storing last makecache time.")
                return False

    def since_last_makecache(self):
        try:
            return int(dnf.util.file_age(self._last_makecache_path))
        except OSError:
            logger.info("Failed determining last makecache time.")
            return None


class TempfilePersistor(JSONDB):

    def __init__(self, cachedir):
        self.db_path = os.path.join(cachedir, "tempfiles.json")
        self.tempfiles_to_add = set()
        self._empty = False

    def get_saved_tempfiles(self):
        self._check_json_db(self.db_path)
        return self._get_json_db(self.db_path)

    def save(self):
        if not self._empty and not self.tempfiles_to_add:
            return
        self._check_json_db(self.db_path)
        if self._empty:
            self._write_json_db(self.db_path, [])
            return
        if self.tempfiles_to_add:
            data = set(self._get_json_db(self.db_path))
            data.update(self.tempfiles_to_add)
            self._write_json_db(self.db_path, list(data))

    def empty(self):
        self._empty = True
