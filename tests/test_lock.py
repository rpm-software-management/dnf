# Copyright (C) 2012-2016 Red Hat, Inc.
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

"""Unit test dnf.lock module.

Locking is very hard to cover reasonably with a unit test, this is more or less
just a sanity check.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.exceptions import ProcessLockError, ThreadLockError
from tests.support import mock

import dnf.lock
import dnf.pycomp
import dnf.util
import multiprocessing
import os
import re
import tests.support
import threading

class ConcurrencyMixin(object):
    def __init__(self, lock):
        self.lock = lock

    def run(self):
        try:
            with self.lock:
                pass
        except (ProcessLockError, ThreadLockError) as e:
            self.queue.put(e)

class OtherThread(ConcurrencyMixin, threading.Thread):
    def __init__(self, lock):
        ConcurrencyMixin.__init__(self, lock)
        threading.Thread.__init__(self)
        self.queue = dnf.pycomp.Queue(1)

class OtherProcess(ConcurrencyMixin, multiprocessing.Process):
    def __init__(self, lock):
        ConcurrencyMixin.__init__(self, lock)
        multiprocessing.Process.__init__(self)
        self.queue = multiprocessing.Queue(1)

TARGET = os.path.join(tests.support.USER_RUNDIR, 'unit-test.pid')


def build_lock(blocking=False):
    return dnf.lock.ProcessLock(TARGET, 'unit-tests', blocking)


class LockTest(tests.support.TestCase):
    def test_fit_lock_dir(self):
        orig = '/some'
        with mock.patch('dnf.util.am_i_root', return_value=True):
            self.assertEqual(dnf.lock._fit_lock_dir(orig), '/some')
        with mock.patch('dnf.util.am_i_root', return_value=False):
            dir_ = dnf.lock._fit_lock_dir(orig)
            match = re.match(
                r'/var/tmp/dnf-[^:]+-[^/]+/locks/8e58d9adbd213a8b602f30604a8875f2',
                dir_)
            self.assertTrue(match)


class ProcessLockTest(tests.support.TestCase):
    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(tests.support.USER_RUNDIR)

    def test_simple(self):
        l1 = build_lock()
        target = l1.target
        with l1:
            self.assertFile(target)
        self.assertPathDoesNotExist(target)

    def test_reentrance(self):
        l1 = build_lock()
        with l1:
            with l1:
                pass

    def test_another_process(self):
        l1 = build_lock()
        process = OtherProcess(l1)
        with l1:
            process.start()
            process.join()
        self.assertIsInstance(process.queue.get(), ProcessLockError)

    def test_another_process_blocking(self):
        l1 = build_lock(blocking=True)
        l2 = build_lock(blocking=True)
        process = OtherProcess(l1)
        target = l1.target
        with l2:
            process.start()
        process.join()
        self.assertEqual(process.queue.empty(), True)
        self.assertPathDoesNotExist(target)

    def test_another_thread(self):
        l1 = build_lock()
        thread = OtherThread(l1)
        with l1:
            thread.start()
            thread.join()
        self.assertIsInstance(thread.queue.get(), ThreadLockError)
