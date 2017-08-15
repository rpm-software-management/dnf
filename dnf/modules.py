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


from __future__ import print_function

import fnmatch
import gzip
import os
from collections import OrderedDict

import dnf
import hawkey
import modulemd
import smartcols

from dnf.conf import ModuleConf
from dnf.conf.read import ModuleReader, ModuleDefaultsReader
from dnf.exceptions import Error
from dnf.pycomp import ConfigParser
from dnf.subject import Subject
from dnf.util import logger, first_not_none, ensure_dir

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


class RepoModuleStream(OrderedDict):
    def __init__(self):
        super(RepoModuleStream, self).__init__()

        self.stream = None
        self.parent = None

    def add(self, repo_module_version):
        self[repo_module_version.version] = repo_module_version
        repo_module_version.parent = self

        self.stream = repo_module_version.stream

    def latest(self):
        return max(self.values())


class RepoModule(OrderedDict):
    def __init__(self):
        super(RepoModule, self).__init__()

        self._conf = None
        self.defaults = None
        self.name = None
        self.parent = None

    @property
    def conf(self):
        if self._conf is None:
            self._conf = ModuleConf(section=self.name, parser=ConfigParser())
            self._conf.name = self.name
            self._conf.enabled = False
            self._conf.locked = False
            self._conf.version = -1

        return self._conf

    @conf.setter
    def conf(self, value):
        self._conf = value

    def add(self, repo_module_version):
        module_stream = self.setdefault(repo_module_version.stream, RepoModuleStream())
        module_stream.add(repo_module_version)
        module_stream.parent = self

        self.name = repo_module_version.name
        repo_module_version.repo_module = self

    def enable(self, stream, assumeyes, assumeno):
        if stream not in self:
            raise Error(module_errors[NO_STREAM_ERR].format(stream, self.name))

        if self.conf.stream is not None and str(self.conf.stream) != str(stream) and not assumeyes:
            logger.info(module_errors[DIFFERENT_STREAM_INFO].format(self.name))
            if not assumeno and self.parent.base.output.userconfirm():
                self.enable(stream, True, assumeno)
            else:
                logger.info(module_errors[STREAM_NOT_ENABLED_ERR].format(stream))

        self.conf.stream = stream
        self.conf.enabled = True
        self.write_conf_to_file()

    def disable(self):
        self.conf.enabled = False
        self.write_conf_to_file()

    def lock(self, version):
        self.conf.locked = True
        self.conf.version = version
        self.write_conf_to_file()

    def unlock(self):
        self.conf.locked = False
        self.write_conf_to_file()

    def write_conf_to_file(self):
        output_file = os.path.join(self.parent.get_modules_dir(), "%s.module" % self.conf.name)
        ensure_dir(self.parent.get_modules_dir())

        with open(output_file, "w") as config_file:
            self.conf._write(config_file)


class RepoModuleDict(OrderedDict):

    def __init__(self, base):
        super(RepoModuleDict, self).__init__()

        self.base = base

    def add(self, repo_module_version):
        module = self.setdefault(repo_module_version.name, RepoModule())
        module.add(repo_module_version)
        module.parent = self

    def find_module_version(self, name, stream=None, version=None, context=None, arch=None):
        def use_enabled_stream(repo_module):
            if repo_module.conf and repo_module.conf.enabled:
                return repo_module.conf.stream
            return None

        def use_default_stream(repo_module):
            if repo_module.defaults:
                return repo_module.defaults.stream
            return None

        try:
            repo_module = self[name]

            stream = first_not_none([stream,
                                     use_enabled_stream(repo_module),
                                     use_default_stream(repo_module)])

            repo_module_stream = repo_module[stream]

            if repo_module.conf and \
                    repo_module.conf.locked and \
                    repo_module.conf.version is not None:
                if repo_module_stream.latest().version != repo_module.conf.version:
                    logger.info(module_errors[VERSION_LOCKED]
                                .format("{}:{}".format(repo_module.name, stream),
                                        repo_module.conf.version))

                repo_module_version = repo_module_stream[repo_module.conf.version]
            elif version:
                repo_module_version = repo_module_stream[version]
            else:
                # if version is not specified, pick the latest
                repo_module_version = repo_module_stream.latest()

            # TODO: arch
            # TODO: platform module

        except KeyError:
            return None
        return repo_module_version

    def enable(self, pkg_spec, assumeyes, assumeno=False):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if not module_version:
            raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

        self[module_version.name].enable(module_version.stream, assumeyes, assumeno)

    def disable(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module
            repo_module.disable()
            return

        # if lookup by pkg_spec failed, try disabling module by name
        try:
            self[pkg_spec].disable()
        except KeyError:
            raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def lock(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module

            if not repo_module.conf.enabled:
                raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(pkg_spec))

            repo_module.lock(module_version.version)
            return repo_module.conf.stream, repo_module.conf.version

        raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def unlock(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module

            if not repo_module.conf.enabled:
                raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(pkg_spec))

            repo_module.unlock()
            return

        raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def install(self, pkg_specs, autoenable=False):
        preferred_versions = self.get_preferred_versions(pkg_specs)

        for version in preferred_versions.values():
            for module_version, nsvcap, pkg_spec in version.moduleversion_nsvcap_pkgspec:
                module_version = self.decide_newer_version(module_version, pkg_spec,
                                                           version.preferred_version,
                                                           version.reason)

                if not module_version:
                    raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))
                elif module_version.repo_module.conf.locked:
                    continue

                if autoenable:
                    self.enable("{}:{}".format(module_version.name, module_version.stream), True)
                elif not self[nsvcap.name].conf.enabled:
                    raise Error(module_errors[NO_ACTIVE_STREAM_ERR].format(module_version.name))

                if nsvcap.profile:
                    profiles = [nsvcap.profile]
                else:
                    profiles = module_version.repo_module.defaults.profiles

                if module_version.version > module_version.repo_module.conf.version:
                    profiles.extend(module_version.repo_module.conf.profiles)
                    profiles = list(set(profiles))

                module_version.install(profiles)

    def decide_newer_version(self, module_version, pkg_spec, preferred_version, reason):
        if int(preferred_version) != module_version.version:
            logger.info(module_errors[INSTALLING_NEWER_VERSION].format(pkg_spec, reason))
            module_version = self.find_module_version(module_version.name, module_version.stream,
                                                      preferred_version)
        return module_version

    def get_preferred_versions(self, pkg_specs):
        preferred_versions = {}
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            key = "{}:{}".format(module_version.name, module_version.stream)
            versions = preferred_versions.setdefault(key, PreferredModuleVersion())
            versions.moduleversion_nsvcap_pkgspec.append([module_version, nsvcap, pkg_spec])
            if versions.preferred_version < module_version.version:
                versions.preferred_version = module_version.version
                versions.reason = pkg_spec

        return preferred_versions

    def upgrade(self, pkg_specs):
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            if not module_version:
                raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))
            elif module_version.repo_module.conf.locked:
                continue

            conf = self[nsvcap.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if nsvcap.profile:
                if nsvcap.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(pkg_spec))
                profiles = [nsvcap.profile]
            else:
                profiles = installed_profiles

            module_version.upgrade(profiles)

    def upgrade_all(self):
        modules = []
        for module_name, repo_module in self.items():
            if not repo_module.conf:
                continue
            if not repo_module.conf.enabled:
                continue
            modules.append(module_name)
        modules.sort()
        self.upgrade(modules)

    def remove(self, pkg_specs):
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            if not module_version:
                raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

            conf = self[nsvcap.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if nsvcap.profile:
                if nsvcap.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(pkg_spec))
                profiles = [nsvcap.profile]
            else:
                profiles = installed_profiles

            module_version.remove(profiles)

    def load_modules(self, repo):
        loader = ModuleMetadataLoader(repo)
        for module_metadata in loader.load():
            module_version = RepoModuleVersion(module_metadata, base=self.base, repo=repo)

            self.add(module_version)

    def read_all_modules(self):
        module_reader = ModuleReader(self.get_modules_dir())
        for conf in module_reader:
            repo_module = self.setdefault(conf.name, RepoModule())
            repo_module.conf = conf
            repo_module.name = conf.name
            repo_module.parent = self

    def read_all_module_defaults(self):
        defaults_reader = ModuleDefaultsReader(self.base.conf.moduledefaultsdir)
        for conf in defaults_reader:
            try:
                self[conf.name].defaults = conf
            except KeyError:
                logger.debug("No module named {}, skipping.".format(conf.name))

    def get_modules_dir(self):
        modules_dir = os.path.join(self.base.conf.installroot,
                                   self.base.conf.modulesdir.lstrip("/"))

        ensure_dir(modules_dir)
        return modules_dir

    def get_module_defaults_dir(self):
        return self.base.conf.moduledefaultsdir

    def get_info(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        lines = {"Name": module_version.name,
                 "Stream": module_version.stream,
                 "Version": module_version.version,
                 "Profiles": ", ".join(module_version.profiles),
                 "Summary": module_version.module_metadata.summary,
                 "Description": module_version.module_metadata.description,
                 "Artifacts": ", ".join(module_version.module_metadata.artifacts.rpms)}

        table = smartcols.Table()
        table.noheadings = True
        table.column_separator = " : "

        column_name = table.new_column("Name")
        column_value = table.new_column("Value")
        column_value.wrap = True

        for line_name, value in lines.items():
            line = table.new_line()
            if value:
                line[column_name] = line_name
                line[column_value] = str(value)

        return table

    def get_full_info(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)
        return module_version.module_metadata.dumps().rstrip("\n")

    def list_module_version_latest(self):
        versions = []

        for module in self.values():
            for stream in module.values():
                versions.append(stream.latest())

        return versions

    def list_module_version_all(self):
        versions = []

        for module in self.values():
            for stream in module.values():
                for version in stream.values():
                    versions.append(version)

        return versions

    def list_module_version_enabled(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is not None and conf.enabled and conf.stream == version.parent.stream:
                versions.append(version)

        return versions

    def list_module_version_disabled(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is None or not conf.enabled or version.stream != conf.stream:
                versions.append(version)

        return versions

    def list_module_version_installed(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is not None and conf.enabled and conf.version:
                versions.append(version)

        return versions

    def get_brief_description_latest(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_latest())

    def get_brief_description_all(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_all())

    def get_brief_description_enabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_enabled())

    def get_brief_description_disabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_disabled())

    def get_brief_description_installed(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_installed(),
                                                  True)

    def get_brief_description_by_name(self, module_n, repo_module_versions, only_installed=False):
        if module_n is None or not module_n:
            return self._get_brief_description(repo_module_versions, only_installed)
        else:
            filtered_versions_by_name = set()
            for name in module_n:
                for version in repo_module_versions:
                    if fnmatch.fnmatch(version.name, name):
                        filtered_versions_by_name.add(version)

            return self._get_brief_description(list(filtered_versions_by_name), only_installed)

    @staticmethod
    def _get_brief_description(repo_module_versions, only_installed=False):
        if only_installed:
            only_installed_versions = []
            for i in repo_module_versions:
                conf = i.parent.parent.conf
                if int(conf.version) == int(i.version) and conf.stream == i.stream:
                    only_installed_versions.append(i)
            repo_module_versions = only_installed_versions

        if not repo_module_versions:
            return module_errors[NOTHING_TO_SHOW]

        table = smartcols.Table()
        table.maxout = True

        column_name = table.new_column("Name")
        column_stream = table.new_column("Stream")
        column_version = table.new_column("Version")
        column_repo = table.new_column("Repo")
        column_installed = table.new_column("Installed")
        column_info = table.new_column("Info")

        for i in sorted(repo_module_versions, key=lambda data: data.name):
            line = table.new_line()
            conf = i.parent.parent.conf
            data = i.module_metadata
            line[column_name] = data.name
            line[column_stream] = data.stream
            line[column_version] = str(data.version)
            line[column_repo] = i.repo.id
            if conf and conf.version == i.version and conf.stream == i.stream:
                line[column_installed] = ", ".join(conf.profiles)
            line[column_info] = data.summary

        return table


class PreferredModuleVersion(object):

    def __init__(self):
        self.moduleversion_nsvcap_pkgspec = []
        self.preferred_version = -1
        self.reason = None


class ModuleMetadataLoader(object):
    def __init__(self, repo=None):
        self.repo = repo

    def load(self):
        if self.repo is None:
            raise Error(module_errors[LOAD_CACHE_ERR].format(self.repo))

        content_of_cachedir = os.listdir(self.repo._cachedir + "/repodata")
        modules_yaml_gz = list(filter(lambda repodata_file: 'modules' in repodata_file,
                                      content_of_cachedir))

        if not modules_yaml_gz:
            raise Error(module_errors[MISSING_YAML_ERR].format(self.repo._cachedir))
        modules_yaml_gz = "{}/repodata/{}".format(self.repo._cachedir, modules_yaml_gz[0])

        with gzip.open(modules_yaml_gz, "r") as extracted_modules_yaml_gz:
            modules_yaml = extracted_modules_yaml_gz.read()

        return modulemd.loads_all(modules_yaml)


class ModuleSubject(object):
    """
    Find matching modules for given user input (pkg_spec).
    """

    def __init__(self, pkg_spec):
        self.pkg_spec = pkg_spec

    def get_nsvcap_possibilities(self, forms=None):
        subj = hawkey.Subject(self.pkg_spec)
        kwargs = {}
        if forms:
            kwargs["form"] = forms
        return subj.nsvcap_possibilities(**kwargs)

    def find_module_version(self, repo_module_dict):
        """
        Find module that matches self.pkg_spec in given repo_module_dict.
        Return (RepoModuleVersion, NSVCAP).
        """

        result = (None, None)
        for nsvcap in self.get_nsvcap_possibilities():
            module_version = repo_module_dict.find_module_version(nsvcap.name, nsvcap.stream,
                                                                  nsvcap.version, nsvcap.context,
                                                                  nsvcap.arch)
            if module_version:
                result = (module_version, nsvcap)
                break
        return result


class ModulePersistor(object):

    def __init__(self):
        self.repo_modules = []

    def set_data(self, repo_module, **kwargs):
        self.repo_modules.append(repo_module)
        for name, value in kwargs.items():
            setattr(repo_module.conf, name, value)

    def save(self):
        for repo_module in self.repo_modules:
            repo_module.write_conf_to_file()

        return True

    def reset(self):
        # read configs from disk
        pass
