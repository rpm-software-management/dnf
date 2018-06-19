#!/usr/bin/python


import os
import json

import gi

gi.require_version('Modulemd', '1.0')
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

        mmd = Modulemd.Module()
        mmd.set_mdversion(int(1))
        mmd.set_name(name)
        mmd.set_stream(stream)
        mmd.set_version(int(version))
        sset = Modulemd.SimpleSet()
        sset.add("LGPLv2")
        mmd.set_module_licenses(sset)
        mmd.set_summary("Fake module")
        mmd.set_description(mmd.get_summary())
        artifacts = Modulemd.SimpleSet()
        for rpm in rpms:
            artifacts.add(rpm[:-4])
        mmd.set_rpm_artifacts(artifacts)
        for profile_name in profiles:
            profile = Modulemd.Profile()
            profile.set_name(profile_name)
            profile_rpms = Modulemd.SimpleSet()
            profile_rpms.set(profiles[profile_name]["rpms"])
            profile.set_rpms(profile_rpms)
            mmd.add_profile(profile)

        Modulemd.dump([mmd], os.path.join(module_dir, "%s.%s.yaml" % (module_id, arch)))
