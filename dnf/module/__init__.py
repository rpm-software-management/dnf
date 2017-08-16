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

LOAD_CACHE_ERR = 1
MISSING_YAML_ERR = 2
NO_METADATA_ERR = 3
NO_MODULE_OR_STREAM_ERR = 4
NO_MODULE_ERR = 5
NO_PROFILE_ERR = 6
NO_STREAM_ERR = 7
NO_ACTIVE_STREAM_ERR = 8
STREAM_NOT_ENABLED_ERR = 9
DIFFERENT_STREAM_INFO = 10
INVALID_MODULE_ERR = 11
LOWER_VERSION_INFO = 12
NOTHING_TO_SHOW = 13
PARSING_ERR = 14
PROFILE_NOT_INSTALLED = 15
VERSION_LOCKED = 16
INSTALLING_NEWER_VERSION = 17

module_errors = {
    LOAD_CACHE_ERR: "Cannot load from cache dir: {}",
    MISSING_YAML_ERR: "Missing file *modules.yaml in metadata cache dir: {}",
    NO_METADATA_ERR: "No available metadata for module: {}",
    NO_MODULE_OR_STREAM_ERR: "No such module: {} or active stream (enable a stream first)",
    NO_MODULE_ERR: "No such module: {}",
    NO_PROFILE_ERR: "No such profile: {}. Possible profiles: {}",
    NO_STREAM_ERR: "No such stream {} in {}",
    NO_ACTIVE_STREAM_ERR: "No active stream for module: {}",
    STREAM_NOT_ENABLED_ERR: "Stream not enabled. Skipping {}",
    DIFFERENT_STREAM_INFO: "Enabling different stream for {}",
    INVALID_MODULE_ERR: "Not a valid module: {}",
    LOWER_VERSION_INFO: "Using lower version due to missing profile in latest version",
    NOTHING_TO_SHOW: "Nothing to show",
    PARSING_ERR: "Probable parsing problem of {}, try specifying MODULE-STREAM-VERSION",
    PROFILE_NOT_INSTALLED: "Profile not installed: {}",
    VERSION_LOCKED: "'{}' is locked to version: {}",
    INSTALLING_NEWER_VERSION: "Installing newer version of '{}' than specified. Reason: {}",
}
