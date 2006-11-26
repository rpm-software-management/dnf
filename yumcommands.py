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

import os
import cli
from yum import logginglevels
import yum.Errors
from i18n import _

def checkRootUID(base):
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
            'all')

    if len(extcmds) == 0:
        base.logger.critical(_('Error: clean requires an option: %s') % (
            ", ".join(VALID_ARGS)))

    for cmd in extcmds:
        if cmd not in VALID_ARGS:
            base.logger.critical(_('Error: invalid clean argument: %r') % cmd)
            base.usage()
            raise cli.CliError

def checkShellArg(base, basecmd, extcmds):
    if len(extcmds) == 0:
        base.verbose_logger.debug("No argument to shell")
        pass
    elif len(extcmds) == 1:
        base.verbose_logger.debug("Filename passed to shell: %s", 
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
        return ''
    
    def doCheck(self, base, basecmd, extcmds):
        pass

    def doCommand(self, base, basecmd, extcmds):
        """
        @return: (exit_code, [ errors ]) where exit_code is:
           0 = we're done, exit
           1 = we've errored, exit with error string
           2 = we've got work yet to do, onto the next stage
        """
        return 0, ['Nothing to do']

class InstallCommand(YumCommand):
    def getNames(self):
        return ['install']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                "Setting up Install Process")
        try:
            return base.installPkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class UpdateCommand(YumCommand):
    def getNames(self):
        return ['update']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                "Setting up Update Process")
        try:
            return base.updatePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class InfoCommand(YumCommand):
    def getNames(self):
        return ['info', 'list']

    def doCommand(self, base, basecmd, extcmds):
        try:
            ypl = base.returnPkgLists(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        else:
            base.listPkgs(ypl.installed, 'Installed Packages', basecmd)
            base.listPkgs(ypl.available, 'Available Packages', basecmd)
            base.listPkgs(ypl.extras, 'Extra Packages', basecmd)
            base.listPkgs(ypl.updates, 'Updated Packages', basecmd)
            if len(ypl.obsoletes) > 0 and basecmd == 'list': 
            # if we've looked up obsolete lists and it's a list request
                print 'Obsoleting Packages'
                for obtup in ypl.obsoletesTuples:
                    base.updatesObsoletesList(obtup, 'obsoletes')
            else:
                base.listPkgs(ypl.obsoletes, 'Obsoleting Packages', basecmd)
            base.listPkgs(ypl.recent, 'Recently Added Packages', basecmd)
            return 0, []

class EraseCommand(YumCommand):
    def getNames(self):
        return ['erase', 'remove']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                "Setting up Remove Process")
        try:
            return base.erasePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class GroupCommand(YumCommand):
    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 
                "Setting up Group Process")

        base.doRepoSetup(dosack=0)
        try:
            base.doGroupSetup()
        except yum.Errors.GroupsError:
            return 1, ['No Groups on which to run command']
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]


class GroupListCommand(GroupCommand):
    def getNames(self):
        return ['grouplist']

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        return base.returnGroupLists(extcmds)

class GroupInstallCommand(GroupCommand):
    def getNames(self):
        return ['groupinstall', 'groupupdate']

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

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGroupArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        try:
            return base.removeGroups(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class GroupInfoCommand(GroupCommand):
    def getNames(self):
        return ['groupinfo']

    def doCheck(self, base, basecmd, extcmds):
        checkGroupArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        GroupCommand.doCommand(self, base, basecmd, extcmds)
        try:
            return base.returnGroupInfo(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class MakeCacheCommand(YumCommand):
    def getNames(self):
        return ['makecache']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug("Making cache files for all metadata files.")
        base.logger.debug("This may take a while depending on the speed of this computer")
        try:
            for repo in base.repos.findRepos('*'):
                repo.metadata_expire = 0
            base.doRepoSetup(dosack=0)
            base.repos.populateSack(with='metadata', cacheonly=1)
            base.repos.populateSack(with='filelists', cacheonly=1)
            base.repos.populateSack(with='otherdata', cacheonly=1)

        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]
        return 0, ['Metadata Cache Created']

class CleanCommand(YumCommand):
    def getNames(self):
        return ['clean']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkCleanArg(base, basecmd, extcmds)
        
    def doCommand(self, base, basecmd, extcmds):
        base.conf.cache = 1
        return base.cleanCli(extcmds)

class ProvidesCommand(YumCommand):
    def getNames(self):
        return ['provides', 'whatprovides']

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

    def doCheck(self, base, basecmd, extcmds):
        checkItemArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug("Searching Packages: ")
        try:
            return base.search(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class UpgradeCommand(YumCommand):
    def getNames(self):
        return ['upgrade']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)

    def doCommand(self, base, basecmd, extcmds):
        base.conf.obsoletes = 1
        base.verbose_logger.log(logginglevels.INFO_2, 
                "Setting up Upgrade Process")
        try:
            return base.updatePkgs(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class LocalInstallCommand(YumCommand):
    def getNames(self):
        return ['localinstall', 'localupdate']

    def doCheck(self, base, basecmd, extcmds):
        checkRootUID(base)
        checkGPGKey(base)
        checkPackageArg(base, basecmd, extcmds)
        
    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2,
                                "Setting up Local Package Process")

        updateonly = basecmd == 'localupdate'
        try:
            return base.localInstall(filelist=extcmds, updateonly=updateonly)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class ResolveDepCommand(YumCommand):
    def getNames(self):
        return ['resolvedep']

    def doCommand(self, base, basecmd, extcmds):
        base.logger.debug("Searching Packages for Dependency:")
        try:
            return base.resolveDepCli(extcmds)
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

class ShellCommand(YumCommand):
    def getNames(self):
        return ['shell']

    def doCheck(self, base, basecmd, extcmds):
        checkShellArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
        base.verbose_logger.log(logginglevels.INFO_2, 'Setting up Yum Shell')
        try:
            return base.doShell()
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]


class DepListCommand(YumCommand):
    def getNames(self):
        return ['deplist']

    def doCheck(self, base, basecmd, extcmds):
        checkPackageArg(base, basecmd, extcmds)

    def doCommand(self, base, basecmd, extcmds):
       base.verbose_logger.log(logginglevels.INFO_2, "Finding dependencies: ")
       try:
          return base.deplist(extcmds)
       except yum.Errors.YumBaseError, e:
          return 1, [str(e)]


