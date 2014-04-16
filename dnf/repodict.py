# repodict.py
# Managing repo configuration in DNF.
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

from __future__ import unicode_literals
import fnmatch
import dnf.util
from dnf.exceptions import ConfigError, RepoError

class MultiCallList(list):
    def __init__(self, iterable):
        self.extend(iterable)

    def __getattr__(self, what):
        def fn(*args, **kwargs):
            def call_what(v):
                method = getattr(v, what)
                return method(*args, **kwargs)
            return list(map(call_what, self))
        return fn

    def __setattr__(self, what, val):
        def setter(item):
            setattr(item, what, val)
        return list(map(setter, self))

class RepoDict(dict):
    # :api
    def add(self, repo):
        # :api
        id_ = repo.id
        if id_ in self:
            msg = 'Repository %s is listed more than once in the configuration'
            raise ConfigError(msg % id_)
        msg = repo.valid()
        if msg:
            raise ConfigError(msg)
        self[id_] = repo

    def all(self):
        # :api
        return MultiCallList(self.values())

    def any_enabled(self):
        return not dnf.util.empty(self.iter_enabled())

    def enabled(self):
        return [r for r in self.values() if r.enabled]

    def get_matching(self, key):
        # :api
        if dnf.util.is_glob_pattern(key):
            l = [self[k] for k in self if fnmatch.fnmatch(k, key)]
            return MultiCallList(l)
        repo = self.get(key, None)
        if repo is None:
            return MultiCallList([])
        return MultiCallList([repo])

    def iter_enabled(self):
        # :api
        return (r for r in self.values() if r.enabled)
