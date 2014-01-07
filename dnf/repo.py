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

from __future__ import absolute_import
from dnf.i18n import ucd
import dnf.const
import dnf.util
import dnf.exceptions
import dnf.yum.config
import dnf.yum.misc
import logging
import librepo
import operator
import os
import shutil
import string
import time
import types

_METADATA_RELATIVE_DIR ="repodata"
_METALINK_FILENAME     ="metalink.xml"
_MIRRORLIST_FILENAME   ="mirrorlist"
_RECOGNIZED_CHKSUMS    = ['sha512', 'sha256']

logger = logging.getLogger("dnf")

def repo_id_invalid(repo_id):
    """Return index of an invalid character in the repo ID (if present). :api"""
    allowed_chars = ''.join((string.ascii_letters, string.digits, '-_.:'))
    invalids = (index for index, char in enumerate(repo_id)
                if char not in allowed_chars)
    return dnf.util.first(invalids)

def _metalink_path(dirname):
    return os.path.join(dirname, _METALINK_FILENAME)

def _mirrorlist_path(dirname):
    return os.path.join(dirname, _MIRRORLIST_FILENAME)

def _subst2tuples(subst_dct):
    return [(k, v) for (k, v) in subst_dct.items()]

class _Handle(librepo.Handle):
    def __init__(self, gpgcheck, max_mirror_tries):
        super(_Handle, self).__init__()
        self.gpgcheck = gpgcheck
        self.maxmirrortries = max_mirror_tries
        self.interruptible = True
        self.repotype = librepo.LR_YUMREPO
        self.useragent = dnf.const.USER_AGENT
        self.yumdlist = ["primary", "filelists", "prestodelta", "group_gz"]

    @classmethod
    def new_local(cls, subst_dct, gpgcheck, max_mirror_tries, cachedir):
        h = cls(gpgcheck, max_mirror_tries)
        h.varsub = _subst2tuples(subst_dct)
        h.destdir = cachedir
        h.urls = cachedir
        h.local = True
        if os.access(h.metalink_path, os.R_OK):
            h.mirrorlist = h.metalink_path
        elif os.access(h.mirrorlist_path, os.R_OK):
            h.mirrorlist = h.mirrorlist_path
        return h

    @property
    def metadata_dir(self):
        return os.path.join(self.destdir, _METADATA_RELATIVE_DIR)

    @property
    def metalink_path(self):
        return _metalink_path(self.destdir)

    @property
    def mirrorlist_path(self):
        return _mirrorlist_path(self.destdir)

class Metadata(object):
    def __init__(self, res, handle):
        self.expired = False
        self.fresh = False # :api
        self.repo_dct = res.yum_repo
        self.repomd_dct = res.yum_repomd
        self._mirrors = handle.mirrors[:]

    @property
    def age(self):
        return self.file_age('primary')

    @property
    def comps_fn(self):
        return self.repo_dct.get("group_gz") or self.repo_dct.get("group")

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
        try:
            return dnf.util.file_timestamp(self.repo_dct[what])
        except OSError as e:
            raise dnf.exceptions.MetadataError(ucd(e))

    @property
    def filelists_fn(self):
        return self.repo_dct.get('filelists')

    @property
    def mirrors(self):
        return self._mirrors

    @property
    def md_timestamp(self):
        """Gets the highest timestamp of all metadata types."""
        timestamps = [content.get('timestamp')
                      for (what, content) in self.repomd_dct.items()
                      if isinstance(content, dict)]
        return max(timestamps)

    @property
    def presto_fn(self):
        return self.repo_dct.get('prestodelta')

    @property
    def primary_fn(self):
        return self.repo_dct.get('primary')

    def reset_age(self):
        dnf.util.touch(self.primary_fn, no_create=True)

    @property
    def repomd_fn(self):
        return self.repo_dct.get('repomd')

    @property
    def revision(self):
        return self.repomd_dct.get('revision')

    @property
    def timestamp(self):
        return self.file_timestamp('primary')

SYNC_TRY_CACHE  = 1
SYNC_EXPIRED    = 2 # consider the current cache expired, no matter its real age
SYNC_ONLY_CACHE = 3 # use the local cache, even if it's expired, never download.

class Repo(dnf.yum.config.RepoConf):
    # :api
    DEFAULT_SYNC = SYNC_TRY_CACHE

    def __init__(self, id_, basecachedir):
        # :api
        super(Repo, self).__init__()
        self._progress = None
        self.id = id_ # :api
        self.basecachedir = basecachedir
        self.metadata = None # :api
        self.sync_strategy = self.DEFAULT_SYNC
        self.yumvar = {} # empty dict of yumvariables for $string replacement
        self.max_mirror_tries = 0 # try them all
        self._handle = None

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.id)

    def _exc2msg(self, librepo_exception):
        exc_msg = librepo_exception.args[1]
        msg = "Problem with repo '%s': %s" % (self.id, exc_msg)
        return msg

    def _handle_load(self, handle):
        if handle.progresscb:
            self._progress.begin(self.name)
        result = handle.perform()
        if handle.progresscb:
            self._progress.end()
        return Metadata(result, handle)

    def _handle_new_local(self, destdir):
        return _Handle.new_local(self.yumvar, self.repo_gpgcheck,
                                 self.max_mirror_tries, destdir)

    def _handle_new_remote(self, destdir, mirror_setup=True):
        h = _Handle(self.repo_gpgcheck, self.max_mirror_tries)
        h.varsub = _subst2tuples(self.yumvar)
        h.destdir = destdir

        # setup mirror URLs
        mirrorlist = self.metalink or self.mirrorlist
        if mirrorlist:
            if mirror_setup:
                h.setopt(librepo.LRO_MIRRORLIST, mirrorlist)
                h.setopt(librepo.LRO_FASTESTMIRROR, True)
                h.setopt(librepo.LRO_FASTESTMIRRORCACHE,
                         os.path.join(self.basecachedir, 'fastestmirror.cache'))
            else:
                # use already resolved mirror list
                h.setopt(librepo.LRO_URLS, self.metadata.mirrors)
        elif self.baseurl:
            h.setopt(librepo.LRO_URLS, self.baseurl)
        else:
            msg = 'Cannot find a valid baseurl for repo: %s' % self.id
            raise dnf.exceptions.RepoError(msg)

        # single-file download progress
        if self._progress:
            h.progresscb = self._progress.librepo_cb

            fo = self._progress.fo
            running = [False]
            def callback(cbdata, stage, data):
                if stage == librepo.FMSTAGE_DETECTION:
                    # pinging mirrors, this might take a while
                    msg = 'determining the fastest mirror (%d hosts).. ' % data
                    running[0] = True
                elif stage == librepo.FMSTAGE_STATUS and running[0]:
                    # done.. report but ignore any errors
                    msg = 'error: %s\n' % data if data else 'done.\n'
                else:
                    # ignore other stages
                    return
                fo.write(msg)
                fo.flush()
            h.fastestmirrorcb = callback

        # apply repo options
        h.proxy = self.proxy

        return h

    def _handle_new_pkg_download(self):
        return self._handle_new_remote(self.pkgdir, mirror_setup=False)

    def get_handle(self):
        """Returns a librepo handle, set as per the repo options

        Note that destdir is None, and the handle is cached.
        """
        if not self._handle:
            self._handle = self._handle_new_remote(None)
        return self._handle

    @property
    def local(self):
        if self.metalink or self.mirrorlist:
            return False
        if self.baseurl[0].startswith('file://'):
            return True
        return False

    def _replace_metadata(self, handle):
        dnf.util.ensure_dir(self.cachedir)
        dnf.util.rm_rf(self.metadata_dir)
        dnf.util.rm_rf(self.metalink_path)
        dnf.util.rm_rf(self.mirrorlist_path)
        shutil.move(handle.metadata_dir, self.metadata_dir)
        if handle.metalink:
            shutil.move(handle.metalink_path, self.metalink_path)
        elif handle.mirrorlist:
            shutil.move(handle.mirrorlist_path, self.mirrorlist_path)

    def _try_cache(self):
        """Tries to load metadata from the local cache.

        Correctly sets self.metadata.expired.

        Returns True if we got any (even expired) metadata locally.

        """
        assert(self.metadata is None)
        handle = self._handle_new_local(self.cachedir)
        try:
            self.metadata = self._handle_load(handle)
        except (librepo.LibrepoException, IOError) as e:
            return False
        if self.sync_strategy == SYNC_EXPIRED:
            # we shouldn't exit earlier as reviving needs self.metadata
            self.metadata.expired = True
            return False
        self.metadata.expired = self.metadata.age >= self.metadata_expire
        return True

    def _try_revive(self):
        """Use metalink to check whether our metadata are still current."""
        if not self.metadata:
            return False
        if not self.metalink:
            return False
        repomd_fn = self.metadata.repo_dct['repomd']
        with dnf.util.tmpdir() as tmpdir, open(repomd_fn) as repomd:
            handle = self._handle_new_remote(tmpdir)
            handle.fetchmirrors = True
            handle.perform()
            if handle.metalink is None:
                logger.debug("reviving: repo '%s' skipped, no metalink.", self.id)
                return False
            hashes = handle.metalink['hashes']
            hashes = [hsh_val for hsh_val in hashes if hsh_val[0] in _RECOGNIZED_CHKSUMS]
            if len(hashes) < 1:
                logger.debug("reviving: repo '%s' skipped, no usable hash.",
                             self.id)
                return False
            algos = list(map(operator.itemgetter(0), hashes))
            chksums = dnf.yum.misc.Checksums(algos,
                                             ignore_missing=True,
                                             ignore_none=True)
            chksums.read(repomd, -1)
            digests = chksums.hexdigests()
            for (algo, digest) in hashes:
                if digests[algo] != digest:
                    logger.debug("reviving: failed for '%s', mismatched %s sum.",
                                 self.id, algo)
                    return False
        logger.debug("reviving: '%s' can be revived.", self.id)
        return True

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
            if isinstance(res, list):
                res = ',\n   '.join(res)
            output = output + '%s = %s\n' % (attr, res)

        return output

    def disable(self):
        # :api
        self.enabled = False

    def enable(self):
        # :api
        self.enabled = True

    @property
    def filelists_fn(self):
        return self.metadata.filelists_fn

    def get_package_target(self, po, cb):
        dnf.util.ensure_dir(self.pkgdir)
        ctype, csum = po.returnIdSum()
        ctype_code = getattr(librepo, ctype.upper(), librepo.CHECKSUM_UNKNOWN)
        if ctype_code == librepo.CHECKSUM_UNKNOWN:
            logger.warn(_("unsupported checksum type: %s") % ctype)

        progresscb = endcb = None
        if cb:
            progresscb = cb.progress
            def endcb(text, status, msg):
                # using a local file with good checksum is not a failure
                status = 'SKIPPED' if status == librepo.TRANSFER_ALREADYEXISTS else 'FAILED'
                cb.end(text, po.size, msg, status)

        target = librepo.PackageTarget(
            po.location, self.pkgdir, ctype_code, csum, po.size, po.baseurl, True,
            progresscb=progresscb,
            cbdata=os.path.basename(po.location),
            handle=self.get_handle(),
            endcb=endcb)
        target.po = po
        return target

    def get_package(self, pkg, text=None):
        if self.local:
            return pkg.localPkg()
        dnf.util.ensure_dir(self.pkgdir)
        handle = self._handle_new_pkg_download()
        if handle.progresscb:
            text = text if text is not None else pkg.location
            self._progress.begin(text)
        try:
            handle.download(pkg.location, base_url=pkg.baseurl)
        except librepo.LibrepoException as e:
            raise dnf.exceptions.RepoError(self._exc2msg(e))
        finally:
            if handle.progresscb:
                self._progress.end()
        return pkg.localPkg()

    def load(self):
        """Load the metadata for this repo. :api

        Depending on the configuration and the age and consistence of data
        available on the disk cache, either loads the metadata from the cache or
        downloads them from the mirror, baseurl or metalink.

        This method will by default not try to refresh already loaded data if
        called repeatedly.

        Returns True if this call to load() caused a fresh metadata download.

        """
        if self.metadata or self._try_cache():
            if self.sync_strategy == SYNC_ONLY_CACHE or not self.metadata.expired:
                logger.debug('repo: using cache for: %s' % self.id)
                return False
        if self.sync_strategy == SYNC_ONLY_CACHE:
            msg = "Cache-only enabled but no cache for '%s'" % self.id
            raise dnf.exceptions.RepoError(msg)
        try:
            if self._try_revive():
                # the expired metadata still reflect the origin:
                self.metadata.reset_age()
                self.sync_strategy = SYNC_TRY_CACHE
                self.metadata.expired = False
                return True

            with dnf.util.tmpdir() as tmpdir:
                logger.debug('repo: downloading from remote: %s' % self.id)
                handle = self._handle_new_remote(tmpdir)
                self._handle_load(handle)
                # override old md with the new ones:
                self._replace_metadata(handle)

            # get md from the cache now:
            handle = self._handle_new_local(self.cachedir)
            self.metadata = self._handle_load(handle)
            self.metadata.fresh = True
        except librepo.LibrepoException as e:
            self.metadata = None
            raise dnf.exceptions.RepoError(self._exc2msg(e))
        self.sync_strategy = SYNC_TRY_CACHE
        return True

    @property
    def metadata_dir(self):
        return os.path.join(self.cachedir, _METADATA_RELATIVE_DIR)

    @property
    def metalink_path(self):
        return _metalink_path(self.cachedir)

    @property
    def mirrorlist_path(self):
        return _mirrorlist_path(self.cachedir)

    def metadata_expire_in(self):
        """Get the number of seconds after which the cached metadata will expire.

        Returns a tuple, boolean whether there even is cached metadata and the
        number of seconds it will expire in. Negative number means the metadata
        has expired already.

        """
        if not self.metadata:
            self._try_cache()
        if self.metadata:
            expiration = self.metadata_expire - self.metadata.age
            if self.metadata.expired:
                expiration = min(0, expiration)
            return True, expiration
        return False, 0

    def md_expire_cache(self):
        """Mark whatever is in the current cache expired.

        This repo instance will alway try to fetch a fresh metadata after this
        method is called.

        """
        if self.metadata:
            self.metadata.expired = True
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
        return self.metadata.presto_fn

    @property
    def pkgdir(self):
        if self.local:
            return dnf.util.strip_prefix(self.baseurl[0], 'file://')
        return os.path.join(self.cachedir, 'packages')

    @property
    def primary_fn(self):
        return self.metadata.primary_fn

    @property
    def repomd_fn(self):
        return self.metadata.repomd_fn

    def set_progress_bar(self, progress):
        self._progress = progress

    def valid(self):
        if len(self.baseurl) == 0 and not self.metalink and not self.mirrorlist:
            return "Repository %s has no mirror or baseurl set." % self.id
        return None
