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
    commands:  update, install, info, remove, list, clean, provides, search,
    check-update, groupinstall, groupupdate, grouplist, groupinfo, groupremove,
    makecache, localinstall, transaction, run, quit, exit
    """
        if arg in ['transaction', 'ts']:
            msg = """
    transaction arg
      list: lists the contents of the transaction
      reset: reset (zero-out) the transaction
      solve: run the dependency solver on the transaction
      run: run the transaction
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
        if cmd is None:
            pass
            
        elif cmd == 'list':
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
    
    def do_enablerepo(self, line):
        line = line.replace('\n', '')
        repos = line.split()
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


    def do_disablerepo(self, line):
        line = line.replace('\n', '')
        repos = line.split()
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

