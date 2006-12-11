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



import exceptions


class YumBaseError(exceptions.Exception):
    def __init__(self, value=None):
        exceptions.Exception.__init__(self)    
        self.value = value
    def __str__(self):
        return "%s" %(self.value,)

class LockError(YumBaseError):
    def __init__(self, errno, msg):
        YumBaseError.__init__(self)
        self.errno = errno
        self.msg = msg
        
class DepError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class RepoError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class DuplicateRepoError(RepoError):
    def __init__(self, value=None):
        RepoError.__init__(self)
        self.value = value

class ConfigError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value
    
class MiscError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class GroupsError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class InstallError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class UpdateError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class RemoveError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class RepoMDError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value

class PackageSackError(YumBaseError):
    def __init__(self, value=None):
        YumBaseError.__init__(self)
        self.value = value
