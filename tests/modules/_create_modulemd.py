#!/usr/bin/python


import os
import sys



MODULES_DIR = os.path.join(os.path.dirname(__file__), "modules")


import modulemd


def parse_module_id(module_id):
    return module_id.rsplit("-", 2)


for module_id in os.listdir(MODULES_DIR):
    if module_id.startswith("_"):
        continue

    name, stream, version = parse_module_id(module_id)

    for arch in os.listdir(os.path.join(MODULES_DIR, module_id)):
        module_dir = os.path.join(MODULES_DIR, module_id, arch)
        rpms = [i for i in os.listdir(module_dir) if i.endswith(".rpm")]

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

        mmd.dump(os.path.join(module_dir, "%s.%s.yaml" % (module_id, arch)))
