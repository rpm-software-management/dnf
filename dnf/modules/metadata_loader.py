# Copyright (c) 2017  Red Hat, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import gzip
import os

from dnf.i18n import _
import modulemd

supported_mdversions = (1, )


class ModuleMetadataLoader(object):
    def __init__(self, repo=None):
        self.repo = repo

    def load(self):
        if self.repo is None:
            raise Exception(_("Cannot load from cache dir: {}".format(self.repo)))

        content_of_cachedir = os.listdir(self.repo._cachedir + "/repodata")
        modules_yaml_gz = list(filter(lambda repodata_file: 'modules' in repodata_file,
                                      content_of_cachedir))

        if len(modules_yaml_gz) == 0:
            raise Exception(_("Missing file *modules.yaml in metadata cache dir: {}"
                            .format(self.repo._cachedir)))
        modules_yaml_gz = "{}/repodata/{}".format(self.repo._cachedir, modules_yaml_gz[0])

        with gzip.open(modules_yaml_gz, "r") as extracted_modules_yaml_gz:
            modules_yaml = extracted_modules_yaml_gz.read()

        return modulemd.loads_all(modules_yaml)
