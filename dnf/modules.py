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

import errno
import fnmatch
import gzip
import os
from collections import OrderedDict

import hawkey
import modulemd
import smartcols

from dnf.callback import TransactionProgress, TRANS_POST, PKG_VERIFY
from dnf.conf import ModuleConf
from dnf.conf.read import ModuleReader
from dnf.exceptions import Error
from dnf.i18n import _
from dnf.pycomp import ConfigParser
from dnf.util import logger


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
HORRIBLE_HACK_WARN = 15


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
    HORRIBLE_HACK_WARN: "DNF has made a horrible hack by guessing "
                        "default stream instead of using (non-existing) "
                        "system-profile"
}

default_profile = "default"
name_profile_delimiter = "/"
name_stream_version_delimiter = "-"


class RepoModuleVersion(object):
    def __init__(self, module_metadata, base, repo):
        self.module_metadata = module_metadata
        self.repo = repo
        self.base = base
        self.parent = None

    def __lt__(self, other):
        # for finding latest
        assert self.full_stream == other.full_stream
        return self.module_metadata.version < other.module_metadata.version

    def install(self, profile):
        if profile not in self.profiles:
            raise Error(module_errors[NO_PROFILE_ERR].format(profile, self.profiles))

        self.parent.parent.installed_repo_module_version = self
        self.parent.parent.installed_profiles.append(profile)

        for single_nevra in self.profile_nevra(profile):
            self.base.install(single_nevra, reponame=self.repo.id, forms=hawkey.FORM_NEVR)

    def upgrade(self, profiles):
        self.parent.parent.installed_repo_module_version = self
        for profile in profiles:
            if profile not in self.profiles:
                raise Error(module_errors[NO_PROFILE_ERR].format(profile, self.profiles))

            for single_nevra in self.profile_nevra(profile):
                self.base.upgrade(single_nevra, reponame=self.repo.id)

    def nevra(self):
        return self.module_metadata.artifacts.rpms

    def rpms(self, profile):
        return self.module_metadata.profiles[profile].rpms

    def profile_nevra(self, profile):
        profile_rpms = self.rpms(profile)
        profile_nevra = set()
        for single_nevra in self.nevra():
            name = self.get_name_from_nevra(single_nevra)
            if name in profile_rpms:
                nevr, arch = self.split_to_nevr_arch(single_nevra)
                profile_nevra.add(nevr)
        return profile_nevra

    def get_name_from_nevra(self, nevra):
        nevr, arch = self.split_to_nevr_arch(nevra)
        name, ev, release = nevr.rsplit(name_stream_version_delimiter, 2)
        return name

    @staticmethod
    def split_to_nevr_arch(nevra):
        return nevra.rsplit('.', 1)

    @property
    def version(self):
        return self.module_metadata.version

    @property
    def full_version(self):
        return "%s-%s-%s" % (
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

    def install(self, version, profile):
        self[int(version or self.latest().version)].install(profile)

    def upgrade(self, installed_version, profiles):
        for repo_module_version in sorted(self.values(), reverse=True):
            try:
                if not installed_version or repo_module_version.version == installed_version:
                    repo_module_version.install(profiles)
                else:
                    repo_module_version.upgrade(profiles)
                break
            except Error as e:
                logger.warning(e)
                logger.warning(module_errors[LOWER_VERSION_INFO])


class RepoModule(OrderedDict):
    def __init__(self):
        super(RepoModule, self).__init__()

        self.conf = None
        self.name = None
        self.parent = None
        self.installed_profiles = []
        self.installed_version = None

    def add(self, repo_module_version):
        module_stream = self.setdefault(repo_module_version.stream, RepoModuleStream())
        module_stream.add(repo_module_version)
        module_stream.parent = self

        self.name = repo_module_version.name

    def enable(self, stream, assumeyes, assumeno):
        if stream not in self:
            raise Error(module_errors[NO_STREAM_ERR].format(stream, self.name))

        if self.conf is None:
            self.conf = ModuleConf(section=self.name, parser=ConfigParser())
            self.conf.name = self.name

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
        if self.conf is None:
            self.conf = ModuleConf(section=self.name, parser=ConfigParser())
            self.conf.name = self.name

        self.conf.enabled = False
        self.write_conf_to_file()

    def install(self, stream, version, profile):
        self.parent.transaction_callback.repo_modules.append(self)

        try:
            self[stream].install(version, profile)
        except KeyError:
            raise Error(module_errors[NO_STREAM_ERR].format(stream, self.name))

    def upgrade(self):
        self.parent.transaction_callback.repo_modules.append(self)
        try:
            self[self.conf.stream].upgrade(self.conf.version, self.conf.profiles)
        except KeyError:
            raise Error(module_errors[NO_STREAM_ERR].format(self.conf.stream, self.name))

    def write_conf_to_file(self):
        output_file = os.path.join(self.parent.get_modules_dir(), "%s.module" % self.conf.name)

        with open(output_file, "w") as config_file:
            self.conf._write(config_file)


class RepoModuleDict(OrderedDict):
    def __init__(self, base):
        super(RepoModuleDict, self).__init__()

        self.base = base
        self.transaction_callback = ModuleTransactionProgress()

    def add(self, repo_module_version):
        module = self.setdefault(repo_module_version.name, RepoModule())
        module.add(repo_module_version)
        module.parent = self

    def enable(self, module_ns, assumeyes, assumeno=False):
        name, stream, version, _ = self.parse_module_nsvp(module_ns)
        try:
            self[name].enable(stream, assumeyes, assumeno)
        except KeyError:
            logger.error(module_errors[NO_MODULE_ERR].format(name))

    def disable(self, module_name):
        try:
            self[module_name].disable()
        except KeyError:
            logger.warning(_("No such module: {}, try specifying only module name"
                             .format(module_name)))

    def install(self, specs, autoenable=False):
        for module in specs:
            name, stream, version, profile = self.parse_module_nsvp(module)
            if name not in self:
                logger.error(module_errors[NO_MODULE_ERR].format(name))
                continue

            if autoenable:
                self.enable(module, True)

            self[name].install(stream, version, profile)

    def upgrade(self, specs):
        for name in specs:
            if name not in self:
                logger.error(module_errors[NO_MODULE_ERR].format(name))
                continue

            any_profile_installed = self[name].conf and self[name].conf.profiles
            if not any_profile_installed:
                continue

            self[name].upgrade()

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

    def get_modules_dir(self):
        modules_dir = os.path.join(self.base.conf.installroot, self.base.conf.modulesdir.lstrip("/"))

        if not os.path.exists(modules_dir):
            self.create_dir(modules_dir)

        return modules_dir

    @staticmethod
    def create_dir(output_file):
        oumask = os.umask(0o22)
        try:
            os.makedirs(output_file)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        finally:
            os.umask(oumask)

    def get_modules_by_name_stream_version(self, name, stream=None, version=None):
        filtered_names = fnmatch.filter(self, name)
        if not filtered_names:
            raise Error(module_errors[NO_MODULE_ERR].format(name))

        filtered_streams = []
        module_metadata = []
        if stream is not None:
            for filtered_name in filtered_names:
                filtered_streams.extend(fnmatch.filter(self[filtered_name], stream))

        if not filtered_streams:
            for filtered_name in filtered_names:
                filtered_streams.extend(list(self[filtered_name].keys()))

        for filtered_name in filtered_names:
            for filtered_stream in filtered_streams:
                for module_version in self[filtered_name][filtered_stream].values():
                    if version is None:
                        module_metadata.append(module_version.module_metadata)
                    elif fnmatch.fnmatch(str(module_version.version), version):
                        module_metadata.append(module_version.module_metadata)

        if not module_metadata:
            raise Error(module_errors[NO_METADATA_ERR].format(name))

        return module_metadata

    def get_full_description(self, module_nsvp):
        name, stream, version = self.parse_module_nsv(module_nsvp)
        module_metadata = self.get_modules_by_name_stream_version(name, stream, version)
        module_metadata = sorted(module_metadata, key=lambda data: data.version)

        ret = ""
        for data in module_metadata:
            ret += data.dumps() + "\n"
        return ret[:-1]

    def get_brief_description_all(self, module_n):
        return self.get_brief_description_by_name(module_n, [stream for module in self.values()
                                                             for stream in module.values()])

    def get_brief_description_enabled(self, module_n):
        return self.get_brief_description_by_name(module_n,
                                                  [stream for module in self.values()
                                                   for stream in module.values()
                                                   if module.conf is not None and
                                                   module.conf.enabled and
                                                   module.conf.stream == stream.stream])

    def get_brief_description_disabled(self, module_n):
        return self.get_brief_description_by_name(module_n,
                                                  [stream for module in self.values()
                                                   for stream in module.values()
                                                   if module.conf is None or
                                                   not module.conf.enabled])

    def get_brief_description_installed(self, module_n):
        return self.get_brief_description_by_name(module_n,
                                                  [stream for module in self.values()
                                                   for stream in module.values()
                                                   if module.conf is not None and
                                                   module.conf.enabled and
                                                   module.conf.version],
                                                  True)

    def get_brief_description_by_name(self, module_n, repo_module_streams, only_installed=False):
        if module_n is None or not module_n:
            return self._get_brief_description(repo_module_streams, only_installed)
        else:
            return self._get_brief_description([stream for stream in repo_module_streams
                                                if fnmatch.fnmatch(stream.parent.name,
                                                                   module_n[0])],
                                               only_installed)

    @staticmethod
    def _get_brief_description(repo_module_streams, only_installed=False):
        repo_module_versions = [repo_module_version
                                for repo_module_stream in repo_module_streams
                                for repo_module_version in repo_module_stream.values()]

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
        column_info.right = True

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

    def parse_module_nsvp(self, user_input):
        def parse_module_np(user_input):
            try:
                name, profile = user_input.split(name_profile_delimiter, 1)
            except ValueError:
                name = user_input
                profile = default_profile

            return name, profile

        nsv, profile = parse_module_np(user_input)
        name, stream, version = self.parse_module_nsv(nsv)

        return name, stream, version, profile

    def parse_module_nsv(self, user_input):
        # TODO dehack
        def get_default_stream(releasever=None):

            def get_split_lower_values(line):
                line_without_crlf = line[:-1]
                return line_without_crlf.lower().split("=")

            values = {}
            with open("/etc/os-release") as f:
                for line in f.readlines():
                    option, value = get_split_lower_values(line)
                    values[option] = value

            # higher management order
            logger.warning(module_errors[HORRIBLE_HACK_WARN])
            return "f{}".format(releasever) if releasever is not None \
                else "{}{}".format(values["id"][0], values["version_id"])

        def determine_stream_or_version(stream_or_version):
            filtered_names = fnmatch.filter(self, name)
            for filtered_name in filtered_names:
                if fnmatch.filter(self[filtered_name], stream_or_version):
                    return name, stream_or_version, None

            return name, get_default_stream(self.base.conf.releasever), stream_or_version

        try:
            name, stream, version = user_input.rsplit(name_stream_version_delimiter, 2)

            if not fnmatch.filter(self, name) \
                    and fnmatch.filter(self, "{}-{}".format(name, stream)):
                name = "{}-{}".format(name, stream)
                return determine_stream_or_version(version)
            elif not fnmatch.filter(self, name) \
                    and not fnmatch.filter(self, "{}-{}".format(name, stream)) \
                    and fnmatch.filter(self, "{}-{}-{}".format(name, stream, version)):
                return name, get_default_stream(self.base.conf.releasever), None

            return name, stream, version
        except ValueError:
            try:
                name, stream = user_input.rsplit(name_stream_version_delimiter, 1)

                if not fnmatch.filter(self, name) \
                        and fnmatch.filter(self, "{}-{}".format(name, stream)):
                    return "{}-{}".format(name, stream), \
                           get_default_stream(self.base.conf.releasever), \
                           None

                return determine_stream_or_version(stream)
            except ValueError:
                return user_input, get_default_stream(self.base.conf.releasever), None


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


class ModuleTransactionProgress(TransactionProgress):
    def __init__(self):
        super(ModuleTransactionProgress, self).__init__()
        self.repo_modules = []
        self.saved = False

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        if not self.saved and (action == TRANS_POST or action == PKG_VERIFY):
            self.saved = True
            for repo_module in self.repo_modules:
                conf = repo_module.conf
                conf.enabled = True
                conf.version = repo_module.installed_repo_module_version.version

                profiles = repo_module.installed_profiles
                profiles.extend(conf.profiles)
                conf.profiles = sorted(set(profiles))

                repo_module.write_conf_to_file()
