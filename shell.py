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

import cmd
from yum import Errors

class YumShell(cmd.Cmd):
    def __init__(self, base):
        cmd.Cmd.__init__(self)
        self.base = base
        self.prompt = '> '
        self.result = 0
        self.resultmsgs = ['Leaving Shell']
        
    def default(self, line):
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
        self.base.usage()
        
    def do_EOF(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_quit(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_exit(self, line):
        self.resultmsgs = ['Leaving Shell']
        return True
        
    def do_run(self, line):
        if len(self.base.tsInfo) > 0:
            self.result = 2
            self.resultmsgs = ['Running commands']
            return True
        else:
            self.resultmsgs = ['Nothing to do']
        
