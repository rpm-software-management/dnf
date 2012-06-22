# sack.py
# The dnf.Sack class, derived from hawkey.Sack
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import hawkey
import logging
import sys
import yum.Errors
import queries
from yum.packageSack import PackageSackVersion

class Sack(hawkey.Sack):
    def __init__(self, *args, **kwargs):
        super(Sack, self).__init__(*args, **kwargs)
        self._filelists = False
        self.verbose_logger = logging.getLogger("yum.verbose.YumBase")

    def ensure_filelists(self, repos):
        if self._filelists:
            return False

        self._filelists = True
        for yum_repo in repos.listEnabled():
            repo = yum_repo.hawkey_repo
            repo.filelists_fn = yum_repo.getFileListsXML()

        self.load_filelists()
        self.write_filelists()
        return True

    def ensure_presto(self, repos):
        for yum_repo in repos.listEnabled():
            repo = yum_repo.hawkey_repo
            try:
                repo.presto_fn = yum_repo.getPrestoXML()
            except yum.Errors.RepoMDError, e:
                self.verbose_logger.debug("not found deltainfo for: %s" %
                                          yum_repo.name)
        self.load_presto()
        self.write_presto()

    def rpmdb_version(self):
        pkgs = queries.installed(self)
        main = PackageSackVersion()
        for pkg in pkgs:
            ydbi = {} # :hawkey, was: pkg.yumdb_info
            csum = None
            if 'checksum_type' in ydbi and 'checksum_data' in ydbi:
                csum = (ydbi.checksum_type, ydbi.checksum_data)
            main.update(pkg, csum)
        return main
