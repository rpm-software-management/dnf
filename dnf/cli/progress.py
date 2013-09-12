# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys, os
from time import time
from dnf.cli.output import YumOutput
from dnf.cli.term import _term_width
format_number = YumOutput.format_number
format_time = YumOutput.format_time

class MultiProgressMeter:
    """Since downloads from multiple repositories run concurrently
       there's no repo-local progress callback
    """
    def __init__(self, total_files, total_size):
        # const
        self.fo = sys.stdout
        self.total_files = int(total_files)
        self.total_size = int(total_size)
        # downloading state
        self.done_files = 0
        self.done_size = 0
        self.state = {}
        self.meters = []
        self.started = {}
        # update timer
        self.last_time = 0
        self.last_size = 0
        self.rate = 0
        # ticker
        self.index_time = 0
        self.index = 0

    def __call__(self, text, total, done):
        now = time()
        total = int(total)
        done = int(done)
        # update the total done size
        if text not in self.state:
            self.state[text] = 0
            self.meters.append(text)
            self.started[text] = now
        delta = done - self.state[text]
        blank = False
        if delta > 0:
            self.done_size += delta
            self.state[text] = done
            if done == total:
                self.done_files += 1
                self.meters.remove(text)
                tm = now - self.started.pop(text)
                if self.total_files > 1:
                    text = '(%d/%d): %s' % (self.done_files, self.total_files, text)
                msg = ' %5sB/s | %5sB %9s    \n' % (
                    format_number(float(total)/tm),
                    format_number(total), format_time(tm))
                left = _term_width() - len(msg)
                msg = '%-*.*s%s' % (left, left, text, msg)
                self.fo.write(msg)
                self.fo.flush()
                blank = True
        # bail out when called too fast
        if not blank and now < self.last_time + 0.3:
            return
        if self.meters:
            # cycle through active meters
            if now > self.index_time:
                self.index_time = now + 1.0
                self.index += 1
            if self.index >= len(self.meters):
                self.index = 0
            text = self.meters[self.index]

            # add file counter
            if self.total_files > 1:
                n = '%d' % (self.done_files + 1)
                if len(self.meters) > 1:
                    n += '-%d' % (self.done_files + len(self.meters))
                text = '(%s/%d): %s' % (n, self.total_files, text)

            # update rate
            delta = now - self.last_time
            if delta > 0:
                rate = float(self.done_size - self.last_size)/delta
                weight = min(delta / 5.0, 1.0) # clamp to 0..1
                self.rate = self.rate * (1 - weight) + rate * weight

            # display current progress
            msg = ' %5sB/s | %5sB %9s ETA\r' % (
                format_number(self.rate), format_number(self.done_size),
                format_time((self.total_size - self.done_size) / self.rate) if self.rate > 1 else '')
            left = _term_width() - len(msg)

            # add a bar if enough space
            bl = (left - 7)/3
            if bl > 8:
                n, p = divmod(self.done_size * bl * 2 / self.total_size, 2)
                msg = ' %2d%% [%-*s]%s' % (self.done_size * 100 / self.total_size,
                                           bl, '=' * n + '-' * p, msg)
                left -= bl + 7

            msg = '%-*.*s%s' % (left, left, text, msg)
            self.fo.write(msg)
            self.fo.flush()
        self.last_time = now
        self.last_size = self.done_size
