#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, write to the 
#      Free Software Foundation, Inc., 
#      59 Temple Place, Suite 330, 
#      Boston, MA  02111-1307  USA

# This file is part of urlgrabber, a high-level cross-protocol url-grabber
# Copyright 2002-2004 Michael D. Stenner, Ryan Tomayko

# $Id$

import sys
import time
import math
import thread
    
class BaseMeter:
    def __init__(self):
        self.update_period = 0.3 # seconds

        self.filename   = None
        self.url        = None
        self.basename   = None
        self.size       = None
        self.start_time = None
        self.last_amount_read = 0
        self.last_update_time = None
        self.re = RateEstimator()
        
    def start(self, filename=None, url=None, basename=None,
              size=None, now=None):
        self.filename = filename
        self.url      = url
        self.basename = basename

        #size = None #########  TESTING
        self.size = size
        if not size is None: self.fsize = format_number(size) + 'B'

        if now is None: now = time.time()
        self.start_time = now
        self.re.start(size, now)
        self.last_amount_read = 0
        self.last_update_time = now
        self._do_start(now)
        
    def _do_start(self, now=None):
        pass

    def update(self, amount_read, now=None):
        # for a real gui, you probably want to override and put a call
        # to your mainloop iteration function here
        if now is None: now = time.time()
        if (now >= self.last_update_time + self.update_period) or \
               not self.last_update_time:
            self.re.update(amount_read, now)
            self.last_amount_read = amount_read
            self.last_update_time = now
            self._do_update(amount_read, now)

    def _do_update(self, amount_read, now=None):
        pass

    def end(self, amount_read, now=None):
        if now is None: now = time.time()
        self.re.update(amount_read, now)
        self.last_amount_read = amount_read
        self.last_update_time = now
        self._do_end(amount_read, now)

    def _do_end(self, amount_read, now=None):
        pass
        
class TextMeter(BaseMeter):
    def __init__(self, fo=sys.stderr):
        BaseMeter.__init__(self)
        self.fo = fo

    def _do_update(self, amount_read, now=None):
        etime = self.re.elapsed_time()
        fetime = format_time(etime)
        fread = format_number(amount_read)
        #self.size = None
        if self.size is None:
            out = '\r%-60.60s    %5sB %s ' % \
                  (self.basename, fread, fetime)
        else:
            rtime = self.re.remaining_time()
            frtime = format_time(rtime)
            frac = self.re.fraction_read()
            bar = '='*int(25 * frac)
            out = '\r%-25.25s %3i%% |%-25.25s| %5sB %8s ETA ' % \
                  (self.basename, frac*100, bar, fread, frtime)
        self.fo.write(out)
        self.fo.flush()

    def _do_end(self, amount_read, now=None):
        total_time = format_time(self.re.elapsed_time())
        total_size = format_number(amount_read)
        if self.size is None:
            out = '\r%-60.60s    %5sB %s ' % \
                  (self.basename, total_size, total_time)
        else:
            bar = '='*25
            out = '\r%-25.25s %3i%% |%-25.25s| %5sB %8s     ' % \
                  (self.basename, 100, bar, total_size, total_time)
        self.fo.write(out + '\n')
        self.fo.flush()

text_progress_meter = TextMeter

class MultiFileHelper(BaseMeter):
    def __init__(self, master):
        BaseMeter.__init__(self)
        self.master = master

    def _do_start(self, now):
        self.master.start_meter(self, now)

    def _do_update(self, amount_read, now):
        # elapsed time since last update
        self.master.update_meter(self, now)

    def _do_end(self, amount_read, now):
        self.ftotal_time = format_time(now - self.start_time)
        self.ftotal_size = format_number(self.last_amount_read)
        self.master.end_meter(self, now)

    def failure(self, message, now=None):
        self.master.failure_meter(self, message, now)

    def message(self, message):
        self.master.message_meter(self, message)

class MultiFileMeter:
    helperclass = MultiFileHelper
    def __init__(self):
        self.meters = []
        self.in_progress_meters = []
        self._lock = thread.allocate_lock()
        self.update_period = 0.3 # seconds
        
        self.numfiles         = None
        self.finished_files   = 0
        self.failed_files     = 0
        self.open_files       = 0
        self.total_size       = None
        self.failed_size      = 0
        self.start_time       = None
        self.finished_file_size = 0
        self.last_update_time = None
        self.re = RateEstimator()

    def start(self, numfiles=None, total_size=None, now=None):
        if now is None: now = time.time()
        self.numfiles         = numfiles
        self.finished_files   = 0
        self.failed_files     = 0
        self.open_files       = 0
        self.total_size       = total_size
        self.failed_size      = 0
        self.start_time       = now
        self.finished_file_size = 0
        self.last_update_time = now
        self.re.start(total_size, now)
        self._do_start(now)

    def _do_start(self, now):
        pass

    def end(self, now=None):
        if now is None: now = time.time()
        self._do_end(now)
        
    def _do_end(self, now):
        pass

    def lock(self): self._lock.acquire()
    def unlock(self): self._lock.release()

    ###########################################################
    # child meter creation and destruction
    def newMeter(self):
        newmeter = self.helperclass(self)
        self.meters.append(newmeter)
        return newmeter
    
    def removeMeter(self, meter):
        self.meters.remove(meter)
        
    ###########################################################
    # child functions - these should only be called by helpers
    def start_meter(self, meter, now):
        if not meter in self.meters:
            raise ValueError('attempt to use orphaned meter')
        self._lock.acquire()
        try:
            if not meter in self.in_progress_meters:
                self.in_progress_meters.append(meter)
                self.open_files += 1
        finally:
            self._lock.release()
        self._do_start_meter(meter, now)
        
    def _do_start_meter(self, meter, now):
        pass
        
    def update_meter(self, meter, now):
        if not meter in self.meters:
            raise ValueError('attempt to use orphaned meter')
        if (now >= self.last_update_time + self.update_period) or \
               not self.last_update_time:
            self.re.update(self._amount_read(), now)
            self.last_update_time = now
            self._do_update_meter(meter, now)

    def _do_update_meter(self, meter, now):
        pass

    def end_meter(self, meter, now):
        if not meter in self.meters:
            raise ValueError('attempt to use orphaned meter')
        self._lock.acquire()
        try:
            try: self.in_progress_meters.remove(meter)
            except ValueError: pass
            self.open_files     -= 1
            self.finished_files += 1
            self.finished_file_size += meter.last_amount_read
        finally:
            self._lock.release()
        self._do_end_meter(meter, now)

    def _do_end_meter(self, meter, now):
        pass

    def failure_meter(self, meter, message, now):
        if not meter in self.meters:
            raise ValueError('attempt to use orphaned meter')
        self._lock.acquire()
        try:
            try: self.in_progress_meters.remove(meter)
            except ValueError: pass
            self.open_files     -= 1
            self.failed_files   += 1
            if meter.size and self.failed_size is not None:
                self.failed_size += meter.size
            else:
                self.failed_size = None
        finally:
            self._lock.release()
        self._do_failure_meter(meter, message, now)

    def _do_failure_meter(self, meter, message, now):
        pass

    def message_meter(self, meter, message):
        pass

    ########################################################
    # internal functions
    def _amount_read(self):
        tot = self.finished_file_size
        for m in self.in_progress_meters:
            tot += m.last_amount_read
        return tot


class TextMultiFileMeter(MultiFileMeter):
    def __init__(self, fo=sys.stderr):
        self.fo = fo
        MultiFileMeter.__init__(self)

    # files: ###/### ###%  data: ######/###### ###%  time: ##:##:##/##:##:##
    def _do_update_meter(self, meter, now):
        self._lock.acquire()
        try:
            format = "files: %3i/%-3i %3i%%   data: %6.6s/%-6.6s %3i%%   " \
                     "time: %8.8s/%8.8s"
            df = self.finished_files
            tf = self.numfiles
            pf = 100 * float(df)/tf + 0.49
            dd = self.re.last_amount_read
            td = self.total_size
            pd = 100 * self.re.fraction_read() + 0.49
            dt = self.re.elapsed_time()
            rt = self.re.remaining_time()
            if rt is None: tt = None
            else: tt = dt + rt

            fdd = format_number(dd) + 'B'
            ftd = format_number(td) + 'B'
            fdt = format_time(dt, 1)
            ftt = format_time(tt, 1)
            
            out = '%-79.79s' % (format % (df, tf, pf, fdd, ftd, pd, fdt, ftt))
            self.fo.write('\r' + out)
            self.fo.flush()
        finally:
            self._lock.release()

    def _do_end_meter(self, meter, now):
        self._lock.acquire()
        try:
            format = "%-30.30s %6.6s    %8.8s    %9.9s"
            fn = meter.basename
            size = meter.last_amount_read
            fsize = format_number(size) + 'B'
            et = meter.re.elapsed_time()
            fet = format_time(et, 1)
            frate = format_number(size / et) + 'B/s'
            
            out = '%-79.79s' % (format % (fn, fsize, fet, frate))
            self.fo.write('\r' + out + '\n')
        finally:
            self._lock.release()
        self._do_update_meter(meter, now)

    def _do_failure_meter(self, meter, message, now):
        self._lock.acquire()
        try:
            format = "%-30.30s %6.6s %s"
            fn = meter.basename
            if type(message) in (type(''), type(u'')):
                message = message.splitlines()
            if not message: message = ['']
            out = '%-79s' % (format % (fn, 'FAILED', message[0] or ''))
            self.fo.write('\r' + out + '\n')
            for m in message[1:]: self.fo.write('  ' + m + '\n')
            self._lock.release()
        finally:
            self._do_update_meter(meter, now)

    def message_meter(self, meter, message):
        self._lock.acquire()
        try:
            pass
        finally:
            self._lock.release()

    def _do_end(self, now):
        self._do_update_meter(None, now)
        self._lock.acquire()
        try:
            self.fo.write('\n')
            self.fo.flush()
        finally:
            self._lock.release()
        
######################################################################
# support classes and functions

class RateEstimator:
    def __init__(self, timescale=5.0):
        self.timescale = timescale

    def start(self, total=None, now=None):
        if now is None: now = time.time()
        self.total = total
        self.start_time = now
        self.last_update_time = now
        self.last_amount_read = 0
        self.ave_rate = None
        
    def update(self, amount_read, now=None):
        if now is None: now = time.time()
        if amount_read == 0:
            # if we just started this file, all bets are off
            self.last_update_time = now
            self.last_amount_read = 0
            self.ave_rate = None
            return

        #print 'times', now, self.last_update_time
        time_diff = now         - self.last_update_time
        read_diff = amount_read - self.last_amount_read
        self.last_update_time = now
        self.last_amount_read = amount_read
        self.ave_rate = self._temporal_rolling_ave(\
            time_diff, read_diff, self.ave_rate, self.timescale)
        #print 'results', time_diff, read_diff, self.ave_rate
        
    #####################################################################
    # result methods
    def average_rate(self):
        "get the average transfer rate (in bytes/second)"
        return self.ave_rate

    def elapsed_time(self):
        "the time between the start of the transfer and the most recent update"
        return self.last_update_time - self.start_time

    def remaining_time(self):
        "estimated time remaining"
        if not self.ave_rate or not self.total: return None
        return (self.total - self.last_amount_read) / self.ave_rate

    def fraction_read(self):
        """the fraction of the data that has been read
        (can be None for unknown transfer size)"""
        if self.total is None: return None
        elif self.total == 0: return 1.0
        else: return float(self.last_amount_read)/self.total

    #########################################################################
    # support methods
    def _temporal_rolling_ave(self, time_diff, read_diff, last_ave, timescale):
        """a temporal rolling average performs smooth averaging even when
        updates come at irregular intervals.  This is performed by scaling
        the "epsilon" according to the time since the last update.
        Specifically, epsilon = time_diff / timescale

        As a general rule, the average will take on a completely new value
        after 'timescale' seconds."""
        epsilon = time_diff / timescale
        if epsilon > 1: epsilon = 1.0
        return self._rolling_ave(time_diff, read_diff, last_ave, epsilon)
    
    def _rolling_ave(self, time_diff, read_diff, last_ave, epsilon):
        """perform a "rolling average" iteration
        a rolling average "folds" new data into an existing average with
        some weight, epsilon.  epsilon must be between 0.0 and 1.0 (inclusive)
        a value of 0.0 means only the old value (initial value) counts,
        and a value of 1.0 means only the newest value is considered."""
        
        try:
            recent_rate = read_diff / time_diff
        except ZeroDivisionError:
            recent_rate = None
        if last_ave is None: return recent_rate
        elif recent_rate is None: return last_ave

        # at this point, both last_ave and recent_rate are numbers
        return epsilon * recent_rate  +  (1 - epsilon) * last_ave

    def _round_remaining_time(self, rt, start_time=15.0):
        """round the remaining time, depending on its size
        If rt is between n*start_time and (n+1)*start_time round downward
        to the nearest multiple of n (for any counting number n).
        If rt < start_time, round down to the nearest 1.
        For example (for start_time = 15.0):
         2.7  -> 2.0
         25.2 -> 25.0
         26.4 -> 26.0
         35.3 -> 34.0
         63.6 -> 60.0
        """

        if rt < 0: return 0.0
        shift = int(math.log(rt/start_time)/math.log(2))
        rt = int(rt)
        if shift <= 0: return rt
        return float(int(rt) >> shift << shift)
        

def format_time(seconds, use_hours=0):
    if seconds is None or seconds < 0:
        if use_hours: return '--:--:--'
        else:         return '--:--'
    else:
        seconds = int(seconds)
        minutes = seconds / 60
        seconds = seconds % 60
        if use_hours:
            hours = minutes / 60
            minutes = minutes % 60
            return '%02i:%02i:%02i' % (hours, minutes, seconds)
        else:
            return '%02i:%02i' % (minutes, seconds)
        
def format_number(number, SI=0, space=' '):
    """Turn numbers into human-readable metric-like numbers"""
    symbols = ['',  # (none)
               'k', # kilo
               'M', # mega
               'G', # giga
               'T', # tera
               'P', # peta
               'E', # exa
               'Z', # zetta
               'Y'] # yotta
    
    if SI: step = 1000.0
    else: step = 1024.0

    thresh = 999
    depth = 0
    
    # we want numbers between 
    while number > thresh:
        depth  = depth + 1
        number = number / step
        
    # just in case someone needs more than 1000 yottabytes!
    diff = depth - len(symbols) + 1
    if diff > 0:
        depth = depth - diff
        number = number * thresh**depth

    if type(number) == type(1) or type(number) == type(1L):
        format = '%i%s%s'
    elif number < 9.95:
        # must use 9.95 for proper sizing.  For example, 9.99 will be
        # rounded to 10.0 with the .1f format string (which is too long)
        format = '%.1f%s%s'
    else:
        format = '%.0f%s%s'
        
    return(format % (number, space, symbols[depth]))
