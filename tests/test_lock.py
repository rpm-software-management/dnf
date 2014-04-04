# Copyright (C) 2012-2013  Red Hat, Inc.
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
import dnf.util
import multiprocessing
try:
    import queue
except ImportError:
    import Queue as queue
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
        self.queue = queue.Queue(1)

class OtherProcess(ConcurrencyMixin, multiprocessing.Process):
    def __init__(self, lock):
        ConcurrencyMixin.__init__(self, lock)
        multiprocessing.Process.__init__(self)
        self.queue = multiprocessing.Queue(1)

@mock.patch('dnf.const.USER_RUNDIR', tests.support.USER_RUNDIR)
class ProcessLockTest(tests.support.TestCase):
    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(tests.support.USER_RUNDIR)

    def test_simple(self):
        l1 = dnf.lock.ProcessLock("unit-test")
        target = l1._target
        with l1:
            self.assertFile(target)
        self.assertPathDoesNotExist(target)

    def test_reentrance(self):
        l1 = dnf.lock.ProcessLock("unit-test")
        with l1:
            with l1:
                pass

    def test_another_process(self):
        l1 = dnf.lock.ProcessLock("unit-test")
        process = OtherProcess(l1)
        with l1:
            process.start()
            process.join()
        self.assertIsInstance(process.queue.get(), ProcessLockError)

    def test_another_thread(self):
        l1 = dnf.lock.ProcessLock("unit-test")
        thread = OtherThread(l1)
        with l1:
            thread.start()
            thread.join()
        self.assertIsInstance(thread.queue.get(), ThreadLockError)

    def test_decorator(self):
        l1 = dnf.lock.ProcessLock("unit-test")

        @l1.decorator
        def decorated():
            self.assertEqual(l1.count, 1)

        decorated()
