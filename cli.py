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
            logfd = os.open(conf.getConfigOption('logfile'), os.WRONLY |
                            os.O_APPEND | os.O_CREAT)
            logfile =  os.fdopen(logd, 'a')
            fcntl.fcntl(logfd, fcntl.F_SETFD)
            filelog = Logger(threshold = 10, file_object = logfile, 
                             preprefix = printtime())
        else:
            filelog = Logger(threshold = 10, file_object = None, 
                             preprefix = printtime())
        
       
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
    
    parseCommands() # before we exit check over the base command + args
                    # make sure they match
        

def printtime():
    return time.strftime('%b %d %H:%M:%S', time.localtime(time.time()))
    

def simpleProgressBar(current, total, name=None):
    """simple progress bar 50 # marks"""
    
    mark = '#'
    
    if current == 0:
        percent = 0 
    else:
        percent = current*100/total

    numblocks = int(percent/2)
    hashbar = mark * numblocks
    if name is None:
        output = '\r%-50s %d/%d' % (hashbar, current, total)
    else:
        output = '\r%s:%-50s %d/%d' % (name, hashbar, current, total)
     
    sys.stdout.write(output)
    if current == total:
        sys.stdout.write('\n')
        

def parseCommands():
    """reads base.cmds and parses them out to make sure that the requested 
       base command + argument makes any sense at all""" 
          
    basecmd = base.cmds[0]
   
    if base.conf.getConfigOption('uid') != 0:
        if basecmd in ['install', 'update', 'clean', 'upgrade','erase', 
                      'groupupdate', 'groupinstall', 
                      'groupremove']:
            base.errorlog(0, _('You need to be root to perform these commands'))
            sys.exit(1)
    
    if basecmd in ['install', 'update', 'erase', 'remove']:
        if len(base.cmds[1:]) == 0:
            base.errorlog(0, _('Error: Need to pass a list of pkgs to %s') % basecmd)
            usage()

    elif basecmd in ['provides', 'search']:       
        if len(base.cmds[1:]) == 0:
            base.errorlog(0, _('Error: Need an item to match'))
            usage()
        
    elif basecmd in ['groupupdate', 'groupinstall', 'groupremove']:
        if len(base.cmds[1:]) == 0:
            base.errorlog(0, _('Error: Need a group or list of groups'))
            usage()

    elif basecmd == 'clean':
        if len(base.cmds[1:]) > 0 and cmds[1] not in ['packages' 'headers', 'all']:
            base.errorlog(0, _('Error: Invalid clean option %s') % cmds[0])
            usage()

    elif basecmd in ['list', 'check-update', 'info']:
        pass
    else:
        usage()
        

def format_number(number, SI=0, space=' '):
    """Turn numbers into human-readable metric-like numbers"""
    symbols = ['',  # (none)
                'k', # kilo
                'M', # mega
                'G', # giga
                'T', # tera
                'P', # peta
                'E', # exa
                'Z', # zetta
                'Y'] # yotta

    if SI: step = 1000.0
    else: step = 1024.0

    thresh = 999
    depth = 0

    # we want numbers between 
    while number > thresh:
        depth  = depth + 1
        number = number / step

    # just in case someone needs more than 1000 yottabytes!
    diff = depth - len(symbols) + 1
    if diff > 0:
        depth = depth - diff
        number = number * thresh**depth

    if type(number) == type(1) or type(number) == type(1L):
        format = '%i%s%s'
    elif number < 9.95:
        # must use 9.95 for proper sizing.  For example, 9.99 will be
        # rounded to 10.0 with the .1f format string (which is too long)
        format = '%.1f%s%s'
    else:
        format = '%.0f%s%s'

    return(format % (number, space, symbols[depth]))
        

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
