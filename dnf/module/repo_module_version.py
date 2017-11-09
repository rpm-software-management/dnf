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
        # for finding latest
        assert self.full_stream == other.full_stream
        if self.repo_module.conf.locked:
            return self.version < self.repo_module.conf.version
        return self.module_metadata.version < other.module_metadata.version

    def __repr__(self):
        return self.full_version

    def report_profile_error(self, profile, default_profiles_used=False):
        if default_profiles_used:
            raise NoProfileException("{}/{}".format(self.full_version, profile))
        elif self.profiles:
            raise PossibleProfilesExceptions("{}/{}".format(self.full_version, profile),
                                             self.profiles)
        else:
            raise NoProfilesException("{}/{}".format(self.full_version, profile))

    def install(self, profiles, default_profiles):
        result = self._install_profiles(profiles, False)
        result |= self._install_profiles(default_profiles, True)

        profiles.extend(self.repo_module.conf.profiles)
        profiles.extend(default_profiles)
        self.base._module_persistor.set_data(self.repo_module, stream=self.stream,
                                             version=self.version, profiles=sorted(set(profiles)))

        return result

    def _install_profiles(self, profiles, defaults_used):
        installed = self.base.sack.query().installed().run()
        installed_nevras = [str(pkg) for pkg in installed]

        result = False
        for profile in profiles:
            if profile not in self.profiles:
                self.report_profile_error(profile, defaults_used)

            for nevra_object in self.profile_nevra_objects(profile):
                nevr = self.nevra_object_to_nevr_str(nevra_object)
                nevra = "{}.{}".format(nevr, nevra_object.arch)

                if nevra not in installed_nevras:
                    self.base.install(nevr, reponame=self.repo.id, forms=hawkey.FORM_NEVR)
                    self.base._goal.group_members.add(nevra_object.name)
                    self.base._goal.module_members.add(nevra)
                    result = True

        return result

    def upgrade(self, profiles):
        installed = self.base.sack.query().installed().run()
        installed_nevras = [str(pkg) for pkg in installed]
        query_to_return = None

        for profile in profiles:
            if profile not in self.profiles:
                raise NoProfileException("{}/{}".format(self.full_version, profile))

            for nevra_object in self.profile_nevra_objects(profile):
                nevr = self.nevra_object_to_nevr_str(nevra_object)
                nevra = "{}.{}".format(nevr, nevra_object.arch)

                if nevra not in installed_nevras:
                    self.base.install(nevr, reponame=self.repo.id, forms=hawkey.FORM_NEVR)
                else:
                    # TODO: verify that filter(nevra) really works correctly
                    # (possibly breaks multilib)
                    query = self.base.sack.query().filter(nevra=nevra)
                    if query_to_return is None:
                        query_to_return = query
                    else:
                        query_to_return = query_to_return.union(query)

        self.base._module_persistor.set_data(self.repo_module, stream=self.stream,
                                             version=self.version)

        return query_to_return

    def remove(self, profiles):
        for profile in profiles:
            if profile not in self.profiles:
                raise NoProfileException("{}/{}".format(self.full_version, profile))

            for nevra_object in self.profile_nevra_objects(profile):
                nevr = self.nevra_object_to_nevr_str(nevra_object)
                remove_query = dnf.subject.Subject(nevr) \
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

    @staticmethod
    def nevra_object_to_nevr_str(nevra_object):
        return "{}-{}".format(nevra_object.name, nevra_object.evr())

    def rpms(self, profile):
        return self.module_metadata.profiles[profile].rpms

    def profile_nevra_objects(self, profile):
        result = []
        rpms = set(self.rpms(profile))
        for nevra in self.nevra():
            subj = Subject(nevra)
            nevra_obj = list(subj.get_nevra_possibilities(hawkey.FORM_NEVRA))[0]
            if nevra_obj.name not in rpms:
                continue
            result.append(nevra_obj)
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
