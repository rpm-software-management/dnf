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
import os.path
import sys
import time
import random
import fcntl
import fnmatch
import re
from optparse import OptionParser

import output
import shell
import yum
from yum.constants import *
import yum.Errors
import yum.misc
import rpmUtils.arch
from rpmUtils.miscutils import compareEVR
from yum.packages import parsePackages, YumInstalledPackage, YumLocalPackage
from yum.logger import Logger, SysLogger, LogContainer
from yum import pgpmsg
from i18n import _
import callback
import urlgrabber
import urlgrabber.grabber

class CliError(yum.Errors.YumBaseError):
   def __init__(self, args=''):
        yum.Errors.YumBaseError.__init__(self)
        self.args = args

class YumBaseCli(yum.YumBase, output.YumOutput):
    """This is the base class for yum cli.
       Inherits from yum.YumBase and output.YumOutput """
       
    def __init__(self):
        yum.YumBase.__init__(self)
        self.in_shell = False
        self.yum_cli_commands = ['update', 'install','info', 'list', 'erase',
                                'grouplist', 'groupupdate', 'groupinstall',
                                'groupremove', 'groupinfo', 'makecache',
                                'clean', 'remove', 'provides', 'check-update',
                                'search', 'upgrade', 'whatprovides',
                                'localinstall', 'localupdate',
                                'resolvedep', 'shell', 'deplist']
        
        
    def doRepoSetup(self, thisrepo=None, dosack=1):
        """grabs the repomd.xml for each enabled repository 
           and sets up the basics of the repository"""
        
        if hasattr(self, 'pkgSack') and thisrepo is None:
            self.log(7, 'skipping reposetup, pkgsack exists')
            return
            
        self.log(2, 'Setting up repositories')

        # Call parent class to do the bulk of work 
        # (this also ensures that reposetup plugin hook is called)
        yum.YumBase.doRepoSetup(self, thisrepo=thisrepo)

        if dosack: # so we can make the dirs and grab the repomd.xml but not import the md
            self.log(2, 'Reading repository metadata in from local files')
            self.doSackSetup(thisrepo=thisrepo)
    
        
    def getOptionsConfig(self, args):
        """parses command line arguments, takes cli args:
        sets up self.conf and self.cmds as well as logger objects 
        in base instance"""
        
        # setup our errorlog object 
        self.errorlog = Logger(threshold=2, file_object=sys.stderr)
    
        def repo_optcb(optobj, opt, value, parser):
            '''Callback for the enablerepo and disablerepo option. 
            
            Combines the values given for these options while preserving order
            from command line.
            '''
            dest = eval('parser.values.%s' % optobj.dest)
            dest.append((opt, value))

        self.optparser = YumOptionParser(base=self, usage='''\
yum [options] < update | install | info | remove | list |
    clean | provides | search | check-update | groupinstall | 
    groupupdate | grouplist | groupinfo | groupremove |
    makecache | localinstall | erase | upgrade | whatprovides |
    localupdate | resolvedep | shell | deplist >''')

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
        self.optparser.add_option("", "--exclude", dest="exclude", default=[], 
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
                        ('--noplugins',), 
                        ('-c', '-d', '-e', '--installroot'), 
                        args,
                    )
        except ValueError:
            self.usage()
            sys.exit(1)
        opts = self.optparser.parse_args(args=args)[0]

        try: 
            # If the conf file is inside the  installroot - use that.
            # otherwise look for it in the normal root
            if opts.installroot:
                if os.access(opts.installroot+'/'+opts.conffile, os.R_OK):
                    opts.conffile = opts.installroot+'/'+opts.conffile
                root=opts.installroot
            else:
                root = '/'
                    
            # Parse the configuration file
            try:
                self.doConfigSetup(fn=opts.conffile, root=root)
            except yum.Errors.ConfigError, e:
                self.errorlog(0, _('Config Error: %s') % e)
                sys.exit(1)
                
            # Initialise logger object
            self.log=Logger(threshold=self.conf.debuglevel,
                    file_object=sys.stdout)

            # Setup debug and error levels
            if opts.debuglevel is not None:
                self.log.threshold=opts.debuglevel
                self.conf.debuglevel = opts.debuglevel

            if opts.errorlevel is not None:
                self.errorlog.threshold=opts.errorlevel
                self.conf.errorlevel = opts.errorlevel

        except ValueError, e:
            self.errorlog(0, _('Options Error: %s') % e)
            self.usage()
            sys.exit(1)

        # Initialise plugins if cmd line and config file say these should be in
        # use (this may add extra command line options)
        if not opts.noplugins and self.conf.plugins:
            self.doPluginSetup(self.optparser)

        # Now parse the command line for real
        (opts, self.cmds) = self.optparser.parse_args()

        # Just print out the version if that's what the user wanted
        if opts.version:
            print yum.__version__
            sys.exit(0)

        # Let the plugins know what happened on the command line
        self.plugins.setCmdLine(opts, self.cmds)

        try:
            # config file is parsed and moving us forward
            # set some things in it.
                
            # who are we:
            self.conf.uid = os.geteuid()

            # version of yum
            self.conf.yumversion = yum.__version__
            
            # syslog-style log
            if self.conf.uid == 0:
                logpath = os.path.dirname(self.conf.logfile)
                if not os.path.exists(logpath):
                    try:
                        os.makedirs(logpath, mode=0755)
                    except OSError, e:
                        self.errorlog(0, _('Cannot make directory for logfile %s' % logpath))
                        sys.exit(1)
                try:
                    logfd = os.open(self.conf.logfile, os.O_WRONLY |
                                    os.O_APPEND | os.O_CREAT, 0644)
                except OSError, e:
                    self.errorlog(0, _('Cannot open logfile %s' % self.conf.logfile))
                    sys.exit(1)

                logfile =  os.fdopen(logfd, 'a')
                fcntl.fcntl(logfd, fcntl.F_SETFD)
            
                                      
                filelog_object = Logger(threshold = 10, file_object = logfile, 
                                preprefix = self.printtime)
            else:
                filelog_object = Logger(threshold = 10, file_object = None, 
                                preprefix = self.printtime)

            syslog_object = SysLogger(threshold = 10, 
                                      facility=self.conf.syslog_facility,
                                      ident='yum')
            
            self.filelog = LogContainer([syslog_object, filelog_object])

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
                    self.errorlog(0, _(e))
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
                    self.errorlog(0, _(e))
                    self.usage()
                    sys.exit(1)
                            
        except ValueError, e:
            self.errorlog(0, _('Options Error: %s') % e)
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

        self.log(3, 'Yum Version: %s' % self.conf.yumversion)
        self.log(3, 'COMMAND: %s' % self.cmdstring)
        self.log(3, 'Installroot: %s' % self.conf.installroot)
        if len(self.conf.commands) == 0 and len(self.cmds) < 1:
            self.cmds = self.conf.commands
        else:
            self.conf.commands = self.cmds
        if len(self.cmds) < 1:
            self.errorlog(0, _('You need to give some command'))
            self.usage()
            raise CliError
            
        self.basecmd = self.cmds[0] # our base command
        self.extcmds = self.cmds[1:] # out extended arguments/commands
        
        if len(self.extcmds) > 0:
            self.log(3, 'Ext Commands:\n')
            for arg in self.extcmds:
                self.log(3, '   %s' % arg)
        
        if self.basecmd not in self.yum_cli_commands:
            self.usage()
            raise CliError
    
        if self.conf.uid != 0:
            if self.basecmd in ['install', 'update', 'clean', 'upgrade','erase', 
                                'groupupdate', 'groupinstall', 'remove',
                                'groupremove', 'importkey', 'makecache', 
                                'localinstall', 'localupdate']:
                self.errorlog(0, _('You need to be root to perform this command.'))
                raise CliError

        if self.basecmd in ['install', 'update', 'upgrade', 'groupinstall',
                            'groupupdate', 'localinstall', 'localupdate']:

            if not self.gpgKeyCheck():
                for repo in self.repos.listEnabled():
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
                        self.errorlog(0, msg)
                        raise CliError

                
        if self.basecmd in ['install', 'erase', 'remove', 'localinstall', 'localupdate', 'deplist']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need to pass a list of pkgs to %s') % self.basecmd)
                self.usage()
                raise CliError
    
        elif self.basecmd in ['provides', 'search', 'whatprovides']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need an item to match'))
                self.usage()
                raise CliError
                
        elif self.basecmd in ['groupupdate', 'groupinstall', 'groupremove', 'groupinfo']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need a group or list of groups'))
                self.usage()
                raise CliError
                
        elif self.basecmd == 'clean':
            if len(self.extcmds) == 0:
                self.errorlog(0,
                    _('Error: clean requires an option: headers, packages, cache, metadata, all'))
            for cmd in self.extcmds:
                if cmd not in ['headers', 'packages', 'metadata', 'cache', 'dbcache', 'all']:
                    self.usage()
                    raise CliError
                    
        elif self.basecmd == 'shell':
            if len(self.extcmds) == 0:
                self.log(3, "No argument to shell")
                pass
            elif len(self.extcmds) == 1:
                self.log(3, "Filename passed to shell: %s" % self.extcmds[0])              
                if not os.path.isfile(self.extcmds[0]):
                    self.errorlog(
                        0, _("File: %s given has argument to shell does not exists." % self.extcmds))
                    self.usage()
                    raise CliError
            else:
                self.errorlog(0,_("Error: more than one file given as argument to shell."))
                self.usage()
                raise CliError
              
        elif self.basecmd in ['list', 'check-update', 'info', 'update', 'upgrade',
                              'grouplist', 'makecache', 'resolvedep']:
            pass
    
        else:
            self.usage()
            raise CliError


    def doShell(self):
        """do a shell-like interface for yum commands"""

        self.log(2, 'Setting up Yum Shell')
        self.in_shell = True
        self.doTsSetup()
        self.doRpmDBSetup()
        
        if len(self.extcmds) == 0:
            yumshell = shell.YumShell(base=self)
            yumshell.cmdloop()
        else:
            yumshell = shell.YumShell(base=self)
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
        
        if self.basecmd == 'install':
            self.log(2, "Setting up Install Process")
            try:
                return self.installPkgs()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
        
        elif self.basecmd == 'update':
            self.log(2, "Setting up Update Process")
            try:
                return self.updatePkgs()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]

            
        elif self.basecmd == 'upgrade':
            self.conf.obsoletes = 1
            self.log(2, "Setting up Upgrade Process")
            try:
                return self.updatePkgs()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            
            
        elif self.basecmd in ['erase', 'remove']:
            self.log(2, "Setting up Remove Process")
            try:
                return self.erasePkgs()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            

        elif self.basecmd in ['localinstall', 'localupdate']:
            self.log(2, "Setting up Local Package Process")
            updateonly=0
            if self.basecmd == 'localupdate': updateonly=1
                
            try:
                return self.localInstall(updateonly=updateonly)
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]

            
        elif self.basecmd in ['list', 'info']:
            try:
                ypl = self.returnPkgLists()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            else:
                self.listPkgs(ypl.installed, 'Installed Packages', self.basecmd)
                self.listPkgs(ypl.available, 'Available Packages', self.basecmd)
                self.listPkgs(ypl.extras, 'Extra Packages', self.basecmd)
                self.listPkgs(ypl.updates, 'Updated Packages', self.basecmd)
                if len(ypl.obsoletes) > 0 and self.basecmd == 'list': 
                # if we've looked up obsolete lists and it's a list request
                    print 'Obsoleting Packages'
                    for obtup in ypl.obsoletesTuples:
                        self.updatesObsoletesList(obtup, 'obsoletes')
                else:
                    self.listPkgs(ypl.obsoletes, 'Obsoleting Packages', self.basecmd)
                self.listPkgs(ypl.recent, 'Recently Added Packages', self.basecmd)
                return 0, []

        elif self.basecmd == 'check-update':
            self.extcmds.insert(0, 'updates')
            result = 0
            try:
                ypl = self.returnPkgLists()
                if len(ypl.updates) > 0:
                    self.listPkgs(ypl.updates, '', outputType='list')
                    result = 100
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            else:
                return result, []
            
        elif self.basecmd in ['deplist']:
           self.log(2, "Finding dependencies: ")
           try:
              return self.deplist()
           except yum.Errors.YumBaseError, e:
              return 1, [str(e)]

        elif self.basecmd == 'clean':
            self.conf.cache = 1
            return self.cleanCli()
        
        elif self.basecmd in ['groupupdate', 'groupinstall', 'groupremove', 
                              'grouplist', 'groupinfo']:

            self.log(2, "Setting up Group Process")

            self.doRepoSetup(dosack=0)
            try:
                self.doGroupSetup()
            except yum.Errors.GroupsError:
                return 1, ['No Groups on which to run command']
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            
            if self.basecmd == 'grouplist':
                return self.returnGroupLists()
            
            elif self.basecmd in ['groupinstall', 'groupupdate']:
                try:
                    return self.installGroups()
                except yum.Errors.YumBaseError, e:
                    return 1, [str(e)]
            
            elif self.basecmd == 'groupremove':
                try:
                    return self.removeGroups()
                except yum.Errors.YumBaseError, e:
                    return 1, [str(e)]
            elif self.basecmd == 'groupinfo':
                try:
                    return self.returnGroupInfo()
                except yum.Errors.YumBaseError, e:
                    return 1, [str(e)]
            
        elif self.basecmd in ['search']:
            self.log(2, "Searching Packages: ")
            try:
                return self.search()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
        
        elif self.basecmd in ['provides', 'whatprovides']:
            self.log(2, "Searching Packages: ")
            try:
                return self.provides()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]

        elif self.basecmd in ['resolvedep']:
            self.log(2, "Searching Packages for Dependency:")
            try:
                return self.resolveDepCli()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
        
        elif self.basecmd in ['makecache']:
            self.log(2, "Making cache files for all metadata files.")
            self.log(2, "This may take a while depending on the speed of this computer")
            self.log(3, '%s' % self.pickleRecipe())
            try:
                for repo in self.repos.findRepos('*'):
                    repo.metadata_expire = 0
                self.doRepoSetup(dosack=0)
                self.repos.populateSack(with='metadata', pickleonly=1)
                self.repos.populateSack(with='filelists', pickleonly=1)
                self.repos.populateSack(with='otherdata', pickleonly=1)
                
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            return 0, ['Metadata Cache Created']
            
        else:
            return 1, ['command not implemented/not found']

    def doTransaction(self):
        """takes care of package downloading, checking, user confirmation and actually
           RUNNING the transaction"""

        # output what will be done:
        self.log(1, self.listTransaction())
        
        # Check which packages have to be downloaded
        downloadpkgs = []
        stuff_to_download = False
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                stuff_to_download = True
                po = txmbr.po
                if po:
                    downloadpkgs.append(po)

        # Report the total download size to the user, so he/she can base
        # the answer on this info
        if stuff_to_download:
            self.reportDownloadSize(downloadpkgs)
        
        # confirm with user
        if self._promptWanted():
            if not self.userconfirm():
                self.log(0, 'Exiting on user Command')
                return 1

        self.log(2, 'Downloading Packages:')
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
        
        self.log(2, 'Running Transaction Test')
        tsConf = {}
        for feature in ['diskspacecheck']: # more to come, I'm sure
            tsConf[feature] = getattr(self.conf, feature)
        
        testcb = callback.RPMInstallCallback(output=0)
        testcb.tsInfo = self.tsInfo
        # clean out the ts b/c we have to give it new paths to the rpms 
        del self.ts
        
        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs(keepold=0) # sigh
        tserrors = self.ts.test(testcb, conf=tsConf)
        del testcb
        
        self.log(2, 'Finished Transaction Test')
        if len(tserrors) > 0:
            errstring = 'Transaction Check Error: '
            for descr in tserrors:
                errstring += '  %s\n' % descr 
            
            raise yum.Errors.YumBaseError, errstring
        self.log(2, 'Transaction Test Succeeded')
        del self.ts
        
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
        cb.filelog = self.filelog # needed for log file output
        cb.tsInfo = self.tsInfo

        self.log(2, 'Running Transaction')
        self.runTransaction(cb=cb)

        # close things
        self.log(1, self.postTransactionOutput())
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
                # Key needs to be installed
                self.log(0, errmsg)
    
                # Bail if not -y and stdin isn't a tty as key import will
                # require user confirmation
                if not sys.stdin.isatty() and not \
                            self.conf.assumeyes:
                    raise yum.Errors.YumBaseError, \
                        'Refusing to automatically import keys when running ' \
                        'unattended.\nUse "-y" to override.'

                repo = self.repos.getRepo(po.repoid)
                keyurls = repo.gpgkey
                key_installed = False

                for keyurl in keyurls:
                    self.log(0, 'Retrieving GPG key from %s' % keyurl)

                    # Go get the GPG key from the given URL
                    try:
                        rawkey = urlgrabber.urlread(keyurl, limit=9999)
                    except urlgrabber.grabber.URLGrabError, e:
                        raise yum.Errors.YumBaseError(
                                'GPG key retrieval failed: ' + str(e))

                    # Parse the key
                    try:
                        keyinfo = yum.misc.getgpgkeyinfo(rawkey)
                        keyid = keyinfo['keyid']
                        hexkeyid = yum.misc.keyIdToRPMVer(keyid).upper()
                        timestamp = keyinfo['timestamp']
                        userid = keyinfo['userid']
                    except ValueError, e:
                        raise yum.Errors.YumBaseError, \
                                'GPG key parsing failed: ' + str(e)

                    # Check if key is already installed
                    if yum.misc.keyInstalled(self.read_ts, keyid, timestamp) >= 0:
                        self.log(0, 'GPG key at %s (0x%s) is already installed' % (
                                keyurl,
                                hexkeyid
                                ))
                        continue

                    # Try installing/updating GPG key
                    self.log(0, 'Importing GPG key 0x%s "%s"' % (hexkeyid, userid))
                    if not self.conf.assumeyes:
                        if not self.userconfirm():
                            self.log(0, 'Exiting on user command')
                            return 1
            
                    # Import the key
                    result = self.ts.pgpImportPubkey(yum.misc.procgpgkey(rawkey))
                    if result != 0:
                        raise yum.Errors.YumBaseError, \
                                'Key import failed (code %d)' % result
                    self.log(1, 'Key imported successfully')
                    key_installed = True

                if not key_installed:
                    raise yum.Errors.YumBaseError, \
                        'The GPG keys listed for the "%s" repository are ' \
                        'already installed but they are not correct for this ' \
                        'package.\n' \
                        'Check that the correct key URLs are configured for ' \
                        'this repository.' % (repo.name)

                # Check if the newly installed keys helped
                result, errmsg = self.sigCheckPkg(po)
                if result != 0:
                    self.log(0, "Import of key(s) didn't help, wrong key(s)?")
                    raise yum.Errors.YumBaseError, errmsg

            else:
                # Fatal error
                raise yum.Errors.YumBaseError, errmsg

        return 0

    
    def installPkgs(self, userlist=None):
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
        
        if not userlist:
            userlist = self.extcmds

        self.doRepoSetup()
        self.doRpmDBSetup()
        installed = self.rpmdb.getPkgList()
        avail = self.pkgSack.returnPackages()
        toBeInstalled = {} # keyed on name
        passToUpdate = [] # list of pkgtups to pass along to updatecheck

        self.log(2, _('Parsing package install arguments'))
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
                self.log(3, 'Checking for virtual provide or file-provide for %s' % arg)
                try:
                    mypkg = self.returnPackageByDep(arg)
                except yum.Errors.YumBaseError, e:
                    self.errorlog(0, _('No Match for argument: %s') % arg)
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
                if pkg.pkgtup in installed:
                    self.log(6, 'Package %s is already installed, skipping' % pkg)
                    continue
                
                # everything installed that matches the name
                installedByKey = self.rpmdb.returnTupleByKeyword(name=pkg.name)
                comparable = []
                for instTup in installedByKey:
                    (n2, a2, e2, v2, r2) = instTup
                    if rpmUtils.arch.isMultiLibArch(a2) == rpmUtils.arch.isMultiLibArch(pkg.arch):
                        comparable.append(instTup)
                    else:
                        self.log(6, 'Discarding non-comparable pkg %s.%s' % (n2, a2))
                        continue
                        
                # go through each package 
                if len(comparable) > 0:
                    for instTup in comparable:
                        (n2, a2, e2, v2, r2) = instTup
                        rc = compareEVR((e2, v2, r2), (pkg.epoch, pkg.version, pkg.release))
                        if rc < 0: # we're newer - this is an update, pass to them
                            if n2 in exactarchlist:
                                if pkg.arch == a2:
                                    passToUpdate.append(pkg.pkgtup)
                            else:
                                passToUpdate.append(pkg.pkgtup)
                        elif rc == 0: # same, ignore
                            continue
                        elif rc > 0: # lesser, check if the pkgtup is an exactmatch
                                        # if so then add it to be installed,
                                        # the user explicitly wants this version
                                        # FIXME this is untrue if the exactmatch
                                        # does not include a version-rel section
                            if pkg.pkgtup in exactmatch:
                                if not toBeInstalled.has_key(pkg.name): toBeInstalled[pkg.name] = []
                                toBeInstalled[pkg.name].append(pkg)
                else: # we've not got any installed that match n or n+a
                    self.log(4, 'No other %s installed, adding to list for potential install' % pkg.name)
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
            self.log(3, 'reduced installs :')
        for po in pkglist:
            self.log(3,'   %s.%s %s:%s-%s' % po.pkgtup)
            self.install(po)

        if len(passToUpdate) > 0:
            self.log(3, 'potential updates :')
            updatelist = []
            for (n,a,e,v,r) in passToUpdate:
                self.log(3, '   %s.%s %s:%s-%s' % (n, a, e, v, r))
                pkgstring = '%s:%s-%s-%s.%s' % (e,n,v,r,a)
                updatelist.append(pkgstring)
            self.updatePkgs(userlist=updatelist, quiet=1)

        if len(self.tsInfo) > oldcount:
            return 2, ['Package(s) to install']
        return 0, ['Nothing to do']
        
        
    def updatePkgs(self, userlist=None, quiet=0):
        """take user commands and populate transaction wrapper with 
           packages to be updated"""
        
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting
        
        oldcount = len(self.tsInfo)
        if not userlist:
            userlist = self.extcmds
        self.doRepoSetup()
        avail = self.pkgSack.simplePkgList()
        self.doRpmDBSetup()
        installed = self.rpmdb.getPkgList()
        self.doUpdateSetup()
        updates = self.up.getUpdatesTuples()
        if self.conf.obsoletes:
            obsoletes = self.up.getObsoletesTuples(newest=1)
        else:
            obsoletes = []

        if len(userlist) == 0: # simple case - do them all
            for (obsoleting, installed) in obsoletes:
                obsoleting_pkg = self.getPackageObject(obsoleting)
                installed_pkg =  YumInstalledPackage(self.rpmdb.returnHeaderByTuple(installed)[0])
                self.tsInfo.addObsoleting(obsoleting_pkg, installed_pkg)
                self.tsInfo.addObsoleted(installed_pkg, obsoleting_pkg)
                                
            for (new, old) in updates:
                txmbrs = self.tsInfo.getMembers(pkgtup=old)

                if txmbrs and txmbrs[0].output_state == TS_OBSOLETED: 
                    self.log(5, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s' % old)
                else:
                    updating_pkg = self.getPackageObject(new)
                    updated_pkg = YumInstalledPackage(self.rpmdb.returnHeaderByTuple(old)[0])
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
                    self.errorlog(1, 'Could not find update match for %s' % userarg)

            updateMatches = yum.misc.unique(matched + exactmatch)
            for po in updateMatches:
                for (new, old) in updates:
                    if po.pkgtup == new:
                        updated_pkg = YumInstalledPackage(self.rpmdb.returnHeaderByTuple(old)[0])
                        self.tsInfo.addUpdate(po, updated_pkg)


        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            msg = '%d packages marked for Update/Obsoletion' % change
            return 2, [msg]
        else:
            return 0, ['No Packages marked for Update/Obsoletion']


        
    
    def erasePkgs(self, userlist=None):
        """take user commands and populate a transaction wrapper with packages
           to be erased/removed"""
        
        oldcount = len(self.tsInfo)
        
        if not userlist:
            userlist = self.extcmds
        
        self.doRpmDBSetup()
        installed = []
        for hdr in self.rpmdb.getHdrList():
            po = YumInstalledPackage(hdr)
            installed.append(po)
        
        if len(userlist) > 0: # if it ain't well, that'd be real _bad_ :)
            exactmatch, matched, unmatched = yum.packages.parsePackages(
                                             installed, userlist, casematch=1)
            erases = yum.misc.unique(matched + exactmatch)

        if unmatched:
            for arg in unmatched:
                try:
                    depmatches = self.returnInstalledPackagesByDep(arg)
                except yum.Errors.YumBaseError, e:
                    self.errorlog(0, _('%s') % e)
                    continue
                    
                if not depmatches:
                    self.errorlog(0, _('No Match for argument: %s') % arg)
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
    
    def localInstall(self, filelist=None, updateonly=0):
        """handles installs/updates of rpms provided on the filesystem in a 
           local dir (ie: not from a repo)"""
           
        # read in each package into a YumLocalPackage Object
        # append it to self.localPackages
        # check if it can be installed or updated based on nevra versus rpmdb
        # don't import the repos until we absolutely need them for depsolving
        
        oldcount = len(self.tsInfo)
        
        if not filelist:
            filelist = self.extcmds
        
        if len(filelist) == 0:
            return 0, ['No Packages Provided']
        
        self.doRpmDBSetup()
        installpkgs = []
        updatepkgs = []
        donothingpkgs = []
        
        for pkg in filelist:
            try:
                po = YumLocalPackage(ts=self.read_ts, filename=pkg)
            except yum.Errors.MiscError, e:
                self.errorlog(0, 'Cannot open file: %s. Skipping.' % pkg)
                continue
            self.log(2, 'Examining %s: %s' % (po.localpath, po))

            # everything installed that matches the name
            installedByKey = self.rpmdb.returnTupleByKeyword(name=po.name)
            # go through each package 
            if len(installedByKey) == 0: # nothing installed by that name
                if updateonly:
                    self.errorlog(2, 'Package %s not installed, cannot update it. Run yum install to install it instead.' % po.name)
                else:
                    installpkgs.append(po)
                continue

            for instTup in installedByKey:
                installed_pkg = YumInstalledPackage(self.rpmdb.returnHeaderByTuple(instTup)[0])
                (n, a, e, v, r) = po.pkgtup
                (n2, a2, e2, v2, r2) = installed_pkg.pkgtup
                rc = compareEVR((e2, v2, r2), (e, v, r))
                if rc < 0: # we're newer - this is an update, pass to them
                    if n2 in self.conf.exactarchlist:
                        if a == a2:
                            updatepkgs.append((po, installed_pkg))
                            continue
                        else:
                            donothingpkgs.append(po)
                            continue
                    else:
                        updatepkgs.append((po, installed_pkg))
                        continue
                elif rc == 0: # same, ignore
                    donothingpkgs.append(po)
                    continue
                elif rc > 0: 
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
               self.log(3, 'Excluding %s' % po)
               continue
            
            self.log(2, 'Marking %s to be installed' % po.localpath)
            self.localPackages.append(po)
            self.install(po=po)
        
        for (po, oldpo) in updatepkgs:
            if po in toexc:
               self.log(3, 'Excluding %s' % po)
               continue
           
            self.log(2, 'Marking %s as an update to %s' % (po.localpath, oldpo))
            self.localPackages.append(po)
            self.tsInfo.addUpdate(po, oldpo)
        
        for po in donothingpkgs:
            self.log(2, '%s: does not update installed package.' % po.localpath)

        if len(self.tsInfo) > oldcount:
            return 2, ['Package(s) to install']
        return 0, ['Nothing to do']
        
            
        
        
    def returnPkgLists(self):
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
        if len(self.extcmds) > 0:
            if self.extcmds[0] in special:
                pkgnarrow = self.extcmds.pop(0)
            
        ypl = self.doPackageLists(pkgnarrow=pkgnarrow)
        
        # rework the list output code to know about:
        # obsoletes output
        # the updates format

        def _shrinklist(lst, args):
            if len(lst) > 0 and len(args) > 0:
                self.log(4, 'Matching packages for package list to user args')
                exactmatch, matched, unmatched = yum.packages.parsePackages(lst, args)
                return yum.misc.unique(matched + exactmatch)
            else:
                return lst
        
        ypl.updates = _shrinklist(ypl.updates, self.extcmds)
        ypl.installed = _shrinklist(ypl.installed, self.extcmds)
        ypl.available = _shrinklist(ypl.available, self.extcmds)
        ypl.recent = _shrinklist(ypl.recent, self.extcmds)
        ypl.extras = _shrinklist(ypl.extras, self.extcmds)
        ypl.obsoletes = _shrinklist(ypl.obsoletes, self.extcmds)
        
#        for lst in [ypl.obsoletes, ypl.updates]:
#            if len(lst) > 0 and len(self.extcmds) > 0:
#                self.log(4, 'Matching packages for tupled package list to user args')
#                for (pkg, instpkg) in lst:
#                    exactmatch, matched, unmatched = yum.packages.parsePackages(lst, self.extcmds)
                    
        return ypl

    def search(self, args=None):
        """cli wrapper method for module search function, searches simple
           text tags in a package object"""
        
        # call the yum module search function with lists of tags to search
        # and what to search for
        # display the list of matches
        if not args:
            args = self.extcmds
            
        searchlist = ['name', 'summary', 'description', 'packager', 'group', 'url']
        matching = self.searchGenerator(searchlist, args)
        
        total = 0
        for (po, matched_value) in matching:
            self.matchcallback(po, matched_value)
            total += 1
            
        if total == 0:
            return 0, ['No Matches found']
        return 0, []

    def deplist(self, args=None):
       """cli wrapper method for findDeps method takes a list of packages and 
       returns a formatted deplist for that package"""

       if not args:
          args = self.extcmds

       results = self.findDeps(args)
       self.depListOutput(results)

       return 0, []

    def provides(self, args=None):
        """use the provides methods in the rpmdb and pkgsack to produce a list 
           of items matching the provides strings. This is a cli wrapper to the 
           module"""
        if not args:
            args = self.extcmds
        
        matching = self.searchPackageProvides(args, callback=self.matchcallback)
        
        if len(matching.keys()) == 0:
            return 0, ['No Matches found']
        
        return 0, []
    
    def resolveDepCli(self, args=None):
        """returns a package (one per user arg) that provide the supplied arg"""
        
        if not args:
            args = self.extcmds
        
        for arg in args:
            try:
                pkg = self.returnPackageByDep(arg)
            except yum.Errors.YumBaseError, e:
                self.errorlog(0, _('No Package Found for %s') % arg)
            else:
                msg = '%s:%s-%s-%s.%s' % (pkg.epoch, pkg.name, pkg.version, pkg.release, pkg.arch)
                self.log(0, msg)

        return 0, []
    
    def cleanCli(self, userlist=None):
        if userlist is None:
            userlist = self.extcmds
        hdrcode = pkgcode = xmlcode = piklcode = dbcode = 0
        pkgresults = hdrresults = xmlresults = piklresults = dbresults = []

        if 'all' in self.extcmds:
            self.log(2, 'Cleaning up Everything')
            pkgcode, pkgresults = self.cleanPackages()
            hdrcode, hdrresults = self.cleanHeaders()
            xmlcode, xmlresults = self.cleanMetadata()
            dbcode, dbresults = self.cleanSqlite()
            piklcode, piklresults = self.cleanPickles()
            
            code = hdrcode + pkgcode + xmlcode + piklcode + dbcode
            results = hdrresults + pkgresults + xmlresults + piklresults + dbresults
            for msg in results:
                self.log(2, msg)
            return code, []
            
        if 'headers' in self.extcmds:
            self.log(2, 'Cleaning up Headers')
            hdrcode, hdrresults = self.cleanHeaders()
        if 'packages' in self.extcmds:
            self.log(2, 'Cleaning up Packages')
            pkgcode, pkgresults = self.cleanPackages()
        if 'metadata' in self.extcmds:
            self.log(2, 'Cleaning up xml metadata')
            xmlcode, xmlresults = self.cleanMetadata()
        if 'cache' in self.extcmds:
            self.log(2, 'Cleaning up pickled cache')
            piklcode, piklresults =  self.cleanPickles()
        if 'dbcache' in self.extcmds:
            self.log(2, 'Cleaning up database cache')
            dbcode, dbresults =  self.cleanSqlite()
            
        code = hdrcode + pkgcode + xmlcode + piklcode + dbcode
        results = hdrresults + pkgresults + xmlresults + piklresults + dbresults
        for msg in results:
            self.log(2, msg)
        return code, []

    def returnGroupLists(self, userlist=None):

        uservisible=1
        if userlist is None:
            userlist = self.extcmds
            
        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0

        installed, available = self.doGroupLists(uservisible=uservisible)

        if len(installed) > 0:
            self.log(2, 'Installed Groups:')
            for group in installed:
                self.log(2, '   %s' % group.name)
        
        if len(available) > 0:
            self.log(2, 'Available Groups:')
            for group in available:
                self.log(2, '   %s' % group.name)

            
        return 0, ['Done']
    
    def returnGroupInfo(self, userlist=None):
        """returns complete information on a list of groups"""
        if userlist is None:
            userlist = self.extcmds
        
        for strng in userlist:
            group = self.comps.return_group(strng)
            if group:
                self.displayPkgsInGroups(group)
            else:
                self.errorlog(1, 'Warning: Group %s does not exist.' % strng)
        
        return 0, []
        
    def installGroups(self, grouplist=None):
        """for each group requested do 'selectGroup' on them."""
        
        self.doRepoSetup()
        pkgs_used = []
        
        if grouplist is None:
            grouplist = self.extcmds
        
        for group_string in grouplist:
            group = self.comps.return_group(group_string)
            if not group:
                self.errorlog(0, _('Warning: Group %s does not exist.') % group)
                continue
            
            try:
                txmbrs = self.selectGroup(group.groupid)
            except yum.Errors.GroupsError, e:
                self.errorlog(0, _('Warning: Group %s does not exist.') % group)
                continue
            else:
                pkgs_used.extend(txmbrs)
            
        if not pkgs_used:
            return 0, ['No packages in any requested group available to install or update']
        else:
            return 2, ['%d Package(s) to Install' % len(pkgs_used)]

    def removeGroups(self, grouplist=None):
        """Remove only packages of the named group(s). Do not recurse."""

        pkgs_used = []
        
        if grouplist is None:
            grouplist = self.extcmds
        
        erasesbygroup = []
        for group_string in grouplist:
            try:
                txmbrs = self.groupRemove(group_string)
            except yum.Errors.GroupsError, e:
                self.errorlog(0, 'No group named %s exists' % group_string)
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
        '''Print out command line usage
        '''
        if not self.in_shell:
            print 
            self.optparser.print_help()
        else:
            print 
            self.optparser.print_usage()
            
            
            

class YumOptionParser(OptionParser):
    '''Subclass that makes some minor tweaks to make OptionParser do things the
    "yum way".
    '''

    def __init__(self, base, **kwargs):
        OptionParser.__init__(self, **kwargs)
        self.base = base

    def error(self, msg):
        '''This method is overridden so that error output goes to errorlog
        '''
        self.print_usage()
        self.base.errorlog(0, "Command line error: "+msg)
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
