# updateinfo.py
# UpdateInfo CLI command.
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

"""UpdateInfo CLI command."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from collections import OrderedDict
from dnf.cli import commands
from dnf.i18n import _
from dnf.pycomp import unicode
from itertools import chain
from operator import itemgetter

import collections
import dnf.exceptions
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
                  hawkey.ADVISORY_UNKNOWN: _('unknown')}

    aliases = ['updateinfo']
    summary = _('Display advisories about packages')
    usage = ''

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
        return self.base.sack.evr_cmp(ievr, apkg.evr) >= 0

    def configure(self, args):
        """Do any command-specific configuration based on command arguments."""
        super(UpdateInfoCommand, self).configure(args)
        self.cli.demands.sack_activation = True

    def _apackage_advisories(self, cmptype, requested_apkg):
        """Return (advisory package, advisory) pairs."""
        for package in self.base.sack.query().installed():
            for advisory in package.get_advisories(cmptype):
                for apackage in advisory.packages:
                    if requested_apkg(apackage):
                        yield apackage, advisory

    def available_apackage_advisories(self):
        """Return available (advisory package, advisory) pairs."""
        return self._apackage_advisories(hawkey.GT, self._older_installed)

    def installed_apackage_advisories(self):
        """Return installed (advisory package, advisory) pairs."""
        return self._apackage_advisories(
            hawkey.LT | hawkey.EQ, self._newer_equal_installed)

    @staticmethod
    def _summary(apkg_advs):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {apkg_adv[1].id: apkg_adv[1].type for apkg_adv in apkg_advs}
        return collections.Counter(id2type.values())

    @classmethod
    def display_summary(cls, apkg_advs, description):
        """Display the summary of advisories."""
        typ2cnt = cls._summary(apkg_advs)
        if not typ2cnt:
            return
        print(_('Updates Information Summary: ') + description)
        # Convert types to strings and order the entries.
        label_counts = [
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
    def _list(apkg_advs):
        """Make the list of advisories."""
        # Get (NEVRA, advisory ID, advisory type)
        apkg2nevra = lambda apkg: apkg.name + '-' + apkg.evr + '.' + apkg.arch
        nevra_id_types = (
            (apkg2nevra(apkg), adv.id, adv.type)
            for apkg, adv in apkg_advs)
        # Sort and group by NEVRAs.
        nevra_nits = itertools.groupby(
            sorted(nevra_id_types, key=itemgetter(0)), key=itemgetter(0))
        for nevra, nits in nevra_nits:
            # Remove duplicate IDs. We assume that two advisories with the same
            # IDs (e.g. from different repositories) must have the same type.
            yield nevra, {nit[1]: nit[2] for nit in nits}

    @classmethod
    def display_list(cls, apkg_advs, description):
        """Display the list of advisories."""
        nevra_id2types = cls._list(apkg_advs)
        # Sort IDs and convert types to labels.
        nevra2id2tlbl = OrderedDict(
            (nevra, OrderedDict(sorted(((id_, cls.TYPE2LABEL[typ])
                                        for id_, typ in id2type.items()),
                                       key=itemgetter(0))))
            for nevra, id2type in nevra_id2types)
        if not nevra2id2tlbl:
            return
        # Get all advisory IDs and types as two iterables.
        ids, tlbls = zip(*chain.from_iterable(
            id2tlbl.items() for id2tlbl in nevra2id2tlbl.values()))
        idw, tlw = _maxlen(ids), _maxlen(tlbls)
        for nevra, id2tlbl in nevra2id2tlbl.items():
            for id_, tlbl in id2tlbl.items():
                print('%-*s %-*s %s' % (idw, id_, tlw, tlbl, nevra))

    def _info(self, apkg_advs):
        """Make detailed information about advisories."""
        # Get mapping from identity to (title, ID, type, time, BZs, CVEs,
        # description, rights, files). This way we get rid of unneeded advisory
        # packages given with the advisories and we remove duplicate advisories
        # (that SPEEDS UP the information extraction because the advisory
        # attribute getters are expensive, so we won't get the attributes
        # multiple times). We cannot use a set because advisories are not
        # hashable.
        getrefs = lambda apkg, typ: (
            (ref.id, ref.title) for ref in apkg.references if ref.type == typ)
        id2tuple = OrderedDict()
        for apkg_adv in apkg_advs:
            identity = id(apkg_adv[1])
            # Don't use id2tuple.setdefault because we don't want to access the
            # attributes unless needed.
            if identity not in id2tuple:
                id2tuple[identity] = (
                    apkg_adv[1].title,
                    apkg_adv[1].id,
                    apkg_adv[1].type,
                    apkg_adv[1].updated,
                    getrefs(apkg_adv[1], hawkey.REFERENCE_BUGZILLA),
                    getrefs(apkg_adv[1], hawkey.REFERENCE_CVE),
                    apkg_adv[1].description,
                    apkg_adv[1].rights,
                    (pkg.filename for pkg in apkg_adv[1].packages
                     if pkg.arch in self.base.sack.list_arches()))
        # Get mapping from title to (ID, type, time, BZs, CVEs, description,
        # rights, files) => group by titles and merge values. We assume that
        # two advisories with the same title (e.g. from different repositories)
        # must have the same ID, type, time, description and rights.
        # References and files are merged.
        merge = lambda old, new: set(chain(old, new))
        title2info = OrderedDict()
        for tuple_ in id2tuple.values():
            title, new = tuple_[0], tuple_[1:]
            old = title2info.get(
                title, (None, None, None, [], [], None, None, []))
            title2info[title] = (
                new[:3] +
                (merge(old[3], new[3]),
                 merge(old[4], new[4])) +
                new[5:7] +
                (merge(old[7], new[7]),))
        return title2info

    def display_info(self, apkg_advs, description):
        """Display the details about available advisories."""
        info = self._info(apkg_advs).items()
        # Convert objects to string lines and mark verbose fields.
        verbose = lambda value: value if self.base.conf.verbose else None
        title_vallines = (
            (title, ([id_], [self.TYPE2LABEL[type_]], [unicode(upd)],
                     (id_title[0] + ' - ' + id_title[1] for id_title in bzs),
                     (id_title[0] for id_title in cvs), desc.splitlines(),
                     verbose(rigs.splitlines() if rigs else None),
                     verbose(fils)))
             for title, (id_, type_, upd, bzs, cvs, desc, rigs, fils) in info)
        labels = (_('Update ID'), _('Type'), _('Updated'), _('Bugs'),
                  _('CVEs'), _('Description'), _('Rights'), _('Files'))
        width = _maxlen(labels)
        for title, vallines in title_vallines:
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

    def run(self, args):
        """Execute the command with arguments."""

        super(UpdateInfoCommand, self).run(args)
        display = self.display_summary
        if args[:1] in (['summary'], []):
            args = args[1:]
        elif args[:1] == ['list']:
            display, args = self.display_list, args[1:]
        elif args[:1] == ['info']:
            display, args = self.display_info, args[1:]

        self.refresh_installed_cache()

        apackage_advisories = self.available_apackage_advisories()
        description = _('available')
        if args == ['installed']:
            apackage_advisories = self.installed_apackage_advisories()
            description = _('installed')
        elif args not in (['available'], []):
            raise dnf.exceptions.Error('invalid command arguments')

        display(apackage_advisories, description)

        self.clear_installed_cache()
