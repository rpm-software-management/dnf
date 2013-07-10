# comps.py
# Interface to libcomps.
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

from dnf.exceptions import CompsException

import dnf.i18n
import fnmatch
import itertools
import libcomps
import operator
import re

def _internal_comps_length(comps):
    collections = (comps.categories, comps.groups, comps.environments)
    return reduce(operator.__add__, map(len, collections))

def _by_pattern(self, pattern, case_sensitive, sqn):
    """Return items from sqn matching either exactly or glob-wise."""

    pattern = dnf.i18n.ucd(pattern)
    ret = set()

    for item in pattern.split(','):
        item = item.strip()
        exact = [g for g in sqn if g.name == item or g.id == item]
        if exact:
            ret.update(exact)
            continue

        if case_sensitive:
            match = re.compile(fnmatch.translate(item)).match
        else:
            match = re.compile(fnmatch.translate(item), flags=re.I).match

        matching = [g for g in sqn if match(g.name) or match(g.id)]
        ret.update(matching)

    return ret

class Forwarder(object):
    def __init__(self, iobj):
        self._i = iobj

    def __getattr__(self, name):
        return getattr(self._i, name)

class Group(Forwarder):
    def __init__(self, iobj, installed_groups):
        super(Group, self).__init__(iobj)
        self._installed_groups = installed_groups
        self.selected = False

    def _packages_of_type(self, type_):
        return [pkg for pkg in self.packages if pkg.type == type_]

    @property
    def conditional_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_CONDITIONAL)

    @property
    def default_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_DEFAULT)

    @property
    def installed(self):
        return self.id in self._installed_groups

    @property
    def mandatory_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_MANDATORY)

    @property
    def optional_packages(self):
        return self._packages_of_type(libcomps.PACKAGE_TYPE_OPTIONAL)

class Category(Forwarder):
    pass

class Environment(Forwarder):
    pass

class Comps(object):
    def __init__(self):
        self._i = libcomps.Comps()
        self._installed_groups = set()

    def __len__(self):
        return _internal_comps_length(self._i)

    def add_from_xml_filename(self, fn):
        comps = libcomps.Comps()
        errors = comps.fromxml_f(fn)
        if errors and not _internal_comps_length(self._i):
            raise CompsException(' '.join(errors))
        self._i = self._i + comps

    @property
    def categories(self):
        return list(self.categories_iter)

    @property
    def categories_iter(self):
        return (Category(c) for c in self._i.categories)

    def compile(self, installed_pkgs):
        """ compile the groups into installed/available groups """

        self._installed_groups.clear()
        # convert the tuple list to a simple dict of pkgnames
        inst_names = set([pkg.name for pkg in installed_pkgs])
        for group in self.groups_iter:
            # if there are mandatory packages in the group, then make sure
            # they're all installed.  if any are missing, then the group
            # isn't installed.
            mandatory_packages = group.mandatory_packages
            if len(mandatory_packages):
                for pkg in mandatory_packages:
                    if pkg.name not in inst_names:
                        break
                else:
                    self._installed_groups.add(group.id)
            else:
                for pkg in itertools.chain(group.optional_packages,
                                           group.default_packages):
                    if pkg.name in inst_names:
                        self._installed_groups.add(group.id)
                        break

    @property
    def environments(self):
        return list(self.environments_iter)

    @property
    def environments_iter(self):
        return (Environment(e) for e in self._i.environments)

    @property
    def groups(self):
        return list(self.groups_iter)

    def groups_by_pattern(self, pattern, case_sensitive=False):
        return _by_pattern(self, pattern, case_sensitive, self.groups)

    @property
    def groups_iter(self):
        return (Group(g, self._installed_groups) for g in self._i.groups)
