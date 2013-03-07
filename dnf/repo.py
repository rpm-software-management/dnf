# repo.py
# DNF Repository objects.
#
# Copyright (C) 2013  Red Hat, Inc.
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

import dnf.util
import dnf.yum.Errors
import dnf.yum.config
import librepo
import os.path
import time

class _Result(object):
    def __init__(self, res):
        self.repo_dct = res.getinfo(librepo.LRR_YUM_REPO)
        self.repomd_dct = res.getinfo(librepo.LRR_YUM_REPOMD)

    def file_age(self, what):
        f_ts = dnf.util.file_timestamp(self.repo_dct[what])
        return time.time() - f_ts

    @property
    def filelists_fn(self):
        return self.repo_dct.get('filelists')

    @property
    def presto_fn(self):
        return self.repo_dct.get('prestodelta')

    @property
    def primary_fn(self):
        return self.repo_dct.get('primary')

    @property
    def repomd_fn(self):
        return self.repo_dct.get('repomd')

class Repo(dnf.yum.config.RepoConf):
    def __init__(self, id_):
        super(Repo, self).__init__()
        self._progress = None
        self.id = id_
        self.basecachedir = None
        self.fallback_basecachedir = None
        self.base_persistdir = ""
        self.res = None
        self.yumvar = {} # empty dict of yumvariables for $string replacement

    def _lr_handle(self):
        h = librepo.Handle()
        h.setopt(librepo.LRO_REPOTYPE, librepo.LR_YUMREPO)
        h.setopt(librepo.LRO_YUMDLIST, ["primary", "filelists", "prestodelta"])
        h.setopt(librepo.LRO_GPGCHECK, self.repo_gpgcheck)
        return h

    def _lr_cache_handle(self):
        h = self._lr_handle()
        h.setopt(librepo.LRO_DESTDIR, self.cachedir)
        h.setopt(librepo.LRO_URL, self.cachedir)
        h.setopt(librepo.LRO_LOCAL, True)
        return h

    def _lr_download_handle(self):
        h = self._lr_handle()
        h.setopt(librepo.LRO_DESTDIR, dnf.util.tmpdir())
        if self.metalink:
            h.setopt(librepo.LRO_MIRRORLIST, self.metalink)
        elif self.mirrorlist:
            h.setopt(librepo.LRO_MIRRORLIST, self.mirrorlist)
        elif self.baseurl:
            h.setopt(librepo.LRO_URL, self.baseurl[0])
        else:
            msg = 'Cannot find a valid baseurl for repo: %s' % self.id
            raise Errors.RepoError, msg
        if self._progress is not None:
            h.setopt(librepo.LRO_PROGRESSCB, self._progress.librepo_cb)
        return h

    def _lr_get_destdir(self, handle):
        return handle.getinfo(librepo.LRI_DESTDIR)

    def _lr_get_local(self, handle):
        return handle.getinfo(librepo.LRI_LOCAL)

    def _handle_uses_callback(self, handle):
        return self._progress is not None and not self._lr_get_local(handle)

    def _lr_perform(self, handle):
        r = librepo.Result()
        dnf.util.ensure_dir(self.cachedir)
        if self._handle_uses_callback(handle):
            self._progress.begin(self.name)
        handle.perform(r)
        if self._handle_uses_callback(handle):
            self._progress.end()
        return _Result(r)

    @property
    def cachedir(self):
        return os.path.join(self.basecachedir, self.id)

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def error_message(self, exception):
        msg = "Problem with repo '%s': %s" % (self.id, str(exception))
        print msg

    @property
    def filelists_fn(self):
        return self.res.filelists_fn

    @property
    def presto_fn(self):
        return self.res.presto_fn

    @property
    def primary_fn(self):
        return self.res.primary_fn

    def replace_cache(self, from_dir):
        dnf.util.rm_rf(self.cachedir)
        os.rename(from_dir, self.cachedir)

    @property
    def repomd_fn(self):
        return self.res.repomd_fn

    def sync(self):
        try:
            handle = self._lr_cache_handle()
            self.res = self._lr_perform(handle)
            if self.res.file_age("primary") < self.metadata_expire:
                return True
        except librepo.LibrepoException as e:
            pass

        try:
            handle = self._lr_download_handle()
            self.res = self._lr_perform(handle)
            self.replace_cache(self._lr_get_destdir(handle))

            # get everything from the cache now:
            handle = self._lr_cache_handle()
            self.res = self._lr_perform(handle)
        except librepo.LibrepoException as e:
            msg = str(e)
            self.error_message(msg)
            raise dnf.yum.Errors.RepoError(msg)
        return True

    def set_failure_callback(self, cb):
        pass

    def set_interrupt_callback(self, cb):
        pass

    def set_progress_bar(self, progress):
        self._progress = progress
