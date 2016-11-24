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
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _, ucd

import argparse
import dnf.cli
import dnf.cli.demand
import dnf.const
import dnf.exceptions
import dnf.i18n
import dnf.pycomp
import dnf.util
import functools
import logging
import operator
import os

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


def _checkGPGKey(base, cli):
    """Verify that there are gpg keys for the enabled repositories in the
    rpm database.

    :param base: a :class:`dnf.Base` object.
    :raises: :class:`cli.CliError`
    """
    if not base.conf.gpgcheck:
        return
    if not base._gpg_key_check():
        for repo in base.repos.iter_enabled():
            if (repo.gpgcheck or repo.repo_gpgcheck) and not repo.gpgkey:
                logger.critical("\n%s\n", gpg_msg)
                logger.critical(_("Problem repository: %s"), repo)
                raise dnf.cli.CliError


def _checkEnabledRepo(base, possible_local_files=[]):
    """Verify that there is at least one enabled repo.

    :param base: a :class:`dnf.Base` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`:
    """
    if base.repos._any_enabled():
        return

    for lfile in possible_local_files:
        if lfile.endswith(".rpm") and os.path.exists(lfile):
            return

    msg = _('There are no enabled repos.')
    raise dnf.cli.CliError(msg)


class Command(object):
    """Abstract base class for CLI commands."""

    aliases = [] # :api
    summary = ""  # :api
    opts = None

    def __init__(self, cli):
        # :api
        self.cli = cli

    @property
    def base(self):
        # :api
        return self.cli.base

    @property
    def _basecmd(self):
        return self.aliases[0]

    @property
    def output(self):
        return self.cli.base.output

    def set_argparser(self, parser):
        """Define command specific options and arguments. #:api"""
        pass

    def configure(self):
        # :api
        """Do any command-specific configuration."""
        pass

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            return (_RPM_VERIFY, _RPM_REBUILDDB)
        raise NotImplementedError('error not supported yet: %s' % error)

    def run(self):
        # :api
        """Execute the command."""
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
    DEFAULT_PKGNARROW = 'all'
    pkgnarrows = {'available', 'installed', 'extras', 'updates', 'upgrades',
                  'autoremove', 'recent', 'obsoletes', DEFAULT_PKGNARROW}

    @classmethod
    def set_argparser(cls, parser):
        narrows = parser.add_mutually_exclusive_group()
        narrows.add_argument('--all', dest='_packages_action',
                             action='store_const', const='all', default=None,
                             help=_("show all packages (default)"))
        narrows.add_argument('--available', dest='_packages_action',
                             action='store_const', const='available',
                             help=_("show only available packages"))
        narrows.add_argument('--installed', dest='_packages_action',
                             action='store_const', const='installed',
                             help=_("show only installed packages"))
        narrows.add_argument('--extras', dest='_packages_action',
                             action='store_const', const='extras',
                             help=_("show only extras packages"))
        narrows.add_argument('--updates', dest='_packages_action',
                             action='store_const', const='upgrades',
                             help=_("show only upgrades packages"))
        narrows.add_argument('--upgrades', dest='_packages_action',
                             action='store_const', const='upgrades',
                             help=_("show only upgrades packages"))
        narrows.add_argument('--autoremove', dest='_packages_action',
                             action='store_const', const='autoremove',
                             help=_("show only autoremove packages"))
        narrows.add_argument('--recent', dest='_packages_action',
                             action='store_const', const='recent',
                             help=_("show only recently changed packages"))
        narrows.add_argument('--obsoletes', dest='_packages_action',
                             action='store_const', const='obsoletes',
                             help=_("show only obsoletes packages"))
        parser.add_argument('packages', nargs='*', metavar=_('PACKAGE'),
                            choices=cls.pkgnarrows, default=cls.DEFAULT_PKGNARROW,
                            action=OptionParser.PkgNarrowCallback)

    def configure(self):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True
        if self.opts._packages_action:
            self.opts.packages_action = self.opts._packages_action
        if self.opts.packages_action == 'updates':
            self.opts.packages_action = 'upgrades'

    def run(self):
        return self.base.output_packages('info', self.opts.packages_action,
                                         self.opts.packages)

class ListCommand(InfoCommand):
    """A class containing methods needed by the cli to execute the
    list command.
    """

    aliases = ('list',)
    summary = _('list a package or groups of packages')

    def run(self):
        return self.base.output_packages('list', self.opts.packages_action,
                                         self.opts.packages)


class ProvidesCommand(Command):
    """A class containing methods needed by the cli to execute the
    provides command.
    """

    aliases = ('provides', 'whatprovides')
    summary = _('find what package provides the given value')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('dependency', nargs='+', metavar=_('SOME_STRING'))

    def configure(self):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def run(self):
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

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        _checkEnabledRepo(self.base)

    def run(self):
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
        @staticmethod
        def set_argparser(parser):
            parser.add_argument('pkg_specs', nargs='*', metavar=_('PACKAGE'))

    class CheckUpdateSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        aliases = ('check-update',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            found = self.base.check_updates(self.opts.pkg_specs,
                                            self.reponame, print_=True)
            if found:
                self.cli.demands.success_exit_status = 100

    class InfoSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        aliases = ('info',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            if self.opts._pkg_specs_action:
                self.opts.pkg_specs_action = self.opts._pkg_specs_action

        @staticmethod
        def set_argparser(parser):
            DEFAULT_PKGNARROW = 'all'
            pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available',
                          'autoremove', 'extras', 'obsoletes', 'recent',
                          'upgrades'}

            narrows = parser.add_mutually_exclusive_group()
            narrows.add_argument('--all', dest='_pkg_specs_action',
                                 action='store_const', const='all', default=None,
                                 help=_("show all packages (default)"))
            narrows.add_argument('--available', dest='_pkg_specs_action',
                                 action='store_const', const='available',
                                 help=_("show only available packages"))
            narrows.add_argument('--installed', dest='_pkg_specs_action',
                                 action='store_const', const='installed',
                                 help=_("show only installed packages"))
            narrows.add_argument('--extras', dest='_pkg_specs_action',
                                 action='store_const', const='extras',
                                 help=_("show only extras packages"))
            narrows.add_argument('--updates', dest='_pkg_specs_action',
                                 action='store_const', const='upgrades',
                                 help=_("show only upgrades packages"))
            narrows.add_argument('--upgrades', dest='_pkg_specs_action',
                                 action='store_const', const='upgrades',
                                 help=_("show only upgrades packages"))
            narrows.add_argument('--autoremove', dest='_pkg_specs_action',
                                 action='store_const', const='autoremove',
                                 help=_("show only autoremove packages"))
            narrows.add_argument('--recent', dest='_pkg_specs_action',
                                 action='store_const', const='recent',
                                 help=_("show only recently changed packages"))
            narrows.add_argument('--obsoletes', dest='_pkg_specs_action',
                                 action='store_const', const='obsoletes',
                                 help=_("show only obsoletes packages"))
            parser.add_argument('pkg_specs', nargs='*', metavar=_('PACKAGE'),
                                choices=pkgnarrows, default=DEFAULT_PKGNARROW,
                                action=OptionParser.PkgNarrowCallback)

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            self.base.output_packages('info', self.opts.pkg_specs_action,
                                      self.opts.pkg_specs, self.reponame)

    class InstallSubCommand(SubCommand):
        """Implementation of the install sub-command."""

        aliases = ('install',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Install all packages.
                try:
                    self.base.install('*', self.reponame)
                except dnf.exceptions.MarkingError:
                    logger.info(_('No package available.'))
                else:
                    done = True
            else:
                # Install packages.
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.install(pkg_spec, self.reponame)
                    except dnf.exceptions.MarkingError:
                        msg = _('No package %s available.')
                        logger.info(msg, self.output.term.bold(pkg_spec))
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ListSubCommand(InfoSubCommand):
        """Implementation of the list sub-command."""

        aliases = ('list',)

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            self.base.output_packages('list', self.opts.pkg_specs_action,
                                      self.opts.pkg_specs, self.reponame)

    class MoveToSubCommand(SubCommand):
        """Implementation of the move-to sub-command."""

        aliases = ('move-to',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', new_reponame=self.reponame)
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
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.reinstall(pkg_spec, new_reponame=self.reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base._yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s not available.')
                            logger.info(msg, self.output.term.bold(pkg), xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, \
                               'Only the above marking errors are expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ReinstallOldSubCommand(SubCommand):
        """Implementation of the reinstall-old sub-command."""

        aliases = ('reinstall-old',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', self.reponame, self.reponame)
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
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.reinstall(pkg_spec, self.reponame,
                                            self.reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base._yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s not available.')
                            logger.info(msg, self.output.term.bold(pkg), xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, \
                               'Only the above marking errors are expected.'
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

        def configure(self):
            self.cli.demands.available_repos = True
            for command in self.wrapped_commands:
                command.opts = self.opts
                command.reponame = self.reponame
                command.configure()

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)
            for command in self.wrapped_commands:
                try:
                    command.run_on_repo()
                except dnf.exceptions.Error:
                    continue
                else:
                    break
            else:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class RemoveOrDistroSyncSubCommand(SubCommand):
        """Implementation of the remove-or-distro-sync sub-command."""

        aliases = ('remove-or-distro-sync',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

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

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Sync all packages.
                try:
                    self._replace('*', self.reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                else:
                    done = True
            else:
                # Reinstall packages.
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self._replace(pkg_spec, self.reponame)
                    except dnf.exceptions.PackagesNotInstalledError:
                        msg = _('No match for argument: %s')
                        logger.info(msg, pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class RemoveOrReinstallSubCommand(SubCommand):
        """Implementation of the remove-or-reinstall sub-command."""

        aliases = ('remove-or-reinstall',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', old_reponame=self.reponame,
                                        new_reponame_neq=self.reponame,
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
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.reinstall(
                            pkg_spec, old_reponame=self.reponame,
                            new_reponame_neq=self.reponame, remove_na=True)
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

        aliases = ('remove',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.allow_erasing = True
            demands.available_repos = False
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""

            done = False

            if not self.opts.pkg_specs:
                # Remove all packages.
                try:
                    self.base.remove('*', self.reponame)
                except dnf.exceptions.MarkingError:
                    msg = _('No package installed from the repository.')
                    logger.info(msg)
                else:
                    done = True
            else:
                # Remove packages.
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.remove(pkg_spec, self.reponame)
                    except dnf.exceptions.MarkingError:
                        logger.info(_('No match for argument: %s'), pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for removal.'))

    class UpgradeSubCommand(SubCommand):
        """Implementation of the upgrade sub-command."""

        aliases = ('upgrade',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)

            done = False

            if not self.opts.pkg_specs:
                # Update all packages.
                self.base.upgrade_all(self.reponame)
                done = True
            else:
                # Update packages.
                for pkg_spec in self.opts.pkg_specs:
                    try:
                        self.base.upgrade(pkg_spec, self.reponame)
                    except dnf.exceptions.MarkingError:
                        logger.info(_('No match for argument: %s'), pkg_spec)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for upgrade.'))

    class UpgradeToSubCommand(SubCommand):
        """Implementation of the upgrade-to sub-command."""

        aliases = ('upgrade-to',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('pkg_specs', nargs='+', metavar=_('PACKAGE'))

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            _checkGPGKey(self.base, self.cli)
            self.base.upgrade_userlist_to(self.opts.pkg_specs, self.reponame)

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
        self.subcmd = None
        self._subcmd_name2obj = {
            alias: subcmd for subcmd in subcmd_objs for alias in subcmd.aliases}

    def set_argparser(self, parser):
        super(OptionParser, parser).add_argument(
            'reponame', nargs=1, action=OptionParser._RepoCallbackEnable,
            metavar=_('REPO'))
        subparser = parser.add_subparsers(dest='subcmd',
                                          parser_class=argparse.ArgumentParser)
        for subcommand in self._subcmd_name2obj.keys():
            p = subparser.add_parser(subcommand)
            self._subcmd_name2obj[subcommand].set_argparser(p)

    def configure(self):
        """Verify whether the command can run with given arguments."""
        # Check sub-command.
        try:
            self.subcmd = self._subcmd_name2obj[self.opts.subcmd]
        except (dnf.cli.CliError, KeyError) as e:
            self.cli.optparser.print_usage()
            raise dnf.cli.CliError
        self.subcmd.opts = self.opts
        self.subcmd.reponame = self.opts.reponame[0]
        self.subcmd.configure()

    def run(self):
        """Execute the command with respect to given arguments *extcmds*."""
        self.subcmd.run_on_repo()

class HelpCommand(Command):
    """A class containing methods needed by the cli to execute the
    help command.
    """

    aliases = ('help',)
    summary = _('display a helpful usage message')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('cmd', nargs='?', metavar=_('COMMAND'))

    def run(self):
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

    @staticmethod
    def set_argparser(parser):
        cmds = ['list', 'info', 'redo', 'undo', 'rollback', 'userinstalled']
        parser.add_argument('tid', nargs='*',
                            choices=cmds, default=cmds[0],
                            action=OptionParser.PkgNarrowCallback,
                            metavar="[%s]" % "|".join(cmds))

    def configure(self):
        demands = self.cli.demands
        if self.opts.tid_action in ['redo', 'undo', 'rollback']:
            if not self.opts.tid:
                logger.critical(_('No transaction ID given'))
                raise dnf.cli.CliError
            elif len(self.opts.tid) > 1:
                logger.critical(_('Found more than one transaction ID!'))
                raise dnf.cli.CliError
            demands.available_repos = True
            _checkGPGKey(self.base, self.cli)
        else:
            demands.fresh_metadata = False
        demands.available_repos = True
        demands.sack_activation = True
        demands.root_user = True
        if not os.access(self.base.history._db_file, os.R_OK):
            logger.critical(_("You don't have access to the history DB."))
            raise dnf.cli.CliError

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            if self.opts.tid_action == 'undo':
                id_, = self.opts.tid
                return (_('Cannot undo transaction %s, doing so would result '
                          'in an inconsistent package database.') % id_,)
            elif self.opts.tid_action == 'rollback':
                id_, = (self.opts.tid if self.opts.tid[0] != 'force'
                        else self.opts.tid[1:])
                return (_('Cannot rollback transaction %s, doing so would '
                          'result in an inconsistent package database.') % id_,)

        return Command.get_error_output(self, error)

    def _hcmd_redo(self, extcmds):
        old = self.base.history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history redo']
        tm = dnf.util.normalize_time(old.beg_timestamp)
        print('Repeating transaction %u, from %s' % (old.tid, tm))
        self.output.historyInfoCmdPkgsAltered(old)

        converter = dnf.history.TransactionConverter(self.base.sack)
        history = dnf.history.open_history(self.base.history)
        operations = history.transaction_nevra_ops(old.tid)

        try:
            self.base.transaction = converter.convert(operations, 'history')
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s installed.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['An operation cannot be redone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s available.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['An operation cannot be redone']
        else:
            return 2, ['Repeating transaction %u' % (old.tid,)]

    def _hcmd_undo(self, extcmds):
        try:
            return self.base.history_undo_transaction(extcmds[0])
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_rollback(self, extcmds):
        try:
            return self.base.history_rollback_transaction(extcmds[0])
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_userinstalled(self):
        """Execute history userinstalled command."""
        pkgs = tuple(self.base.iter_userinstalled())
        return self.output.listPkgs(pkgs, 'Packages installed by user', 'nevra')

    def _convert_tids(self):
        """Convert commandline arguments to transaction ids"""
        def str2tid(s):
            if s.startswith('last'):
                s = s[4:] if s != 'last' else '0'
            tid = int(s)
            if tid <= 0:
                tid += self.output.history.last().tid
            return tid

        tids = set()
        for t in self.opts.tid:
            if '..' in t:
                btid, etid = t.split('..', 2)
                tids.update(range(str2tid(btid), str2tid(etid) + 1))
            else:
                try:
                    tids.add(str2tid(t))
                except ValueError:
                    # not a transaction id, assume it's package name
                    tids.update(self.output.history.search([t]))

        return sorted(tids)

    def run(self):
        vcmd = self.opts.tid_action
        extcmds = self._convert_tids()

        if False: pass
        elif vcmd == 'list':
            ret = self.output.historyListCmd(extcmds)
        elif vcmd == 'info':
            ret = self.output.historyInfoCmd(extcmds, self.opts.tid)
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
