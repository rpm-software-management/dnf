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

import progress_meter
import yum.Errors
from yum.logger import Logger
from yum.config import yumconf
from i18n import _

__version__ = '2.1.0'

base = None # this is a stub

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
                sleeptime = random.randrange(int(a)*60)
                time.sleep(sleeptime)
            if o == '-c':
                yumconffile = a

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
        log=Logger(threshold=conf.getConfigOption('debuglevel'), file_object = 
                                                                     sys.stdout)
        
        # syslog-style log
        if conf.getConfigOption('uid') == 0:
            logfd = os.open(conf.getConfigOption('logfile'), os.O_WRONLY |
                            os.O_APPEND | os.O_CREAT)
            logfile =  os.fdopen(logfd, 'a')
            fcntl.fcntl(logfd, fcntl.F_SETFD)
            filelog = Logger(threshold = 10, file_object = logfile, 
                             preprefix = output.printtime())
        else:
            filelog = Logger(threshold = 10, file_object = None, 
                             preprefix = output.printtime())
        
       
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
    # save our original args out
    baseclass.args = args
    
    parseCommands(baseclass) # before we exit check over the base command + args
                    # make sure they match
        


def parseCommands(baseclass):
    """reads baseclass.cmds and parses them out to make sure that the requested 
       base command + argument makes any sense at all""" 

    cmds = baseclass.cmds          
    if len(cmds) < 1:
        baseclass.errorlog(0, _('You need to give some command'))
        usage()
        
    basecmd = cmds[0]
    

    if baseclass.conf.getConfigOption('uid') != 0:
        if basecmd in ['install', 'update', 'clean', 'upgrade','erase', 
                      'groupupdate', 'groupinstall', 'remove',
                      'groupremove']:
            baseclass.errorlog(0, _('You need to be root to perform these commands'))
            sys.exit(1)
    
    if basecmd in ['install', 'update', 'erase', 'remove']:
        if len(cmds[1:]) == 0:
            baseclass.errorlog(0, _('Error: Need to pass a list of pkgs to %s') % basecmd)
            usage()

    elif basecmd in ['provides', 'search']:       
        if len(cmds[1:]) == 0:
            baseclass.errorlog(0, _('Error: Need an item to match'))
            usage()
        
    elif basecmd in ['groupupdate', 'groupinstall', 'groupremove']:
        if len(cmds[1:]) == 0:
            baseclass.errorlog(0, _('Error: Need a group or list of groups'))
            usage()

    elif basecmd == 'clean':
        if len(cmds[1:]) > 0 and cmds[1] not in ['packages' 'headers', 'all']:
            baseclass.errorlog(0, _('Error: Invalid clean option %s') % cmds[1])
            usage()

    elif basecmd in ['list', 'check-update', 'info']:
        pass
    else:
        usage()
        

def doCommands(baseclass):
    """calls the command based on the args, also passes the args out to be 
       parsed"""
    
    cmds = baseclass.cmds
    basecmd = cmds[0]
    args = cmds[1:]
    
    if basecmd in ['install', 'update']:
        matched, unmatched = parsePackages(baseclass.pkgSack.simplePkgList(), args)

    elif basecmd in ['erase', 'remove']:
        matched, unmatched = parsePackages(baseclass.rpmdb.getPkgList(), args)
        
    return basecmd, matched, unmatched    
        
   
def buildPkgRefDict(pkgs):
    """take a list of pkg tuples and return a dict the contains all the possible
       naming conventions for them eg: for (name,i386,0,1,1)
       dict[name] = (name, i386, 0, 1, 1)
       dict[name.i386] = (name, i386, 0, 1, 1)
       dict[name-1-1.i386] = (name, i386, 0, 1, 1)       
       dict[name-1] = (name, i386, 0, 1, 1)       
       dict[name-1-1] = (name, i386, 0, 1, 1)
       dict[0:name-1-1.i386] = (name, i386, 0, 1, 1)
       """
    pkgdict = {}
    for pkgtup in pkgs:
        (n, a, e, v, r) = pkgtup
        name = n
        nameArch = '%s.%s' % (n, a)
        nameVerRelArch = '%s-%s-%s.%s' % (n, v, r, a)
        nameVer = '%s-%s' % (n, v)
        nameVerRel = '%s-%s-%s' % (n, v, r)
        full = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        for item in [name, nameArch, nameVerRelArch, nameVer, nameVerRel, full]:
            if not pkgdict.has_key(item):
                pkgdict[item] = []
            pkgdict[item].append(pkgtup)
            
    return pkgdict            
       
def parsePackages(pkgs, usercommands):
    """matches up the user request versus a pkg list:
       for installs/updates available pkgs should be the 'others list' for removes it should
       be the installed list of pkgs"""

    pkgdict = buildPkgRefDict(pkgs)
    matched = []
    unmatched = []
    for command in usercommands:
        if pkgdict.has_key(command):
            matched.extend(pkgdict[command])
            del pkgdict[command]
        else:
            # anything we couldn't find a match for
            # could mean it's not there, could mean it's a wildcard
            if re.match('.*[\*,\[,\],\{,\},\?].*', command):
                trylist = pkgdict.keys()
                restring = fnmatch.translate(command)
                regex = re.compile(restring, flags=re.I) # case insensitive
                foundit = 0
                for item in trylist:
                    if regex.match(item):
                        matched.extend(pkgdict[item])
                        del pkgdict[item]
                        foundit = 1
 
                if not foundit:    
                    unmatched.append(command)
                    
            else:
                # we got nada
                unmatched.append(command)


    return matched, unmatched


        

def userconfirm():
    """gets a yes or no from the user, defaults to No"""
    choice = raw_input('Is this ok [y/N]: ')
    if len(choice) == 0:
        return 1
    else:
        if choice[0] != 'y' and choice[0] != 'Y':
            return 1
        else:
            return 0        

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
