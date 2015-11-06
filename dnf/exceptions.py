# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# Copyright 2004 Duke University

"""
Core DNF Errors.
"""

from __future__ import unicode_literals
from dnf.i18n import ucd


class DeprecationWarning(DeprecationWarning):
    # :api
    # bla
    pass


class Error(Exception):
    """Base Error. All other Errors thrown by DNF should inherit from this.

    :api

    """
    def __init__(self, value=None):
        super(Error, self).__init__()
        self.value = None if value is None else ucd(value)

    def __str__(self):
        return "%s" %(self.value,)

    def __unicode__(self):
        return '%s' % self.value


class CompsError(Error):
    pass


class ConfigError(Error):
    pass


class DepsolveError(Error):
    # :api
    pass


class DownloadError(Error):
    # :api
    def __init__(self, errmap):
        super(DownloadError, self).__init__()
        self.errmap = errmap

    @staticmethod
    def errmap2str(errmap):
        errstrings = []
        for key in errmap:
            for error in errmap[key]:
                msg = '%s: %s' % (key, error) if key else '%s' % error
                errstrings.append(msg)
        return '\n'.join(errstrings)

    def __str__(self):
        return self.errmap2str(self.errmap)

    def __unicode__(self):
        return ucd(self.__str__())


class LockError(Error):
    pass


class MarkingError(Error):
    # :api

    def __init__(self, value=None, pkg_spec=None):
        """Initialize the marking error instance."""
        super(MarkingError, self).__init__(value)
        self.pkg_spec = None if pkg_spec is None else ucd(pkg_spec)

    def __unicode__(self):
        string = super(MarkingError, self).__unicode__()
        if self.pkg_spec:
            string += ': ' + self.pkg_spec
        return string



class MetadataError(Error):
    pass


class MiscError(Error):
    pass


class PackagesNotAvailableError(MarkingError):
    def __init__(self, value=None, pkg_spec=None, packages=None):
        super(PackagesNotAvailableError, self).__init__(value, pkg_spec)
        self.packages = packages or []


class PackageNotFoundError(MarkingError):
    pass


class PackagesNotInstalledError(MarkingError):
    def __init__(self, value=None, pkg_spec=None, packages=None):
        super(PackagesNotInstalledError, self).__init__(value, pkg_spec)
        self.packages = packages or []


class ProcessLockError(LockError):
    def __init__(self, value, pid):
        super(ProcessLockError, self).__init__(value)
        self.pid = pid

    def __reduce__(self):
        """Pickling support."""
        return (ProcessLockError, (self.value, self.pid))


class RepoError(Error):
    # :api
    pass


class ThreadLockError(LockError):
    pass


class TransactionCheckError(Error):
    pass
