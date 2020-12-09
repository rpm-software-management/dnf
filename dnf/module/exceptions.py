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
from dnf.i18n import _


class NoModuleException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("No such module: {}").format(module_spec)
        super(NoModuleException, self).__init__(value)


class NoStreamException(dnf.exceptions.Error):
    def __init__(self, stream):
        value = _("No such stream: {}").format(stream)
        super(NoStreamException, self).__init__(value)


class EnabledStreamException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("No enabled stream for module: {}").format(module_spec)
        super(EnabledStreamException, self).__init__(value)


class EnableMultipleStreamsException(dnf.exceptions.Error):
    def __init__(self, module_spec, value=None):
        if value is None:
            value = _("Cannot enable more streams from module '{}' at the same time").format(module_spec)
        super(EnableMultipleStreamsException, self).__init__(value)


class DifferentStreamEnabledException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("Different stream enabled for module: {}").format(module_spec)
        super(DifferentStreamEnabledException, self).__init__(value)


class NoProfileException(dnf.exceptions.Error):
    def __init__(self, profile):
        value = _("No such profile: {}").format(profile)
        super(NoProfileException, self).__init__(value)


class ProfileNotInstalledException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("Specified profile not installed for {}").format(module_spec)
        super(ProfileNotInstalledException, self).__init__(value)


class NoStreamSpecifiedException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("No stream specified for '{}', please specify stream").format(module_spec)
        super(NoStreamSpecifiedException, self).__init__(value)


class NoProfileSpecifiedException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = module_messages[NO_PROFILE_SPECIFIED].format(module_spec)
        super(NoProfileSpecifiedException, self).__init__(value)


class NoProfilesException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("No such profile: {}. No profiles available").format(module_spec)
        super(NoProfilesException, self).__init__(value)


class NoProfileToRemoveException(dnf.exceptions.Error):
    def __init__(self, module_spec):
        value = _("No profile to remove for '{}'").format(module_spec)
        super(NoProfileToRemoveException, self).__init__(value)
