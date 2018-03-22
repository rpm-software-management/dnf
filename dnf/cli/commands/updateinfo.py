# updateinfo.py
# UpdateInfo CLI command.
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

"""UpdateInfo CLI command."""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import collections
import fnmatch

import hawkey
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _
from dnf.pycomp import unicode

def _maxlen(iterable):
    """Return maximum length of items in a non-empty iterable."""
    return max(len(item) for item in iterable)

class UpdateInfoCommand(commands.Command):
    """Implementation of the UpdateInfo command."""

    TYPE2LABEL = {hawkey.ADVISORY_BUGFIX: _('bugfix'),
                  hawkey.ADVISORY_ENHANCEMENT: _('enhancement'),
                  hawkey.ADVISORY_SECURITY: _('security'),
                  hawkey.ADVISORY_UNKNOWN: _('unknown'),
                  hawkey.ADVISORY_NEWPACKAGE: _('newpackage')}

    SECURITY2LABEL = {'Critical': _('Critical/Sec.'),
                      'Important': _('Important/Sec.'),
                      'Moderate': _('Moderate/Sec.'),
                      'Low': _('Low/Sec.')}

    direct_commands = {'list-updateinfo'    : 'list',
                       'list-security'      : 'list',
                       'list-sec'           : 'list',
                       'info-updateinfo'    : 'info',
                       'info-security'      : 'info',
                       'info-sec'           : 'info',
                       'summary-updateinfo' : 'summary'}
    aliases = ['updateinfo'] + list(direct_commands.keys())
    summary = _('display advisories about packages')
    availability_default = 'available'
    availabilities = ['installed', 'updates', 'all', availability_default]

    def __init__(self, cli):
        """Initialize the command."""
        super(UpdateInfoCommand, self).__init__(cli)
        self._ina2evr_cache = None
        self._update_filters_cmp_cache = dict()

    @staticmethod
    def set_argparser(parser):
        availability = parser.add_mutually_exclusive_group()
        availability.add_argument(
            "--available", dest='_availability', const='available', action='store_const',
            help=_("advisories about newer versions of installed packages (default)"))
        availability.add_argument(
            "--installed", dest='_availability', const='installed', action='store_const',
            help=_("advisories about equal and older versions of installed packages"))
        availability.add_argument(
            "--updates", dest='_availability', const='updates', action='store_const',
            help=_("advisories about newer versions of those installed packages "
                   "for which a newer version is available"))
        availability.add_argument(
            "--all", dest='_availability', const='all', action='store_const',
            help=_("advisories about any versions of installed packages"))
        cmds = ['summary', 'list', 'info']
        output_format = parser.add_mutually_exclusive_group()
        output_format.add_argument("--summary", dest='_spec_action', const='summary',
                                   action='store_const',
                                   help=_('show summary of advisories (default)'))
        output_format.add_argument("--list", dest='_spec_action', const='list',
                                   action='store_const',
                                   help=_('show list of advisories'))
        output_format.add_argument("--info", dest='_spec_action', const='info',
                                   action='store_const',
                                   help=_('show info of advisories'))
        parser.add_argument('spec', nargs='*', metavar='SPEC',
                            choices=cmds, default=cmds[0],
                            action=OptionParser.PkgNarrowCallback)

    def configure(self):
        """Do any command-specific configuration based on command arguments."""
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

        if self.opts.command[0] in self.direct_commands:
            # we were called with direct command
            self.opts.spec_action = self.direct_commands[self.opts.command[0]]
        else:
            if self.opts._spec_action:
                self.opts.spec_action = self.opts._spec_action

        if self.opts._availability:
            self.opts.availability = self.opts._availability
        else:
            if not self.opts.spec or self.opts.spec[0] not in self.availabilities:
                self.opts.availability = self.availability_default
            else:
                self.opts.availability = self.opts.spec.pop(0)

    def run(self):
        """Execute the command with arguments."""
        self.cli._populate_update_security_filter(self.opts, self.base.sack.query())

        mixed = False
        if self.opts.availability == 'installed':
            apkg_adv_insts = self.installed_apkg_adv_insts(self.opts.spec)
            description = _('installed')
        elif self.opts.availability == 'updates':
            apkg_adv_insts = self.updating_apkg_adv_insts(self.opts.spec)
            description = _('updates')
        elif self.opts.availability == 'all':
            mixed = True
            apkg_adv_insts = self.all_apkg_adv_insts(self.opts.spec)
            description = _('all')
        else:
            apkg_adv_insts = self.available_apkg_adv_insts(self.opts.spec)
            description = _('available')

        if self.opts.spec_action == 'list':
            self.display_list(apkg_adv_insts, mixed)
        elif self.opts.spec_action == 'info':
            self.display_info(apkg_adv_insts, mixed)
        else:
            self.display_summary(apkg_adv_insts, description)

    def get_installed_version(self, name, arch):
        if self._ina2evr_cache is None:
            self._ina2evr_cache = {(pkg.name, pkg.arch): pkg.evr
                                   for pkg in self.base.sack.query().installed()}
        return self._ina2evr_cache.get((name, arch), None)

    def compare_with_installed(self, apackage):
        """Compare installed version with apackage version. Returns None either if
        apackage is not installed, or if there are no update filters for apackage"""
        key = (apackage.name, apackage.evr, apackage.arch)
        if key not in self._update_filters_cmp_cache:
            ievr = self.get_installed_version(key[0], key[2])
            if ievr is None:
                self._update_filters_cmp_cache[key] = None
            else:
                q = self.base.sack.query().filterm(name=key[0], evr=key[1])
                if len(self.base._merge_update_filters(q, warning=False)) == 0:
                    self._update_filters_cmp_cache[key] = None
                else:
                    self._update_filters_cmp_cache[key] = self.base.sack.evr_cmp(ievr, key[1])
        return self._update_filters_cmp_cache[key]

    def _older_installed(self, apackage):
        """Test whether an older version of a package is installed."""
        cmp = self.compare_with_installed(apackage)
        if cmp is None:
            return False
        else:
            return cmp < 0

    def _newer_equal_installed(self, apackage):
        """Test whether a newer or equal version of a package is installed."""
        cmp = self.compare_with_installed(apackage)
        if cmp is None:
            return False
        else:
            return cmp >= 0

    def _any_installed(self, apackage):
        """Test whether any version of a package is installed."""
        if self.compare_with_installed(apackage) is None:
            return False
        return True

    def _apackage_advisory_installeds(self, pkgs, cmptype, req_apkg, specs):
        """Return (adv. package, advisory, installed) triplets."""
        specs_types = set()
        specs_patterns = set()
        for spec in specs:
            if spec == 'bugfix':
                specs_types.add(hawkey.ADVISORY_BUGFIX)
            elif spec == 'enhancement':
                specs_types.add(hawkey.ADVISORY_ENHANCEMENT)
            elif spec in ('security', 'sec'):
                specs_types.add(hawkey.ADVISORY_SECURITY)
            elif spec == 'newpackage':
                specs_types.add(hawkey.ADVISORY_NEWPACKAGE)
            else:
                specs_patterns.add(spec)

        for package in pkgs:
            for advisory in package.get_advisories(cmptype):
                if not specs_types and not specs_patterns:
                    advisory_match = True
                else:
                    advisory_match = advisory.type in specs_types or \
                        any(fnmatch.fnmatchcase(advisory.id, pat)
                            for pat in specs_patterns)
                for apackage in advisory.packages:
                    passed = req_apkg(apackage) \
                        and (advisory_match or
                             any(fnmatch.fnmatchcase(apackage.name, pat)
                                 for pat in specs_patterns))
                    if passed:
                        installed = self._newer_equal_installed(apackage)
                        yield apackage, advisory, installed

    def available_apkg_adv_insts(self, specs):
        """Return available (adv. package, adv., inst.) triplets"""
        return self._apackage_advisory_installeds(
            self.base.sack.query().installed(), hawkey.GT,
            self._older_installed, specs)

    def installed_apkg_adv_insts(self, specs):
        """Return installed (adv. package, adv., inst.) triplets"""
        return self._apackage_advisory_installeds(
            self.base.sack.query().installed(), hawkey.LT | hawkey.EQ,
            self._newer_equal_installed, specs)

    def updating_apkg_adv_insts(self, specs):
        """Return updating (adv. package, adv., inst.) triplets"""
        return self._apackage_advisory_installeds(
            self.base.sack.query().filterm(upgradable=True), hawkey.GT,
            self._older_installed, specs)

    def all_apkg_adv_insts(self, specs):
        """Return installed (adv. package, adv., inst.) triplets"""
        return self._apackage_advisory_installeds(
            self.base.sack.query().installed(), hawkey.LT | hawkey.EQ | hawkey.GT,
            self._any_installed, specs)

    def _summary(self, apkg_adv_insts):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {}
        for (apkg, advisory, installed) in apkg_adv_insts:
            id2type[advisory.id] = advisory.type
            if advisory.type == hawkey.ADVISORY_SECURITY:
                id2type[(advisory.id, advisory.severity)] = (advisory.type, advisory.severity)
        return collections.Counter(id2type.values())

    def display_summary(self, apkg_adv_insts, description):
        """Display the summary of advisories."""
        typ2cnt = self._summary(apkg_adv_insts)
        if typ2cnt:
            print(_('Updates Information Summary: ') + description)
            # Convert types to strings and order the entries.
            label_counts = [
                (0, _('New Package notice(s)'), typ2cnt[hawkey.ADVISORY_NEWPACKAGE]),
                (0, _('Security notice(s)'), typ2cnt[hawkey.ADVISORY_SECURITY]),
                (1, _('Critical Security notice(s)'),
                 typ2cnt[(hawkey.ADVISORY_SECURITY, 'Critical')]),
                (1, _('Important Security notice(s)'),
                 typ2cnt[(hawkey.ADVISORY_SECURITY, 'Important')]),
                (1, _('Moderate Security notice(s)'),
                 typ2cnt[(hawkey.ADVISORY_SECURITY, 'Moderate')]),
                (1, _('Low Security notice(s)'),
                 typ2cnt[(hawkey.ADVISORY_SECURITY, 'Low')]),
                (1, _('Unknown Security notice(s)'),
                 typ2cnt[(hawkey.ADVISORY_SECURITY, None)]),
                (0, _('Bugfix notice(s)'), typ2cnt[hawkey.ADVISORY_BUGFIX]),
                (0, _('Enhancement notice(s)'), typ2cnt[hawkey.ADVISORY_ENHANCEMENT]),
                (0, _('other notice(s)'), typ2cnt[hawkey.ADVISORY_UNKNOWN])]
            width = _maxlen(unicode(v[2]) for v in label_counts if v[2])
            for indent, label, count in label_counts:
                if not count:
                    continue
                print('    %*s %s' % (width + 4 * indent, unicode(count), label))
        if self.base.conf.autocheck_running_kernel:
            self.cli._check_running_kernel()

    def display_list(self, apkg_adv_insts, mixed):
        """Display the list of advisories."""
        def inst2mark(inst):
            if not mixed:
                return ''
            elif inst:
                return 'i '
            else:
                return '  '

        def type2label(typ, sev):
            if typ == hawkey.ADVISORY_SECURITY:
                return self.SECURITY2LABEL.get(sev, _('Unknown/Sec.'))
            else:
                return self.TYPE2LABEL.get(typ, _('unknown'))

        nevra_inst_dict = dict()
        for apkg, advisory, installed in apkg_adv_insts:
            nevra = '%s-%s.%s' % (apkg.name, apkg.evr, apkg.arch)
            nevra_inst_dict.setdefault((nevra, installed), dict())[advisory.id] = (
                advisory.type, advisory.severity)

        advlist = []
        # convert types to labels, find max len of advisory IDs and types
        idw = tlw = 0
        for (nevra, inst), id2type in sorted(nevra_inst_dict.items(), key=lambda x: x[0]):
            for aid, atypesev in id2type.items():
                idw = max(idw, len(aid))
                label = type2label(*atypesev)
                tlw = max(tlw, len(label))
                advlist.append((inst2mark(inst), aid, label, nevra))

        for (inst, aid, label, nevra) in advlist:
            print('%s%-*s %-*s %s' % (inst, idw, aid, tlw, label, nevra))


    def _info(self, apkg_adv_insts):
        """Make detailed information about advisories."""
        arches = self.base.sack.list_arches()

        # Get mapping from title to [title, ID, type, time, BZs, CVEs,
        # description, rights, files, installed]. This way we get rid of
        # unneeded advisory packages given with the advisories and we remove
        # duplicate advisories (that SPEEDS UP the information extraction
        # because the advisory attribute getters are expensive, so we won't get
        # the attributes multiple times). We cannot use a set because
        # advisories are not hashable.
        verbose = self.base.conf.verbose
        bytitle = dict()
        # mapping from title to list of identities
        for apkg, advisory, installed in apkg_adv_insts:
            title = advisory.title.lower()
            try:
                advlist = bytitle[title]
            except KeyError:
                advlist = [
                    advisory.title,
                    advisory.id,
                    self.TYPE2LABEL.get(advisory.type, _('unknown')),
                    unicode(advisory.updated),
                    set((ref.type, ref.id, ref.title) for ref in advisory.references),
                    [],
                    advisory.description,
                    advisory.severity,
                    advisory.rights if verbose else None,
                    set(pkg.filename for pkg in advisory.packages
                        if pkg.arch in arches) if verbose else None,
                    installed]
                bytitle[title] = advlist
            else:
                # References and files are merged.
                advlist[4].update(set((ref.type, ref.id, ref.title)
                                      for ref in advisory.references))
                if verbose:
                    advlist[9].update(set(pkg.filename
                                          for pkg in advisory.packages
                                          if pkg.arch in arches))
                # If the stored advisory is marked as not installed and the
                # current is marked as installed, mark the stored as installed.
                advlist[10] = advlist[10] or installed

        for title in sorted(bytitle.keys()):
            yield bytitle[title]

    def display_info(self, apkg_adv_insts, mixed):
        """Display the details about available advisories."""
        def advlist2lines(advlist):
            # simple one line fields
            for i in (1, 2, 3, 7):
                advlist[i] = [advlist[i]]
            # split referencies to bzs / cves
            references = sorted(advlist[4])
            advlist[4] = []
            advlist[5] = []
            for ref_type, ref_id, ref_title in references:
                if ref_type == hawkey.REFERENCE_BUGZILLA:
                    advlist[4].append('{} - {}'.format(ref_id, ref_title or ''))
                elif ref_type == hawkey.REFERENCE_CVE:
                    advlist[5].append(ref_id)
            # multiline fields
            for i in (6, 8):
                if advlist[i]:
                    advlist[i] = advlist[i].splitlines()
            # sort filenames
            if advlist[9]:
                advlist[9] = sorted(advlist[9])
            # installed value
            if not mixed:
                advlist[10] = None
            else:
                advlist[10] = [_('true') if advlist[10] else _('false')]
            return advlist

        labels = (_('Update ID'), _('Type'), _('Updated'), _('Bugs'),
                  _('CVEs'), _('Description'), _('Severity'), _('Rights'),
                  _('Files'), _('Installed'))
        width = _maxlen(labels)
        for advlist in self._info(apkg_adv_insts):
            print('=' * 79)
            print('  ' + advlist[0])
            print('=' * 79)
            for label, lines in zip(labels, advlist2lines(advlist)[1:]):
                if lines is None or lines == [None]:
                    continue
                for i, line in enumerate(lines):
                    print('%*s: %s' % (width, label if i == 0 else '', line))
            print()

