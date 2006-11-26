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
# Copyright 2005 Duke University 
# Written by Seth Vidal


import os
import sys
import time
import random
import logging
from optparse import OptionParser

import output
import shell
import yum
import yum.Errors
import yum.misc
from yum.constants import TS_OBSOLETED
import rpmUtils.arch
from yum.packages import parsePackages, YumLocalPackage
from yum import logginglevels
from yum import plugins
from i18n import _
import callback
import signal
import yumcommands

def sigquit(signum, frame):
    print >> sys.stderr, "Quit signal sent - exiting immediately"
    sys.exit(1)

class CliError(yum.Errors.YumBaseError):
   def __init__(self, args=''):
        yum.Errors.YumBaseError.__init__(self)
        self.args = args

class YumBaseCli(yum.YumBase, output.YumOutput):
    """This is the base class for yum cli.
       Inherits from yum.YumBase and output.YumOutput """
       
    def __init__(self):
        # handle sigquit early on
        signal.signal(signal.SIGQUIT, sigquit)
        yum.YumBase.__init__(self)
        logging.basicConfig()
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.yum_cli_commands = {}
        self.registerCommand(yumcommands.InstallCommand())
        self.registerCommand(yumcommands.UpdateCommand())
        self.registerCommand(yumcommands.InfoCommand())
        self.registerCommand(yumcommands.EraseCommand())
        self.registerCommand(yumcommands.GroupCommand())
        self.registerCommand(yumcommands.GroupListCommand())
        self.registerCommand(yumcommands.GroupInstallCommand())
        self.registerCommand(yumcommands.GroupRemoveCommand())
        self.registerCommand(yumcommands.GroupInfoCommand())
        self.registerCommand(yumcommands.MakeCacheCommand())
        self.registerCommand(yumcommands.CleanCommand())
        self.registerCommand(yumcommands.ProvidesCommand())
        self.registerCommand(yumcommands.CheckUpdateCommand())
        self.registerCommand(yumcommands.SearchCommand())
        self.registerCommand(yumcommands.UpgradeCommand())
        self.registerCommand(yumcommands.LocalInstallCommand())
        self.registerCommand(yumcommands.ResolveDepCommand())
        self.registerCommand(yumcommands.ShellCommand())
        self.registerCommand(yumcommands.DepListCommand())

    def registerCommand(self, command):
        for name in command.getNames():
            if self.yum_cli_commands.has_key(name):
                raise yum.Errors.ConfigError('Command "%s" already defined' % name)
            self.yum_cli_commands[name] = command
            
    def doRepoSetup(self, thisrepo=None, dosack=1):
        """grabs the repomd.xml for each enabled repository 
           and sets up the basics of the repository"""
        
        if self.pkgSack and thisrepo is None:
            self.verbose_logger.log(logginglevels.DEBUG_4,
                'skipping reposetup, pkgsack exists')
            return
      
        self.verbose_logger.log(logginglevels.INFO_2, 'Setting up repositories')

        # Call parent class to do the bulk of work 
        # (this also ensures that reposetup plugin hook is called)
        yum.YumBase.doRepoSetup(self, thisrepo=thisrepo)

        if dosack: # so we can make the dirs and grab the repomd.xml but not import the md
            self.verbose_logger.log(logginglevels.INFO_2,
                'Reading repository metadata in from local files')
            self.doSackSetup(thisrepo=thisrepo)
    
        
    def getOptionsConfig(self, args):
        """parses command line arguments, takes cli args:
        sets up self.conf and self.cmds as well as logger objects 
        in base instance"""
        
        def repo_optcb(optobj, opt, value, parser):
            '''Callback for the enablerepo and disablerepo option. 
            
            Combines the values given for these options while preserving order
            from command line.
            '''
            dest = eval('parser.values.%s' % optobj.dest)
            dest.append((opt, value))

        self.optparser = YumOptionParser(base=self, 
            usage='yum [options] < %s >' % (', '.join(self.yum_cli_commands)))

        self.optparser.add_option("-t", "--tolerant", dest="tolerant",
                action="store_true", default=False, help="be tolerant of errors")
        self.optparser.add_option("-C", "", dest="cacheonly",
                action="store_true", default=False, 
                help="run entirely from cache, don't update cache")
        self.optparser.add_option("-c", "", dest="conffile", action="store", 
                default='/etc/yum.conf', help="config file location", 
                metavar=' [config file]')
        self.optparser.add_option("-R", "", dest="sleeptime", action="store", 
                type='int', default=None, help="maximum command wait time",
                metavar=' [minutes]')
        self.optparser.add_option("-d", "", dest="debuglevel", action="store", 
                default=None, help="debugging output level", type='int',
                metavar=' [debug level]')
        self.optparser.add_option("-e", "", dest="errorlevel", action="store", 
                default=None, help="error output level", type='int',
                metavar=' [error level]')
        self.optparser.add_option("-y", "", dest="assumeyes",
                action="store_true", default=False, 
                help="answer yes for all questions")
        self.optparser.add_option("", "--version", dest="version",
                default=False, action="store_true", 
                help="show Yum version and exit")
        self.optparser.add_option("", "--installroot", dest="installroot",
                action="store", default=None, help="set install root", 
                metavar='[path]')
        self.optparser.add_option("", "--enablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                help="enable one or more repositories (wildcards allowed)",
                metavar='[repo]')
        self.optparser.add_option("", "--disablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                help="disable one or more repositories (wildcards allowed)",
                metavar='[repo]')
        self.optparser.add_option("-x", "--exclude", dest="exclude", default=[], 
                action="append", help="exclude package(s) by name or glob",
                metavar='[package]')
        self.optparser.add_option("", "--obsoletes", dest="obsoletes",
                default=False, action="store_true", 
                help="enable obsoletes processing during updates")
        self.optparser.add_option("", "--noplugins", dest="noplugins",
                default=False, action="store_true", 
                help="disable Yum plugins")
        
        # Parse only command line options that affect basic yum setup
        try:
            args = _filtercmdline(
                        ('--noplugins','--version'), 
                        ('-c', '-d', '-e', '--installroot'), 
                        args,
                    )
        except ValueError:
            self.usage()
            sys.exit(1)
        opts = self.optparser.parse_args(args=args)[0]

        # Just print out the version if that's what the user wanted
        if opts.version:
            print yum.__version__
            sys.exit(0)

        # If the conf file is inside the  installroot - use that.
        # otherwise look for it in the normal root
        if opts.installroot:
            if os.access(opts.installroot+'/'+opts.conffile, os.R_OK):
                opts.conffile = opts.installroot+'/'+opts.conffile
            root=opts.installroot
        else:
            root = '/'
       
        # Read up configuration options and initialise plugins
        try:
            self.doConfigSetup(opts.conffile, root, 
                    init_plugins=not opts.noplugins,
                    plugin_types=(plugins.TYPE_CORE,plugins.TYPE_INTERACTIVE,),
                    optparser=self.optparser,
                    debuglevel=opts.debuglevel,
                    errorlevel=opts.errorlevel)
        except yum.Errors.ConfigError, e:
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            sys.exit(1)

        # update usage in case plugins have added commands
        self.optparser.set_usage('yum [options] < %s >''' % (
            ', '.join(self.yum_cli_commands)))
        
        # Now parse the command line for real
        (opts, self.cmds) = self.optparser.parse_args()

        # Let the plugins know what happened on the command line
        self.plugins.setCmdLine(opts, self.cmds)

        try:
            # config file is parsed and moving us forward
            # set some things in it.
                
            # version of yum
            self.conf.yumversion = yum.__version__
            
            # Handle remaining options
            if opts.assumeyes:
                self.conf.assumeyes =1

            if opts.cacheonly:
                self.conf.cache = 1

            if opts.sleeptime is not None:
                sleeptime = random.randrange(opts.sleeptime*60)
            else:
                sleeptime = 0

            if opts.obsoletes:
                self.conf.obsoletes = 1

            if opts.installroot:
                self.conf.installroot = opts.installroot

            for exclude in opts.exclude:
                try:
                    excludelist = self.conf.exclude
                    excludelist.append(exclude)
                    self.conf.exclude = excludelist
                except yum.Errors.ConfigError, e:
                    self.logger.critical(e)
                    self.usage()
                    sys.exit(1)
               
            # Process repo enables and disables in order
            for opt, repoexp in opts.repos:
                try:
                    if opt == '--enablerepo':
                        self.repos.enableRepo(repoexp)
                    elif opt == '--disablerepo':
                        self.repos.disableRepo(repoexp)
                except yum.Errors.ConfigError, e:
                    self.logger.critical(e)
                    self.usage()
                    sys.exit(1)
                            
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            self.usage()
            sys.exit(1)
         
        # setup the progress bars/callbacks
        self.setupProgessCallbacks()
        
        # save our original args out
        self.args = args
        # save out as a nice command string
        self.cmdstring = 'yum '
        for arg in self.args:
            self.cmdstring += '%s ' % arg

        try:
            self.parseCommands() # before we return check over the base command + args
                                 # make sure they match/make sense
        except CliError:
            sys.exit(1)
    
        # set our caching mode correctly
        if self.conf.uid != 0:
            self.conf.cache = 1
        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)
        
    def parseCommands(self, mycommands=[]):
        """reads self.cmds and parses them out to make sure that the requested 
        base command + argument makes any sense at all""" 

        self.verbose_logger.debug('Yum Version: %s', self.conf.yumversion)
        self.verbose_logger.debug('COMMAND: %s', self.cmdstring)
        self.verbose_logger.debug('Installroot: %s', self.conf.installroot)
        if len(self.conf.commands) == 0 and len(self.cmds) < 1:
            self.cmds = self.conf.commands
        else:
            self.conf.commands = self.cmds
        if len(self.cmds) < 1:
            self.logger.critical(_('You need to give some command'))
            self.usage()
            raise CliError
            
        self.basecmd = self.cmds[0] # our base command
        self.extcmds = self.cmds[1:] # out extended arguments/commands
        
        if len(self.extcmds) > 0:
            self.verbose_logger.debug('Ext Commands:\n')
            for arg in self.extcmds:
                self.verbose_logger.debug('   %s', arg)
        
        if not self.yum_cli_commands.has_key(self.basecmd):
            self.usage()
            raise CliError
    
        self.yum_cli_commands[self.basecmd].doCheck(self, self.basecmd, self.extcmds)

    def doShell(self):
        """do a shell-like interface for yum commands"""

        self.doRpmDBSetup()
        
        yumshell = shell.YumShell(base=self)
        if len(self.extcmds) == 0:
            yumshell.cmdloop()
        else:
            yumshell.script()
        return yumshell.result, yumshell.resultmsgs

    def doCommands(self):
        """calls the base command passes the extended commands/args out to be
        parsed. (most notably package globs). returns a numeric result code and
        an optional string
           0 = we're done, exit
           1 = we've errored, exit with error string
           2 = we've got work yet to do, onto the next stage"""
        
        # at this point we know the args are valid - we don't know their meaning
        # but we know we're not being sent garbage
        
        # setup our transaction sets (needed globally, here's a good a place as any)
        try:
            self.doTsSetup()
        except yum.Errors.YumBaseError, e:
            return 1, [str(e)]

        return self.yum_cli_commands[self.basecmd].doCommand(self, self.basecmd, self.extcmds)

    def doTransaction(self):
        """takes care of package downloading, checking, user confirmation and actually
           RUNNING the transaction"""

        # output what will be done:
        self.verbose_logger.log(logginglevels.INFO_1, self.listTransaction())
        
        # Check which packages have to be downloaded
        downloadpkgs = []
        stuff_to_download = False
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                stuff_to_download = True
                po = txmbr.po
                if po:
                    downloadpkgs.append(po)

        # Close the connection to the rpmdb so that rpm doesn't hold the SIGINT
        # handler during the downloads. self.ts is reinitialised later in this
        # function anyway (initActionTs). 
        self.ts.close()

        # Report the total download size to the user, so he/she can base
        # the answer on this info
        if stuff_to_download:
            self.reportDownloadSize(downloadpkgs)
        
        # confirm with user
        if self._promptWanted():
            if not self.userconfirm():
                self.verbose_logger.info('Exiting on user Command')
                return 1

        self.verbose_logger.log(logginglevels.INFO_2, 'Downloading Packages:')
        problems = self.downloadPkgs(downloadpkgs) 

        if len(problems.keys()) > 0:
            errstring = ''
            errstring += 'Error Downloading Packages:\n'
            for key in problems.keys():
                errors = yum.misc.unique(problems[key])
                for error in errors:
                    errstring += '  %s: %s\n' % (key, error)
            raise yum.Errors.YumBaseError, errstring

        # Check GPG signatures
        if self.gpgsigcheck(downloadpkgs) != 0:
            return 1
        
        self.verbose_logger.log(logginglevels.INFO_2, 'Running Transaction Test')
        tsConf = {}
        for feature in ['diskspacecheck']: # more to come, I'm sure
            tsConf[feature] = getattr(self.conf, feature)
        
        testcb = callback.RPMInstallCallback(output=0)
        testcb.tsInfo = self.tsInfo
        
        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs(keepold=0) # sigh
        tserrors = self.ts.test(testcb, conf=tsConf)
        del testcb
        
        self.verbose_logger.log(logginglevels.INFO_2, 'Finished Transaction Test')
        if len(tserrors) > 0:
            errstring = 'Transaction Check Error: '
            for descr in tserrors:
                errstring += '  %s\n' % descr 
            
            raise yum.Errors.YumBaseError, errstring
        self.verbose_logger.log(logginglevels.INFO_2, 'Transaction Test Succeeded')
        del self.ts
        
        # unset the sigquit handler
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)
        
        self.initActionTs() # make a new, blank ts to populate
        self.populateTs(keepold=0) # populate the ts
        self.ts.check() #required for ordering
        self.ts.order() # order

        # put back our depcheck callback
        self.dsCallback = dscb

        output = 1
        if self.conf.debuglevel < 2:
            output = 0
        cb = callback.RPMInstallCallback(output=output)
        cb.tsInfo = self.tsInfo

        self.verbose_logger.log(logginglevels.INFO_2, 'Running Transaction')
        self.runTransaction(cb=cb)

        # close things
        self.verbose_logger.log(logginglevels.INFO_1, self.postTransactionOutput())
        
        # put back the sigquit handler
        signal.signal(signal.SIGQUIT, sigquit)
        
        return 0
        
    def gpgsigcheck(self, pkgs):
        '''Perform GPG signature verification on the given packages, installing
        keys if possible

        Returns non-zero if execution should stop (user abort).
        Will raise YumBaseError if there's a problem
        '''
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)

            if result == 0:
                # Verified ok, or verify not req'd
                continue            

            elif result == 1:
               if not sys.stdin.isatty() and not self.conf.assumeyes:
                  raise yum.Errors.YumBaseError, \
                        'Refusing to automatically import keys when running ' \
                        'unattended.\nUse "-y" to override.'

               # the callback here expects to be able to take options which
               # userconfirm really doesn't... so fake it
               self.getKeyForPackage(po, lambda x, y, z: self.userconfirm())

            else:
                # Fatal error
                raise yum.Errors.YumBaseError, errmsg

        return 0

    
    def installPkgs(self, userlist):
        """Attempts to take the user specified list of packages/wildcards
           and install them, or if they are installed, update them to a newer
           version. If a complete version number if specified, attempt to 
           downgrade them to the specified version"""
        # get the list of available packages
        # iterate over the user's list
        # add packages to Transaction holding class if they match.
        # if we've added any packages to the transaction then return 2 and a string
        # if we've hit a snag, return 1 and the failure explanation
        # if we've got nothing to do, return 0 and a 'nothing available to install' string
        
        oldcount = len(self.tsInfo)
        
        self.doRepoSetup()
        self.doRpmDBSetup()
        avail = self.pkgSack.returnPackages()
        toBeInstalled = {} # keyed on name
        passToUpdate = [] # list of pkgtups to pass along to updatecheck

        self.verbose_logger.log(logginglevels.INFO_2,
            _('Parsing package install arguments'))
        for arg in userlist:
            if os.path.exists(arg) and arg.endswith('.rpm'): # this is hurky, deal w/it
                val, msglist = self.localInstall(filelist=[arg])
                continue # it was something on disk and it ended in rpm 
                         # no matter what we don't go looking at repos

            arglist = [arg]
            exactmatch, matched, unmatched = parsePackages(avail, arglist, 
                                                               casematch=1)
            if len(unmatched) > 0: # if we get back anything in unmatched, check it for a virtual-provide
                arg = unmatched[0] #only one in there
                self.verbose_logger.debug('Checking for virtual provide or file-provide for %s', 
                    arg)
                try:
                    mypkg = self.returnPackageByDep(arg)
                except yum.Errors.YumBaseError, e:
                    self.logger.critical(_('No Match for argument: %s') % arg)
                else:
                    arg = '%s:%s-%s-%s.%s' % (mypkg.epoch, mypkg.name,
                                              mypkg.version, mypkg.release,
                                              mypkg.arch)
                    emtch, mtch, unmtch = parsePackages(avail, [arg])
                    exactmatch.extend(emtch)
                    matched.extend(mtch)
            
            installable = yum.misc.unique(exactmatch + matched)
            exactarchlist = self.conf.exactarchlist
            
            # we look through each returned possibility and rule out the
            # ones that we obviously can't use
            for pkg in installable:
                if self.rpmdb.installed(po=pkg):
                    self.verbose_logger.log(logginglevels.DEBUG_3,
                        'Package %s is already installed, skipping', pkg)
                    continue
                
                # everything installed that matches the name
                installedByKey = self.rpmdb.searchNevra(name=pkg.name)
                comparable = []
                for instpo in installedByKey:
                    if rpmUtils.arch.isMultiLibArch(instpo.arch) == rpmUtils.arch.isMultiLibArch(pkg.arch):
                        comparable.append(instpo)
                    else:
                        self.verbose_logger.log(logginglevels.DEBUG_3,
                            'Discarding non-comparable pkg %s.%s', instpo.name, instpo.arch)
                        continue
                        
                # go through each package 
                if len(comparable) > 0:
                    for instpo in comparable:
                        if pkg.EVR > instpo.EVR: # we're newer - this is an update, pass to them
                            if instpo.name in exactarchlist:
                                if pkg.arch == instpo.arch:
                                    passToUpdate.append(pkg.pkgtup)
                            else:
                                passToUpdate.append(pkg.pkgtup)
                        elif pkg.EVR == instpo.EVR: # same, ignore
                            continue
                        elif pkg.EVR < instpo.EVR: # lesser, check if the pkgtup is an exactmatch
                                           # if so then add it to be installed
                                           # if it can be multiply installed
                                           # this is where we could handle setting 
                                           # it to be an 'oldpackage' revert.
                                           
                            if pkg in exactmatch and self.allowedMultipleInstalls(pkg):
                                if not toBeInstalled.has_key(pkg.name): toBeInstalled[pkg.name] = []
                                toBeInstalled[pkg.name].append(pkg)
                else: # we've not got any installed that match n or n+a
                    self.verbose_logger.log(logginglevels.DEBUG_1, 'No other %s installed, adding to list for potential install', pkg.name)
                    if not toBeInstalled.has_key(pkg.name): toBeInstalled[pkg.name] = []
                    toBeInstalled[pkg.name].append(pkg)
        
        
        # this is where I could catch the installs of compat and multilib 
        # arches on a single yum install command. 
        pkglist = []
        for name in toBeInstalled.keys():
            pkglist.extend(self.bestPackagesFromList(toBeInstalled[name]))
            
        # This is where we need to do a lookup to find out if this install
        # is also an obsolete. if so then we need to mark it as such in the
        # tsInfo.
        if len(pkglist) > 0:
            self.verbose_logger.debug('reduced installs :')
        for po in pkglist:
            self.verbose_logger.debug('   %s.%s %s:%s-%s', *po.pkgtup)
            self.install(po)

        if len(passToUpdate) > 0:
            self.verbose_logger.debug('potential updates :')
            updatelist = []
            for (n,a,e,v,r) in passToUpdate:
                self.verbose_logger.debug('   %s.%s %s:%s-%s', n, a, e, v, r)
                pkgstring = '%s:%s-%s-%s.%s' % (e,n,v,r,a)
                updatelist.append(pkgstring)
            self.updatePkgs(userlist=updatelist, quiet=1)

        if len(self.tsInfo) > oldcount:
            return 2, ['Package(s) to install']
        return 0, ['Nothing to do']
        
        
    def updatePkgs(self, userlist, quiet=0):
        """take user commands and populate transaction wrapper with 
           packages to be updated"""
        
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting
        
        oldcount = len(self.tsInfo)
        self.doRepoSetup()
        avail = self.pkgSack.simplePkgList()
        self.doRpmDBSetup()
        installed = self.rpmdb.simplePkgList()
        self.doUpdateSetup()
        updates = self.up.getUpdatesTuples()
        if self.conf.obsoletes:
            obsoletes = self.up.getObsoletesTuples(newest=1)
        else:
            obsoletes = []

        if len(userlist) == 0: # simple case - do them all
            for (obsoleting, installed) in obsoletes:
                obsoleting_pkg = self.getPackageObject(obsoleting)
                installed_pkg =  self.rpmdb.searchPkgTuple(installed)[0]
                self.tsInfo.addObsoleting(obsoleting_pkg, installed_pkg)
                self.tsInfo.addObsoleted(installed_pkg, obsoleting_pkg)
                                
            for (new, old) in updates:
                txmbrs = self.tsInfo.getMembers(pkgtup=old)

                if txmbrs and txmbrs[0].output_state == TS_OBSOLETED: 
                    self.verbose_logger.log(logginglevels.DEBUG_2, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s', old)
                else:
                    updating_pkg = self.getPackageObject(new)
                    updated_pkg = self.rpmdb.searchPkgTuple(old)[0]
                    self.tsInfo.addUpdate(updating_pkg, updated_pkg)


        else:
            # go through the userlist - look for items that are local rpms. If we find them
            # pass them off to localInstall() and then move on
            localupdates = []
            for item in userlist:
                if os.path.exists(item) and item[-4:] == '.rpm': # this is hurky, deal w/it
                    localupdates.append(item)
            
            if len(localupdates) > 0:
                val, msglist = self.localInstall(filelist=localupdates, updateonly=1)
                for item in localupdates:
                    userlist.remove(item)
                
            # we've got a userlist, match it against updates tuples and populate
            # the tsInfo with the matches
            updatesPo = []
            for (new, old) in updates:
                (n,a,e,v,r) = new
                updatesPo.extend(self.pkgSack.searchNevra(name=n, arch=a, epoch=e, 
                                 ver=v, rel=r))
                                 
            exactmatch, matched, unmatched = yum.packages.parsePackages(
                                                updatesPo, userlist, casematch=1)
            for userarg in unmatched:
                if not quiet:
                    self.logger.error('Could not find update match for %s' % userarg)

            updateMatches = yum.misc.unique(matched + exactmatch)
            for po in updateMatches:
                for (new, old) in updates:
                    if po.pkgtup == new:
                        updated_pkg = self.rpmdb.searchPkgTuple(old)[0]
                        self.tsInfo.addUpdate(po, updated_pkg)


        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            msg = '%d packages marked for Update/Obsoletion' % change
            return 2, [msg]
        else:
            return 0, ['No Packages marked for Update/Obsoletion']


        
    
    def erasePkgs(self, userlist):
        """take user commands and populate a transaction wrapper with packages
           to be erased/removed"""
        
        oldcount = len(self.tsInfo)
        
        self.doRpmDBSetup()
        installed = self.rpmdb.returnPackages()
        
        if len(userlist) > 0: # if it ain't well, that'd be real _bad_ :)
            exactmatch, matched, unmatched = yum.packages.parsePackages(
                                             installed, userlist, casematch=1)
            erases = yum.misc.unique(matched + exactmatch)

        if unmatched:
            for arg in unmatched:
                try:
                    depmatches = self.returnInstalledPackagesByDep(arg)
                except yum.Errors.YumBaseError, e:
                    self.logger.critical(_('%s') % e)
                    continue
                    
                if not depmatches:
                    self.logger.critical(_('No Match for argument: %s') % arg)
                else:
                    erases.extend(depmatches)
            
        for pkg in erases:
            self.remove(po=pkg)
        
        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            msg = '%d packages marked for removal' % change
            return 2, [msg]
        else:
            return 0, ['No Packages marked for removal']
    
    def localInstall(self, filelist, updateonly=0):
        """handles installs/updates of rpms provided on the filesystem in a 
           local dir (ie: not from a repo)"""
           
        # read in each package into a YumLocalPackage Object
        # append it to self.localPackages
        # check if it can be installed or updated based on nevra versus rpmdb
        # don't import the repos until we absolutely need them for depsolving
        
        oldcount = len(self.tsInfo)
        
        if len(filelist) == 0:
            return 0, ['No Packages Provided']
        
        self.doRpmDBSetup()
        installpkgs = []
        updatepkgs = []
        donothingpkgs = []
        
        for pkg in filelist:
            try:
                po = YumLocalPackage(ts=self.rpmdb.readOnlyTS(), filename=pkg)
            except yum.Errors.MiscError, e:
                self.logger.critical('Cannot open file: %s. Skipping.', pkg)
                continue
            self.verbose_logger.log(logginglevels.INFO_2, 'Examining %s: %s', 
                po.localpath, po)

            # everything installed that matches the name
            installedByKey = self.rpmdb.searchNevra(name=po.name)
            # go through each package 
            if len(installedByKey) == 0: # nothing installed by that name
                if updateonly:
                    self.logger.warning('Package %s not installed, cannot update it. Run yum install to install it instead.', po.name)
                else:
                    installpkgs.append(po)
                continue

            for installed_pkg in installedByKey:
                if po.EVR > installed_pkg.EVR: # we're newer - this is an update, pass to them
                    if installed_pkg.name in self.conf.exactarchlist:
                        if po.arch == installed_pkg.arch:
                            updatepkgs.append((po, installed_pkg))
                            continue
                        else:
                            donothingpkgs.append(po)
                            continue
                    else:
                        updatepkgs.append((po, installed_pkg))
                        continue
                else:
                    donothingpkgs.append(po)
                    continue

        # handle excludes for a localinstall
        toexc = []
        if len(self.conf.exclude) > 0:
           exactmatch, matched, unmatched = \
                   parsePackages(installpkgs + map(lambda x: x[0], updatepkgs),
                                 self.conf.exclude, casematch=1)
           toexc = exactmatch + matched

        for po in installpkgs:
            if po in toexc:
               self.verbose_logger.debug('Excluding %s', po)
               continue
            
            self.verbose_logger.log(logginglevels.INFO_2, 'Marking %s to be installed',
                po.localpath)
            self.localPackages.append(po)
            self.install(po=po)
        
        for (po, oldpo) in updatepkgs:
            if po in toexc:
               self.verbose_logger.debug('Excluding %s', po)
               continue
           
            self.verbose_logger.log(logginglevels.INFO_2,
                'Marking %s as an update to %s', po.localpath, oldpo)
            self.localPackages.append(po)
            self.tsInfo.addUpdate(po, oldpo)
        
        for po in donothingpkgs:
            self.verbose_logger.log(logginglevels.INFO_2,
                '%s: does not update installed package.', po.localpath)

        if len(self.tsInfo) > oldcount:
            return 2, ['Package(s) to install']
        return 0, ['Nothing to do']
        
            
        
        
    def returnPkgLists(self, extcmds):
        """Returns packages lists based on arguments on the cli.returns a 
           GenericHolder instance with the following lists defined:
           available = list of packageObjects
           installed = list of packageObjects
           updates = tuples of packageObjects (updating, installed)
           extras = list of packageObjects
           obsoletes = tuples of packageObjects (obsoleting, installed)
           recent = list of packageObjects
           """
        
        special = ['available', 'installed', 'all', 'extras', 'updates', 'recent',
                   'obsoletes']
        
        pkgnarrow = 'all'
        if len(extcmds) > 0:
            if extcmds[0] in special:
                pkgnarrow = extcmds.pop(0)
            
        ypl = self.doPackageLists(pkgnarrow=pkgnarrow)
        
        # rework the list output code to know about:
        # obsoletes output
        # the updates format

        def _shrinklist(lst, args):
            if len(lst) > 0 and len(args) > 0:
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    'Matching packages for package list to user args')
                exactmatch, matched, unmatched = yum.packages.parsePackages(lst, args)
                return yum.misc.unique(matched + exactmatch)
            else:
                return lst
        
        ypl.updates = _shrinklist(ypl.updates, extcmds)
        ypl.installed = _shrinklist(ypl.installed, extcmds)
        ypl.available = _shrinklist(ypl.available, extcmds)
        ypl.recent = _shrinklist(ypl.recent, extcmds)
        ypl.extras = _shrinklist(ypl.extras, extcmds)
        ypl.obsoletes = _shrinklist(ypl.obsoletes, extcmds)
        
#        for lst in [ypl.obsoletes, ypl.updates]:
#            if len(lst) > 0 and len(extcmds) > 0:
#                self.logger.log(4, 'Matching packages for tupled package list to user args')
#                for (pkg, instpkg) in lst:
#                    exactmatch, matched, unmatched = yum.packages.parsePackages(lst, extcmds)
                    
        return ypl

    def search(self, args):
        """cli wrapper method for module search function, searches simple
           text tags in a package object"""
        
        # call the yum module search function with lists of tags to search
        # and what to search for
        # display the list of matches
            
        searchlist = ['name', 'summary', 'description', 'packager', 'group', 'url']
        matching = self.searchGenerator(searchlist, args)
        
        total = 0
        for (po, matched_value) in matching:
            self.matchcallback(po, matched_value)
            total += 1
            
        if total == 0:
            return 0, ['No Matches found']
        return 0, matching

    def deplist(self, args):
        """cli wrapper method for findDeps method takes a list of packages and 
            returns a formatted deplist for that package"""
        
        self.doRepoSetup()
        
        
        for arg in args:
            pkgs = []
            pogen = self.pkgSack.matchPackageNames(arg)
            for po in pogen:
                pkgs.append(po)
                
            results = self.findDeps(pkgs)
            self.depListOutput(results)

        return 0, []

    def provides(self, args):
        """use the provides methods in the rpmdb and pkgsack to produce a list 
           of items matching the provides strings. This is a cli wrapper to the 
           module"""
        
        matching = self.searchPackageProvides(args, callback=self.matchcallback)
        
        if len(matching.keys()) == 0:
            return 0, ['No Matches found']
        
        return 0, []
    
    def resolveDepCli(self, args):
        """returns a package (one per user arg) that provide the supplied arg"""
        
        for arg in args:
            try:
                pkg = self.returnPackageByDep(arg)
            except yum.Errors.YumBaseError, e:
                self.logger.critical(_('No Package Found for %s'), arg)
            else:
                msg = '%s:%s-%s-%s.%s' % (pkg.epoch, pkg.name, pkg.version, pkg.release, pkg.arch)
                self.verbose_logger.info(msg)

        return 0, []
    
    def cleanCli(self, userlist):
        hdrcode = pkgcode = xmlcode = dbcode = 0
        pkgresults = hdrresults = xmlresults = dbresults = []

        if 'all' in userlist:
            self.verbose_logger.log(logginglevels.INFO_2, 'Cleaning up Everything')
            pkgcode, pkgresults = self.cleanPackages()
            hdrcode, hdrresults = self.cleanHeaders()
            xmlcode, xmlresults = self.cleanMetadata()
            dbcode, dbresults = self.cleanSqlite()
            self.plugins.run('clean')
            
            code = hdrcode + pkgcode + xmlcode + dbcode
            results = hdrresults + pkgresults + xmlresults + dbresults
            for msg in results:
                self.logger.debug(msg)
            return code, []
            
        if 'headers' in userlist:
            self.logger.debug('Cleaning up Headers')
            hdrcode, hdrresults = self.cleanHeaders()
        if 'packages' in userlist:
            self.logger.debug('Cleaning up Packages')
            pkgcode, pkgresults = self.cleanPackages()
        if 'metadata' in userlist:
            self.logger.debug('Cleaning up xml metadata')
            xmlcode, xmlresults = self.cleanMetadata()
        if 'dbcache' in userlist:
            self.logger.debug('Cleaning up database cache')
            dbcode, dbresults =  self.cleanSqlite()
        if 'plugins' in userlist:
            self.logger.debug('Cleaning up plugins')
            self.plugins.run('clean')

            
        code = hdrcode + pkgcode + xmlcode + dbcode
        results = hdrresults + pkgresults + xmlresults + dbresults
        for msg in results:
            self.verbose_logger.log(logginglevels.INFO_2, msg)
        return code, []

    def returnGroupLists(self, userlist):

        uservisible=1
            
        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0

        installed, available = self.doGroupLists(uservisible=uservisible)

        if len(installed) > 0:
            self.verbose_logger.log(logginglevels.INFO_2, 'Installed Groups:')
            for group in installed:
                self.verbose_logger.log(logginglevels.INFO_2, '   %s',
                    group.name)
        
        if len(available) > 0:
            self.verbose_logger.log(logginglevels.INFO_2, 'Available Groups:')
            for group in available:
                self.verbose_logger.log(logginglevels.INFO_2, '   %s',
                    group.name)

            
        return 0, ['Done']
    
    def returnGroupInfo(self, userlist):
        """returns complete information on a list of groups"""
        for strng in userlist:
            group = self.comps.return_group(strng)
            if group:
                self.displayPkgsInGroups(group)
            else:
                self.logger.error('Warning: Group %s does not exist.', strng)
        
        return 0, []
        
    def installGroups(self, grouplist):
        """for each group requested do 'selectGroup' on them."""
        
        self.doRepoSetup()
        pkgs_used = []
        
        for group_string in grouplist:
            group = self.comps.return_group(group_string)
            if not group:
                self.logger.critical(_('Warning: Group %s does not exist.'), group_string)
                continue
            
            try:
                txmbrs = self.selectGroup(group.groupid)
            except yum.Errors.GroupsError, e:
                self.logger.critical(_('Warning: Group %s does not exist.'), group_string)
                continue
            else:
                pkgs_used.extend(txmbrs)
            
        if not pkgs_used:
            return 0, ['No packages in any requested group available to install or update']
        else:
            return 2, ['%d Package(s) to Install' % len(pkgs_used)]

    def removeGroups(self, grouplist):
        """Remove only packages of the named group(s). Do not recurse."""

        pkgs_used = []
        
        erasesbygroup = []
        for group_string in grouplist:
            try:
                txmbrs = self.groupRemove(group_string)
            except yum.Errors.GroupsError, e:
                self.logger.critical('No group named %s exists', group_string)
                continue
            else:
                pkgs_used.extend(txmbrs)
                
        if not pkgs_used:
            return 0, ['No packages to remove from groups']
        else:
            return 2, ['%d Package(s) to remove' % len(pkgs_used)]



    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes:
            return False
        if self.conf.alwaysprompt:
            return True
        
        # prompt if:
        #  package was added to fill a dependency
        #  package is being removed
        #  package wasn't explictly given on the command line
        for txmbr in self.tsInfo.getMembers():
            if txmbr.isDep or \
                   txmbr.ts_state == 'e' or \
                   txmbr.name not in self.extcmds:
                return True
        
        # otherwise, don't prompt        
        return False

    def usage(self):
        ''' Print out command line usage '''
        print self.optparser.print_help()

    def shellUsage(self):
        ''' Print out the shell usage '''
        print self.optparser.print_usage()
            
            

class YumOptionParser(OptionParser):
    '''Subclass that makes some minor tweaks to make OptionParser do things the
    "yum way".
    '''

    def __init__(self, base, **kwargs):
        OptionParser.__init__(self, **kwargs)
        self.logger = logging.getLogger("yum.cli")

    def error(self, msg):
        '''This method is overridden so that error output goes to logger. '''
        self.print_usage()
        self.logger.critical("Command line error: %s", msg)
        sys.exit(1)


        
def _filtercmdline(novalopts, valopts, args):
    '''Keep only specific options from the command line argument list

    This function allows us to peek at specific command line options when using
    the optparse module. This is useful when some options affect what other
    options should be available.

    @param novalopts: A sequence of options to keep that don't take an argument.
    @param valopts: A sequence of options to keep that take a single argument.
    @param args: The command line arguments to parse (as per sys.argv[:1]
    @return: A list of strings containing the filtered version of args.

    Will raise ValueError if there was a problem parsing the command line.
    '''
    out = []
    args = list(args)       # Make a copy because this func is destructive

    while len(args) > 0:
        a = args.pop(0)
        if '=' in a:
            opt, _ = a.split('=', 1)
            if opt in valopts:
                out.append(a)

        elif a in novalopts:
            out.append(a)

        elif a in valopts:
            if len(args) < 1:
                raise ValueError
            next = args.pop(0)
            if next.startswith('-'):
                raise ValueError

            out.extend([a, next])
       
        else:
            # Check for single letter options that take a value, where the
            # value is right up against the option
            for opt in valopts:
                if len(opt) == 2 and a.startswith(opt):
                    out.append(a)

    return out
