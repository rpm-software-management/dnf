# queries.py
# Often reused hawkey queries.
#
# Copyright (C) 2012  Red Hat, Inc.
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

import hawkey
import itertools
import types

def is_glob_pattern(pattern):
    return set(pattern) & set("*[?")

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
    if type(patterns) in types.StringTypes:
        patterns = [patterns]
    elif patterns is None:
        patterns = []
    glob = len(filter(is_glob_pattern, patterns)) > 0

    flags = []
    q = hawkey.Query(sack)
    if ignore_case:
        flags = [hawkey.ICASE]
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

def installed(sack, get_query=False):
    return installed_by_name(sack, None, get_query=get_query)

def installed_by_name(sack, patterns, ignore_case=False, get_query=False):
    return _construct_result(sack, patterns, ignore_case,
                             include_repo=hawkey.SYSTEM_REPO_NAME,
                             get_query=get_query)

def available_by_name(sack, patterns, ignore_case=False, latest_only=False):
    return _construct_result(sack, patterns, ignore_case,
                             exclude_repo=hawkey.SYSTEM_REPO_NAME,
                             latest_only=latest_only)

def installed_exact(sack, name, evr, arch, get_query=False):
    q = _construct_result(sack, name, False, get_query=True,
                          include_repo=hawkey.SYSTEM_REPO_NAME)
    q.filterm(arch__eq=arch, evr__eq=evr);
    return q if get_query else q.run()

def by_name(sack, patterns, ignore_case=False, get_query=False):
    return _construct_result(sack, patterns, ignore_case, get_query=get_query)

def by_file(sack, patterns, ignore_case=False, get_query=False):
    if type(patterns) in types.StringTypes:
        patterns = [patterns]

    glob = len(filter(is_glob_pattern, patterns)) > 0
    flags = []
    q = hawkey.Query(sack)
    if ignore_case:
        flags = [hawkey.ICASE]
    if glob:
        q.filterm(*flags, file__glob=patterns)
    else:
        q.filterm(*flags, file=patterns)

    if get_query:
        return q
    return q.run()

def by_repo(sack, reponame):
    return _construct_result(sack, None, ignore_case=False, include_repo=reponame)

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

def latest_installed_per_arch(sack, patterns, ignore_case=False):
    return latest_per_arch(sack, patterns, ignore_case,
                           include_repo=hawkey.SYSTEM_REPO_NAME)

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
