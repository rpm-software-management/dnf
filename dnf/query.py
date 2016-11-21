# query.py
# Implements Query.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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


class Query(hawkey.Query):
    # :api

    def available(self):
        # :api
        return self.filter(reponame__neq=hawkey.SYSTEM_REPO_NAME)

    def _unneeded(self, sack, yumdb, debug_solver=False):
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
        installed_name = self.installed()._name_dict()
        duplicated = []
        for name, pkgs in installed_name.items():
            if len(pkgs) > 1:
                for x in range(0, len(pkgs)):
                    dups = False
                    for y in range(x+1, len(pkgs)):
                        if not ((pkgs[x].evr_cmp(pkgs[y]) == 0)
                                and (pkgs[x].arch != pkgs[y].arch)):
                            duplicated.append(pkgs[y])
                            dups = True
                    if dups:
                        duplicated.append(pkgs[x])
        return self.filter(pkg=duplicated)

    def extras(self):
        # :api
        # anything installed but not in a repo is an extra
        avail_dict = self.available()._pkgtup_dict()
        inst_dict = self.installed()._pkgtup_dict()
        extras = []
        for pkgtup, pkgs in inst_dict.items():
            if pkgtup not in avail_dict:
                extras.extend(pkgs)
        return self.filter(pkg=extras)

    def filter(self, *args, **kwargs):
        # :api
        return super(Query, self).filter(*args, **kwargs)

    def _filterm(self, *args, **kwargs):
        nargs = {}
        for (key, value) in kwargs.items():
            if (key.endswith("__glob") and not dnf.util.is_glob_pattern(value)):
                # remove __glob when pattern is not glob
                key = key[:-6]
            nargs[key] = value
        return super(Query, self)._filterm(*args, **nargs)

    def installed(self):
        # :api
        return self.filter(reponame=hawkey.SYSTEM_REPO_NAME)

    def latest(self, limit=1):
        # :api
        if limit == 1:
            return self.filter(latest_per_arch=True)
        else:
            pkgs_na = self._na_dict()
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

    def _name_dict(self):
        d = {}
        for pkg in self:
            d.setdefault(pkg.name, []).append(pkg)
        return d

    def _na_dict(self):
        d = {}
        for pkg in self.run():
            key = (pkg.name, pkg.arch)
            d.setdefault(key, []).append(pkg)
        return d

    def _pkgtup_dict(self):
        return _per_pkgtup_dict(self.run())

    def _recent(self, recent):
        now = time.time()
        recentlimit = now - (recent*86400)
        recent = [po for po in self if int(po.buildtime) > recentlimit]
        return self.filter(pkg=recent)

    def _nevra(self, *args):
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


def _by_provides(sack, patterns, ignore_case=False, get_query=False):
    if isinstance(patterns, basestring):
        patterns = [patterns]

    q = sack.query()
    flags = []
    if ignore_case:
        flags.append(hawkey.ICASE)

    q._filterm(*flags, provides__glob=patterns)
    if get_query:
        return q
    return q.run()


def _per_pkgtup_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        d.setdefault(pkg.pkgtup, []).append(pkg)
    return d


def _per_nevra_dict(pkg_list):
    return {ucd(pkg):pkg for pkg in pkg_list}
