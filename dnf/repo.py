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

import dnf.const
import dnf.util
import dnf.yum.Errors
import dnf.yum.config
import librepo
import os
import shutil
import urlgrabber.grabber
import time
import types

_METADATA_RELATIVE_DIR="repodata"

class _Result(object):
    def __init__(self, res):
        self.repo_dct = res.getinfo(librepo.LRR_YUM_REPO)
        self.repomd_dct = res.getinfo(librepo.LRR_YUM_REPOMD)

    @property
    def age(self):
        return self.file_age('primary')

    @property
    def content_tags(self):
        return self.repomd_dct.get('content_tags')

    @property
    def distro_tags(self):
        pairs = self.repomd_dct.get('distro_tags', [])
        return {k:v for (k, v) in pairs}

    def file_age(self, what):
        return time.time() - self.file_timestamp(what)

    def file_timestamp(self, what):
        return dnf.util.file_timestamp(self.repo_dct[what])

    @property
    def filelists_fn(self):
        return self.repo_dct.get('filelists')

    @property
    def md_timestamp(self):
        """Gets the highest timestamp of all metadata types."""
        timestamps = [content.get('timestamp')
                      for (what, content) in self.repomd_dct.iteritems()
                      if isinstance(content, dict)]
        return max(timestamps)

    @property
    def presto_fn(self):
        return self.repo_dct.get('prestodelta')

    @property
    def primary_fn(self):
        return self.repo_dct.get('primary')

    @property
    def repomd_fn(self):
        return self.repo_dct.get('repomd')

    @property
    def revision(self):
        return self.repomd_dct.get('revision')

    @property
    def timestamp(self):
        return self.file_timestamp('primary')

    @property
    def url(self):
        return self.repo_dct.get('url')

class _Handle(librepo.Handle):
    def __init__(self, gpgcheck):
        super(_Handle, self).__init__()
        self.gpgcheck = gpgcheck
        self.interruptible = True
        self.repotype = librepo.LR_YUMREPO
        self.useragent = dnf.const.USER_AGENT
        self.yumdlist = ["primary", "filelists", "prestodelta"]

    @classmethod
    def new_local(cls, gpgcheck, cachedir):
        h = cls(gpgcheck)
        h.destdir = cachedir
        h.url = cachedir
        h.local = True
        return h

    @classmethod
    def new_remote(cls, gpgcheck, destdir, mirror_setup, progress_cb):
        h = cls(gpgcheck)
        h.destdir = destdir
        h.setopt(mirror_setup[0], mirror_setup[1])
        h.progresscb = progress_cb
        return h

    @property
    def metadata_dir(self):
        return os.path.join(self.destdir, _METADATA_RELATIVE_DIR)

SYNC_TRY_CACHE  = 1
SYNC_EXPIRED   = 2
SYNC_ONLY_CACHE = 3

class Repo(dnf.yum.config.RepoConf):
    DEFAULT_SYNC = SYNC_TRY_CACHE

    def __init__(self, id_):
        super(Repo, self).__init__()
        self._progress = None
        self.id = id_
        self.basecachedir = None
        self.base_persistdir = ""
        self.res = None
        self.sync_strategy = self.DEFAULT_SYNC
        self.yumvar = {} # empty dict of yumvariables for $string replacement

    def _exc2msg(self, librepo_exception):
        exc_msg = librepo_exception[1]
        msg = "Problem with repo '%s': %s" % (self.id, exc_msg)
        return msg

    def _handle_load(self, handle):
        r = librepo.Result()
        if handle.progresscb:
            self._progress.begin(self.name)
        handle.perform(r)
        if handle.progresscb:
            self._progress.end()
        return _Result(r)

    def _handle_new_local(self, destdir):
        return _Handle.new_local(self.repo_gpgcheck, destdir)

    def _handle_new_remote(self, destdir):
        cb = None
        if self._progress is not None:
            cb = self._progress.librepo_cb
        return _Handle.new_remote(self.repo_gpgcheck, destdir,
                                  self._mirror_setup_args(), cb)

    def _mirror_setup_args(self):
        if self.metalink:
            return librepo.LRO_MIRRORLIST, self.metalink
        elif self.mirrorlist:
            return librepo.LRO_MIRRORLIST, self.mirrorlist
        elif self.baseurl:
            return librepo.LRO_URL, self.baseurl[0]
        else:
            msg = 'Cannot find a valid baseurl for repo: %s' % self.id
            raise dnf.yum.Errors.RepoError, msg

    def _replace_metadata(self, from_dir):
        dnf.util.ensure_dir(self.cachedir)
        dnf.util.rm_rf(self.metadata_dir)
        shutil.move(from_dir, self.metadata_dir)
        # metadata is fresh, it's ok to use it
        self.sync_strategy = SYNC_TRY_CACHE

    def _try_cache(self):
        if self.sync_strategy == SYNC_EXPIRED:
            return False
        if self.res:
            return True
        handle = self._handle_new_local(self.cachedir)
        try:
            self.res = self._handle_load(handle)
        except librepo.LibrepoException as e:
            return False
        if self.sync_strategy == SYNC_ONLY_CACHE:
            return True
        return self.res.file_age("primary") < self.metadata_expire

    @property
    def cachedir(self):
        return os.path.join(self.basecachedir, self.id)

    _REPOCONF_ATTRS = set(dir(dnf.yum.config.RepoConf))
    def dump(self):
        """Return a string representing configuration of this repo."""
        output = '[%s]\n' % self.id
        for attr in dir(self):
            # exclude all vars which are not opts
            if attr not in self._REPOCONF_ATTRS:
                continue
            if attr.startswith('_'):
                continue

            res = getattr(self, attr)
            if isinstance(res, types.MethodType):
                continue
            if not res and type(res) not in (type(False), type(0)):
                res = ''
            if type(res) == types.ListType:
                res = ',\n   '.join(res)
            output = output + '%s = %s\n' % (attr, res)

        return output

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    @property
    def filelists_fn(self):
        return self.res.filelists_fn

    def get_package(self, pkg, text=None):
        dnf.util.ensure_dir(self.pkgdir)
        handle = self._handle_new_remote(self.pkgdir)
        if handle.progresscb:
            text = text if text is not None else pkg.location
            self._progress.begin(text)
        handle.download(pkg.location)
        if handle.progresscb:
            self._progress.end()
        return pkg.localPkg()

    @property
    def metadata_dir(self):
        return os.path.join(self.cachedir, _METADATA_RELATIVE_DIR)

    def metadata_expire_in(self):
        """Get the number of seconds after which the metadata will expire.

        Returns a tuple, boolean whether the information can be obtained and the
        number of seconds. Negative number means the metadata has expired
        already.

        """
        self._try_cache()
        if self.res:
            return (True, self.metadata_expire - self.res.age)
        return (False, 0)

    def md_expire_cache(self):
        """Mark whatever is in the current cache expired.

        This repo instance will alway try to fetch a fresh metadata after this
        method is called.

        """
        self.res = None
        self.sync_strategy = SYNC_EXPIRED

    def md_try_cache(self):
        """Use cache for metadata if possible, sync otherwise."""
        self.sync_strategy = SYNC_TRY_CACHE

    @property
    def md_only_cached(self):
        return self.sync_strategy == SYNC_ONLY_CACHE

    @md_only_cached.setter
    def md_only_cached(self, val):
        """Force using only the metadata the repo has in the local cache."""
        if val:
            self.sync_strategy = SYNC_ONLY_CACHE
        else:
            self.sync_strategy = SYNC_TRY_CACHE

    @property
    def presto_fn(self):
        return self.res.presto_fn

    @property
    def pkgdir(self):
        return os.path.join(self.cachedir, 'packages')

    @property
    def primary_fn(self):
        return self.res.primary_fn

    @property
    def repomd_fn(self):
        return self.res.repomd_fn

    def load(self):
        """Load the metadata for this repo.

        Depending on the configuration and the age and consistence of data
        available on the disk cache, either loads the metadata from the cache or
        downloads them from the mirror, baseurl or metalink.

        This method will not try to refresh the loaded data if called twice, IOW
        the loading is by default lazy.

        Returns True if this call to load() caused a fresh metadata download.

        """
        if self._try_cache():
            return False
        if self.sync_strategy == SYNC_ONLY_CACHE:
            msg = "Cache-only enabled but no cache for '%s'" % self.id
            raise dnf.yum.Errors.RepoError(msg)
        try:
            with dnf.util.tmpdir() as tmpdir:
                handle = self._handle_new_remote(tmpdir)
                self._handle_load(handle)
                # override old md with the new ones:
                self._replace_metadata(handle.metadata_dir)

            # get md from the cache now:
            handle = self._handle_new_local(self.cachedir)
            self.res = self._handle_load(handle)
        except librepo.LibrepoException as e:
            self.res = None
            raise dnf.yum.Errors.RepoError(self._exc2msg(e))
        return True

    def set_failure_callback(self, cb):
        pass

    def set_interrupt_callback(self, cb):
        pass

    def set_progress_bar(self, progress):
        self._progress = progress

    def urlgrabber_opts(self):
        """Get http configuration for urlgrabber.

        Deprecated. :noapi

        """
        return {'keepalive': self.keepalive,
                'bandwidth': self.bandwidth,
                'retry': self.retries,
                'throttle': self.throttle,
                'proxies': {},
                'timeout': self.timeout,
                'ip_resolve': self.ip_resolve,
                'http_headers': (),
                'ssl_verify_peer': self.sslverify,
                'ssl_verify_host': self.sslverify,
                'ssl_ca_cert': self.sslcacert,
                'ssl_cert': self.sslclientcert,
                'ssl_key': self.sslclientkey,
                'user_agent': urlgrabber.grabber.default_grabber.opts.user_agent,
                'username': self.username,
                'password': self.password,
                }
