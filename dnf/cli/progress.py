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

class MultiFileProgressMeter(object):
    """Multi-file download progress meter"""

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

    def start(self, total_files, total_size):
        """Initialize the progress meter

        This must be called first to initialize the progress object.
        We should know the number of files and total size in advance.

        total_files -- the number of files to download
        total_size -- the total size of all files
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
        """Update the progress display

        text -- the file id
        total -- file total size (mostly ignored)
        done -- how much of this file is already downloaded
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
            pct = self.done_size*100 / self.total_size
            n, p = divmod(self.done_size*bl*2 // self.total_size, 2)
            bar = '='*n + '-'*p
            msg = '%3d%% [%-*s]%s' % (pct, bl, bar, msg)
            left -= bl + 7
        self.fo.write('%-*.*s%s' % (left, left, text, msg))
        self.fo.flush()

    def end(self, text, size, err):
        """Display a message that file has finished downloading

        text -- the file id
        size -- the file size
        err -- None if ok, error message otherwise
        """
        # update state
        start = now = time()
        if text in self.state:
            start, done = self.state.pop(text)
            self.active.remove(text)
            size -= done
        self.done_files += 1
        self.done_size += size

        if err:
            # the error message, no trimming
            msg = '[FAILED] %s: ' % text
            left = _term_width() - len(msg) - 1
            msg = '%s%-*s\n' % (msg, left, err)
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
        self.fo.write(msg)
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
        MultiFileProgressMeter.end(self, self.text, 0, None)
