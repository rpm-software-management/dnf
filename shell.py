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
            self.base.cmdstring = line
            self.base.cmdstring = self.base.cmdstring.replace('\n', '')
            self.base.cmds = self.base.cmdstring.split()
            try:
                self.base.parseCommands()
            except Errors.YumBaseError:
                pass
            else:
                self.base.doCommands()
    
    def emptyline(self):
        pass
    
    def do_help(self, arg):
        msg = """
    commands:  check-update, clean, disablerepo, enablerepo,
               exit, groupinfo, groupinstall, grouplist,
               groupremove, groupupdate, info, install, list,
               listrepos, localinstall, makecache, provides, quit,
               remove, run, search, transaction, update
    """
        if arg in ['transaction', 'ts']:
            msg = """
    transaction arg
      list: lists the contents of the transaction
      reset: reset (zero-out) the transaction
      solve: run the dependency solver on the transaction
      run: run the transaction
                  """
        elif arg in ['repos', 'repositories']:
            msg = """
    repos arg [option]
      list: lists repositories and their status
      enable: enable repositories. option = repository id
      disable: disable repositories. option = repository id
    """
    
        self.base.log(1, msg)
        
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
        # ints
        if cmd in ['debuglevel', 'errorlevel']:
            opts = args.split()
            if not opts:
                self.base.log(2, '%s' % (self.base.conf.getConfigOption(cmd)))
            else:
                val = int(opts[0])
                self.base.conf.setConfigOption(cmd, val)
        # bools
        elif cmd in ['gpgcheck', 'obsoletes', 'assumeyes']:
            opts = args.split()
            if not opts:
                self.base.log(2, '%s' % (self.base.conf.getConfigOption(cmd)))
            else:
                value = opts[0]
                if value.lower() not in BOOLEAN_STATES:
                    self.base.errorlog('Value %s for %s is not a Boolean' % (value, cmd))
                    return False
                value = BOOLEAN_STATES[value.lower()]
                self.base.conf.setConfigOption(cmd, value)

            
    def do_repositories(self, line):
        self.do_repos(line)
        
    def do_repos(self, line):
        (cmd, args, line) = self.parseline(line)
        if cmd in ['list', None]:
            for repo in self.base.repos.repos.values():
                if repo in self.base.repos.listEnabled():
                    self.base.log('%-20.20s %-40.40s  enabled' % (repo, repo.name))
                else:
                    self.base.log('%-20.20s %-40.40s  disabled' % (repo, repo.name))
        
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
            self.do_help('repos')
                
    def do_test(self, line):
        (cmd, args, line) = self.parseline(line)
        print cmd
        print args
        print line
        
    def do_run(self, line):
        if len(self.base.tsInfo) > 0:
            try:
                self.base.doTransaction()
            except Errors.YumBaseError, e:
                self.base.errorlog(0, '%s' % e)
            except KeyboardInterrupt, e:
                self.base.errorlog(0, '\n\nExiting on user cancel')
            except IOError, e:
                if e.errno == 32:
                    self.base.errorlog(0, '\n\nExiting on Broken Pipe')
            else:
                self.base.log(2, 'Finished Transaction')
                self.base.closeRpmDB()
                self.base.doTsSetup()
                self.base.doRpmDBSetup()

