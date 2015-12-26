# package.py
# Module defining the dnf.Package class.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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

""" Contains the dnf.Package class. """

from __future__ import absolute_import
from __future__ import unicode_literals

import binascii
import dnf.rpm
import dnf.yum.misc
import hawkey
import logging
import os

logger = logging.getLogger("dnf")


class Package(hawkey.Package):
    """ Represents a package. #:api """

    def __init__(self, initobject, base):
        super(Package, self).__init__(initobject)
        self.base = base
        self._chksum = None
        self._repo = None
        self._size = None

    @property
    def chksum(self):
        if self._chksum:
            return self._chksum
        if self.from_cmdline:
            chksum_type = dnf.yum.misc.get_default_chksum_type()
            chksum_val = dnf.yum.misc.checksum(chksum_type, self.location)
            return (hawkey.chksum_type(chksum_type),
                    binascii.unhexlify(chksum_val))
        return super(Package, self).chksum

    @chksum.setter
    def chksum(self, val):
        self._chksum = val

    @property
    def from_cmdline(self):
        return self.reponame == hawkey.CMDLINE_REPO_NAME

    @property
    def from_system(self):
        return self.reponame == hawkey.SYSTEM_REPO_NAME

    @property
    def from_repo(self):
        yumdb_info = self.base.yumdb.get_package(self) if self.from_system else {}
        if 'from_repo' in yumdb_info:
            return '@'+yumdb_info.from_repo
        return self.reponame

    @property
    def header(self):
        return dnf.rpm.header(self.localPkg())

    @property
    def size(self):
        if self._size:
            return self._size
        return super(Package, self).size

    @size.setter
    def size(self, val):
        self._size = val

    @property
    def pkgid(self):
        try:
            (_, chksum) = self.hdr_chksum
            return binascii.hexlify(chksum)
        except AttributeError:
            return None

    @property # yum compatibility attribute
    def idx(self):
        """ Always type it to int, rpm bindings expect it like that. """
        return int(self.rpmdbid)

    @property # yum compatibility attribute
    def repoid(self):
        return self.reponame

    @property # yum compatibility attribute
    def pkgtup(self):
        return (self.name, self.arch, str(self.e), self.v, self.r)

    @property # yum compatibility attribute
    def repo(self):
        if self._repo:
            return self._repo
        return self.base.repos[self.reponame]

    @repo.setter
    def repo(self, val):
        self._repo = val

    @property # yum compatibility attribute
    def relativepath(self):
        return self.location

    @property # yum compatibility attribute
    def a(self):
        return self.arch

    @property # yum compatibility attribute
    def e(self):
        return self.epoch

    @property # yum compatibility attribute
    def v(self):
        return self.version

    @property # yum compatibility attribute
    def r(self):
        return self.release

    @property # yum compatibility attribute
    def ui_from_repo(self):
        return self.reponame

    # yum compatibility method
    def evr_eq(self, pkg):
        return self.evr_cmp(pkg) == 0

    # yum compatibility method
    def evr_gt(self, pkg):
        return self.evr_cmp(pkg) > 0

    # yum compatibility method
    def evr_lt(self, pkg):
        return self.evr_cmp(pkg) < 0

    # yum compatibility method
    def getDiscNum(self):
        return self.medianr

    # yum compatibility method
    def localPkg(self):
        """ Package's location in the filesystem.

            For packages in remote repo returns where the package will be/has
            been downloaded.
        """
        if self.from_cmdline:
            return self.location
        if self.baseurl:
            path = os.path.join(self.baseurl, self.location)
            if path.startswith("file://"):
                path = path[7:]
            return path
        loc = self.location
        if not self.repo.local:
            loc = os.path.basename(loc)
        return os.path.join(self.repo.pkgdir, loc)

    # yum compatibility method
    def returnIdSum(self):
        """ Return the chksum type and chksum string how the legacy yum expects
            it.
        """
        (chksum_type, chksum) = self.chksum
        return (hawkey.chksum_name(chksum_type), binascii.hexlify(chksum).decode())

    # yum compatibility method
    def verifyLocalPkg(self):
        if self.from_system:
            raise ValueError("Can not verify an installed package.")
        if self.from_cmdline:
            return True # local package always verifies against itself
        (chksum_type, chksum) = self.returnIdSum()
        real_sum = dnf.yum.misc.checksum(chksum_type, self.localPkg(),
                                         datasize=self.size)
        if real_sum != chksum:
            logger.debug('%s: %s check failed: %s vs %s',
                         self, chksum_type, real_sum, chksum)
            return False
        return True
