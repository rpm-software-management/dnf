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
from dnf.util import _parse_specs

import argparse
import dnf.exceptions
import dnf.util
import dnf.rpm
import dnf.yum.misc
import logging
import os.path
import re
import sys

logger = logging.getLogger("dnf")


class MultilineHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if '\n' in text:
            return text.splitlines()
        return super(MultilineHelpFormatter, self)._split_lines(text, width)

class OptionParser(argparse.ArgumentParser):
    """ArgumentParser like class to do things the "yum way"."""

    def __init__(self, reset_usage=True):
        super(OptionParser, self).__init__(add_help=False,
                                           formatter_class=MultilineHelpFormatter)
        self.command_positional_parser = None
        self.command_group = None
        self._add_general_options()
        if reset_usage:
            self._cmd_usage = {}      # names, summary for dnf commands, to build usage
            self._cmd_groups = set()  # cmd groups added (main, plugin)

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
        SPLITTER = r'\s*[,\s]\s*'

        def __call__(self, parser, namespace, values, opt_str):
            first = True
            for val in re.split(self.SPLITTER, values):
                if first or val:
                    # Empty values are sometimes used to clear existing content of the option.
                    # Only the first value in the parsed string can be empty. Other empty values
                    # are ignored.
                    super(OptionParser._SplitCallback,
                          self).__call__(parser, namespace, val, opt_str)
                first = False

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
        def __call__(self, parser, namespace, values, opt_str):
            vals = values.split('=')
            if len(vals) > 2:
                logger.warning(_("Setopt argument has multiple values: %s"), values)
                return
            if len(vals) < 2:
                logger.warning(_("Setopt argument has no value: %s"), values)
                return
            k, v = vals
            period = k.rfind('.')
            if period != -1:
                repo = k[:period]
                k = k[period+1:]
                if hasattr(namespace, 'repo_setopts'):
                    repoopts = namespace.repo_setopts
                else:
                    repoopts = {}
                repoopts.setdefault(repo, {}).setdefault(k, []).append(v)
                setattr(namespace, 'repo_' + self.dest, repoopts)
            else:
                if hasattr(namespace, 'main_setopts'):
                    mainopts = namespace.main_setopts
                else:
                    mainopts = {}
                mainopts.setdefault(k, []).append(v)
                setattr(namespace, 'main_' + self.dest, mainopts)

    class ParseSpecGroupFileCallback(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            _parse_specs(namespace, values)

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

    class ForceArchAction(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            namespace.ignorearch = True
            namespace.arch = values

    def _add_general_options(self):
        """ Standard options known to all dnf subcommands. """
        # All defaults need to be a None, so we can always tell whether the user
        # has set something or whether we are getting a default.
        general_grp = self.add_argument_group(_('General {prog} options'.format(
            prog=dnf.util.MAIN_PROG_UPPER)))
        general_grp.add_argument("-c", "--config", dest="config_file_path",
                                 default=None, metavar='[config file]',
                                 help=_("config file location"))
        general_grp.add_argument("-q", "--quiet", dest="quiet",
                                 action="store_true", default=None,
                                 help=_("quiet operation"))
        general_grp.add_argument("-v", "--verbose", action="store_true",
                                 default=None, help=_("verbose operation"))
        general_grp.add_argument("--version", action="store_true", default=None,
                                 help=_("show {prog} version and exit").format(
                                     prog=dnf.util.MAIN_PROG_UPPER))
        general_grp.add_argument("--installroot", help=_("set install root"),
                                 metavar='[path]')
        general_grp.add_argument("--nodocs", action="store_const", const=['nodocs'], dest='tsflags',
                                 help=_("do not install documentations"))
        general_grp.add_argument("--noplugins", action="store_false",
                                 default=None, dest='plugins',
                                 help=_("disable all plugins"))
        general_grp.add_argument("--enableplugin", dest="enableplugin",
                                 default=[], action=self._SplitCallback,
                                 help=_("enable plugins by name"),
                                 metavar='[plugin]')
        general_grp.add_argument("--disableplugin", dest="disableplugin",
                                 default=[], action=self._SplitCallback,
                                 help=_("disable plugins by name"),
                                 metavar='[plugin]')
        general_grp.add_argument("--releasever", default=None,
                                 help=_("override the value of $releasever"
                                        " in config and repo files"))
        general_grp.add_argument("--setopt", dest="setopts", default=[],
                                 action=self._SetoptsCallback,
                                 help=_("set arbitrary config and repo options"))
        general_grp.add_argument("--skip-broken", dest="skip_broken", action="store_true",
                                 default=None,
                                 help=_("resolve depsolve problems by skipping packages"))
        general_grp.add_argument('-h', '--help', '--help-cmd',
                                 action="store_true", dest='help',
                                 help=_("show command help"))

        general_grp.add_argument('--allowerasing', action='store_true',
                                 default=None,
                                 help=_('allow erasing of installed packages to '
                                        'resolve dependencies'))
        best_group = general_grp.add_mutually_exclusive_group()
        best_group.add_argument("-b", "--best", action="store_true", dest='best', default=None,
                                help=_("try the best available package versions in transactions."))
        best_group.add_argument("--nobest", action="store_false", dest='best',
                                help=_("do not limit the transaction to the best candidate"))
        general_grp.add_argument("-C", "--cacheonly", dest="cacheonly",
                                 action="store_true", default=None,
                                 help=_("run entirely from system cache, "
                                        "don't update cache"))
        general_grp.add_argument("-R", "--randomwait", dest="sleeptime", type=int,
                                 default=None, metavar='[minutes]',
                                 help=_("maximum command wait time"))
        general_grp.add_argument("-d", "--debuglevel", dest="debuglevel",
                                 metavar='[debug level]', default=None,
                                 help=_("debugging output level"), type=int)
        general_grp.add_argument("--debugsolver",
                                 action="store_true", default=None,
                                 help=_("dumps detailed solving results into"
                                        " files"))
        general_grp.add_argument("--showduplicates", dest="showdupesfromrepos",
                                 action="store_true", default=None,
                                 help=_("show duplicates, in repos, "
                                        "in list/search commands"))
        general_grp.add_argument("-e", "--errorlevel", default=None, type=int,
                                 help=_("error output level"))
        general_grp.add_argument("--obsoletes", default=None, dest="obsoletes",
                                 action="store_true",
                                 help=_("enables {prog}'s obsoletes processing logic "
                                        "for upgrade or display capabilities that "
                                        "the package obsoletes for info, list and "
                                        "repoquery").format(prog=dnf.util.MAIN_PROG))
        general_grp.add_argument("--rpmverbosity", default=None,
                                 help=_("debugging output level for rpm"),
                                 metavar='[debug level name]')
        general_grp.add_argument("-y", "--assumeyes", action="store_true",
                                 default=None, help=_("automatically answer yes"
                                                      " for all questions"))
        general_grp.add_argument("--assumeno", action="store_true",
                                 default=None, help=_("automatically answer no"
                                                      " for all questions"))
        general_grp.add_argument("--enablerepo", action=self._RepoCallback,
                                 dest='repos_ed', default=[], metavar='[repo]',
                                 help=_("Enable additional repositories. List option. "
                                        "Supports globs, can be specified multiple times."))
        repo_group = general_grp.add_mutually_exclusive_group()
        repo_group.add_argument("--disablerepo", action=self._RepoCallback,
                                dest='repos_ed', default=[], metavar='[repo]',
                                help=_("Disable repositories. List option. "
                                       "Supports globs, can be specified multiple times."))
        repo_group.add_argument('--repo', '--repoid', metavar='[repo]', dest='repo',
                                action=self._SplitCallback, default=[],
                                help=_('enable just specific repositories by an id or a glob, '
                                       'can be specified multiple times'))
        enable_group = general_grp.add_mutually_exclusive_group()
        enable_group.add_argument("--enable", "--set-enabled", default=False,
                                  dest="set_enabled", action="store_true",
                                  help=_("enable repos with config-manager "
                                         "command (automatically saves)"))
        enable_group.add_argument("--disable", "--set-disabled", default=False,
                                  dest="set_disabled", action="store_true",
                                  help=_("disable repos with config-manager "
                                         "command (automatically saves)"))
        general_grp.add_argument("-x", "--exclude", "--excludepkgs", default=[],
                                 dest='excludepkgs', action=self._SplitCallback,
                                 help=_("exclude packages by name or glob"),
                                 metavar='[package]')
        general_grp.add_argument("--disableexcludes", "--disableexcludepkgs",
                                 default=[], dest="disable_excludes",
                                 action=self._SplitCallback,
                                 help=_("disable excludepkgs"),
                                 metavar='[repo]')
        general_grp.add_argument("--repofrompath", default={},
                                 action=self._SplitExtendDictCallback,
                                 metavar='[repo,path]',
                                 help=_("label and path to an additional repository to use (same "
                                        "path as in a baseurl), can be specified multiple times."))
        general_grp.add_argument("--noautoremove", action="store_false",
                                 default=None, dest='clean_requirements_on_remove',
                                 help=_("disable removal of dependencies that are no longer used"))
        general_grp.add_argument("--nogpgcheck", action="store_false",
                                 default=None, dest='gpgcheck',
                                 help=_("disable gpg signature checking (if RPM policy allows)"))
        general_grp.add_argument("--color", dest="color", default=None,
                                 help=_("control whether color is used"))
        general_grp.add_argument("--refresh", dest="freshest_metadata",
                                 action="store_true",
                                 help=_("set metadata as expired before running"
                                        " the command"))
        general_grp.add_argument("-4", dest="ip_resolve", default=None,
                                 help=_("resolve to IPv4 addresses only"),
                                 action="store_const", const='ipv4')
        general_grp.add_argument("-6", dest="ip_resolve", default=None,
                                 help=_("resolve to IPv6 addresses only"),
                                 action="store_const", const='ipv6')
        general_grp.add_argument("--destdir", "--downloaddir", dest="destdir", default=None,
                                 help=_("set directory to copy packages to"))
        general_grp.add_argument("--downloadonly", dest="downloadonly",
                                 action="store_true", default=False,
                                 help=_("only download packages"))
        general_grp.add_argument("--comment", dest="comment", default=None,
                                 help=_("add a comment to transaction"))
        # Updateinfo options...
        general_grp.add_argument("--bugfix", action="store_true",
                                 help=_("Include bugfix relevant packages, "
                                        "in updates"))
        general_grp.add_argument("--enhancement", action="store_true",
                                 help=_("Include enhancement relevant packages,"
                                        " in updates"))
        general_grp.add_argument("--newpackage", action="store_true",
                                 help=_("Include newpackage relevant packages,"
                                        " in updates"))
        general_grp.add_argument("--security", action="store_true",
                                 help=_("Include security relevant packages, "
                                        "in updates"))
        general_grp.add_argument("--advisory", "--advisories", dest="advisory",
                                 default=[], action=self._SplitCallback,
                                 help=_("Include packages needed to fix the "
                                        "given advisory, in updates"))
        general_grp.add_argument("--bz", "--bzs", default=[], dest="bugzilla",
                                 action=self._SplitCallback, help=_(
                "Include packages needed to fix the given BZ, in updates"))
        general_grp.add_argument("--cve", "--cves", default=[], dest="cves",
                                 action=self._SplitCallback,
                                 help=_("Include packages needed to fix the given CVE, in updates"))
        general_grp.add_argument(
            "--sec-severity", "--secseverity",
            choices=['Critical', 'Important', 'Moderate', 'Low'], default=[],
            dest="severity", action=self._SplitCallback, help=_(
                "Include security relevant packages matching the severity, "
                "in updates"))
        general_grp.add_argument("--forcearch", metavar="ARCH",
                                 dest=argparse.SUPPRESS,
                                 action=self.ForceArchAction,
                                 choices=sorted(dnf.rpm._BASEARCH_MAP.keys()),
                                 help=_("Force the use of an architecture"))
        general_grp.add_argument('command', nargs='?', help=argparse.SUPPRESS)

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
        desc = {'main': _('List of Main Commands:'),
                'plugin': _('List of Plugin Commands:')}
        usage = '%s [options] COMMAND\n' % dnf.util.MAIN_PROG
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

    def _add_command_options(self, command):
        self.prog = "%s %s" % (dnf.util.MAIN_PROG, command._basecmd)
        self.description = command.summary
        self.command_positional_parser = argparse.ArgumentParser(self.prog, add_help=False)
        self.command_positional_parser.print_usage = self.print_usage
        self.command_positional_parser._positionals.title = None
        self.command_group = self.add_argument_group(
            '{} command-specific options'.format(command._basecmd.capitalize()))
        self.command_group.add_argument = self.cmd_add_argument
        self.command_group._command = command._basecmd
        command.set_argparser(self.command_group)

    def cmd_add_argument(self, *args, **kwargs):
        if all([(arg[0] in self.prefix_chars) for arg in args]):
            return type(self.command_group).add_argument(self.command_group, *args, **kwargs)
        else:
            return self.command_positional_parser.add_argument(*args, **kwargs)

    def _check_encoding(self, args):
        for arg in args:
            try:
                arg.encode('utf-8')
            except UnicodeEncodeError as e:
                raise dnf.exceptions.ConfigError(
                    _("Cannot encode argument '%s': %s") % (arg, str(e)))

    def parse_main_args(self, args):
        self._check_encoding(args)
        namespace, _unused_args = self.parse_known_args(args)
        return namespace

    def parse_command_args(self, command, args):
        self._add_command_options(command)
        namespace, unused_args = self.parse_known_args(args)
        namespace = self.command_positional_parser.parse_args(unused_args, namespace)
        command.opts = namespace
        return command.opts

    def print_usage(self, file_=None):
        if self.command_positional_parser:
            self._actions += self.command_positional_parser._actions
        super(OptionParser, self).print_usage(file_)

    def print_help(self, command=None):
        # pylint: disable=W0212
        if command:
            if not self.command_group or self.command_group._command != command._basecmd:
                self._add_command_options(command)
            self._actions += self.command_positional_parser._actions
            self._action_groups.append(self.command_positional_parser._positionals)
        else:
            self.usage = self.get_usage()
        super(OptionParser, self).print_help()
