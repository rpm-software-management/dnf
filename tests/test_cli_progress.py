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

import dnf.cli.progress
from tests import mock
import time
import unittest

class MockStdout:
    def __init__(self): self.out = []
    def write(self, s): self.out.append(s)
    def flush(self): pass

class ProgressTest(unittest.TestCase):
    def test_single(self):
        now = 1379406823.9
        fo = MockStdout()
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
             mock.patch('dnf.cli.progress.time', lambda: now):

            p = dnf.cli.progress.LibrepoCallbackAdaptor(fo)
            p.begin('dummy-text')
            for i in range(6):
                now += 1.0
                p.librepo_cb(None, 5, i)
                self.assertEquals(len(fo.out), i + 1) # always update
            p.end()

        # this is straightforward..
        self.assertEquals(fo.out, [
            'dummy-text  0% [          ] ---  B/s |   0  B     --:-- ETA\r',
            'dummy-text 20% [==        ] 1.0  B/s |   1  B     00:04 ETA\r',
            'dummy-text 40% [====      ] 1.0  B/s |   2  B     00:03 ETA\r',
            'dummy-text 60% [======    ] 1.0  B/s |   3  B     00:02 ETA\r',
            'dummy-text 80% [========  ] 1.0  B/s |   4  B     00:01 ETA\r',
            'dummy-text 99% [==========] 1.0  B/s |   5  B     00:00 ETA\r',
            'dummy-text                  1.0  B/s |   5  B     00:05    \n'])

    def test_multi(self):
        now = 1379406823.9
        fo = MockStdout()
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
             mock.patch('dnf.cli.progress.time', lambda: now):

            p = dnf.cli.progress.MultiFileProgressMeter(fo)
            p.start(2, 30)
            for i in range(11):
                p.progress('foo', 10.0, float(i))
                self.assertEquals(len(fo.out), i*2 + 1)
                if i == 10: p.end('foo')
                now += 0.5

                p.progress('bar', 20.0, float(i*2))
                self.assertEquals(len(fo.out), i*2 + 2 + (i == 10 and 2))
                if i == 10: p.end('bar')
                now += 0.5

        # check "end" events
        self.assertEquals([o for o in fo.out if o.endswith('\n')], [
'(1/2): foo                  1.0  B/s |  10  B     00:10    \n',
'(2/2): bar                  2.0  B/s |  20  B     00:10    \n'])
        # verify we estimated a sane rate (should be around 3 B/s)
        self.assertTrue(2.0 < p.rate < 4.0)
