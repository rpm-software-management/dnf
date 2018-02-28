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
from collections import OrderedDict
from itertools import chain
from operator import itemgetter
import collections
import fnmatch
import itertools

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
        elif self.opts.availability == 'available':
            apkg_adv_insts = self.available_apkg_adv_insts(self.opts.spec)
            description = _('available')

        display = self.display_summary
        if self.opts.spec_action == 'list':
            display = self.display_list
        elif self.opts.spec_action == 'info':
            display = self.display_info
        display(apkg_adv_insts, mixed, description)

    def get_installed_version(self, name, arch):
        if self._ina2evr_cache is None:
            self._ina2evr_cache = {(pkg.name, pkg.arch): pkg.evr
                                   for pkg in self.base.sack.query().installed()}
        return self._ina2evr_cache.get((name, arch), None)

    def compare_with_installed(self, apackage):
        """Compare installed version with apackage version. Returns None either if
        apackage is not installed, or if there are no update filters for apackage"""
        key = (apackage.name, apackage.evr, apackage.arch)
        if not key in self._update_filters_cmp_cache:
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
                    advisory_match = advisory.type in specs_types \
                        or any(fnmatch.fnmatchcase(advisory.id, pat) for pat in specs_patterns)
                for apackage in advisory.packages:
                    passed = req_apkg(apackage) \
                        and (advisory_match or any(fnmatch.fnmatchcase(apackage.name, pat) for pat in specs_patterns))
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
        ipackages = self.base.sack.query().installed()
        gttriplets = self._apackage_advisory_installeds(
            ipackages, hawkey.GT, self._any_installed, specs)
        lteqtriplets = self._apackage_advisory_installeds(
            ipackages, hawkey.LT | hawkey.EQ, self._any_installed, specs)
        return chain(gttriplets, lteqtriplets)

    #TODO this is quicker, but returns different output
    def xall_apkg_adv_insts(self, specs):
        """Return installed (adv. package, adv., inst.) triplets"""
        ipackages = self.base.sack.query().installed()
        return self._apackage_advisory_installeds(
            ipackages, hawkey.LT | hawkey.EQ | hawkey.GT, self._any_installed, specs)














    def _summary(self, apkg_adv_insts):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {}
        for pkadin in apkg_adv_insts:
            id2type[pkadin[1].id] = pkadin[1].type
            if pkadin[1].type == hawkey.ADVISORY_SECURITY:
                id2type[(pkadin[1].id, pkadin[1].severity)] = (pkadin[1].type,
                                                               pkadin[1].severity)
        return collections.Counter(id2type.values())

    def display_summary(self, apkg_adv_insts, mixed, description):
        """Display the summary of advisories."""
        typ2cnt = self._summary(apkg_adv_insts)
        if not typ2cnt:
            if self.base.conf.autocheck_running_kernel:
                self.cli._check_running_kernel()
            return
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
        # Convert counts to strings and skip missing types.
        label2value = OrderedDict((label, (indent, unicode(count)))
                                  for indent, label, count in label_counts
                                  if count)
        width = _maxlen(v[1] for v in label2value.values())
        for label, (indent, value) in label2value.items():
            print('    %*s %s' % (width + 4 * indent, value, label))
        if self.base.conf.autocheck_running_kernel:
            self.cli._check_running_kernel()

    @staticmethod
    def _list(apkg_adv_insts):
        """Make the list of advisories."""
        # Get ((NEVRA, installed), advisory ID, advisory type)
        apkg2nevra = lambda apkg: apkg.name + '-' + apkg.evr + '.' + apkg.arch
        nevrains_id_types = (
            ((apkg2nevra(apkg), inst), adv.id, (adv.type, adv.severity))
            for apkg, adv, inst in apkg_adv_insts)
        # Sort and group by (NEVRA, installed).
        nevrains_nits = itertools.groupby(
            sorted(nevrains_id_types, key=itemgetter(0)), key=itemgetter(0))
        for nevra_ins, nits in nevrains_nits:
            # Remove duplicate IDs. We assume that two advisories with the same
            # IDs (e.g. from different repositories) must have the same type.
            yield nevra_ins, {nit[1]: nit[2] for nit in nits}

    def display_list(self, apkg_adv_insts, mixed, description):
        """Display the list of advisories."""
        def inst2mark(inst):
            return ('' if not mixed else 'i ' if inst else '  ')

        def type2label(typ, sev):
            if typ == hawkey.ADVISORY_SECURITY:
                return cls.SECURITY2LABEL.get(sev, _('Unknown/Sec.'))
            else:
                return cls.TYPE2LABEL.get(typ, _('unknown'))

        # Sort IDs and convert types to labels.
        nevramark2id2tlbl = OrderedDict(
            ((nevra, inst2mark(inst)),
             OrderedDict(sorted(((id_, type2label(typ, sev))
                                 for id_, (typ, sev) in id2type.items()),
                                key=itemgetter(0))))
            for (nevra, inst), id2type in self._list(apkg_adv_insts))
        if not nevramark2id2tlbl:
            return
        # Get all advisory IDs and types as two iterables.
        ids, tlbls = zip(*chain.from_iterable(
            id2tlbl.items() for id2tlbl in nevramark2id2tlbl.values()))
        idw, tlw = _maxlen(ids), _maxlen(tlbls)
        for (nevra, mark), id2tlbl in nevramark2id2tlbl.items():
            for id_, tlbl in id2tlbl.items():
                print('%s%-*s %-*s %s' % (mark, idw, id_, tlw, tlbl, nevra))

    def _info(self, apkg_adv_insts):
        """Make detailed information about advisories."""
        # Get mapping from identity to (title, ID, type, time, BZs, CVEs,
        # description, rights, files, installed). This way we get rid of
        # unneeded advisory packages given with the advisories and we remove
        # duplicate advisories (that SPEEDS UP the information extraction
        # because the advisory attribute getters are expensive, so we won't get
        # the attributes multiple times). We cannot use a set because
        # advisories are not hashable.
        getrefs = lambda apkg, typ: (
            (ref.id, ref.title) for ref in apkg.references if ref.type == typ)
        id2tuple = OrderedDict()
        for apkg_adv_inst in apkg_adv_insts:
            identity, inst = id(apkg_adv_inst[1]), apkg_adv_inst[2]
            try:
                tuple_ = id2tuple[identity]
            except KeyError:
                id2tuple[identity] = (
                    apkg_adv_inst[1].title,
                    apkg_adv_inst[1].id,
                    apkg_adv_inst[1].type,
                    apkg_adv_inst[1].updated,
                    getrefs(apkg_adv_inst[1], hawkey.REFERENCE_BUGZILLA),
                    getrefs(apkg_adv_inst[1], hawkey.REFERENCE_CVE),
                    apkg_adv_inst[1].description,
                    apkg_adv_inst[1].severity,
                    apkg_adv_inst[1].rights,
                    (pkg.filename for pkg in apkg_adv_inst[1].packages
                     if pkg.arch in self.base.sack.list_arches()),
                    inst)
            else:
                # If the stored advisory is marked as not installed and the
                # current is marked as installed, mark the stored as installed.
                if not tuple_[10] and inst:
                    id2tuple[identity] = tuple_[:10] + (inst,)
        # Get mapping from title to (ID, type, time, BZs, CVEs, description,
        # rights, files, installed) => group by titles and merge values. We
        # assume that two advisories with the same title (e.g. from different
        # repositories) must have the same ID, type, time, description and
        # rights. References, files and installs are merged.
        merge = lambda old, new: set(chain(old, new))
        title2info = OrderedDict()
        for tuple_ in id2tuple.values():
            title, new = tuple_[0], tuple_[1:]
            old = title2info.get(
                title, (None, None, None, [], [], None, None, None, [], False))
            title2info[title] = (
                new[:3] +
                (merge(old[3], new[3]),
                 merge(old[4], new[4])) +
                new[5:8] +
                (merge(old[8], new[8]),
                 old[9] or new[9]))
        return title2info

    def display_info(self, apkg_adv_insts, mixed, description):
        """Display the details about available advisories."""
        info = self._info(apkg_adv_insts).items()
        # Convert objects to string lines and mark verbose fields.
        verbse = lambda value: value if self.base.conf.verbose else None
        info = (
            (tit, ([id_], [self.TYPE2LABEL[typ]], [unicode(upd)],
                   (id_title[0] + (' - ' + id_title[1] if id_title[1] else '')
                    for id_title in bzs),
                   (id_title[0] for id_title in cvs), desc.splitlines(), [sev],
                   verbse(rigs.splitlines() if rigs else None), verbse(fils),
                   None if not mixed else [_('true') if ins else _('false')]))
            for tit, (id_, typ, upd, bzs, cvs, desc, sev, rigs, fils, ins) in info)
        labels = (_('Update ID'), _('Type'), _('Updated'), _('Bugs'),
                  _('CVEs'), _('Description'), _('Severity'), _('Rights'),
                  _('Files'), _('Installed'))
        width = _maxlen(labels)
        for title, vallines in info:
            print('=' * 79)
            print('  ' + title)
            print('=' * 79)
            for label, lines in zip(labels, vallines):
                if lines is None or lines == [None]:
                    continue
                # Use the label only for the first item. For the remaining
                # items, use an empty label.
                labels_ = chain([label], itertools.repeat(''))
                for label_, line in zip(labels_, lines):
                    print('%*s : %s' % (width, label_, line))
            print()

