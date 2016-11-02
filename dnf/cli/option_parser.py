# optparse.py
# CLI options parser.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
import dnf.exceptions
import dnf.yum.misc
import logging
import os.path
import re
import sys

logger = logging.getLogger("dnf")

class OptionParser(argparse.ArgumentParser):
    """ArgumentParser like class to do things the "yum way"."""

    def __init__(self):
        super(OptionParser, self).__init__()
        self._cmd_usage = {} # names, summary for dnf commands, to build usage
        self._cmd_groups = set() # cmd groups added (main, plugin)
        self.main_parser = self._main_parser()
        self.command_arg_parser = None

    def error(self, msg):
        """Output an error message, and exit the program.
           This method overrides standard argparser's error
           so that error output goes to the logger.

        :param msg: the error message to output
        """
        self.print_usage()
        logger.critical(_("Command line error: %s"), msg)
        sys.exit(1)

    class _RepoCallback(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            operation = 'disable' if opt_str == '--disablerepo' else 'enable'
            l = getattr(namespace, self.dest)
            l.extend((x, operation) for x in re.split(r'\s*[,\s]\s*', values))

    class _RepoCallbackEnable(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            namespace.repos_ed.append((values[0], 'enable'))
            setattr(namespace, 'reponame', values)

    class _SplitCallback(argparse._AppendAction):
        """ Split all strings in seq, at "," and whitespace.
        Returns a new list. """
        def __call__(self, parser, namespace, values, opt_str):
            for val in re.split(r'\s*[,\s]\s*', values):
                super(OptionParser._SplitCallback,
                      self).__call__(parser, namespace, val, opt_str)

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

    class _SetoptsCallback(argparse.Action):
        """ Parse setopts arguments and put them into main_<setopts>
            and repo_<setopts>."""
        def __init__(self, *args, **kwargs):
            super(OptionParser._SetoptsCallback, self).__init__(*args, **kwargs)
            self.repoopts = {}
            self.mainopts = argparse.Namespace()

        def __call__(self, parser, namespace, values, opt_str):
            vals = values.split('=')
            if len(vals) > 2:
                logger.warning("Setopt argument has multiple values: %s", values)
                return
            if len(vals) < 2:
                logger.warning("Setopt argument has no value: %s", values)
                return
            k, v = vals
            period = k.find('.')
            if period != -1:
                repo = k[:period]
                k = k[period+1:]
                if repo not in self.repoopts:
                    self.repoopts[repo] = argparse.Namespace()
                setattr(self.repoopts[repo], k, v)
                setattr(namespace, 'repo_' + self.dest, self.repoopts)
            else:
                setattr(self.mainopts, k, v)
                setattr(namespace, k, v)
                setattr(namespace, 'main_' + self.dest, self.mainopts)

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

    class PkgNarrowCallback(argparse.Action):
        def __init__(self, *args, **kwargs):
            self.pkgnarrow = {}
            try:
                for k in ['choices', 'default']:
                    self.pkgnarrow[k] = kwargs[k]
                    del kwargs[k]
            except KeyError as e:
                raise TypeError("%s() missing mandatory argument %s"
                                % (self.__class__.__name__, e))
            kwargs['default'] = []
            super(OptionParser.PkgNarrowCallback, self).__init__(*args, **kwargs)

        def __call__(self, parser, namespace, values, opt_str):
            dest_action = self.dest + '_action'
            if not values or values[0] not in self.pkgnarrow['choices']:
                narrow = self.pkgnarrow['default']
            else:
                narrow = values.pop(0)
            setattr(namespace, dest_action, narrow)
            setattr(namespace, self.dest, values)

    def _main_parser(self):
        """ Standard options known to all dnf subcommands. """
        # All defaults need to be a None, so we can always tell whether the user
        # has set something or whether we are getting a default.
        main_parser = argparse.ArgumentParser(dnf.const.PROGRAM_NAME,
                                              add_help=False)
        main_parser.add_argument("-c", "--config", dest="config_file_path",
                                 default=None, metavar='[config file]',
                                 help=_("config file location"))
        main_parser.add_argument("-q", "--quiet", dest="quiet",
                                 action="store_true", default=None,
                                 help=_("quiet operation"))
        main_parser.add_argument("-v", "--verbose", action="store_true",
                                 default=None, help=_("verbose operation"))
        main_parser.add_argument("--version", action="store_true", default=None,
                                 help=_("show DNF version and exit"))
        main_parser.add_argument("--installroot", help=_("set install root"),
                                 metavar='[path]')
        main_parser.add_argument("--noplugins", action="store_false",
                                 default=None, dest='plugins',
                                 help=_("disable all plugins"))
        main_parser.add_argument("--disableplugins", dest="disableplugins",
                                 default=[], action=self._SplitCallback,
                                 help=_("disable plugins by name"),
                                 metavar='[plugin]')
        main_parser.add_argument("--releasever", default=None,
                                 help=_("override the value of $releasever"
                                        " in config and repo files"))
        main_parser.add_argument("--setopt", dest="setopts", default=[],
                                 action=self._SetoptsCallback,
                                 help=_("set arbitrary config and repo options"))
        main_parser.add_argument('-h', '--help', '--help-cmd',
                                 action="store_true", dest='help',
                                 help=_("show command help"))

        main_parser.add_argument('--allowerasing', action='store_true',
                                 default=None,
                                 help=_('allow erasing of installed packages to '
                                        'resolve dependencies'))
        main_parser.add_argument("-b", "--best", action="store_true",
                                 default=None,
                                 help=_("try the best available package "
                                        "versions in transactions."))
        main_parser.add_argument("-C", "--cacheonly", dest="cacheonly",
                                 action="store_true", default=None,
                                 help=_("run entirely from system cache, "
                                        "don't update cache"))
        main_parser.add_argument("-d", "--debuglevel", dest="debuglevel",
                                 metavar='[debug level]', default=None,
                                 help=_("debugging output level"), type=int)
        main_parser.add_argument("--debugsolver",
                                 action="store_true", default=None,
                                 help=_("dumps detailed solving results into"
                                        " files"))
        main_parser.add_argument("--showduplicates", dest="showdupesfromrepos",
                                 action="store_true", default=None,
                                 help=_("show duplicates, in repos, "
                                        "in list/search commands"))
        main_parser.add_argument("-e", "--errorlevel", default=None, type=int,
                                 help=_("error output level"))
        main_parser.add_argument("--rpmverbosity", default=None,
                                 help=_("debugging output level for rpm"),
                                 metavar='[debug level name]')
        main_parser.add_argument("-y", "--assumeyes", action="store_true",
                                 default=None, help=_("automatically answer yes"
                                                      " for all questions"))
        main_parser.add_argument("--assumeno", action="store_true",
                                 default=None, help=_("automatically answer no"
                                                      " for all questions"))
        main_parser.add_argument("--enablerepo", action=self._RepoCallback,
                                 dest='repos_ed', default=[],
                                 metavar='[repo]')
        repo_group = main_parser.add_mutually_exclusive_group()
        repo_group.add_argument("--disablerepo", action=self._RepoCallback,
                                dest='repos_ed', default=[],
                                metavar='[repo]')
        repo_group.add_argument('--repo', metavar='[repo]',
                                action=self._SplitCallback, default=[],
                                help=_('enable just specific repositories '
                                       'by an id or a glob, '
                                       'can be specified multiple times'))
        main_parser.add_argument("-x", "--exclude", "--excludepkgs", default=[],
                                 dest='excludepkgs', action=self._SplitCallback,
                                 help=_("exclude packages by name or glob"),
                                 metavar='[package]')
        main_parser.add_argument("--disableexcludes", "--disableexcludepkgs",
                                 default=[], dest="disable_excludes",
                                 action=self._SplitCallback,
                                 help=_("disable excludepkgs"),
                                 metavar='[repo]')
        main_parser.add_argument("--repofrompath", default={},
                                 action=self._SplitExtendDictCallback,
                                 metavar='[repo,path]',
                                 help=_("label and path to additional repository,"
                                        " can be specified multiple times."))
        main_parser.add_argument("--nogpgcheck", action="store_false",
                                 default=None, dest='gpgcheck',
                                 help=_("disable gpg signature checking"))
        main_parser.add_argument("--color", dest="color", default=None,
                                 help=_("control whether color is used"))
        main_parser.add_argument("--refresh", dest="freshest_metadata",
                                 action="store_true",
                                 help=_("set metadata as expired before running"
                                        " the command"))
        main_parser.add_argument("-4", dest="ip_resolve", default=None,
                                 help=_("resolve to IPv4 addresses only"),
                                 action="store_const", const='ipv4')
        main_parser.add_argument("-6", dest="ip_resolve", default=None,
                                 help=_("resolve to IPv6 addresses only"),
                                 action="store_const", const='ipv6')
        main_parser.add_argument("--downloadonly", dest="downloadonly",
                                 action="store_true", default=False,
                                 help=_("only download packages"))
        # Updateinfo options...
        main_parser.add_argument("--bugfix", action="store_true",
                                 help=_("Include bugfix relevant packages, "
                                        "in updates"))
        main_parser.add_argument("--enhancement", action="store_true",
                                 help=_("Include enhancement relevant packages,"
                                        " in updates"))
        main_parser.add_argument("--newpackage", action="store_true",
                                 help=_("Include newpackage relevant packages,"
                                        " in updates"))
        main_parser.add_argument("--security", action="store_true",
                                 help=_("Include security relevant packages, "
                                        "in updates"))
        main_parser.add_argument("--advisory", "--advisories", dest="advisory",
                                 default=[], action="append",
                                 help=_("Include packages needed to fix the "
                                        "given advisory, in updates"))
        main_parser.add_argument("--bzs", default=[], dest="bugzilla",
                                 action="append", help=_(
                "Include packages needed to fix the given BZ, in updates"))
        main_parser.add_argument("--cves", default=[], action="append", help=_(
            "Include packages needed to fix the given CVE, in updates"))
        main_parser.add_argument(
            "--sec-severity", "--secseverity",
            choices=['Critical', 'Important', 'Moderate', 'Low'], default=[],
            dest="severity", action="append", help=_(
                "Include security relevant packages matching the severity, "
                "in updates"))
        return main_parser

    def _command_parser(self, command):
        prog = "%s %s" % (dnf.const.PROGRAM_NAME, command._basecmd)
        super(OptionParser, self).__init__(prog, add_help=False,
                                           parents=[self.main_parser],
                                           description=command.summary)
        super(OptionParser, self).add_argument('command', nargs=1,
                                               help=argparse.SUPPRESS)
        self.command_arg_parser = argparse.ArgumentParser(prog, add_help=False)
        self.command_arg_parser.print_usage = self.print_usage
        command.set_argparser(self)
        return self

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

    def get_usage(self):
        """ get the usage information to show the user. """
        desc = {'main': _('List of Main Commands'),
                'plugin': _('List of Plugin Commands')}
        name = dnf.const.PROGRAM_NAME
        usage = '%s [options] COMMAND\n' % name
        for grp in ['main', 'plugin']:
            if not grp in self._cmd_groups:
                # dont add plugin usage, if we dont have plugins
                continue
            usage += "\n%s\n\n" % desc[grp]
            for name in sorted(self._cmd_usage.keys()):
                group, summary = self._cmd_usage[name]
                if group == grp:
                    usage += "%-25s %s\n" % (name, summary)
        return usage

    def add_argument(self, *args, **kwargs):
        # process options and arguments separately
        if all([(arg[0] in self.prefix_chars) for arg in args]):
            return super(OptionParser, self).add_argument(*args, **kwargs)
        else:
            return self.command_arg_parser.add_argument(*args, **kwargs)

    def parse_main_args(self, args):
        parser = argparse.ArgumentParser(dnf.const.PROGRAM_NAME, add_help=False,
                                         parents=[self.main_parser])
        parser.add_argument('command', nargs='?', help=argparse.SUPPRESS)
        namespace, _unused_args = parser.parse_known_args(args)
        return namespace

    def parse_command_args(self, command, args):
        self._command_parser(command)
        namespace, extras = super(OptionParser,
                                  self).parse_known_args(args)
        command.opts = self.command_arg_parser.parse_args(extras, namespace)
        return command.opts

    def print_usage(self, file_=None):
        # pylint: disable=E0202,W0212
        self._actions += self.command_arg_parser._actions
        super(OptionParser, self).print_usage(file_)

    def print_help(self, command=None):
        # pylint: disable=W0212
        if command:
            cp = self._command_parser(command)
            cp._actions += cp.command_arg_parser._actions
            super(OptionParser, cp).print_help()
        else:
            self.main_parser.usage = self.get_usage()
            self.main_parser.print_help()
