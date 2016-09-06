# lock.py
# DNF Locking Subsystem.
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
from dnf.exceptions import ProcessLockError, ThreadLockError, LockError
from dnf.i18n import _
from dnf.yum import misc
import dnf.logging
import dnf.util
import errno
import hashlib
import logging
import os
import threading
import time

logger = logging.getLogger("dnf")

def _fit_lock_dir(dir_):
    if not dnf.util.am_i_root():
        # for regular users the best we currently do is not to clash with
        # another DNF process of the same user. Since dir_ is quite definitely
        # not writable for us, yet significant, use its hash:
        hexdir = hashlib.md5(dir_.encode('utf-8')).hexdigest()
        dir_ = os.path.join(misc.getCacheDir(), 'locks', hexdir)
    return dir_

def build_download_lock(cachedir, exit_on_lock):
    return ProcessLock(os.path.join(_fit_lock_dir(cachedir), 'download_lock.pid'),
                       'cachedir', not exit_on_lock)

def build_metadata_lock(cachedir, exit_on_lock):
    return ProcessLock(os.path.join(_fit_lock_dir(cachedir), 'metadata_lock.pid'),
                       'metadata', not exit_on_lock)


def build_rpmdb_lock(persistdir, exit_on_lock):
    return ProcessLock(os.path.join(_fit_lock_dir(persistdir), 'rpmdb_lock.pid'),
                       'RPMDB', not exit_on_lock)


class ProcessLock(object):
    def __init__(self, target, description, blocking=False):
        self.blocking = blocking
        self.count = 0
        self.description = description
        self.target = target
        self.thread_lock = threading.RLock()

    def _lock_thread(self):
        if not self.thread_lock.acquire(blocking=False):
            msg = '%s already locked by a different thread' % self.description
            raise ThreadLockError(msg)
        self.count += 1

    def _try_lock(self):
        pid = str(os.getpid()).encode('utf-8')
        try:
            fd = os.open(self.target, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)
            os.write(fd, pid)
            os.close(fd)
            return True
        except OSError as e:
            if e.errno == errno.EEXIST:   # File exists
                return False
            raise

    def _try_read_lock(self):
        try:
            with open(self.target, 'r') as f:
                return int(f.readline())
        except IOError:
            return -1
        except ValueError:
            time.sleep(2)
            try:
                with open(self.target, 'r') as f:
                    return int(f.readline())
            except IOError:
                return -1
            except ValueError:
                msg = _('Malformed lock file found: %s.\n'
                        'Ensure no other dnf process is running and '
                        'remove the lock file manually or run '
                        'systemd-tmpfiles --remove dnf.conf.' % (self.target))
                raise LockError(msg)

    def _try_unlink(self):
        try:
            os.unlink(self.target)
            return True
        except OSError:
            return False

    def _unlock_thread(self):
        self.count -= 1
        self.thread_lock.release()

    def __enter__(self):
        dnf.util.ensure_dir(os.path.dirname(self.target))
        self._lock_thread()
        inform = True
        prev_pid = 0
        while not self._try_lock():
            pid = self._try_read_lock()
            if pid == -1:
                # already removed by other process
                continue
            if pid == os.getpid():
                # already locked by this process
                return
            if not os.access('/proc/%d/stat' % pid, os.F_OK):
                # locked by a dead process
                self._try_unlink()
                continue
            if not self.blocking:
                self._unlock_thread()
                msg = '%s already locked by %d' % (self.description, pid)
                raise ProcessLockError(msg, pid)
            if inform or prev_pid != pid:
                msg = _('Waiting for process with pid %d to finish.' % (pid))
                logger.info(msg)
                inform = False
                prev_pid = pid
            time.sleep(2)

    def __exit__(self, *exc_args):
        if self.count == 1:
            os.unlink(self.target)
        self._unlock_thread()
