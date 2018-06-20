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
import libdnf.conf as cfg

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

_PACKAGES_RELATIVE_DIR = "packages"
_MIRRORLIST_FILENAME = "mirrorlist"
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
    first_invalid = cfg.Repo.verifyId(repo_id)
    return None if first_invalid < 0 else first_invalid

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
        cfg.PackageTarget.downloadPackages(cfg.VectorPPackageTarget(targets), True)
    except librepo.LibrepoException as e:
        errs._fatal = e.args[1] or '<unspecified librepo error>'
    drpm.wait()

    # process downloading errors
    errs._recoverable = drpm.err.copy()
    for tgt in targets:
        err = tgt.getErr()
        if err is None or err.startswith('Not finished'):
            continue
        callbacks = tgt.getCallbacks()
        payload = callbacks.package_pload
        pkg = payload.pkg
        if err == _('Already downloaded'):
            errs._skipped.add(pkg)
            continue
        pkg.repo._repo.expire()
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


class _NullKeyImport(dnf.callback.KeyImport):
    def _confirm(self, _keyinfo):
        return True


class Metadata(object):
    def __init__(self, repo):
        self._repo = repo

    @property
    def fresh(self):
        # :api
        return self._repo.fresh()


class PackageTargetCallbacks(cfg.PackageTargetCB):
    def __init__(self, package_pload):
        super(PackageTargetCallbacks, self).__init__()
        self.package_pload = package_pload

    def end(self, status, msg):
        self.package_pload._end_cb(None, status, msg)
        return 0

    def progress(self, totalToDownload, downloaded):
        self.package_pload._progress_cb(None, totalToDownload, downloaded)
        # print("totalToDownload:", totalToDownload,  "downloaded:", downloaded)
        return 0

    def mirrorFailure(self, msg, url):
        self.package_pload._mirrorfail_cb(None, msg, url)
        # print("handlemirrorFailure:", msg, url, metadata)
        return 0


class PackagePayload(dnf.callback.Payload):
    def __init__(self, pkg, progress):
        super(PackagePayload, self).__init__(progress)
        self.callbacks = PackageTargetCallbacks(self)
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
            'dest': pkgdir,
            'resume': True,
            'cbdata': self,
            'progresscb': self._progress_cb,
            'endcb': self._end_cb,
            'mirrorfailurecb': self._mirrorfail_cb,
        }
        target_dct.update(self._target_params())

        return cfg.PackageTarget(pkg.repo._repo, target_dct['relative_url'], target_dct['dest'],
            target_dct['checksum_type'], target_dct['checksum'], target_dct['expectedsize'],
            target_dct['base_url'], target_dct['resume'], 0, 0, self.callbacks)


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

    def __init__(self, remote_location, conf, progress):
        super(RemoteRPMPayload, self).__init__("unused_object", progress)
        self.remote_location = remote_location
        self.remote_size = 0
        self.conf = conf
        s = (self.conf.releasever or "") + self.conf.substitutions.get('basearch')
        digest = hashlib.sha256(s.encode('utf8')).hexdigest()[:16]
        repodir = "commandline-" + digest
        self.pkgdir = os.path.join(self.conf.cachedir, repodir, "packages")
        dnf.util.ensure_dir(self.pkgdir)
        self.local_path = os.path.join(self.pkgdir, self.__str__().lstrip("/"))

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
        return cfg.PackageTarget(self.conf._config, os.path.basename(self.remote_location), self.pkgdir,
            0, None, 0, os.path.dirname(self.remote_location), True, 0, 0, self.callbacks)

    @property
    def download_size(self):
        """Total size of the download."""
        return self.remote_size


class MDPayload(dnf.callback.Payload):

    def __init__(self, progress):
        super(MDPayload, self).__init__(progress)
        self._text = ""
        self._download_size = 0
        self.fastest_mirror_running = False

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
            self.fastest_mirror_running = True
        elif stage == librepo.FMSTAGE_STATUS and self.fastest_mirror_running:
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
        self.progress.start(1, 0)

    def end(self):
        self._download_size = 0
        self.progress.end(self, None, None)


# use the local cache even if it's expired. download if there's no cache.
SYNC_LAZY = cfg.Repo.SyncStrategy_LAZY
 # use the local cache, even if it's expired, never download.
SYNC_ONLY_CACHE = cfg.Repo.SyncStrategy_ONLY_CACHE
# try the cache, if it is expired download new md.
SYNC_TRY_CACHE = cfg.Repo.SyncStrategy_TRY_CACHE


class RepoCallbacks(cfg.RepoCB):
    def __init__(self, md_pload):
        super(RepoCallbacks, self).__init__()
        self._md_pload = md_pload

    def start(self, what):
        self._md_pload.start(what)

    def end(self):
        self._md_pload.end()

    def progress(self, totalToDownload, downloaded):
        self._md_pload._progress_cb(None, totalToDownload, downloaded)
        # print("totalToDownload:", totalToDownload,  "downloaded:", downloaded)
        return 0

    def fastestMirror(self, stage, ptr):
        self._md_pload._fastestmirror_cb(None, stage, ptr)
        #print("fastestMirror:", stage)

    def handleMirrorFailure(self, msg, url, metadata):
        self._md_pload._mirror_failure_cb(None, msg, url, metadata)
        # print("handlemirrorFailure:", msg, url, metadata)
        return 0

class Repo(dnf.conf.RepoConf):
    # :api
    DEFAULT_SYNC = SYNC_TRY_CACHE

    def __init__(self, name=None, parent_conf=None):
        # :api
        super(Repo, self).__init__(section=name, parent=parent_conf)

        self._config.this.disown()  # _repo will be the owner of _config
        self._repo = cfg.Repo(name, self._config)

        self._md_pload = MDPayload(dnf.callback.NullDownloadProgress())
        self._callbacks = RepoCallbacks(self._md_pload)
        self._callbacks.this.disown()  # _repo will be the owner of callbacks
        self._repo.setCallbacks(self._callbacks)

        self._pkgdir = None
        self._key_import = _NullKeyImport()
        self.metadata = None  # :api
        self._repo.setSyncStrategy(self.DEFAULT_SYNC)
        self._substitutions = dnf.conf.substitutions.Substitutions()
        self._hawkey_repo = self._init_hawkey_repo()
        self._check_config_file_age = parent_conf.check_config_file_age \
            if parent_conf is not None else True

    @property
    def id(self):
        # :api
        return self._repo.getId()

    @property
    def repofile(self):
        # :api
        return self._repo.getRepoFilePath()

    @repofile.setter
    def repofile(self, value):
        self._repo.setRepoFilePath(value)

    @property
    def pkgdir(self):
        # :api
        if self._repo.isLocal():
            return dnf.util.strip_prefix(self.baseurl[0], 'file://')
        if self._pkgdir is not None:
            return self._pkgdir
        return os.path.join(self._repo.getCachedir(), _PACKAGES_RELATIVE_DIR)

    @pkgdir.setter
    def pkgdir(self, val):
        # :api
        self._pkgdir = val

    @property
    def _pubring_dir(self):
        return os.path.join(self._repo.getCachedir(), 'pubring')

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

    def _init_hawkey_repo(self):
        hrepo = hawkey.Repo(self.id)
        hrepo.cost = self.cost
        hrepo.priority = self.priority
        return hrepo

    def disable(self):
        # :api
        self._repo.disable()

    def enable(self):
        # :api
        self._repo.enable()

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
        self._repo.load()
        self.metadata = Metadata(self._repo)

    def _metadata_expire_in(self):
        """Get the number of seconds after which the cached metadata will expire.

        Returns a tuple, boolean whether there even is cached metadata and the
        number of seconds it will expire in. Negative number means the metadata
        has expired already, None that it never expires.

        """
        if not self.metadata:
            self._repo.loadCache()
        if self.metadata:
            if self.metadata_expire == -1:
                return True, None
            expiration = self._repo.getExpiresIn()
            if self._repo.isExpired():
                expiration = min(0, expiration)
            return True, expiration
        return False, 0

    def _set_key_import(self, key_import):
        self._key_import = key_import

    def set_progress_bar(self, progress):
        # :api
        self._md_pload.progress = progress
