# -*- coding: utf-8 -*-

# transaction.py
# Managing the transaction to be passed to RPM.
#
# Copyright (C) 2013-2018 Red Hat, Inc.
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
from __future__ import unicode_literals

import libdnf.transaction

from dnf.i18n import _, C_

# :api - all action constants are considered an API

# per-package actions - from libdnf
PKG_DOWNGRADE = libdnf.transaction.TransactionItemAction_DOWNGRADE
PKG_DOWNGRADED = libdnf.transaction.TransactionItemAction_DOWNGRADED
PKG_INSTALL = libdnf.transaction.TransactionItemAction_INSTALL
PKG_OBSOLETE = libdnf.transaction.TransactionItemAction_OBSOLETE
PKG_OBSOLETED = libdnf.transaction.TransactionItemAction_OBSOLETED
PKG_REINSTALL = libdnf.transaction.TransactionItemAction_REINSTALL
PKG_REINSTALLED = libdnf.transaction.TransactionItemAction_REINSTALLED
PKG_REMOVE = libdnf.transaction.TransactionItemAction_REMOVE
PKG_UPGRADE = libdnf.transaction.TransactionItemAction_UPGRADE
PKG_UPGRADED = libdnf.transaction.TransactionItemAction_UPGRADED

# compatibility
PKG_ERASE = PKG_REMOVE

# per-package actions - additional
PKG_CLEANUP = 101
PKG_VERIFY = 102
PKG_SCRIPTLET = 103

# transaction-wide actions
TRANS_PREPARATION = 201
TRANS_POST = 202


# packages that appeared on the system
FORWARD_ACTIONS = [
    libdnf.transaction.TransactionItemAction_INSTALL,
    libdnf.transaction.TransactionItemAction_DOWNGRADE,
    libdnf.transaction.TransactionItemAction_OBSOLETE,
    libdnf.transaction.TransactionItemAction_UPGRADE,
    libdnf.transaction.TransactionItemAction_REINSTALL,
]


# packages that got removed from the system
BACKWARD_ACTIONS = [
    libdnf.transaction.TransactionItemAction_DOWNGRADED,
    libdnf.transaction.TransactionItemAction_OBSOLETED,
    libdnf.transaction.TransactionItemAction_UPGRADED,
    libdnf.transaction.TransactionItemAction_REMOVE,
# TODO: REINSTALLED may and may not belong here; the same NEVRA is in FORWARD_ACTIONS already
#    libdnf.transaction.TransactionItemAction_REINSTALLED,
]


ACTIONS = {
    # TRANSLATORS: This is for a single package currently being downgraded.
    PKG_DOWNGRADE: C_('currently', 'Downgrading'),
    PKG_DOWNGRADED: _('Cleanup'),
    # TRANSLATORS: This is for a single package currently being installed.
    PKG_INSTALL: C_('currently', 'Installing'),
    PKG_OBSOLETE: _('Obsoleting'),
    PKG_OBSOLETED: _('Obsoleting'),
    # TRANSLATORS: This is for a single package currently being reinstalled.
    PKG_REINSTALL: C_('currently', 'Reinstalling'),
    PKG_REINSTALLED: _('Cleanup'),
    # TODO: 'Removing'?
    PKG_REMOVE: _('Erasing'),
    # TRANSLATORS: This is for a single package currently being upgraded.
    PKG_UPGRADE: C_('currently', 'Upgrading'),
    PKG_UPGRADED: _('Cleanup'),

    PKG_CLEANUP: _('Cleanup'),
    PKG_VERIFY: _('Verifying'),
    PKG_SCRIPTLET: _('Running scriptlet'),

    TRANS_PREPARATION: _('Preparing'),
    # TODO: TRANS_POST
}


# untranslated strings, logging to /var/log/dnf/dnf.rpm.log
FILE_ACTIONS = {
    PKG_DOWNGRADE: 'Downgrade',
    PKG_DOWNGRADED: 'Downgraded',
    PKG_INSTALL: 'Installed',
    PKG_OBSOLETE: 'Obsolete',
    PKG_OBSOLETED: 'Obsoleted',
    PKG_REINSTALL: 'Reinstall',
    PKG_REINSTALLED: 'Reinstalled',
    # TODO: 'Removed'?
    PKG_REMOVE: 'Erase',
    PKG_UPGRADE: 'Upgrade',
    PKG_UPGRADED: 'Upgraded',

    PKG_CLEANUP: 'Cleanup',
    PKG_VERIFY: 'Verified',
    PKG_SCRIPTLET: 'Running scriptlet',

    TRANS_PREPARATION: 'Preparing',
    # TODO: TRANS_POST
}
