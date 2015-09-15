# optparse.py
# CLI options parser.
#
# Copyright (C) 2014  Red Hat, Inc.
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

from __future__ import unicode_literals
from dnf.i18n import _

import argparse
import dnf
import dnf.exceptions
import dnf.yum.misc
import logging
import re
import sys

logger = logging.getLogger("dnf")


def error(self, msg):
    """Output an error message, and exit the program.  This method
    is overridden so that error output goes to the logger.

    :param msg: the error message to output
    """
    self.print_help()
    g = re.match(r"argument COMMAND: invalid choice: u'([^']*)'", msg)
    if g:
        cmd = g.groups(1)[0]
        logger.critical(_("\nNo such command: %s"), cmd)
        logger.info(_("It could be a DNF plugin command, "
                      "try: \"dnf install 'dnf-command(%s)'\""),
                    cmd)
    else:
        logger.critical(msg)
    raise dnf.cli.CliError


class OptionParser:
    """Subclass that makes some minor tweaks to make ArgumentParser do things the
    "yum way".
    """

    def __init__(self, **kwargs):
        self._cmd_usage = {} # names, summary for dnf commands, to build usage
        self._cmd_groups = set() # cmd groups added (main, plugin)
        # parent instance of Argument parser with dnf global switches
        self.opt_parser = None
        # main instance of Argument parser to which are subparsers applied
        self.argparser = None
        self._add_global_options()
        # bind the function to the object
        self.argparser.error = error.__get__(self.argparser)

    @staticmethod
    def _non_nones2dict(in_dct):
        dct = {k: in_dct[k] for k in in_dct
               if in_dct[k] is not None
               if in_dct[k] != []}
        return dct

    def configure_from_options(self, opts, conf, demands, output):
        """Configure parts of CLI from the opts. """

        options_to_move = ('best', 'assumeyes', 'assumeno',
                           'showdupesfromrepos', 'plugins', 'ip_resolve',
                           'rpmverbosity', 'disable_excludes')

        # transfer user specified options to conf
        for option_name in options_to_move:
            opt = getattr(opts, option_name)
            if opt is not None:
                setattr(conf, option_name, opt)

        if opts.allowerasing:
            demands.allow_erasing = opts.allowerasing

        try:
            # config file is parsed and moving us forward
            # set some things in it.
            if opts.installroot:
                self._checkAbsInstallRoot(opts.installroot)
                conf.installroot = opts.installroot

            demands.freshest_metadata = opts.freshest_metadata

            if opts.color not in (None, 'auto', 'always', 'never',
                                  'tty', 'if-tty', 'yes', 'no', 'on', 'off'):
                raise ValueError(_("--color takes one of: auto, always, never"))
            elif opts.color is None:
                if conf.color != 'auto':
                    output.term.reinit(color=conf.color)
            else:
                _remap = {'tty' : 'auto', 'if-tty' : 'auto',
                          '1' : 'always', 'true' : 'always',
                          'yes' : 'always', 'on' : 'always',
                          '0' : 'always', 'false' : 'always',
                          'no' : 'never', 'off' : 'never'}
                opts.color = _remap.get(opts.color, opts.color)
                if opts.color != 'auto':
                    output.term.reinit(color=opts.color)

            conf.exclude.extend(opts.excludepkgs)

        except ValueError as e:
            logger.critical(_('Options Error: %s'), e)
            self.argparser.print_help()
            sys.exit(1)

    @staticmethod
    def _checkAbsInstallRoot(installroot):
        if not installroot:
            return
        if installroot[0] == '/':
            return
        # We have a relative installroot ... haha
        logger.critical(_('--installroot must be an absolute path: %s'),
                             installroot)
        sys.exit(1)

    class _RepoCallback(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            operation = 'disable' if opt_str == '--disablerepo' else 'enable'
            l = getattr(namespace, self.dest)
            l.append((values, operation))

    class ParseSpecGroupFileCallback(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            setattr(namespace, "filenames", [])
            setattr(namespace, "grp_specs", [])
            setattr(namespace, "pkg_specs", [])
            for value in values:
                if value.endswith('.rpm'):
                    namespace.filenames.append(value)
                elif value.startswith('@'):
                    namespace.grp_specs.append(value[1:])
                else:
                    namespace.pkg_specs.append(value)

    class _SplitCallback(argparse.Action):
        """ Split all strings in seq, at "," and whitespace.
        Returns a new list. """
        def __call__(self, parser, namespace, values, opt_str):
            res = getattr(namespace, self.dest)
            res.extend(re.split("\s*,?\s*", values))

    class _SplitExtendDictCallback(argparse.Action):
        """ Split string at "," or whitespace to (key, value).
        Extends dict with {key: value}."""
        def __call__(self, parser, namespace, values, opt_str):
            try:
                key, val = values.split(',')
                if not key or not val:
                    raise ValueError
            except ValueError:
                msg = _('bad format: %s') % values
                raise argparse.ArgumentError(self, msg)
            dct = getattr(namespace, self.dest)
            dct[key] = val

    def _add_global_options(self):
        # All defaults need to be a None, so we can always tell whether the user
        # has set something or whether we are getting a default.

        opt_parser = argparse.ArgumentParser(add_help=False)
        opt_parser.add_argument(
            '--allowerasing', action='store_true',
            default=None,
            help=_('allow erasing of installed packages to '
                   'resolve dependencies'))
        opt_parser.add_argument(
            "-b", "--best", action="store_true",
            default=None,
            help=_("try the best available package versions in transactions."))
        opt_parser.add_argument("-C", "--cacheonly", dest="cacheonly",
                                action="store_true", default=None,
                                help=_("run entirely from system cache, "
                                       "don't update cache"))
        opt_parser.add_argument("-c", "--config", dest="conffile",
                                default=None, metavar='[config file]',
                                help=_("config file location"))
        opt_parser.add_argument("-d", "--debuglevel", dest="debuglevel",
                                metavar='[debug level]', default=None,
                                help=_("debugging output level"), type=int)
        opt_parser.add_argument(
            "--debugsolver", action="store_true", default=None,
            help=_("dumps detailed solving results into files"))
        opt_parser.add_argument("--showduplicates", dest="showdupesfromrepos",
                                action="store_true", default=None,
                                help=_("show duplicates, in repos, "
                                       "in list/search commands"))
        opt_parser.add_argument("-e", "--errorlevel", default=None, type=int,
                                help=_("error output level"))
        opt_parser.add_argument("--rpmverbosity", default=None,
                                help=_("debugging output level for rpm"),
                                metavar='[debug level name]')
        opt_parser.add_argument("-q", "--quiet", dest="quiet", default=None,
                                action="store_true", help=_("quiet operation"))
        opt_parser.add_argument("-v", "--verbose", action="store_true",
                                default=None, help=_("verbose operation"))
        opt_parser.add_argument("-y", "--assumeyes", action="store_true",
                                help=_("answer yes for all questions"),
                                default=None)
        opt_parser.add_argument("--assumeno", action="store_true",
                                help=_("answer no for all questions"),
                                default=None)
        opt_parser.add_argument("--version", action="store_true", default=None,
                                help=_("show DNF version and exit"))
        opt_parser.add_argument("--installroot", help=_("set install root"),
                                metavar='[path]')
        opt_parser.add_argument("--enablerepo", action=self._RepoCallback,
                                dest='repos_ed', default=[],
                                metavar='[repo]')
        repo_group = opt_parser.add_mutually_exclusive_group()
        repo_group.add_argument("--disablerepo", action=self._RepoCallback,
                                dest='repos_ed', default=[],
                                metavar='[repo]')
        repo_group.add_argument(
            '--repo', metavar='[repo]', action='append',
            help=_('enable just specific repositories by an id or a glob, '
                   'can be specified multiple times'))
        # compat: erase in 2.0.0 --repoid hidden compatibility alias for --repo
        repo_group.add_argument('--repoid', dest='repo', action='append',
                                help=argparse.SUPPRESS)
        opt_parser.add_argument("-x", "--exclude", default=[],
                                action=self._SplitCallback, dest='excludepkgs',
                                help=_("exclude packages by name or glob"),
                                metavar='[package]')
        opt_parser.add_argument("--disableexcludes", default=[],
                                dest="disable_excludes",
                                action=self._SplitCallback,
                                help=_("disable excludes"),
                                metavar='[repo]')
        opt_parser.add_argument("--repofrompath", default={},
                                action=self._SplitExtendDictCallback,
                                metavar='[repo,path]',
                                help=_("label and path to additional "
                                       "repository, can be specified multiple"
                                       "times."))
        opt_parser.add_argument("--noplugins", action="store_false",
                                default=None,
                                dest='plugins', help=_("disable all plugins"))
        opt_parser.add_argument("--nogpgcheck", action="store_true",
                                default=None,
                                help=_("disable gpg signature checking"))
        opt_parser.add_argument("--disableplugin", dest="disableplugins",
                                action=self._SplitCallback, default=[],
                                help=_("disable plugins by name"),
                                metavar='[plugin]')
        opt_parser.add_argument("--color", dest="color", default=None,
                                help=_("control whether color is used"))
        opt_parser.add_argument("--releasever", default=None,
                                help=_("override the value of $releasever in "
                                       "config and repo files"))
        opt_parser.add_argument(
            "--setopt", dest="setopts", default=[],
            action="append",
            help=_("set arbitrary config and repo options"))
        opt_parser.add_argument(
            "--refresh", dest="freshest_metadata",
            action="store_true",
            help=_("set metadata as expired before running the command"))
        opt_parser.add_argument("-4", dest="ip_resolve", default=None,
                                help=_("resolve to IPv4 addresses only"),
                                action="store_const", const='ipv4')
        opt_parser.add_argument("-6", dest="ip_resolve", default=None,
                                help=_("resolve to IPv6 addresses only"),
                                action="store_const", const='ipv6')
        opt_parser.add_argument("--downloadonly", dest="downloadonly",
                                action="store_true", default=False,
                                help=_("only download packages"))
        # we add our own help option, so we can control that help is not shown
        # automatic when we do the .parse_known_args(args)
        # but first after plugins are loaded.
        opt_parser.add_argument('-h', '--help', action="store_true",
                                help="show help")
        opt_parser.add_argument('--help-cmd', action="store_true",
                                help="show command help")
        self.argparser = argparse.ArgumentParser(
            self, add_help=False,
            usage="dnf [options] COMMAND", parents=[opt_parser])
        self.opt_parser = opt_parser

    def _add_cmd_usage(self, cmd, group):
        """ store usage info about a single dnf command."""
        summary = dnf.i18n.ucd(cmd.summary)
        name = dnf.i18n.ucd(cmd.aliases[0])
        if not name in self._cmd_usage:
            self._cmd_usage[name] = (group, summary)
            self._cmd_groups.add(group)

    def add_commands(self, cli_cmds, group):
        """ store name & summary for dnf commands

        The stored information is used build usage information
        grouped by build-in & plugin commands.
        """
        for cmd in set(cli_cmds.values()):
            self._add_cmd_usage(cmd, group)

    def init_subparser_commands(self, commands):
        subparsers = self.argparser.add_subparsers(dest="cmd",
                                                   metavar="COMMAND",
                                                   help=argparse.SUPPRESS)
        for cmd in commands:
            kwargs = {}
            if cmd.usage:
                kwargs["usage"] = cmd.usage
            if cmd.summary:
                kwargs["description"] = cmd.summary
            # in python2 aliases are not supported
            # TODO when python2 is gone: add aliases=cmd.aliases[1:]
            for alias in cmd.aliases:
                parser = subparsers.add_parser(alias, add_help=False,
                                               parents=[self.opt_parser],
                                               **kwargs)
                if getattr(cmd, "set_argparse_subparser", None):
                    cmd.set_argparse_subparser(parser)
                cmd.parser = parser

    def get_usage(self):
        """ get the usage information to show the user. """
        desc = {'main': _('List of Main Commands'),
                'plugin': _('List of Plugin Commands')}
        name = dnf.const.PROGRAM_NAME
        usage = '%s [options] COMMAND\n' % name
        for grp in ['main', 'plugin']:
            if not grp in self._cmd_groups:  # dont add plugin usage, if we dont have plugins
                continue
            usage += "\n%s\n\n" % desc[grp]
            for name in sorted(self._cmd_usage.keys()):
                group, summary = self._cmd_usage[name]
                if group == grp:
                    usage += "%-25s %s\n" % (name, summary)
        return usage
