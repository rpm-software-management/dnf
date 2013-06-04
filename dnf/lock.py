# lock.py
# DNF Locking Subsystem.
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
from dnf.exceptions import ProcessLockError, ThreadLockError
import dnf.util
import os
import threading

class ProcessLock(object):
    def __init__(self, name):
        self.name = name
        self.thread_lock = threading.RLock()
        self.count = 0

    def _lock_thread(self):
        if not self.thread_lock.acquire(blocking=False):
            msg = '%s already locked by a different thread' % self.name
            raise ThreadLockError(msg)
        self.count += 1

    def _read_lock(self):
        with open(self._target, 'r') as f:
            return int(f.readline())

    @property
    @dnf.util.lazyattr('_tgt')
    def _target(self):
        fn = 'dnf-%s-lock.pid' % self.name
        if dnf.util.am_i_root():
            return os.path.join(dnf.const.RUNDIR, fn)
        dnf_homedir = os.path.join(dnf.util.home_dir(), '.dnf')
        dnf.util.ensure_dir(dnf_homedir)
        return os.path.join(dnf_homedir, fn)

    def _try_lock(self):
        pid = str(os.getpid())
        try:
            fd = os.open(self._target, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0644)
            os.write(fd, pid)
            os.close(fd)
            return True
        except OSError:
            return False

    def _unlock_thread(self):
        self.count -= 1
        self.thread_lock.release()

    def __enter__(self):
        self._lock_thread()
        if self._try_lock():
            return
        pid = self._read_lock()
        if pid == os.getpid():
            # already locked by this process
            return
        if not os.access('/proc/%d/stat' % pid, os.F_OK):
            # locked by a dead process
            os.unlink(self._target)
            if self._try_lock():
                return
        self._unlock_thread()
        msg = '%s already locked by %d' % (self.name, pid)
        raise ProcessLockError(msg, pid)

    def __exit__(self, *exc_args):
        if self.count == 1:
            os.unlink(self._target)
        self._unlock_thread()
