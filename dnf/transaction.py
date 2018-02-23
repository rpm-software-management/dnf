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

import libdnf.swdb

from dnf.i18n import _


# per-package actions - errors
PKG_FAIL = -1

# per-package actions - from libdnf
PKG_DOWNGRADE = libdnf.swdb.TransactionItemAction_DOWNGRADE
PKG_DOWNGRADED = libdnf.swdb.TransactionItemAction_DOWNGRADED
PKG_INSTALL = libdnf.swdb.TransactionItemAction_INSTALL
PKG_OBSOLETE = libdnf.swdb.TransactionItemAction_OBSOLETE
PKG_OBSOLETED = libdnf.swdb.TransactionItemAction_OBSOLETED
PKG_REINSTALL = libdnf.swdb.TransactionItemAction_REINSTALL
PKG_REINSTALLED = libdnf.swdb.TransactionItemAction_REINSTALLED
PKG_REMOVE = libdnf.swdb.TransactionItemAction_REMOVE
PKG_UPGRADE = libdnf.swdb.TransactionItemAction_UPGRADE
PKG_UPGRADED = libdnf.swdb.TransactionItemAction_UPGRADED

# compatibility
PKG_ERASE = PKG_REMOVE

# per-package actions - additional
PKG_CLEANUP = 101
PKG_VERIFY = 102
PKG_SCRIPTLET = 103

# transaction-wide actions
TRANS_PREPARATION = 201
TRANS_POST = 202


ACTIONS = {
    # TODO: PKG_FAIL

    PKG_DOWNGRADE: _('Downgrading'),
    PKG_INSTALL: _('Installing'),
    PKG_OBSOLETE: _('Obsoleting'),
    PKG_REINSTALL: _('Reinstalling'),
    # TODO: 'Removing'?
    PKG_REMOVE: _('Erasing'),
    PKG_UPGRADE: _('Upgrading'),

    PKG_CLEANUP: _('Cleanup'),
    PKG_VERIFY: _('Verifying'),
    PKG_SCRIPTLET: _('Running scriptlet'),

    TRANS_PREPARATION: _('Preparing'),
    # TODO: TRANS_POST
}


# untranslated strings, logging to /var/log/dnf/dnf.rpm.log
FILE_ACTIONS = {
    # TODO: PKG_FAIL

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
