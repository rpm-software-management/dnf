# read.py
# Reading configuration from files.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
import dnf.conf.parser
import dnf.exceptions
import dnf.repo
import glob
import logging

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
        for repofn in (repofn for reposdir in self.conf.reposdir
                       for repofn in sorted(glob.glob('%s/*.repo' % reposdir))):
            try:
                for r in self._get_repos(repofn):
                    yield r
            except dnf.exceptions.ConfigError:
                logger.warning(_("Warning: failed loading '%s', skipping."),
                               repofn)

    def _build_repo(self, parser, id_):
        """Build a repository using the parsed data."""

        repo = dnf.repo.Repo(id_, self.conf)
        try:
            repo._populate(parser, id_, dnf.conf.PRIO_REPOCONFIG)
        except ValueError as e:
            msg = _("Repository '%s': Error parsing config: %s" % (id_, e))
            raise dnf.exceptions.ConfigError(msg)

        # Ensure that the repo name is set
        if not repo.name:
            repo.name = id_
            msg = _("Repository '%s' is missing name in configuration, using id.")
            logger.warning(msg, id_)
        repo.name = ucd(repo.name)
        repo.substitutions.update(self.conf.substitutions)
        repo.cfg = parser

        return repo

    def _get_repos(self, repofn):
        """Parse and yield all repositories from a config file."""

        substs = self.conf.substitutions
        parser = dnf.conf.ConfigParser()
        try:
            confpp_obj = dnf.conf.parser.ConfigPreProcessor(repofn,
                                                            variables=substs)

            parser.readfp(confpp_obj)
        except dnf.conf.ParsingError as e:
            msg = str(e)
            raise dnf.exceptions.ConfigError(msg)

        # Check sections in the .repo file that was just slurped up
        for section in parser.sections():

            if section == 'main':
                continue

            # Check the repo.id against the valid chars
            invalid = dnf.repo.repo_id_invalid(section)
            if invalid is not None:
                logger.warning("Bad id for repo: %s, byte = %s %d", section,
                               section[invalid], invalid)
                continue

            try:
                thisrepo = self._build_repo(parser, section)
            except (dnf.exceptions.RepoError, dnf.exceptions.ConfigError) as e:
                logger.warning(e)
                continue
            else:
                thisrepo.repofile = repofn

            thisrepo._configure_from_options(self.opts)

            yield thisrepo
