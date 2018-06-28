# Copyright (C) 2017  Red Hat, Inc.
#
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

from dnf.i18n import _

DIFFERENT_STREAM_INFO = 1
NOTHING_TO_SHOW = 2
INSTALLING_NEWER_VERSION = 4
ENABLED_MODULES = 5
NO_PROFILE_SPECIFIED = 6

module_messages = {
    DIFFERENT_STREAM_INFO: _("Enabling different stream for '{}'."),
    NOTHING_TO_SHOW: _("Nothing to show."),
    INSTALLING_NEWER_VERSION: _("Installing newer version of '{}' than specified. Reason: {}"),
    ENABLED_MODULES: _("Enabled modules: {}."),
    NO_PROFILE_SPECIFIED: _("No profile specified for '{}', please specify profile."),
}
