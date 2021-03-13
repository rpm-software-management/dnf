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
from dnf.i18n import _

import dnf.cli
import dnf.exceptions
import dnf.pycomp
import dnf.util
import logging
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
for a repository in the 'gpgkey' option in a repository section and {prog}
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
                logger.critical("\n%s\n", gpg_msg.format(prog=dnf.util.MAIN_PROG_UPPER))
                logger.critical(_("Problem repository: %s"), repo)
                raise dnf.cli.CliError


def _checkEnabledRepo(base, possible_local_files=()):
    """Verify that there is at least one enabled repo.

    :param base: a :class:`dnf.Base` object.
    :param possible_local_files: the list of strings that could be a local rpms
    :raises: :class:`cli.CliError`:
    """
    if base.repos._any_enabled():
        return

    for lfile in possible_local_files:
        if lfile.endswith(".rpm") and os.path.exists(lfile):
            return
        scheme = dnf.pycomp.urlparse.urlparse(lfile)[0]
        if scheme in ('http', 'ftp', 'file', 'https'):
            return
    msg = _('There are no enabled repositories in "{}".').format('", "'.join(base.conf.reposdir))
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

    def pre_configure(self):
        # :api
        """Do any command-specific pre-configuration."""
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

    def run_resolved(self):
        """Finalize operation after resolvement"""
        pass

    def run_transaction(self):
        """Finalize operations post-transaction."""
        pass

class InfoCommand(Command):
    """A class containing methods needed by the cli to execute the
    info command.
    """

    aliases = ('info', 'if')
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
        parser.add_argument('packages', nargs='*', metavar=_('PACKAGE'),
                            choices=cls.pkgnarrows, default=cls.DEFAULT_PKGNARROW,
                            action=OptionParser.PkgNarrowCallback,
                            help=_("Package name specification"))

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        if self.opts._packages_action:
            self.opts.packages_action = self.opts._packages_action
        if self.opts.packages_action != 'installed':
            demands.available_repos = True
        if self.opts.obsoletes:
            if self.opts._packages_action:
                self.cli._option_conflict("--obsoletes", "--" + self.opts._packages_action)
            else:
                self.opts.packages_action = 'obsoletes'
        if self.opts.packages_action == 'updates':
            self.opts.packages_action = 'upgrades'

    def run(self):
        self.cli._populate_update_security_filter(self.opts)
        return self.base.output_packages('info', self.opts.packages_action,
                                         self.opts.packages)

class ListCommand(InfoCommand):
    """A class containing methods needed by the cli to execute the
    list command.
    """

    aliases = ('list', 'ls')
    summary = _('list a package or groups of packages')

    def run(self):
        self.cli._populate_update_security_filter(self.opts)
        return self.base.output_packages('list', self.opts.packages_action,
                                         self.opts.packages)


class ProvidesCommand(Command):
    """A class containing methods needed by the cli to execute the
    provides command.
    """

    aliases = ('provides', 'whatprovides', 'prov', 'wp')
    summary = _('find what package provides the given value')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('dependency', nargs='+', metavar=_('PROVIDE'),
                            help=_("Provide specification to search for"))

    def configure(self):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def run(self):
        logger.debug(_("Searching Packages: "))
        return self.base.provides(self.opts.dependency)

class CheckUpdateCommand(Command):
    """A class containing methods needed by the cli to execute the
    check-update command.
    """

    aliases = ('check-update', 'check-upgrade')
    summary = _('check for available package upgrades')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('--changelogs', dest='changelogs',
                            default=False, action='store_true',
                            help=_('show changelogs before update'))
        parser.add_argument('packages', nargs='*', metavar=_('PACKAGE'))

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.plugin_filtering_enabled = True
        if self.opts.changelogs:
            demands.changelogs = True
        _checkEnabledRepo(self.base)

    def run(self):
        self.cli._populate_update_security_filter(self.opts, cmp_type="gte")

        found = self.base.check_updates(self.opts.packages, print_=True,
                                        changelogs=self.opts.changelogs)
        if found:
            self.cli.demands.success_exit_status = 100

        if self.base.conf.autocheck_running_kernel:
            self.cli._check_running_kernel()


class RepoPkgsCommand(Command):
    """Implementation of the repository-packages command."""

    class CheckUpdateSubCommand(Command):
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

    class InfoSubCommand(Command):
        """Implementation of the info sub-command."""

        aliases = ('info',)

        def configure(self):
            demands = self.cli.demands
            demands.sack_activation = True
            if self.opts._pkg_specs_action:
                self.opts.pkg_specs_action = self.opts._pkg_specs_action
            if self.opts.pkg_specs_action != 'installed':
                demands.available_repos = True
            if self.opts.obsoletes:
                if self.opts._pkg_specs_action:
                    self.cli._option_conflict("--obsoletes", "--" + self.opts._pkg_specs_action)
                else:
                    self.opts.pkg_specs_action = 'obsoletes'

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            self.cli._populate_update_security_filter(self.opts)
            self.base.output_packages('info', self.opts.pkg_specs_action,
                                      self.opts.pkg_specs, self.reponame)

    class InstallSubCommand(Command):
        """Implementation of the install sub-command."""

        aliases = ('install',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_repo(self):
            self.cli._populate_update_security_filter(self.opts)
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
                    except dnf.exceptions.MarkingError as e:
                        msg = '{}: {}'.format(e.value, self.base.output.term.bold(pkg_spec))
                        logger.info(msg)
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for install.'))

    class ListSubCommand(InfoSubCommand):
        """Implementation of the list sub-command."""

        aliases = ('list',)

        def run_on_repo(self):
            """Execute the command with respect to given arguments *cli_args*."""
            self.cli._populate_update_security_filter(self.opts)
            self.base.output_packages('list', self.opts.pkg_specs_action,
                                      self.opts.pkg_specs, self.reponame)

    class MoveToSubCommand(Command):
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
                            pkgrepo = self.base.history.repo(pkg)
                            if pkgrepo:
                                xmsg = _(' (from %s)') % pkgrepo
                            msg = _('Installed package %s%s not available.')
                            logger.info(msg, self.output.term.bold(pkg), xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, \
                               'Only the above marking errors are expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ReinstallOldSubCommand(Command):
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
                            pkgrepo = self.base.history.repo(pkg)
                            if pkgrepo:
                                xmsg = _(' (from %s)') % pkgrepo
                            msg = _('Installed package %s%s not available.')
                            logger.info(msg, self.output.term.bold(pkg), xmsg)
                    except dnf.exceptions.MarkingError:
                        assert False, \
                               'Only the above marking errors are expected.'
                    else:
                        done = True

            if not done:
                raise dnf.exceptions.Error(_('Nothing to do.'))

    class ReinstallSubCommand(Command):
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
                raise dnf.exceptions.Error(_('No packages marked for reinstall.'))

    class RemoveOrDistroSyncSubCommand(Command):
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
            history = self.cli.base.history
            installed = [
                pkg for pkg in matches.installed()
                if history.repo(pkg) == reponame]
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

    class RemoveOrReinstallSubCommand(Command):
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

    class RemoveSubCommand(Command):
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
                    except dnf.exceptions.MarkingError as e:
                        logger.info(str(e))
                    else:
                        done = True

            if not done:
                logger.warning(_('No packages marked for removal.'))

    class UpgradeSubCommand(Command):
        """Implementation of the upgrade sub-command."""

        aliases = ('upgrade', 'upgrade-to')

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

    SUBCMDS = {CheckUpdateSubCommand, InfoSubCommand, InstallSubCommand,
               ListSubCommand, MoveToSubCommand, ReinstallOldSubCommand,
               ReinstallSubCommand, RemoveOrDistroSyncSubCommand,
               RemoveOrReinstallSubCommand, RemoveSubCommand,
               UpgradeSubCommand}

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

        parser.add_argument(
            'reponame', nargs=1, action=OptionParser._RepoCallbackEnable,
            metavar=_('REPOID'), help=_("Repository ID"))
        subcommand_choices = [subcmd.aliases[0] for subcmd in self.SUBCMDS]
        subcommand_choices_all = [alias for subcmd in self.SUBCMDS for alias in subcmd.aliases]
        parser.add_argument('subcmd', nargs=1, metavar="SUBCOMMAND",
                            choices=subcommand_choices_all, help=", ".join(subcommand_choices))
        DEFAULT_PKGNARROW = 'all'
        pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available',
                      'autoremove', 'extras', 'obsoletes', 'recent',
                      'upgrades'}
        parser.add_argument('pkg_specs', nargs='*', metavar=_('PACKAGE'),
                            choices=pkgnarrows, default=DEFAULT_PKGNARROW,
                            action=OptionParser.PkgNarrowCallback,
                            help=_("Package specification"))

    def configure(self):
        """Verify whether the command can run with given arguments."""
        # Check sub-command.
        try:
            self.subcmd = self._subcmd_name2obj[self.opts.subcmd[0]]
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
        parser.add_argument('cmd', nargs='?', metavar=_('COMMAND'),
                            help=_("{prog} command to get help for").format(
                                prog=dnf.util.MAIN_PROG_UPPER))

    def run(self):
        if (not self.opts.cmd
                or self.opts.cmd not in self.cli.cli_commands):
            self.cli.optparser.print_help()
        else:
            command = self.cli.cli_commands[self.opts.cmd]
            self.cli.optparser.print_help(command(self))
