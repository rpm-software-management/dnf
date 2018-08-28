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

import hawkey
import rpm

import dnf
from dnf.module.exceptions import NoProfileException, PossibleProfilesExceptions, \
    NoProfilesException
from dnf.subject import Subject


class RepoModuleVersion(object):
    def __init__(self, module_metadata, base, repo):
        self.module_metadata = module_metadata
        self.repo = repo
        self.base = base
        self.parent = None
        self.repo_module = None

    def __lt__(self, other):
        return rpm.labelCompare((self.name, self.stream, str(self.version)),
                                (other.name, other.stream, str(other.version))) == -1

    def __repr__(self):
        return self.full_version

    def artifacts(self):
        return self.module_metadata.peek_rpm_artifacts().dup()

    def requires(self):
        requires = {}
        for dependencies in self.module_metadata.peek_dependencies():
            for name, streams in dependencies.peek_requires().items():
                requires[name] = streams.dup()
        return requires

    def summary(self):
        return self.module_metadata.peek_summary()

    def description(self):
        return self.module_metadata.peek_description()

    def rpms(self, profile):
        module_profiles = self.module_metadata.peek_profiles()
        if profile not in module_profiles and profile in ['default']:
            result = []
        else:
            result = module_profiles[profile].peek_rpms().dup()
        return result

    def profile_nevra_objects(self, profile):
        result = []
        rpms = set(self.rpms(profile))
        for nevra in self.artifacts():
            subj = Subject(nevra)
            nevra_obj = list(subj.get_nevra_possibilities(hawkey.FORM_NEVRA))[0]
            if nevra_obj.name not in rpms:
                continue
            result.append(nevra_obj)
        return result

    @property
    def version(self):
        return self.module_metadata.peek_version()

    @property
    def full_version(self):
        return "%s:%s:%s" % (
            self.module_metadata.peek_name(), self.module_metadata.peek_stream(),
            self.module_metadata.peek_version())

    @property
    def stream(self):
        return self.module_metadata.peek_stream()

    @property
    def full_stream(self):
        return "%s-%s" % (self.module_metadata.peek_name(), self.module_metadata.peek_stream())

    @property
    def name(self):
        return self.module_metadata.peek_name()

    @property
    def profiles(self):
        return sorted(self.module_metadata.peek_profiles())
