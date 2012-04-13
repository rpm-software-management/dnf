#! /usr/bin/python -tt
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

"""
A shell implementation for the yum command line interface.
"""

import sys
import cmd
import shlex
import logging

from yum import Errors
from yum.constants import *
import yum.logginglevels as logginglevels
from yum.i18n import to_utf8
import __builtin__

class YumShell(cmd.Cmd):
    """A class to implement an interactive yum shell."""

    def __init__(self, base):
        cmd.Cmd.__init__(self)
        self.base = base
        self.prompt = '> '
        self.result = 0
        self.identchars += '-'
        self.from_file = False # if we're running from a file, set this
        self.resultmsgs = ['Leaving Shell']
        if (len(base.extcmds)) > 0:
            self.file = base.extcmds[0]
        self.shell_specific_commands = ['repo', 'repository', 'exit', 'quit',
                'run', 'ts', 'transaction', 'config']
                
        self.commandlist = self.shell_specific_commands + self.base.yum_cli_commands.keys()
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")

        # NOTE: This is shared with self.base ... so don't reassign.
        self._shell_history_cmds = []

    def _shell_history_add_cmds(self, cmds):
        if not self.base.conf.history_record:
            return

        self._shell_history_cmds.append(cmds)

    def _shlex_split(self, input_string):
        """split the input using shlex rules, and error or exit accordingly"""
        
        inputs = []
        if input_string is None: # apparently shlex.split() doesn't like None as its input :)
            return inputs
            
        try:
            inputs = shlex.split(input_string)
        except ValueError, e:
            self.logger.critical('Script Error: %s', e)
            if self.from_file:
                raise Errors.YumBaseError, "Fatal error in script, exiting"
        
        return inputs

    def cmdloop(self, *args, **kwargs):
        """ Sick hack for readline. """

        oraw_input = raw_input
        owriter    = sys.stdout
        _ostdout   = owriter.stream

        def _sick_hack_raw_input(prompt):
            sys.stdout = _ostdout
            rret = oraw_input(to_utf8(prompt))
            sys.stdout = owriter

            return rret

        __builtin__.raw_input = _sick_hack_raw_input

        try:
            cret = cmd.Cmd.cmdloop(self, *args, **kwargs)
        except:
            __builtin__.raw_input  = oraw_input
            raise

        __builtin__.raw_input = oraw_input

        return cret

    def script(self):
        """Execute a script file in the yum shell.  The location of
        the script file is supplied by the :class:`cli.YumBaseCli`
        object that is passed as a parameter to the :class:`YumShell`
        object when it is created.
        """
        try:
            fd = open(self.file, 'r')
        except IOError:
            sys.exit("Error: Cannot open %s for reading" % self.file)
        lines = fd.readlines()
        fd.close()
        self.from_file = True
        for line in lines:
            self.onecmd(line)
        self.onecmd('EOF')
        return True
            
    def default(self, line):
        """Handle the next line of input if there is not a dedicated
        method of :class:`YumShell` to handle it.  This method will
        handle yum commands that are not unique to the shell, such as
        install, erase, etc.

        :param line: the next line of input
        """
        if len(line) > 0 and line.strip()[0] == '#':
            pass
        else:
            (cmd, args, line) = self.parseline(line)
            if cmd not in self.commandlist:
                xargs = [cmd]
                self.base.plugins.run('args', args=xargs)
                if xargs[0] == cmd:
                    self.do_help('')
                    return False
            if cmd == 'shell':
                return
            self.base.cmdstring = line
            self.base.cmdstring = self.base.cmdstring.replace('\n', '')
            self.base.cmds = self._shlex_split(self.base.cmdstring)
            self.base.plugins.run('args', args=self.base.cmds)

            self._shell_history_add_cmds(self.base.cmds)

            try:
                self.base.parseCommands()
            except Errors.YumBaseError:
                pass
            else:
                self.base.doCommands()
    
    def emptyline(self):
        """Do nothing on an empty line of input."""
        pass

    def completenames(self, text, line, begidx, endidx):
        """Return a list of possible completions of a command.

        :param text: the command to be completed
        :return: a list of possible completions of the command
        """
        ret = cmd.Cmd.completenames(self, text, line, begidx, endidx)
        for command in self.base.yum_cli_commands:
            if command.startswith(text) and command != "shell":
                ret.append(command)
        return ret

    def do_help(self, arg):
        """Output help information.

        :param arg: the command to ouput help information about. If
           *arg* is an empty string, general help will be output.
        """
        msg = """
    Shell specific arguments:
      config - set config options
      repository (or repo) - enable/disable/list repositories
      transaction (or ts) - list, reset or run the transaction set
      run - run the transaction set
      exit or quit - exit the shell
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
      list: lists repositories and their status. option = [all] name/id glob
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
        
        else:
            self.base.shellUsage()
        
        self.verbose_logger.info(msg)
        
    def do_EOF(self, line):
        """Exit the shell when EOF is reached.

        :param line: unused
        """
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_quit(self, line):
        """Exit the shell.

        :param line: unused
        """
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_exit(self, line):
        """Exit the shell.

        :param line: unused
        """
        self.resultmsgs = ['Leaving Shell']
        return True
    
    def do_ts(self, line):
        """Handle the ts alias of the :func:`do_transaction` method.

        :param line: the remainder of the line, containing the name of
           a subcommand.  If no subcommand is given, run the list subcommand.
        """
        self.do_transaction(line)

    def do_transaction(self, line):
        """Execute the given transaction subcommand.  The list
        subcommand outputs the contents of the transaction, the reset
        subcommand clears the transaction, the solve subcommand solves
        dependencies for the transaction, and the run subcommand
        executes the transaction.

        :param line: the remainder of the line, containing the name of
           a subcommand.  If no subcommand is given, run the list subcommand.
        """
        (cmd, args, line) = self.parseline(line)
        if cmd in ['list', None]:
            self.verbose_logger.log(logginglevels.INFO_2,
                self.base.listTransaction())
        
        elif cmd == 'reset':
            self.base.closeRpmDB()
        
        elif cmd == 'solve':
            try:
                (code, msgs) = self.base.buildTransaction()
            except Errors.YumBaseError, e:
                self.logger.critical('Error building transaction: %s', e)
                return False
                
            if code == 1:
                for msg in msgs:
                    self.logger.critical('Error: %s', msg)
            else:
                self.verbose_logger.log(logginglevels.INFO_2,
                    'Success resolving dependencies')
                
        elif cmd == 'run':
            return self.do_run('')
            
        else:
            self.do_help('transaction')
    
    def do_config(self, line):
        """Configure yum shell options.
        
        :param line: the remainder of the line, containing an option,
           and then optionally a value in the form [option] [value].
           Valid options are one of the following: debuglevel,
           errorlevel, obsoletes, gpgcheck, assumeyes, exclude.  If no
           value is given, print the current value.  If a value is
           supplied, set the option to the given value.
        """
        (cmd, args, line) = self.parseline(line)
        # logs
        if cmd in ['debuglevel', 'errorlevel']:
            opts = self._shlex_split(args)
            if not opts:
                self.verbose_logger.log(logginglevels.INFO_2, '%s: %s', cmd,
                    getattr(self.base.conf, cmd))
            else:
                val = opts[0]
                try:
                    val = int(val)
                except ValueError:
                    self.logger.critical('Value %s for %s cannot be made to an int', val, cmd)
                    return
                setattr(self.base.conf, cmd, val)
                if cmd == 'debuglevel':
                    logginglevels.setDebugLevel(val)
                elif cmd == 'errorlevel':
                    logginglevels.setErrorLevel(val)
        # bools
        elif cmd in ['gpgcheck', 'repo_gpgcheck', 'obsoletes', 'assumeyes']:
            opts = self._shlex_split(args)
            if not opts:
                self.verbose_logger.log(logginglevels.INFO_2, '%s: %s', cmd,
                    getattr(self.base.conf, cmd))
            else:
                value = opts[0]
                if value.lower() not in BOOLEAN_STATES:
                    self.logger.critical('Value %s for %s is not a Boolean', value, cmd)
                    return False
                value = BOOLEAN_STATES[value.lower()]
                setattr(self.base.conf, cmd, value)
                if cmd == 'obsoletes':
                    self.base.up = None
        
        elif cmd in ['exclude']:
            args = args.replace(',', ' ')
            opts = self._shlex_split(args)
            if not opts:
                msg = '%s: ' % cmd
                msg = msg + ' '.join(getattr(self.base.conf, cmd))
                self.verbose_logger.log(logginglevels.INFO_2, msg)
                return False
            else:
                setattr(self.base.conf, cmd, opts)
                if self.base.pkgSack:       # kill the pkgSack
                    self.base.pkgSack = None
                self.base.up = None         # reset the updates
                # reset the transaction set, we have to or we shall surely die!
                self.base.closeRpmDB() 
        else:
            self.do_help('config')

    def do_repository(self, line):
        """Handle the repository alias of the :func:`do_repo` method.

        :param line: the remainder of the line, containing the name of
           a subcommand.
        """
        self.do_repo(line)
        
    def do_repo(self, line):
        """Execute the given repo subcommand.  The list subcommand
        lists repositories and their statuses, the enable subcommand
        enables the given repository, and the disable subcommand
        disables the given repository.

        :param line: the remainder of the line, containing the name of
           a subcommand and other parameters if required.  If no
           subcommand is given, run the list subcommand.
        """
        (cmd, args, line) = self.parseline(line)
        if cmd in ['list', None]:
            # Munge things to run the repolist command
            cmds = self._shlex_split(args)

            if not cmds:
                cmds = ['enabled']
            cmds.insert(0, 'repolist')
            self.base.cmds = cmds

            self._shell_history_add_cmds(self.base.cmds)

            try:
                self.base.parseCommands()
            except Errors.YumBaseError:
                pass
            else:
                self.base.doCommands()

        elif cmd == 'enable':
            repos = self._shlex_split(args)
            for repo in repos:
                try:
                    #  Setup the sacks/repos, we need this because we are about
                    # to setup the enabled one. And having some setup is bad.
                    self.base.pkgSack
                    changed = self.base.repos.enableRepo(repo)
                except Errors.ConfigError, e:
                    self.logger.critical(e)
                except Errors.RepoError, e:
                    self.logger.critical(e)
                    
                else:
                    for repo in changed:
                        try:
                            self.base.doRepoSetup(thisrepo=repo)
                        except Errors.RepoError, e:
                            self.logger.critical('Disabling Repository')
                            self.base.repos.disableRepo(repo)
                            return False
                            
                    self.base.up = None
            
        elif cmd == 'disable':
            repos = self._shlex_split(args)
            for repo in repos:
                try:
                    offrepos = self.base.repos.disableRepo(repo)
                except Errors.ConfigError, e:
                    self.logger.critical(e)
                except Errors.RepoError, e:
                    self.logger.critical(e)

                else:
                    # close the repos, too
                    for repoid in offrepos:
                        thisrepo = self.base.repos.repos[repoid]
                        thisrepo.close()       # kill the pkgSack
            # rebuild the indexes to be sure we cleaned up
            self.base.pkgSack.buildIndexes()
            
        else:
            self.do_help('repo')
                
    def do_test(self, line):
        (cmd, args, line) = self.parseline(line)
        print cmd
        print args
        print line
        
    def do_run(self, line):
        """Run the transaction.

        :param line: unused
        """
        if len(self.base.tsInfo) > 0:
            try:
                (code, msgs) = self.base.buildTransaction()
                if code == 1:
                    for msg in msgs:
                        self.logger.critical('Error: %s', msg)
                    return False

                returnval = self.base.doTransaction()
            except Errors.YumBaseError, e:
                self.logger.critical('Error: %s', e)
            except KeyboardInterrupt, e:
                self.logger.critical('\n\nExiting on user cancel')
            except IOError, e:
                if e.errno == 32:
                    self.logger.critical('\n\nExiting on Broken Pipe')
            else:
                if returnval not in [0,1,-1]:
                    self.verbose_logger.info('Transaction encountered a serious error.')
                else:
                    if returnval == 1:
                        self.verbose_logger.info('There were non-fatal errors in the transaction')
                    elif returnval == -1:
                        self.verbose_logger.info("Transaction didn't start")
                    self.verbose_logger.log(logginglevels.INFO_2,
                        'Finished Transaction')
                self.base.closeRpmDB()


