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
import yum.Errors
import operator
import locale
import fnmatch
import time

def checkRootUID(base):
    """
    Verify that the program is being run by the root user.

    @param base: a YumBase object.
    """
    if base.conf.uid != 0:
        base.logger.critical(_('You need to be root to perform this command.'))
        raise cli.CliError

def checkGPGKey(base):
    if not base.gpgKeyCheck():
        for repo in base.repos.listEnabled():
            if repo.gpgcheck and repo.gpgkey == '':
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
                raise cli.CliError

def checkPackageArg(base, basecmd, extcmds):
    if len(extcmds) == 0:
        base.logger.critical(
                _('Error: Need to pass a list of pkgs to %s') % basecmd)
        base.usage()
        raise cli.CliError

def checkItemArg(base, basecmd, extcmds):
    if len(extcmds) == 0:
        base.logger.critical(_('Error: Need an item to match'))
        base.usage()
        raise cli.CliError

def checkGroupArg(base, basecmd, extcmds):
    if len(extcmds) == 0:
        base.logger.critical(_('Error: Need a group or list of groups'))
        base.usage()
        raise cli.CliError    

def checkCleanArg(base, basecmd, extcmds):
    VALID_ARGS = ('headers', 'packages', 'metadata', 'dbcache', 'plugins',
                  'expire-cache', 'all')

    if len(extcmds) == 0:
        base.logger.critical(_('Error: clean requires an option: %s') % (
            ", ".join(VALID_ARGS)))

    for cmd in extcmds:
        if cmd not in VALID_ARGS:
            base.logger.critical(_('Error: invalid clean argument: %r') % cmd)
            base.usage()
            raise cli.CliError

def checkShellArg(base, basecmd, extcmds):
    """
    Verify that the arguments given to 'yum shell' are valid.

    yum shell can be given either no args, or exactly one argument,
    which is the name of a file. If these are not met,
    raise cli.CliError.
    """
    if len(extcmds) == 0:
        base.verbose_logger.debug(_("No argument to shell"))
        pass
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

class YumCommand:
        
    def getNames(self):
        return []

    def getUsage(self):
        """
        @return: A usage string for the command, including arguments.
        """
        raise NotImplementedError

    def getSummary(self):
        """
        @return: A one line summary of what the command does.
        """
        raise NotImplementedError
    
    def doCheck(self, base, basecmd, extcmds):
        pass

    def doCommand(self, base, basecmd, extcmds):
        """
        @return: (exit_code, [ errors ]) where exit_code is:
           0 = we're done, exit
           1 = we've errored, exit with error string
           2 = we've got work yet to do, onto the next stage
        """
        return 0, [_('Nothing to do')]
    
    def needTs(self, base, basecmd, extcmds):
        return True
        
class InstallCommand(YumCommand):
    def getNames(self):
        return ['install']

    def getUsage(self):
        return _("PACKAGE...")

    def getSummary(self):
        return _("Install a package or packages on your system")
    
    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Install Process"))
        try:
            return base.installPkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class UpdateCommand(YumCommand):
    def getNames(self):
        return ['update']

    def getUsage(self):
        return _("[PACKAGE...]")

    def getSummary(self):
        return _("Update a package or packages on your system")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Update Process"))
        try:
            return base.updatePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class InfoCommand(YumCommand):
    def getNames(self):
        return ['info']

    def getUsage(self):
        return "[PACKAGE|all|installed|updates|extras|obsoletes|recent]"

    def getSummary(self):
        return _("Display details about a package or group of packages")

    def doCommand(self, base, basecmd, extcmds):
        try:
            ypl = base.returnPkgLists(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        else:
            rip = base.listPkgs(ypl.installed, _('Installed Packages'), basecmd)
            rap = base.listPkgs(ypl.available, _('Available Packages'), basecmd)
            rep = base.listPkgs(ypl.extras, _('Extra Packages'), basecmd)
            rup = base.listPkgs(ypl.updates, _('Updated Packages'), basecmd)

            # XXX put this into the ListCommand at some point
            if len(ypl.obsoletes) > 0 and basecmd == 'list': 
            # if we've looked up obsolete lists and it's a list request
                rop = [0, '']
                print _('Obsoleting Packages')
                # The tuple is (newPkg, oldPkg) ... so sort by new
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    base.updatesObsoletesList(obtup, 'obsoletes')
            else:
                rop = base.listPkgs(ypl.obsoletes, _('Obsoleting Packages'), basecmd)
            rrap = base.listPkgs(ypl.recent, _('Recently Added Packages'), basecmd)
            # extcmds is pop(0)'d if they pass a "special" param like "updates"
            # in returnPkgLists(). This allows us to always return "ok" for
            # things like "yum list updates".
            if len(extcmds) and \
               rrap[0] and rop[0] and rup[0] and rep[0] and rap[0] and rip[0]:
                return 1, [_('No matching Packages to list')]
            return 0, []

    def needTs(self, base, basecmd, extcmds):
        if len(extcmds) and extcmds[0] == 'installed':
            return False
        
        return True

class ListCommand(InfoCommand):
    def getNames(self):
        return ['list']

    def getSummary(self):
        return _("List a package or groups of packages")


class EraseCommand(YumCommand):
        
    def getNames(self):
        return ['erase', 'remove']

    def getUsage(self):
        return "PACKAGE..."

    def getSummary(self):
        return _("Remove a package or packages from your system")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Remove Process"))
        try:
            return base.erasePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

class GroupCommand(YumCommand):
    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Group Process"))

        base.doRepoSetup(dosack=0)
        try:
            base.doGroupSetup()
        except yum.Errors.GroupsError:
            return 1, [_('No Groups on which to run command')]
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]


class GroupListCommand(GroupCommand):
    def getNames(self):
        return ['grouplist']

    def getUsage(self):
        return ""

    def getSummary(self):
        return _("List available package groups")
    
    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        return base.returnGroupLists(extcmds)

    def needTs(self, base, basecmd, extcmds):
        return False

class GroupInstallCommand(GroupCommand):
    def getNames(self):
        return ['groupinstall', 'groupupdate']

    def getUsage(self):
        return "GROUP..."

    def getSummary(self):
        return _("Install the packages in a group on your system")
    
    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkGroupArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        try:
            return base.installGroups(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class GroupRemoveCommand(GroupCommand):
    def getNames(self):
        return ['groupremove', 'grouperase']

    def getUsage(self):
        return "GROUP..."

    def getSummary(self):
        return _("Remove the packages in a group from your system")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGroupArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        try:
            return base.removeGroups(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

class GroupInfoCommand(GroupCommand):
    def getNames(self):
        return ['groupinfo']

    def getUsage(self):
        return "GROUP..."

    def getSummary(self):
        return _("Display details about a package group")

    def doCheck(self, base, basecmd, extcmds):
        checkGroupArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        try:
            return base.returnGroupInfo(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

class MakeCacheCommand(YumCommand):

    def getNames(self):
        return ['makecache']

    def getUsage(self):
        return ""

    def getSummary(self):
        return _("Generate the metadata cache")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug(_("Making cache files for all metadata files."))
        base.logger.debug(_("This may take a while depending on the speed of this computer"))
        try:
            for repo in base.repos.findRepos('*'):
                repo.metadata_expire = 0
                repo.mdpolicy = "group:all"
            base.doRepoSetup(dosack=0)
            base.repos.doSetup()
            for repo in base.repos.listEnabled():
                repo.repoXML
            
            # These convert the downloaded data into usable data,
            # we can't remove them until *LoadRepo() can do:
            # 1. Download a .sqlite.bz2 and convert to .sqlite
            # 2. Download a .xml.gz and convert to .xml.gz.sqlite
            base.repos.populateSack(mdtype='metadata', cacheonly=1)
            base.repos.populateSack(mdtype='filelists', cacheonly=1)
            base.repos.populateSack(mdtype='otherdata', cacheonly=1)


        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        return 0, [_('Metadata Cache Created')]

    def needTs(self, base, basecmd, extcmds):
        return False

class CleanCommand(YumCommand):
    
    def getNames(self):
        return ['clean']

    def getUsage(self):
        return "[headers|packages|metadata|dbcache|plugins|expire-cache|all]"

    def getSummary(self):
        return _("Remove cached data")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkCleanArg(base, basecmd, extcmds)
        
    def doCommand(self, base, basecmd, extcmds):
        base.conf.cache = 1
        return base.cleanCli(extcmds)

    def needTs(self, base, basecmd, extcmds):
        return False

class ProvidesCommand(YumCommand):
    def getNames(self):
        return ['provides', 'whatprovides']

    def getUsage(self):
        return "SOME_STRING"
    
    def getSummary(self):
        return _("Find what package provides the given value")

    def doCheck(self, base, basecmd, extcmds):
        checkItemArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug("Searching Packages: ")
        try:
            return base.provides(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class CheckUpdateCommand(YumCommand):
    def getNames(self):
        return ['check-update']

    def getUsage(self):
        return "[PACKAGE...]"

    def getSummary(self):
        return _("Check for available package updates")

    def doCommand(self, base, basecmd, extcmds):
        base.extcmds.insert(0, 'updates')
        result = 0
        try:
            ypl = base.returnPkgLists(extcmds)
            if len(ypl.updates) > 0:
                base.listPkgs(ypl.updates, '', outputType='list')
                result = 100
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        else:
            return result, []

class SearchCommand(YumCommand):
    def getNames(self):
        return ['search']

    def getUsage(self):
        return "SOME_STRING"

    def getSummary(self):
        return _("Search package details for the given string")

    def doCheck(self, base, basecmd, extcmds):
        checkItemArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug(_("Searching Packages: "))
        try:
            return base.search(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

class UpgradeCommand(YumCommand):
    def getNames(self):
        return ['upgrade']

    def getUsage(self):
        return 'PACKAGE...'

    def getSummary(self):
        return _("Update packages taking obsoletes into account")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
        base.conf.obsoletes = 1
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Upgrade Process"))
        try:
            return base.updatePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class LocalInstallCommand(YumCommand):
    def getNames(self):
        return ['localinstall', 'localupdate']

    def getUsage(self):
        return "FILE"

    def getSummary(self):
        return _("Install a local RPM")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        
    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2,
                                _("Setting up Local Package Process"))

        updateonly = basecmd == 'localupdate'
        try:
            return base.localInstall(filelist=extcmds, updateonly=updateonly)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

class ResolveDepCommand(YumCommand):
    def getNames(self):
        return ['resolvedep']

    def getUsage(self):
        return "DEPENDENCY"

    def getSummary(self):
        return _("Determine which package provides the given dependency")

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug(_("Searching Packages for Dependency:"))
        try:
            return base.resolveDepCli(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class ShellCommand(YumCommand):
    def getNames(self):
        return ['shell']

    def getUsage(self):
        return "[FILENAME]"

    def getSummary(self):
        return _("Run an interactive yum shell")

    def doCheck(self, base, basecmd, extcmds):
        checkShellArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, _('Setting up Yum Shell'))
        try:
            return base.doShell()
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False


class DepListCommand(YumCommand):
    def getNames(self):
        return ['deplist']

    def getUsage(self):
        return 'PACKAGE...'

    def getSummary(self):
        return _("List a package's dependencies")

    def doCheck(self, base, basecmd, extcmds):
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
       base.verbose_logger.log(logginglevels.INFO_2, _("Finding dependencies: "))
       try:
          return base.deplist(extcmds)
       except yum.Errors.YumBaseError, e:
          return 1, [str(e)]


class RepoListCommand(YumCommand):
    
    def getNames(self):
        return ('repolist',)

    def getUsage(self):
        return '[all|enabled|disabled]'

    def getSummary(self):
        return _('Display the configured software repositories')

    def doCommand(self, base, basecmd, extcmds):
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

        if len(extcmds) >= 1 and extcmds[0] in ('all', 'disabled', 'enabled'):
            arg = extcmds[0]
            extcmds = extcmds[1:]
        else:
            arg = 'enabled'
        extcmds = map(lambda x: x.lower(), extcmds)

        # Setup so len(repo.sack) is correct
        base.repos.populateSack()

        format_string = "%-20.20s %-40.40s %-8s%s"
        repos = base.repos.repos.values()
        repos.sort()
        enabled_repos = base.repos.listEnabled()
        done = False
        verbose = base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if arg == 'all':
            ehibeg = base.term.FG_COLOR['green'] + base.term.MODE['bold']
            dhibeg = base.term.FG_COLOR['red']
            hiend  = base.term.MODE['normal']
        else:
            ehibeg = ''
            dhibeg = ''
            hiend  = ''
        tot_num = 0
        for repo in repos:
            if len(extcmds) and not _repo_match(repo, extcmds):
                continue
            if repo in enabled_repos:
                enabled = True
                ui_enabled = ehibeg + _('enabled') + hiend
                num        = len(repo.sack)
                tot_num   += num
                ui_num     = locale.format("%d", num, True)
                ui_fmt_num = ": %7s"
                if verbose:
                    ui_size = _repo_size(repo)
            else:
                enabled = False
                ui_enabled = dhibeg + _('disabled') + hiend
                ui_num     = ""
                ui_fmt_num = "%s"
                
            if (arg == 'all' or
                (arg == 'enabled' and enabled) or
                (arg == 'disabled' and not enabled)):
                if not done and not verbose:
                    base.verbose_logger.log(logginglevels.INFO_2,
                                            format_string, _('repo id'),
                                            _('repo name'), _('status'), "")
                done = True
                if verbose:
                    out = [base.fmtKeyValFill(_("Repo-id     : "), repo),
                           base.fmtKeyValFill(_("Repo-name   : "), repo.name),
                           base.fmtKeyValFill(_("Repo-status : "), ui_enabled)]
                    if enabled:
                        out += [base.fmtKeyValFill(_("Repo-updated: "),
                                                   time.ctime(repo.repoXML.timestamp)),
                                base.fmtKeyValFill(_("Repo-pkgs   : "), ui_num),
                                base.fmtKeyValFill(_("Repo-size   : "),ui_size)]

                    if repo.baseurl:
                        out += [base.fmtKeyValFill(_("Repo-baseurl: "),
                                                   ", ".join(repo.baseurl))]

                    if repo.mirrorlist:
                        out += [base.fmtKeyValFill(_("Repo-mirrors: "),
                                                   repo.mirrorlist)]

                    if repo.exclude:
                        out += [base.fmtKeyValFill(_("Repo-exclude: "),
                                                   ", ".join(repo.exclude))]

                    if repo.includepkgs:
                        out += [base.fmtKeyValFill(_("Repo-include: "),
                                                   ", ".join(repo.includepkgs))]

                    base.verbose_logger.log(logginglevels.DEBUG_3,
                                            "%s\n",
                                            "\n".join(out))
                else:
                    base.verbose_logger.log(logginglevels.INFO_2, format_string,
                                            repo, repo.name, ui_enabled,
                                            ui_fmt_num % ui_num)

        return 0, ['repolist: ' + locale.format("%d", tot_num, True)]

    def needTs(self, base, basecmd, extcmds):
        return False


class HelpCommand(YumCommand):

    def getNames(self):
        return ['help']

    def getUsage(self):
        return "COMMAND"

    def getSummary(self):
        return _("Display a helpful usage message")

    def doCheck(self, base, basecmd, extcmds):
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
        if base.yum_cli_commands.has_key(extcmds[0]):
            command = base.yum_cli_commands[extcmds[0]]
            base.verbose_logger.log(logginglevels.INFO_2,
                    self._makeOutput(command))
        return 0, []

    def needTs(self, base, basecmd, extcmds):
        return False

class ReInstallCommand(YumCommand):
    def getNames(self):
        return ['reinstall']

    def getUsage(self):
        return "PACKAGE..."

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                _("Setting up Reinstall Process"))
        oldcount = len(base.tsInfo)
        try:
            for item in extcmds:
                base.reinstall(pattern=item)

            if len(base.tsInfo) > oldcount:
                return 2, [_('Package(s) to install')]
            return 0, [_('Nothing to do')]            
            
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def getSummary(self):
        return _("reinstall a package")


    def needTs(self, base, basecmd, extcmds):
        return False
        
