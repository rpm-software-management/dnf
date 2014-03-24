# Copyright 2006 Duke University
# Copyright (C) 2012-2014  Red Hat, Inc.
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
from dnf.cli.format import format_number
from dnf.yum.i18n import utf8_width, utf8_width_fill, to_unicode, _

import dnf.cli
import dnf.const
import dnf.exceptions
import dnf.i18n
import dnf.logging
import dnf.util
import dnf.yum.config
import fnmatch
import functools
import locale
import operator
import os
import time

_RPM_VERIFY = _("To diagnose the problem, try running: '%s'.") % \
    'rpm -Va --nofiles --nodigest'
_RPM_REBUILDDB = _("To fix inconsistent RPMDB, try running: '%s'.") % \
    'rpm --rebuilddb'
_REPORT_TMPLT = _("If the above doesn't help please report this error at '%s'.")

def _err_mini_usage(cli, basecmd):
    if basecmd not in cli.cli_commands:
        cli.print_usage()
        return
    cmd = cli.cli_commands[basecmd]
    txt = cli.cli_commands["help"]._makeOutput(cmd)
    cli.logger.critical(_(' Mini usage:\n'))
    cli.logger.critical(txt)

def checkGPGKey(base, cli):
    """Verify that there are gpg keys for the enabled repositories in the
    rpm database.

    :param base: a :class:`dnf.yum.Yumbase` object.
    :raises: :class:`cli.CliError`
    """
    if cli.nogpgcheck:
        return
    if not base.gpgKeyCheck():
        for repo in base.repos.iter_enabled():
            if (repo.gpgcheck or repo.repo_gpgcheck) and not repo.gpgkey:
                msg = _("""
You have enabled checking of packages via GPG keys. This is a good thing.
However, you do not have any GPG public keys installed. You need to download
the keys for packages you wish to install and install them.
You can do that by running the command:
    rpm --import public.gpg.key


Alternatively you can specify the url to the key you would like to use
for a repository in the 'gpgkey' option in a repository section and yum
will install it for you.

For more information contact your distribution or package provider.
""")
                base.logger.critical(msg)
                base.logger.critical(_("Problem repository: %s"), repo)
                raise dnf.cli.CliError

def checkPackageArg(cli, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one package for
    *basecmd* to act on.

    :param base: a :class:`dnf.yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        cli.logger.critical(
                _('Error: Need to pass a list of pkgs to %s') % basecmd)
        _err_mini_usage(cli, basecmd)
        raise dnf.cli.CliError

def checkItemArg(cli, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one item for
    *basecmd* to act on.  Generally, the items are command-line
    arguments that are not the name of a package, such as a file name
    passed to provides.

    :param base: a :class:`dnf.yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        cli.logger.critical(_('Error: Need an item to match'))
        _err_mini_usage(cli, basecmd)
        raise dnf.cli.CliError

def checkCleanArg(cli, basecmd, extcmds):
    """Verify that *extcmds* contains at least one argument, and that all
    arguments in *extcmds* are valid options for clean.

    :param base: a :class:`dnf.yum.Yumbase` object
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    VALID_ARGS = ('packages', 'metadata', 'dbcache', 'plugins',
                  'expire-cache', 'rpmdb', 'all')

    if len(extcmds) == 0:
        cli.logger.critical(_('Error: clean requires an option: %s') % (
            ", ".join(VALID_ARGS)))

    for cmd in extcmds:
        if cmd not in VALID_ARGS:
            cli.logger.critical(_('Error: invalid clean argument: %r') % cmd)
            _err_mini_usage(cli, basecmd)
            raise dnf.cli.CliError

def checkEnabledRepo(base, possible_local_files=[]):
    """Verify that there is at least one enabled repo.

    :param base: a :class:`dnf.yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`:
    """
    if base.repos.any_enabled():
        return

    for lfile in possible_local_files:
        if lfile.endswith(".rpm") and os.path.exists(lfile):
            return

    msg = _('There are no enabled repos.\n'
            ' Run "yum repolist all" to see the repos you have.\n'
            ' You can enable repos with yum-config-manager --enable <repo>')
    base.logger.critical(msg)
    raise dnf.cli.CliError

class Command(object):
    """An abstract base class that defines the methods needed by the cli
    to execute a specific command.  Subclasses must override at least
    :func:`get_usage` and :func:`get_summary`.
    """

    activate_sack = False
    aliases = [] # :api
    load_available_repos = True
    resolve = False
    success_retval = 0
    writes_rpmdb = False

    def __init__(self, cli):
        self.done_command_once = False
        self.hidden = False
        self.cli = cli

    @property
    def base(self):
        return self.cli.base

    @property
    def output(self):
        return self.cli.base.output

    @classmethod
    def canonical(cls, command_list):
        """Turn list of comamnds into a canonical form.

        Returns the base command and a list of extra commands.

        """
        base = cls.aliases[0]
        extra = command_list[1:]
        return (base, extra)

    def configure(self):
        """ Do any command-specific Base configuration. """
        pass

    def get_error_output(self, error):
        """Get suggestions for resolving the given error."""
        if isinstance(error, dnf.exceptions.TransactionCheckError):
            return (_RPM_VERIFY, _RPM_REBUILDDB,
                    _REPORT_TMPLT % self.base.conf.bugtracker_url)
        raise NotImplementedError('error not supported yet: %s' % error)

    @staticmethod
    def get_usage():
        """Return a usage string for the command, including arguments.

        :return: a usage string for the command
        """
        raise NotImplementedError

    @staticmethod
    def get_summary():
        """Return a one line summary of what the command does.

        :return: a one line summary of what the command does
        """
        raise NotImplementedError

    def doCheck(self, basecmd, extcmds):
        """Verify that various conditions are met so that the command
        can run.

        :param basecmd: the name of the command being checked for
        :param extcmds: a list of arguments passed to *basecmd*
        """
        pass

    def run(self, extcmds):
        """Execute the command #:api

        :param extcmds: a list of arguments passed to *basecmd*

        """
        pass

class InstallCommand(Command):
    """A class containing methods needed by the cli to execute the
    install command.
    """

    aliases = ('install',)
    activate_sack = True
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("PACKAGE...")

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Install a package or packages on your system")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that the program is being run by the root user,
        that there are enabled repositories with gpg keys, and that
        this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkGPGKey(self.base, self.cli)
        checkPackageArg(self.cli, basecmd, extcmds)
        checkEnabledRepo(self.base, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        pkg_specs, grp_specs, filenames = [], [], []
        for argument in extcmds:
            if argument.endswith('.rpm'):
                filenames.append(argument)
            elif argument.startswith('@'):
                grp_specs.append(argument[1:])
            else:
                pkg_specs.append(argument)
        return pkg_specs, grp_specs, filenames

    def run(self, extcmds):
        pkg_specs, grp_specs, filenames = self.parse_extcmds(extcmds)

        # Install files.
        results = map(self.base.install_local, filenames)
        done = functools.reduce(operator.or_, results, False)

        # Install groups.
        if grp_specs:
            self.base.read_comps()
        cnt = 0
        for spec in grp_specs:
            group = self.base.comps.group_by_pattern(spec)
            if group is None:
                msg = _("Warning: Group '%s' does not exist.")
                self.base.logger.error(msg, dnf.i18n.ucd(spec))
                continue
            cnt += self.base.group_install(group, dnf.const.GROUP_PACKAGE_TYPES)
        if grp_specs and not cnt:
            msg = _('No packages in any requested group available '\
                    'to install or upgrade.')
            raise dnf.exceptions.Error(msg)
        elif cnt:
            done = True

        # Install packages.
        for pkg_spec in pkg_specs:
            try:
                self.base.install(pkg_spec)
            except dnf.exceptions.MarkingError:
                msg = _('No package %s%s%s available.')
                self.base.logger.info(
                    msg, self.base.output.term.MODE['bold'], pkg_spec,
                    self.base.output.term.MODE['normal'])
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('Nothing to do.'))

class UpgradeCommand(Command):
    """A class containing methods needed by the cli to execute the
    update command.
    """
    aliases = ('upgrade', 'update')
    activate_sack = True
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("[PACKAGE...]")

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Upgrade a package or packages on your system")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.

        These include that there are enabled repositories with gpg
        keys, and that this command is being run by the root user.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkGPGKey(self.base, self.cli)
        checkEnabledRepo(self.base, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        pkg_specs, filenames = [], []
        for argument in extcmds:
            if argument.endswith('.rpm'):
                filenames.append(argument)
            else:
                pkg_specs.append(argument)
        return pkg_specs, filenames

    def run(self, extcmds):
        pkg_specs, filenames = self.parse_extcmds(extcmds)

        if not pkg_specs and not filenames:
            # Update all packages.
            self.base.upgrade_all()
            done = True
        else:
            # Update files.
            results = map(self.base.update_local, filenames)
            done = functools.reduce(operator.or_, results, False)

            # Update packages.
            for pkg_spec in pkg_specs:
                try:
                    self.base.upgrade(pkg_spec)
                except dnf.exceptions.MarkingError:
                    self.base.logger.info(_('No match for argument: %s'),
                                          dnf.pycomp.unicode(pkg_spec))
                    self.base._checkMaybeYouMeant(pkg_spec)
                else:
                    done = True

        if not done:
            raise dnf.exceptions.Error(_('No packages marked for upgrade.'))

class UpgradeToCommand(Command):
    """ A class containing methods needed by the cli to execute the upgrade-to
        command.
    """

    aliases = ('upgrade-to', 'update-to')
    activate_sack = True
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        return _("[PACKAGE...]")

    @staticmethod
    def get_summary():
        return _("Upgrade a package on your system to the specified version")

    def doCheck(self, basecmd, extcmds):
        checkGPGKey(self.base, self.cli)
        checkEnabledRepo(self.base, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        return extcmds

    def run(self, extcmds):
        patterns = self.parse_extcmds(extcmds)
        return self.base.upgrade_userlist_to(patterns)

class DistroSyncCommand(Command):
    """A class containing methods needed by the cli to execute the
    distro-synch command.
    """

    aliases = ('distribution-synchronization', 'distro-sync')
    activate_sack = True
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("[PACKAGE...]")

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Synchronize installed packages to the latest available versions")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that the program is being run by the root user,
        and that there are enabled repositories with gpg keys.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkGPGKey(self.base, self.cli)
        checkEnabledRepo(self.base, extcmds)

    def run(self, extcmds):
        return self.base.distro_sync_userlist(extcmds)

class InfoCommand(Command):
    """A class containing methods needed by the cli to execute the
    info command.
    """

    aliases = ('info',)
    activate_sack = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[PACKAGE|all|available|installed|updates|extras|obsoletes|recent]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display details about a package or group of packages")

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        DEFAULT_PKGNARROW = 'all'
        if len(extcmds) == 0:
            return DEFAULT_PKGNARROW, extcmds

        pkgnarrows = {'available', 'installed', 'extras', 'upgrades',
                      'recent', 'obsoletes', DEFAULT_PKGNARROW}
        if extcmds[0] in pkgnarrows:
            return extcmds[0], extcmds[1:]
        elif extcmds[0] == 'updates':
            return 'upgrades', extcmds[1:]
        else:
            return DEFAULT_PKGNARROW, extcmds

    def run(self, extcmds):
        pkgnarrow, patterns = self.parse_extcmds(extcmds)
        return self.base.output_packages('info', pkgnarrow, patterns)

class ListCommand(InfoCommand):
    """A class containing methods needed by the cli to execute the
    list command.
    """

    aliases = ('list',)
    activate_sack = True

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("List a package or groups of packages")

    def run(self, extcmds):
        pkgnarrow, patterns = self.parse_extcmds(extcmds)
        return self.base.output_packages('list', pkgnarrow, patterns)

class EraseCommand(Command):
    """A class containing methods needed by the cli to execute the
    erase command.
    """

    activate_sack = True
    aliases = ('erase', 'remove')
    load_available_repos = False
    resolve = True
    writes_rpmdb = True

    def configure(self):
        self.base.goal_parameters.allow_uninstall = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Remove a package or packages from your system")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, and that this command is called with appropriate
        arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkPackageArg(self.cli, basecmd, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        return extcmds

    def run(self, extcmds):
        pkg_specs = self.parse_extcmds(extcmds)

        done = False

        for pkg_spec in pkg_specs:
            try:
                self.base.remove(pkg_spec)
            except dnf.exceptions.MarkingError:
                self.base.logger.info(_('No match for argument: %s'),
                                      dnf.pycomp.unicode(pkg_spec))
                self.base._checkMaybeYouMeant(pkg_spec, always_output=False,
                                              rpmdb_only=True)
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('No packages marked for removal.'))

class MakeCacheCommand(Command):
    """A class containing methods needed by the cli to execute the
    makecache command.
    """

    aliases = ('makecache',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return ""

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Generate the metadata cache")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that there is an enabled repository.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkEnabledRepo(self.base)

    def run(self, extcmds):
        msg = _("Making cache files for all metadata files.")
        self.base.logger.debug(msg)
        period = self.base.conf.metadata_timer_sync
        timer = 'timer' == dnf.util.first(extcmds)
        persistor = self.base._persistor
        if timer:
            if dnf.util.on_ac_power() is False:
                msg = _('Metadata timer caching disabled '
                        'when running on a battery.')
                self.base.logger.info(msg)
                return False
            if period <= 0:
                msg = _('Metadata timer caching disabled.')
                self.base.logger.info(msg)
                return False
            since_last_makecache = persistor.since_last_makecache()
            if since_last_makecache is not None and since_last_makecache < period:
                self.base.logger.info(_('Metadata cache refreshed recently.'))
                return False
            self.base.repos.all().max_mirror_tries = 1

        for r in self.base.repos.iter_enabled():
            (is_cache, expires_in) = r.metadata_expire_in()
            if not is_cache or expires_in <= 0:
                self.base.logger.debug("%s: has expired and will be "
                                          "refreshed." % r.id)
                r.md_expire_cache()
            elif timer and expires_in < period:
                # expires within the checking period:
                msg = "%s: metadata will expire after %d seconds " \
                    "and will be refreshed now" % (r.id, expires_in)
                self.base.logger.debug(msg)
                r.md_expire_cache()
            else:
                self.base.logger.debug("%s: will expire after %d "
                                          "seconds." % (r.id, expires_in))

        if timer:
            persistor.reset_last_makecache()
        self.base.fill_sack() # performs the md sync
        self.base.logger.info(_('Metadata cache created.'))
        return True

class CleanCommand(Command):
    """A class containing methods needed by the cli to execute the
    clean command.
    """

    aliases = ('clean',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[packages|metadata|dbcache|plugins|expire-cache|all]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Remove cached data")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that there is at least one enabled repository,
        and that this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkCleanArg(self.cli, basecmd, extcmds)
        checkEnabledRepo(self.base)

    def run(self, extcmds):
        return self.base.cleanCli(extcmds)

class ProvidesCommand(Command):
    """A class containing methods needed by the cli to execute the
    provides command.
    """

    activate_sack = True
    aliases = ('provides', 'whatprovides')

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "SOME_STRING"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Find what package provides the given value")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkItemArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        self.base.logger.debug("Searching Packages: ")
        return self.base.provides(extcmds)

class CheckUpdateCommand(Command):
    """A class containing methods needed by the cli to execute the
    check-update command.
    """

    activate_sack = True
    aliases = ('check-update',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[PACKAGE...]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Check for available package upgrades")

    def __init__(self, cli):
        super(CheckUpdateCommand, self).__init__(cli)
        self._success_retval = 0

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that there is at least one enabled repository.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkEnabledRepo(self.base)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        return extcmds

    def run(self, extcmds):
        patterns = self.parse_extcmds(extcmds)
        found = self.base.check_updates(patterns, print_=True)
        if found:
            self._success_retval = 100

    @property
    def success_retval(self):
        return self._success_retval

class SearchCommand(Command):
    """A class containing methods needed by the cli to execute the
    search command.
    """

    activate_sack = True
    aliases = ('search',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "SOME_STRING"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Search package details for the given string")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkItemArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        self.base.logger.debug(_("Searching Packages: "))
        return self.cli.search(extcmds)

class DepListCommand(Command):
    """A class containing methods needed by the cli to execute the
    deplist command.
    """

    activate_sack = True
    aliases = ('deplist',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return 'PACKAGE...'

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("List a package's dependencies")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate
        arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkPackageArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        return self.base.deplist(extcmds)

class RepoListCommand(Command):
    """A class containing methods needed by the cli to execute the
    repolist command.
    """

    activate_sack = True
    aliases = ('repolist',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return '[all|enabled|disabled]'

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _('Display the configured software repositories')

    def run(self, extcmds):
        def _repo_size(repo):
            ret = 0
            for pkg in self.base.sack.query().filter(reponame__eq=repo.id):
                ret += pkg.size
            return format_number(ret)

        def _repo_match(repo, patterns):
            rid = repo.id.lower()
            rnm = repo.name.lower()
            for pat in patterns:
                if fnmatch.fnmatch(rid, pat):
                    return True
                if fnmatch.fnmatch(rnm, pat):
                    return True
            return False

        def _num2ui_num(num):
            return to_unicode(locale.format("%d", num, True))

        if len(extcmds) >= 1 and extcmds[0] in ('all', 'disabled', 'enabled'):
            arg = extcmds[0]
            extcmds = extcmds[1:]
        else:
            arg = 'enabled'
        extcmds = [x.lower() for x in extcmds]

        verbose = self.base.conf.verbose

        repos = list(self.base.repos.values())
        repos.sort(key=operator.attrgetter('id'))
        enabled_repos = self.base.repos.enabled()
        on_ehibeg = self.output.term.FG_COLOR['green'] + self.output.term.MODE['bold']
        on_dhibeg = self.output.term.FG_COLOR['red']
        on_hiend  = self.output.term.MODE['normal']
        tot_num = 0
        cols = []
        for repo in repos:
            if len(extcmds) and not _repo_match(repo, extcmds):
                continue
            (ehibeg, dhibeg, hiend)  = '', '', ''
            ui_enabled      = ''
            ui_endis_wid    = 0
            ui_num          = ""
            ui_excludes_num = ''
            force_show = False
            if arg == 'all' or repo.id in extcmds or repo.name in extcmds:
                force_show = True
                (ehibeg, dhibeg, hiend) = (on_ehibeg, on_dhibeg, on_hiend)
            if repo in enabled_repos:
                enabled = True
                if arg == 'enabled':
                    force_show = False
                elif arg == 'disabled' and not force_show:
                    continue
                if force_show or verbose:
                    ui_enabled = ehibeg + _('enabled') + hiend
                    ui_endis_wid = utf8_width(_('enabled'))
                    if not verbose:
                        ui_enabled += ": "
                        ui_endis_wid += 2
                if verbose:
                    ui_size = _repo_size(repo)
                # We don't show status for list disabled
                if arg != 'disabled' or verbose:
                    num = len(self.base.sack.query().filter(
                        reponame__eq=repo.id))
                    ui_num     = _num2ui_num(num)
                    tot_num   += num
            else:
                enabled = False
                if arg == 'disabled':
                    force_show = False
                elif arg == 'enabled' and not force_show:
                    continue
                ui_enabled = dhibeg + _('disabled') + hiend
                ui_endis_wid = utf8_width(_('disabled'))

            if not verbose:
                rid = repo.id
                if enabled and repo.metalink:
                    mdts = repo.metadata.timestamp
                    if mdts > repo.metadata.md_timestamp:
                        rid = '*' + rid
                cols.append((rid, repo.name,
                             (ui_enabled, ui_endis_wid), ui_num))
            else:
                if enabled:
                    md = repo.metadata
                else:
                    md = None
                out = [self.output.fmtKeyValFill(_("Repo-id      : "), repo.id),
                       self.output.fmtKeyValFill(_("Repo-name    : "), repo.name)]

                if force_show or extcmds:
                    out += [self.output.fmtKeyValFill(_("Repo-status  : "),
                                               ui_enabled)]
                if md and md.revision is not None:
                    out += [self.output.fmtKeyValFill(_("Repo-revision: "),
                                               md.revision)]
                if md and md.content_tags:
                    tags = md.content_tags
                    out += [self.output.fmtKeyValFill(_("Repo-tags    : "),
                                               ", ".join(sorted(tags)))]

                if md and md.distro_tags:
                    for (distro, tags) in md.distro_tags.items():
                        out += [self.output.fmtKeyValFill(_("Repo-distro-tags: "),
                                                   "[%s]: %s" % (distro,
                                                   ", ".join(sorted(tags))))]

                if md:
                    out += [self.output.fmtKeyValFill(_("Repo-updated : "),
                                               time.ctime(md.md_timestamp)),
                            self.output.fmtKeyValFill(_("Repo-pkgs    : "),ui_num),
                            self.output.fmtKeyValFill(_("Repo-size    : "),ui_size)]

                if repo.metalink:
                    out += [self.output.fmtKeyValFill(_("Repo-metalink: "),
                                               repo.metalink)]
                    if enabled:
                        ts = repo.metadata.timestamp
                        out += [self.output.fmtKeyValFill(_("  Updated    : "),
                                                   time.ctime(ts))]
                elif repo.mirrorlist:
                    out += [self.output.fmtKeyValFill(_("Repo-mirrors : "),
                                               repo.mirrorlist)]
                baseurls = repo.baseurl
                if baseurls:
                    out += [self.output.fmtKeyValFill(_("Repo-baseurl : "),
                                               ", ".join(baseurls))]
                elif enabled and md.mirrors:
                    url = "%s (%d more)" % (md.mirrors[0], len(md.mirrors) - 1)
                    out += [self.output.fmtKeyValFill(_("Repo-baseurl : "), url)]

                last = time.ctime(md.timestamp)
                if repo.metadata_expire <= -1:
                    num = _("Never (last: %s)") % last
                elif not repo.metadata_expire:
                    num = _("Instant (last: %s)") % last
                else:
                    num = _num2ui_num(repo.metadata_expire)
                    num = _("%s second(s) (last: %s)") % (num, last)

                out += [self.output.fmtKeyValFill(_("Repo-expire  : "), num)]

                if repo.exclude:
                    out += [self.output.fmtKeyValFill(_("Repo-exclude : "),
                                               ", ".join(repo.exclude))]

                if repo.includepkgs:
                    out += [self.output.fmtKeyValFill(_("Repo-include : "),
                                               ", ".join(repo.includepkgs))]

                if ui_excludes_num:
                    out += [self.output.fmtKeyValFill(_("Repo-excluded: "),
                                               ui_excludes_num)]

                if repo.repofile:
                    out += [self.output.fmtKeyValFill(_("Repo-filename: "),
                                               repo.repofile)]

                self.base.logger.log(dnf.logging.DEBUG, "%s\n",
                                        "\n".join(map(to_unicode, out)))

        if not verbose and cols:
            #  Work out the first (id) and last (enabled/disalbed/count),
            # then chop the middle (name)...
            id_len = utf8_width(_('repo id'))
            nm_len = 0
            st_len = 0
            ui_len = 0

            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if id_len < utf8_width(rid):
                    id_len = utf8_width(rid)
                if nm_len < utf8_width(rname):
                    nm_len = utf8_width(rname)
                if st_len < (ui_endis_wid + len(ui_num)):
                    st_len = (ui_endis_wid + len(ui_num))
                # Need this as well as above for: utf8_width_fill()
                if ui_len < len(ui_num):
                    ui_len = len(ui_num)
            if arg == 'disabled': # Don't output a status column.
                left = self.output.term.columns - (id_len + 1)
            elif utf8_width(_('status')) > st_len:
                left = self.output.term.columns - (id_len + utf8_width(_('status')) +2)
            else:
                left = self.output.term.columns - (id_len + st_len + 2)

            if left < nm_len: # Name gets chopped
                nm_len = left
            else: # Share the extra...
                left -= nm_len
                id_len += left // 2
                nm_len += left - (left // 2)

            txt_rid  = utf8_width_fill(_('repo id'), id_len)
            txt_rnam = utf8_width_fill(_('repo name'), nm_len, nm_len)
            if arg == 'disabled': # Don't output a status column.
                self.base.logger.info("%s %s",
                                        txt_rid, txt_rnam)
            else:
                self.base.logger.info("%s %s %s",
                                        txt_rid, txt_rnam, _('status'))
            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if arg == 'disabled': # Don't output a status column.
                    self.base.logger.info("%s %s",
                                            utf8_width_fill(rid, id_len),
                                            utf8_width_fill(rname, nm_len,
                                                            nm_len))
                    continue

                if ui_num:
                    ui_num = utf8_width_fill(ui_num, ui_len, left=False)
                self.base.logger.info("%s %s %s%s",
                                        utf8_width_fill(rid, id_len),
                                        utf8_width_fill(rname, nm_len, nm_len),
                                        ui_enabled, ui_num)
        msg = 'repolist: ' +to_unicode(locale.format("%d", tot_num, True))
        self.base.logger.info(msg)

class RepoPkgsCommand(Command):
    """Implementation of the repository-packages command."""

    class SubCommand(Command):
        """Base class for repository-packages sub-commands.

        The main purpose of the inheritance is to get the same default values
        of unset attributes.

        """

        def check(self, cli_args):
            """Verify whether the command can run with given arguments."""

        def doCheck(self, alias, cli_args):
            """Verify whether the command can run with given arguments."""
            super(RepoPkgsCommand.SubCommand, self).doCheck(alias, cli_args)
            if alias not in self.aliases:
                raise ValueError("alias must be one of command's aliases")
            self.check(cli_args)

    class CheckUpdateSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        activate_sack = True

        aliases = ('check-update',)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.CheckUpdateSubCommand, self).run(cli_args)
            self.check(cli_args)
            patterns = self.parse_arguments(cli_args)
            found = self.base.check_updates(patterns, reponame, print_=True)
            if found:
                self.success_retval = 100

    class InfoSubCommand(SubCommand):
        """Implementation of the info sub-command."""

        activate_sack = True

        aliases = ('info',)

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            DEFAULT_PKGNARROW = 'all'
            pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available',
                          'extras', 'obsoletes', 'recent', 'upgrades'}
            if not cli_args or cli_args[0] not in pkgnarrows:
                return DEFAULT_PKGNARROW, cli_args
            else:
                return cli_args[0], cli_args[1:]

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.InfoSubCommand, self).run(cli_args)
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

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.InstallSubCommand, self).run(cli_args)
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Install all packages.
                try:
                    self.base.install('*', reponame)
                except dnf.exceptions.MarkingError:
                    self.base.logger.info(_('No package available.'))
                else:
                    done = True
            else:
                # Install packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.install(pkg_spec, reponame)
                    except dnf.exceptions.MarkingError:
                        msg = _('No package %s%s%s available.')
                        self.base.logger.info(
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
            pkgnarrows = {DEFAULT_PKGNARROW, 'installed', 'available',
                          'extras', 'obsoletes', 'recent', 'upgrades'}
            if not cli_args or cli_args[0] not in pkgnarrows:
                return DEFAULT_PKGNARROW, cli_args
            else:
                return cli_args[0], cli_args[1:]

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.ListSubCommand, self).run(cli_args)
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

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.MoveToSubCommand, self).run(cli_args)
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', new_reponame=reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    self.base.logger.info(_('No package installed.'))
                except dnf.exceptions.PackagesNotAvailableError:
                    self.base.logger.info(_('No package available.'))
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
                        self.base.logger.info(msg, dnf.pycomp.unicode(pkg_spec))
                        self.base._checkMaybeYouMeant(pkg_spec, always_output=False)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base.yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s%s%s not available.')
                            self.base.logger.info(
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

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.ReinstallOldSubCommand, self).run(cli_args)
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Reinstall all packages.
                try:
                    self.base.reinstall('*', reponame, reponame)
                except dnf.exceptions.PackagesNotInstalledError:
                    msg = _('No package installed from the repository.')
                    self.base.logger.info(msg)
                except dnf.exceptions.PackagesNotAvailableError:
                    self.base.logger.info(_('No package available.'))
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
                        self.base.logger.info(msg, dnf.pycomp.unicode(pkg_spec))
                        self.base._checkMaybeYouMeant(pkg_spec, always_output=False)
                    except dnf.exceptions.PackagesNotAvailableError as err:
                        for pkg in err.packages:
                            xmsg = ''
                            yumdb_info = self.base.yumdb.get_package(pkg)
                            if 'from_repo' in yumdb_info:
                                xmsg = _(' (from %s)') % yumdb_info.from_repo
                            msg = _('Installed package %s%s%s%s not available.')
                            self.base.logger.info(
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

        def configure(self):
            """Do any command-specific Base configuration."""
            super(RepoPkgsCommand.ReinstallSubCommand, self).configure()
            for command in self.wrapped_commands:
                command.configure()

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.ReinstallSubCommand, self).run(cli_args)
            self.check(cli_args)
            for command in self.wrapped_commands:
                try:
                    command.run(reponame, cli_args)
                except dnf.exceptions.Error:
                    continue
                else:
                    break
                finally:
                    self.resolve = command.resolve
            else:
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

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.RemoveOrReinstallSubCommand, self).run(cli_args)
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
                    self.base.logger.info(msg)
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
                        self.base.logger.info(msg, dnf.pycomp.unicode(pkg_spec))
                        self.base._checkMaybeYouMeant(pkg_spec, always_output=False)
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

        writes_rpmdb = True

        def configure(self):
            """Do any command-specific Base configuration."""
            super(RepoPkgsCommand.RemoveSubCommand, self).configure()
            self.base.goal_parameters.allow_uninstall = True

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            return cli_args

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.RemoveSubCommand, self).run(cli_args)
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)

            done = False

            if not pkg_specs:
                # Remove all packages.
                try:
                    self.base.remove('*', reponame)
                except dnf.exceptions.MarkingError:
                    msg = _('No package installed from the repository.')
                    self.base.logger.info(msg)
                else:
                    done = True
            else:
                # Remove packages.
                for pkg_spec in pkg_specs:
                    try:
                        self.base.remove(pkg_spec, reponame)
                    except dnf.exceptions.MarkingError:
                        self.base.logger.info(_('No match for argument: %s'),
                                              dnf.pycomp.unicode(pkg_spec))
                        self.base._checkMaybeYouMeant(
                            pkg_spec, always_output=False, rpmdb_only=True)
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

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.UpgradeSubCommand, self).run(cli_args)
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
                        self.base.logger.info(_('No match for argument: %s'),
                                              dnf.pycomp.unicode(pkg_spec))
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
                self.cli.logger.critical(
                    _('Error: Requires at least one package specification'))
                raise dnf.cli.CliError('a package specification required')

        def parse_arguments(self, cli_args):
            """Parse command arguments."""
            if not cli_args:
                raise ValueError('at least one argument must be given')
            return cli_args

        def run(self, reponame, cli_args):
            """Execute the command with respect to given arguments *cli_args*."""
            super(RepoPkgsCommand.UpgradeToSubCommand, self).run(cli_args)
            self.check(cli_args)
            pkg_specs = self.parse_arguments(cli_args)
            self.base.upgrade_userlist_to(pkg_specs, reponame)

    SUBCMDS = {CheckUpdateSubCommand, InfoSubCommand, InstallSubCommand,
               ListSubCommand, MoveToSubCommand, ReinstallOldSubCommand,
               ReinstallSubCommand, RemoveOrReinstallSubCommand,
               RemoveSubCommand, UpgradeSubCommand, UpgradeToSubCommand}

    aliases = ('repository-packages',
               'repo-pkgs', 'repo-packages', 'repository-pkgs')

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

    def configure(self):
        """Do any command-specific Base configuration."""
        _, subcmd, _ = self.parse_extcmds(self.base.extcmds)
        subcmd.configure()

    @staticmethod
    def get_usage():
        """Return a usage string for the command, including arguments."""
        return _('REPO check-update|info|install|list|move-to|reinstall|'
                 'reinstall-old|remove|remove-or-reinstall|upgrade|'
                 'upgrade-to [ARG...]')

    @staticmethod
    def get_summary():
        """Return a one line summary of what the command does."""
        return _('Run commands on top of all packages in given repository')

    def parse_extcmds(self, extcmds):
        """Parse command arguments *extcmds*."""
        # TODO: replace with ``repo, subcmd_name, *subargs = extcmds`` after
        # switching to Python 3.
        (repo, subcmd_name), subargs = extcmds[:2], extcmds[2:]

        try:
            subcmd_obj = self._subcmd_name2obj[subcmd_name]
        except KeyError:
            raise ValueError('invalid sub-command')

        return repo, subcmd_obj, subargs

    def doCheck(self, basecmd, extcmds):
        """Verify whether the command can run with given arguments."""
        # Check basecmd.
        if basecmd not in self.aliases:
            raise ValueError('basecmd should be one of the command aliases')

        # Check command arguments.
        try:
            _repo, subcmd, subargs = self.parse_extcmds(extcmds)
        except ValueError:
            self.cli.logger.critical(
                _('Error: Requires a repo ID and a valid sub-command'))
            dnf.cli.commands._err_mini_usage(self.cli, basecmd)
            raise dnf.cli.CliError('a repo ID and a valid sub-command required')

        # Check sub-command.
        try:
            subcmd.check(subargs)
        except dnf.cli.CliError:
            dnf.cli.commands._err_mini_usage(self.cli, basecmd)
            raise

    def run(self, extcmds):
        """Execute the command with respect to given arguments *extcmds*."""
        self.doCheck(self.base.basecmd, extcmds)

        repo, subcmd, subargs = self.parse_extcmds(extcmds)

        subcmd.run(repo, subargs)

        self.success_retval = subcmd.success_retval
        self.resolve = subcmd.resolve

class HelpCommand(Command):
    """A class containing methods needed by the cli to execute the
    help command.
    """

    aliases = ('help',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "COMMAND"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display a helpful usage message")

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate
        arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        if len(extcmds) == 0:
            self.cli.print_usage()
            raise dnf.cli.CliError
        elif len(extcmds) > 1 or extcmds[0] not in self.cli.cli_commands:
            self.cli.print_usage()
            raise dnf.cli.CliError

    @staticmethod
    def _makeOutput(command):
        canonical_name = command.aliases[0]

        # Check for the methods in case we have plugins that don't
        # implement these.
        # XXX Remove this once usage/summary are common enough
        try:
            usage = command.get_usage()
        except (AttributeError, NotImplementedError):
            usage = None
        try:
            summary = command.get_summary()
        except (AttributeError, NotImplementedError):
            summary = None

        # XXX need detailed help here, too
        help_output = ""
        if usage is not None:
            help_output += "%s %s" % (canonical_name, usage)
        if summary is not None:
            help_output += "\n\n%s" % summary

        if usage is None and summary is None:
            help_output = _("No help available for %s") % canonical_name

        command_names = command.aliases
        if len(command_names) > 1:
            if len(command_names) > 2:
                help_output += _("\n\naliases: ")
            else:
                help_output += _("\n\nalias: ")
            help_output += ', '.join(command.aliases[1:])

        return help_output

    def run(self, extcmds):
        if extcmds[0] in self.cli.cli_commands:
            command = self.cli.cli_commands[extcmds[0]]
            self.base.logger.info(self._makeOutput(command))

class ReInstallCommand(Command):
    """A class containing methods needed by the cli to execute the
    reinstall command.
    """

    activate_sack = True
    aliases = ('reinstall',)
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.


        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkGPGKey(self.base, self.cli)
        checkPackageArg(self.cli, basecmd, extcmds)
        checkEnabledRepo(self.base, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        pkg_specs, filenames = [], []
        for argument in extcmds:
            if argument.endswith('.rpm'):
                filenames.append(argument)
            else:
                pkg_specs.append(argument)
        return pkg_specs, filenames

    def run(self, extcmds):
        pkg_specs, filenames = self.parse_extcmds(extcmds)

        # Reinstall files.
        results = map(self.base.reinstall_local, filenames)
        done = functools.reduce(operator.or_, results, False)

        # Reinstall packages.
        for pkg_spec in pkg_specs:
            try:
                self.base.reinstall(pkg_spec)
            except dnf.exceptions.PackagesNotInstalledError:
                self.base.logger.info(_('No match for argument: %s'),
                                      dnf.pycomp.unicode(pkg_spec))
                self.base._checkMaybeYouMeant(pkg_spec, always_output=False)
            except dnf.exceptions.PackagesNotAvailableError as err:
                for pkg in err.packages:
                    xmsg = ''
                    yumdb_info = self.base.yumdb.get_package(pkg)
                    if 'from_repo' in yumdb_info:
                        xmsg = _(' (from %s)') % yumdb_info.from_repo
                    msg = _('Installed package %s%s%s%s not available.')
                    self.base.logger.info(
                        msg, self.base.output.term.MODE['bold'], pkg,
                        self.base.output.term.MODE['normal'], xmsg)
            except dnf.exceptions.MarkingError:
                assert False, 'Only the above marking errors are expected.'
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('Nothing to do.'))

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("reinstall a package")

class DowngradeCommand(Command):
    """A class containing methods needed by the cli to execute the
    downgrade command.
    """

    activate_sack = True
    aliases = ('downgrade',)
    resolve = True
    writes_rpmdb = True

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.


        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkGPGKey(self.base, self.cli)
        checkPackageArg(self.cli, basecmd, extcmds)
        checkEnabledRepo(self.base, extcmds)

    def run(self, extcmds):
        return self.base.downgradePkgs(extcmds)

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("downgrade a package")

class VersionCommand(Command):
    """A class containing methods needed by the cli to execute the
    version command.
    """

    aliases = ('version',)

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[all|installed|available]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display a version for the machine and/or available repos.")

    def run(self, extcmds):
        vcmd = 'installed'
        if extcmds:
            vcmd = extcmds[0]

        def _append_repos(cols, repo_data):
            for repoid in sorted(repo_data):
                cur = repo_data[repoid]
                ncols = []
                last_rev = None
                for rev in sorted(cur):
                    if rev is None:
                        continue
                    last_rev = cur[rev]
                    ncols.append(("    %s/%s" % (repoid, rev), str(cur[rev])))
                if None in cur and (not last_rev or cur[None] != last_rev):
                    cols.append(("    %s" % repoid, str(cur[None])))
                cols.extend(ncols)

        verbose = self.base.conf.verbose
        groups = {}
        if vcmd in ('nogroups', 'nogroups-installed', 'nogroups-available',
                    'nogroups-all'):
            gconf = []
            if vcmd == 'nogroups':
                vcmd = 'installed'
            else:
                vcmd = vcmd[len('nogroups-'):]
        else:
            gconf = dnf.yum.config.readVersionGroupsConfig()

        for group in gconf:
            groups[group] = set(gconf[group].pkglist)
            if gconf[group].run_with_packages:
                groups[group].update(self.base.conf.history_record_packages)

        if vcmd == 'grouplist':
            print(_(" Yum version groups:"))
            for group in sorted(groups):
                print("   ", group)

            return 0, ['version grouplist']

        if vcmd == 'groupinfo':
            for group in groups:
                if group not in extcmds[1:]:
                    continue
                print(_(" Group   :"), group)
                print(_(" Packages:"))
                if not verbose:
                    for pkgname in sorted(groups[group]):
                        print("   ", pkgname)
                else:
                    data = {'envra' : {}, 'rid' : {}}
                    pkg_names = groups[group]
                    pkg_names2pkgs = self.base._group_names2aipkgs(pkg_names)
                    self.base._calcDataPkgColumns(data, pkg_names, pkg_names2pkgs)
                    data = [data['envra'], data['rid']]
                    columns = self.output.calcColumns(data)
                    columns = (-columns[0], -columns[1])
                    self.base._displayPkgsFromNames(pkg_names, True, pkg_names2pkgs,
                                               columns=columns)

            return 0, ['version groupinfo']

        rel = self.base.conf.yumvar['releasever']
        ba  = self.base.conf.yumvar['basearch']
        cols = []
        if vcmd in ('installed', 'all', 'group-installed', 'group-all'):
            try:
                data = self.base.rpmdb.simpleVersion(not verbose, groups=groups)
                if vcmd not in ('group-installed', 'group-all'):
                    cols.append(("%s %s/%s" % (_("Installed:"), rel, ba),
                                 str(data[0])))
                    _append_repos(cols, data[1])
                if groups:
                    for grp in sorted(data[2]):
                        if (vcmd.startswith("group-") and
                            len(extcmds) > 1 and grp not in extcmds[1:]):
                            continue
                        cols.append(("%s %s" % (_("Group-Installed:"), grp),
                                     str(data[2][grp])))
                        _append_repos(cols, data[3][grp])
            except dnf.exceptions.Error as e:
                return 1, [str(e)]
        if vcmd in ('available', 'all', 'group-available', 'group-all'):
            try:
                data = self.base.pkgSack.simpleVersion(not verbose, groups=groups)
                if vcmd not in ('group-available', 'group-all'):
                    cols.append(("%s %s/%s" % (_("Available:"), rel, ba),
                                 str(data[0])))
                    if verbose:
                        _append_repos(cols, data[1])
                if groups:
                    for grp in sorted(data[2]):
                        if (vcmd.startswith("group-") and
                            len(extcmds) > 1 and grp not in extcmds[1:]):
                            continue
                        cols.append(("%s %s" % (_("Group-Available:"), grp),
                                     str(data[2][grp])))
                        if verbose:
                            _append_repos(cols, data[3][grp])
            except dnf.exceptions.Error as e:
                return 1, [str(e)]

        data = {'rid' : {}, 'ver' : {}}
        for (rid, ver) in cols:
            for (d, v) in (('rid', len(rid)), ('ver', len(ver))):
                data[d].setdefault(v, 0)
                data[d][v] += 1
        data = [data['rid'], data['ver']]
        columns = self.output.calcColumns(data)
        columns = (-columns[0], columns[1])

        for line in cols:
            print(self.output.fmtColumns(list(zip(line, columns))))

        return 0, ['version']

class HistoryCommand(Command):
    """A class containing methods needed by the cli to execute the
    history command.
    """

    activate_sack = True
    aliases = ('history',)

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

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[info|list|packages-list|summary|addon-info|redo|undo|rollback|new]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display, or use, the transaction history")


    def __init__(self, cli):
        super(HistoryCommand, self).__init__(cli)
        self._resolve = False

    def _hcmd_redo(self, extcmds):
        kwargs = {'force_reinstall' : False,
                  'force_changed_removal' : False,
                  }
        kwargs_map = {'reinstall' : 'force_reinstall',
                      'force-reinstall' : 'force_reinstall',
                      'remove' : 'force_changed_removal',
                      'force-remove' : 'force_changed_removal',
                      }
        while len(extcmds) > 1:
            done = False
            for arg in extcmds[1].replace(' ', ',').split(','):
                if arg not in kwargs_map:
                    continue

                done = True
                key = kwargs_map[extcmds[1]]
                kwargs[key] = not kwargs[key]

            if not done:
                break
            extcmds = [extcmds[0]] + extcmds[2:]

        old = self.base.history_get_transaction(extcmds[1:])
        if old is None:
            return 1, ['Failed history redo']
        tm = time.ctime(old.beg_timestamp)
        print("Repeating transaction %u, from %s" % (old.tid, tm))
        self.output.historyInfoCmdPkgsAltered(old)
        if self.base.history_redo(old, **kwargs):
            return 2, ["Repeating transaction %u" % (old.tid,)]

    def _hcmd_undo(self, extcmds):
        # Parse the transaction specification.
        try:
            extcmd, = extcmds
        except ValueError:
            if not extcmds:
                self.base.logger.critical(_('No transaction ID given'))
            elif len(extcmds) > 1:
                self.base.logger.critical(_('Found more than one transaction ID!'))
            return 1, ['Failed history undo']

        try:
            return self.base.history_undo_transaction(extcmd)
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_rollback(self, extcmds):
        # Parse the transaction specification.
        try:
            extcmd, = extcmds
        except ValueError:
            if not extcmds:
                self.base.logger.critical(_('No transaction ID given'))
            elif len(extcmds) > 1:
                self.base.logger.critical(_('Found more than one transaction ID!'))
            return 1, ['Failed history rollback']

        try:
            return self.base.history_rollback_transaction(extcmd)
        except dnf.exceptions.Error as err:
            return 1, [str(err)]

    def _hcmd_new(self, extcmds):
        self.base.history._create_db_file()

    def _hcmd_stats(self, extcmds):
        print("File        :", self.base.history._db_file)
        num = os.stat(self.base.history._db_file).st_size
        print("Size        :", locale.format("%d", num, True))
        counts = self.base.history._pkg_stats()
        trans_1 = self.base.history.old("1")[0]
        trans_N = self.base.history.last()
        print(_("Transactions:"), trans_N.tid)
        print(_("Begin time  :"), time.ctime(trans_1.beg_timestamp))
        print(_("End time    :"), time.ctime(trans_N.end_timestamp))
        print(_("Counts      :"))
        print(_("  NEVRAC :"), locale.format("%6d", counts['nevrac'], True))
        print(_("  NEVRA  :"), locale.format("%6d", counts['nevra'],  True))
        print(_("  NA     :"), locale.format("%6d", counts['na'],     True))
        print(_("  NEVR   :"), locale.format("%6d", counts['nevr'],   True))
        print(_("  rpm DB :"), locale.format("%6d", counts['rpmdb'],  True))
        print(_("  yum DB :"), locale.format("%6d", counts['yumdb'],  True))

    def _hcmd_sync(self, extcmds):
        extcmds = extcmds[1:]
        if not extcmds:
            extcmds = None
        for ipkg in sorted(self.base.rpmdb.returnPackages(patterns=extcmds)):
            if self.base.history.pkg2pid(ipkg, create=False) is None:
                continue

            print("Syncing rpm/yum DB data for:", ipkg, "...", end='')
            if self.base.history.sync_alldb(ipkg):
                print("Done.")
            else:
                print("FAILED.")

    def _hcmd_userinstalled(self, extcmds):
        """Execute history userinstalled command."""
        if extcmds:
            self.base.logger.critical(_('Unrecognized options "%s"!') %
                                      ' '.join(extcmds))
            return 1, ['Failed history userinstalled']

        pkgs = tuple(self.base.iter_userinstalled())
        return self.output.listPkgs(pkgs, 'Packages installed by user', 'name')

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  The exact conditions checked will vary depending on the
        subcommand that is being called.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        cmds = ('list', 'info', 'summary', 'undo', 'rollback', 'userinstalled')
        if extcmds and extcmds[0] not in cmds:
            self.base.logger.critical(_('Invalid history sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise dnf.cli.CliError
        if extcmds and extcmds[0] in ('repeat', 'redo', 'undo', 'rollback', 'new'):
            checkGPGKey(self.base, self.cli)
        elif not os.access(self.base.history._db_file, os.R_OK):
            self.base.logger.critical(_("You don't have access to the history DB."))
            raise dnf.cli.CliError

    @property
    def resolve(self):
        return self._resolve

    def run(self, extcmds):
        vcmd = 'list'
        if extcmds:
            vcmd = extcmds[0]

        if False: pass
        elif vcmd == 'list':
            ret = self.output.historyListCmd(extcmds)
        elif vcmd == 'info':
            ret = self.output.historyInfoCmd(extcmds)
        elif vcmd == 'summary':
            ret = self.output.historySummaryCmd(extcmds)
        elif vcmd in ('addon', 'addon-info'):
            ret = self.output.historyAddonInfoCmd(extcmds)
        elif vcmd in ('pkg', 'pkgs', 'pkg-list', 'pkgs-list',
                      'package', 'package-list', 'packages', 'packages-list'):
            ret = self.output.historyPackageListCmd(extcmds)
        elif vcmd == 'undo':
            ret = self._hcmd_undo(extcmds[1:])
        elif vcmd in ('redo', 'repeat'):
            ret = self._hcmd_redo(extcmds)
        elif vcmd == 'rollback':
            ret = self._hcmd_rollback(extcmds[1:])
        elif vcmd == 'new':
            ret = self._hcmd_new(extcmds)
        elif vcmd in ('stats', 'statistics'):
            ret = self._hcmd_stats(extcmds)
        elif vcmd in ('sync', 'synchronize'):
            ret = self._hcmd_sync(extcmds)
        elif vcmd in ('pkg-info', 'pkgs-info', 'package-info', 'packages-info'):
            ret = self.output.historyPackageInfoCmd(extcmds)
        elif vcmd == 'userinstalled':
            ret = self._hcmd_userinstalled(extcmds[1:])

        if ret is None:
            return
        (code, strs) = ret
        if code == 2:
            self._resolve = True
        elif code != 0:
            raise dnf.exceptions.Error(strs[0])

class CheckRpmdbCommand(Command):
    """A class containing methods needed by the cli to execute the
    check-rpmdb command.
    """

    aliases = ('check', 'check-rpmdb')

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[dependencies|duplicates|all]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Check for problems in the rpmdb")

    def run(self, extcmds):
        chkcmd = 'all'
        if extcmds:
            chkcmd = extcmds

        def _out(x):
            print(to_unicode(x.__str__()))

        rc = 0
        msg = 'check %s' % chkcmd
        if self.base._rpmdb_warn_checks(out=_out, warn=False, chkcmd=chkcmd,
                                   header=lambda x: None):
            raise dnf.exceptions.Error(msg)
        self.base.logger.info(msg)
