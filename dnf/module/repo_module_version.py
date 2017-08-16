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

import dnf
import hawkey

from dnf.exceptions import Error
from dnf.module import module_errors, NO_PROFILE_ERR
from dnf.subject import Subject


class RepoModuleVersion(object):
    def __init__(self, module_metadata, base, repo):
        self.module_metadata = module_metadata
        self.repo = repo
        self.base = base
        self.parent = None
        self.repo_module = None

    def __lt__(self, other):
        # for finding latest
        assert self.full_stream == other.full_stream
        return self.module_metadata.version < other.module_metadata.version

    def __repr__(self):
        return self.full_version

    def install(self, profiles):
        for profile in profiles:
            if profile not in self.profiles:
                raise Error(module_errors[NO_PROFILE_ERR].format(profile, self.profiles))

            for single_nevra in self.profile_nevra(profile):
                subject = Subject(single_nevra)
                nevra_obj = list(subject.get_nevra_possibilities(hawkey.FORM_NEVR))[0]

                self.base.install(single_nevra, reponame=self.repo.id, forms=hawkey.FORM_NEVR)
                self.base._goal.group_members.add(nevra_obj.name)

        profiles.extend(self.repo_module.conf.profiles)
        self.base._module_persistor.set_data(self.repo_module, stream=self.stream,
                                             version=self.version, profiles=sorted(set(profiles)))

    def upgrade(self, profiles):
        for profile in profiles:
            if profile not in self.profiles:
                raise Error(module_errors[NO_PROFILE_ERR].format(profile, self.profiles))

            for single_nevra in self.profile_nevra(profile):
                self.base.upgrade(single_nevra, reponame=self.repo.id)

        self.base._module_persistor.set_data(self.repo_module, stream=self.stream,
                                             version=self.version)

    def remove(self, profiles):
        for profile in profiles:
            if profile not in self.profiles:
                raise Error(module_errors[NO_PROFILE_ERR].format(profile, self.profiles))

            for single_nevra in self.profile_nevra(profile):
                remove_query = dnf.subject.Subject(single_nevra) \
                    .get_best_query(self.base.sack, forms=hawkey.FORM_NEVR)

                if self.base._yumdb.get_package(remove_query[0]).reason == 'user':
                    continue

                self.base._remove_if_unneeded(remove_query)

        conf = self.repo_module.conf
        version = conf.version
        profiles = [x for x in conf.profiles if x not in profiles]

        if len(conf.profiles) == 0:
            conf.version = -1

        self.base._module_persistor.set_data(self.repo_module, stream=self.stream, version=version,
                                             profiles=sorted(set(profiles)))

    def nevra(self):
        result = self.module_metadata.artifacts.rpms
        # HACK: remove epoch to make filter(nevra=...) work
        result = [i.replace("0:", "") for i in result]
        return result

    def rpms(self, profile):
        return self.module_metadata.profiles[profile].rpms

    def profile_nevra(self, profile):
        result = set()
        rpms = set(self.rpms(profile))
        for nevra in self.nevra():
            subj = Subject(nevra)
            nevra_obj = list(subj.get_nevra_possibilities(hawkey.FORM_NEVRA))[0]
            if nevra_obj.name not in rpms:
                continue
            result.add("{}-{}".format(nevra_obj.name, nevra_obj.evr()))
        return result

    @property
    def version(self):
        return self.module_metadata.version

    @property
    def full_version(self):
        return "%s:%s:%s" % (
            self.module_metadata.name, self.module_metadata.stream, self.module_metadata.version)

    @property
    def stream(self):
        return self.module_metadata.stream

    @property
    def full_stream(self):
        return "%s-%s" % (self.module_metadata.name, self.module_metadata.stream)

    @property
    def name(self):
        return self.module_metadata.name

    @property
    def profiles(self):
        return sorted(self.module_metadata.profiles)
