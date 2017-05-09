#!/usr/bin/python


import os
import argparse
import subprocess
import tempfile

import modulemd


def get_parser():
    """
    Construct argument parser.

    :returns: ArgumentParser object with arguments set up.
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Scan directory for modulemd yaml files and inject them into repodata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "path",
        metavar="directory_to_index",
    )
    return parser


def index_modulemd_files(repo_path):
    result = []
    for fn in sorted(os.listdir(repo_path)):
        if not fn.endswith(".yaml"):
            continue
        yaml_path = os.path.join(repo_path, fn)
        mmd = modulemd.ModuleMetadata()
        mmd.load(yaml_path)
        result.append(mmd)
    return result


def modify_repo(repo_path, modules):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "modules.yaml")
    modulemd.dump_all(path, modules)
    subprocess.check_call(["modifyrepo_c", "--mdtype=modules", path,
                           os.path.join(repo_path, "repodata")])
    os.unlink(path)
    os.rmdir(tmp)


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    modules = index_modulemd_files(args.path)
    modify_repo(args.path, modules)
