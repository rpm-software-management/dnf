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


class TransactionBunch(object):
    def __init__(self):
        self.install = set()
        self.install_opt = set()
        self.remove = set()
        self.upgrade = set()

    def __iadd__(self, other):
        self.install.update(other.install)
        self.install_opt.update(other.install_opt)
        self.upgrade.update(other.upgrade)
        self.remove = (self.remove | other.remove) - \
            self.install - self.install_opt - self.upgrade
        return self


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
                grp.default_packages + grp.optional_packages}

    @staticmethod
    def _pkgs_of_type(group, pkg_types, exclude):
        def pkgs_update(pkgs, group):
            pkgs.update(pkg.name for pkg in group
                        if pkg.name not in exclude)

        pkgs = set()
        if pkg_types & MANDATORY:
            pkgs_update(pkgs, group.mandatory_packages)
        if pkg_types & DEFAULT:
            pkgs_update(pkgs, group.default_packages)
        if pkg_types & OPTIONAL:
            pkgs_update(pkgs, group.optional_packages)
        return pkgs

    def _removable_pkg(self, pkg_name):
        prst = self.persistor
        count = 0
        if self._reason_fn(pkg_name) != 'group':
            return False
        for id_ in prst.groups:
            p_grp = prst.group(id_)
            count += sum(1 for pkg in p_grp.full_list if pkg == pkg_name)
        return count < 2

    def _removable_grp(self, grp_name):
        prst = self.persistor
        count = 0
        if not prst.group(grp_name).installed:
            return False
        for id_ in prst.environments:
            p_env = prst.environment(id_)
            count += sum(1 for grp in p_env.full_list if grp == grp_name)
        return count < 2

    def _environment_install(self, env_id, pkg_types, exclude, strict=True):
        env = self.comps._environment_by_id(env_id)
        p_env = self.persistor.environment(env_id)
        if p_env.installed:
            raise CompsError(_("Environment '%s' is already installed.") %
                             env.ui_name)

        p_env.grp_types = CONDITIONAL | DEFAULT | MANDATORY | OPTIONAL
        exclude = set() if exclude is None else set(exclude)
        p_env.name = env.name
        p_env.ui_name = env.ui_name
        p_env.pkg_exclude.extend(exclude)
        p_env.pkg_types = pkg_types
        p_env.full_list.extend(self._mandatory_group_set(env))

        trans = TransactionBunch()
        for grp in env.mandatory_groups:
            try:
                trans += self._group_install(grp.id, pkg_types, exclude, strict)
            except dnf.exceptions.CompsError:
                pass
        return trans

    def _environment_remove(self, env_id):
        p_env = self.persistor.environment(env_id)
        if not p_env.installed:
            raise CompsError(_("Environment '%s' is not installed.") %
                             p_env.ui_name)

        trans = TransactionBunch()
        group_ids = set(p_env.full_list)

        for grp in group_ids:
            if not self._removable_grp(grp):
                continue
            trans += self._group_remove(grp)

        del p_env.full_list[:]
        del p_env.pkg_exclude[:]
        p_env.grp_types = 0
        p_env.pkg_types = 0
        return trans

    def _environment_upgrade(self, env_id):
        env = self.comps._environment_by_id(env_id)
        p_env = self.persistor.environment(env.id)
        if not p_env.installed:
            raise CompsError(_("Environment '%s' is not installed.") %
                             env.ui_name)

        old_set = set(p_env.full_list)
        pkg_types = p_env.pkg_types
        exclude = p_env.pkg_exclude

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
        group = self.comps._group_by_id(group_id)
        if not group:
            raise ValueError(_("Group_id '%s' does not exist.") % ucd(group_id))
        p_grp = self.persistor.group(group_id)
        if p_grp.installed:
            raise CompsError(_("Group '%s' is already installed.") %
                             group.ui_name)

        exclude = set() if exclude is None else set(exclude)
        p_grp.name = group.name
        p_grp.ui_name = group.ui_name
        p_grp.pkg_exclude.extend(exclude)
        p_grp.pkg_types = pkg_types
        p_grp.full_list.extend(self._full_package_set(group))

        trans = TransactionBunch()
        types = pkg_types & MANDATORY
        mandatory = self._pkgs_of_type(group, types, exclude)
        types = pkg_types & (DEFAULT | OPTIONAL)
        trans.install_opt = self._pkgs_of_type(group, types, exclude)

        if strict:
            trans.install = mandatory
        else:
            trans.install_opt.update(mandatory)
        return trans

    def _group_remove(self, group_id):
        p_grp = self.persistor.group(group_id)
        if not p_grp.installed:
            raise CompsError(_("Group '%s' not installed.") %
                             p_grp.ui_name)

        trans = TransactionBunch()
        exclude = p_grp.pkg_exclude
        trans.remove = {pkg for pkg in p_grp.full_list
                        if pkg not in exclude and self._removable_pkg(pkg)}
        p_grp.pkg_types = 0
        del p_grp.full_list[:]
        del p_grp.pkg_exclude[:]
        return trans

    def _group_upgrade(self, group_id):
        group = self.comps._group_by_id(group_id)
        p_grp = self.persistor.group(group.id)
        if not p_grp.installed:
            raise CompsError(_("Group '%s' not installed.") %
                             group.ui_name)
        exclude = set(p_grp.pkg_exclude)
        old_set = set(p_grp.full_list)
        new_set = self._pkgs_of_type(group, p_grp.pkg_types, exclude)
        del p_grp.full_list[:]
        p_grp.full_list.extend(self._full_package_set(group))

        trans = TransactionBunch()
        trans.install = new_set - old_set
        trans.remove = old_set - new_set
        trans.upgrade = old_set - trans.remove
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
