# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

from __future__ import absolute_import
from __future__ import unicode_literals

import dnf.callback
import dnf.cli.progress
import dnf.pycomp

import tests.support
from tests.support import mock


class MockStdout(dnf.pycomp.StringIO):
    def visible_lines(self):
        lines = self.lines()
        last = len(lines) - 1
        return [l[:-1] for (i, l) in enumerate(lines)
                if l.endswith('\n') or i == last]

    def lines(self):
        return self.getvalue().splitlines(True)


class FakePayload(object):
    def __init__(self, string, size):
        self.string = string
        self._size = size

    def __str__(self):
        return self.string

    @property
    def download_size(self):
        return self._size


class ProgressTest(tests.support.TestCase):
    def test_single(self):
        now = 1379406823.9
        fo = MockStdout()
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
                mock.patch('dnf.cli.progress.time', lambda: now):

            p = dnf.cli.progress.MultiFileProgressMeter(fo)
            p.isatty = True
            pload = FakePayload('dummy-text', 5)
            p.start(1, 1)
            for i in range(6):
                now += 1.0
                p.progress(pload, i)
            p.end(pload, None, None)
        self.assertEqual(fo.lines(), [
            'dummy-text  0% [          ] ---  B/s |   0  B     --:-- ETA\r',
            'dummy-text 20% [==        ] 1.0  B/s |   1  B     00:04 ETA\r',
            'dummy-text 40% [====      ] 1.0  B/s |   2  B     00:03 ETA\r',
            'dummy-text 60% [======    ] 1.0  B/s |   3  B     00:02 ETA\r',
            'dummy-text 80% [========  ] 1.0  B/s |   4  B     00:01 ETA\r',
            'dummy-text100% [==========] 1.0  B/s |   5  B     00:00 ETA\r',
            'dummy-text                  1.0  B/s |   5  B     00:05    \n'])

    def test_mirror(self):
        fo = MockStdout()
        p = dnf.cli.progress.MultiFileProgressMeter(fo, update_period=-1)
        p.isatty = True
        p.start(1, 5)
        pload = FakePayload('foo', 5.0)
        now = 1379406823.9

        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
                mock.patch('dnf.cli.progress.time', lambda: now):
            p.progress(pload, 3)
            p.end(pload, dnf.callback.STATUS_MIRROR, 'Timeout.')
            p.progress(pload, 4)
        self.assertEqual(fo.visible_lines(), [
            '[MIRROR] foo: Timeout.                                     ',
            'foo        80% [========  ] ---  B/s |   4  B     --:-- ETA'])

    _REFERENCE_TAB = [
        ['(1-2/2): f  0% [          ] ---  B/s |   0  B     --:-- ETA'],
        ['(1-2/2): b 10% [=         ] 2.2  B/s |   3  B     00:12 ETA'],
        ['(1-2/2): f 20% [==        ] 2.4  B/s |   6  B     00:10 ETA'],
        ['(1-2/2): b 30% [===       ] 2.5  B/s |   9  B     00:08 ETA'],
        ['(1-2/2): f 40% [====      ] 2.6  B/s |  12  B     00:06 ETA'],
        ['(1-2/2): b 50% [=====     ] 2.7  B/s |  15  B     00:05 ETA'],
        ['(1-2/2): f 60% [======    ] 2.8  B/s |  18  B     00:04 ETA'],
        ['(1-2/2): b 70% [=======   ] 2.8  B/s |  21  B     00:03 ETA'],
        ['(1-2/2): f 80% [========  ] 2.9  B/s |  24  B     00:02 ETA'],
        ['(1-2/2): b 90% [========= ] 2.9  B/s |  27  B     00:01 ETA'],
        ['(1/2): foo                  1.0  B/s |  10  B     00:10    ',
         '(2/2): bar100% [==========] 2.9  B/s |  30  B     00:00 ETA']]

    def test_multi(self):
        now = 1379406823.9
        fo = MockStdout()
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
                mock.patch('dnf.cli.progress.time', lambda: now):

            p = dnf.cli.progress.MultiFileProgressMeter(fo)
            p.isatty = True
            p.start(2, 30)
            pload1 = FakePayload('foo', 10.0)
            pload2 = FakePayload('bar', 20.0)
            for i in range(11):
                p.progress(pload1, float(i))
                if i == 10:
                    p.end(pload1, None, None)
                now += 0.5

                p.progress(pload2, float(i * 2))
                self.assertEqual(self._REFERENCE_TAB[i], fo.visible_lines())
                if i == 10:
                    p.end(pload2, dnf.callback.STATUS_FAILED, 'some error')
                now += 0.5

        # check "end" events
        self.assertEqual(fo.visible_lines(), [
            '(1/2): foo                  1.0  B/s |  10  B     00:10    ',
            '[FAILED] bar: some error                                   '])
        self.assertTrue(2.0 < p.rate < 4.0)

    @mock.patch('dnf.cli.progress._term_width', return_value=40)
    def test_skip(self, mock_term_width):
        fo = MockStdout()
        p = dnf.cli.progress.MultiFileProgressMeter(fo)
        p.start(2, 30)
        pload1 = FakePayload('club', 20.0)
        p.end(pload1, dnf.callback.STATUS_ALREADY_EXISTS, 'already got')
        self.assertEqual(p.done_files, 1)
        self.assertEqual(p.done_size, pload1._size)
        self.assertEqual(fo.getvalue(),
                         '[SKIPPED] club: already got            \n')
