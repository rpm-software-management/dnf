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

import sys
import os.path
import cmd
import string

from yum import Errors
from yum.constants import *

# TODO: implement setconfig and getconfig - this should only expose a subset
#       of the configuration options. exposing all of them, especially the lists
#       would be a pain to parse and handle but the int, string and booleans
#       should be doable. Config only affects global config settings not
#       repo configuration.
#       one of the oft-requested lists will be 'exclude' - this should be its 
#       own command, probably so we can set excludes. make it a space separated
#       list

class YumShell(cmd.Cmd):
    def __init__(self, base):
        cmd.Cmd.__init__(self)
        self.base = base
        self.prompt = '> '
        self.result = 0
        self.resultmsgs = ['Leaving Shell']
        if (len(base.extcmds)) > 0:
            self.file = base.extcmds[0]
        self.commandlist = ['clean', 'repo', 'exit', 'groupinfo',
            'groupinstall', 'grouplist', 'groupremove', 'groupupdate',
            'info', 'install', 'list', 'localinstall', 'repository',
            'makecache', 'provides', 'quit', 'remove', 'run', 'search',
            'transaction', 'ts', 'update', 'config']

    def script(self):
        try:
            fd = open(self.file, 'r')
        except IOError, e:
            sys.exit("Error: Cannot open %s for reading")
        lines = fd.readlines()
        fd.close()
        for line in lines:
            self.onecmd(line)
        self.onecmd('EOF')
        return True
            
    def default(self, line):
        if len(line) > 0 and line.strip()[0] == '#':
            pass
        else:
            (cmd, args, line) = self.parseline(line)
            if cmd not in self.commandlist:
                self.do_help('')
                return False
            self.base.cmdstring = line
            self.base.cmdstring = self.base.cmdstring.replace('\n', '')
            self.base.cmds = self.base.cmdstring.split()
            try:
                self.base.parseCommands()
            except Errors.YumBaseError:
                self.do_help('')
            else:
                self.base.doCommands()
    
    def emptyline(self):
        pass
    
    def do_help(self, arg):
        msg = """
    commands:  clean, config, exit, groupinfo, groupinstall, grouplist,
               groupremove, groupupdate, info, install, list,
               localinstall, makecache, provides, quit, remove, 
               repo, run, search, transaction, update
    """
        if arg in ['transaction', 'ts']:
            msg = """
    %s arg
      list: lists the contents of the transaction
      reset: reset (zero-out) the transaction
      solve: run the dependency solver on the transaction
      run: run the transaction
                  """ % arg
        elif arg in ['repo', 'repository']:
            msg = """
    %s arg [option]
      list: lists repositories and their status
      enable: enable repositories. option = repository id
      disable: disable repositories. option = repository id
    """ % arg
    
        elif arg == 'config':
            msg = """
    %s arg [value]
      args: debuglevel, errorlevel, obsoletes, gpgcheck, assumeyes, exclude
        If no value is given it prints the current value.
        If value is given it sets that value.
        """ % arg
        
        self.base.log(0, msg)
        
    def do_EOF(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_quit(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_exit(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_ts(self, line):
        self.do_transaction(line)

    def do_transaction(self, line):
        (cmd, args, line) = self.parseline(line)
        if cmd in ['list', None]:
            self.base.log(2,self.base.listTransaction())
        
        elif cmd == 'reset':
            self.base.closeRpmDB()
            self.base.doTsSetup()
            self.base.doRpmDBSetup()
        
        elif cmd == 'solve':
            (code, msgs) = self.base.buildTransaction()
            if code == 1:
                for msg in msgs:
                    self.base.errorlog(0, 'Error: %s' % msg)
        
        elif cmd == 'run':
            return self.do_run('')
            
        else:
            self.do_help('transaction')
    
    def do_config(self, line):
        (cmd, args, line) = self.parseline(line)
        # logs
        if cmd in ['debuglevel', 'errorlevel']:
            opts = args.split()
            if not opts:
                self.base.log(2, '%s: %s' % (cmd, self.base.conf.getConfigOption(cmd)))
            else:
                val = opts[0]
                try:
                    val = int(val)
                except ValueError, e:
                    self.base.errorlog(0, 'Value %s for %s cannot be made to an int' % (val, cmd))
                    return
                self.base.conf.setConfigOption(cmd, val)
                if cmd == 'debuglevel':
                    self.base.log.threshold = val
                elif cmd == 'errorlevel':
                    self.base.errorlog.threshold = val
        # bools
        elif cmd in ['gpgcheck', 'obsoletes', 'assumeyes']:
            opts = args.split()
            if not opts:
                self.base.log(2, '%s: %s' % (cmd, self.base.conf.getConfigOption(cmd)))
            else:
                value = opts[0]
                if value.lower() not in BOOLEAN_STATES:
                    self.base.errorlog(0, 'Value %s for %s is not a Boolean' % (value, cmd))
                    return False
                value = BOOLEAN_STATES[value.lower()]
                self.base.conf.setConfigOption(cmd, value)
                if cmd == 'obsoletes':
                    if hasattr(self.base, 'up'): # reset the updates
                        del self.base.up
        
        elif cmd in ['exclude']:
            args = args.replace(',', ' ')
            opts = args.split()
            if not opts:
                msg = '%s: ' % cmd
                msg = msg + string.join(self.base.conf.getConfigOption(cmd))
                self.base.log(2, msg)
                return False
            else:
                self.base.conf.setConfigOption(cmd, opts)
                if hasattr(self.base, 'pkgSack'): # kill the pkgSack
                    del self.base.pkgSack
                    self.base.repos._selectSackType()
                if hasattr(self.base, 'up'): # reset the updates
                    del self.base.up
                # reset the transaction set, we have to or we shall surely die!
                self.base.closeRpmDB() 
                self.base.doTsSetup()
                self.base.doRpmDBSetup()
        else:
            self.do_help('config')

    def do_repository(self, line):
        self.do_repo(line)
        
    def do_repo(self, line):
        (cmd, args, line) = self.parseline(line)
        if cmd in ['list', None]:
            if self.base.repos.repos.values():
                self.base.log(2, '%-20.20s %-40.40s  status' % ('repo id', 'repo name'))
            for repo in self.base.repos.repos.values():
                if repo in self.base.repos.listEnabled():
                    self.base.log(2, '%-20.20s %-40.40s  enabled' % (repo, repo.name))
                else:
                    self.base.log(2, '%-20.20s %-40.40s  disabled' % (repo, repo.name))
        
        elif cmd == 'enable':
            repos = args.split()
            for repo in repos:
                try:
                    changed = self.base.repos.enableRepo(repo)
                except yum.Errors.ConfigError, e:
                    self.base.errorlog(0, e)
                else:
                    for repoid in changed:
                        self.base.doRepoSetup(thisrepo=repoid)
                    
                    if hasattr(self.base, 'up'): # reset the updates
                        del self.base.up
            
        elif cmd == 'disable':
            repos = args.split()
            for repo in repos:
                try:
                    self.base.repos.disableRepo(repo)
                except yum.Errors.ConfigError, e:
                    self.base.errorlog(0, e)
    
                else:
                    if hasattr(self.base, 'pkgSack'): # kill the pkgSack
                        del self.base.pkgSack
                        self.base.repos._selectSackType()
                    if hasattr(self.base, 'up'): # reset the updates
                        del self.base.up
                    # reset the transaction set and refresh everything
                    self.base.closeRpmDB() 
                    self.base.doTsSetup()
                    self.base.doRpmDBSetup()
        
        else:
            self.do_help('repo')
                
    def do_test(self, line):
        (cmd, args, line) = self.parseline(line)
        print cmd
        print args
        print line
        
    def do_run(self, line):
        if len(self.base.tsInfo) > 0:
            try:
                returnval = self.base.doTransaction()
            except Errors.YumBaseError, e:
                self.base.errorlog(0, '%s' % e)
            except KeyboardInterrupt, e:
                self.base.errorlog(0, '\n\nExiting on user cancel')
            except IOError, e:
                if e.errno == 32:
                    self.base.errorlog(0, '\n\nExiting on Broken Pipe')
            else:
                if returnval != 0:
                    self.base.log(0, 'Transaction did not run.')
                else:
                    self.base.log(2, 'Finished Transaction')
                    self.base.closeRpmDB()
                    self.base.doTsSetup()
                    self.base.doRpmDBSetup()

