import sys
import time

class text_progress_meter:
    def __init__(self, fo=sys.stderr):
        self.fo = fo
        self.update_period = 0.3 # seconds

    def start(self, filename, url, basename, length):
        self.filename = filename
        self.url = url
        self.basename = basename
        self.length = length
        if not length == None:
            self.flength = self.format_number(length) + 'B'
        self.start_time = time.time()
        self.last_update = 0
        self._do_start()

    def _do_start(self):
        pass

    def end(self):
        self.now = time.time()
        self._do_end()

    def _do_end(self):
        total_time = self.format_time(self.now - self.start_time)
        total_size = self.format_number(self.read)
        if self.length is None:
            out = '\r%-60.60s    %5sB %s ' % \
                  (self.basename, total_size, total_time)
        else:
            bar = '='*25
            out = '\r%-25.25s %3i%% |%-25.25s| %5sB %8s     ' % \
                  (self.basename, 100, bar, total_size, total_time)
        self.fo.write(out)
        self.fo.write('\n')
        self.fo.flush()
        
    def update(self, read):
        # for a real gui, you probably want to override and put a call
        # to your mainloop iteration function here
        self.read = read # put this here so it's caught for self.end
        now = time.time()
        if (now >= self.last_update + self.update_period) or \
               not self.last_update:
            self.now = now
            self._do_update(read)
            self.last_update = now

    def _do_update(self, read):
        # elapsed time since last update
        etime = self.now - self.start_time
        fetime = self.format_time(etime)
        fread = self.format_number(read)

        #self.length = None
        if self.length is None:
            out = '\r%-60.60s    %5sB %s ' % \
                  (self.basename, fread, fetime)
        else:
            rtime = self.format_time(self.project(etime, read))
            try: frac = float(read)/self.length
            except ZeroDivisionError, e: frac = 1.0
            if frac > 1.0: frac = 1.0
            bar = '='*int(25 * frac)
            out = '\r%-25.25s %3i%% |%-25.25s| %5sB %8s ETA ' % \
                  (self.basename, frac*100, bar, fread, rtime)
        self.fo.write(out)
        self.fo.flush()

    def project(self, etime, read):
        # get projected time for total download
        if read == 0:
            # if we just started this file, all bets are off
            self.last_etime = etime
            self.last_read  = 0
            self.ave_rate = None
            return None

        time_diff = etime - self.last_etime
        read_diff = read  - self.last_read
        self.last_etime = etime
        self.last_read  = read
        try: rate = time_diff / read_diff  ## this is actually an inverse-rate
        except ZeroDivisionError: return 0 ## should only happen at end of file

        self._get_new_ave_rate(rate)
        remaining_time = self.ave_rate * (self.length - read)
        if remaining_time < 0: remaining_time = 0
        return self._round_remaining_time(remaining_time)
        
    def _get_new_ave_rate(self, rate, epsilon=0.98):
        if self.ave_rate == None:
            self.ave_rate = rate
        else:
            # calculate a "rolling average" - this balances long-term behavior
            # with short-term fluctuations
            # epsilon = 0.0  -->  only consider most recent block
            # epsilon = 1.0  -->  only consider first block
            self.ave_rate = (self.ave_rate * epsilon) + (rate * (1-epsilon))

    def _round_remaining_time(self, remaining_time):
        # round to further stabilize it
        i = 1
        while remaining_time > 30:
            i = i * 2
            remaining_time = remaining_time / 2
        remaining_time = int(remaining_time)
        return float(remaining_time * i)
            
    def format_time(self, seconds):
        if seconds is None or seconds < 0:
            return '--:--'
        else:
            seconds = int(seconds)
            minutes = seconds / 60
            seconds = seconds % 60
            return '%02i:%02i' % (minutes, seconds)
        
    def format_number(self, number, SI=0, space=' '):
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
