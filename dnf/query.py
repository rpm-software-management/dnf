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
import hawkey
import dnf.exceptions
import dnf.selector
import dnf.util
import time

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

    def unneeded(self, sack, yumdb, debug_solver=False):
        goal = dnf.goal.Goal(sack)
        goal.push_userinstalled(self.installed(), yumdb)
        solved = goal.run()
        if debug_solver:
            goal.write_debugdata('./debugdata-autoremove')
        assert solved
        unneeded = goal.list_unneeded()
        return self.filter(pkg=unneeded)

    def downgrades(self):
        # :api
        return self.filter(downgrades=True)

    def duplicated(self):
        # :api
        installed_na = self.installed().na_dict()
        duplicated = []
        for (name, arch), pkgs in installed_na.items():
            if len(pkgs) > 1:
                duplicated.extend(pkgs)
        return self.filter(pkg=duplicated)

    def extras(self):
        # anything installed but not in a repo is an extra
        avail_dict = self.available().pkgtup_dict()
        inst_dict = self.installed().pkgtup_dict()
        extras = []
        for pkgtup, pkgs in inst_dict.items():
            if pkgtup not in avail_dict:
                extras.extend(pkgs)
        return self.filter(pkg=extras)

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

    def latest(self, limit=1):
        # :api
        if limit == 1:
            return self.filter(latest_per_arch=True)
        else:
            pkgs_na = self.na_dict()
            latest_pkgs = []
            for pkg_list in pkgs_na.values():
                pkg_list.sort(reverse=True)
                if limit > 0:
                    latest_pkgs.extend(pkg_list[0:limit])
                else:
                    latest_pkgs.extend(pkg_list[-limit:])
            return self.filter(pkg=latest_pkgs)

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

    def recent(self, recent):
        now = time.time()
        recentlimit = now - (recent*86400)
        recent = [po for po in self if int(po.buildtime) > recentlimit]
        return self.filter(pkg=recent)

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

    q = sack.query()
    flags = []
    if ignore_case:
        flags.append(hawkey.ICASE)

    if any(map(dnf.util.is_glob_pattern, patterns)):
        kw = 'provides__glob'
    else:
        kw = 'provides'

    q.filterm(*flags, **{kw: patterns})
    if get_query:
        return q
    return q.run()


def per_pkgtup_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        d.setdefault(pkg.pkgtup, []).append(pkg)
    return d


def per_nevra_dict(pkg_list):
    return {ucd(pkg):pkg for pkg in pkg_list}


def autoremove_pkgs(query, sack, yumdb, debug_solver=False):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    return query.unneeded(sack, yumdb, debug_solver).run()


def duplicated_pkgs(query, installonlypkgs):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    installonly = query.installed().filter(provides__glob=installonlypkgs)
    exclude = [pkg.name for pkg in installonly]
    return query.filter(name__neq=exclude).duplicated().run()


def extras_pkgs(query):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    return query.extras.run()


def installonly_pkgs(query, installonlypkgs):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    return query.installed().filter(provides__glob=installonlypkgs).run()


def latest_limit_pkgs(query, limit):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    return query.latest(limit).run()


def recent_pkgs(query, recent):
    # compat: erase in 2.0.0
    # required by dnf-plugins-core =< 0.1.12-2
    return query.recent(recent).run()
