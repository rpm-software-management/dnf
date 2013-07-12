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

from dnf.yum.i18n import to_unicode

class Error(Exception):
    """
    Base Yum Error. All other Errors thrown by yum should inherit from
    this.
    """
    def __init__(self, value=None):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return "%s" %(self.value,)

    def __unicode__(self):
        return '%s' % to_unicode(self.value)

class CompsError(Error):
    pass

class YumRPMTransError(Error):
    def __init__(self, msg, errors):
        Error.__init__(self, msg)
        self.errors = errors

class LockError(Error):
    pass

class ProcessLockError(LockError):
    def __init__(self, value, pid):
        super(ProcessLockError, self).__init__(value)
        self.pid = pid

    def __reduce__(self):
        """Pickling support."""
        return (ProcessLockError, (self.value, self.pid))

class ThreadLockError(LockError):
    pass

class RepoError(Error):
    pass

class ConfigError(Error):
    pass

class MetadataError(Error):
    pass

class MiscError(Error):
    pass

class ReinstallError(Error):
    pass

class ReinstallRemoveError(ReinstallError):
    pass

class ReinstallInstallError(ReinstallError):
    def __init__(self, value=None, failed_pkgs=[]):
        ReinstallError.__init__(self, value)
        self.failed_pkgs = failed_pkgs
