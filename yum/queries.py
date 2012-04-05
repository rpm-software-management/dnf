# package.py
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

def _is_glob_pattern(pattern):
    return set(pattern) & set("*[?")

def _construct_result(sack, patterns, ignore_case,
                      include_repo=None, exclude_repo=None,
                      updates_only=False, latest_only=False):
    queries = []
    for p in patterns:
        q = hawkey.Query(sack)
        flags = []
        if ignore_case:
            flags = [hawkey.ICASE]
        # autodetect glob patterns
        if _is_glob_pattern(p):
            q.filter(*flags, name__glob=p)
        else:
            q.filter(*flags, name__eq=p)
        if include_repo:
            q.filter(repo__eq=include_repo)
        if exclude_repo:
            q.filter(repo__neq=exclude_repo)
        q.filter(updates__eq=updates_only)
        q.filter(latest__eq=latest_only)
        queries.append(q)
    return itertools.chain.from_iterable(queries)

def installed_by_name(sack, patterns, ignore_case=False):
    return _construct_result(sack, patterns, ignore_case,
                             include_repo=hawkey.SYSTEM_REPO_NAME)

def available_by_name(sack, patterns, ignore_case=False, latest_only=False):
    return _construct_result(sack, patterns, ignore_case,
                             exclude_repo=hawkey.SYSTEM_REPO_NAME,
                             latest_only=latest_only)

def by_name(sack, patterns, ignore_case=False):
    return _construct_result(sack, patterns, ignore_case)

def by_file(sack, patterns, ignore_case=False):
    queries = []
    for p in patterns:
        q = hawkey.Query(sack)
        flags = []
        if ignore_case:
            flags = [hawkey.ICASE]
        if _is_glob_pattern(p):
            q.filter(*flags, file__glob=p)
        else:
            q.filter(*flags, file__eq=p)
        queries.append(q)
    return itertools.chain.from_iterable(queries)

def latest_per_arch(sack, patterns, ignore_case=False, include_repo=None,
                    exclude_repo=None):
    matching = _construct_result(sack, patterns, ignore_case,
                                 include_repo, exclude_repo)
    latest = {} # (name, arch) -> pkg mapping
    for pkg in matching:
        key = (pkg.name, pkg.arch)
        if key in latest and latest[key].evr_gt(pkg):
            continue
        latest[key] = pkg
    return latest

def latest_installed_per_arch(sack, patterns, ignore_case=False):
    return latest_per_arch(sack, patterns, ignore_case,
                           include_repo=hawkey.SYSTEM_REPO_NAME)

def latest_available_per_arch(sack, patterns, ignore_case=False):
    return latest_per_arch(sack, patterns, ignore_case,
                           exclude_repo=hawkey.SYSTEM_REPO_NAME)

def updates_by_name(sack, patterns, ignore_case=False):
    return _construct_result(sack, patterns, ignore_case,
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
