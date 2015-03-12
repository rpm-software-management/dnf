# query.py
# Implements Query.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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
from __future__ import unicode_literals
import functools
import hawkey
import dnf.exceptions
import dnf.selector
import dnf.util

from dnf.i18n import ucd
from dnf.pycomp import basestring

def is_nevra(pattern):
    try:
        hawkey.split_nevra(pattern)
    except hawkey.ValueException:
        return False
    return True

class Query(hawkey.Query):
    # :api
    # :api also includes hawkey.Query.filter

    def available(self):
        # :api
        return self.filter(reponame__neq=hawkey.SYSTEM_REPO_NAME)

    def downgrades(self):
        # :api
        return self.filter(downgrades=True)

    def filter_autoglob(self, *args, **kwargs):
        nargs = {}
        for (key, value) in kwargs.items():
            if dnf.util.is_glob_pattern(value):
                nargs[key + "__glob"] = value
            else:
                nargs[key] = value
        return self.filter(*args, **nargs)

    def installed(self):
        # :api
        return self.filter(reponame=hawkey.SYSTEM_REPO_NAME)

    def latest(self):
        # :api
        return self.filter(latest_per_arch=True)

    def upgrades(self):
        # :api
        return self.filter(upgrades=True)

    def name_dict(self):
        d = {}
        for pkg in self:
            d.setdefault(pkg.name, []).append(pkg)
        return d

    def na_dict(self):
        d = {}
        for pkg in self.run():
            key = (pkg.name, pkg.arch)
            d.setdefault(key, []).append(pkg)
        return d

    def pkgtup_dict(self):
        return per_pkgtup_dict(self.run())

    def nevra(self, *args):
        args_len = len(args)
        if args_len == 3:
            return self.filter(name=args[0], evr=args[1], arch=args[2])
        if args_len == 1:
            nevra = hawkey.split_nevra(args[0])
        elif args_len == 5:
            nevra = args
        else:
            raise TypeError("nevra() takes 1, 3 or 5 str params")
        return self.filter(
            name=nevra.name, epoch=nevra.epoch, version=nevra.version,
            release=nevra.release, arch=nevra.arch)


def by_provides(sack, patterns, ignore_case=False, get_query=False):
    if isinstance(patterns, basestring):
        patterns = [patterns]
    try:
        reldeps = list(map(functools.partial(hawkey.Reldep, sack), patterns))
    except hawkey.ValueException:
        return sack.query().filter(empty=True)
    q = sack.query()
    flags = []
    if ignore_case:
        flags.append(hawkey.ICASE)
    q.filterm(*flags, provides=reldeps)
    if get_query:
        return q
    return q.run()

def duplicated_pkgs(query, installonlypkgs):
    installed_na = query.installed().na_dict()
    duplicated = []
    for (name, arch), pkgs in installed_na.items():
        if len(pkgs) > 1 and name not in installonlypkgs:
            duplicated.extend(pkgs)
    return duplicated

def installonly_pkgs(query, installonlypkgs):
    q = query.filter(name=installonlypkgs).installed()
    return q.run()

def per_pkgtup_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        d.setdefault(pkg.pkgtup, []).append(pkg)
    return d

def per_nevra_dict(pkg_list):
    return {ucd(pkg):pkg for pkg in pkg_list}
