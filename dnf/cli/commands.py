# Copyright 2006 Duke University
# Copyright (C) 2012-2013  Red Hat, Inc.
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
import dnf.persistor
import dnf.util
import os
from dnf.cli import CliError
from dnf.cli.format import format_number
import dnf.logging
from dnf.yum import misc
import dnf.exceptions
import operator
import locale
import fnmatch
import time
from dnf.yum.i18n import utf8_width, utf8_width_fill, to_unicode, _

import dnf.yum.config
import hawkey

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
                raise CliError

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
        raise CliError

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
        raise CliError

def checkGroupArg(cli, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one group for
    *basecmd* to act on.

    :param base: a :class:`dnf.yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        cli.logger.critical(_('Error: Need a group or list of groups'))
        _err_mini_usage(cli, basecmd)
        raise CliError

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
            raise CliError

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
    raise CliError

class Command(object):
    """An abstract base class that defines the methods needed by the cli
    to execute a specific command.  Subclasses must override at least
    :func:`get_usage` and :func:`get_summary`.
    """

    activate_sack = False
    aliases = []
    load_available_repos = True

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

    def doCommand(self, basecmd, extcmds):
        """Execute the command

        :param basecmd: the name of the command being executed
        :param extcmds: a list of arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        return 0, [_('Nothing to do')]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before the
        command can run

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return True

class InstallCommand(Command):
    """A class containing methods needed by the cli to execute the
    install command.
    """

    aliases = ('install',)
    activate_sack = True

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.installPkgs(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

class UpgradeCommand(Command):
    """A class containing methods needed by the cli to execute the
    update command.
    """
    aliases = ('upgrade', 'update')
    activate_sack = True

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.updatePkgs(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

class UpgradeToCommand(Command):
    """ A class containing methods needed by the cli to execute the upgrade-to
        command.
    """

    aliases = ('upgrade-to', 'update-to')
    activate_sack = True

    @staticmethod
    def get_usage():
        return _("[PACKAGE...]")

    @staticmethod
    def get_summary():
        return _("Upgrade a package on your system to the specified version")

    def doCheck(self, basecmd, extcmds):
        checkGPGKey(self.base, self.cli)
        checkEnabledRepo(self.base, extcmds)

    def doCommand(self, basecmd, extcmds):
        try:
            return self.base.upgrade_userlist_to(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

class DistroSyncCommand(Command):
    """A class containing methods needed by the cli to execute the
    distro-synch command.
    """

    aliases = ('distribution-synchronization', 'distro-sync')
    activate_sack = True

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
        if extcmds:
            self.cli.logger.critical(_('distro-sync accepts no package specs.'))
            raise CliError

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.distro_sync_userlist(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

def _add_pkg_simple_list_lens(data, pkg, indent=''):
    """ Get the length of each pkg's column. Add that to data.
        This "knows" about simpleList and printVer. """
    na  = len(pkg.name) + 1 + len(pkg.arch) + len(indent)
    ver = len(pkg.evr)
    rid = len(pkg.reponame)
    for (d, v) in (('na', na), ('ver', ver), ('rid', rid)):
        data[d].setdefault(v, 0)
        data[d][v] += 1

def _list_cmd_calc_columns(output, ypl):
    """ Work out the dynamic size of the columns to pass to fmtColumns. """
    data = {'na' : {}, 'ver' : {}, 'rid' : {}}
    for lst in (ypl.installed, ypl.available, ypl.extras,
                ypl.updates, ypl.recent):
        for pkg in lst:
            _add_pkg_simple_list_lens(data, pkg)
    if len(ypl.obsoletes) > 0:
        for (npkg, opkg) in ypl.obsoletesTuples:
            _add_pkg_simple_list_lens(data, npkg)
            _add_pkg_simple_list_lens(data, opkg, indent=" " * 4)

    data = [data['na'], data['ver'], data['rid']]
    columns = output.calcColumns(data, remainder_column=1)
    return (-columns[0], -columns[1], -columns[2])

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            highlight = self.output.term.MODE['bold']
            ypl = self.base.returnPkgLists(extcmds, installed_available=highlight)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]
        else:
            update_pkgs = {}
            inst_pkgs   = {}
            local_pkgs  = {}

            columns = None
            if basecmd == 'list':
                # Dynamically size the columns
                columns = _list_cmd_calc_columns(self.output, ypl)

            if highlight and ypl.installed:
                #  If we have installed and available lists, then do the
                # highlighting for the installed packages so you can see what's
                # available to update, an extra, or newer than what we have.
                for pkg in (ypl.hidden_available +
                            ypl.reinstall_available +
                            ypl.old_available):
                    key = (pkg.name, pkg.arch)
                    if key not in update_pkgs or pkg > update_pkgs[key]:
                        update_pkgs[key] = pkg

            if highlight and ypl.available:
                #  If we have installed and available lists, then do the
                # highlighting for the available packages so you can see what's
                # available to install vs. update vs. old.
                for pkg in ypl.hidden_installed:
                    key = (pkg.name, pkg.arch)
                    if key not in inst_pkgs or pkg > inst_pkgs[key]:
                        inst_pkgs[key] = pkg

            if highlight and ypl.updates:
                # Do the local/remote split we get in "yum updates"
                for po in sorted(ypl.updates):
                    if po.reponame != hawkey.SYSTEM_REPO_NAME:
                        local_pkgs[(po.name, po.arch)] = po

            # Output the packages:
            clio = self.base.conf.color_list_installed_older
            clin = self.base.conf.color_list_installed_newer
            clir = self.base.conf.color_list_installed_reinstall
            clie = self.base.conf.color_list_installed_extra
            rip = self.output.listPkgs(ypl.installed, _('Installed Packages'), basecmd,
                                highlight_na=update_pkgs, columns=columns,
                                highlight_modes={'>' : clio, '<' : clin,
                                                 '=' : clir, 'not in' : clie})
            clau = self.base.conf.color_list_available_upgrade
            clad = self.base.conf.color_list_available_downgrade
            clar = self.base.conf.color_list_available_reinstall
            clai = self.base.conf.color_list_available_install
            rap = self.output.listPkgs(ypl.available, _('Available Packages'), basecmd,
                                highlight_na=inst_pkgs, columns=columns,
                                highlight_modes={'<' : clau, '>' : clad,
                                                 '=' : clar, 'not in' : clai})
            rep = self.output.listPkgs(ypl.extras, _('Extra Packages'), basecmd,
                                columns=columns)
            cul = self.base.conf.color_update_local
            cur = self.base.conf.color_update_remote
            rup = self.output.listPkgs(ypl.updates, _('Upgraded Packages'), basecmd,
                                highlight_na=local_pkgs, columns=columns,
                                highlight_modes={'=' : cul, 'not in' : cur})

            # XXX put this into the ListCommand at some point
            if len(ypl.obsoletes) > 0 and basecmd == 'list':
            # if we've looked up obsolete lists and it's a list request
                rop = [0, '']
                print(_('Obsoleting Packages'))
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    self.output.updatesObsoletesList(obtup, 'obsoletes',
                                                     columns=columns)
            else:
                rop = self.output.listPkgs(ypl.obsoletes, _('Obsoleting Packages'),
                                    basecmd, columns=columns)
            rrap = self.output.listPkgs(ypl.recent, _('Recently Added Packages'),
                                 basecmd, columns=columns)
            # extcmds is pop(0)'d if they pass a "special" param like "updates"
            # in returnPkgLists(). This allows us to always return "ok" for
            # things like "yum list updates".
            if len(extcmds) and \
               rrap[0] and rop[0] and rup[0] and rep[0] and rap[0] and rip[0]:
                return 1, [_('No matching Packages to list')]
            return 0, []

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        if len(extcmds) and extcmds[0] == 'installed':
            return False

        return True

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


class EraseCommand(Command):
    """A class containing methods needed by the cli to execute the
    erase command.
    """

    activate_sack = True
    aliases = ('erase', 'remove')
    load_available_repos = False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.erasePkgs(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

    def needTsRemove(self, basecmd, extcmds):
        """Return whether a transaction set for removal only must be
        set up before this command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a remove-only transaction set is needed, False otherwise
        """
        return True


class GroupsCommand(Command):
    """ Single sub-command interface for most groups interaction. """

    activate_sack = True
    direct_commands = {'grouplist'    : 'list',
                       'groupinstall' : 'install',
                       'groupupdate'  : 'install',
                       'groupremove'  : 'remove',
                       'grouperase'   : 'remove',
                       'groupinfo'    : 'info'}
    aliases = ('group', 'groups') + tuple(direct_commands.keys())

    @staticmethod
    def get_usage():
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[list|info|summary|install|upgrade|remove|mark] [GROUP]"

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display, or use, the groups information")

    def _grp_setup_doCommand(self):
        try:
            self.base.read_comps()
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

    def _grp_cmd(self, basecmd, extcmds):
        return extcmds[0], extcmds[1:]

    _CMD_ALIASES = {'update'     : 'upgrade',
                    'erase'      : 'remove',
                    'mark-erase' : 'mark-remove'}

    @classmethod
    def canonical(cls, command_list):
        first = command_list[0]
        rest = command_list[1:]

        cmd = cls.direct_commands.get(first)
        if cmd is None:
            cmd = 'summary'
            if rest:
                cmd = rest.pop(0)
        cmd = cls._CMD_ALIASES.get(cmd, cmd)

        rest.insert(0, cmd)
        return ('groups', rest)

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        The exact conditions checked will vary depending on the
        subcommand that is being called.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        checkEnabledRepo(self.base)

        if cmd in ('install', 'remove',
                   'mark-install', 'mark-remove',
                   'mark-members', 'info', 'mark-members-sync'):
            checkGroupArg(self.cli, cmd, extcmds)

        if cmd in ('install', 'upgrade'):
            checkGPGKey(self.base, self.cli)

        cmds = ('list', 'info', 'remove', 'install', 'upgrade', 'summary',
                'mark-install', 'mark-remove',
                'mark-members', 'mark-members-sync')
        if cmd not in cmds:
            self.base.logger.critical(_('Invalid groups sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise CliError

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        self._grp_setup_doCommand()
        if cmd == 'summary':
            return self.base.returnGroupSummary(extcmds)

        if cmd == 'list':
            return self.base.returnGroupLists(extcmds)

        try:
            if cmd == 'info':
                return self.base.returnGroupInfo(extcmds)
            if cmd == 'install':
                return self.base.install_grouplist(extcmds)
            if cmd == 'upgrade':
                return self.base.install_grouplist(extcmds)
            if cmd == 'remove':
                return self.base.removeGroups(extcmds)

        except dnf.exceptions.Error as e:
            return 1, [str(e)]


    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        if cmd in ('list', 'info', 'remove', 'summary'):
            return False
        return True

    def needTsRemove(self, basecmd, extcmds):
        """Return whether a transaction set for removal only must be
        set up before this command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a remove-only transaction set is needed, False otherwise
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        if cmd in ('remove',):
            return True
        return False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        msg = _("Making cache files for all metadata files.")
        self.base.logger.debug(msg)
        period = self.base.conf.metadata_timer_sync
        timer = 'timer' == dnf.util.first(extcmds)
        persistor = self.base._persistor
        if timer:
            if dnf.util.on_ac_power() is False:
                return 0, [_('Metadata timer caching disabled '
                             'when running on a battery.')]
            if period <= 0:
                return 0, [_('Metadata timer caching disabled.')]
            since_last_makecache = persistor.since_last_makecache()
            if since_last_makecache is not None and since_last_makecache < period:
                return 0, [_('Metadata cache refreshed recently.')]
            self.base.repos.all.max_mirror_tries = 1

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
        return 0, [_('Metadata Cache Created')]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        return self.base.cleanCli(extcmds)

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.base.logger.debug("Searching Packages: ")
        try:
            return self.base.provides(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

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

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that there is at least one enabled repository.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkEnabledRepo(self.base)

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        obscmds = ['obsoletes'] + extcmds
        self.base.extcmds.insert(0, 'updates')
        result = 0
        try:
            ypl = self.base.returnPkgLists(extcmds)
            if self.base.conf.obsoletes or self.base.conf.verbose:
                typl = self.base.returnPkgLists(obscmds)
                ypl.obsoletes = typl.obsoletes
                ypl.obsoletesTuples = typl.obsoletesTuples

            columns = _list_cmd_calc_columns(self.output, ypl)
            if len(ypl.updates) > 0:
                local_pkgs = {}
                highlight = self.output.term.MODE['bold']
                if highlight:
                    # Do the local/remote split we get in "yum updates"
                    for po in sorted(ypl.updates):
                        local = po.localPkg()
                        if os.path.exists(local) and po.verifyLocalPkg():
                            local_pkgs[(po.name, po.arch)] = po

                cul = self.base.conf.color_update_local
                cur = self.base.conf.color_update_remote
                self.output.listPkgs(ypl.updates, '', outputType='list',
                              highlight_na=local_pkgs, columns=columns,
                              highlight_modes={'=' : cul, 'not in' : cur})
                result = 100
            if len(ypl.obsoletes) > 0:
                print(_('Obsoleting Packages'))
                # The tuple is (newPkg, oldPkg) ... so sort by new
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    self.output.updatesObsoletesList(obtup, 'obsoletes',
                                                     columns=columns)
                result = 100
        except dnf.exceptions.Error as e:
            return 1, [str(e)]
        else:
            return result, []

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.base.logger.debug(_("Searching Packages: "))
        try:
            return self.cli.search(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.deplist(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]


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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
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

        return 0, ['repolist: ' +to_unicode(locale.format("%d", tot_num, True))]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False


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
            raise CliError
        elif len(extcmds) > 1 or extcmds[0] not in self.cli.cli_commands:
            self.cli.print_usage()
            raise CliError

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        if extcmds[0] in self.cli.cli_commands:
            command = self.cli.cli_commands[extcmds[0]]
            self.base.logger.info(self._makeOutput(command))
        return 0, []

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class ReInstallCommand(Command):
    """A class containing methods needed by the cli to execute the
    reinstall command.
    """

    activate_sack = True
    aliases = ('reinstall',)

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.reinstallPkgs(extcmds)

        except dnf.exceptions.Error as e:
            return 1, [to_unicode(e)]

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("reinstall a package")

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class DowngradeCommand(Command):
    """A class containing methods needed by the cli to execute the
    downgrade command.
    """

    activate_sack = True
    aliases = ('downgrade',)

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            return self.base.downgradePkgs(extcmds)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]

    @staticmethod
    def get_summary():
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("downgrade a package")

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
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

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        vcmd = 'installed'
        if extcmds:
            vcmd = extcmds[0]
        verbose = self.base.conf.verbose
        if vcmd == 'groupinfo' and verbose:
            return True
        return vcmd in ('available', 'all', 'group-available', 'group-all')


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
            raise CliError
        if extcmds and extcmds[0] in ('repeat', 'redo', 'undo', 'rollback', 'new'):
            checkGPGKey(self.base, self.cli)
        elif not os.access(self.base.history._db_file, os.R_OK):
            self.base.logger.critical(_("You don't have access to the history DB."))
            raise CliError

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
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
            return 0, []
        return ret

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        vcmd = 'list'
        if extcmds:
            vcmd = extcmds[0]
        return vcmd in ('repeat', 'redo', 'undo', 'rollback')


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

    def doCommand(self, basecmd, extcmds):
        """Execute this command.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        chkcmd = 'all'
        if extcmds:
            chkcmd = extcmds

        def _out(x):
            print(to_unicode(x.__str__()))

        rc = 0
        if self.base._rpmdb_warn_checks(out=_out, warn=False, chkcmd=chkcmd,
                                   header=lambda x: None):
            rc = 1
        return rc, ['%s %s' % (basecmd, chkcmd)]

    def needTs(self, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False
