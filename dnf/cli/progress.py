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

from __future__ import unicode_literals
from dnf.cli.format import format_number, format_time
from dnf.cli.term import _term_width
from dnf.pycomp import unicode
from time import time

import sys
import dnf.callback
import dnf.util


class MultiFileProgressMeter(dnf.callback.DownloadProgress):
    """Multi-file download progress meter"""

    STATUS_2_STR = {
        dnf.callback.STATUS_FAILED : 'FAILED',
        dnf.callback.STATUS_ALREADY_EXISTS : 'SKIPPED',
        dnf.callback.STATUS_MIRROR : 'MIRROR',
        dnf.callback.STATUS_DRPM : 'DRPM',
    }

    def __init__(self, fo=sys.stderr, update_period=0.3, tick_period=1.0, rate_average=5.0):
        """Creates a new progress meter instance

        update_period -- how often to update the progress bar
        tick_period -- how fast to cycle through concurrent downloads
        rate_average -- time constant for average speed calculation
        """
        self.fo = fo
        self.update_period = update_period
        self.tick_period = tick_period
        self.rate_average = rate_average

    def message(self, msg):
        dnf.util._terminal_messenger('write_flush', msg, self.fo)

    def start(self, total_files, total_size):
        self.total_files = total_files
        self.total_size = total_size

        # download state
        self.done_files = 0
        self.done_size = 0
        self.state = {}
        self.active = []

        # rate averaging
        self.last_time = 0
        self.last_size = 0
        self.rate = None

    def progress(self, payload, done):
        now = time()
        text = unicode(payload)
        total = int(payload.download_size)
        done = int(done)

        # update done_size
        if text not in self.state:
            self.state[text] = now, 0
            self.active.append(text)
        start, old = self.state[text]
        self.state[text] = start, done
        self.done_size += done - old

        # update screen if enough time has elapsed
        if now - self.last_time > self.update_period:
            if total > self.total_size:
                self.total_size = total
            self._update(now)

    def _update(self, now):
        if self.last_time:
            delta_time = now - self.last_time
            delta_size = self.done_size - self.last_size
            if delta_time > 0 and delta_size > 0:
                # update the average rate
                rate = delta_size / delta_time
                if self.rate is not None:
                    weight = min(delta_time/self.rate_average, 1)
                    rate = rate*weight + self.rate*(1 - weight)
                self.rate = rate
        self.last_time = now
        self.last_size = self.done_size

        # pick one of the active downloads
        text = self.active[int(now/self.tick_period) % len(self.active)]
        if self.total_files > 1:
            n = '%d' % (self.done_files + 1)
            if len(self.active) > 1:
                n += '-%d' % (self.done_files + len(self.active))
            text = '(%s/%d): %s' % (n, self.total_files, text)

        # average rate, total done size, estimated remaining time
        msg = ' %5sB/s | %5sB %9s ETA\r' % (
            format_number(self.rate) if self.rate else '---  ',
            format_number(self.done_size),
            format_time((self.total_size - self.done_size) / self.rate) if self.rate else '--:--')
        left = _term_width() - len(msg)
        bl = (left - 7)//2
        if bl > 8:
            # use part of the remaining space for progress bar
            pct = self.done_size*100 // self.total_size
            n, p = divmod(self.done_size*bl*2 // self.total_size, 2)
            bar = '='*n + '-'*p
            msg = '%3d%% [%-*s]%s' % (pct, bl, bar, msg)
            left -= bl + 7
        self.message('%-*.*s%s' % (left, left, text, msg))

    def end(self, payload, status, err_msg):
        start = now = time()
        text = unicode(payload)
        size = int(payload.download_size)

        # update state
        if status in (dnf.callback.STATUS_MIRROR, dnf.callback.STATUS_DRPM):
            pass
        elif text in self.state:
            start, done = self.state.pop(text)
            self.active.remove(text)
            size -= done
            self.done_files += 1
            self.done_size += size
        elif status == dnf.callback.STATUS_ALREADY_EXISTS:
            self.done_files += 1
            self.done_size += size

        if status:
            # the error message, no trimming
            msg = '[%s] %s: ' % (self.STATUS_2_STR[status], text)
            left = _term_width() - len(msg) - 1
            msg = '%s%-*s\n' % (msg, left, err_msg)
        else:
            if self.total_files > 1:
                text = '(%d/%d): %s' % (self.done_files, self.total_files, text)

            # average rate, file size, download time
            tm = max(now - start, 0.001)
            msg = ' %5sB/s | %5sB %9s    \n' % (
                format_number(float(done) / tm),
                format_number(done),
                format_time(tm))
            left = _term_width() - len(msg)
            msg = '%-*.*s%s' % (left, left, text, msg)
        self.message(msg)

        # now there's a blank line. fill it if possible.
        if self.active:
            self._update(now)
