# read.py
# Reading configuration from files.
#
# Copyright (C) 2014-2017 Red Hat, Inc.
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
from dnf.i18n import _, ucd
import dnf.conf
import libdnf.conf
import dnf.exceptions
import dnf.repo
import glob
import logging
import os

logger = logging.getLogger('dnf')


class RepoReader(object):
    def __init__(self, conf, opts):
        self.conf = conf
        self.opts = opts

    def __iter__(self):
        # get the repos from the main yum.conf file
        for r in self._get_repos(self.conf.config_file_path):
            yield r

        # read .repo files from directories specified by conf.reposdir
        repo_configs = []
        for reposdir in self.conf.reposdir:
            for path in glob.glob(os.path.join(reposdir, "*.repo")):
                repo_configs.append(path)

        # remove .conf suffix before calling the sort function
        # also split the path so the separators are not treated as ordinary characters
        repo_configs.sort(key=lambda x: dnf.util.split_path(x[:-5]))

        for repofn in repo_configs:
            try:
                for r in self._get_repos(repofn):
                    yield r
            except dnf.exceptions.ConfigError:
                logger.warning(_("Warning: failed loading '%s', skipping."),
                               repofn)

    def _build_repo(self, parser, id_, repofn):
        """Build a repository using the parsed data."""

        substituted_id = libdnf.conf.ConfigParser.substitute(id_, self.conf.substitutions)

        # Check the repo.id against the valid chars
        invalid = dnf.repo.repo_id_invalid(substituted_id)
        if invalid is not None:
            if substituted_id != id_:
                msg = _("Bad id for repo: {} ({}), byte = {} {}").format(substituted_id, id_,
                                                                         substituted_id[invalid],
                                                                         invalid)
            else:
                msg = _("Bad id for repo: {}, byte = {} {}").format(id_, id_[invalid], invalid)
            raise dnf.exceptions.ConfigError(msg)

        repo = dnf.repo.Repo(substituted_id, self.conf)
        try:
            repo._populate(parser, id_, repofn, dnf.conf.PRIO_REPOCONFIG)
        except ValueError as e:
            if substituted_id != id_:
                msg = _("Repository '{}' ({}): Error parsing config: {}").format(substituted_id,
                                                                                 id_, e)
            else:
                msg = _("Repository '{}': Error parsing config: {}").format(id_, e)
            raise dnf.exceptions.ConfigError(msg)

        # Ensure that the repo name is set
        if repo._get_priority('name') == dnf.conf.PRIO_DEFAULT:
            if substituted_id != id_:
                msg = _("Repository '{}' ({}) is missing name in configuration, using id.").format(
                    substituted_id, id_)
            else:
                msg = _("Repository '{}' is missing name in configuration, using id.").format(id_)
            logger.warning(msg)
        repo.name = ucd(repo.name)
        repo._substitutions.update(self.conf.substitutions)
        repo.cfg = parser

        return repo

    def _get_repos(self, repofn):
        """Parse and yield all repositories from a config file."""

        substs = self.conf.substitutions
        parser = libdnf.conf.ConfigParser()
        parser.setSubstitutions(substs)
        try:
            parser.read(repofn)
        except RuntimeError as e:
            raise dnf.exceptions.ConfigError(_('Parsing file "{}" failed: {}').format(repofn, e))
        except IOError as e:
            logger.warning(e)

        # Check sections in the .repo file that was just slurped up
        for section in parser.getData():

            if section == 'main':
                continue

            try:
                thisrepo = self._build_repo(parser, ucd(section), repofn)
            except (dnf.exceptions.RepoError, dnf.exceptions.ConfigError) as e:
                logger.warning(e)
                continue
            else:
                thisrepo.repofile = repofn

            thisrepo._configure_from_options(self.opts)

            yield thisrepo
