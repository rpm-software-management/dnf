# repo.py
# DNF Repository objects.
#
# Copyright (C) 2013-2016 Red Hat, Inc.
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
from __future__ import unicode_literals
from dnf.i18n import ucd, _

import dnf.callback
import dnf.conf
import dnf.conf.substitutions
import dnf.const
import dnf.crypto
import dnf.exceptions
import dnf.logging
import dnf.pycomp
import dnf.util
import dnf.yum.misc
import functools
import hashlib
import hawkey
import logging
import librepo
import operator
import os
import re
import shutil
import string
import sys
import time
import traceback

_METADATA_RELATIVE_DIR = "repodata"
_PACKAGES_RELATIVE_DIR = "packages"
_METALINK_FILENAME = "metalink.xml"
_MIRRORLIST_FILENAME = "mirrorlist"
_RECOGNIZED_CHKSUMS = ['sha512', 'sha256']
# Chars allowed in a repo ID
_REPOID_CHARS = string.ascii_letters + string.digits + '-_.:'
# Regex pattern that matches a repo cachedir and captures the repo ID
_CACHEDIR_RE = r'(?P<repoid>[%s]+)\-[%s]{16}' % (re.escape(_REPOID_CHARS),
                                                 string.hexdigits)

# Regex patterns matching any filename that is repo-specific cache data of a
# particular type.  The filename is expected to not contain the base cachedir
# path components.
CACHE_FILES = {
    'metadata': r'^%s\/.*(xml(\.gz|\.xz|\.bz2)?|asc|cachecookie|%s)$' %
                (_CACHEDIR_RE, _MIRRORLIST_FILENAME),
    'packages': r'^%s\/%s\/.+rpm$' % (_CACHEDIR_RE, _PACKAGES_RELATIVE_DIR),
    'dbcache': r'^.+(solv|solvx)$',
}

logger = logging.getLogger("dnf")


def repo_id_invalid(repo_id):
    # :api
    """Return index of an invalid character in the repo ID (if present)."""
    invalids = (i for i, c in enumerate(repo_id) if c not in _REPOID_CHARS)
    return dnf.util.first(invalids)


def _user_pass_str(user, password):
    if user is None:
        return None
    user = dnf.pycomp.urllib_quote(user)
    password = '' if password is None else dnf.pycomp.urllib_quote(password)
    return '%s:%s' % (user, password)


def _priv_metalink_path(dirname):
    return os.path.join(dirname, _METALINK_FILENAME)


def _priv_mirrorlist_path(dirname):
    return os.path.join(dirname, _MIRRORLIST_FILENAME)


def _subst2tuples(subst_dct):
    return [(k, v) for (k, v) in subst_dct.items()]


def _pkg2payload(pkg, progress, *factories):
    for fn in factories:
        pload = fn(pkg, progress)
        if pload is not None:
            return pload
    raise ValueError(_('no matching payload factory for %s') % pkg)


def _download_payloads(payloads, drpm):
    # download packages
    def _download_sort_key(payload):
        return not hasattr(payload, 'delta')

    drpm.err.clear()
    targets = [pload._librepo_target()
               for pload in sorted(payloads, key=_download_sort_key)]
    errs = _DownloadErrors()
    try:
        librepo.download_packages(targets, failfast=True)
    except librepo.LibrepoException as e:
        errs._fatal = e.args[1] or '<unspecified librepo error>'
    drpm.wait()

    # process downloading errors
    errs._recoverable = drpm.err.copy()
    for tgt in targets:
        err = tgt.err
        if err is None or err.startswith('Not finished'):
            continue
        payload = tgt.cbdata
        pkg = payload.pkg
        if err == _('Already downloaded'):
            errs._skipped.add(pkg)
            continue
        pkg.repo._md_expire_cache()
        errs._irrecoverable[pkg] = [err]

    return errs


def _update_saving(saving, payloads, errs):
    real, full = saving
    for pload in payloads:
        pkg = pload.pkg
        if pkg in errs:
            real += pload.download_size
            continue
        real += pload.download_size
        full += pload._full_size
    return real, full


class _DownloadErrors(object):
    def __init__(self):
        self._val_irrecoverable = {}
        self._val_recoverable = {}
        self._fatal = None
        self._skipped = set()

    @property
    def _irrecoverable(self):
        if self._val_irrecoverable:
            return self._val_irrecoverable
        if self._fatal:
            return {'': [self._fatal]}
        return {}

    @property
    def _recoverable(self):
        return self._val_recoverable

    @_recoverable.setter
    def _recoverable(self, new_dct):
        self._val_recoverable = new_dct

    def _bandwidth_used(self, pload):
        if pload.pkg in self._skipped:
            return 0
        return pload.download_size


class _DetailedLibrepoError(Exception):
    def __init__(self, librepo_err, source_url):
        Exception.__init__(self)
        self.librepo_code = librepo_err.args[0]
        self.librepo_msg = librepo_err.args[1]
        self.source_url = source_url


class _Handle(librepo.Handle):
    def __init__(self, gpgcheck, max_mirror_tries, max_parallel_downloads=None):
        super(_Handle, self).__init__()
        self.gpgcheck = gpgcheck
        self.maxmirrortries = max_mirror_tries
        self.interruptible = True
        self.repotype = librepo.LR_YUMREPO
        self.useragent = dnf.const.USER_AGENT
        self.maxparalleldownloads = max_parallel_downloads
        self.yumdlist = [
            "primary", "filelists", "prestodelta", "group_gz", "updateinfo"]
        self.yumslist = [('group_gz', 'group')]

    def __str__(self):
        return '_Handle: metalnk: %s, mlist: %s, urls %s.' % \
            (self.metalinkurl, self.mirrorlisturl, self.urls)

    @classmethod
    def _new_local(cls, subst_dct, gpgcheck, max_mirror_tries, cachedir):
        h = cls(gpgcheck, max_mirror_tries)
        h.varsub = _subst2tuples(subst_dct)
        h.destdir = cachedir
        h.urls = [cachedir]
        h.local = True
        return h

    @property
    def _metadata_dir(self):
        return os.path.join(self.destdir, _METADATA_RELATIVE_DIR)

    @property
    def _metalink_path(self):
        return _priv_metalink_path(self.destdir)

    @property
    def _mirrorlist_path(self):
        return _priv_mirrorlist_path(self.destdir)

    def _perform(self, result=None):
        try:
            return super(_Handle, self).perform(result)
        except librepo.LibrepoException as exc:
            source = self.metalinkurl or self.mirrorlisturl or \
                     ', '.join(self.urls)
            raise _DetailedLibrepoError(exc, source)


class _NullKeyImport(dnf.callback.KeyImport):
    def _confirm(self, _keyinfo):
        return True


class Metadata(object):
    def __init__(self, res, handle):
        self.fresh = False  # :api
        self._repo_dct = res.yum_repo
        self._repomd_dct = res.yum_repomd
        self._priv_mirrors = handle.mirrors[:]

    @property
    def _age(self):
        return self._file_age('primary')

    @property
    def _comps_fn(self):
        return self._repo_dct.get("group_gz") or self._repo_dct.get("group")

    @property
    def _content_tags(self):
        return self._repomd_dct.get('content_tags')

    @property
    def _distro_tags(self):
        pairs = self._repomd_dct.get('distro_tags', [])
        return {k: v for (k, v) in pairs}

    def _file_age(self, what):
        return time.time() - self._file_timestamp(what)

    def _file_timestamp(self, what):
        try:
            return dnf.util.file_timestamp(self._repo_dct[what])
        except OSError as e:
            raise dnf.exceptions.MetadataError(ucd(e))

    @property
    def _filelists_fn(self):
        return self._repo_dct.get('filelists')

    @property
    def _mirrors(self):
        return self._priv_mirrors

    @property
    def _md_timestamp(self):
        """Gets the highest timestamp of all metadata types."""
        timestamps = [content.get('timestamp')
                      for (_, content) in self._repomd_dct.items()
                      if isinstance(content, dict)]
        return max(timestamps)

    @property
    def _presto_fn(self):
        return self._repo_dct.get('prestodelta')

    @property
    def _primary_fn(self):
        return self._repo_dct.get('primary')

    def _reset_age(self):
        dnf.util.touch(self._primary_fn, no_create=True)

    @property
    def _repomd_fn(self):
        return self._repo_dct.get('repomd')

    @property
    def _revision(self):
        return self._repomd_dct.get('revision')

    @property
    def _timestamp(self):
        return self._file_timestamp('primary')

    @property
    def _updateinfo_fn(self):
        return self._repo_dct.get('updateinfo')


class PackagePayload(dnf.callback.Payload):
    def __init__(self, pkg, progress):
        super(PackagePayload, self).__init__(progress)
        self.pkg = pkg

    @dnf.util.log_method_call(functools.partial(logger.log, dnf.logging.SUBDEBUG))
    def _end_cb(self, cbdata, lr_status, msg):
        """End callback to librepo operation."""
        status = dnf.callback.STATUS_FAILED
        if msg is None:
            status = dnf.callback.STATUS_OK
        elif msg.startswith('Not finished'):
            return
        elif lr_status == librepo.TRANSFER_ALREADYEXISTS:
            status = dnf.callback.STATUS_ALREADY_EXISTS

        self.progress.end(self, status, msg)

    @dnf.util.log_method_call(functools.partial(logger.log, dnf.logging.SUBDEBUG))
    def _mirrorfail_cb(self, cbdata, err, url):
        self.progress.end(self, dnf.callback.STATUS_MIRROR, err)

    def _progress_cb(self, cbdata, total, done):
        try:
            self.progress.progress(self, done)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            except_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.critical(''.join(except_list))

    @property
    def _full_size(self):
        return self.download_size

    def _librepo_target(self):
        pkg = self.pkg
        pkgdir = pkg.repo.pkgdir
        dnf.util.ensure_dir(pkgdir)

        target_dct = {
            'handle': pkg.repo._get_handle(),
            'dest': pkgdir,
            'resume': True,
            'cbdata': self,
            'progresscb': self._progress_cb,
            'endcb': self._end_cb,
            'mirrorfailurecb': self._mirrorfail_cb,
        }
        target_dct.update(self._target_params())

        return librepo.PackageTarget(**target_dct)


class RPMPayload(PackagePayload):

    def __str__(self):
        return os.path.basename(self.pkg.location)

    def _target_params(self):
        pkg = self.pkg
        ctype, csum = pkg.returnIdSum()
        ctype_code = getattr(librepo, ctype.upper(), librepo.CHECKSUM_UNKNOWN)
        if ctype_code == librepo.CHECKSUM_UNKNOWN:
            logger.warning(_("unsupported checksum type: %s"), ctype)

        return {
            'relative_url': pkg.location,
            'checksum_type': ctype_code,
            'checksum': csum,
            'expectedsize': pkg.downloadsize,
            'base_url': pkg.baseurl,
        }

    @property
    def download_size(self):
        """Total size of the download."""
        return self.pkg.downloadsize


class RemoteRPMPayload(PackagePayload):

    def __init__(self, remote_location, conf, handle, progress):
        super(RemoteRPMPayload, self).__init__("unused_object", progress)
        self.remote_location = remote_location
        self.remote_size = 0
        self.handle = handle
        self.conf = conf
        s = (self.conf.releasever or "") + self.conf.substitutions.get('basearch')
        digest = hashlib.sha256(s.encode('utf8')).hexdigest()[:16]
        repodir = "commandline-" + digest
        self.pkgdir = os.path.join(self.conf.cachedir, repodir, "packages")
        dnf.util.ensure_dir(self.pkgdir)
        self.local_path = os.path.join(self.pkgdir, self.__str__())

    def __str__(self):
        return os.path.basename(self.remote_location)

    def _progress_cb(self, cbdata, total, done):
        self.remote_size = total
        try:
            self.progress.progress(self, done)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            except_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.critical(''.join(except_list))

    def _librepo_target(self):
        target_dct = {
            'handle': self.handle,
            'relative_url': os.path.basename(self.remote_location),
            'dest': self.pkgdir,
            'resume': True,
            'cbdata': self,
            'progresscb': self._progress_cb,
            'endcb': self._end_cb,
            'mirrorfailurecb': self._mirrorfail_cb,
            'base_url': os.path.dirname(self.remote_location),
        }

        return librepo.PackageTarget(**target_dct)

    @property
    def download_size(self):
        """Total size of the download."""
        return self.remote_size


class MDPayload(dnf.callback.Payload):

    def __str__(self):
        if dnf.pycomp.PY3:
            return self._text
        else:
            return self._text.encode('utf-8')

    def __unicode__(self):
        return self._text

    def _progress_cb(self, cbdata, total, done):
        self._download_size = total
        self.progress.progress(self, done)

    def _fastestmirror_cb(self, cbdata, stage, data):
        if stage == librepo.FMSTAGE_DETECTION:
            # pinging mirrors, this might take a while
            msg = _('determining the fastest mirror (%d hosts).. ') % data
            self.fm_running = True
        elif stage == librepo.FMSTAGE_STATUS and self.fm_running:
            # done.. report but ignore any errors
            msg = 'error: %s\n' % data if data else 'done.\n'
        else:
            return
        self.progress.message(msg)

    def _mirror_failure_cb(self, cbdata, msg, url, metadata):
        msg = 'error: %s (%s).' % (msg, url)
        logger.debug(msg)

    @property
    def download_size(self):
        return self._download_size

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, progress):
        if progress is None:
            progress = dnf.callback.NullDownloadProgress()
        self._progress = progress

    def start(self, text):
        self._text = text
        self._download_size = 0
        self.progress.start(1, 1)

    def end(self):
        self._download_size = 0
        self.progress.end(self, None, None)


# use the local cache even if it's expired. download if there's no cache.
SYNC_LAZY = 1
 # use the local cache, even if it's expired, never download.
SYNC_ONLY_CACHE = 2
# try the cache, if it is expired download new md.
SYNC_TRY_CACHE = 3


class Repo(dnf.conf.RepoConf):
    # :api
    DEFAULT_SYNC = SYNC_TRY_CACHE

    def __init__(self, name=None, parent_conf=None):
        # :api
        super(Repo, self).__init__(section=name, parent=parent_conf)
        self._repofile = None
        self._expired = False
        self._pkgdir = None
        self._md_pload = MDPayload(dnf.callback.NullDownloadProgress())
        self._key_import = _NullKeyImport()
        self.metadata = None  # :api
        self._sync_strategy = self.DEFAULT_SYNC
        self._substitutions = dnf.conf.substitutions.Substitutions()
        self._max_mirror_tries = 0  # try them all
        self._handle = None
        self._hawkey_repo = self._init_hawkey_repo()
        self._check_config_file_age = parent_conf.check_config_file_age \
            if parent_conf is not None else True

    @property
    def id(self):
        # :api
        return self._section

    @property
    def repofile(self):
        # :api
        return self._repofile

    @repofile.setter
    def repofile(self, value):
        self._repofile = value

    @property
    def _cachedir(self):
        s = self.metalink or self.mirrorlist or \
            (self.baseurl and self.baseurl[0]) or self.id
        digest = hashlib.sha256(s.encode('utf8')).hexdigest()[:16]
        repodir = "%s-%s" % (self.id, digest)
        return os.path.join(self.basecachedir, repodir)

    @property
    def _filelists_fn(self):
        return self.metadata._filelists_fn

    @property
    def _local(self):
        if self.metalink or self.mirrorlist:
            return False
        if self.baseurl[0].startswith('file://'):
            return True
        return False

    @property
    def _md_lazy(self):
        return self._sync_strategy == SYNC_LAZY

    @_md_lazy.setter
    def _md_lazy(self, val):
        """Set whether it is fine to use stale metadata."""
        if val:
            self._sync_strategy = SYNC_LAZY
        else:
            self._sync_strategy = SYNC_TRY_CACHE

    @property
    def _md_only_cached(self):
        return self._sync_strategy == SYNC_ONLY_CACHE

    @_md_only_cached.setter
    def _md_only_cached(self, val):
        """Force using only the metadata the repo has in the local cache."""
        if val:
            self._sync_strategy = SYNC_ONLY_CACHE
        else:
            self._sync_strategy = SYNC_TRY_CACHE

    @property
    def _md_expired(self):
        """Return whether the cached metadata is expired."""
        try:
            exp_remaining = self._metadata_expire_in()[1]
            return False if exp_remaining is None else exp_remaining <= 0
        except dnf.exceptions.MetadataError:
            return False

    @property
    def _metadata_dir(self):
        return os.path.join(self._cachedir, _METADATA_RELATIVE_DIR)

    @property
    def _metalink_path(self):
        return _priv_metalink_path(self._cachedir)

    @property
    def _mirrorlist_path(self):
        return _priv_mirrorlist_path(self._cachedir)

    @property
    def pkgdir(self):
        # :api
        if self._local:
            return dnf.util.strip_prefix(self.baseurl[0], 'file://')
        if self._pkgdir is not None:
            return self._pkgdir
        return os.path.join(self._cachedir, _PACKAGES_RELATIVE_DIR)

    @pkgdir.setter
    def pkgdir(self, val):
        # :api
        self._pkgdir = val

    @property
    def _presto_fn(self):
        return self.metadata._presto_fn

    @property
    def _primary_fn(self):
        return self.metadata._primary_fn

    @property
    def _pubring_dir(self):
        return os.path.join(self._cachedir, 'pubring')

    @property
    def _repomd_fn(self):
        return self.metadata._repomd_fn

    @property
    def _updateinfo_fn(self):
        return self.metadata._updateinfo_fn

    def __lt__(self, other):
        return self.id < other.id

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.id)

    def __setattr__(self, name, value):
        super(Repo, self).__setattr__(name, value)
        if name == 'cost':
            self._hawkey_repo.cost = self.cost
        if name == 'priority':
            self._hawkey_repo.priority = self.priority

    def _handle_load(self, handle):
        if not self.repo_gpgcheck:
            return self._handle_load_core(handle)
        try:
            return self._handle_load_with_pubring(handle)
        except _DetailedLibrepoError as e:
            if e.librepo_code != librepo.LRE_BADGPG:
                raise
            dnf.util.clear_dir(handle.destdir)
            dnf.crypto.import_repo_keys(self)
            return self._handle_load_with_pubring(handle)

    def _handle_load_core(self, handle):
        if handle.progresscb:
            self._md_pload.start(self.name or self.id or 'unknown')
        result = handle._perform()
        if handle.progresscb:
            self._md_pload.end()

        return Metadata(result, handle)

    def _handle_load_with_pubring(self, handle):
        with dnf.crypto.pubring_dir(self._pubring_dir):
            return self._handle_load_core(handle)

    def _handle_new_local(self, destdir):
        return _Handle._new_local(self._substitutions, self.repo_gpgcheck,
                                  self._max_mirror_tries, destdir)

    def _handle_new_pkg_download(self):
        return self._handle_new_remote(self.pkgdir, mirror_setup=False)

    def _handle_new_remote(self, destdir, mirror_setup=True):
        h = _Handle(self.repo_gpgcheck, self._max_mirror_tries,
                    self.max_parallel_downloads)
        h.varsub = _subst2tuples(self._substitutions)
        h.destdir = destdir
        self._set_ip_resolve(h)

        # setup mirror URLs
        mirrorlist = self.metalink or self.mirrorlist
        if mirrorlist:
            h.hmfcb = self._md_pload._mirror_failure_cb
            if mirror_setup:
                if self.metalink:
                    h.setopt(librepo.LRO_METALINKURL, mirrorlist)
                else:
                    h.setopt(librepo.LRO_MIRRORLISTURL, mirrorlist)
                    # YUM-DNF compatibility hack. YUM guessed by content of keyword "metalink" if
                    # mirrorlist is really mirrorlist or metalink)
                    if 'metalink' in mirrorlist:
                        h.setopt(librepo.LRO_METALINKURL, mirrorlist)
                h.setopt(librepo.LRO_FASTESTMIRROR, self.fastestmirror)
                h.setopt(librepo.LRO_FASTESTMIRRORCACHE,
                         os.path.join(self.basecachedir, 'fastestmirror.cache'))
            else:
                # use already resolved mirror list
                h.setopt(librepo.LRO_URLS, self.metadata._mirrors)
        elif self.baseurl:
            h.setopt(librepo.LRO_URLS, self.baseurl)
        else:
            msg = _('Cannot find a valid baseurl for repo: %s') % self.id
            raise dnf.exceptions.RepoError(msg)

        # setup username/password if needed
        if self.username:
            h.setopt(librepo.LRO_USERPWD, _user_pass_str(self.username, self.password))

        # setup ssl stuff
        if self.sslcacert:
            h.setopt(librepo.LRO_SSLCACERT, self.sslcacert)
        if self.sslclientcert:
            h.setopt(librepo.LRO_SSLCLIENTCERT, self.sslclientcert)
        if self.sslclientkey:
            h.setopt(librepo.LRO_SSLCLIENTKEY, self.sslclientkey)

        # setup download progress
        h.progresscb = self._md_pload._progress_cb
        self._md_pload.fm_running = False
        h.fastestmirrorcb = self._md_pload._fastestmirror_cb

        # apply repo options
        h.lowspeedlimit = self.minrate
        maxspeed = self.throttle if isinstance(self.throttle, int) \
            else int(self.bandwidth * self.throttle)
        if maxspeed != 0 and self.minrate > maxspeed:
            raise dnf.exceptions.Error(_("Maximum download speed is lower than minimum. "
                                         "Please change configuration of minrate or throttle"))
        h.maxspeed = maxspeed
        h.setopt(librepo.LRO_PROXYAUTH, True)
        h.proxy = self.proxy
        if self.timeout > 0:
            h.connecttimeout = self.timeout
            h.lowspeedtime = self.timeout
        else:
            h.connecttimeout = None
            h.lowspeedtime = None
        h.proxyuserpwd = _user_pass_str(self.proxy_username, self.proxy_password)
        h.sslverifypeer = h.sslverifyhost = self.sslverify
        return h

    def _init_hawkey_repo(self):
        hrepo = hawkey.Repo(self.id)
        hrepo.cost = self.cost
        hrepo.priority = self.priority
        return hrepo

    def _replace_metadata(self, handle):
        dnf.util.ensure_dir(self._cachedir)
        dnf.util.rm_rf(self._metadata_dir)
        dnf.util.rm_rf(self._metalink_path)
        dnf.util.rm_rf(self._mirrorlist_path)
        shutil.move(handle._metadata_dir, self._metadata_dir)
        if handle.metalink:
            shutil.move(handle._metalink_path, self._metalink_path)
        elif handle.mirrorlist:
            shutil.move(handle._mirrorlist_path, self._mirrorlist_path)

    def _reset_metadata_expired(self):
        if self._expired:
            # explicitly requested expired state
            return
        self._expired = self.metadata._age >= self.metadata_expire
        if self.metadata_expire == -1:
            self._expired = False

    def _set_ip_resolve(self, handle):
        if self.ip_resolve == 'ipv4':
            handle.setopt(librepo.LRO_IPRESOLVE, librepo.IPRESOLVE_V4)
        elif self.ip_resolve == 'ipv6':
            handle.setopt(librepo.LRO_IPRESOLVE, librepo.IPRESOLVE_V6)

    def _try_cache(self):
        """Tries to load metadata from the local cache.

        Correctly sets self._expired.

        Returns True if we got any (even expired) metadata locally.

        """
        assert self.metadata is None
        handle = self._handle_new_local(self._cachedir)
        try:
            self.metadata = self._handle_load(handle)
        except (_DetailedLibrepoError, IOError):
            return False
        self._reset_metadata_expired()
        return True

    def _try_revive_by_metalink(self):
        """Use metalink to check whether our metadata are still current."""
        repomd_fn = self.metadata._repo_dct['repomd']
        with dnf.util.tmpdir() as tmpdir, open(repomd_fn) as repomd:
            handle = self._handle_new_remote(tmpdir)
            handle.fetchmirrors = True
            handle._perform()
            if handle.metalink is None:
                logger.debug(_("reviving: repo '%s' skipped, no metalink."), self.id)
                return False
            hashes = handle.metalink['hashes']
            hashes = [hsh_val for hsh_val in hashes
                      if hsh_val[0] in _RECOGNIZED_CHKSUMS]
            if len(hashes) < 1:
                logger.debug(_("reviving: repo '%s' skipped, no usable hash."),
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
                    logger.debug(_("reviving: failed for '%s', mismatched %s sum."),
                                 self.id, algo)
                    return False
        logger.debug(_("reviving: '%s' can be revived - metalink checksums match."), self.id)
        return True

    def _try_revive_by_repomd(self):
        """Use repomd to check whether our metadata are still current."""
        repomd_fn = self.metadata._repo_dct['repomd']
        with dnf.util.tmpdir() as tmpdir, open(repomd_fn) as repomd:
            handle = self._handle_new_remote(tmpdir)
            handle.yumdlist = librepo.YUM_REPOMDONLY
            with dnf.crypto.pubring_dir(self._pubring_dir):
                result = handle._perform()
            fresh_repomd_fn = result.rpmmd_repo['repomd']
            with open(fresh_repomd_fn) as fresh_repomd:
                if repomd.read() != fresh_repomd.read():
                    logger.debug(_("reviving: failed for '%s', mismatched repomd."), self.id)
                    return False
        logger.debug(_("reviving: '%s' can be revived - repomd matches."), self.id)
        return True

    def _try_revive(self):
        """Use metalink to check whether our metadata are still current."""
        if not self.metadata:
            return False

        if self.metalink:
            return self._try_revive_by_metalink()
        else:
            return self._try_revive_by_repomd()

    def _configure_from_options(self, opts):
        if getattr(opts, 'cacheonly', None):
            self._md_only_cached = True
        super(Repo, self)._configure_from_options(opts)

    def disable(self):
        # :api
        self.enabled = False

    def enable(self):
        # :api
        self.enabled = True

    def _get_handle(self):
        """Returns a librepo handle, set as per the repo options

        Note that destdir is None, and the handle is cached.
        """
        if not self._handle:
            self._handle = self._handle_new_remote(None)
        return self._handle

    def load(self):
        # :api
        """Load the metadata for this repo.

        Depending on the configuration and the age and consistence of data
        available on the disk cache, either loads the metadata from the cache or
        downloads them from the mirror, baseurl or metalink.

        This method will by default not try to refresh already loaded data if
        called repeatedly.

        Returns True if this call to load() caused a fresh metadata download.

        """
        if self.metadata or self._try_cache():
            if self.metadata_expire < 0 \
                    and self._check_config_file_age \
                    and self.repofile \
                    and dnf.util.file_age(self.repofile) < self.metadata._age:
                self._md_expire_cache()
            if self._sync_strategy in (SYNC_ONLY_CACHE, SYNC_LAZY) or \
               not self._expired:
                logger.debug(_('repo: using cache for: %s'), self.id)
                return False
        if self._sync_strategy == SYNC_ONLY_CACHE:
            msg = _("Cache-only enabled but no cache for '%s'") % self.id
            raise dnf.exceptions.RepoError(msg)
        try:
            if self._try_revive():
                # the expired metadata still reflect the origin:
                self.metadata._reset_age()
                self._expired = False
                return True

            with dnf.util.tmpdir() as tmpdir:
                handle = self._handle_new_remote(tmpdir)
                msg = _('repo: downloading from remote: %s, %s')
                logger.log(dnf.logging.DDEBUG, msg, self.id, handle)
                self._handle_load(handle)
                # override old md with the new ones:
                self._replace_metadata(handle)

            # get md from the cache now:
            handle = self._handle_new_local(self._cachedir)
            self.metadata = self._handle_load(handle)
            self.metadata.fresh = True
        except _DetailedLibrepoError as e:
            dmsg = _("Cannot download '%s': %s.")
            logger.log(dnf.logging.DEBUG, dmsg, e.source_url, e.librepo_msg)
            msg = _("Failed to synchronize cache for repo '%s'") % (self.id)
            raise dnf.exceptions.RepoError(msg)
        self._expired = False
        return True

    def _md_expire_cache(self):
        """Mark whatever is in the current cache expired.

        This repo instance will alway try to fetch a fresh metadata after this
        method is called.

        """
        self._expired = True

    def _metadata_expire_in(self):
        """Get the number of seconds after which the cached metadata will expire.

        Returns a tuple, boolean whether there even is cached metadata and the
        number of seconds it will expire in. Negative number means the metadata
        has expired already, None that it never expires.

        """
        if not self.metadata:
            self._try_cache()
        if self.metadata:
            if self.metadata_expire == -1:
                return True, None
            expiration = self.metadata_expire - self.metadata._age
            if self._expired:
                expiration = min(0, expiration)
            return True, expiration
        return False, 0

    def _set_key_import(self, key_import):
        self._key_import = key_import

    def set_progress_bar(self, progress):
        # :api
        self._md_pload.progress = progress

    def _valid(self):
        if len(self.baseurl) == 0 and not self.metalink and not self.mirrorlist:
            return _("Repository %s has no mirror or baseurl set.") % self.id
        supported_types = ['rpm-md', 'rpm', 'repomd', 'rpmmd', 'yum', 'YUM']
        if self.type and self.type not in supported_types:
            return _("Repository '{}' has unsupported type: 'type={}', skipping.").format(
                self.id, self.type)
        return None
