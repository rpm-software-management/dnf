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

    def _build_repo(self, parser, id_, repofn):
        """Build a repository using the parsed data."""

        repo = dnf.repo.Repo(id_, self.conf)
        try:
            repo._populate(parser, id_, repofn, dnf.conf.PRIO_REPOCONFIG)
        except ValueError as e:
            msg = _("Repository '%s': Error parsing config: %s" % (id_, e))
            raise dnf.exceptions.ConfigError(msg)

        # Ensure that the repo name is set
        repo_name_object = repo._get_option('name')
        if repo_name_object._get_priority() == dnf.conf.PRIO_DEFAULT:
            msg = _("Repository '%s' is missing name in configuration, using id.")
            logger.warning(msg, id_)
        repo.name = ucd(repo.name)
        repo._substitutions.update(self.conf.substitutions)
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
                thisrepo = self._build_repo(parser, section, repofn)
            except (dnf.exceptions.RepoError, dnf.exceptions.ConfigError) as e:
                logger.warning(e)
                continue
            else:
                thisrepo.repofile = repofn

            thisrepo._configure_from_options(self.opts)

            yield thisrepo


class ModuleReader(object):
    def __init__(self, module_dir, conf_suffix="module"):
        self.conf_dir = module_dir
        self.conf_suffix = conf_suffix

    def __iter__(self):
        for module_path in sorted(glob.glob('{}/*.{}'.format(self.conf_dir, self.conf_suffix))):
            try:
                for module_conf in self._get_module_configs(module_path):
                    yield module_conf
            except dnf.exceptions.ConfigError:
                # TODO: handle properly; broken module conf must be considered as an error
                raise
                # logger.warning(_("Warning: failed loading '%s', skipping."), module_path)

    def _build_module(self, parser, id_, module_path):
        """Build a module using the parsed data."""

        module = dnf.conf.ModuleConf(section=id_, parser=parser)
        try:
            module._populate(parser, id_, module_path)
        except ValueError as e:
            msg = _("Module '%s': Error parsing config: %s" % (id_, e))
            raise dnf.exceptions.ConfigError(msg)

        # TODO: unset module.name?
        module._cfg = parser

        return module

    def _get_module_configs(self, module_path):
        """Parse and yield all module configs from a config file."""

        parser = dnf.conf.ConfigParser()
        try:
            confpp_obj = dnf.conf.parser.ConfigPreProcessor(module_path)
            parser.readfp(confpp_obj)
        except dnf.conf.ParsingError as e:
            msg = str(e)
            raise dnf.exceptions.ConfigError(msg)

        # Check sections in the .module file that was just slurped up
        for section in parser.sections():

            if section == 'main':
                continue

            try:
                module = self._build_module(parser, section, module_path)
            except (dnf.exceptions.RepoError, dnf.exceptions.ConfigError) as e:
                logger.warning(e)
                continue
            else:
                module.config_file = module_path

            yield module


class ModuleDefaultsReader(ModuleReader):
    def __init__(self, module_defaults_dir):
        super(ModuleDefaultsReader, self).__init__(module_defaults_dir, "defaults")

    def _build_module(self, parser, id_, defaults_path):
        """Build a module using the parsed data."""

        defaults = dnf.conf.ModuleDefaultsConf(section=id_, parser=parser)
        try:
            defaults._populate(parser, id_, defaults_path)
        except ValueError as e:
            msg = _("Module defaults '%s': Error parsing config: %s" % (id_, e))
            raise dnf.exceptions.ConfigError(msg)

        defaults._cfg = parser

        return defaults
