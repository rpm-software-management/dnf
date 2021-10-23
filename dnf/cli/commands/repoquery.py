#
# Copyright (C) 2014 Red Hat, Inc.
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from dnf.i18n import _
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser

import argparse
import datetime
import logging
import re
import sys

import dnf
import dnf.cli
import dnf.exceptions
import dnf.subject
import dnf.util
import hawkey

logger = logging.getLogger('dnf')


QFORMAT_DEFAULT = '%{name}-%{epoch}:%{version}-%{release}.%{arch}'
# matches %[-][dd]{attr}
QFORMAT_MATCH = re.compile(r'%(-?\d*?){([:.\w]+?)}')

QUERY_TAGS = """\
name, arch, epoch, version, release, reponame (repoid), from_repo, evr,
debug_name, source_name, source_debug_name,
installtime, buildtime, size, downloadsize, installsize,
provides, requires, obsoletes, conflicts, sourcerpm,
description, summary, license, url, reason"""

OPTS_MAPPING = {
    'conflicts': 'conflicts',
    'enhances': 'enhances',
    'obsoletes': 'obsoletes',
    'provides': 'provides',
    'recommends': 'recommends',
    'requires': 'requires',
    'requires-pre': 'requires_pre',
    'suggests': 'suggests',
    'supplements': 'supplements'
}


def rpm2py_format(queryformat):
    """Convert a rpm like QUERYFMT to an python .format() string."""
    def fmt_repl(matchobj):
        fill = matchobj.groups()[0]
        key = matchobj.groups()[1]
        if fill:
            if fill[0] == '-':
                fill = '>' + fill[1:]
            else:
                fill = '<' + fill
            fill = ':' + fill
        return '{0.' + key.lower() + fill + "}"

    def brackets(txt):
        return txt.replace('{', '{{').replace('}', '}}')

    queryformat = queryformat.replace("\\n", "\n").replace("\\t", "\t")
    for key, value in OPTS_MAPPING.items():
        queryformat = queryformat.replace(key, value)
    fmt = ""
    spos = 0
    for item in QFORMAT_MATCH.finditer(queryformat):
        fmt += brackets(queryformat[spos:item.start()])
        fmt += fmt_repl(item)
        spos = item.end()
    fmt += brackets(queryformat[spos:])
    return fmt


class _CommaSplitCallback(OptionParser._SplitCallback):
    SPLITTER = r'\s*,\s*'


class RepoQueryCommand(commands.Command):
    """A class containing methods needed by the cli to execute the repoquery command.
    """
    nevra_forms = {'repoquery-n': hawkey.FORM_NAME,
                   'repoquery-na': hawkey.FORM_NA,
                   'repoquery-nevra': hawkey.FORM_NEVRA}

    aliases = ('repoquery', 'rq') + tuple(nevra_forms.keys())
    summary = _('search for packages matching keyword')

    @staticmethod
    def filter_repo_arch(opts, query):
        """Filter query by repoid and arch options"""
        if opts.repo:
            query.filterm(reponame=opts.repo)
        if opts.arches:
            query.filterm(arch=opts.arches)
        return query

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('-a', '--all', dest='queryall', action='store_true',
                            help=_("Query all packages (shorthand for repoquery '*' "
                                   "or repoquery without argument)"))
        parser.add_argument('--show-duplicates', action='store_true',
                            help=_("Query all versions of packages (default)"))
        parser.add_argument('--arch', '--archlist', dest='arches', default=[],
                            action=_CommaSplitCallback, metavar='[arch]',
                            help=_('show only results from this ARCH'))
        parser.add_argument('-f', '--file', metavar='FILE', nargs='+',
                            help=_('show only results that owns FILE'))
        parser.add_argument('--whatconflicts', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that conflict REQ'))
        parser.add_argument('--whatdepends', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('shows results that requires, suggests, supplements, enhances, '
                                   'or recommends package provides and files REQ'))
        parser.add_argument('--whatobsoletes', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that obsolete REQ'))
        parser.add_argument('--whatprovides', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that provide REQ'))
        parser.add_argument('--whatrequires', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('shows results that requires package provides and files REQ'))
        parser.add_argument('--whatrecommends', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that recommend REQ'))
        parser.add_argument('--whatenhances', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that enhance REQ'))
        parser.add_argument('--whatsuggests', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that suggest REQ'))
        parser.add_argument('--whatsupplements', default=[], action=_CommaSplitCallback,
                            metavar='REQ',
                            help=_('show only results that supplement REQ'))
        whatrequiresform = parser.add_mutually_exclusive_group()
        whatrequiresform.add_argument("--alldeps", action="store_true",
                                      help=_("check non-explicit dependencies (files and Provides); default"))
        whatrequiresform.add_argument("--exactdeps", action="store_true",
                                      help=_('check dependencies exactly as given, opposite of --alldeps'))
        parser.add_argument("--recursive", action="store_true", help=_(
            'used with --whatrequires, and --requires --resolve, query packages recursively.'))
        parser.add_argument('--deplist', action='store_true', help=_(
            "show a list of all dependencies and what packages provide them"))
        parser.add_argument('--resolve', action='store_true',
                            help=_('resolve capabilities to originating package(s)'))
        parser.add_argument("--tree", action="store_true",
                            help=_('show recursive tree for package(s)'))
        parser.add_argument('--srpm', action='store_true',
                            help=_('operate on corresponding source RPM'))
        parser.add_argument("--latest-limit", dest='latest_limit', type=int,
                             help=_('show N latest packages for a given name.arch'
                                    ' (or latest but N if N is negative)'))
        parser.add_argument("--disable-modular-filtering", action="store_true",
                            help=_("list also packages of inactive module streams"))

        outform = parser.add_mutually_exclusive_group()
        outform.add_argument('-i', "--info", dest='queryinfo',
                             default=False, action='store_true',
                             help=_('show detailed information about the package'))
        outform.add_argument('-l', "--list", dest='queryfilelist',
                             default=False, action='store_true',
                             help=_('show list of files in the package'))
        outform.add_argument('-s', "--source", dest='querysourcerpm',
                             default=False, action='store_true',
                             help=_('show package source RPM name'))
        outform.add_argument('--changelogs', dest='querychangelogs',
                             default=False, action='store_true',
                             help=_('show changelogs of the package'))
        outform.add_argument('--qf', "--queryformat", dest='queryformat',
                             default=QFORMAT_DEFAULT,
                             help=_('display format for listing packages: '
                                    '"%%{name} %%{version} ...", '
                                    'use --querytags to view full tag list'))
        parser.add_argument('--querytags', action='store_true',
                            help=_('show available tags to use with '
                                   '--queryformat'))
        outform.add_argument("--nevra", dest='queryformat', const=QFORMAT_DEFAULT,
                             action='store_const',
                             help=_('use name-epoch:version-release.architecture format for '
                                    'displaying found packages (default)'))
        outform.add_argument("--nvr", dest='queryformat', const='%{name}-%{version}-%{release}',
                             action='store_const', help=_('use name-version-release format for '
                                                          'displaying found packages '
                                                          '(rpm query default)'))
        outform.add_argument("--envra", dest='queryformat',
                             const='%{epoch}:%{name}-%{version}-%{release}.%{arch}',
                             action='store_const',
                             help=_('use epoch:name-version-release.architecture format for '
                                    'displaying found packages'))
        outform.add_argument('--groupmember', action="store_true", help=_(
            'Display in which comps groups are presented selected packages'))
        pkgfilter = parser.add_mutually_exclusive_group()
        pkgfilter.add_argument("--duplicates", dest='pkgfilter',
                               const='duplicated', action='store_const',
                               help=_('limit the query to installed duplicate '
                                      'packages'))
        pkgfilter.add_argument("--duplicated", dest='pkgfilter',
                               const='duplicated', action='store_const',
                               help=argparse.SUPPRESS)
        pkgfilter.add_argument("--installonly", dest='pkgfilter',
                               const='installonly', action='store_const',
                               help=_('limit the query to installed installonly packages'))
        pkgfilter.add_argument("--unsatisfied", dest='pkgfilter',
                               const='unsatisfied', action='store_const',
                               help=_('limit the query to installed packages with unsatisfied dependencies'))
        parser.add_argument('--location', action='store_true',
                            help=_('show a location from where packages can be downloaded'))
        package_attribute = parser.add_mutually_exclusive_group()
        help_msgs = {
            'conflicts': _('Display capabilities that the package conflicts with.'),
            'depends': _('Display capabilities that the package can depend on, enhance, recommend,'
                         ' suggest, and supplement.'),
            'enhances': _('Display capabilities that the package can enhance.'),
            'provides': _('Display capabilities provided by the package.'),
            'recommends':  _('Display capabilities that the package recommends.'),
            'requires':  _('Display capabilities that the package depends on.'),
            'requires-pre':  _('If the package is not installed display capabilities that it depends on for '
                               'running %%pre and %%post scriptlets. If the package is installed display '
                               'capabilities that is depends for %%pre, %%post, %%preun and %%postun.'),
            'suggests':  _('Display capabilities that the package suggests.'),
            'supplements':  _('Display capabilities that the package can supplement.')
        }
        for arg, help_msg in help_msgs.items():
            name = '--%s' % arg
            package_attribute.add_argument(name, dest='packageatr', action='store_const',
                                           const=arg, help=help_msg)
        parser.add_argument('--available', action="store_true", help=_('Display only available packages.'))

        help_list = {
            'installed': _('Display only installed packages.'),
            'extras': _('Display only packages that are not present in any of available repositories.'),
            'upgrades': _('Display only packages that provide an upgrade for some already installed package.'),
            'unneeded': _('Display only packages that can be removed by "{prog} autoremove" '
                          'command.').format(prog=dnf.util.MAIN_PROG),
            'userinstalled': _('Display only packages that were installed by user.')
        }
        list_group = parser.add_mutually_exclusive_group()
        for list_arg, help_arg in help_list.items():
            switch = '--%s' % list_arg
            list_group.add_argument(switch, dest='list', action='store_const',
                                    const=list_arg, help=help_arg)

        # make --autoremove hidden compatibility alias for --unneeded
        list_group.add_argument(
            '--autoremove', dest='list', action='store_const',
            const="unneeded", help=argparse.SUPPRESS)
        parser.add_argument('--recent', action="store_true", help=_('Display only recently edited packages'))

        parser.add_argument('key', nargs='*', metavar="KEY",
                            help=_('the key to search for'))

    def pre_configure(self):
        if not self.opts.quiet:
            self.cli.redirect_logger(stdout=logging.WARNING, stderr=logging.INFO)

    def configure(self):
        if not self.opts.quiet:
            self.cli.redirect_repo_progress()
        demands = self.cli.demands

        if self.opts.obsoletes:
            if self.opts.packageatr:
                self.cli._option_conflict("--obsoletes", "--" + self.opts.packageatr)
            else:
                self.opts.packageatr = "obsoletes"

        if self.opts.querytags:
            return

        if self.opts.resolve and not self.opts.packageatr:
            raise dnf.cli.CliError(
                _("Option '--resolve' has to be used together with one of the "
                  "'--conflicts', '--depends', '--enhances', '--provides', '--recommends', "
                  "'--requires', '--requires-pre', '--suggests' or '--supplements' options"))

        if self.opts.recursive:
            if self.opts.exactdeps:
                self.cli._option_conflict("--recursive", "--exactdeps")
            if not any([self.opts.whatrequires,
                        (self.opts.packageatr == "requires" and self.opts.resolve)]):
                raise dnf.cli.CliError(
                    _("Option '--recursive' has to be used with '--whatrequires <REQ>' "
                      "(optionally with '--alldeps', but not with '--exactdeps'), or with "
                      "'--requires <REQ> --resolve'"))

        if self.opts.alldeps or self.opts.exactdeps:
            if not (self.opts.whatrequires or self.opts.whatdepends):
                raise dnf.cli.CliError(
                    _("argument {} requires --whatrequires or --whatdepends option".format(
                        '--alldeps' if self.opts.alldeps else '--exactdeps')))

        if self.opts.srpm:
            self.base.repos.enable_source_repos()

        if (self.opts.list not in ["installed", "userinstalled"] and
           self.opts.pkgfilter != "installonly") or self.opts.available:
            demands.available_repos = True

        demands.sack_activation = True

        if self.opts.querychangelogs:
            demands.changelogs = True

    def build_format_fn(self, opts, pkg):
        if opts.querychangelogs:
            out = []
            out.append('Changelog for %s' % str(pkg))
            for chlog in pkg.changelogs:
                dt = chlog['timestamp']
                out.append('* %s %s\n%s\n' % (dt.strftime("%a %b %d %Y"),
                                              dnf.i18n.ucd(chlog['author']),
                                              dnf.i18n.ucd(chlog['text'])))
            return '\n'.join(out)
        try:
            po = PackageWrapper(pkg)
            if opts.queryinfo:
                return self.base.output.infoOutput(pkg)
            elif opts.queryfilelist:
                filelist = po.files
                if not filelist:
                    print(_('Package {} contains no files').format(pkg), file=sys.stderr)
                return filelist
            elif opts.querysourcerpm:
                return po.sourcerpm
            else:
                return rpm2py_format(opts.queryformat).format(po)
        except AttributeError as e:
            # catch that the user has specified attributes
            # there don't exist on the dnf Package object.
            raise dnf.exceptions.Error(str(e))

    def _resolve_nevras(self, nevras, base_query):
        resolved_nevras_query = self.base.sack.query().filterm(empty=True)
        for nevra in nevras:
            resolved_nevras_query = resolved_nevras_query.union(base_query.intersection(
                dnf.subject.Subject(nevra).get_best_query(
                    self.base.sack,
                    with_provides=False,
                    with_filenames=False
                )
            ))

        return resolved_nevras_query

    def _do_recursive_deps(self, query_in, query_select, done=None):
        done = done if done else query_select

        query_required = query_in.filter(requires=query_select)

        query_select = query_required.difference(done)
        done = query_required.union(done)

        if query_select:
            done = self._do_recursive_deps(query_in, query_select, done=done)

        return done

    def by_all_deps(self, names, query, all_dep_types=False):
        # in case of arguments being NEVRAs, resolve them to packages
        resolved_nevras_query = self._resolve_nevras(names, query)

        # filter the arguments directly as reldeps
        depquery = query.filter(requires__glob=names)

        # filter the resolved NEVRAs as packages
        depquery = depquery.union(query.filter(requires=resolved_nevras_query))

        if all_dep_types:
            # TODO this is very inefficient, as it resolves the `names` glob to
            # reldeps four more times, which in a reasonably wide glob like
            # `dnf repoquery --whatdepends "libdnf*"` can take roughly 50% of
            # the total execution time.
            depquery = depquery.union(query.filter(recommends__glob=names))
            depquery = depquery.union(query.filter(enhances__glob=names))
            depquery = depquery.union(query.filter(supplements__glob=names))
            depquery = depquery.union(query.filter(suggests__glob=names))

            depquery = depquery.union(query.filter(recommends=resolved_nevras_query))
            depquery = depquery.union(query.filter(enhances=resolved_nevras_query))
            depquery = depquery.union(query.filter(supplements=resolved_nevras_query))
            depquery = depquery.union(query.filter(suggests=resolved_nevras_query))

        if self.opts.recursive:
            depquery = self._do_recursive_deps(query, depquery)

        return depquery

    def _get_recursive_providers_query(self, query_in, providers, done=None):
        done = done if done else self.base.sack.query().filterm(empty=True)
        t = self.base.sack.query().filterm(empty=True)
        for pkg in providers.run():
            t = t.union(query_in.filter(provides=pkg.requires))
        query_select = t.difference(done)
        if query_select:
            done = self._get_recursive_providers_query(query_in, query_select, done=t.union(done))
        return t.union(done)

    def _add_add_remote_packages(self):
        rpmnames = []
        remote_packages = []
        for key in self.opts.key:
            schemes = dnf.pycomp.urlparse.urlparse(key)[0]
            if key.endswith('.rpm'):
                rpmnames.append(key)
            elif schemes and schemes in ('http', 'ftp', 'file', 'https'):
                rpmnames.append(key)
        if rpmnames:
            remote_packages = self.base.add_remote_rpms(
                rpmnames, strict=False, progress=self.base.output.progress)
        return remote_packages

    def run(self):
        if self.opts.querytags:
            print(QUERY_TAGS)
            return

        self.cli._populate_update_security_filter(self.opts)

        q = self.base.sack.query(
            flags=hawkey.IGNORE_MODULAR_EXCLUDES
            if self.opts.disable_modular_filtering
            else hawkey.APPLY_EXCLUDES
        )
        if self.opts.key:
            remote_packages = self._add_add_remote_packages()

            kwark = {}
            if self.opts.command in self.nevra_forms:
                kwark["forms"] = [self.nevra_forms[self.opts.command]]
            pkgs = []
            query_results = q.filter(empty=True)

            if remote_packages:
                query_results = query_results.union(
                    self.base.sack.query().filterm(pkg=remote_packages))

            for key in self.opts.key:
                query_results = query_results.union(
                    dnf.subject.Subject(key, ignore_case=True).get_best_query(
                        self.base.sack, with_provides=False, query=q, **kwark))
            q = query_results

        if self.opts.recent:
            q = q._recent(self.base.conf.recent)
        if self.opts.available:
            if self.opts.list and self.opts.list != "installed":
                print(self.cli.optparser.print_usage())
                raise dnf.exceptions.Error(_("argument {}: not allowed with argument {}".format(
                    "--available", "--" + self.opts.list)))
        elif self.opts.list == "unneeded":
            q = q._unneeded(self.base.history.swdb)
        elif self.opts.list and self.opts.list != 'userinstalled':
            q = getattr(q, self.opts.list)()

        if self.opts.pkgfilter == "duplicated":
            installonly = self.base._get_installonly_query(q)
            q = q.difference(installonly).duplicated()
        elif self.opts.pkgfilter == "installonly":
            q = self.base._get_installonly_query(q)
        elif self.opts.pkgfilter == "unsatisfied":
            rpmdb = dnf.sack.rpmdb_sack(self.base)
            rpmdb._configure(self.base.conf.installonlypkgs, self.base.conf.installonly_limit)
            goal = dnf.goal.Goal(rpmdb)
            goal.protect_running_kernel = False
            solved = goal.run(verify=True)
            if not solved:
                print(dnf.util._format_resolve_problems(goal.problem_rules()))
            return
        elif not self.opts.list:
            # do not show packages from @System repo
            q = q.available()

        # filter repo and arch
        q = self.filter_repo_arch(self.opts, q)
        orquery = q

        if self.opts.file:
            q.filterm(file__glob=self.opts.file)
        if self.opts.whatconflicts:
            rels = q.filter(conflicts__glob=self.opts.whatconflicts)
            q = rels.union(q.filter(conflicts=self._resolve_nevras(self.opts.whatconflicts, q)))
        if self.opts.whatobsoletes:
            q.filterm(obsoletes=self.opts.whatobsoletes)
        if self.opts.whatprovides:
            query_for_provide = q.filter(provides__glob=self.opts.whatprovides)
            if query_for_provide:
                q = query_for_provide
            else:
                q.filterm(file__glob=self.opts.whatprovides)

        if self.opts.whatrequires:
            if (self.opts.exactdeps):
                q.filterm(requires__glob=self.opts.whatrequires)
            else:
                q = self.by_all_deps(self.opts.whatrequires, q)

        if self.opts.whatdepends:
            if (self.opts.exactdeps):
                dependsquery = q.filter(requires__glob=self.opts.whatdepends)
                dependsquery = dependsquery.union(q.filter(recommends__glob=self.opts.whatdepends))
                dependsquery = dependsquery.union(q.filter(enhances__glob=self.opts.whatdepends))
                dependsquery = dependsquery.union(q.filter(supplements__glob=self.opts.whatdepends))
                q = dependsquery.union(q.filter(suggests__glob=self.opts.whatdepends))
            else:
                q = self.by_all_deps(self.opts.whatdepends, q, True)

        if self.opts.whatrecommends:
            rels = q.filter(recommends__glob=self.opts.whatrecommends)
            q = rels.union(q.filter(recommends=self._resolve_nevras(self.opts.whatrecommends, q)))
        if self.opts.whatenhances:
            rels = q.filter(enhances__glob=self.opts.whatenhances)
            q = rels.union(q.filter(enhances=self._resolve_nevras(self.opts.whatenhances, q)))
        if self.opts.whatsupplements:
            rels = q.filter(supplements__glob=self.opts.whatsupplements)
            q = rels.union(q.filter(supplements=self._resolve_nevras(self.opts.whatsupplements, q)))
        if self.opts.whatsuggests:
            rels = q.filter(suggests__glob=self.opts.whatsuggests)
            q = rels.union(q.filter(suggests=self._resolve_nevras(self.opts.whatsuggests, q)))

        if self.opts.latest_limit:
            q = q.latest(self.opts.latest_limit)
        # reduce a query to security upgrades if they are specified
        q = self.base._merge_update_filters(q, warning=False)
        if self.opts.srpm:
            pkg_list = []
            for pkg in q:
                srcname = pkg.source_name
                if srcname is not None:
                    tmp_query = self.base.sack.query().filterm(name=srcname, evr=pkg.evr,
                                                               arch='src')
                    pkg_list += tmp_query.run()
            q = self.base.sack.query().filterm(pkg=pkg_list)
        if self.opts.tree:
            if not self.opts.whatrequires and self.opts.packageatr not in (
                    'conflicts', 'enhances', 'obsoletes', 'provides', 'recommends',
                    'requires', 'suggests', 'supplements'):
                raise dnf.exceptions.Error(
                    _("No valid switch specified\nusage: {prog} repoquery [--conflicts|"
                      "--enhances|--obsoletes|--provides|--recommends|--requires|"
                      "--suggest|--supplements|--whatrequires] [key] [--tree]\n\n"
                      "description:\n  For the given packages print a tree of the "
                      "packages.").format(prog=dnf.util.MAIN_PROG))
            self.tree_seed(q, orquery, self.opts)
            return

        pkgs = set()
        if self.opts.packageatr:
            rels = set()
            for pkg in q.run():
                if self.opts.list != 'userinstalled' or self.base.history.user_installed(pkg):
                    if self.opts.packageatr == 'depends':
                        rels.update(pkg.requires + pkg.enhances + pkg.suggests +
                                    pkg.supplements + pkg.recommends)
                    else:
                        rels.update(getattr(pkg, OPTS_MAPPING[self.opts.packageatr]))
            if self.opts.resolve:
                # find the providing packages and show them
                if self.opts.list == "installed":
                    query = self.filter_repo_arch(self.opts, self.base.sack.query())
                else:
                    query = self.filter_repo_arch(self.opts, self.base.sack.query().available())
                providers = query.filter(provides=rels)
                if self.opts.recursive:
                    providers = providers.union(
                        self._get_recursive_providers_query(query, providers))
                pkgs = set()
                for pkg in providers.latest().run():
                    pkgs.add(self.build_format_fn(self.opts, pkg))
            else:
                pkgs.update(str(rel) for rel in rels)
        elif self.opts.location:
            for pkg in q.run():
                location = pkg.remote_location()
                if location is not None:
                    pkgs.add(location)
        elif self.opts.deplist:
            pkgs = []
            for pkg in sorted(set(q.run())):
                if self.opts.list != 'userinstalled' or self.base.history.user_installed(pkg):
                    deplist_output = []
                    deplist_output.append('package: ' + str(pkg))
                    for req in sorted([str(req) for req in pkg.requires]):
                        deplist_output.append('  dependency: ' + req)
                        subject = dnf.subject.Subject(req)
                        query = subject.get_best_query(self.base.sack)
                        query = self.filter_repo_arch(
                            self.opts, query.available())
                        if not self.opts.verbose:
                            query = query.latest()
                        for provider in query.run():
                            deplist_output.append('   provider: ' + str(provider))
                    pkgs.append('\n'.join(deplist_output))
            if pkgs:
                print('\n\n'.join(pkgs))
            return
        elif self.opts.groupmember:
            self._group_member_report(q)
            return

        else:
            for pkg in q.run():
                if self.opts.list != 'userinstalled' or self.base.history.user_installed(pkg):
                    pkgs.add(self.build_format_fn(self.opts, pkg))

        if pkgs:
            if self.opts.queryinfo:
                print("\n\n".join(sorted(pkgs)))
            else:
                print("\n".join(sorted(pkgs)))

    def _group_member_report(self, query):
        package_conf_dict = {}
        for group in self.base.comps.groups:
            package_conf_dict[group.id] = set([pkg.name for pkg in group.packages_iter()])
        group_package_dict = {}
        pkg_not_in_group = []
        for pkg in query.run():
            group_id_list = []
            for group_id, package_name_set in package_conf_dict.items():
                if pkg.name in package_name_set:
                    group_id_list.append(group_id)
            if group_id_list:
                group_package_dict.setdefault(
                    '$'.join(sorted(group_id_list)), []).append(str(pkg))
            else:
                pkg_not_in_group.append(str(pkg))
        output = []
        for key, package_list in sorted(group_package_dict.items()):
            output.append(
                '\n'.join(sorted(package_list) + sorted(['  @' + id for id in key.split('$')])))
        output.append('\n'.join(sorted(pkg_not_in_group)))
        if output:
            print('\n'.join(output))

    def grow_tree(self, level, pkg, opts):
        pkg_string = self.build_format_fn(opts, pkg)
        if level == -1:
            print(pkg_string)
            return
        spacing = " "
        for x in range(0, level):
            spacing += "|   "
        requires = []
        for requirepkg in pkg.requires:
            requires.append(str(requirepkg))
        reqstr = "[" + str(len(requires)) + ": " + ", ".join(requires) + "]"
        print(spacing + r"\_ " + pkg_string + " " + reqstr)

    def tree_seed(self, query, aquery, opts, level=-1, usedpkgs=None):
        for pkg in sorted(set(query.run()), key=lambda p: p.name):
            usedpkgs = set() if usedpkgs is None or level == -1 else usedpkgs
            if pkg.name.startswith("rpmlib") or pkg.name.startswith("solvable"):
                return
            self.grow_tree(level, pkg, opts)
            if pkg not in usedpkgs:
                usedpkgs.add(pkg)
                if opts.packageatr:
                    strpkg = getattr(pkg, opts.packageatr)
                    ar = {}
                    for name in set(strpkg):
                        pkgquery = self.base.sack.query().filterm(provides=name)
                        for querypkg in pkgquery:
                            ar[querypkg.name + "." + querypkg.arch] = querypkg
                    pkgquery = self.base.sack.query().filterm(pkg=list(ar.values()))
                else:
                    pkgquery = self.by_all_deps((pkg.name, ), aquery) if opts.alldeps \
                        else aquery.filter(requires__glob=pkg.name)
                self.tree_seed(pkgquery, aquery, opts, level + 1, usedpkgs)


class PackageWrapper(object):

    """Wrapper for dnf.package.Package, so we can control formatting."""

    def __init__(self, pkg):
        self._pkg = pkg

    def __getattr__(self, attr):
        atr = getattr(self._pkg, attr)
        if atr is None:
            return "(none)"
        if isinstance(atr, list):
            return '\n'.join(sorted({dnf.i18n.ucd(reldep) for reldep in atr}))
        return dnf.i18n.ucd(atr)

    @staticmethod
    def _get_timestamp(timestamp):
        if timestamp > 0:
            dt = datetime.datetime.utcfromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        else:
            return ''

    @property
    def buildtime(self):
        return self._get_timestamp(self._pkg.buildtime)

    @property
    def installtime(self):
        return self._get_timestamp(self._pkg.installtime)
