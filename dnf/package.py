# package.py
# Module defining the dnf.Package class.
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

""" Contains the dnf.Package class. """

from __future__ import absolute_import
from __future__ import unicode_literals

from dnf.i18n import _

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
        self._priv_chksum = None
        self._repo = None
        self._priv_size = None

    @property
    def _chksum(self):
        if self._priv_chksum:
            return self._priv_chksum
        if self._from_cmdline:
            chksum_type = dnf.yum.misc.get_default_chksum_type()
            chksum_val = dnf.yum.misc.checksum(chksum_type, self.location)
            return (hawkey.chksum_type(chksum_type),
                    binascii.unhexlify(chksum_val))
        return super(Package, self).chksum

    @_chksum.setter
    def _chksum(self, val):
        self._priv_chksum = val

    @property
    def debug_name(self):
        # :api
        """
        returns name of debuginfo package for given package
        e.g. kernel-PAE -> kernel-PAE-debuginfo
        """
        return "{}-debuginfo".format(self.name)

    @property
    def _from_cmdline(self):
        return self.reponame == hawkey.CMDLINE_REPO_NAME

    @property
    def _from_system(self):
        return self.reponame == hawkey.SYSTEM_REPO_NAME

    @property
    def _from_repo(self):
        pkgrepo = None
        if self._from_system:
            pkgrepo = self.base.history.repo(self)
        else:
            pkgrepo = {}
        if pkgrepo:
            return '@' + pkgrepo
        return self.reponame

    @property
    def _header(self):
        return dnf.rpm._header(self.localPkg())

    @property
    def _size(self):
        if self._priv_size:
            return self._priv_size
        return super(Package, self).size

    @_size.setter
    def _size(self, val):
        self._priv_size = val

    @property
    def source_debug_name(self):
        # :api
        """
        returns name of debuginfo package for source package of given package
        e.g. krb5-libs -> krb5-debuginfo
        """
        return "{}-debuginfo".format(self.source_name)

    @property
    def source_name(self):
        # :api
        """
        returns name of source package
        e.g. krb5-libs -> krb5
        """
        if self.sourcerpm is not None:
            # trim suffix first
            srcname = dnf.util.rtrim(self.sourcerpm, ".src.rpm")
            # sourcerpm should be in form of name-version-release now, so we
            # will strip the two rightmost parts separated by dash.
            # Using rtrim with version and release of self is not sufficient
            # because the package can have different version to the source
            # package.
            srcname = srcname.rsplit('-', 2)[0]
        else:
            srcname = None
        return srcname

    @property
    def _pkgid(self):
        if self.hdr_chksum is None:
            return None
        (_, chksum) = self.hdr_chksum
        return binascii.hexlify(chksum)

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
        if self._from_cmdline:
            return self.location
        loc = self.location
        if not self.repo._repo.isLocal():
            loc = os.path.basename(loc)
        elif self.baseurl and self.baseurl.startswith('file://'):
            return os.path.join(self.baseurl, loc.lstrip("/"))[7:]
        return os.path.join(self.repo.pkgdir, loc.lstrip("/"))

    def remote_location(self, schemes=('http', 'ftp', 'file', 'https')):
        # :api
        """
        The location from where the package can be downloaded from

        :param schemes: list of allowed protocols. Default is ('http', 'ftp', 'file', 'https')
        :return: location (string) or None
        """
        def schemes_filter(url_list):
            for url in url_list:
                if schemes:
                    s = dnf.pycomp.urlparse.urlparse(url)[0]
                    if s in schemes:
                        return os.path.join(url, self.location.lstrip('/'))
                else:
                    return os.path.join(url, self.location.lstrip('/'))
            return None

        if not self.location:
            return None

        mirrors = self.repo._repo.getMirrors()
        if mirrors:
            return schemes_filter(mirrors)
        elif self.repo.baseurl:
            return schemes_filter(self.repo.baseurl)

    def _is_local_pkg(self):
        if self.repoid == "@System":
            return True
        return self._from_cmdline or \
            (self.repo._repo.isLocal() and (not self.baseurl or self.baseurl.startswith('file://')))

    # yum compatibility method
    def returnIdSum(self):
        """ Return the chksum type and chksum string how the legacy yum expects
            it.
        """
        if self._chksum is None:
            return (None, None)
        (chksum_type, chksum) = self._chksum
        return (hawkey.chksum_name(chksum_type), binascii.hexlify(chksum).decode())

    # yum compatibility method
    def verifyLocalPkg(self):
        if self._from_system:
            raise ValueError("Can not verify an installed package.")
        if self._from_cmdline:
            return True # local package always verifies against itself
        (chksum_type, chksum) = self.returnIdSum()
        real_sum = dnf.yum.misc.checksum(chksum_type, self.localPkg(),
                                         datasize=self._size)
        if real_sum != chksum:
            logger.debug(_('%s: %s check failed: %s vs %s'),
                         self, chksum_type, real_sum, chksum)
            return False
        return True
