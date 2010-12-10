#!/usr/bin/python -tt
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2004 Duke University

"""
Exceptions and Errors thrown by yum.
"""

from i18n import to_unicode

class YumBaseError(Exception):
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

class YumGPGCheckError(YumBaseError):
    pass

class YumDownloadError(YumBaseError):
    pass

class YumTestTransactionError(YumBaseError):
    pass

class YumRPMCheckError(YumBaseError):
    pass
        
class YumRPMTransError(YumBaseError):
    """ This class means rpm's .ts.run() returned known errors. We are compat.
        with YumBaseError in that we print nicely, and compat. with traditional
        usage of this error from runTransaction(). """
    def __init__(self, msg, errors):
        self.msg    = msg
        self.errors = errors
        # old YumBaseError raises from runTransaction used to raise just this
        self.value  = self.errors

    def __str__(self):
        return "%s" %(self.msg,)

    def __unicode__(self):
        return '%s' % to_unicode(self.msg)


class LockError(YumBaseError):
    def __init__(self, errno, msg, pid=0):
        YumBaseError.__init__(self, msg)
        self.errno = errno
        self.msg = msg
        self.pid = pid
        
class DepError(YumBaseError):
    pass
    
class RepoError(YumBaseError):
    pass

class DuplicateRepoError(RepoError):
    pass

class NoMoreMirrorsRepoError(RepoError):
    pass
    
class ConfigError(YumBaseError):
    pass
    
class MiscError(YumBaseError):
    pass

class GroupsError(YumBaseError):
    pass

class InstallError(YumBaseError):
    pass

class UpdateError(YumBaseError):
    pass
    
class RemoveError(YumBaseError):
    pass

class ReinstallError(YumBaseError):
    pass

class ReinstallRemoveError(ReinstallError):
    pass

class ReinstallInstallError(ReinstallError):
    def __init__(self, value=None, failed_pkgs=[]):
        ReinstallError.__init__(self, value)
        self.failed_pkgs = failed_pkgs

class DowngradeError(YumBaseError):
    pass

class RepoMDError(YumBaseError):
    pass

class PackageSackError(YumBaseError):
    pass

class RpmDBError(YumBaseError):
    pass

class CompsException(YumBaseError):
    pass

class MediaError(YumBaseError):
    pass
    
class PkgTagsError(YumBaseError):
    pass
    
class YumDeprecationWarning(DeprecationWarning):
    """
    Used to mark a method as deprecated.
    """
    def __init__(self, value=None):
        DeprecationWarning.__init__(self, value)

class YumFutureDeprecationWarning(YumDeprecationWarning):
    """
    Used to mark a method as deprecated. Unlike YumDeprecationWarning,
    YumFutureDeprecationWarnings will not be shown on the console.
    """
    def __init__(self, value=None):
        YumDeprecationWarning.__init__(self, value)
