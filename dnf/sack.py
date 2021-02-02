# sack.py
# The dnf.Sack class, derived from hawkey.Sack
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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
import dnf.util
import dnf.package
import dnf.query
import logging
import hawkey
import os
from dnf.pycomp import basestring
from dnf.i18n import _

logger = logging.getLogger("dnf")

class Sack(hawkey.Sack):
    # :api

    def __init__(self, *args, **kwargs):
        super(Sack, self).__init__(*args, **kwargs)

    def _configure(self, installonly=None, installonly_limit=0, allow_vendor_change=None):
        if installonly:
            self.installonly = installonly
        self.installonly_limit = installonly_limit
        if allow_vendor_change is not None:
            self.allow_vendor_change = allow_vendor_change
            if allow_vendor_change is False:
                logger.warning(_("allow_vendor_change is disabled. This option is currently not supported for downgrade and distro-sync commands"))

    def query(self, flags=0):
        # :api
        """Factory function returning a DNF Query."""
        return dnf.query.Query(self, flags)


def _build_sack(base):
    cachedir = base.conf.cachedir
    # create the dir ourselves so we have the permissions under control:
    dnf.util.ensure_dir(cachedir)
    return Sack(pkgcls=dnf.package.Package, pkginitval=base,
                arch=base.conf.substitutions["arch"],
                cachedir=cachedir, rootdir=base.conf.installroot,
                logfile=os.path.join(base.conf.logdir, dnf.const.LOG_HAWKEY),
                logdebug=base.conf.logfilelevel > 9)


def _rpmdb_sack(base):
    # used by subscription-manager (src/dnf-plugins/product-id.py)
    sack = _build_sack(base)
    try:
        # It can fail if rpmDB is not present
        sack.load_system_repo(build_cache=False)
    except IOError:
        pass
    return sack


def rpmdb_sack(base):
    # :api
    """
    Returns a new instance of sack containing only installed packages (@System repo)
    Useful to get list of the installed RPMs after transaction.
    """
    return _rpmdb_sack(base)
