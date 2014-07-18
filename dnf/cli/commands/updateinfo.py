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

    def configure(self, args):
        """Do any command-specific configuration based on command arguments."""
        super(UpdateInfoCommand, self).configure(args)
        self.cli.demands.sack_activation = True

    def _apackage_advisories(self):
        """Return (advisory package, advisory) pairs."""
        for package in self.base.sack.query().installed():
            for advisory in package.get_advisories(hawkey.GT):
                for apackage in advisory.packages:
                    if self._older_installed(apackage):
                        yield apackage, advisory

    @staticmethod
    def _summary(apkg_advs):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {apkg_adv[1].id: apkg_adv[1].type for apkg_adv in apkg_advs}
        return collections.Counter(id2type.values())

    @classmethod
    def _display_summary(cls, apkg_advs, description):
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
    def _display_list(cls, apkg_advs, description):
        """Display the list of advisories."""

        type2lbl = {hawkey.ADVISORY_BUGFIX: _('bugfix'),
                    hawkey.ADVISORY_ENHANCEMENT: _('enhancement'),
                    hawkey.ADVISORY_SECURITY: _('security'),
                    hawkey.ADVISORY_UNKNOWN: _('unknown')}

        nevra_id2types = cls._list(apkg_advs)
        # Sort IDs and convert types to labels.
        nevra2id2tlbl = OrderedDict(
            (nevra, OrderedDict(sorted(((id_, type2lbl[typ])
                                        for id_, typ in id2type.items()),
                                       key=itemgetter(0))))
            for nevra, id2type in nevra_id2types)
        if not nevra2id2tlbl:
            return
        # Get all advisory IDs and types as two iterables.
        ids, tlbls = zip(*itertools.chain.from_iterable(
            id2tlbl.items() for id2tlbl in nevra2id2tlbl.values()))
        idw, tlw = _maxlen(ids), _maxlen(tlbls)
        for nevra, id2tlbl in nevra2id2tlbl.items():
            for id_, tlbl in id2tlbl.items():
                print('%-*s %-*s %s' % (idw, id_, tlw, tlbl, nevra))

    def run(self, args):
        """Execute the command with arguments."""

        super(UpdateInfoCommand, self).run(args)
        display = self._display_summary
        if args[:1] in (['summary'], []):
            args = args[1:]
        elif args[:1] == ['list']:
            display, args = self._display_list, args[1:]

        if args not in (['available'], []):
            raise dnf.exceptions.Error('invalid command arguments')

        self.refresh_installed_cache()
        display(self._apackage_advisories(), _('available'))
        self.clear_installed_cache()
