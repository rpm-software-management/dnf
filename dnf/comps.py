# comps.py
# Interface to libcomps.
#
# Copyright (C) 2013-2018 Red Hat, Inc.
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

import libdnf.transaction

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
CONDITIONAL = libdnf.transaction.CompsPackageType_CONDITIONAL
DEFAULT     = libdnf.transaction.CompsPackageType_DEFAULT
MANDATORY   = libdnf.transaction.CompsPackageType_MANDATORY
OPTIONAL    = libdnf.transaction.CompsPackageType_OPTIONAL

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
                    strict=True, exclude_groups=None):
    """Either mark in persistor as installed given `grp_or_env` (group
       or environment) or skip it (if it's already installed).
       `install_fnc` has to be Solver._group_install
       or Solver._environment_install.
       """
    try:
        return install_fnc(grp_or_env_id, types, exclude, strict, exclude_groups)
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

    def __init__(self, comps, history, kinds, status):
        self.comps = comps
        self.history = history
        self.kinds = kinds
        self.status = status

    def _get_groups(self, available, installed):
        result = set()
        if self.status & self.AVAILABLE:
            result.update({i.id for i in available})
        if self.status & self.INSTALLED:
            for i in installed:
                group = i.getCompsGroupItem()
                if not group:
                    continue
                result.add(group.getGroupId())
        return result

    def _get_envs(self, available, installed):
        result = set()
        if self.status & self.AVAILABLE:
            result.update({i.id for i in available})
        if self.status & self.INSTALLED:
            for i in installed:
                env = i.getCompsEnvironmentItem()
                if not env:
                    continue
                result.add(env.getEnvironmentId())
        return result

    def get(self, *patterns):
        res = dnf.util.Bunch()
        res.environments = []
        res.groups = []
        for pat in patterns:
            envs = grps = []
            if self.kinds & self.ENVIRONMENTS:
                available = self.comps.environments_by_pattern(pat)
                installed = self.history.env.search_by_pattern(pat)
                envs = self._get_envs(available, installed)
                res.environments.extend(envs)
            if self.kinds & self.GROUPS:
                available = self.comps.groups_by_pattern(pat)
                installed = self.history.group.search_by_pattern(pat)
                grps = self._get_groups(available, installed)
                res.groups.extend(grps)
            if not envs and not grps:
                if self.status == self.INSTALLED:
                    msg = _("Module or Group '%s' is not installed.") % ucd(pat)
                elif self.status == self.AVAILABLE:
                    msg = _("Module or Group '%s' is not available.") % ucd(pat)
                else:
                    msg = _("Module or Group '%s' does not exist.") % ucd(pat)
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

    def _build_groups(self, ids):
        groups = []
        for gi in ids:
            try:
                groups.append(self._build_group(gi))
            except ValueError as e:
                logger.error(e)

        return groups

    def groups_iter(self):
        for grp_id in itertools.chain(self.group_ids, self.option_ids):
            try:
                yield self._build_group(grp_id)
            except ValueError as e:
                logger.error(e)

    @property
    def mandatory_groups(self):
        return self._build_groups(self.group_ids)

    @property
    def optional_groups(self):
        return self._build_groups(self.option_ids)

class Group(Forwarder):
    # :api
    def __init__(self, iobj, langs, pkg_factory):
        super(Group, self).__init__(iobj, langs)
        self._pkg_factory = pkg_factory
        self.selected = iobj.default

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
        try:
            comps.fromxml_f(fn)
        except libcomps.ParserError:
            errors = comps.get_last_errors()
            raise CompsError(' '.join(errors))
        self._i += comps

    @property
    def categories(self):
        # :api
        return list(self.categories_iter())

    def category_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
        cats = self.categories_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(cats)

    def categories_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
        return _by_pattern(pattern, case_sensitive, self.categories)

    def categories_iter(self):
        # :api
        return (self._build_category(c) for c in self._i.categories)

    @property
    def environments(self):
        # :api
        return sorted(self.environments_iter(), key=_fn_display_order)

    def _environment_by_id(self, id):
        assert dnf.util.is_string_type(id)
        return dnf.util.first(g for g in self.environments_iter() if g.id == id)

    def environment_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
        envs = self.environments_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(envs)

    def environments_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
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
        assert dnf.util.is_string_type(id_)
        return dnf.util.first(g for g in self.groups_iter() if g.id == id_)

    def group_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
        grps = self.groups_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(grps)

    def groups_by_pattern(self, pattern, case_sensitive=False):
        # :api
        assert dnf.util.is_string_type(pattern)
        grps = _by_pattern(pattern, case_sensitive, list(self.groups_iter()))
        return sorted(grps, key=_fn_display_order)

    def groups_iter(self):
        # :api
        return (self._build_group(g) for g in self._i.groups)

class CompsTransPkg(object):
    def __init__(self, pkg_or_name):
        if dnf.util.is_string_type(pkg_or_name):
            # from package name
            self.basearchonly = False
            self.name = pkg_or_name
            self.optional = True
            self.requires = None
        elif isinstance(pkg_or_name, libdnf.transaction.CompsGroupPackage):
            # from swdb package
            # TODO:
            self.basearchonly = False
            # self.basearchonly = pkg_or_name.basearchonly
            self.name = pkg_or_name.getName()
            self.optional = pkg_or_name.getPackageType() & libcomps.PACKAGE_TYPE_OPTIONAL
            # TODO:
            self.requires = None
            # self.requires = pkg_or_name.requires
        else:
            # from comps package
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
        self._install_opt = set()
        self._remove = set()
        self._upgrade = set()

    def __iadd__(self, other):
        self._install.update(other._install)
        self._install_opt.update(other._install_opt)
        self._upgrade.update(other._upgrade)
        self._remove = (self._remove | other._remove) - \
            self._install - self._install_opt - self._upgrade
        return self

    def __len__(self):
        return len(self.install) + len(self.install_opt) + len(self.upgrade) + len(self.remove)

    @staticmethod
    def _set_value(param, val):
        for item in val:
            if isinstance(item, CompsTransPkg):
                param.add(item)
            else:
                param.add(CompsTransPkg(item))

    @property
    def install(self):
        """
        Packages to be installed with strict=True - transaction will
        fail if they cannot be installed due to dependency errors etc.
        """
        return self._install

    @install.setter
    def install(self, value):
        self._set_value(self._install, value)

    @property
    def install_opt(self):
        """
        Packages to be installed with strict=False - they will be
        skipped if they cannot be installed
        """
        return self._install_opt

    @install_opt.setter
    def install_opt(self, value):
        self._set_value(self._install_opt, value)

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
    def __init__(self, history, comps, reason_fn):
        self.history = history
        self.comps = comps
        self._reason_fn = reason_fn

    @staticmethod
    def _mandatory_group_set(env):
        return {grp.id for grp in env.mandatory_groups}

    @staticmethod
    def _full_package_set(grp):
        return {pkg.getName() for pkg in grp.mandatory_packages +
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
        assert dnf.util.is_string_type(pkg_name)
        return self.history.group.is_removable_pkg(pkg_name)

    def _removable_grp(self, group_id):
        assert dnf.util.is_string_type(group_id)
        return self.history.env.is_removable_group(group_id)

    def _environment_install(self, env_id, pkg_types, exclude, strict=True, exclude_groups=None):
        assert dnf.util.is_string_type(env_id)
        comps_env = self.comps._environment_by_id(env_id)
        swdb_env = self.history.env.new(env_id, comps_env.name, comps_env.ui_name, pkg_types)
        self.history.env.install(swdb_env)

        trans = TransactionBunch()
        for comps_group in comps_env.mandatory_groups:
            if exclude_groups and comps_group.id in exclude_groups:
                continue
            trans += self._group_install(comps_group.id, pkg_types, exclude, strict)
            swdb_env.addGroup(comps_group.id, True, MANDATORY)

        for comps_group in comps_env.optional_groups:
            if exclude_groups and comps_group.id in exclude_groups:
                continue
            swdb_env.addGroup(comps_group.id, False, OPTIONAL)
            # TODO: if a group is already installed, mark it as installed?
        return trans

    def _environment_remove(self, env_id):
        assert dnf.util.is_string_type(env_id) is True
        swdb_env = self.history.env.get(env_id)
        if not swdb_env:
            raise CompsError(_("Environment '%s' is not installed.") % env_id)

        self.history.env.remove(swdb_env)

        trans = TransactionBunch()
        group_ids = set([i.getGroupId() for i in swdb_env.getGroups()])
        for group_id in group_ids:
            if not self._removable_grp(group_id):
                continue
            trans += self._group_remove(group_id)
        return trans

    def _environment_upgrade(self, env_id):
        assert dnf.util.is_string_type(env_id)
        comps_env = self.comps._environment_by_id(env_id)
        swdb_env = self.history.env.get(comps_env.id)
        if not swdb_env:
            raise CompsError(_("Environment '%s' is not installed.") % env_id)
        if not comps_env:
            raise CompsError(_("Environment '%s' is not available.") % env_id)

        old_set = set([i.getGroupId() for i in swdb_env.getGroups() if i.getInstalled()])
        pkg_types = swdb_env.getPackageTypes()

        # create a new record for current transaction
        swdb_env = self.history.env.new(comps_env.id, comps_env.name, comps_env.ui_name, pkg_types)

        trans = TransactionBunch()
        for comps_group in comps_env.mandatory_groups:
            if comps_group.id in old_set:
                # upgrade existing group
                trans += self._group_upgrade(comps_group.id)
            else:
                # install new group
                trans += self._group_install(comps_group.id, pkg_types)
            swdb_env.addGroup(comps_group.id, True, MANDATORY)

        for comps_group in comps_env.optional_groups:
            swdb_env.addGroup(comps_group.id, False, OPTIONAL)
            # TODO: if a group is already installed, mark it as installed?
        self.history.env.upgrade(swdb_env)
        return trans

    def _group_install(self, group_id, pkg_types, exclude=None, strict=True, exclude_groups=None):
        assert dnf.util.is_string_type(group_id)
        comps_group = self.comps._group_by_id(group_id)
        if not comps_group:
            raise ValueError(_("Group_id '%s' does not exist.") % ucd(group_id))

        swdb_group = self.history.group.new(group_id, comps_group.name, comps_group.ui_name, pkg_types)
        for i in comps_group.packages_iter():
            swdb_group.addPackage(i.name, False, i.type)
        self.history.group.install(swdb_group)

        trans = TransactionBunch()
        # TODO: remove exclude
        if strict:
            trans.install.update(self._pkgs_of_type(comps_group, pkg_types, exclude=[]))
        else:
            trans.install_opt.update(self._pkgs_of_type(comps_group, pkg_types, exclude=[]))
        return trans

    def _group_remove(self, group_id):
        assert dnf.util.is_string_type(group_id)
        swdb_group = self.history.group.get(group_id)
        self.history.group.remove(swdb_group)

        trans = TransactionBunch()
        trans.remove = {pkg for pkg in swdb_group.getPackages() if self._removable_pkg(pkg.getName())}
        return trans

    def _group_upgrade(self, group_id):
        assert dnf.util.is_string_type(group_id)
        comps_group = self.comps._group_by_id(group_id)
        swdb_group = self.history.group.get(group_id)
        exclude = []

        if not swdb_group:
            argument = comps_group.ui_name if comps_group else group_id
            raise CompsError(_("Module or Group '%s' is not installed.") % argument)
        if not comps_group:
            raise CompsError(_("Module or Group '%s' is not available.") % group_id)
        pkg_types = swdb_group.getPackageTypes()
        old_set = set([i.getName() for i in swdb_group.getPackages()])
        new_set = self._pkgs_of_type(comps_group, pkg_types, exclude)

        # create a new record for current transaction
        swdb_group = self.history.group.new(group_id, comps_group.name, comps_group.ui_name, pkg_types)
        for i in comps_group.packages_iter():
            swdb_group.addPackage(i.name, False, i.type)
        self.history.group.upgrade(swdb_group)

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
                installed_pkgs = base.sack.query().installed().filterm(name=installed_pkg_names)
                for pkg in installed_pkgs:
                    base._goal.install(pkg)
