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
# Copyright 2004 Duke University 

import os
import sys
import time
import getopt
import random
import fcntl
import fnmatch
import re
import output

from urlgrabber.progress import TextMeter
import yum
import yum.Errors
import yum.misc
from rpmUtils.miscutils import compareEVR
from yum.packages import parsePackages, returnBestPackages, YumInstalledPackage
from yum.logger import Logger
from yum.config import yumconf
from i18n import _
import callback


__version__ = '2.1.3'


class YumBaseCli(yum.YumBase, output.YumOutput):
    """This is the base class for yum cli.
       Inherits from yum.YumBase and output.YumOutput """
       
    def __init__(self):
        yum.YumBase.__init__(self)
        
    def doRepoSetup(self):
        """grabs the repomd.xml for each enabled repository and sets up the basics
           of the repository"""
           
        for repo in self.repos.listEnabled():
            self.log(2, 'Setting up Repo:  %s' % repo)
            try:
                repo.cache = self.conf.getConfigOption('cache')
                repo.dirSetup()
                self.log(3, 'Baseurl(s) for repo: %s' % repo.urls)
            except yum.Errors.RepoError, e:
                self.errorlog(0, '%s' % e)
                sys.exit(1)
            try:
                repo.getRepoXML()
            except yum.Errors.RepoError, e:
                self.errorlog(0, 'Cannot open/read repomd.xml file for repository: %s' % repo)
                self.errorlog(0, str(e))
                sys.exit(1)
        self.log(2, 'Reading repository metadata in from local files')
        self.doSackSetup()
    
        
    def getOptionsConfig(self, args):
        """parses command line arguments, takes cli args:
        sets up self.conf and self.cmds as well as logger objects 
        in base instance"""
        
        # setup our errorlog object 
        self.errorlog = Logger(threshold=2, file_object=sys.stderr)
    
        # our default config file location
        yumconffile = None
        if os.access("/etc/yum.conf", os.R_OK):
            yumconffile = "/etc/yum.conf"
    
        try:
            gopts, self.cmds = getopt.getopt(args, 'tCc:hR:e:d:y', ['help',
                                                            'version',
                                                            'installroot=',
                                                            'enablerepo=',
                                                            'disablerepo=',
                                                            'exclude=',
                                                            'obsoletes',
                                                            'download-only',
                                                            'rss-filename=',
                                                            'tolerant'])
        except getopt.error, e:
            self.errorlog(0, _('Options Error: %s') % e)
            self.usage()
    
        # get the early options out of the way
        # these are ones that:
        #  - we need to know about and do NOW
        #  - answering quicker is better
        #  - give us info for parsing the others
        
        # our sleep variable for the random start time
        sleeptime=0
        root = '/'
        
        try: 
            for o,a in gopts:
                if o == '--version':
                    print __version__
                    sys.exit(0)
                if o == '--installroot':
                    root = a
                    if os.access(a + "/etc/yum.conf", os.R_OK):
                        yumconffile = a + '/etc/yum.conf'
                if o == '-c':
                    yumconffile = a
    
            if yumconffile:
                try:
                    self.conf = yumconf(configfile = yumconffile, root=root)
                except yum.Errors.ConfigError, e:
                    self.errorlog(0, _('Config Error: %s.') % e)
                    sys.exit(1)
            else:
                self.errorlog(0, _('Cannot find any conf file.'))
                sys.exit(1)
                
            # config file is parsed and moving us forward
            # set some things in it.
                
            # who are we:
            self.conf.setConfigOption('uid', os.geteuid())

            # version of yum
            self.conf.setConfigOption('yumversion', __version__)
            
            
            # we'd like to have a log object now
            self.log=Logger(threshold=self.conf.getConfigOption('debuglevel'), file_object = 
                                                                        sys.stdout)
            
            # syslog-style log
            if self.conf.getConfigOption('uid') == 0:
                logfd = os.open(self.conf.getConfigOption('logfile'), os.O_WRONLY |
                                os.O_APPEND | os.O_CREAT)
                logfile =  os.fdopen(logfd, 'a')
                fcntl.fcntl(logfd, fcntl.F_SETFD)
                self.filelog = Logger(threshold = 10, file_object = logfile, 
                                preprefix = self.printtime())
            else:
                self.filelog = Logger(threshold = 10, file_object = None, 
                                preprefix = self.printtime())
            
        
            # now the rest of the options
            for o,a in gopts:
                if o == '-d':
                    self.log.threshold=int(a)
                    self.conf.setConfigOption('debuglevel', int(a))
                elif o == '-e':
                    self.errorlog.threshold=int(a)
                    self.conf.setConfigOption('errorlevel', int(a))
                elif o == '-y':
                    self.conf.setConfigOption('assumeyes',1)
                elif o in ['-h', '--help']:
                    self.usage()
                elif o == '-C':
                    self.conf.setConfigOption('cache', 1)
                elif o == '-R':
                    sleeptime = random.randrange(int(a)*60)
                elif o == '--obsoletes':
                    self.conf.setConfigOption('obsoletes', 1)
                elif o == '--installroot':
                    self.conf.setConfigOption('installroot', a)
                elif o == '--rss-filename':
                    self.conf.setConfigOption('rss-filename', a)
                elif o == '--enablerepo':
                    try:
                        self.conf.repos.enableRepo(a)
                    except yum.Errors.ConfigError, e:
                        self.errorlog(0, _(e))
                        self.usage()
                elif o == '--disablerepo':
                    try:
                        self.conf.repos.disableRepo(a)
                    except yum.Errors.ConfigError, e:
                        self.errorlog(0, _(e))
                        self.usage()
                        
                elif o == '--exclude':
                    try:
                        excludelist = self.conf.getConfigOption('exclude')
                        excludelist.append(a)
                        self.conf.setConfigOption('exclude', excludelist)
                    except yum.Errors.ConfigError, e:
                        self.errorlog(0, _(e))
                        self.usage()
                
                            
        except ValueError, e:
            self.errorlog(0, _('Options Error: %s') % e)
            self.usage()
        
        # if we're below 2 on the debug level we don't need to be outputting
        # progress bars - this is hacky - I'm open to other options
        # One of these is a download
        if self.conf.getConfigOption('debuglevel') < 2 or not sys.stdout.isatty():
            self.conf.repos.setProgressBar(None)
            self.conf.repos.callback = None
        else:
            self.conf.repos.setProgressBar(TextMeter(fo=sys.stdout))
            self.conf.repos.callback = self.simpleProgressBar

        # setup our failure report for failover
        freport = (self.failureReport,(),{'errorlog':self.errorlog})
        self.conf.repos.setFailureCallback(freport)
        
        # this is just a convenience reference
        self.repos = self.conf.repos
        
        # save our original args out
        self.args = args
        # save out as a nice command string
        self.cmdstring = 'yum '
        for arg in self.args:
            self.cmdstring += '%s ' % arg

        self.parseCommands() # before we exit check over the base command + args
                             # make sure they match
    
        # set our caching mode correctly
        
        if self.conf.getConfigOption('uid') != 0:
            self.conf.setConfigOption('cache', 1)
        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)


    def parseCommands(self):
        """reads self.cmds and parses them out to make sure that the requested 
        base command + argument makes any sense at all""" 

        self.log(3, 'Yum Version: %s' % self.conf.getConfigOption('yumversion'))
        self.log(3, 'COMMAND: %s' % self.cmdstring)
        self.log(3, 'Installroot: %s' % self.conf.getConfigOption('installroot'))
        
        
        if len(self.conf.getConfigOption('commands')) == 0 and len(self.cmds) < 1:
            self.cmds = self.conf.getConfigOption('commands')
        else:
            self.conf.setConfigOption('commands', self.cmds)
        if len(self.cmds) < 1:
            self.errorlog(0, _('You need to give some command'))
            self.usage()

        self.basecmd = self.cmds[0] # our base command
        self.extcmds = self.cmds[1:] # out extended arguments/commands
        
        if self.basecmd not in ['update', 'install','info', 'list', 'erase',\
                                'grouplist', 'groupupdate', 'groupinstall',\
                                'clean', 'remove', 'provides', 'check-update',\
                                'search', 'generate-rss', 'upgrade']:
            self.usage()
            
    
        if self.conf.getConfigOption('uid') != 0:
            if self.basecmd in ['install', 'update', 'clean', 'upgrade','erase', 
                                'groupupdate', 'groupinstall', 'remove',
                                'groupremove', 'importkey']:
                self.errorlog(0, _('You need to be root to perform these commands'))
                sys.exit(1)
        
        if self.basecmd in ['install', 'erase', 'remove']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need to pass a list of pkgs to %s') % self.basecmd)
                self.usage()
    
        elif self.basecmd in ['provides', 'search']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need an item to match'))
                self.usage()
            
        elif self.basecmd in ['groupupdate', 'groupinstall', 'groupremove']:
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Need a group or list of groups'))
                self.usage()
    
        elif self.basecmd == 'clean':
            if len(self.extcmds) == 0:
                self.errorlog(0, _('Error: Clean Now Requires an option'))
            for cmd in self.extcmds:
                if cmd not in ['headers', 'packages', 'all']:
                    self.usage()
    
        elif self.basecmd in ['list', 'check-update', 'info', 'update', 
                              'generate-rss', 'grouplist']:
            pass
    
        else:
            self.usage()

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
            return self.installPkgs()
        
        elif self.basecmd == 'update':
            self.log(2, "Setting up Update Process")
            return self.updatePkgs()
            
        elif self.basecmd == 'upgrade':
            self.conf.setConfigOption('obsoletes', 1)
            self.log(2, "Setting up Update Process")
            return self.updatePkgs()
            
        elif self.basecmd in ['erase', 'remove']:
            self.log(2, "Setting up Remove Process")
            return self.erasePkgs()
    
        elif self.basecmd in ['list', 'info']:
            try:
                pkgLists = self.genPkgLists()
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            else:
                self.listPkgs(pkgLists, outputType=self.basecmd)
                return 0, []

        elif self.basecmd == 'check-update':
            self.extcmds.insert(0, 'updates')
            result = 0
            try:
                pkgLists = self.genPkgLists()
                if len(pkgLists['Updated']) > 0:
                    self.listPkgs(pkgLists, outputType='list')
                    result = 100
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            else:
                return result, []
            
            
        elif self.basecmd == 'generate-rss':
            self.log(2, 'Generating RSS File')
            self.extcmds.insert(0, 'recent')
            try:
                pkgLists = self.genPkgLists()
                if len(pkgLists['Recently available']) > 0:
                    needrepos = []
                    
                    for po in pkgLists['Recently available']:
                        if po.repoid not in needrepos:
                            needrepos.append(po.repoid)

                    self.log(2, 'Importing Changelog Metadata')
                    self.repos.populateSack(with='other', which=needrepos)
                    self.listPkgs(pkgLists, outputType='rss',)
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
            else:
                return 0, []
                
        elif self.basecmd == 'clean':
            self.conf.setConfigOption('cache', 1)
            hdrcode = 0
            pkgcode = 0
            pkgresults = []
            hdrresults = []
            if 'all' in self.extcmds:
                self.log(2, 'Cleaning up Packages and Headers')
                pkgcode, pkgresults = self.cleanPackages()
                hdrcode, hdrresults = self.cleanHeaders()
                code = hdrcode + pkgcode
                results = hdrresults + pkgresults
                return code, results
            if 'headers' in self.extcmds:
                self.log(2, 'Cleaning up Headers')
                hdrcode, hdrresults = self.cleanHeaders()
            if 'packages' in self.extcmds:
                self.log(2, 'Cleaning up Packages')
                pkgcode, pkgresults = self.cleanPackages()
            
            code = hdrcode + pkgcode
            results = hdrresults + pkgresults
            return code, results
            
        
        elif self.basecmd in ['groupupdate', 'groupinstall', 'groupremove', 
                              'grouplist']:
            self.doRepoSetup()
            self.doRpmDBSetup()
            try:
                self.doGroupSetup()
            except yum.Errors.GroupsError:
                return 1, ['No Groups on which to run command']
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]
                
            if self.basecmd == 'grouplist':
                self.groupInfo._dumppkgs()
                return 0, []
        else:
            return 1, ['command not implemented yet']

    def doTransaction(self):
        """takes care of package downloading, checking, user confirmation and actually
           RUNNING the transaction"""

        # output what will be done:
        self.log(2, self.tsInfo.display())
        # confirm with user
        if not self.conf.getConfigOption('assumeyes'):
            if not self.userconfirm():
                self.log(0, 'Exiting on user Command')
                return

        
        # download all pkgs in the tsInfo - md5sum vs the metadata as you go 
        downloadpkgs = []
        for (pkg, mode) in self.tsInfo.dump():
            if mode in ['i', 'u']:
                po = self.getPackageObject(pkg)
                if po:
                    downloadpkgs.append(po)
        problems = self.downloadPkgs(downloadpkgs) 

        if len(problems.keys()) > 0:
            errstring = ''
            errstring += 'Error Downloading Packages:\n'
            for key in problems.keys():
                errors = yum.misc.unique(problems[key])
                for error in errors:
                    errstring += '  %s: %s\n' % (key, error)
            raise yum.Errors.YumBaseError, errstring

        # gpgcheck in a big pile, report all errors at once
        problems = self.sigCheckPkgs(downloadpkgs)
        
        if len(problems) > 0:
            errstring = ''
            for problem in problems:
                errstring += problem
            
            raise yum.Errors.YumBaseError, errstring
        
        self.log(2, 'Running Transaction Test')
        tsConf = {}
        for feature in ['diskspacecheck']: # more to come, I'm sure
            tsConf['diskspacecheck'] = self.conf.getConfigOption('diskspacecheck')
        
        testcb = callback.RPMInstallCallback()
        # clean out the ts b/c we have to give it new paths to the rpms 
        del self.ts
        self.initActionTs()
        self.populateTs(keepold=0) # sigh
        tserrors = self.ts.test(testcb, conf=tsConf)
        del testcb
        self.log(2, 'Finished Transaction Test')
        if len(tserrors) > 0:
            errstring = 'Transaction Check Error: '
            for (descr, (etype, mount, need)) in tserrors:
                errstring += '  %s\n' % descr 
            
            raise yum.Errors.YumBaseError, errstring
        self.log(2, 'Transaction Test Succeeded')
        del self.ts
        
        self.initActionTs() # make a new, blank ts to populate
        self.populateTs(keepold=0) # populate the ts
        self.ts.check() #required for ordering
        self.ts.order() # order
        self.ts.setFlags(0) # unset the test flag
        cb = callback.RPMInstallCallback()
        # run ts
        self.log(2, 'Running Transaction')
        
        errors = self.ts.run(cb.callback, '')
        if errors:
            errstring = 'Error in Transaction: '
            for (descr, (etype, mount, need)) in errors:
                errstring += '  %s\n' % descr
            
            raise yum.Errors.YumBaseError, errstring

        # close things
        

    
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
        
        oldcount = self.tsInfo.count()
        if not userlist:
            userlist = self.extcmds
            
        self.doRpmDBSetup()
        installed = self.rpmdb.getPkgList()
        self.doRepoSetup()
        avail = self.pkgSack.returnPackages()
        toBeInstalled = {} # keyed on name
        passToUpdate = [] # list of pkgtups to pass along to updatecheck

        for arg in userlist:
            arglist = [arg]
            exactmatch, matched, unmatched = parsePackages(avail, arglist)
            if len(unmatched) > 0: # if we get back anything in unmatched, it fails
                self.errorlog(0, _('No Match for argument %s') % arg)
                continue
            
            installable = yum.misc.unique(exactmatch + matched)
            exactarch = self.conf.getConfigOption('exactarch')
            
            # we look through each returned possibility and rule out the
            # ones that we obviously can't use
            for pkg in installable:
                (n, e, v, r, a) = pkg.returnNevraTuple()
                pkgtup = (n, a, e, v, r)
                if a == 'src':
                    continue
                if pkgtup in installed:
                    continue

                # look up the installed packages based on name or name+arch, 
                # depending on exactarch being set.
                if exactarch:
                    installedByKey = self.rpmdb.returnTupleByKeyword(name=n, arch=a)
                else:
                    installedByKey = self.rpmdb.returnTupleByKeyword(name=n)
                
                
                # go through each package 
                if len(installedByKey) > 0:
                    for instTup in installedByKey:
                        (n2, a2, e2, v2, r2) = instTup
                        rc = compareEVR((e2, v2, r2), (e, v, r))
                        if rc < 0: # we're newer - this is an update, pass to them
                            passToUpdate.append(pkgtup)
                        elif rc == 0: # same, ignore
                            continue
                        elif rc > 0: # lesser, check if the pkgtup is an exactmatch
                                        # if so then add it to be installed,
                                        # the user explicitly wants this version
                                        # FIXME this is untrue if the exactmatch
                                        # does not include a version-rel section
                            if pkgtup in exactmatch:
                                if not toBeInstalled.has_key(n): toBeInstalled[n] = []
                                toBeInstalled[n].append(pkgtup)
                else: # we've not got any installed that match n or n+a
                    if not toBeInstalled.has_key(n): toBeInstalled[n] = []
                    toBeInstalled[n].append(pkgtup)
        
        
        oldcount = self.tsInfo.count()
        pkglist = returnBestPackages(toBeInstalled)
        if len(pkglist) > 0:
            self.log(3, 'reduced installs :')
        for (n,a,e,v,r) in pkglist:
            self.log(3,'   %s.%s %s:%s-%s' % (n, a, e, v, r))
            self.tsInfo.add((n,a,e,v,r), 'i')

        if len(passToUpdate) > 0:
            self.log(3, 'potential updates :')
            updatelist = []
            for (n,a,e,v,r) in passToUpdate:
                self.log(3, '   %s.%s %s:%s-%s' % (n, a, e, v, r))
                pkgstring = '%s:%s-%s-%s.%s' % (e,n,v,r,a)
                updatelist.append(pkgstring)
            self.updatePkgs(userlist=updatelist)

        if self.tsInfo.count() > oldcount:
            return 2, ['Package(s) to install']
        return 0, ['Nothing to do']
        
        #FIXME - what do I do in the case of yum install kernel\*
        # where kernel-1.1-1.i686 is installed and kernel-1.2-1.i[3456]86 are
        # available. the i686 kernel is an update, but the rest are potential
        # installs, right? Or in the event of one member of an arch being
        # an update all other members should be considered potential upgrades
        # unless the other member is also a multilib Arch.
        
    def updatePkgs(self, userlist=None):
        """take user commands and populate transaction wrapper with 
           packages to be updated"""
        
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting
        
        oldcount = self.tsInfo.count()
        if not userlist:
            userlist = self.extcmds

        self.doRpmDBSetup()
        installed = self.rpmdb.getPkgList()
        self.doRepoSetup()
        avail = self.pkgSack.simplePkgList()
        self.doUpdateSetup()
        updates = self.up.getUpdatesTuples()
        if self.conf.getConfigOption('obsoletes'):
            obsoletes = self.up.getObsoletesTuples(newest=1)
        else:
            obsoletes = []


        if len(userlist) == 0: # simple case - do them all
            for (obsoleting,installed) in obsoletes:
                (o_n, o_a, o_e, o_v, o_r) = obsoleting
                self.tsInfo.add(obsoleting, 'u', 'user')
                reason = '%s.%s %s:%s-%s' % obsoleting
                self.tsInfo.add(installed, 'o', reason)
                
            for (new, old) in updates:
                (o_n, o_a, o_e, o_v, o_r) = old
                oldstate = self.tsInfo.getMode(name=o_n, arch=o_a, epoch=o_e, ver=o_v, rel=o_r)
                if oldstate != 'o':
                    self.tsInfo.add(new, 'u', 'user')
                else:
                    self.log(5, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s' % old)

        else:
            # we've got a userlist, match it against updates tuples and populate
            # the tsInfo with the matches
            updatesPo = []
            for (new, old) in updates:
                (n,a,e,v,r) = new
                updatesPo.extend(self.pkgSack.searchNevra(name=n, arch=a, epoch=e, 
                                 ver=v, rel=r))
                                 
            exactmatch, matched, unmatched = yum.packages.parsePackages(updatesPo, userlist)
            for userarg in unmatched:
                self.errorlog(1, 'Could not find update match for %s' % userarg)

            updateMatches = yum.misc.unique(matched + exactmatch)
            for po in updateMatches:
                self.tsInfo.add(po.pkgtup(), 'u', 'user')


        if self.tsInfo.count() > oldcount:
            change = self.tsInfo.count() - oldcount
            msg = '%d packages marked for Update/Obsoletion' % change
            return 2, [msg]
        else:
            return 0, ['No Packages marked for Update/Obsoletion']


        
    
    def erasePkgs(self, userlist=None):
        """take user commands and populate a transaction wrapper with packages
           to be erased/removed"""
        
        oldcount = self.tsInfo.count()
        
        if not userlist:
            userlist = self.extcmds
        
        self.doRpmDBSetup()
        installed = []
        for hdr in self.rpmdb.getHdrList():
            po = YumInstalledPackage(hdr)
            installed.append(po)
        
        if len(userlist) > 0: # if it ain't well, that'd be real _bad_ :)
            exactmatch, matched, unmatched = yum.packages.parsePackages(installed, userlist)
            erases = yum.misc.unique(matched + exactmatch)
        
        for pkg in erases:
            pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
            self.tsInfo.add(pkgtup, 'e', 'user')
        
        
        
        if self.tsInfo.count() > oldcount:
            change = self.tsInfo.count() - oldcount
            msg = '%d packages marked for removal' % change
            return 2, [msg]
        else:
            return 0, ['No Packages marked for removal']
    
    def genPkgLists(self):
        """Generates lists of packages based on arguments on the cli.
           returns a dict: key = string describing the list, value = list of pkg
           objects"""
            
        special = ['available', 'installed', 'all', 'extras', 'updates', 'recent',
                   'obsoletes']

        installed = []
        available = []
        updates = []
        obsoletes = []
        recent = []
        extras = []
        pkgnarrow = 'all' # option used to narrow the subset of packages to
                          # list from
                        
        if len(self.extcmds) > 0:
            if self.extcmds[0] in special:
                pkgnarrow = self.extcmds.pop(0)

        if pkgnarrow == 'all':
            self.doRpmDBSetup()
            inst = self.rpmdb.getPkgList()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                installed.append(po)
            self.doRepoSetup()
            for pkg in self.pkgSack.returnPackages():
                pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
                if pkgtup not in inst:
                    available.append(pkg)

            
        elif pkgnarrow == 'updates':
            self.doRpmDBSetup()
            self.doRepoSetup()
            self.doUpdateSetup()
            for (n,a,e,v,r) in self.up.getUpdatesList():
                matches = self.pkgSack.searchNevra(name=n, arch=a, epoch=e, 
                                                   ver=v, rel=r)
                if len(matches) > 1:
                    updates.append(matches[0])
                    self.log(4, 'More than one identical match in sack for %s' % matches[0])
                elif len(matches) == 1:
                    updates.append(matches[0])
                else:
                    self.log(4, 'Nothing matches %s.%s %s:%s-%s from update' % (n,a,e,v,r))


        elif pkgnarrow == 'installed':
            self.doRpmDBSetup()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                installed.append(po)

        elif pkgnarrow == 'available':
            self.doRpmDBSetup()
            self.doRepoSetup()
            inst = self.rpmdb.getPkgList()
            for pkg in self.pkgSack.returnPackages():
                pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
                if pkgtup not in inst:
                    available.append(pkg)


        elif pkgnarrow == 'extras':
            # we must compare the installed set versus the repo set
            # anything installed but not in a repo is an extra
            self.doRpmDBSetup()
            self.doRepoSetup()
            avail = self.pkgSack.simplePkgList()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                if po.pkgtup() not in avail:
                    extras.append(po)

        elif pkgnarrow == 'obsoletes':
            self.doRpmDBSetup()
            self.doRepoSetup()
            self.conf.setConfigOption('obsoletes', 1)
            self.doUpdateSetup()

            for pkgtup in self.up.getObsoletesList():
                (n,a,e,v,r) = pkgtup
                pkgs = self.pkgSack.searchNevra(name=n, arch=a, ver=v, rel=r, epoch=e)
                for po in pkgs:
                    obsoletes.append(po)

        elif pkgnarrow == 'recent':
            ftimehash = {}
            self.doRepoSetup()
            for po in self.pkgSack.returnPackages():
                ftime = po.returnSimple('filetime')
                if not ftimehash.has_key(ftime):
                    ftimehash[ftime] = [po]
                else:
                    ftimehash[ftime].append(po)
            
            timekeys = ftimehash.keys()
            timekeys.sort()
            timekeys.reverse()
            for sometime in timekeys:
                for po in ftimehash[sometime]:
                    recent.append(po)
        
        returndict = {}
        for (lst, description) in [(updates, 'Updated'), (available, 'Available'), 
                      (installed, 'Installed'), (recent, 'Recently available'),
                      (obsoletes, 'Obsoleting'), (extras, 'Extra')]:

            if len(lst) > 0 and len(self.extcmds) > 0:
                self.log(4, 'Matching packages for %s list to user args' % description)
                exactmatch, matched, unmatched = yum.packages.parsePackages(lst, self.extcmds)
                lst = yum.misc.unique(matched + exactmatch)
                
            # reduce recent to the top N
            if description == 'Recently available':
                num = int(self.conf.getConfigOption('numrecent'))
                lst = lst[:num]

            returndict[description] = lst

        return returndict

    def usage(self):
        print _("""
    Usage:  yum [options] <update | install | info | remove | list |
            clean | provides | search | check-update | groupinstall | 
            groupupdate | grouplist | generate-rss >
                
        Options:
        -c [config file] - specify the config file to use
        -e [error level] - set the error logging level
        -d [debug level] - set the debugging level
        -y - answer yes to all questions
        -R [time in minutes] - set the max amount of time to randomly run in
        -C run from cache only - do not update the cache
        --installroot=[path] - set the install root (default '/')
        --version - output the version of yum
        --rss-filename=[path/filename] - set the filename to generate rss to
        -h, --help  - this screen
    """)
        sys.exit(1)

           


        

