#!/usr/bin/python

"""
Generate module metadata for modularity tests.

Input:

RPMs built under ../modules/$name-$stream-$version/$arch
profiles defined in $name-$stream-$version/profiles.json
Output:

../modules/$name-$stream-$version/$arch/$name-$stream-$version.$arch.yaml
"""

import os
import json

import gi

gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd

MODULES_DIR = os.path.join(os.path.dirname(__file__), "..", "modules")
SPECS_DIR = os.path.join(os.path.dirname(__file__), "..", "specs")


def parse_module_id(module_id):
    return module_id.rsplit("-", 2)


for module_id in os.listdir(MODULES_DIR):
    if module_id.startswith("_"):
        continue

    name, stream, version = parse_module_id(module_id)

    profiles_file = os.path.join(SPECS_DIR, module_id, "profiles.json")
    if os.path.isfile(profiles_file):
        with open(profiles_file, "r") as f:
            profiles = json.load(f)
    else:
        profiles = {}

    for arch in os.listdir(os.path.join(MODULES_DIR, module_id)):
        if arch == "noarch":
            continue

        module_dir = os.path.join(MODULES_DIR, module_id, arch)
        rpms = [i for i in os.listdir(module_dir) if i.endswith(".rpm")]

        noarch_module_dir = os.path.join(MODULES_DIR, module_id, "noarch")
        if os.path.isdir(noarch_module_dir):
            noarch_rpms = [i for i in os.listdir(noarch_module_dir) if i.endswith(".rpm")]
        else:
            noarch_rpms = []

        rpms = sorted(set(rpms) | set(noarch_rpms))

        # HACK: force epoch to make test data compatible with libmodulemd >= 1.4.0
        rpms_with_epoch = []
        for i in rpms:
            n, v, ra = i.rsplit("-", 2)
            nevra = "%s-0:%s-%s" % (n, v, ra)
            rpms_with_epoch.append(nevra)
        rpms = rpms_with_epoch

        module_stream = Modulemd.ModuleStreamV2.new(name, stream)
        module_stream.set_version(int(version))
        module_stream.add_module_license("LGPLv2")
        module_stream.set_summary("Fake module")
        module_stream.set_description(module_stream.get_summary())
        for rpm in rpms:
            module_stream.add_rpm_artifact(rpm[:-4])
        for profile_name in profiles:
            profile = Modulemd.Profile.new(profile_name)
            profile.set_description("Description for profile %s." % profile_name)

            for profile_rpm in profiles[profile_name]["rpms"]:
                profile.add_rpm(profile_rpm)

            module_stream.add_profile(profile)

        module_index = Modulemd.ModuleIndex()
        module_index.add_module_stream(module_stream)

        with open(os.path.join(module_dir, "%s.%s.yaml" % (module_id, arch)), 'w') as f:
            f.write(module_index.dump_to_string())
