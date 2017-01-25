# comps.py
# Interface to libcomps.
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from dnf.exceptions import CompsError
from dnf.i18n import _, ucd
from functools import reduce

import dnf.i18n
import dnf.util
import fnmatch
import gettext
import itertools
import libcomps
import locale
import logging
import operator
import re
import sys

logger = logging.getLogger("dnf")

# :api :binformat
CONDITIONAL = 1
DEFAULT     = 2
MANDATORY   = 4
OPTIONAL    = 8

ALL_TYPES = CONDITIONAL | DEFAULT | MANDATORY | OPTIONAL


def _internal_comps_length(comps):
    collections = (comps.categories, comps.groups, comps.environments)
    return reduce(operator.__add__, map(len, collections))


def _first_if_iterable(seq):
    if seq is None:
        return None
    return dnf.util.first(seq)


def _by_pattern(pattern, case_sensitive, sqn):
    """Return items from sqn matching either exactly or glob-wise."""

    pattern = dnf.i18n.ucd(pattern)
    exact = {g for g in sqn if g.name == pattern or g.id == pattern}
    if exact:
        return exact

    if case_sensitive:
        match = re.compile(fnmatch.translate(pattern)).match
    else:
        match = re.compile(fnmatch.translate(pattern), flags=re.I).match

    return {g for g in sqn if match(g.name) or match(g.id) or match(g.ui_name)}


def _fn_display_order(group):
    return sys.maxsize if group.display_order is None else group.display_order


def install_or_skip(install_fnc, grp_or_env_id, types, exclude=None,
                    strict=True):
    """Either mark in persistor as installed given `grp_or_env` (group
       or environment) or skip it (if it's already installed).
       `install_fnc` has to be Solver._group_install
       or Solver._environment_install.
       """
    try:
        return install_fnc(grp_or_env_id, types, exclude, strict)
    except dnf.comps.CompsError as e:
        logger.warning("%s, %s", ucd(e)[:-1], _("skipping."))


class _Langs(object):

    """Get all usable abbreviations for the current language."""

    def __init__(self):
        self.last_locale = None
        self.cache = None

    @staticmethod
    def _dotted_locale_str():
        lcl = locale.getlocale(locale.LC_MESSAGES)
        if lcl == (None, None):
            return 'C'
        return'.'.join(lcl)

    def get(self):
        current_locale = self._dotted_locale_str()
        if self.last_locale == current_locale:
            return self.cache

        self.cache = []
        locales = [current_locale]
        if current_locale != 'C':
            locales.append('C')
        for l in locales:
            for nlang in gettext._expand_lang(l):
                if nlang not in self.cache:
                    self.cache.append(nlang)

        self.last_locale = current_locale
        return self.cache


class CompsQuery(object):

    AVAILABLE = 1
    INSTALLED = 2

    ENVIRONMENTS = 1
    GROUPS = 2

    def __init__(self, comps, prst, kinds, status):
        self.comps = comps
        self.prst = prst
        self.kinds = kinds
        self.status = status

    def _get(self, available, installed):
        result = set()
        if self.status & self.AVAILABLE:
            result.update({g.id for g in available})
        if self.status & self.INSTALLED:
            result.update(installed)
        return result

    def get(self, *patterns):
        res = dnf.util.Bunch()
        res.environments = []
        res.groups = []
        for pat in patterns:
            envs = grps = []
            if self.kinds & self.ENVIRONMENTS:
                available = self.comps.environments_by_pattern(pat)
                installed = self.prst.environments_by_pattern(pat)
                envs = self._get(available,
                                 installed)
                res.environments.extend(envs)
            if self.kinds & self.GROUPS:
                available = self.comps.groups_by_pattern(pat)
                installed = self.prst.groups_by_pattern(pat)
                grps = self._get(available,
                                 installed)
                res.groups.extend(grps)
            if not envs and not grps:
                if self.status == self.INSTALLED:
                    msg = _("Group '%s' is not installed.") % ucd(pat)
                else:
                    msg = _("Group '%s' does not exist.") % ucd(pat)
                raise CompsError(msg)
        return res


class Forwarder(object):
    def __init__(self, iobj, langs):
        self._i = iobj
        self._langs = langs

    def __getattr__(self, name):
        return getattr(self._i, name)

    def _ui_text(self, default, dct):
        for l in self._langs.get():
            t = dct.get(l)
            if t is not None:
                return t
        return default

    @property
    def ui_description(self):
        return self._ui_text(self.desc, self.desc_by_lang)

    @property
    def ui_name(self):
        return self._ui_text(self.name, self.name_by_lang)

class Category(Forwarder):
    # :api
    def __init__(self, iobj, langs, group_factory):
        super(Category, self).__init__(iobj, langs)
        self._group_factory = group_factory

    def _build_group(self, grp_id):
        grp = self._group_factory(grp_id.name)
        if grp is None:
            msg = "no group '%s' from category '%s'"
            raise ValueError(msg % (grp_id.name, self.id))
        return grp

    def groups_iter(self):
        for grp_id in self.group_ids:
            yield self._build_group(grp_id)

    @property
    def groups(self):
        return list(self.groups_iter())

class Environment(Forwarder):
    # :api

    def __init__(self, iobj, langs, group_factory):
        super(Environment, self).__init__(iobj, langs)
        self._group_factory = group_factory

    def _build_group(self, grp_id):
        grp = self._group_factory(grp_id.name)
        if grp is None:
            msg = "no group '%s' from environment '%s'"
            raise ValueError(msg % (grp_id.name, self.id))
        return grp

    def groups_iter(self):
        for grp_id in itertools.chain(self.group_ids, self.option_ids):
            yield self._build_group(grp_id)

    @property
    def mandatory_groups(self):
        return [self._build_group(gi) for gi in self.group_ids]

    @property
    def optional_groups(self):
        return [self._build_group(gi) for gi in self.option_ids]

class Group(Forwarder):
    # :api
    def __init__(self, iobj, langs, pkg_factory):
        super(Group, self).__init__(iobj, langs)
        self._pkg_factory = pkg_factory
        self.selected = False

    def _packages_of_type(self, type_):
        return [pkg for pkg in self.packages if pkg.type == type_]

    @property
    def conditional_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_CONDITIONAL)

    @property
    def default_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_DEFAULT)

    def packages_iter(self):
        # :api
        return map(self._pkg_factory, self.packages)

    @property
    def mandatory_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_MANDATORY)

    @property
    def optional_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_OPTIONAL)

    @property
    def visible(self):
        return self._i.uservisible

class Package(Forwarder):
    """Represents comps package data. :api"""

    _OPT_MAP = {
        libcomps.PACKAGE_TYPE_CONDITIONAL : CONDITIONAL,
        libcomps.PACKAGE_TYPE_DEFAULT     : DEFAULT,
        libcomps.PACKAGE_TYPE_MANDATORY   : MANDATORY,
        libcomps.PACKAGE_TYPE_OPTIONAL    : OPTIONAL,
    }

    def __init__(self, ipkg):
        self._i = ipkg

    @property
    def name(self):
        # :api
        return self._i.name

    @property
    def option_type(self):
        # :api
        return self._OPT_MAP[self.type]

class Comps(object):
    # :api

    def __init__(self):
        self._i = libcomps.Comps()
        self._langs = _Langs()

    def __len__(self):
        return _internal_comps_length(self._i)

    def _build_category(self, icategory):
        return Category(icategory, self._langs, self._group_by_id)

    def _build_environment(self, ienvironment):
        return Environment(ienvironment, self._langs, self._group_by_id)

    def _build_group(self, igroup):
        return Group(igroup, self._langs, self._build_package)

    def _build_package(self, ipkg):
        return Package(ipkg)

    def _add_from_xml_filename(self, fn):
        comps = libcomps.Comps()
        ret = comps.fromxml_f(fn)
        if ret == -1:
            errors = comps.get_last_parse_errors()
            raise CompsError(' '.join(errors))
        self._i = self._i + comps

    @property
    def categories(self):
        # :api
        return list(self.categories_iter())

    def category_by_pattern(self, pattern, case_sensitive=False):
        # :api
        cats = self.categories_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(cats)

    def categories_by_pattern(self, pattern, case_sensitive=False):
        # :api
        return _by_pattern(pattern, case_sensitive, self.categories)

    def categories_iter(self):
        # :api
        return (self._build_category(c) for c in self._i.categories)

    @property
    def environments(self):
        # :api
        return sorted(self.environments_iter(), key=_fn_display_order)

    def _environment_by_id(self, id):
        return dnf.util.first(g for g in self.environments_iter() if g.id == id)

    def environment_by_pattern(self, pattern, case_sensitive=False):
        # :api
        envs = self.environments_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(envs)

    def environments_by_pattern(self, pattern, case_sensitive=False):
        # :api
        envs = list(self.environments_iter())
        found_envs = _by_pattern(pattern, case_sensitive, envs)
        return sorted(found_envs, key=_fn_display_order)

    def environments_iter(self):
        # :api
        return (self._build_environment(e) for e in self._i.environments)

    @property
    def groups(self):
        # :api
        return sorted(self.groups_iter(), key=_fn_display_order)

    def _group_by_id(self, id_):
        return dnf.util.first(g for g in self.groups_iter() if g.id == id_)

    def group_by_pattern(self, pattern, case_sensitive=False):
        # :api
        grps = self.groups_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(grps)

    def groups_by_pattern(self, pattern, case_sensitive=False):
        # :api
        grps = _by_pattern(pattern, case_sensitive, list(self.groups_iter()))
        return sorted(grps, key=_fn_display_order)

    def groups_iter(self):
        # :api
        return (self._build_group(g) for g in self._i.groups)


class CompsTransPkg(object):
    def __init__(self, pkg_or_name):
        if dnf.util.is_string_type(pkg_or_name):
            self.basearchonly = False
            self.name = pkg_or_name
            self.optional = True
            self.requires = None
        else:
            self.basearchonly = pkg_or_name.basearchonly
            self.name = pkg_or_name.name
            self.optional = pkg_or_name.type & libcomps.PACKAGE_TYPE_OPTIONAL
            self.requires = pkg_or_name.requires

    def __eq__(self, other):
        return (self.name == other.name and
                self.basearchonly == self.basearchonly and
                self.optional == self.optional and
                self.requires == self.requires)

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash((self.name,
                    self.basearchonly,
                    self.optional,
                    self.requires))


class TransactionBunch(object):
    def __init__(self):
        self._install = set()
        self._remove = set()
        self._upgrade = set()

    def __iadd__(self, other):
        self._install.update(other._install)
        self._upgrade.update(other._upgrade)
        self._remove = (self._remove | other._remove) - \
            self._install - self._upgrade
        return self

    def __len__(self):
        return len(self.install) + len(self.upgrade) + len(self.remove)

    @staticmethod
    def _set_value(param, val):
        for item in val:
            if isinstance(item, CompsTransPkg):
                param.add(item)
            else:
                param.add(CompsTransPkg(item))

    @property
    def install(self):
        return self._install

    @install.setter
    def install(self, value):
        self._set_value(self._install, value)

    @property
    def remove(self):
        return self._remove

    @remove.setter
    def remove(self, value):
        self._set_value(self._remove, value)

    @property
    def upgrade(self):
        return self._upgrade

    @upgrade.setter
    def upgrade(self, value):
        self._set_value(self._upgrade, value)


class Solver(object):
    def __init__(self, persistor, comps, reason_fn):
        self.comps = comps
        self.persistor = persistor
        self._reason_fn = reason_fn

    @staticmethod
    def _mandatory_group_set(env):
        return {grp.id for grp in env.mandatory_groups}

    @staticmethod
    def _full_package_set(grp):
        return {pkg.name for pkg in grp.mandatory_packages +
                grp.default_packages + grp.optional_packages +
                grp.conditional_packages}

    @staticmethod
    def _pkgs_of_type(group, pkg_types, exclude=[]):
        def filter(pkgs):
            return [pkg for pkg in pkgs
                    if pkg.name not in exclude]

        pkgs = set()
        if pkg_types & MANDATORY:
            pkgs.update(filter(group.mandatory_packages))
        if pkg_types & DEFAULT:
            pkgs.update(filter(group.default_packages))
        if pkg_types & OPTIONAL:
            pkgs.update(filter(group.optional_packages))
        if pkg_types & CONDITIONAL:
            pkgs.update(filter(group.conditional_packages))
        return pkgs

    def _removable_pkg(self, pkg_name):
        prst = self.persistor
        count = 0
        if self._reason_fn(pkg_name) != 'group':
            return False
        for id_ in prst.groups():
            p_grp = prst.group(id_.name_id)
            count += sum(1 for pkg in p_grp.get_full_list() if pkg == pkg_name)
        return count < 2

    def _removable_grp(self, grp_name):
        prst = self.persistor
        count = 0
        if not prst.group(grp_name).is_installed:
            return False
        for id_ in prst.environments():
            p_env = prst.environment(id_.name_id)
            count += sum(1 for grp in p_env.get_group_list() if grp == grp_name)
        return count < 2

    def _environment_install(self, env_id, pkg_types, exclude, strict=True):
        if type(env_id) == self.persistor.get_env_type():
            env_id = env_id.name_id
        env = self.comps._environment_by_id(env_id)
        p_env = self.persistor.environment(env_id)
        if p_env and p_env.is_installed():
            logger.warning(_("Environment '%s' is already installed.") %
                             env.ui_name)
        grp_types = CONDITIONAL | DEFAULT | MANDATORY | OPTIONAL
        exclude = list() if exclude is None else list(exclude)
        if not p_env:
            p_env = self.persistor.new_env(env_id, env.name, env.ui_name,
                                           pkg_types, grp_types)
            self.persistor.add_env(p_env)
            p_env.add_exclude(exclude)
            p_env.add_group(list(self._mandatory_group_set(env)))

        trans = TransactionBunch()
        for grp in env.mandatory_groups:
            try:
                trans += self._group_install(grp.id, pkg_types, exclude, strict)
            except dnf.exceptions.CompsError:
                pass
        return trans

    def _environment_remove(self, env_id):
        if type(env_id) == self.persistor.get_env_type():
            env_id = env_id.name_id
        p_env = self.persistor.environment(env_id)
        if not p_env.is_installed():
            raise CompsError(_("Environment '%s' is not installed.") %
                             ucd(p_env.ui_name))

        trans = TransactionBunch()
        group_ids = set(p_env.get_group_list())

        for grp in group_ids:
            if not self._removable_grp(grp):
                continue
            trans += self._group_remove(grp)
        return trans

    def _environment_upgrade(self, env_id):
        if type(env_id) == self.persistor.get_env_type():
            env_id = env_id.name_id
        env = self.comps._environment_by_id(env_id)
        p_env = self.persistor.environment(env.id)
        if not p_env.is_installed():
            raise CompsError(_("Environment '%s' is not installed.") %
                             env.ui_name)

        old_set = set(p_env.get_group_list())
        pkg_types = p_env.pkg_types
        exclude = p_env.get_exclude()

        trans = TransactionBunch()
        for grp in env.mandatory_groups:
            if grp.id in old_set:
                # upgrade
                try:
                    trans += self._group_upgrade(grp.id)
                except dnf.exceptions.CompsError:
                    # might no longer be installed
                    pass
            else:
                # install
                trans += self._group_install(grp.id, pkg_types, exclude)
        return trans

    def _group_install(self, group_id, pkg_types, exclude, strict=True):
        if type(group_id) == self.persistor.get_group_type():
            group_id = group_id.name_id
        group = self.comps._group_by_id(group_id)
        if not group:
            raise ValueError(_("Group_id '%s' does not exist.") %
                             ucd(group_id))
        # this will return DnfSwdbGroup object
        p_grp = self.persistor.group(group_id)
        if p_grp and p_grp.is_installed:
            logger.warning(_("Group '%s' is already installed.") %
                             group.ui_name)
        exclude = list() if exclude is None else list(exclude)
        p_grp = self.persistor.new_group(group_id, group.name,
                                         group.ui_name, 0, pkg_types, 0)
        self.persistor.add_group(p_grp)
        p_grp.add_exclude(exclude)
        p_grp.add_package(list(self._full_package_set(group)))

        trans = TransactionBunch()
        trans.install.update(self._pkgs_of_type(group, pkg_types, exclude))
        return trans

    def _group_remove(self, group_id):
        if type(group_id) == self.persistor.get_group_type():
            group_id = group_id.name_id
        p_grp = self.persistor.group(group_id)
        if not p_grp.is_installed:
            raise CompsError(_("Group '%s' not installed.") %
                             ucd(p_grp.ui_name))

        trans = TransactionBunch()
        exclude = p_grp.get_exclude()
        trans.remove = {pkg for pkg in p_grp.get_full_list()
                        if pkg not in exclude and self._removable_pkg(pkg)}
        self.persistor.groups_removed.append(p_grp)
        return trans

    def _group_upgrade(self, group_id):
        if type(group_id) == self.persistor.get_group_type():
            group_id = group_id.name_id
        group = self.comps._group_by_id(group_id)
        p_grp = self.persistor.group(group.id)
        if not p_grp.is_installed:
            raise CompsError(_("Group '%s' not installed.") %
                             group.ui_name)
        exclude = set(p_grp.get_exclude())
        old_set = set(p_grp.get_full_list())
        new_set = self._pkgs_of_type(group, p_grp.pkg_types, exclude)
        p_grp.update_full_list(list(self._full_package_set(group)))

        trans = TransactionBunch()
        trans.install = {pkg for pkg in new_set if pkg.name not in old_set}
        trans.remove = {name for name in old_set
                        if name not in [pkg.name for pkg in new_set]}
        trans.upgrade = {pkg for pkg in new_set if pkg.name in old_set}
        return trans

    def _exclude_packages_from_installed_groups(self, base):
        for group in self.persistor.groups:
            p_grp = self.persistor.group(group)
            if p_grp.installed:
                installed_pkg_names = \
                    set(p_grp.full_list) - set(p_grp.pkg_exclude)
                installed_pkgs = base.sack.query().installed().filter(
                    name=installed_pkg_names)
                for pkg in installed_pkgs:
                    base._goal.install(pkg)
