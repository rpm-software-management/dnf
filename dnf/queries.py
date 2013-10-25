# queries.py
# Often reused hawkey queries.
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

import functools
import hawkey
import itertools
import types
import dnf.exceptions
import dnf.selector
from dnf.util import first, is_glob_pattern

from dnf.yum.i18n import _
from .pycomp import basestring

def is_nevra(pattern):
    try:
        hawkey.split_nevra(pattern)
    except hawkey.ValueException:
        return False
    return True

class Query(hawkey.Query):
    def available(self):
        return self.filter(reponame__neq=hawkey.SYSTEM_REPO_NAME)

    def downgrades(self):
        return self.filter(downgrades=True)

    def filter_autoglob(self, **kwargs):
        nargs = {}
        for (key, value) in kwargs.items():
            if dnf.queries.is_glob_pattern(value):
                nargs[key + "__glob"] = value
            else:
                nargs[key] = value
        return self.filter(**nargs)

    def installed(self):
        return self.filter(reponame=hawkey.SYSTEM_REPO_NAME)

    def latest(self):
        return self.filter(latest_per_arch=True)

    def upgrades(self):
        return self.filter(upgrades=True)

    def name_dict(self):
        d = {}
        for pkg in self:
            d.setdefault(pkg.name, []).append(pkg)
        return d

    def na_dict(self):
        return per_arch_dict(self.run())

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

class Subject(object):
    def __init__(self, pkg_spec, ignore_case=False):
        self.subj = hawkey.Subject(pkg_spec) # internal subject
        self.icase = ignore_case

    def _nevra_to_filters(self, query, nevra):
        if nevra.name is not None:
            if is_glob_pattern(nevra.name):
                query.filterm(*self._query_flags, name__glob=nevra.name)
            else:
                query.filterm(*self._query_flags, name=nevra.name)
        if nevra.arch is not None:
            query.filterm(arch=nevra.arch)
        if nevra.epoch is not None:
            query.filterm(epoch=nevra.epoch)
        if nevra.version is not None:
            version = nevra.version
            if is_glob_pattern(version):
                query.filterm(version__glob=version)
            else:
                query.filterm(version=version)
        if nevra.release is not None:
            query.filterm(release=nevra.release)
        return query

    @staticmethod
    def _nevra_to_selector(sltr, nevra):
        if nevra.name is not None:
            sltr.set_autoglob(name=nevra.name)
        if nevra.version is not None:
            evr = nevra.version
            if nevra.epoch is not None and nevra.epoch > 0:
                evr = "%d:%s" % (nevra.epoch, evr)
            if nevra.release is None:
                sltr.set(version=evr)
            else:
                evr = "%s-%s" % (evr, nevra.release)
                sltr.set(evr=evr)
        if nevra.arch is not None:
            sltr.set(arch=nevra.arch)
        return sltr

    @property
    def _query_flags(self):
        flags = []
        if self.icase:
            flags.append(hawkey.ICASE)
        return flags

    @property
    def pattern(self):
        return self.subj.pattern

    def get_best_query(self, sack, with_provides=True, forms=None):
        pat = self.subj.pattern
        if pat.startswith('/'):
            return sack.query().filter_autoglob(file=pat)

        kwargs = {'allow_globs' : True,
                  'icase'	: self.icase}
        if forms:
            kwargs['form'] = forms
        nevra = first(self.subj.nevra_possibilities_real(sack, **kwargs))
        if nevra:
            return self._nevra_to_filters(sack.query(), nevra)

        if with_provides:
            reldeps = self.subj.reldep_possibilities_real(sack, icase=self.icase)
            reldep = first(reldeps)
            if reldep:
                return sack.query().filter(provides=reldep)
        return sack.query().filter(empty=True)

    def get_best_selector(self, sack, forms=None):
        kwargs = {'allow_globs' : True}
        if forms:
            kwargs['form'] = forms
        nevra = first(self.subj.nevra_possibilities_real(sack, **kwargs))
        if nevra:
            return self._nevra_to_selector(dnf.selector.Selector(sack), nevra)

        reldep = first(self.subj.reldep_possibilities_real(sack))
        if reldep:
             # we can not handle full Reldeps
            dep = str(reldep)
            assert(not (set(dep) & set("<=>")))
            return dnf.selector.Selector(sack).set(provides=str(reldep))
        return None

def _construct_result(sack, patterns, ignore_case,
                      include_repo=None, exclude_repo=None,
                      downgrades_only=False,
                      updates_only=False,
                      latest_only=False,
                      get_query=False):
    """ Generic query builder.

        patterns can be:
        :: a string pattern we will use to match against package names
        :: a list of strings representing patterns that are ORed together
        :: None in which case we query over all names.

        If 'get_query' is False the built query is evaluated and matching
        packages returned. Otherwise the query itself is returned (for instance
        to be further specified and then evaluated).
    """
    if isinstance(patterns, basestring):
        patterns = [patterns]
    elif patterns is None:
        patterns = []
    glob = len(list(filter(is_glob_pattern, patterns))) > 0

    flags = []
    q = sack.query()
    if ignore_case:
        flags.append(hawkey.ICASE)
    if len(patterns) == 0:
        pass
    elif glob:
        q.filterm(*flags, name__glob=patterns)
    else:
        q.filterm(*flags, name=patterns)
    if include_repo:
        q.filterm(reponame__eq=include_repo)
    if exclude_repo:
        q.filterm(reponame__neq=exclude_repo)
    q.filterm(downgrades=downgrades_only)
    q.filterm(upgrades=updates_only)
    q.filterm(latest__eq=latest_only)
    if get_query:
        return q
    return q.run()

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

def latest_per_arch(sack, patterns, ignore_case=False, include_repo=None,
                    exclude_repo=None):
    matching = _construct_result(sack, patterns, ignore_case,
                                 include_repo, exclude_repo,
                                 latest_only=True)
    latest = {} # (name, arch) -> pkg mapping
    for pkg in matching:
        key = (pkg.name, pkg.arch)
        latest[key] = pkg
    return latest

def latest_available_per_arch(sack, patterns, ignore_case=False):
    return latest_per_arch(sack, patterns, ignore_case,
                           exclude_repo=hawkey.SYSTEM_REPO_NAME)

def downgrades_by_name(sack, patterns, ignore_case=False, latest_only=False):
    return _construct_result(sack, patterns, ignore_case,
                             latest_only=latest_only,
                             downgrades_only=True)

def updates_by_name(sack, patterns, ignore_case=False, latest_only=False):
    return _construct_result(sack, patterns, ignore_case,
                             latest_only=latest_only,
                             updates_only=True)

def per_arch_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        key = (pkg.name, pkg.arch)
        d.setdefault(key, []).append(pkg)
    return d

def per_pkgtup_dict(pkg_list):
    d = {}
    for pkg in pkg_list:
        d.setdefault(pkg.pkgtup, []).append(pkg)
    return d

def per_nevra_dict(pkg_list):
    return {str(pkg):pkg for pkg in pkg_list}
