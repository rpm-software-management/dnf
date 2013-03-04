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

import fnmatch
import dnf.util
from dnf.yum.Errors import DuplicateRepoError, RepoError

class MultiCallList(list):
    def __init__(self, iterable):
        self.extend(iterable)

    def __getattr__(self, what):
        def fn(*args, **kwargs):
            def call_what(v):
                method = getattr(v, what)
                return method(*args, **kwargs)
            return map(call_what, self)
        return fn

class RepoDict(dict):
    def add(self, repo):
        id_ = repo.id
        if id_ in self:
            msg = 'Repository %s is listed more than once in the configuration'
            raise Errors.DuplicateRepoError(msg % id_)
        self[id_] = repo

    @property
    def all(self):
        return MultiCallList(self.itervalues())

    def any_enabled(self):
        return not dnf.util.empty(self.iter_enabled())

    def enabled(self):
        return [r for r in self.itervalues() if r.enabled]

    def get_multiple(self, key):
        if dnf.util.is_glob_pattern(key):
            l = [self[k] for k in self if fnmatch.fnmatch(k, key)]
            return MultiCallList(l)
        return MultiCallList([self[key]])

    def iter_enabled(self):
        return (r for r in self.itervalues() if r.enabled)
