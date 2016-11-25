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
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _
from dnf.pycomp import unicode
from itertools import chain
from operator import itemgetter

import collections
import fnmatch
import itertools
import hawkey

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

    aliases = ['updateinfo']
    summary = _('display advisories about packages')

    def __init__(self, cli):
        """Initialize the command."""
        super(UpdateInfoCommand, self).__init__(cli)
        self._ina2evr_cache = None
        self.clear_installed_cache()

    def refresh_installed_cache(self):
        """Fill the cache of installed packages."""
        self._ina2evr_cache = {(pkg.name, pkg.arch): pkg.evr
                               for pkg in self.base.sack.query().installed()}

    def clear_installed_cache(self):
        """Clear the cache of installed packages."""
        self._ina2evr_cache = None

    def _older_installed(self, apackage):
        """Test whether an older version of a package is installed."""
        # Non-cached lookup not implemented. Fill the cache or implement the
        # functionality via the slow sack query.
        assert self._ina2evr_cache is not None
        try:
            ievr = self._ina2evr_cache[(apackage.name, apackage.arch)]
        except KeyError:
            return False
        q = self.base.sack.query().filter(name=apackage.name, evr=apackage.evr)
        if len(self.base._merge_update_filters(q, warning=False)) == 0:
            return False
        return self.base.sack.evr_cmp(ievr, apackage.evr) < 0

    def _newer_equal_installed(self, apkg):
        """Test whether a newer or equal version of a package is installed."""
        # Non-cached lookup not implemented. Fill the cache or implement the
        # functionality via the slow sack query.
        assert self._ina2evr_cache is not None
        try:
            ievr = self._ina2evr_cache[(apkg.name, apkg.arch)]
        except KeyError:
            return False
        q = self.base.sack.query().filter(name=apkg.name, evr=apkg.evr)
        if len(self.base._merge_update_filters(q, warning=False)) == 0:
            return False
        return self.base.sack.evr_cmp(ievr, apkg.evr) >= 0

    def _any_installed(self, apkg):
        """Test whether any version of a package is installed."""
        # Non-cached lookup not implemented. Fill the cache or implement the
        # functionality via the slow sack query.
        assert self._ina2evr_cache is not None
        q = self.base.sack.query().filter(name=apkg.name, evr=apkg.evr)
        if len(self.base._merge_update_filters(q, warning=False)) == 0:
            return False
        return (apkg.name, apkg.arch) in self._ina2evr_cache

    @staticmethod
    def set_argparser(parser):
        cmds = ['summary', 'list', 'info']
        parser.add_argument('spec', nargs='*', metavar='SPEC',
                            choices=cmds, default=cmds[0],
                            action=OptionParser.PkgNarrowCallback)

    def configure(self):
        """Do any command-specific configuration based on command arguments."""
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

    @staticmethod
    def _apackage_advisory_match(apackage, advisory, specs=()):
        """Test whether an (adv. pkg., adv.) pair matches specifications."""

        if not specs:
            return True

        specs = set(specs)
        types = set()
        if 'bugfix' in specs:
            types.add(hawkey.ADVISORY_BUGFIX)
        if 'enhancement' in specs:
            types.add(hawkey.ADVISORY_ENHANCEMENT)
        if {'security', 'sec'} & specs:
            types.add(hawkey.ADVISORY_SECURITY)
        if 'newpackage' in specs:
            types.add(hawkey.ADVISORY_NEWPACKAGE)

        return (any(fnmatch.fnmatchcase(advisory.id, pat) for pat in specs) or
                advisory.type in types or
                any(fnmatch.fnmatchcase(apackage.name, pat) for pat in specs))

    def _apackage_advisory_installeds(self, pkgs, cmptype, req_apkg, specs=()):
        """Return (adv. package, advisory, installed) triplets and a flag."""
        for package in pkgs:
            for advisory in package.get_advisories(cmptype):
                for apackage in advisory.packages:
                    passed = (req_apkg(apackage) and
                              self._apackage_advisory_match(
                                  apackage, advisory, specs))
                    if passed:
                        installed = self._newer_equal_installed(apackage)
                        yield apackage, advisory, installed

    def available_apkg_adv_insts(self, specs=()):
        """Return available (adv. package, adv., inst.) triplets and a flag."""
        return False, self._apackage_advisory_installeds(
            self.base.sack.query().installed(), hawkey.GT,
            self._older_installed, specs)

    def installed_apkg_adv_insts(self, specs=()):
        """Return installed (adv. package, adv., inst.) triplets and a flag."""
        return False, self._apackage_advisory_installeds(
            self.base.sack.query().installed(), hawkey.LT | hawkey.EQ,
            self._newer_equal_installed, specs)

    def updating_apkg_adv_insts(self, specs=()):
        """Return updating (adv. package, adv., inst.) triplets and a flag."""
        return False, self._apackage_advisory_installeds(
            self.base.sack.query().filter(upgradable=True), hawkey.GT,
            self._older_installed, specs)

    def all_apkg_adv_insts(self, specs=()):
        """Return installed (adv. package, adv., inst.) triplets and a flag."""
        ipackages = self.base.sack.query().installed()
        gttriplets = self._apackage_advisory_installeds(
            ipackages, hawkey.GT, self._any_installed, specs)
        lteqtriplets = self._apackage_advisory_installeds(
            ipackages, hawkey.LT | hawkey.EQ, self._any_installed, specs)
        return True, chain(gttriplets, lteqtriplets)

    @staticmethod
    def _summary(apkg_adv_insts):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {pkadin[1].id: pkadin[1].type for pkadin in apkg_adv_insts}
        return collections.Counter(id2type.values())

    @classmethod
    def display_summary(cls, apkg_adv_insts, mixed, description):
        """Display the summary of advisories."""
        typ2cnt = cls._summary(apkg_adv_insts)
        if not typ2cnt:
            return
        print(_('Updates Information Summary: ') + description)
        # Convert types to strings and order the entries.
        label_counts = [
            (_('New Package notice(s)'), typ2cnt[hawkey.ADVISORY_NEWPACKAGE]),
            (_('Security notice(s)'), typ2cnt[hawkey.ADVISORY_SECURITY]),
            (_('Bugfix notice(s)'), typ2cnt[hawkey.ADVISORY_BUGFIX]),
            (_('Enhancement notice(s)'), typ2cnt[hawkey.ADVISORY_ENHANCEMENT]),
            (_('other notice(s)'), typ2cnt[hawkey.ADVISORY_UNKNOWN])]
        # Convert counts to strings and skip missing types.
        label2value = OrderedDict(
            (label, unicode(count)) for label, count in label_counts if count)
        width = _maxlen(label2value.values())
        for label, value in label2value.items():
            print('    %*s %s' % (width, value, label))

    @staticmethod
    def _list(apkg_adv_insts):
        """Make the list of advisories."""
        # Get ((NEVRA, installed), advisory ID, advisory type)
        apkg2nevra = lambda apkg: apkg.name + '-' + apkg.evr + '.' + apkg.arch
        nevrains_id_types = (
            ((apkg2nevra(apkg), inst), adv.id, adv.type)
            for apkg, adv, inst in apkg_adv_insts)
        # Sort and group by (NEVRA, installed).
        nevrains_nits = itertools.groupby(
            sorted(nevrains_id_types, key=itemgetter(0)), key=itemgetter(0))
        for nevra_ins, nits in nevrains_nits:
            # Remove duplicate IDs. We assume that two advisories with the same
            # IDs (e.g. from different repositories) must have the same type.
            yield nevra_ins, {nit[1]: nit[2] for nit in nits}

    @classmethod
    def display_list(cls, apkg_adv_insts, mixed, description):
        """Display the list of advisories."""
        # Sort IDs and convert types to labels.
        inst2mark = lambda inst: '' if not mixed else 'i ' if inst else '  '
        nevramark2id2tlbl = OrderedDict(
            ((nevra, inst2mark(inst)),
             OrderedDict(sorted(((id_, cls.TYPE2LABEL[typ])
                                 for id_, typ in id2type.items()),
                                key=itemgetter(0))))
            for (nevra, inst), id2type in cls._list(apkg_adv_insts))
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
                    apkg_adv_inst[1].rights,
                    (pkg.filename for pkg in apkg_adv_inst[1].packages
                     if pkg.arch in self.base.sack.list_arches()),
                    inst)
            else:
                # If the stored advisory is marked as not installed and the
                # current is marked as installed, mark the stored as installed.
                if not tuple_[9] and inst:
                    id2tuple[identity] = tuple_[:9] + (inst,)
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
                title, (None, None, None, [], [], None, None, [], False))
            title2info[title] = (
                new[:3] +
                (merge(old[3], new[3]),
                 merge(old[4], new[4])) +
                new[5:7] +
                (merge(old[7], new[7]),
                 old[8] or new[8]))
        return title2info

    def display_info(self, apkg_adv_insts, mixed, description):
        """Display the details about available advisories."""
        info = self._info(apkg_adv_insts).items()
        # Convert objects to string lines and mark verbose fields.
        verbse = lambda value: value if self.base.conf.verbose else None
        info = (
            (tit, ([id_], [self.TYPE2LABEL[typ]], [unicode(upd)],
                   (id_title[0] + ' - ' + id_title[1] for id_title in bzs),
                   (id_title[0] for id_title in cvs), desc.splitlines(),
                   verbse(rigs.splitlines() if rigs else None), verbse(fils),
                   None if not mixed else [_('true') if ins else _('false')]))
            for tit, (id_, typ, upd, bzs, cvs, desc, rigs, fils, ins) in info)
        labels = (_('Update ID'), _('Type'), _('Updated'), _('Bugs'),
                  _('CVEs'), _('Description'), _('Rights'), _('Files'),
                  _('Installed'))
        width = _maxlen(labels)
        for title, vallines in info:
            print('=' * 79)
            print('  ' + title)
            print('=' * 79)
            for label, lines in zip(labels, vallines):
                if lines is None:
                    continue
                # Use the label only for the first item. For the remaining
                # items, use an empty label.
                labels_ = chain([label], itertools.repeat(''))
                for label_, line in zip(labels_, lines):
                    print('%*s : %s' % (width, label_, line))
            print()

    def run(self):
        """Execute the command with arguments."""
        self.cli._populate_update_security_filter(self.opts, minimal=True)

        args = self.opts.spec
        display = self.display_summary
        if self.opts.spec_action == 'list':
            display = self.display_list
        elif self.opts.spec_action == 'info':
            display = self.display_info

        self.refresh_installed_cache()

        if args[:1] == ['installed']:
            mixed, apkg_adv_insts = self.installed_apkg_adv_insts(args[1:])
            description = _('installed')
        elif args[:1] == ['updates']:
            mixed, apkg_adv_insts = self.updating_apkg_adv_insts(args[1:])
            description = _('updates')
        elif args[:1] == ['all']:
            mixed, apkg_adv_insts = self.all_apkg_adv_insts(args[1:])
            description = _('all')
        else:
            if args[:1] == ['available']:
                args = args[1:]
            mixed, apkg_adv_insts = self.available_apkg_adv_insts(args)
            description = _('available')

        display(apkg_adv_insts, mixed, description)

        self.clear_installed_cache()
