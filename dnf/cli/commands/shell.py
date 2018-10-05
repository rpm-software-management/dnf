# shell.py
# Shell CLI command.
#
# Copyright (C) 2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from dnf.cli import commands
from dnf.i18n import _


import cmd
import copy
import dnf
import logging
import shlex
import sys


logger = logging.getLogger('dnf')


# only demands we'd like to override
class ShellDemandSheet(object):
    available_repos = True
    resolving = True
    root_user = True
    sack_activation = True


class ShellCommand(commands.Command, cmd.Cmd):

    aliases = ('shell',)
    summary = _('run an interactive DNF shell')

    MAPPING = {'repo': 'repo',
               'repository': 'repo',
               'exit': 'quit',
               'quit': 'quit',
               'run': 'ts_run',
               'ts': 'transaction',
               'transaction': 'transaction',
               'config': 'config',
               'resolvedep': 'resolve',
               'help': 'help'
               }

    def __init__(self, cli):
        commands.Command.__init__(self, cli)
        cmd.Cmd.__init__(self)
        self.prompt = '> '

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('script', nargs='?', metavar=_('SCRIPT'),
                            help=_('Script to run in DNF shell'))

    def configure(self):
        # append to ShellDemandSheet missing demands from
        # dnf.cli.demand.DemandSheet with their default values.
        default_demands = self.cli.demands
        self.cli.demands = ShellDemandSheet()
        for attr in dir(default_demands):
            if attr.startswith('__'):
                continue
            try:
                getattr(self.cli.demands, attr)
            except AttributeError:
                setattr(self.cli.demands, attr, getattr(default_demands, attr))

    def run(self):
        if self.opts.script:
            self._run_script(self.opts.script)
        else:
            self.cmdloop()

    def _clean(self):
        self.base._finalize_base()
        self.base._transaction = None
        self.base.fill_sack()

    def onecmd(self, line):
        if not line or line == '\n':
            return
        if line == 'EOF':
            line = 'quit'
        try:
            s_line = shlex.split(line)
        except:
            self._help()
            return
        opts = self.cli.optparser.parse_main_args(s_line)
        # Disable shell recursion.
        if opts.command == 'shell':
            return
        if opts.command in self.MAPPING:
            getattr(self, '_' + self.MAPPING[opts.command])(s_line[1::])
        else:
            cmd_cls = self.cli.cli_commands.get(opts.command)
            if cmd_cls is not None:
                cmd = cmd_cls(self.cli)
                try:
                    opts = self.cli.optparser.parse_command_args(cmd, s_line)
                    cmd.cli.demands = copy.deepcopy(self.cli.demands)
                    cmd.configure()
                    cmd.run()
                except dnf.exceptions.Error as e:
                    logger.error(_("Error:") + " " + e.value)
                except:
                    return
            else:
                self._help()

    def _config(self, args=None):
        def print_or_set(key, val, conf):
            if val:
                setattr(conf, key, val)
            else:
                try:
                    print('{}: {}'.format(key, getattr(conf, str(key))))
                except:
                    logger.warning(_('Unsupported key value.'))

        if not args or len(args) > 2:
            self._help('config')
            return

        key = args[0]
        val = args[1] if len(args) == 2 else None
        period = key.find('.')
        if period != -1:
            repo_name = key[:period]
            key = key[period+1:]
            repos = self.base.repos.get_matching(repo_name)
            for repo in repos:
                print_or_set(key, val, repo)
            if not repos:
                logger.warning(_('Could not find repository: %s'),
                               repo_name)
        else:
            print_or_set(key, val, self.base.conf)

    def _help(self, args=None):
        """Output help information.

        :param args: the command to output help information about. If
           *args* is an empty, general help will be output.
        """
        arg = args[0] if isinstance(args, list) and len(args) > 0 else args
        msg = None

        if arg:
            if arg == 'config':
                msg = _("""{} arg [value]
  arg: debuglevel, errorlevel, obsoletes, gpgcheck, assumeyes, exclude,
        repo_id.gpgcheck, repo_id.exclude
    If no value is given it prints the current value.
    If value is given it sets that value.""").format(arg)

            elif arg == 'help':
                msg = _("""{} [command]
    print help""").format(arg)

            elif arg in ['repo', 'repository']:
                msg = _("""{} arg [option]
  list: lists repositories and their status. option = [all | id | glob]
  enable: enable repositories. option = repository id
  disable: disable repositories. option = repository id""").format(arg)

            elif arg == 'resolvedep':
                msg = _("""{}
    resolve the transaction set""").format(arg)

            elif arg in ['transaction', 'ts']:
                msg = _("""{} arg
  list: lists the contents of the transaction
  reset: reset (zero-out) the transaction
  run: run the transaction""").format(arg)

            elif arg == 'run':
                msg = _("""{}
    run the transaction""").format(arg)

            elif arg in ['exit', 'quit']:
                msg = _("""{}
    exit the shell""").format(arg)

        if not msg:
            self.cli.optparser.print_help()
            msg = _("""Shell specific arguments:

config                   set config options
help                     print help
repository (or repo)     enable, disable or list repositories
resolvedep               resolve the transaction set
transaction (or ts)      list, reset or run the transaction set
run                      resolve and run the transaction set
exit (or quit)           exit the shell""")

        print('\n' + msg)

    def _repo(self, args=None):
        cmd = args[0] if args else None

        if cmd in ['list', None]:
            self.onecmd('repolist ' + ' '.join(args[1:]))

        elif cmd in ['enable', 'disable']:
            repos = self.cli.base.repos
            fill_sack = False
            for repo in args[1::]:
                r = repos.get_matching(repo)
                if r:
                    getattr(r, cmd)()
                    fill_sack = True
                else:
                    logger.critical(_("Error:") + " " + _("Unknown repo: '%s'"),
                                    self.base.output.term.bold(repo))
            if fill_sack:
                self.base.fill_sack()

        else:
            self._help('repo')

    def _resolve(self, args=None):
        if self.cli.base.transaction is None:
            try:
                self.cli.base.resolve(self.cli.demands.allow_erasing)
            except dnf.exceptions.DepsolveError as e:
                print(e)

    def _run_script(self, file):
        try:
            with open(file, 'r') as fd:
                lines = fd.readlines()
                for line in lines:
                    if not line.startswith('#'):
                        self.onecmd(line)
        except IOError:
            logger.info(_('Error: Cannot open %s for reading'), self.base.output.term.bold(file))
            sys.exit(1)

    def _transaction(self, args=None):
        cmd = args[0] if args else None

        if cmd == 'reset':
            self._clean()
            return

        self._resolve()
        if cmd in ['list', None]:
            if self.base._transaction:
                out = self.base.output.list_transaction(self.base._transaction)
                logger.info(out)

        elif cmd == 'run':
            try:
                self.base.do_transaction()
            except:
                pass
            self._clean()

        else:
            self._help('transaction')

    def _ts_run(self, args=None):
        self._transaction(['run'])

    def _quit(self, args=None):
        logger.info(_('Leaving Shell'))
        sys.exit(0)
