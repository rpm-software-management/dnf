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
# Copyright 2002 Duke University 


import os
import sys
import getopt
import time
import random
import locale
import rpm

import callback
import yumlock
import yum
import rpmUtils.transaction
import rpmUtils.updates
import yum.yumcomps
import yum.Errors
import progress_meter
import misc

from yum.logger import Logger
from yum.config import yumconf
from i18n import _

__version__='2.1.0'

def getOptionsConfig(args, baseclass):
    """parses command line arguments, takes cli args, and a simple holder class:
       sets up baseclass.conf and baseclass.cmds as well as logger objects 
       in base instance"""
      
    # setup our errorlog object 
    errorlog = Logger(threshold=2, file_object=sys.stderr)

    # our default config file location
    yumconffile = None
    if os.access("/etc/yum.conf", os.R_OK):
        yumconffile = "/etc/yum.conf"

    try:
        gopts, cmds = getopt.getopt(args, 'tCc:hR:e:d:y', ['help',
                                                           'version',
                                                           'installroot=',
                                                           'enablerepo=',
                                                           'disablerepo=',
                                                           'exclude=',
                                                           'obsoletes',
                                                           'download-only',
                                                           'tolerant'])
    except getopt.error, e:
        errorlog(0, _('Options Error: %s') % e)
        usage()

    # get the early options out of the way
    # these are ones that:
    #  - we need to know about and do NOW
    #  - answering quicker is better
    #  - give us info for parsing the others
    
    
    try: 
        for o,a in gopts:
            if o == '--version':
                print __version__
                sys.exit(0)
            if o == '--installroot':
                if os.access(a + "/etc/yum.conf", os.R_OK):
                    yumconffile = a + '/etc/yum.conf'
            if o == '-R':
                sleeptime=random.randrange(int(a)*60)
                time.sleep(sleeptime)
            if o == '-c':
                yumconffile=a

        if yumconffile:
            try:
                conf = yumconf(configfile = yumconffile)
            except yum.Errors.ConfigError, e:
                errorlog(0, _('Config Error: %s.') % e)
                sys.exit(1)
        else:
            errorlog(0, _('Cannot find any conf file.'))
            sys.exit(1)
            
        # config file is parsed and moving us forward
        # set some things in it.
            
        # who are we:
        conf.setConfigOption('uid', os.geteuid())
        # version of yum
        conf.setConfigOption('yumversion', __version__)
        
        
        # we'd like to have a log object now
        log=Logger(threshold=conf.getConfigOption('debuglevel'), file_object=sys.stdout)
        
        # syslog-style log
        if conf.getConfigOption('uid') == 0:
            logfd = os.open(conf.getConfigOption('logfile'), os.WRONLY, os.O_APPEND)
            logfile =  os.fdopen(logd, 'a')
            fcntl.fcntl(logfd, fcntl.F_SETFD)
            filelog = Logger(threshold = 10, file_object = logfile, preprefix = misc.printtime())
        else:
            filelog = Logger(threshold = 10, file_object = None, preprefix = misc.printtime())
        
       
        # now the rest of the options
        for o,a in gopts:
            if o == '-d':
                log.threshold=int(a)
                conf.setConfigOption('debuglevel', int(a))
            elif o == '-e':
                errorlog.threshold=int(a)
                conf.setConfigOption('errorlevel', int(a))
            elif o == '-y':
                conf.setConfigOption('assumeyes',1)
            elif o in ['-h', '--help']:
                usage()
            elif o == '-C':
                conf.setConfigOption('cache', 1)
            elif o == '--obsoletes':
                conf.setConfigOption('obsoletes', 1)
            elif o in ['-t', '--tolerant']:
                conf.setConfigOption('tolerant', 1)
            elif o == '--installroot':
                conf.setConfigOption('installroot', a)
            elif o == '--enablerepo':
                try:
                    conf.repos.enableRepo(a)
                except yum.Errors.ConfigError, e:
                    errorlog(0, _(e))
                    usage()
            elif o == '--disablerepo':
                try:
                    conf.repos.disableRepo(a)
                except yum.Errors.ConfigError, e:
                    errorlog(0, _(e))
                    usage()
                    
            elif o == '--exclude':
                try:
                    excludelist = conf.getConfigOption('exclude')
                    excludelist.append(a)
                    conf.setConfigOption('exclude', excludelist)
                except yum.Errors.ConfigError, e:
                    errorlog(0, _(e))
                    usage()
            
                        
    except ValueError, e:
        errorlog(0, _('Options Error: %s') % e)
        usage()
    
    # if we're below 2 on the debug level we don't need to be outputting
    # progress bars - this is hacky - I'm open to other options
    if conf.getConfigOption('debuglevel') < 2:
        conf.setConfigOption('progress_obj', None)
    else:
        conf.setConfigOption('progress_obj', progress_meter.text_progress_meter(fo=sys.stdout))
    
    baseclass.conf = conf
    baseclass.cmds = cmds
    baseclass.errorlog = errorlog
    baseclass.log = log
    baseclass.filelog = filelog
    # this is just a convenience reference
    baseclass.repos = conf.repos

def main(args):
    """This does all the real work"""

    locale.setlocale(locale.LC_ALL, '')
    #DEBUG
    print time.time()


    if len(args) < 1:
        usage()

    # this will be our holder object, things will be pushed in here and passed around 
    # think of this like a global
    base = yum.YumBase()
    # parse our cli args, read in the config file and setup the logs
    getOptionsConfig(args, base)
    
    if len(base.conf.getConfigOption('commands')) == 0 and len(base.cmds) < 1:
        base.cmds = base.conf.getConfigOption('commands')
    else:
        base.conf.setConfigOption('commands', base.cmds)
        
    if len (base.cmds) < 1:
        base.errorlog(0, _('Options Error: no commands found'))
        usage()

    if base.cmds[0] not in ('update', 'install','info', 'list', 'erase',\
                       'grouplist','groupupdate','groupinstall','clean', \
                       'remove', 'provides', 'check-update', 'search'):
        usage()
    process = base.cmds[0]
    
    #DEBUG
    print time.time()    
    
    # ok at this point lets check the lock/set the lock if we can
    if base.conf.getConfigOption('uid') == 0:
        mypid = str(os.getpid())
        try:
            yum.doLock('/var/run/yum.pid', mypid)
        except Errors.LockError, e:
            print _('%s') % e.msg
            sys.exit(200)
    #DEBUG
    print time.time()
    
    # set our caching mode correctly
    if base.conf.getConfigOption('uid') != 0:
        base.conf.setConfigOption('cache', 1)
    if process == 'clean':
        base.conf.setConfigOption('cache', 1)

    # get our transaction set together that we'll use all over the place
    base.read_ts = rpmUtils.transaction.initReadOnlyTransaction()
    
    # create structs for local rpmdb
    base.rpmdb = rpmUtils.RpmDBHolder()
    base.rpmdb.addDB(base.read_ts)
    base.log(2, '#pkgs in db = %s' % len(base.rpmdb.getPkgList()))

    
    if process in ['groupupdate', 'groupinstall', 'grouplist', 'groupremove']:
        base.grpInfo = yum.yumcomps.Groups_Info(base.rpmdb.getPkgList(),
                                 base.conf.getConfigOption('overwrite_groups'))
                                 
        for repo in base.repos.listGroupsEnabled():
            groupfile = repo.getGroups(base.conf.getConfigOption('cache'))
            if groupfile:
                base.log(4, 'Group File found for %s' % repo)
                base.log(4, 'Adding Groups from %s' % repo)
                base.grpInfo.add(groupfile)

        if base.grpInfo.compscount > 0:
            base.grpInfo.compileGroups()
        else:
            base.errorlog(0, _('No groups provided or accessible on any repository.'))
            base.errorlog(1, _('Exiting.'))
            sys.exit(1)

    #DEBUG
    print time.time()
    base.repos.populateSack()
    base.pkgSack = base.repos.pkgSack
    base.log(2, '#pkgs in repos = %s' % len(base.pkgSack.returnPackages()))

    #DEBUG
    print time.time()
    
    base.log(2, _('Finding updated packages'))
    base.up = rpmUtils.updates.Updates(base.rpmdb.getPkgList(), base.pkgSack.simplePkgList())
    base.up.exactarch = base.conf.getConfigOption('exactarch')
    base.up.doUpdates()
    base.up.condenseUpdates()
    print len(base.up.getUpdatesList())

    #DEBUG
    print time.time()
        
    
    ##################################################################
    # at this point we have all the prereq info we could ask for. we 
    # know whats in the rpmdb whats available, whats updated and what 
    # obsoletes. We should be able to do everything we want from here 
    # w/o getting anymore header info
    ##################################################################

    #clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
    #                        HeaderInfo, rpmDBInfo, obsoleted)
    # back from taking actions - if we've not exited by this point then we have
    # an action that will install/erase/update something
    
    # at this point we should have a tsInfo nevral with all we need to complete our task.
    # if for some reason we've gotten all the way through this step with 
    # an empty tsInfo then exit and be confused :)
"""
    if len(tsInfo.NAkeys()) < 1:
        log(2, _('No actions to take'))
        sys.exit(0)
        
    
    if process not in ('erase', 'remove'):
        # put available pkgs in tsInfonevral in state 'a'
        for (name, arch) in nulist:
            if not tsInfo.exists(name, arch):
                ((e, v, r, a, l, i), s)=HeaderInfo._get_data(name, arch)
                log(6,'making available: %s' % name)
                tsInfo.add((name, e, v, r, arch, l, i), 'a')

    log(2, _('Resolving dependencies'))
    (errorcode, msgs) = tsInfo.resolvedeps(rpmDBInfo)
    if errorcode:
        for msg in msgs:
            print msg
        sys.exit(1)
    log(2, _('Dependencies resolved'))
    
    # prompt for use permission to do stuff in tsInfo - list all the actions 
    # (i, u, e, ed, ud,iu(installing, but marking as 'u' in the actual ts, just 
    # in case)) confirm w/the user
    
    (i_list, u_list, e_list, ud_list, ed_list)=clientStuff.actionslists(tsInfo)
    
    clientStuff.printactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
    if conf.assumeyes==0:
        if clientStuff.userconfirm():
            errorlog(1, _('Exiting on user command.'))
            sys.exit(1)
    
    # Test run for file conflicts and diskspace check, etc.
    tstest = clientStuff.create_final_ts(tsInfo)
    log(2, _('Running test transaction:'))
    clientStuff.tsTest(tstest)
    tstest.closeDB()
    del tstest
    log(2, _('Test transaction complete, Success!'))
    
    # FIXME the actual run should probably be elsewhere and this should be
    # inside a try, except set
    tsfin = clientStuff.create_final_ts(tsInfo)

    if conf.diskspacecheck == 0:
        tsfin.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)

    if conf.uid == 0:
        # sigh - the magical "order" command - nice of this not to really be 
        # documented anywhere.
        tsfin.check()
        tsfin.order()
        cb = callback.RPMInstallCallback()
        errors = tsfin.run(cb.callback, '')
        if errors:
            errorlog(0, _('Errors installing:'))
            for error in errors:
                errorlog(0, error)
            sys.exit(1)
        tsfin.closeDB()
        del tsfin
        
        # Check to see if we've got a new kernel and put it in the right place in grub/lilo
        pkgaction.kernelupdate(tsInfo)
        
        # log what we did and also print it out
        clientStuff.filelogactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
        clientStuff.shortlogactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
        
    else:
        errorlog(1, _('You\'re not root, we can\'t install things'))
        sys.exit(0)
        
    log(2, _('Transaction(s) Complete'))
    sys.exit(0)
"""

def usage():
    print _("""
    Usage:  yum [options] <update | install | info | remove | list |
            clean | provides | search | check-update | groupinstall | groupupdate |
            grouplist >
                
         Options:
          -c [config file] - specify the config file to use
          -e [error level] - set the error logging level
          -d [debug level] - set the debugging level
          -y answer yes to all questions
          -t be tolerant about errors in package commands
          -R [time in minutes] - set the max amount of time to randomly run in.
          -C run from cache only - do not update the cache
          --installroot=[path] - set the install root (default '/')
          --version - output the version of yum
          -h, --help this screen
    """)
    sys.exit(1)
    
if __name__ == "__main__":
        main(sys.argv[1:])
