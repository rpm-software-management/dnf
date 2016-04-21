# Copyright 2006 Duke University
# Copyright (C) 2012-2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Written by Seth Vidal

"""
Classes for subcommands of the yum command line interface.
"""

from __future__ import print_function
from __future__ import unicode_literals
from dnf.i18n import _, ucd

import dnf.cli
import dnf.const
import dnf.exceptions
import dnf.i18n
import dnf.pycomp
import dnf.util
import dnf.yum.config
import functools
import logging
import operator
import os
import time

logger = logging.getLogger('dnf')
_RPM_VERIFY = _("To diagnose the problem, try running: '%s'.") % \
    'rpm -Va --nofiles --nodigest'
_RPM_REBUILDDB = _("You probably have corrupted RPMDB, running '%s'"
                   " might fix the issue.") % 'rpm --rebuilddb'

gpg_msg = \
    _("""You have enabled checking of packages via GPG keys. This is a good thing.
However, you do not have any GPG public keys installed. You need to download
the keys for packages you wish to install and install them.
You can do that by running the command:
    rpm --import public.gpg.key


Alternatively you can specify the url to the key you would like to use
for a repository in the 'gpgkey' option in a repository section and DNF
will install it for you.

For more information contact your distribution or package provider.""")


def checkGPGKey(base, cli):
    """Verify that there are gpg keys for the enabled repositories in the
    rpm database.

    :param base: a :class:`dnf.Base` object.
    :raises: :class:`cli.CliError`
    """
    if cli.nogpgcheck:
        return
    if not base._gpg_key_check():
        for repo in base.repos.iter_enabled():
            if (repo.gpgcheck or repo.repo_gpgcheck) and not repo.gpgkey:
                logger.critical("\n%s\n", gpg_msg)
                logger.critical(_("Problem repository: %s"), repo)
                raise dnf.cli.CliError

def checkEnabledRepo(base, possible_local_files=[]):
    """Verify that there is at least one enabled repo.

    :param base: a :class:`dnf.Base` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`:
    """
    if base.repos.any_enabled():
        return

    for lfile in possible_local_files:
        if lfile.endswith(".rpm") and os.path.exists(lfile):
            return

    msg = _('There are no enabled repos.')
    raise dnf.cli.CliError(msg)


class Command(object):
    """Abstract base class for CLI commands."""

    activate_sack = False
    aliases = [] # :api
    allow_erasing = False
    load_available_repos = True
    resolve = False
    summary = ""  # :api
    usage = ""  # :api
    writes_rpmdb = False
    opts = None

    def __init__(self, cli):
        # :api
        self.cli = cli

    @property
    def base(self):
        # :api
        return self.cli.base

    @property
    def basecmd(self):
        # :api
        return self.aliases[0]

    @property
    def output(self):
        return self.cli.base.output

    def set_argparser(self, parser):
        """Define command specific options and arguments. #:api"""
        pass

    def configure(self, args):
        # :api
        """Do any command-specific configuration."""

        # built-in commands use class/instance attributes to state their demands:
        demands = self.cli.demands
        if self.activate_sack:
            demands.sack_activation = True
        if self.allow_erasing:
            demands.allow_erasing = True
        if self.load_available_repos:
            demands.available_repos = True
        if self.resolve:
            demands.resolving = True
        if self.writes_rpmdb:
            demands.root_user = True

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            return (_RPM_VERIFY, _RPM_REBUILDDB)
        raise NotImplementedError('error not supported yet: %s' % error)

    def run(self, extcmds):
        # :api
        """Execute the command

        :param extcmds: a list of arguments passed to *basecmd*

        """
        pass

    def run_transaction(self):
        """Finalize operations post-transaction."""
        pass

class InfoCommand(Command):
    """A class containing methods needed by the cli to execute the
    info command.
    """

    aliases = ('info',)
    summary = _('display details about a package or group of packages')

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        DEFAULT_PKGNARROW = 'all'
        if len(extcmds) == 0:
            return DEFAULT_PKGNARROW, extcmds

        pkgnarrows = {'available', 'installed', 'extras', 'upgrades', 'autoremove',
                      'recent', 'obsoletes', DEFAULT_PKGNARROW}
        if extcmds[0] in pkgnarrows:
            return extcmds[0], extcmds[1:]
        elif extcmds[0] == 'updates':
            return 'upgrades', extcmds[1:]
        else:
            return DEFAULT_PKGNARROW, extcmds

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', metavar=_('PACKAGE'),
                             help=("[%s | all | available | installed | updates"
                                   " | extras | autoremove | obsoletes | recent]"
                                   % _('PACKAGE')))

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def run(self, extcmds):
        pkgnarrow, patterns = self.parse_extcmds(self.opts.packages)
        return self.base.output_packages('info', pkgnarrow, patterns)

class ListCommand(InfoCommand):
    """A class containing methods needed by the cli to execute the
    list command.
    """

    aliases = ('list',)
    summary = _('list a package or groups of packages')

    def run(self, extcmds):
        pkgnarrow, patterns = self.parse_extcmds(self.opts.packages)
        return self.base.output_packages('list', pkgnarrow, patterns)


class ProvidesCommand(Command):
    """A class containing methods needed by the cli to execute the
    provides command.
    """

    aliases = ('provides', 'whatprovides')
    summary = _('find what package provides the given value')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('dependency', nargs='+', metavar=_('SOME_STRING'))

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def run(self, extcmds):
        logger.debug("Searching Packages: ")
        return self.base.provides(self.opts.dependency)

class CheckUpdateCommand(Command):
    """A class containing methods needed by the cli to execute the
    check-update command.
    """

    aliases = ('check-update',)
    summary = _('check for available package upgrades')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', metavar=_('PACKAGE'))

    def configure(self, _):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        checkEnabledRepo(self.base)

    def run(self, extcmds):
        found = self.base.check_updates(self.opts.packages, print_=True)
        if found:
            self.cli.demands.success_exit_status = 100


class RepoPkgsCommand(Command):
    """Implementation of the repository-packages command."""

    class SubCommand(Command):
        """Base class for repository-packages sub-commands.

        The main purpose of the inheritance is to get the same default values
        of unset attributes.

        """

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""

    class CheckUpdateSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        activate_sack = True

        aliases = ('check-update',)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            patterns = self.parse_arguments(cli_args)
            found = self.base.check_updates(patterns, reponame, print_=True)
            if found:
                self.cli.demands.success_exit_status = 100

    class InfoSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        activate_sack = True

        aliases = ('info',)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            DEFAULT_PKGNARROW = 'all'
            pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available', 'autoremove',
                          'extras', 'obsoletes', 'recent', 'upgrades'}
            if not cli_args or cli_args[0] not in pkgnarrows:
                return DEFAULT_PKGNARROW, cli_args
            else:
                return cli_args[0], cli_args[1:]

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkgnarrow, patterns = self.parse_arguments(cli_args)
            self.base.output_packages('info', pkgnarrow, patterns, reponame)

    class InstallSubCommand(SubCommand):
        """Implementation of the install sub-command."""

        activate_sack = True

        aliases = ('install',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.InstallSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Install all packages.
                try:
                    self.base.install('*', reponame)
                except dnf.exceptions.MarkingError:
                    logger.info(_('No package available.'))
                else:
                    done = True
            else:
                # Install packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.install(pkg_spec, reponame)
                    except dnf.exceptions.MarkingError:
                        msg = _('No package %s%s%s available.')
                        logger.info(
                            msg, self.output.term.MODE['bold'],
                            pkg_spec, self.output.term.MODE['normal'])
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ListSubCommand(SubCommand):
        """Implementation of the list sub-command."""

        activate_sack = True

        aliases = ('list',)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            DEFAULT_PKGNARROW = 'all'
            pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available', 'autoremove',
                          'extras', 'obsoletes', 'recent', 'upgrades'}
            if not cli_args or cli_args[0] not in pkgnarrows:
                return DEFAULT_PKGNARROW, cli_args
            else:
                return cli_args[0], cli_args[1:]

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkgnarrow, patterns = self.parse_arguments(cli_args)
            self.base.output_packages('list', pkgnarrow, patterns, reponame)

    class MoveToSubCommand(SubCommand):
        """Implementation of the move-to sub-command."""

        activate_sack = True

        aliases = ('move-to',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.MoveToSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', new_reponame=reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    logger.info(_('No package installed.'))
                except dnf.exceptions.PackagesNotAvailableError:
                    logger.info(_('No package available.'))
                except dnf.exceptions.MarkingError:
                    assert False, 'Only the above marking errors are expected.'
                else:
                    done = True
            else:
                # Reinstall packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.reinstall(pkg_spec, new_reponame=reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base._yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s%s%s not available.')
                            logger.info(
                                msg, self.output.term.MODE['bold'], pkg,
                                self.output.term.MODE['normal'], xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, 'Only the above marking errors are expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ReinstallOldSubCommand(SubCommand):
        """Implementation of the reinstall-old sub-command."""

        activate_sack = True

        aliases = ('reinstall-old',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.ReinstallOldSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', reponame, reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                except dnf.exceptions.PackagesNotAvailableError:
                    logger.info(_('No package available.'))
                except dnf.exceptions.MarkingError:
                    assert False, 'Only the above marking errors are expected.'
                else:
                    done = True
            else:
                # Reinstall packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.reinstall(pkg_spec, reponame, reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base._yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s%s%s not available.')
                            logger.info(
                                msg, self.output.term.MODE['bold'], pkg,
                                self.output.term.MODE['normal'], xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, 'Only the above marking errors are expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ReinstallSubCommand(SubCommand):
        """Implementation of the reinstall sub-command."""

        aliases = ('reinstall',)

        def __init__(self, cli):
            """Initialize the command."""
            super(RepoPkgsCommand.ReinstallSubCommand, self).__init__(cli)
            self.wrapped_commands = (RepoPkgsCommand.ReinstallOldSubCommand(cli),
                                     RepoPkgsCommand.MoveToSubCommand(cli))

            cmds_vals = (cmd.activate_sack for cmd in self.wrapped_commands)
            self.activate_sack = functools.reduce(
                operator.or_, cmds_vals, Command.activate_sack)

            cmds_vals = (cmd.load_available_repos for cmd in self.wrapped_commands)
            self.load_available_repos = functools.reduce(
                operator.or_, cmds_vals, Command.load_available_repos)

            cmds_vals = (cmd.writes_rpmdb for cmd in self.wrapped_commands)
            self.writes_rpmdb = functools.reduce(
                operator.or_, cmds_vals, Command.writes_rpmdb)

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.ReinstallSubCommand, self).check(cli_args)
            for command in self.wrapped_commands:
                command.check(cli_args)

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            for command in self.wrapped_commands:
                try:
                    command.run_on_repo(reponame, cli_args)
                except dnf.exceptions.Error:
                    continue
                else:
                    break
                finally:
                    if command.resolve:
                        self.cli.demands.resolving = True
            else:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class RemoveOrDistroSyncSubCommand(SubCommand):
        """Implementation of the remove-or-distro-sync sub-command."""

        activate_sack = True

        aliases = ('remove-or-distro-sync',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.RemoveOrDistroSyncSubCommand, self).check(
                cli_args)
            checkGPGKey(self.base, self.cli)

        @staticmethod
        def parse_arguments(cli_args):
            """Parse command arguments."""
            return cli_args

        def _replace(self, pkg_spec, reponame):
            """Synchronize a package with another repository or remove it."""
            self.cli.base.sack.disable_repo(reponame)

            subject = dnf.subject.Subject(pkg_spec)
            matches = subject.get_best_query(self.cli.base.sack)
            yumdb = self.cli.base._yumdb
            installed = [
                pkg for pkg in matches.installed()
                if yumdb.get_package(pkg).get('from_repo') == reponame]
            if not installed:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', pkg_spec)
            available = matches.available()
            clean_deps = self.cli.base.conf.clean_requirements_on_remove
            for package in installed:
                if available.filter(name=package.name, arch=package.arch):
                    self.cli.base._goal.distupgrade(package)
                else:
                    self.cli.base._goal.erase(package, clean_deps=clean_deps)

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Sync all packages.
                try:
                    self._replace('*', reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                else:
                    done = True
            else:
                # Reinstall packages.
                for pkg_spec in pkg_specs:
                    try:
                        self._replace(pkg_spec, reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class RemoveOrReinstallSubCommand(SubCommand):
        """Implementation of the remove-or-reinstall sub-command."""

        activate_sack = True

        aliases = ('remove-or-reinstall',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.RemoveOrReinstallSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall(
                        '*', old_reponame=reponame, new_reponame_neq=reponame,
                        remove_na=True)
                except dnf.exceptions.PackagesNotInstalledError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                except dnf.exceptions.MarkingError:
                    assert False, 'Only the above marking error is expected.'
                else:
                    done = True
            else:
                # Reinstall packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.reinstall(
                            pkg_spec, old_reponame=reponame,
                            new_reponame_neq=reponame, remove_na=True)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    except dnf.exceptions.MarkingError:
                        assert False, 'Only the above marking error is expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class RemoveSubCommand(SubCommand):
        """Implementation of the remove sub-command."""

        activate_sack = True

        aliases = ('remove',)

        load_available_repos = False

        resolve = True

        allow_erasing = True

        writes_rpmdb = True

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Remove all packages.
                try:
                    self.base.remove('*', reponame)
                except dnf.exceptions.MarkingError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                else:
                    done = True
            else:
                # Remove packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.remove(pkg_spec, reponame)
                    except dnf.exceptions.MarkingError:
                        logger.info(_('No match for argument: %s'),
                                              pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for removal.'))

    class UpgradeSubCommand(SubCommand):
        """Implementation of the upgrade sub-command."""

        activate_sack = True

        aliases = ('upgrade',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.UpgradeSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Update all packages.
                self.base.upgrade_all(reponame)
                done = True
            else:
                # Update packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.upgrade(pkg_spec, reponame)
                    except dnf.exceptions.MarkingError:
                        logger.info(_('No match for argument: %s'),
                                              pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for upgrade.'))

    class UpgradeToSubCommand(SubCommand):
        """Implementation of the upgrade-to sub-command."""

        activate_sack = True

        aliases = ('upgrade-to',)

        resolve = True

        writes_rpmdb = True

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.UpgradeToSubCommand, self).check(cli_args)
            checkGPGKey(self.base, self.cli)
            try:
                self.parse_arguments(cli_args)
            except ValueError:
                logger.critical(
                    _('Error: Requires at least one package specification'))
                raise dnf.cli.CliError('a package specification required')

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            if not cli_args:
                raise ValueError('at least one argument must be given')
            return cli_args

        def run_on_repo(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)
            self.base.upgrade_userlist_to(pkg_specs, reponame)

    SUBCMDS = {CheckUpdateSubCommand, InfoSubCommand, InstallSubCommand,
               ListSubCommand, MoveToSubCommand, ReinstallOldSubCommand,
               ReinstallSubCommand, RemoveOrDistroSyncSubCommand,
               RemoveOrReinstallSubCommand, RemoveSubCommand,
               UpgradeSubCommand, UpgradeToSubCommand}

    aliases = ('repository-packages',
               'repo-pkgs', 'repo-packages', 'repository-pkgs')
    summary = _('run commands on top of all packages in given repository')

    def __init__(self, cli):
        """Initialize the command."""
        super(RepoPkgsCommand, self).__init__(cli)
        subcmd_objs = (subcmd(cli) for subcmd in self.SUBCMDS)
        self._subcmd_name2obj = {
            alias: subcmd for subcmd in subcmd_objs for alias in subcmd.aliases}

        sub_vals = (cmd.activate_sack for cmd in self._subcmd_name2obj.values())
        self.activate_sack = functools.reduce(
            operator.or_, sub_vals, super(RepoPkgsCommand, self).activate_sack)

        sub_vals = (cmd.load_available_repos for cmd in self._subcmd_name2obj.values())
        self.load_available_repos = functools.reduce(
            operator.or_, sub_vals, super(RepoPkgsCommand, self).load_available_repos)

        sub_vals = (cmd.writes_rpmdb for cmd in self._subcmd_name2obj.values())
        self.writes_rpmdb = functools.reduce(
            operator.or_, sub_vals, super(RepoPkgsCommand, self).writes_rpmdb)

    @staticmethod
    def set_argparser(parser):
        subcommands = ['check-update', 'info', 'install', 'list', 'move-to',
                       'reinstall', 'reinstall-old', 'remove',
                       'remove-or-distro-sync', 'remove-or-reinstall', 'upgrade',
                       'upgrade-to']
        parser.add_argument('cmdrepo', nargs=1, metavar=_('REPO'))
        parser.add_argument('subcmd', nargs=1,
                            choices = subcommands,
                            metavar='[ %s ]' % ' | '.join(subcommands))
        parser.add_argument('subargs', nargs='*', metavar=_('ARG'))

    def configure(self, args):
        """Verify whether the command can run with given arguments."""
        # Check sub-command.
        try:
            subcmd = self._subcmd_name2obj[self.opts.subcmd[0]]
            subcmd.check(self.opts.subargs)
        except (dnf.cli.CliError, KeyError) as e:
            self.cli.optparser.print_usage()
            raise dnf.cli.CliError
        subcmd.configure(args)

    def run(self, extcmds):
        """Execute the command with respect to given arguments *extcmds*."""
        subcmd = self._subcmd_name2obj[self.opts.subcmd[0]]

        subcmd.run_on_repo(self.opts.cmdrepo, self.opts.subargs)

        self.cli.demands.resolving = subcmd.resolve

class HelpCommand(Command):
    """A class containing methods needed by the cli to execute the
    help command.
    """

    aliases = ('help',)
    summary = _('display a helpful usage message')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('cmd', nargs='?', metavar=_('COMMAND'))

    def run(self, extcmds):
        if (not self.opts.cmd
            or self.opts.cmd not in self.cli.cli_commands):
            self.cli.optparser.print_help()
        else:
            command = self.cli.cli_commands[self.opts.cmd]
            self.cli.optparser.print_help(command(self))

class HistoryCommand(Command):
    """A class containing methods needed by the cli to execute the
    history command.
    """

    aliases = ('history',)
    summary = _('display, or use, the transaction history')
    usage = "[info|list|redo|undo|rollback|userinstalled]"

    @staticmethod
    def set_argparser(parser):
        sub_p = parser.add_subparsers(dest='vcmd',
                        metavar="[info|list|redo|undo|rollback|userinstalled]")
        info_p = sub_p.add_parser('info')
        info_p.add_argument('tid', metavar='transaction_id', nargs='*')
        list_p = sub_p.add_parser('list')
        list_p.add_argument('tid', metavar='transaction_id', nargs='*')
        redo_p = sub_p.add_parser('redo')
        redo_p.add_argument('tid', metavar='transaction_id', nargs=1)
        undo_p = sub_p.add_parser('undo')
        undo_p.add_argument('tid', metavar='transaction_id', nargs=1)
        rollback_p = sub_p.add_parser('rollback')
        rollback_p.add_argument('tid', metavar='transaction_id', nargs=1)
        userinstalled_p = sub_p.add_parser('userinstalled')

    def configure(self, args):
        demands = self.cli.demands
        if not self.opts.vcmd:
            self.opts.vcmd = 'list'
        if self.opts.vcmd in ['redo', 'undo', 'rollback']:
            demands.available_repos = True
            checkGPGKey(self.base, self.cli)
        else:
            demands.fresh_metadata = False
        demands.sack_activation = True
        if not os.access(self.base.history._db_file, os.R_OK):
            logger.critical(_("You don't have access to the history DB."))
            raise dnf.cli.CliError

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        basecmd, extcmds = self.base.basecmd, self.base.extcmds
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            assert basecmd == 'history'
            if extcmds[0] == 'undo':
                id_, = extcmds[1:]
                return (_('Cannot undo transaction %s, doing so would result '
                          'in an inconsistent package database.') % id_,)
            elif extcmds[0] == 'rollback':
                id_, = extcmds[1:] if extcmds[1] != 'force' else extcmds[2:]
                return (_('Cannot rollback transaction %s, doing so would '
                          'result in an inconsistent package database.') % id_,)

        return Command.get_error_output(self, error)

    def _hcmd_redo(self, extcmds):
        old = self.base.history_get_transaction((extcmd,))
        if old is None:
            return 1, ['Failed history redo']
        tm = time.ctime(old.beg_timestamp)
        print('Repeating transaction %u, from %s' % (old.tid, tm))
        self.output.historyInfoCmdPkgsAltered(old)

        converter = dnf.history.TransactionConverter(self.base.sack)
        history = dnf.history.open_history(self.base.history)
        operations = history.transaction_nevra_ops(old.tid)

        hibeg = self.output.term.MODE['bold']
        hiend = self.output.term.MODE['normal']
        try:
            self.base.transaction = converter.convert(operations, 'history')
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s%s%s installed.'),
                        hibeg, ucd(err.pkg_spec), hiend)
            return 1, ['An operation cannot be redone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s%s%s available.'),
                        hibeg, ucd(err.pkg_spec), hiend)
            return 1, ['An operation cannot be redone']
        else:
            return 2, ['Repeating transaction %u' % (old.tid,)]

    def _hcmd_undo(self, extcmds):
        try:
            return self.base.history_undo_transaction(extcmd)
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_rollback(self, extcmds):
        try:
            return self.base.history_rollback_transaction(extcmd)
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_userinstalled(self):
        """Execute history userinstalled command."""
        pkgs = tuple(self.base.iter_userinstalled())
        return self.output.listPkgs(pkgs, 'Packages installed by user', 'name')

    def run(self, extcmds):
        vcmd = self.opts.vcmd
        extcmds = getattr(self.opts, 'tid', [])

        if False: pass
        elif vcmd == 'list':
            ret = self.output.historyListCmd(extcmds)
        elif vcmd == 'info':
            ret = self.output.historyInfoCmd(extcmds)
        elif vcmd == 'undo':
            ret = self._hcmd_undo(extcmds)
        elif vcmd == 'redo':
            ret = self._hcmd_redo(extcmds)
        elif vcmd == 'rollback':
            ret = self._hcmd_rollback(extcmds)
        elif vcmd == 'userinstalled':
            ret = self._hcmd_userinstalled()

        if ret is None:
            return
        (code, strs) = ret
        if code == 2:
            self.cli.demands.resolving = True
        elif code != 0:
            raise dnf.exceptions.Error(strs[0])
