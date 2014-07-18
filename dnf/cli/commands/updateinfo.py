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
from dnf.cli import commands
from dnf.i18n import _
from dnf.pycomp import unicode

import collections
import dnf.exceptions
import itertools
import hawkey

class UpdateInfoCommand(commands.Command):
    """Implementation of the UpdateInfo command."""

    aliases = ['updateinfo']
    summary = _('Display advisories about packages')
    usage = ''

    def configure(self, args):
        """Do any command-specific configuration based on command arguments."""
        super(UpdateInfoCommand, self).configure(args)
        self.cli.demands.sack_activation = True

    def _advisories(self):
        """Return available advisories."""
        return itertools.chain.from_iterable(
            pkg.get_advisories(hawkey.GT)
            for pkg in self.base.sack.query().installed())

    @staticmethod
    def _summary(advisories):
        """Make the summary of advisories."""
        # Remove duplicate advisory IDs. We assume that the ID is unique within
        # a repository and two advisories with the same IDs in different
        # repositories must have the same type.
        id2type = {advisory.id: advisory.type for advisory in advisories}
        return collections.Counter(id2type.values())

    @staticmethod
    def _display(typ2cnt, description):
        """Display the summary of advisories."""
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
        label2value = collections.OrderedDict(
            (label, unicode(count)) for label, count in label_counts if count)
        width = max(len(string) for string in label2value.values())
        for label, value in label2value.items():
            print('    %*s %s' % (width, value, label))

    def run(self, args):
        """Execute the command with arguments."""
        super(UpdateInfoCommand, self).run(args)
        if args[:1] in (['summary'], []):
            args = args[1:]
        if args not in (['available'], []):
            raise dnf.exceptions.Error('invalid command arguments')
        self._display(self._summary(self._advisories()), _('available'))
