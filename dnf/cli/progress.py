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

import sys
from dnf.cli.format import format_number, format_time
from dnf.cli.term import _term_width
from time import time

class MultiFileProgressMeter:
    """Multi-file download progress meter
    """
    def __init__(self, fo=sys.stderr, update_period=0.3, tick_period=1.0, rate_average=5.0):
        """update_period: how often to update the progress bar
           tick_period: how fast to cycle through concurrent downloads
           rate_average: time constant for average speed calculation
        """
        self.fo = fo
        self.update_period = update_period
        self.tick_period = tick_period
        self.rate_average = rate_average

    def start(self, total_files, total_size):
        """This must be called first to initialize the progress object.
           We should know the number of files and total size in advance.
        """
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

    def progress(self, text, total, done):
        """This is the librepo "progresscb" callback entry point.
           text: the file identifier
           total/done: current progress
        """
        now = time()
        total = int(total)
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
        if self.last_time and now > self.last_time:
            # update the average rate
            delta = now - self.last_time
            rate = (self.done_size - self.last_size)/delta
            if self.rate is not None:
                weight = min(delta/self.rate_average, 1)
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
        bl = (left - 7)/2
        if bl > 8:
            # use part of the remaining space for progress bar
            pct = min(self.done_size*100 / self.total_size, 99)
            n, p = divmod(self.done_size*bl*2 / self.total_size, 2)
            msg = ' %2d%% [%-*s]%s' % (pct, bl, '='*n + '-'*p, msg)
            left -= bl + 7
        self.fo.write('%-*.*s%s' % (left, left, text, msg))
        self.fo.flush()

    def end(self, text):
        """This is the librepo "endcb" callback entry point.
           text: the file that just finished downloading
        """
        now = time()

        # update state
        tm, size = self.state.pop(text)
        tm = max(now - tm, 0.001)
        self.active.remove(text)
        self.done_files += 1

        # enumerate
        if self.total_files > 1:
            text = '(%d/%d): %s' % (self.done_files, self.total_files, text)

        # average rate, file size, download time
        msg = ' %5sB/s | %5sB %9s    \n' % (
            format_number(float(size)/tm),
            format_number(size),
            format_time(tm))
        left = _term_width() - len(msg)
        self.fo.write('%-*.*s%s' % (left, left, text, msg))
        self.fo.flush()

        # now there's a blank line. fill it if possible.
        if self.active:
            self._update(now)

class LibrepoCallbackAdaptor(MultiFileProgressMeter):
    """Use it as single-file progress, too
    """
    def begin(self, text):
        self.text = text
        MultiFileProgressMeter.start(self, 1, 1)

    def librepo_cb(self, data, total, done):
        MultiFileProgressMeter.progress(self, self.text, total, done)

    def end(self):
        MultiFileProgressMeter.end(self, self.text)
