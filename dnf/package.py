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
import dnf.exceptions
import dnf.rpm
import dnf.yum.misc
import hawkey
import libdnf.error
import libdnf.utils
import logging
import os
import rpm

logger = logging.getLogger("dnf")


class Package(hawkey.Package):
    """ Represents a package. #:api """

    DEBUGINFO_SUFFIX = "-debuginfo"  # :api
    DEBUGSOURCE_SUFFIX = "-debugsource"  # :api

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
            try:
                chksum_val = libdnf.utils.checksum_value(chksum_type, self.location)
            except libdnf.error.Error as e:
                raise dnf.exceptions.MiscError(str(e))
            return (hawkey.chksum_type(chksum_type),
                    binascii.unhexlify(chksum_val))
        return super(Package, self).chksum

    @_chksum.setter
    def _chksum(self, val):
        self._priv_chksum = val

    @property
    def _from_cmdline(self):
        return self.reponame == hawkey.CMDLINE_REPO_NAME

    @property
    def _from_system(self):
        return self.reponame == hawkey.SYSTEM_REPO_NAME

    @property
    def _from_repo(self):
        """
        For installed packages returns id of repository from which the package was installed
        prefixed with '@' (if such information is available in the history database). Otherwise
        returns id of repository the package belongs to (@System for installed packages of unknown
        origin)
        """
        pkgrepo = None
        if self._from_system:
            pkgrepo = self.base.history.repo(self)
        if pkgrepo:
            return '@' + pkgrepo
        return self.reponame

    @property
    def from_repo(self):
        # :api
        if self._from_system:
            return self.base.history.repo(self)
        return ""

    @property
    def _header(self):
        """
        Returns the header of a locally present rpm package file. As opposed to
        self.get_header(), which retrieves the header of an installed package
        from rpmdb.
        """
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
    def _pkgid(self):
        if self.hdr_chksum is None:
            return None
        (_, chksum) = self.hdr_chksum
        return binascii.hexlify(chksum)

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
    def debug_name(self):
        # :api
        """
        Returns name of the debuginfo package for this package.
        If this package is a debuginfo package, returns its name.
        If this package is a debugsource package, returns the debuginfo package
        for the base package.
        e.g. kernel-PAE -> kernel-PAE-debuginfo
        """
        if self.name.endswith(self.DEBUGINFO_SUFFIX):
            return self.name

        name = self.name
        if self.name.endswith(self.DEBUGSOURCE_SUFFIX):
            name = name[:-len(self.DEBUGSOURCE_SUFFIX)]

        return name + self.DEBUGINFO_SUFFIX

    @property
    def debugsource_name(self):
        # :api
        """
        Returns name of the debugsource package for this package.
        e.g. krb5-libs -> krb5-debugsource
        """
        # assuming self.source_name is None only for a source package
        src_name = self.source_name if self.source_name is not None else self.name
        return src_name + self.DEBUGSOURCE_SUFFIX

    def get_header(self):
        """
        Returns the rpm header of the package if it is installed. If not
        installed, returns None. The header is not cached, it is retrieved from
        rpmdb on every call. In case of a failure (e.g. when the rpmdb changes
        between loading the data and calling this method), raises an instance
        of PackageNotFoundError.
        """
        if not self._from_system:
            return None

        try:
            # RPMDBI_PACKAGES stands for the header of the package
            return next(self.base._ts.dbMatch(rpm.RPMDBI_PACKAGES, self.rpmdbid))
        except StopIteration:
            raise dnf.exceptions.PackageNotFoundError("Package not found when attempting to retrieve header", str(self))

    @property
    def source_debug_name(self):
        # :api
        """
        returns name of debuginfo package for source package of given package
        e.g. krb5-libs -> krb5-debuginfo
        """
        # assuming self.source_name is None only for a source package
        src_name = self.source_name if self.source_name is not None else self.name
        return src_name + self.DEBUGINFO_SUFFIX

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

    @property
    def reason(self):
        if self.repoid != hawkey.SYSTEM_REPO_NAME:
            return None
        return self.base.history.rpm.get_reason_name(self)

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
        if self.repo._repo.isLocal() and self.baseurl and self.baseurl.startswith('file://'):
            return os.path.join(self.get_local_baseurl(), loc.lstrip("/"))
        if not self._is_local_pkg():
            loc = os.path.basename(loc)
        return os.path.join(self.pkgdir, loc.lstrip("/"))

    def remote_location(self, schemes=('http', 'ftp', 'file', 'https')):
        # :api
        """
        The location from where the package can be downloaded from. Returns None for installed and
        commandline packages.

        :param schemes: list of allowed protocols. Default is ('http', 'ftp', 'file', 'https')
        :return: location (string) or None
        """
        if self._from_system or self._from_cmdline:
            return None
        return self.repo.remote_location(self.location, schemes)

    def _is_local_pkg(self):
        if self._from_system:
            return True
        if '://' in self.location and not self.location.startswith('file://'):
            # the package has a remote URL as its location
            return False
        return self._from_cmdline or \
            (self.repo._repo.isLocal() and (not self.baseurl or self.baseurl.startswith('file://')))

    @property
    def pkgdir(self):
        if (self.repo._repo.isLocal() and not self._is_local_pkg()):
            return self.repo.cache_pkgdir()
        else:
            return self.repo.pkgdir

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
        try:
            return libdnf.utils.checksum_check(chksum_type, self.localPkg(), chksum)
        except libdnf.error.Error as e:
            raise dnf.exceptions.MiscError(str(e))
