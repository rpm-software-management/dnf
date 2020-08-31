#!/usr/bin/python

"""
Createrepo_c doesn't support indexing module metadata.
This script indexes all yaml files found in a target directory,
concatenates them and injects into repodata as "modules" mdtype.
"""

import os
import argparse
import subprocess
import tempfile

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd


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
    merger = Modulemd.ModuleIndexMerger()
    for fn in sorted(os.listdir(repo_path)):
        if not fn.endswith(".yaml"):
            continue
        yaml_path = os.path.join(repo_path, fn)

        mmd = Modulemd.ModuleIndex()
        mmd.update_from_file(yaml_path, strict=True)

        merger.associate_index(mmd, 0)

    return merger.resolve()


def modify_repo(repo_path, module_index):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "modules.yaml")

    with open(path, 'w') as f:
        f.write(module_index.dump_to_string())

    subprocess.check_call(["modifyrepo_c", "--mdtype=modules", path,
                           os.path.join(repo_path, "repodata")])
    os.unlink(path)
    os.rmdir(tmp)


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    module_index = index_modulemd_files(args.path)
    modify_repo(args.path, module_index)
