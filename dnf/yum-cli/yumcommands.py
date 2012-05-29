#!/usr/bin/python -t
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2006 Duke University 
# Written by Seth Vidal

"""
Classes for subcommands of the yum command line interface.
"""

import os
import cli
from yum import logginglevels
from yum import _
from yum import misc
import yum.Errors
import operator
import locale
import fnmatch
import time
from yum.i18n import utf8_width, utf8_width_fill, to_unicode

import yum.config
import hawkey

def _err_mini_usage(base, basecmd):
    if basecmd not in base.yum_cli_commands:
        base.usage()
        return
    cmd = base.yum_cli_commands[basecmd]
    txt = base.yum_cli_commands["help"]._makeOutput(cmd)
    base.logger.critical(_(' Mini usage:\n'))
    base.logger.critical(txt)

def checkRootUID(base):
    """Verify that the program is being run by the root user.

    :param base: a :class:`yum.Yumbase` object.
    :raises: :class:`cli.CliError`
    """
    return None
    if base.conf.uid != 0:
        base.logger.critical(_('You need to be root to perform this command.'))
        raise cli.CliError

def checkGPGKey(base):
    """Verify that there are gpg keys for the enabled repositories in the
    rpm database.

    :param base: a :class:`yum.Yumbase` object.
    :raises: :class:`cli.CliError`
    """
    if base._override_sigchecks:
        return
    if not base.gpgKeyCheck():
        for repo in base.repos.listEnabled():
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
                raise cli.CliError

def checkPackageArg(base, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one package for
    *basecmd* to act on.

    :param base: a :class:`yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        base.logger.critical(
                _('Error: Need to pass a list of pkgs to %s') % basecmd)
        _err_mini_usage(base, basecmd)
        raise cli.CliError

def checkItemArg(base, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one item for
    *basecmd* to act on.  Generally, the items are command-line
    arguments that are not the name of a package, such as a file name
    passed to provides.

    :param base: a :class:`yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        base.logger.critical(_('Error: Need an item to match'))
        _err_mini_usage(base, basecmd)
        raise cli.CliError

def checkGroupArg(base, basecmd, extcmds):
    """Verify that *extcmds* contains the name of at least one group for
    *basecmd* to act on.

    :param base: a :class:`yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        base.logger.critical(_('Error: Need a group or list of groups'))
        _err_mini_usage(base, basecmd)
        raise cli.CliError    

def checkCleanArg(base, basecmd, extcmds):
    """Verify that *extcmds* contains at least one argument, and that all
    arguments in *extcmds* are valid options for clean.

    :param base: a :class:`yum.Yumbase` object
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    VALID_ARGS = ('headers', 'packages', 'metadata', 'dbcache', 'plugins',
                  'expire-cache', 'rpmdb', 'all')

    if len(extcmds) == 0:
        base.logger.critical(_('Error: clean requires an option: %s') % (
            ", ".join(VALID_ARGS)))

    for cmd in extcmds:
        if cmd not in VALID_ARGS:
            base.logger.critical(_('Error: invalid clean argument: %r') % cmd)
            _err_mini_usage(base, basecmd)
            raise cli.CliError

def checkShellArg(base, basecmd, extcmds):
    """Verify that the arguments given to 'yum shell' are valid.  yum
    shell can be given either no argument, or exactly one argument,
    which is the name of a file.

    :param base: a :class:`yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`
    """
    if len(extcmds) == 0:
        base.verbose_logger.debug(_("No argument to shell"))
    elif len(extcmds) == 1:
        base.verbose_logger.debug(_("Filename passed to shell: %s"), 
            extcmds[0])              
        if not os.path.isfile(extcmds[0]):
            base.logger.critical(
                _("File %s given as argument to shell does not exist."), 
                extcmds[0])
            base.usage()
            raise cli.CliError
    else:
        base.logger.critical(
                _("Error: more than one file given as argument to shell."))
        base.usage()
        raise cli.CliError

def checkEnabledRepo(base, possible_local_files=[]):
    """Verify that there is at least one enabled repo.

    :param base: a :class:`yum.Yumbase` object.
    :param basecmd: the name of the command being checked for
    :param extcmds: a list of arguments passed to *basecmd*
    :raises: :class:`cli.CliError`:
    """
    if base.repos.listEnabled():
        return

    for lfile in possible_local_files:
        if lfile.endswith(".rpm") and os.path.exists(lfile):
            return

    msg = _('There are no enabled repos.\n'
            ' Run "yum repolist all" to see the repos you have.\n'
            ' You can enable repos with yum-config-manager --enable <repo>')
    base.logger.critical(msg)
    raise cli.CliError

class YumCommand:
    """An abstract base class that defines the methods needed by the cli
    to execute a specific command.  Subclasses must override at least
    :func:`getUsage` and :func:`getSummary`.
    """

    def __init__(self):
        self.done_command_once = False
        self.hidden = False

    def doneCommand(self, base, msg, *args):
        """ Output *msg* the first time that this method is called, and do
        nothing on subsequent calls.  This is to prevent duplicate
        messages from being printed for the same command.

        :param base: a :class:`yum.Yumbase` object
        :param msg: the message to be output
        :param *args: additional arguments associated with the message
        """
        if not self.done_command_once:
            base.verbose_logger.info(msg, *args)
        self.done_command_once = True

    def getNames(self):
        """Return a list of strings that are the names of the command.
        The command can be called from the command line by using any
        of these names.

        :return: a list containing the names of the command
        """
        return []

    def getUsage(self):
        """Return a usage string for the command, including arguments.

        :return: a usage string for the command
        """
        raise NotImplementedError

    def getSummary(self):
        """Return a one line summary of what the command does.

        :return: a one line summary of what the command does
        """
        raise NotImplementedError
    
    def doCheck(self, base, basecmd, extcmds):
        """Verify that various conditions are met so that the command
        can run.

        :param base: a :class:`yum.Yumbase` object.
        :param basecmd: the name of the command being checked for
        :param extcmds: a list of arguments passed to *basecmd*
        """
        pass

    def doCommand(self, base, basecmd, extcmds):
        """Execute the command

        :param base: a :class:`yum.Yumbase` object.
        :param basecmd: the name of the command being executed
        :param extcmds: a list of arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        return 0, [_('Nothing to do')]
    
    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before the
        command can run

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return True
        
class InstallCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    install command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of
        these names.

        :return: a list containing the names of this command
        """
        return ['install']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("PACKAGE...")

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Install a package or packages on your system")
    
    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that the program is being run by the root user,
        that there are enabled repositories with gpg keys, and that
        this command is called with appropriate arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Install Process"))
        try:
            return base.installPkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class UpdateCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    update command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can by called from the command line by using any of
        these names.

        :return: a list containing the names of this command
        """
        return ['update', 'update-to']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("[PACKAGE...]")

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Update a package or packages on your system")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that there are enabled repositories with gpg
        keys, and that this command is being run by the root user.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Update Process"))
        try:
            return base.updatePkgs(extcmds, update_to=(basecmd == 'update-to'))
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class DistroSyncCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    distro-synch command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['distribution-synchronization', 'distro-sync']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return _("[PACKAGE...]")

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Synchronize installed packages to the latest available versions")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that the program is being run by the root user,
        and that there are enabled repositories with gpg keys.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Distribution Synchronization Process"))
        try:
            base.conf.obsoletes = 1
            return base.distroSyncPkgs(extcmds)
        except yum.Errors.YumBaseError, e:
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

def _list_cmd_calc_columns(base, ypl):
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
    columns = base.calcColumns(data, remainder_column=1)
    return (-columns[0], -columns[1], -columns[2])

class InfoCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    info command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['info']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[PACKAGE|all|available|installed|updates|extras|obsoletes|recent]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display details about a package or group of packages")

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        try:
            highlight = base.term.MODE['bold']
            ypl = base.returnPkgLists(extcmds, installed_available=highlight)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        else:
            update_pkgs = {}
            inst_pkgs   = {}
            local_pkgs  = {}

            columns = None
            if basecmd == 'list':
                # Dynamically size the columns
                columns = _list_cmd_calc_columns(base, ypl)

            if highlight and ypl.installed:
                #  If we have installed and available lists, then do the
                # highlighting for the installed packages so you can see what's
                # available to update, an extra, or newer than what we have.
                for pkg in (ypl.hidden_available +
                            ypl.reinstall_available +
                            ypl.old_available):
                    key = (pkg.name, pkg.arch)
                    if key not in update_pkgs or pkg.verGT(update_pkgs[key]):
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
            clio = base.conf.color_list_installed_older
            clin = base.conf.color_list_installed_newer
            clir = base.conf.color_list_installed_reinstall
            clie = base.conf.color_list_installed_extra
            rip = base.listPkgs(ypl.installed, _('Installed Packages'), basecmd,
                                highlight_na=update_pkgs, columns=columns,
                                highlight_modes={'>' : clio, '<' : clin,
                                                 '=' : clir, 'not in' : clie})
            clau = base.conf.color_list_available_upgrade
            clad = base.conf.color_list_available_downgrade
            clar = base.conf.color_list_available_reinstall
            clai = base.conf.color_list_available_install
            rap = base.listPkgs(ypl.available, _('Available Packages'), basecmd,
                                highlight_na=inst_pkgs, columns=columns,
                                highlight_modes={'<' : clau, '>' : clad,
                                                 '=' : clar, 'not in' : clai})
            rep = base.listPkgs(ypl.extras, _('Extra Packages'), basecmd,
                                columns=columns)
            cul = base.conf.color_update_local
            cur = base.conf.color_update_remote
            rup = base.listPkgs(ypl.updates, _('Updated Packages'), basecmd,
                                highlight_na=local_pkgs, columns=columns,
                                highlight_modes={'=' : cul, 'not in' : cur})

            # XXX put this into the ListCommand at some point
            if len(ypl.obsoletes) > 0 and basecmd == 'list': 
            # if we've looked up obsolete lists and it's a list request
                rop = [0, '']
                print _('Obsoleting Packages')
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    base.updatesObsoletesList(obtup, 'obsoletes', columns=columns)
            else:
                rop = base.listPkgs(ypl.obsoletes, _('Obsoleting Packages'),
                                    basecmd, columns=columns)
            rrap = base.listPkgs(ypl.recent, _('Recently Added Packages'),
                                 basecmd, columns=columns)
            # extcmds is pop(0)'d if they pass a "special" param like "updates"
            # in returnPkgLists(). This allows us to always return "ok" for
            # things like "yum list updates".
            if len(extcmds) and \
               rrap[0] and rop[0] and rup[0] and rep[0] and rap[0] and rip[0]:
                return 1, [_('No matching Packages to list')]
            return 0, []

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
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

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['list']

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("List a package or groups of packages")


class EraseCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    erase command.
    """

        
    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['erase', 'remove']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Remove a package or packages from your system")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, and that this command is called with appropriate
        arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Remove Process"))
        try:
            return base.erasePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

    def needTsRemove(self, base, basecmd, extcmds):
        """Return whether a transaction set for removal only must be
        set up before this command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a remove-only transaction set is needed, False otherwise
        """
        return True

 
class GroupsCommand(YumCommand):
    """ Single sub-command interface for most groups interaction. """

    direct_commands = {'grouplist'    : 'list',
                       'groupinstall' : 'install',
                       'groupupdate'  : 'install',
                       'groupremove'  : 'remove',
                       'grouperase'   : 'remove',
                       'groupinfo'    : 'info'}

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['groups', 'group'] + self.direct_commands.keys()

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[list|info|summary|install|upgrade|remove|mark] [GROUP]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display, or use, the groups information")
    
    def _grp_setup_doCommand(self, base):
        self.doneCommand(base, _("Setting up Group Process"))

        base.doRepoSetup(dosack=0)
        try:
            base.doGroupSetup()
        except yum.Errors.GroupsError:
            return 1, [_('No Groups on which to run command')]
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def _grp_cmd(self, basecmd, extcmds):
        if basecmd in self.direct_commands:
            cmd = self.direct_commands[basecmd]
        elif extcmds:
            cmd = extcmds[0]
            extcmds = extcmds[1:]
        else:
            cmd = 'summary'

        remap = {'update' : 'upgrade',
                 'erase' : 'remove',
                 'mark-erase' : 'mark-remove',
                 }
        cmd = remap.get(cmd, cmd)

        return cmd, extcmds

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        The exact conditions checked will vary depending on the
        subcommand that is being called.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        checkEnabledRepo(base)

        if cmd in ('install', 'remove',
                   'mark-install', 'mark-remove',
                   'mark-members', 'info', 'mark-members-sync'):
            checkGroupArg(base, cmd, extcmds)

        if cmd in ('install', 'remove', 'upgrade',
                   'mark-install', 'mark-remove',
                   'mark-members', 'mark-members-sync'):
            checkRootUID(base)

        if cmd in ('install', 'upgrade'):
            checkGPGKey(base)

        cmds = ('list', 'info', 'remove', 'install', 'upgrade', 'summary',
                'mark-install', 'mark-remove',
                'mark-members', 'mark-members-sync')
        if cmd not in cmds:
            base.logger.critical(_('Invalid groups sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise cli.CliError

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        self._grp_setup_doCommand(base)
        if cmd == 'summary':
            return base.returnGroupSummary(extcmds)

        if cmd == 'list':
            return base.returnGroupLists(extcmds)

        try:
            if cmd == 'info':
                return base.returnGroupInfo(extcmds)
            if cmd == 'install':
                return base.installGroups(extcmds)
            if cmd == 'upgrade':
                return base.installGroups(extcmds, upgrade=True)
            if cmd == 'remove':
                return base.removeGroups(extcmds)

        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]


    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        if cmd in ('list', 'info', 'remove', 'summary'):
            return False
        return True

    def needTsRemove(self, base, basecmd, extcmds):
        """Return whether a transaction set for removal only must be
        set up before this command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a remove-only transaction set is needed, False otherwise
        """
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)

        if cmd in ('remove',):
            return True
        return False

class MakeCacheCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    makecache command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['makecache']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return ""

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Generate the metadata cache")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that there is an enabled repository.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkEnabledRepo(base)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.logger.debug(_("Making cache files for all metadata files."))
        sack = base.sack # triggers metadata sync
        sack.ensure_filelists(base.repos) # does filelists sync
        return 0, [_('Metadata Cache Created')]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class CleanCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    clean command.
    """
    
    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['clean']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[headers|packages|metadata|dbcache|plugins|expire-cache|all]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Remove cached data")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that there is at least one enabled repository,
        and that this command is called with appropriate arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkCleanArg(base, basecmd, extcmds)
        checkEnabledRepo(base)
        
    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.conf.cache = 1
        return base.cleanCli(extcmds)

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class ProvidesCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    provides command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['provides', 'whatprovides']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "SOME_STRING"
    
    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Find what package provides the given value")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkItemArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.logger.debug("Searching Packages: ")
        try:
            return base.provides(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class CheckUpdateCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    check-update command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['check-update']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[PACKAGE...]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Check for available package updates")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that there is at least one enabled repository.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkEnabledRepo(base)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        obscmds = ['obsoletes'] + extcmds
        base.extcmds.insert(0, 'updates')
        result = 0
        try:
            ypl = base.returnPkgLists(extcmds)
            if (base.conf.obsoletes or
                base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)):
                typl = base.returnPkgLists(obscmds)
                ypl.obsoletes = typl.obsoletes
                ypl.obsoletesTuples = typl.obsoletesTuples

            columns = _list_cmd_calc_columns(base, ypl)
            if len(ypl.updates) > 0:
                local_pkgs = {}
                highlight = base.term.MODE['bold']
                if highlight:
                    # Do the local/remote split we get in "yum updates"
                    for po in sorted(ypl.updates):
                        if po.repo.id != 'installed' and po.verifyLocalPkg():
                            local_pkgs[(po.name, po.arch)] = po

                cul = base.conf.color_update_local
                cur = base.conf.color_update_remote
                base.listPkgs(ypl.updates, '', outputType='list',
                              highlight_na=local_pkgs, columns=columns,
                              highlight_modes={'=' : cul, 'not in' : cur})
                result = 100
            if len(ypl.obsoletes) > 0: # This only happens in verbose mode
                print _('Obsoleting Packages')
                # The tuple is (newPkg, oldPkg) ... so sort by new
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    base.updatesObsoletesList(obtup, 'obsoletes',
                                              columns=columns)
                result = 100
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        else:
            return result, []

class SearchCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    search command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['search']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "SOME_STRING"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Search package details for the given string")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkItemArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.logger.debug(_("Searching Packages: "))
        try:
            return base.search(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class UpgradeCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    upgrade command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['upgrade', 'upgrade-to']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return 'PACKAGE...'

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Update packages taking obsoletes into account")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
         run.  These include that the program is being run by the root
         user, and that there are enabled repositories with gpg.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.conf.obsoletes = 1
        self.doneCommand(base, _("Setting up Upgrade Process"))
        try:
            return base.updatePkgs(extcmds, update_to=(basecmd == 'upgrade-to'))
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class LocalInstallCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    localinstall command.
    """

    def __init__(self):
        YumCommand.__init__(self)
        self.hidden = True

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['localinstall', 'localupdate']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "FILE"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Install a local RPM")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that there are enabled repositories with
        gpg keys, and that this command is called with appropriate
        arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        
    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is:

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Local Package Process"))

        updateonly = basecmd == 'localupdate'
        try:
            return base.localInstall(filelist=extcmds, updateonly=updateonly)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class ResolveDepCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    resolvedep command.
    """

    def __init__(self):
        YumCommand.__init__(self)
        self.hidden = True

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['resolvedep']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "DEPENDENCY"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return "repoquery --pkgnarrow=all --whatprovides --qf '%{envra} %{ui_from_repo}'"

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        base.logger.debug(_("Searching Packages for Dependency:"))
        try:
            return base.resolveDepCli(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class ShellCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    shell command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['shell']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[FILENAME]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Run an interactive yum shell")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkShellArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _('Setting up Yum Shell'))
        try:
            return base.doShell()
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False


class DepListCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    deplist command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['deplist']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return 'PACKAGE...'

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("List a package's dependencies")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate
        arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Finding dependencies: "))
        try:
            return base.deplist(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]


class RepoListCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    repolist command.
    """
    
    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ('repolist',)

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return '[all|enabled|disabled]'

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _('Display the configured software repositories')

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
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
            for pkg in repo.sack.returnPackages():
                ret += pkg.packagesize
            return base.format_number(ret)

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
        extcmds = map(lambda x: x.lower(), extcmds)

        verbose = base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if arg != 'disabled' or extcmds:
            try:
                # Setup so len(repo.sack) is correct
                base.repos.populateSack()
                base.pkgSack # Need to setup the pkgSack, so excludes work
            except yum.Errors.RepoError:
                if verbose:
                    raise
                #  populate them by hand, so one failure doesn't kill everything
                # after it.
                for repo in base.repos.listEnabled():
                    try:
                        base.repos.populateSack(repo.id)
                    except yum.Errors.RepoError:
                        pass

        repos = base.repos.repos.values()
        repos.sort()
        enabled_repos = base.repos.listEnabled()
        on_ehibeg = base.term.FG_COLOR['green'] + base.term.MODE['bold']
        on_dhibeg = base.term.FG_COLOR['red']
        on_hiend  = base.term.MODE['normal']
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
                    if verbose or base.conf.exclude or repo.exclude:
                        num        = len(repo.sack.simplePkgList())
                    else:
                        num        = len(repo.sack)
                    ui_num     = _num2ui_num(num)
                    excludes   = repo.sack._excludes
                    excludes   = len([pid for r,pid in excludes if r == repo])
                    if excludes:
                        ui_excludes_num = _num2ui_num(excludes)
                        if not verbose:
                            ui_num += "+%s" % ui_excludes_num
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
                rid = str(repo)
                if enabled and repo.metalink:
                    mdts = repo.metalink_data.repomd.timestamp
                    if mdts > repo.repoXML.timestamp:
                        rid = '*' + rid
                cols.append((rid, repo.name,
                             (ui_enabled, ui_endis_wid), ui_num))
            else:
                if enabled:
                    md = repo.repoXML
                else:
                    md = None
                out = [base.fmtKeyValFill(_("Repo-id      : "), repo),
                       base.fmtKeyValFill(_("Repo-name    : "), repo.name)]

                if force_show or extcmds:
                    out += [base.fmtKeyValFill(_("Repo-status  : "),
                                               ui_enabled)]
                if md and md.revision is not None:
                    out += [base.fmtKeyValFill(_("Repo-revision: "),
                                               md.revision)]
                if md and md.tags['content']:
                    tags = md.tags['content']
                    out += [base.fmtKeyValFill(_("Repo-tags    : "),
                                               ", ".join(sorted(tags)))]

                if md and md.tags['distro']:
                    for distro in sorted(md.tags['distro']):
                        tags = md.tags['distro'][distro]
                        out += [base.fmtKeyValFill(_("Repo-distro-tags: "),
                                                   "[%s]: %s" % (distro,
                                                   ", ".join(sorted(tags))))]

                if md:
                    out += [base.fmtKeyValFill(_("Repo-updated : "),
                                               time.ctime(md.timestamp)),
                            base.fmtKeyValFill(_("Repo-pkgs    : "),ui_num),
                            base.fmtKeyValFill(_("Repo-size    : "),ui_size)]

                if hasattr(repo, '_orig_baseurl'):
                    baseurls = repo._orig_baseurl
                else:
                    baseurls = repo.baseurl
                if baseurls:
                    out += [base.fmtKeyValFill(_("Repo-baseurl : "),
                                               ", ".join(baseurls))]

                if enabled:
                    # This needs to be here due to the mirrorlists are
                    # metalinks hack.
                    repo.urls
                if repo.metalink:
                    out += [base.fmtKeyValFill(_("Repo-metalink: "),
                                               repo.metalink)]
                    if enabled:
                        ts = repo.metalink_data.repomd.timestamp
                        out += [base.fmtKeyValFill(_("  Updated    : "),
                                                   time.ctime(ts))]
                elif repo.mirrorlist:
                    out += [base.fmtKeyValFill(_("Repo-mirrors : "),
                                               repo.mirrorlist)]
                if enabled and repo.urls and not baseurls:
                    url = repo.urls[0]
                    if len(repo.urls) > 1:
                        url += ' (%d more)' % (len(repo.urls) - 1)
                    out += [base.fmtKeyValFill(_("Repo-baseurl : "), url)]

                if not os.path.exists(repo.metadata_cookie):
                    last = _("Unknown")
                else:
                    last = os.stat(repo.metadata_cookie).st_mtime
                    last = time.ctime(last)

                if repo.metadata_expire <= -1:
                    num = _("Never (last: %s)") % last
                elif not repo.metadata_expire:
                    num = _("Instant (last: %s)") % last
                else:
                    num = _num2ui_num(repo.metadata_expire)
                    num = _("%s second(s) (last: %s)") % (num, last)

                out += [base.fmtKeyValFill(_("Repo-expire  : "), num)]

                if repo.exclude:
                    out += [base.fmtKeyValFill(_("Repo-exclude : "),
                                               ", ".join(repo.exclude))]

                if repo.includepkgs:
                    out += [base.fmtKeyValFill(_("Repo-include : "),
                                               ", ".join(repo.includepkgs))]

                if ui_excludes_num:
                    out += [base.fmtKeyValFill(_("Repo-excluded: "),
                                               ui_excludes_num)]

                if repo.repofile:
                    out += [base.fmtKeyValFill(_("Repo-filename: "),
                                               repo.repofile)]

                base.verbose_logger.log(logginglevels.DEBUG_3, "%s\n",
                                        "\n".join(map(misc.to_unicode, out)))

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
                left = base.term.columns - (id_len + 1)
            elif utf8_width(_('status')) > st_len:
                left = base.term.columns - (id_len + utf8_width(_('status')) +2)
            else:
                left = base.term.columns - (id_len + st_len + 2)

            if left < nm_len: # Name gets chopped
                nm_len = left
            else: # Share the extra...
                left -= nm_len
                id_len += left / 2
                nm_len += left - (left / 2)

            txt_rid  = utf8_width_fill(_('repo id'), id_len)
            txt_rnam = utf8_width_fill(_('repo name'), nm_len, nm_len)
            if arg == 'disabled': # Don't output a status column.
                base.verbose_logger.info("%s %s",
                                        txt_rid, txt_rnam)
            else:
                base.verbose_logger.info("%s %s %s",
                                        txt_rid, txt_rnam, _('status'))
            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if arg == 'disabled': # Don't output a status column.
                    base.verbose_logger.info("%s %s",
                                            utf8_width_fill(rid, id_len),
                                            utf8_width_fill(rname, nm_len,
                                                            nm_len))
                    continue

                if ui_num:
                    ui_num = utf8_width_fill(ui_num, ui_len, left=False)
                base.verbose_logger.info("%s %s %s%s",
                                        utf8_width_fill(rid, id_len),
                                        utf8_width_fill(rname, nm_len, nm_len),
                                        ui_enabled, ui_num)

        return 0, ['repolist: ' +to_unicode(locale.format("%d", tot_num, True))]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False


class HelpCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    help command.
    """


    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['help']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "COMMAND"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display a helpful usage message")

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run; namely that this command is called with appropriate
        arguments.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        if len(extcmds) == 0:
            base.usage()
            raise cli.CliError
        elif len(extcmds) > 1 or extcmds[0] not in base.yum_cli_commands:
            base.usage()
            raise cli.CliError

    @staticmethod
    def _makeOutput(command):
        canonical_name = command.getNames()[0]

        # Check for the methods in case we have plugins that don't
        # implement these.
        # XXX Remove this once usage/summary are common enough
        try:
            usage = command.getUsage()
        except (AttributeError, NotImplementedError):
            usage = None
        try:
            summary = command.getSummary()
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

        command_names = command.getNames()
        if len(command_names) > 1:
            if len(command_names) > 2:
                help_output += _("\n\naliases: ")
            else:
                help_output += _("\n\nalias: ")
            help_output += ', '.join(command.getNames()[1:])

        return help_output

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        if extcmds[0] in base.yum_cli_commands:
            command = base.yum_cli_commands[extcmds[0]]
            base.verbose_logger.info(self._makeOutput(command))
        return 0, []

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class ReInstallCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    reinstall command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['reinstall']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.


        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Reinstall Process"))
        try:
            return base.reinstallPkgs(extcmds)
            
        except yum.Errors.YumBaseError, e:
            return 1, [to_unicode(e)]

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("reinstall a package")

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False
        
class DowngradeCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    downgrade command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['downgrade']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "PACKAGE..."

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.


        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        checkEnabledRepo(base, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self.doneCommand(base, _("Setting up Downgrade Process"))
        try:
            return base.downgradePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("downgrade a package")

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False


class VersionCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    version command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['version']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[all|installed|available]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display a version for the machine and/or available repos.")

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
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

        verbose = base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        groups = {}
        if vcmd in ('nogroups', 'nogroups-installed', 'nogroups-available',
                    'nogroups-all'):
            gconf = []
            if vcmd == 'nogroups':
                vcmd = 'installed'
            else:
                vcmd = vcmd[len('nogroups-'):]
        else:
            gconf = yum.config.readVersionGroupsConfig()

        for group in gconf:
            groups[group] = set(gconf[group].pkglist)
            if gconf[group].run_with_packages:
                groups[group].update(base.run_with_package_names)

        if vcmd == 'grouplist':
            print _(" Yum version groups:")
            for group in sorted(groups):
                print "   ", group

            return 0, ['version grouplist']

        if vcmd == 'groupinfo':
            for group in groups:
                if group not in extcmds[1:]:
                    continue
                print _(" Group   :"), group
                print _(" Packages:")
                if not verbose:
                    for pkgname in sorted(groups[group]):
                        print "   ", pkgname
                else:
                    data = {'envra' : {}, 'rid' : {}}
                    pkg_names = groups[group]
                    pkg_names2pkgs = base._group_names2aipkgs(pkg_names)
                    base._calcDataPkgColumns(data, pkg_names, pkg_names2pkgs)
                    data = [data['envra'], data['rid']]
                    columns = base.calcColumns(data)
                    columns = (-columns[0], -columns[1])
                    base._displayPkgsFromNames(pkg_names, True, pkg_names2pkgs,
                                               columns=columns)

            return 0, ['version groupinfo']

        rel = base.conf.yumvar['releasever']
        ba  = base.conf.yumvar['basearch']
        cols = []
        if vcmd in ('installed', 'all', 'group-installed', 'group-all'):
            try:
                data = base.rpmdb.simpleVersion(not verbose, groups=groups)
                lastdbv = base.history.last()
                if lastdbv is not None:
                    lastdbv = lastdbv.end_rpmdbversion
                if lastdbv is not None and data[0] != lastdbv:
                    base._rpmdb_warn_checks(warn=lastdbv is not None)
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
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
        if vcmd in ('available', 'all', 'group-available', 'group-all'):
            try:
                data = base.pkgSack.simpleVersion(not verbose, groups=groups)
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
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]

        data = {'rid' : {}, 'ver' : {}}
        for (rid, ver) in cols:
            for (d, v) in (('rid', len(rid)), ('ver', len(ver))):
                data[d].setdefault(v, 0)
                data[d][v] += 1
        data = [data['rid'], data['ver']]
        columns = base.calcColumns(data)
        columns = (-columns[0], columns[1])

        for line in cols:
            print base.fmtColumns(zip(line, columns))

        return 0, ['version']

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        vcmd = 'installed'
        if extcmds:
            vcmd = extcmds[0]
        verbose = base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if vcmd == 'groupinfo' and verbose:
            return True
        return vcmd in ('available', 'all', 'group-available', 'group-all')


class HistoryCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    history command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['history']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[info|list|packages-list|summary|addon-info|redo|undo|rollback|new]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Display, or use, the transaction history")

    def _hcmd_redo(self, base, extcmds):
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

        old = base._history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history redo']
        tm = time.ctime(old.beg_timestamp)
        print "Repeating transaction %u, from %s" % (old.tid, tm)
        base.historyInfoCmdPkgsAltered(old)
        if base.history_redo(old, **kwargs):
            return 2, ["Repeating transaction %u" % (old.tid,)]

    def _hcmd_undo(self, base, extcmds):
        old = base._history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history undo']
        tm = time.ctime(old.beg_timestamp)
        print "Undoing transaction %u, from %s" % (old.tid, tm)
        base.historyInfoCmdPkgsAltered(old)
        if base.history_undo(old):
            return 2, ["Undoing transaction %u" % (old.tid,)]

    def _hcmd_rollback(self, base, extcmds):
        force = False
        if len(extcmds) > 1 and extcmds[1] == 'force':
            force = True
            extcmds = extcmds[:]
            extcmds.pop(0)

        old = base._history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history rollback, no transaction']
        last = base.history.last()
        if last is None:
            return 1, ['Failed history rollback, no last?']
        if old.tid == last.tid:
            return 0, ['Rollback to current, nothing to do']

        mobj = None
        for tid in base.history.old(range(old.tid + 1, last.tid + 1)):
            if not force and (tid.altered_lt_rpmdb or tid.altered_gt_rpmdb):
                if tid.altered_lt_rpmdb:
                    msg = "Transaction history is incomplete, before %u."
                else:
                    msg = "Transaction history is incomplete, after %u."
                print msg % tid.tid
                print " You can use 'history rollback force', to try anyway."
                return 1, ['Failed history rollback, incomplete']

            if mobj is None:
                mobj = yum.history.YumMergedHistoryTransaction(tid)
            else:
                mobj.merge(tid)

        tm = time.ctime(old.beg_timestamp)
        print "Rollback to transaction %u, from %s" % (old.tid, tm)
        print base.fmtKeyValFill("  Undoing the following transactions: ",
                                 ", ".join((str(x) for x in mobj.tid)))
        base.historyInfoCmdPkgsAltered(mobj)
        if base.history_undo(mobj):
            return 2, ["Rollback to transaction %u" % (old.tid,)]

    def _hcmd_new(self, base, extcmds):
        base.history._create_db_file()

    def _hcmd_stats(self, base, extcmds):
        print "File        :", base.history._db_file
        num = os.stat(base.history._db_file).st_size
        print "Size        :", locale.format("%d", num, True)
        counts = base.history._pkg_stats()
        trans_1 = base.history.old("1")[0]
        trans_N = base.history.last()
        print _("Transactions:"), trans_N.tid
        print _("Begin time  :"), time.ctime(trans_1.beg_timestamp)
        print _("End time    :"), time.ctime(trans_N.end_timestamp)
        print _("Counts      :")
        print _("  NEVRAC :"), locale.format("%6d", counts['nevrac'], True)
        print _("  NEVRA  :"), locale.format("%6d", counts['nevra'],  True)
        print _("  NA     :"), locale.format("%6d", counts['na'],     True)
        print _("  NEVR   :"), locale.format("%6d", counts['nevr'],   True)
        print _("  rpm DB :"), locale.format("%6d", counts['rpmdb'],  True)
        print _("  yum DB :"), locale.format("%6d", counts['yumdb'],  True)

    def _hcmd_sync(self, base, extcmds):
        extcmds = extcmds[1:]
        if not extcmds:
            extcmds = None
        for ipkg in sorted(base.rpmdb.returnPackages(patterns=extcmds)):
            if base.history.pkg2pid(ipkg, create=False) is None:
                continue

            print "Syncing rpm/yum DB data for:", ipkg, "...",
            if base.history.sync_alldb(ipkg):
                print "Done."
            else:
                print "FAILED."

    def doCheck(self, base, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  The exact conditions checked will vary depending on the
        subcommand that is being called.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        cmds = ('list', 'info', 'summary', 'repeat', 'redo', 'undo', 'new',
                'rollback',
                'addon', 'addon-info',
                'stats', 'statistics', 'sync', 'synchronize'
                'pkg', 'pkgs', 'pkg-list', 'pkgs-list',
                'package', 'package-list', 'packages', 'packages-list',
                'pkg-info', 'pkgs-info', 'package-info', 'packages-info')
        if extcmds and extcmds[0] not in cmds:
            base.logger.critical(_('Invalid history sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise cli.CliError
        if extcmds and extcmds[0] in ('repeat', 'redo', 'undo', 'rollback', 'new'):
            checkRootUID(base)
            checkGPGKey(base)
        elif not os.access(base.history._db_file, os.R_OK):
            base.logger.critical(_("You don't have access to the history DB."))
            raise cli.CliError

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
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
            ret = base.historyListCmd(extcmds)
        elif vcmd == 'info':
            ret = base.historyInfoCmd(extcmds)
        elif vcmd == 'summary':
            ret = base.historySummaryCmd(extcmds)
        elif vcmd in ('addon', 'addon-info'):
            ret = base.historyAddonInfoCmd(extcmds)
        elif vcmd in ('pkg', 'pkgs', 'pkg-list', 'pkgs-list',
                      'package', 'package-list', 'packages', 'packages-list'):
            ret = base.historyPackageListCmd(extcmds)
        elif vcmd == 'undo':
            ret = self._hcmd_undo(base, extcmds)
        elif vcmd in ('redo', 'repeat'):
            ret = self._hcmd_redo(base, extcmds)
        elif vcmd == 'rollback':
            ret = self._hcmd_rollback(base, extcmds)
        elif vcmd == 'new':
            ret = self._hcmd_new(base, extcmds)
        elif vcmd in ('stats', 'statistics'):
            ret = self._hcmd_stats(base, extcmds)
        elif vcmd in ('sync', 'synchronize'):
            ret = self._hcmd_sync(base, extcmds)
        elif vcmd in ('pkg-info', 'pkgs-info', 'package-info', 'packages-info'):
            ret = base.historyPackageInfoCmd(extcmds)

        if ret is None:
            return 0, ['history %s' % (vcmd,)]
        return ret

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        vcmd = 'list'
        if extcmds:
            vcmd = extcmds[0]
        return vcmd in ('repeat', 'redo', 'undo', 'rollback')


class CheckRpmdbCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    check-rpmdb command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['check', 'check-rpmdb']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "[dependencies|duplicates|all]"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("Check for problems in the rpmdb")

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
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
            print to_unicode(x.__str__())

        rc = 0
        if base._rpmdb_warn_checks(out=_out, warn=False, chkcmd=chkcmd,
                                   header=lambda x: None):
            rc = 1
        return rc, ['%s %s' % (basecmd, chkcmd)]

    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return False

class LoadTransactionCommand(YumCommand):
    """A class containing methods needed by the cli to execute the
    load-transaction command.
    """

    def getNames(self):
        """Return a list containing the names of this command.  This
        command can be called from the command line by using any of these names.

        :return: a list containing the names of this command
        """
        return ['load-transaction', 'load-ts']

    def getUsage(self):
        """Return a usage string for this command.

        :return: a usage string for this command
        """
        return "filename"

    def getSummary(self):
        """Return a one line summary of this command.

        :return: a one line summary of this command
        """
        return _("load a saved transaction from filename")

    def doCommand(self, base, basecmd, extcmds):
        """Execute this command.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        if not extcmds:
            base.logger.critical(_("No saved transaction file specified."))
            raise cli.CliError
        
        load_file = extcmds[0]
        self.doneCommand(base, _("loading transaction from %s") % load_file)
        
        try:
            base.load_ts(load_file)
        except yum.Errors.YumBaseError, e:
            return 1, [to_unicode(e)]
        return 2, [_('Transaction loaded from %s with %s members') % (load_file, len(base.tsInfo.getMembers()))]


    def needTs(self, base, basecmd, extcmds):
        """Return whether a transaction set must be set up before this
        command can run.

        :param base: a :class:`yum.Yumbase` object
        :param basecmd: the name of the command
        :param extcmds: a list of arguments passed to *basecmd*
        :return: True if a transaction set is needed, False otherwise
        """
        return True

