#!/usr/bin/python


import os
import json

import modulemd


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

        mmd = modulemd.ModuleMetadata()
        mmd.name = name
        mmd.stream = stream
        mmd.version = int(version)
        mmd.add_module_license("LGPLv2")
        mmd.summary = "Fake module"
        mmd.description = mmd.summary
        for rpm in rpms:
            mmd.components.add_rpm(rpm.rsplit("-", 2)[0], "")
            mmd.artifacts.add_rpm(rpm[:-4])
        for profile_name in profiles:
            profile = modulemd.ModuleProfile()
            profile.rpms.update(profiles[profile_name]["rpms"])
            mmd.profiles[profile_name] = profile

        mmd.dump(os.path.join(module_dir, "%s.%s.yaml" % (module_id, arch)))
