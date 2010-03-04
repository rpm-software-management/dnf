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
            if (repo.gpgcheck or repo.repo_gpgcheck) and repo.gpgkey == '':
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
                  'expire-cache', 'rpmdb', 'all')

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
        
    def __init__(self):
        self.done_command_once = False

    def doneCommand(self, base, msg, *args):
        if not self.done_command_once:
            base.verbose_logger.log(logginglevels.INFO_2, msg, *args)
        self.done_command_once = True

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
        self.doneCommand(base, _("Setting up Install Process"))
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
        self.doneCommand(base, _("Setting up Update Process"))
        try:
            return base.updatePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class DistroSyncCommand(YumCommand):
    def getNames(self):
        return ['distribution-synchronization', 'distro-sync']

    def getUsage(self):
        return _("[PACKAGE...]")

    def getSummary(self):
        return _("Synchronize installed packages to the latest available versions")

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
        self.doneCommand(base, _("Setting up Distribution Synchronization Process"))
        try:
            base.conf.obsoletes = 1
            return base.distroSyncPkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

def _add_pkg_simple_list_lens(data, pkg, indent=''):
    """ Get the length of each pkg's column. Add that to data.
        This "knows" about simpleList and printVer. """
    na  = len(pkg.name)    + 1 + len(pkg.arch)    + len(indent)
    ver = len(pkg.version) + 1 + len(pkg.release)
    rid = len(pkg.ui_from_repo)
    if pkg.epoch != '0':
        ver += len(pkg.epoch) + 1
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
    def getNames(self):
        return ['info']

    def getUsage(self):
        return "[PACKAGE|all|installed|updates|extras|obsoletes|recent]"

    def getSummary(self):
        return _("Display details about a package or group of packages")

    def doCommand(self, base, basecmd, extcmds):
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
                    if key not in inst_pkgs or pkg.verGT(inst_pkgs[key]):
                        inst_pkgs[key] = pkg

            if highlight and ypl.updates:
                # Do the local/remote split we get in "yum updates"
                for po in sorted(ypl.updates):
                    if po.repo.id != 'installed' and po.verifyLocalPkg():
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
                # The tuple is (newPkg, oldPkg) ... so sort by new
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    base.updatesObsoletesList(obtup, 'obsoletes',
                                              columns=columns)
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
        self.doneCommand(base, _("Setting up Remove Process"))
        try:
            return base.erasePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def needTs(self, base, basecmd, extcmds):
        return False

    def needTsRemove(self, base, basecmd, extcmds):
        return True

class GroupCommand(YumCommand):
    def doCommand(self, base, basecmd, extcmds):
        self.doneCommand(base, _("Setting up Group Process"))

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

    def needTsRemove(self, base, basecmd, extcmds):
        return True

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
        pass

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
            if (base.conf.obsoletes or
                base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)):
                typl = base.returnPkgLists(['obsoletes'])
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
        self.doneCommand(base, _("Setting up Upgrade Process"))
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
        self.doneCommand(base, _("Setting up Local Package Process"))

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
        self.doneCommand(base, _('Setting up Yum Shell'))
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
        self.doneCommand(base, _("Finding dependencies: "))
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

            if True: # Here to make patch smaller, TODO: rm
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
                        #  This needs to be here due to the mirrorlists are
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

                    base.verbose_logger.log(logginglevels.DEBUG_3,
                                            "%s\n",
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
                base.verbose_logger.log(logginglevels.INFO_2,"%s %s",
                                        txt_rid, txt_rnam)
            else:
                base.verbose_logger.log(logginglevels.INFO_2,"%s %s %s",
                                        txt_rid, txt_rnam, _('status'))
            for (rid, rname, (ui_enabled, ui_endis_wid), ui_num) in cols:
                if arg == 'disabled': # Don't output a status column.
                    base.verbose_logger.log(logginglevels.INFO_2, "%s %s",
                                            utf8_width_fill(rid, id_len),
                                            utf8_width_fill(rname, nm_len,
                                                            nm_len))
                    continue

                if ui_num:
                    ui_num = utf8_width_fill(ui_num, ui_len, left=False)
                base.verbose_logger.log(logginglevels.INFO_2, "%s %s %s%s",
                                        utf8_width_fill(rid, id_len),
                                        utf8_width_fill(rname, nm_len, nm_len),
                                        ui_enabled, ui_num)

        return 0, ['repolist: ' +to_unicode(locale.format("%d", tot_num, True))]

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
        if extcmds[0] in base.yum_cli_commands:
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
        self.doneCommand(base, _("Setting up Reinstall Process"))
        try:
            return base.reinstallPkgs(extcmds)
            
        except yum.Errors.YumBaseError, e:
            return 1, [to_unicode(e)]

    def getSummary(self):
        return _("reinstall a package")

    def needTs(self, base, basecmd, extcmds):
        return False
        
class DowngradeCommand(YumCommand):
    def getNames(self):
        return ['downgrade']

    def getUsage(self):
        return "PACKAGE..."

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        self.doneCommand(base, _("Setting up Downgrade Process"))
        try:
            return base.downgradePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

    def getSummary(self):
        return _("downgrade a package")

    def needTs(self, base, basecmd, extcmds):
        return False


class VersionCommand(YumCommand):
    def getNames(self):
        return ['version']

    def getUsage(self):
        return "[all|installed|available]"

    def getSummary(self):
        return _("Display a version for the machine and/or available repos.")

    def doCommand(self, base, basecmd, extcmds):
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
                if lastdbv is None or data[0] != lastdbv:
                    base._rpmdb_warn_checks(warn=lastdbv is not None)
                if vcmd not in ('group-installed', 'group-all'):
                    cols.append(("%s %s/%s" % (_("Installed:"), rel, ba),
                                 str(data[0])))
                    _append_repos(cols, data[1])
                if groups:
                    for grp in sorted(data[2]):
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
        vcmd = 'installed'
        if extcmds:
            vcmd = extcmds[0]
        verbose = base.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if vcmd == 'groupinfo' and verbose:
            return True
        return vcmd in ('available', 'all', 'group-available', 'group-all')


class HistoryCommand(YumCommand):
    def getNames(self):
        return ['history']

    def getUsage(self):
        return "[info|list|summary|redo|undo|new]"

    def getSummary(self):
        return _("Display, or use, the transaction history")

    def _hcmd_redo(self, base, extcmds):
        old = base._history_get_transaction(extcmds)
        if old is None:
            return 1, ['Failed history redo']
        tm = time.ctime(old.beg_timestamp)
        print "Repeating transaction %u, from %s" % (old.tid, tm)
        base.historyInfoCmdPkgsAltered(old)
        if base.history_redo(old):
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

    def _hcmd_new(self, base, extcmds):
        base.history._create_db_file()

    def doCheck(self, base, basecmd, extcmds):
        cmds = ('list', 'info', 'summary', 'repeat', 'redo', 'undo', 'new')
        if extcmds and extcmds[0] not in cmds:
            base.logger.critical(_('Invalid history sub-command, use: %s.'),
                                 ", ".join(cmds))
            raise cli.CliError
        if extcmds and extcmds[0] in ('repeat', 'redo', 'undo', 'new'):
            checkRootUID(base)
            checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
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
        elif vcmd == 'undo':
            ret = self._hcmd_undo(base, extcmds)
        elif vcmd in ('redo', 'repeat'):
            ret = self._hcmd_redo(base, extcmds)
        elif vcmd == 'new':
            ret = self._hcmd_new(base, extcmds)

        if ret is None:
            return 0, ['history %s' % (vcmd,)]
        return ret

    def needTs(self, base, basecmd, extcmds):
        vcmd = 'list'
        if extcmds:
            vcmd = extcmds[0]
        return vcmd in ('repeat', 'redo', 'undo')


class CheckRpmdbCommand(YumCommand):
    def getNames(self):
        return ['check', 'check-rpmdb']

    def getUsage(self):
        return "[dependencies|duplicates|all]"

    def getSummary(self):
        return _("Check for problems in the rpmdb")

    def doCommand(self, base, basecmd, extcmds):
        chkcmd = 'all'
        if extcmds:
            chkcmd = extcmds[0]

        def _out(x):
            print x

        rc = 0
        if base._rpmdb_warn_checks(_out, False, chkcmd):
            rc = 1
        return rc, ['%s %s' % (basecmd, chkcmd)]

    def needTs(self, base, basecmd, extcmds):
        return False

