# sack.py
# The dnf.Sack class, derived from hawkey.Sack
#
# Copyright (C) 2012-2015  Red Hat, Inc.
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
import dnf.yum.misc
import dnf.package
import dnf.query
import hawkey
import os
from dnf.pycomp import basestring

class SackVersion(object):
    def __init__(self):
        self._num = 0
        self._chksum = dnf.yum.misc.Checksums(['sha1'])

    def __str__(self):
        return "%u:%s" % (self._num, self._chksum.hexdigest())

    def __eq__(self, other):
        if other is None: return False
        if isinstance(other, basestring):
            return str(self) == other
        if self._num != other._num: return False
        if self._chksum.digest() != other._chksum.digest(): return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def update(self, pkg, csum):
        self._num += 1
        self._chksum.update(str(pkg))
        if csum is not None:
            self._chksum.update(csum[0])
            self._chksum.update(csum[1])

class Sack(hawkey.Sack):
    def __init__(self, *args, **kwargs):
        super(Sack, self).__init__(*args, **kwargs)

    def configure(self, installonly=None, installonly_limit=0):
        if installonly:
            self.installonly = installonly
        self.installonly_limit = installonly_limit

    def query(self):
        """Factory function returning a DNF Query. :api"""
        return dnf.query.Query(self)

    def rpmdb_version(self, yumdb):
        pkgs = self.query().installed().run()
        main = SackVersion()
        for pkg in pkgs:
            ydbi = yumdb.get_package(pkg)
            csum = None
            if 'checksum_type' in ydbi and 'checksum_data' in ydbi:
                csum = (ydbi.checksum_type, ydbi.checksum_data)
            main.update(pkg, csum)
        return main

def build_sack(base):
    cachedir = base.conf.cachedir
    # create the dir ourselves so we have the permissions under control:
    dnf.util.ensure_dir(cachedir)
    return Sack(pkgcls=dnf.package.Package, pkginitval=base,
                arch=base.conf.substitutions["arch"],
                cachedir=cachedir, rootdir=base.conf.installroot,
                logfile=os.path.join(base.conf.logdir, dnf.const.LOG_HAWKEY))

def rpmdb_sack(base):
    sack = build_sack(base)
    sack.load_system_repo()
    return sack
