# supplies the 'module' command.
#
# Copyright (C) 2014-2017  Red Hat, Inc.
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

import dnf
from dnf.module import module_messages, NO_PROFILE_SPECIFIED


class LoadCacheException(dnf.exceptions.Error):
    def __init__(self, cache_dir):
        value = "Cannot load from cache dir: {}".format(cache_dir)
        super(LoadCacheException, self).__init__(value)


class MissingYamlException(dnf.exceptions.Error):
    def __init__(self, cache_dir):
        value = "Missing file *modules.yaml in metadata cache dir: {}".format(cache_dir)
        super(MissingYamlException, self).__init__(value)


class NoModuleException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "No such module: {}".format(module_spec)
        super(NoModuleException, self).__init__(value)


class NoStreamException(dnf.exceptions.Error):
    def __init__(self, stream):
        value = "No such stream: {}".format(stream)
        super(NoStreamException, self).__init__(value)


class EnabledStreamException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "No enabled stream for module: {}".format(module_spec)
        super(EnabledStreamException, self).__init__(value)


class DifferentStreamEnabledException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "Different stream enabled for module: {}".format(module_spec)
        super(DifferentStreamEnabledException, self).__init__(value)


class VersionLockedException(dnf.exceptions.Error):
    def __init__(self, module_spec, version):
        value = "'{}' is locked to version: {}".format(module_spec, version)
        super(VersionLockedException, self).__init__(value)


class CannotLockVersionException(dnf.exceptions.Error):
    def __init__(self, module_spec, version, reason=None):
        value = "Cannot lock '{}' to version: {}".format(module_spec, version)
        if reason:
            value = "{}. {}".format(value, reason)
        super(CannotLockVersionException, self).__init__(value)


class NoProfileException(dnf.exceptions.Error):
    def __init__(self, profile):
        value = "No such profile: {}".format(profile)
        super(NoProfileException, self).__init__(value)


class ProfileNotInstalledException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "Profile not installed: {}".format(module_spec)
        super(ProfileNotInstalledException, self).__init__(value)


class NoStreamSpecifiedException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "No stream specified for '{}', please specify stream".format(module_spec)
        super(NoStreamSpecifiedException, self).__init__(value)


class NoProfileSpecifiedException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = module_messages[NO_PROFILE_SPECIFIED].format(module_spec)
        super(NoProfileSpecifiedException, self).__init__(value)


class PossibleProfilesExceptions(dnf.exceptions.Error):
    def __init__(self, module_spec, profiles):
        value = "No such profile: {}. Possible profiles: {}".format(module_spec, profiles)
        super(PossibleProfilesExceptions, self).__init__(value)


class NoProfilesException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "No such profile: {}. No profiles available".format(module_spec)
        super(NoProfilesException, self).__init__(value)


class NoProfileToRemoveException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = "No profile to remove for '{}'".format(module_spec)
        super(NoProfileToRemoveException, self).__init__(value)
