# history.py
# Interfaces to the history of transactions.
#
# Copyright (C) 2013  Red Hat, Inc.
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

"""Interfaces to the history of transactions."""

from __future__ import absolute_import
from dnf.util import split_by
from dnf.yum.history import YumHistory

def open_history(database, sack):
    """Open a history of transactions."""
    if isinstance(database, YumHistory):
        return _HistoryWrapper(database, sack)
    else:
        raise TypeError("unsupported database type: %s" % type(database))

class _HistoryWrapper(object):
    """Transactions history interface on top of an YumHistory."""

    def __init__(self, yum_history, sack):
        """Initialize a wrapper instance."""
        object.__init__(self)
        self._history = yum_history
        self._sack = sack

    def __enter__(self):
        """Enter the runtime context."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Exit the runtime context."""
        self.close()
        return False

    def close(self):
        """Close the history."""
        self._history.close()

    def has_transaction(self, id_):
        """Test whether a transaction with given ID is stored."""
        return bool(self._history.old((str(id_),)))

    def last_transaction_id(self):
        """Get ID of the last stored transaction."""
        last_tx = self._history.last(complete_transactions_only=False)
        return last_tx.tid if last_tx else None

    def transaction_items_ops(self, id_):
        """Get iterable of package manipulations of each transaction item."""
        if not self.has_transaction(id_):
            raise ValueError('no transaction with given ID: %d' % id_)

        hpkgs = self._history._old_data_pkgs(str(id_), sort=False)

        # Split history to history packages representing transaction items.
        states = {'Install', 'Erase', 'Reinstall', 'Downgrade', 'Update'}
        items_hpkgs = split_by(hpkgs, lambda hpkg: hpkg.state in states)

        # First item should be empty if the first state is valid.
        empty_item_hpkgs = next(items_hpkgs)
        if empty_item_hpkgs:  # not empty
            msg = 'corrupted history starting with: %s'
            raise ValueError(msg % empty_item_hpkgs[0].state)

        # Return the items.
        return (((hpkg.nevra, hpkg.state) for hpkg in item_hpkgs)
                for item_hpkgs in items_hpkgs)
