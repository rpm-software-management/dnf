# comps.py
# Interface to libcomps.
#
# Copyright (C) 2013-2014  Red Hat, Inc.
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

from __future__ import print_function
from dnf.exceptions import CompsError
from functools import reduce

import dnf.i18n
import dnf.util
import fnmatch
import gettext
import itertools
import libcomps
import locale
import operator
import re


CONDITIONAL = 1 # :api ...
DEFAULT     = 2
MANDATORY   = 3
OPTIONAL    = 4

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

    return {g for g in sqn if match(g.name) or match(g.id)}

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

class Group(Forwarder):
    # :api
    def __init__(self, iobj, langs, installed_groups, pkg_factory):
        super(Group, self).__init__(iobj, langs)
        self._installed_groups = installed_groups
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

    def mark(self, packages):
        self._installed_groups[self.id] = list(packages)

    @property
    def installed(self):
        return self.id in self._installed_groups

    def installed_packages(self):
        names = self._installed_groups.get(self.id, [])
        pkgs = (pkg for pkg in self.packages if pkg.name in names)
        return map(self._pkg_factory, pkgs)

    def packages_iter(self):
        # :api
        return map(self._pkg_factory, self.packages)

    def unmark(self):
        self._installed_groups.pop(self.id, None)

    @property
    def mandatory_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_MANDATORY)

    @property
    def optional_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_OPTIONAL)

    @property
    def visible(self):
        return self._i.uservisible

class Category(Forwarder):
    # :api
    pass

class Environment(Forwarder):
    # :api

    def __init__(self, iobj, langs, installed_environments, group_factory):
        super(Environment, self).__init__(iobj, langs)
        self._installed_environments = installed_environments
        self._group_factory = group_factory

    def groups_iter(self):
        for grp_id in self.group_ids:
            grp = self._group_factory(grp_id.name)
            if grp is None:
                msg = "no group '%s' from environment '%s'"
                raise ValueError(msg % (grp_id.name, self.id))
            yield grp

    @property
    def installed(self):
        return self.id in self._installed_environments

    @property
    def installed_groups(self):
        for grp_id in self._installed_environments.get(self.id, []):
            grp = self._group_factory(grp_id)
            if grp is None:
                msg = "no group '%s' from environment '%s'"
                raise ValueError(msg % (grp_id.name, self.id))
            yield grp

    def mark(self, groups):
        self._installed_environments[self.id] = list(groups)

    def unmark(self):
        self._installed_environments.pop(self.id, None)

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

    def __init__(self, installed_groups, installed_environments):
        self._i = libcomps.Comps()
        self._installed_groups = installed_groups
        self._installed_environments = installed_environments
        self._langs = _Langs()
        self.persistor = None

    def __len__(self):
        return _internal_comps_length(self._i)

    def _build_category(self, icategory):
        return Category(icategory, self._langs)

    def _build_environment(self, ienvironment):
        return Environment(ienvironment, self._langs,
                           self._installed_environments, self.group_by_id)

    def _build_group(self, igroup):
        return Group(igroup, self._langs, self._installed_groups,
                     self._build_package)

    def _build_package(self, ipkg):
        return Package(ipkg)

    def add_from_xml_filename(self, fn):
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
        return list(self.environments_iter())

    def environment_by_pattern(self, pattern, case_sensitive=False):
        # :api
        envs = self.environments_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(envs)

    def environments_by_pattern(self, pattern, case_sensitive=False):
        # :api
        return _by_pattern(pattern, case_sensitive, self.environments)

    def environments_iter(self):
        # :api
        return (self._build_environment(e) for e in self._i.environments)

    @property
    def groups(self):
        # :api
        return list(self.groups_iter())

    def group_by_id(self, id_):
        return dnf.util.first(g for g in self.groups_iter() if g.id == id_)

    def group_by_pattern(self, pattern, case_sensitive=False):
        # :api
        grps = self.groups_by_pattern(pattern, case_sensitive)
        return _first_if_iterable(grps)

    def groups_by_pattern(self, pattern, case_sensitive=False):
        # :api
        return _by_pattern(pattern, case_sensitive, self.groups)

    def groups_iter(self):
        # :api
        return (self._build_group(g) for g in self._i.groups)
