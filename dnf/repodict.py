# repodict.py
# Managing repo configuration in DNF.
#
# Copyright (C) 2013-2016 Red Hat, Inc.
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
from dnf.exceptions import ConfigError
from dnf.i18n import _

import dnf.util
import libdnf.conf
import fnmatch
import os

logger = dnf.util.logger


class RepoDict(dict):
    # :api
    def add(self, repo):
        # :api
        id_ = repo.id
        if id_ in self:
            msg = 'Repository %s is listed more than once in the configuration'
            raise ConfigError(msg % id_)
        try:
            repo._repo.verify()
        except RuntimeError as e:
            raise ConfigError("{0}".format(e))
        self[id_] = repo

    def all(self):
        # :api
        return dnf.util.MultiCallList(self.values())

    def _any_enabled(self):
        return not dnf.util.empty(self.iter_enabled())

    def _enable_sub_repos(self, sub_name_fn):
        for repo in self.iter_enabled():
            for found in self.get_matching(sub_name_fn(repo.id)):
                if not found.enabled:
                    logger.info(_('enabling %s repository'), found.id)
                    found.enable()

    def add_new_repo(self, repoid, conf, baseurl=(), **kwargs):
        # :api
        """
        Creates new repo object and add it into RepoDict. Variables in provided values will be
        automatically substituted using conf.substitutions (like $releasever, ...)

        @param repoid: Repo ID - string
        @param conf: dnf Base().conf object
        @param baseurl: List of strings
        @param kwargs: keys and values that will be used to setattr on dnf.repo.Repo() object
        @return: dnf.repo.Repo() object
        """
        def substitute(values):
            if isinstance(values, str):
                return libdnf.conf.ConfigParser.substitute(values, conf.substitutions)
            elif isinstance(values, list) or isinstance(values, tuple):
                substituted = []
                for value in values:
                    if isinstance(value, str):
                        substituted.append(
                            libdnf.conf.ConfigParser.substitute(value, conf.substitutions))
                    if substituted:
                        return substituted
            return values

        repo = dnf.repo.Repo(repoid, conf)
        for path in baseurl:
            if '://' not in path:
                path = 'file://{}'.format(os.path.abspath(path))
            repo.baseurl += [substitute(path)]
        for (key, value) in kwargs.items():
            setattr(repo, key, substitute(value))
        self.add(repo)
        logger.info(_("Added %s repo from %s"), repoid, ', '.join(baseurl))
        return repo

    def enable_debug_repos(self):
        # :api
        """enable debug repos corresponding to already enabled binary repos"""

        def debug_name(name):
            return ("{}-debug-rpms".format(name[:-5]) if name.endswith("-rpms")
                    else "{}-debuginfo".format(name))

        self._enable_sub_repos(debug_name)

    def enable_source_repos(self):
        # :api
        """enable source repos corresponding to already enabled binary repos"""

        def source_name(name):
            return ("{}-source-rpms".format(name[:-5]) if name.endswith("-rpms")
                    else "{}-source".format(name))

        self._enable_sub_repos(source_name)

    def get_matching(self, key):
        # :api
        if dnf.util.is_glob_pattern(key):
            l = [self[k] for k in self if fnmatch.fnmatch(k, key)]
            return dnf.util.MultiCallList(l)
        repo = self.get(key, None)
        if repo is None:
            return dnf.util.MultiCallList([])
        return dnf.util.MultiCallList([repo])

    def iter_enabled(self):
        # :api
        return (r for r in self.values() if r.enabled)

    def items(self):
        """return repos sorted by priority"""
        return (item for item in sorted(super(RepoDict, self).items(),
                                        key=lambda x: (x[1].priority, x[1].cost)))

    def __iter__(self):
        return self.keys()

    def keys(self):
        return (k for k, v in self.items())

    def values(self):
        return (v for k, v in self.items())
