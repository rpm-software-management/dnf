"""
A module for convenient yet powerful file-object logging

BASIC USAGE

  from logger import Logger

  log = Logger(threshold=0)    # create the log object and give it
                               # a threshold of 0
  log.log(2, 'all done')       # send a log of priority 2 (not printed)
  log(0, 'error: bandits!')    # send a log of priority 0 (printed)
  log.write(0, stringvar)      # do a raw write on the file object

DESCRIPTION

  Each logging object is given a threshold.  Any messages that are
  then sent to that object are logged only if their priority meets or
  exceeds the threshold.  Lower numerical priority means that a
  message is more important.  For example: if a log object has
  threshold 2, then all messages of priority 2, 1, 0, -1, etc will be
  logged, while those of priority 3, 4, etc. will not.  I suggest the
  following scale:
  
     LOG PRIORITY    MEANING
              -1     failure - cannot be ignored
               0     important message - printed in default mode
               1     informational message - printed with -v
               2     debugging information

        THRESHOLD    MEANING
              -1     quiet mode (-q) only failures are printed
               0     normal operation
               1     verbose mode (-v)
               2     debug mode (-vv or -d)

  It can be extended farther in both directions, but that is rarely
  useful.  It can also be shifted in either direction.  This might be
  useful if you want o supply the threshold directly on the command
  line but have trouble passing in negative numbers.  In that case,
  add 1 to all thresholds and priorities listed above.

BASIC OPTIONS

  There are a couple of basic options that are commonly needed.  These
  are attribues of instances of class Logger.

  preprefix

    Text that will be printed at the start of each line of output (for
    log()ged, not write()en messages).  This might be your program's
    name, for example.

      log.preprefix = 'myprog'

    If preprefix is callable, then it will be called for each log and
    the returned value will be used.  This is useful for printing the
    current time.

      import time
      def printtime():
          return time.strftime('%m/%d/%y %H:%M:%S ',
                               time.localtime(time.time()))
      log.preprefix = printtime
  
  file_object

    This is the file object to which output is directed.  If it is None,
    then the logs are quietly dropped.

LOG CONTAINERS

  If you want a program to log to multiple destinations, it might be
  convenient to use log containers.  A log container is an object
  which hold several log objects.  When you log to a log container it
  passes the message on (with optional tests) to each of the log
  objects it contains.  For example:

    from logger import Logger, LogContainer

    system = Logger(threshold=1, file_object=logfile)
    debug  = Logger(threshold=5, file_object=sys.stdout)
    log = LogContainer([system, debug])

    log(3, 'sent to system and debug, but only debug will print it')
    log(0, 'very important, both will print it')

  In this mode, log containers are just shorthand for calling all
  contained objects with the same priority and message.

  When a log object is held in a container, it can still be used
  directly.  For example, you can still do

    debug(3, ['this will not be sent to the system log, even if its',
              ' threshold is set very high'])

  (Yes, you can send lists of strings and they will be formatted on
  different lines.  It is pretty smart.)

ADVANCED

  There are a number of options available for both classes.  These are
  documented below, in the respective classes and methods.  Here is a
  list of some of the things you can do:

    * make the prefix contain a string which gets repeated for more
      important logs.  (prefix)
    * directly test if a log object WOULD log, so you can do
      complicated stuff, like efficient for loops. (test)
    * make the priority, threshold arbitrary objects, with a
      home-rolled test to see if it should log. (test)
    * give log containers a "master threshold" and define arbitrary
      behavior based on it.  Examples include:
      - only pass on messages of sufficient priority (ragardless of
        the thresholds of the log ojects).
      - only pass on messages to objects whose thresholds are
        (numerically) lower than the master threshold.

SEE ALSO

  Take a look at the examples at the end of this file in the test &
  demo section.

COMMENTS

  I welcome comments, questions, bug reports and requests... I'm very
  lonely. :)
"""

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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# Copyright 2001-2002 Michael D. Stenner

import sys
import string


AUTHOR  = "Michael D. Stenner <mstenner@phy.duke.edu>"
VERSION = "0.6"
DATE    = "2002/08/13"
URL     = "http://www.dulug.duke.edu/~mstenner/software/logger/"

class Logger:
    """A class for file-object logging
    
    USAGE:
      from logger import Logger

      log_obj = Logger(THRESHOLD)     # create the instance

      log_obj.log(3, 'message')       # log a message with priority 3
      log_obj(3, 'message')           # same thing
      log_obj(3, ['message'])         # same thing

      log_obj.test(3)                 # boolean - would a message of
                                      # this priority be printed?

      # a raw write call after the priority test, for writing
      # arbitrary text -- (this will not be followed by \\n)
      log_obj.write(3, 'thing\\nto\\nwrite')  

      # generate the prefix used for priority 3
      pr = log_obj.gen_prefix(3)

      # see the examples in the test section for more

    ATTRIBUTES:
      (all of these are settable as keyword args to __init__)

      ATTRIBUTES   DEFAULT      DESCRIPTION
      ----------------------------------------------------------
      threshold    = 0          how verbose the program should be
      file_object  = sys.stderr file object to which output goes
      prefix       = ''         prefix string - repeated for more
                                important logs
      prefix_depth = 5          times prefix is repeated for logs
                                of priority 0.  Basically, set this
                                one larger than your highest log
                                priority.
      preprefix    = ''         string printed before the prefix
                                if callable, returned string will
                                be used (useful for printing time)
      postprefix   = ''         string printed after the prefix
      default      = 1          default priority to log at

    """

    def __init__(self,
                 threshold    = 0,
                 file_object  = sys.stderr,
                 prefix       = '',
                 prefix_depth = 5,
                 preprefix    = '',
                 postprefix   = '',
                 default      = 1):
        self.threshold    = threshold
        self.file_object  = file_object
        self.prefix       = prefix
        self.prefix_depth = prefix_depth
        self.preprefix    = preprefix
        self.postprefix   = postprefix
        self.default      = default

    def test(self, priority):

        """
        Return true if a log of the given priority would be printed.
        
        This can be overridden to do any test you like.  Specifically,
        log and threshold need not be integers.  They be arbitrary
        objects.  You need only override this method, possibly
        gen_prefix.
        """

        return int(self.threshold) >= int(priority)
        
    def gen_prefix(self, priority):

        """
        Return the full prefix (including pre and post) for the
        given priority.

        If you use prefix and use a more complicated priority and
        verbosity (non-numerical), then you should either give the
        chosen object a __int__ method, or override this function.
        """
        
        if callable(self.preprefix): prefix = self.preprefix()
        else: prefix = self.preprefix

        if self.prefix:
            depth  = self.prefix_depth - int(priority)
            if depth < 1: depth = 1
            for i in range(0, depth):
                prefix = prefix + self.prefix

        return prefix + self.postprefix

    def log(self, priority, message=None):
        """
        Print a log message.  This prepends the prefix to each line
        and does some basic formatting.
        """
        p, m = self._use_default(priority, message)
        if self.test(p):
            if self.file_object is None: return
            if type(m) == type(''): # message is a string
                mlist = string.split(m, '\n')
                if mlist[-1] == '': del mlist[-1] # string ends in \n
            elif type(m) == type([]): # message is a list
                mlist = map(string.rstrip, m)
            else: mlist = [str(m)] # message is other type

            prefix = self.gen_prefix(p)
            for line in mlist:
                self.file_object.write(prefix + line + '\n')

    # make the objects callable
    __call__ = log

    def write(self, priority, message=None):
        """
        Print a log message.  In this case, 'message' must be a string
        as it will be passed directly to the file object's write method.
        """
        p, m = self._use_default(priority, message)
        if self.test(p):
            if self.file_object is None: return
            self.file_object.write(m)

    def _use_default(self, priority, message):
        """Substitute default priority if none was provided"""
        if message == None: return self.default, priority
        else: return priority, message

class LogContainer:
    """A class for consolidating calls to multiple Logger objects

    USAGE:
      from logger import Logger, LogContainer

      log_1 = Logger(threshold=1, file_object=sys.stdout)
      log_2 = Logger(threshold=2, preprefix='LOG2')

      log = LogContainer([log_1, log_2])

      log(1, 'message')               # printed by log_1 and log_2
      log(2, 'message')               # only printed by log_2

    ATTRIBUTES:
      (all of these are settable as keyword args to __init__)

      ATTRIBUTES   DEFAULT      DESCRIPTION
      ----------------------------------------------------------
      list         = []         list of Logger objects
      threshold    = None       meaning depends on test - by default
                                threshold has no effect
      default      = 1          default priority to log at

    """


    def __init__(self, list=[], threshold=None, default=1):
        self.list = list
        self.threshold = threshold
        self.default = default

    def add(self, log_obj):
        """Add a log object to the container."""
        self.list.append(log_obj)

    def log(self, priority, message=None):
        """Log a message to all contained log objects, depending on
        the results of test()
        """
        p, m = self._use_default(priority, message)
        for log_obj in self.list:
            if self.test(p, m, self.threshold, log_obj):
                log_obj.log(p, m)

    __call__ = log
    
    def write(self, priority, message=None):
        p, m = self._use_default(priority, message)
        for log_obj in self.list:
            if self.test(p, m, self.threshold, log_obj):
                log_obj.write(p, m)

    def _use_default(self, priority, message):
        """Substitute default priority if none was provided"""
        if message == None: return self.default, priority
        else: return priority, message

    def test(self, priority, message, threshold, log_obj):
        """Test which log objects should be passed a given message.

        This method is used to determine if a given message (and
        priority) should be passed on to a given log_obj.  The
        container's threshold is also provided.

        This method always returns 1, and is the default, meaning that
        all messages will get passed to all objects.  It is intended
        to be overridden if you want more complex behavior.  To
        override with your own function, just do something like:

          def hell_no(p, m, t, object): return 0
          container.test = hell_no
        """
        return 1

    def test_limit_priority(self, priority, message, threshold, log_obj):
        """Only pass on messages with sufficient priority compared to
        the master threshold.

          container = LogContainer([system, debug], threshold = 2)
          container.test = container.test_limit_priority
        """
        return priority <= threshold
    
    def test_limit_threshold(self, priority, message, threshold, log_obj):
        """Only pass on messages to log objects whose threshold is
        (numerically) lower than the master threshold.

          container = LogContainer([system, debug], threshold = 2)
          container.test = container.test_limit_threshold
        """
        return log_obj.threshold <= threshold
    
if __name__ == '__main__':
    ###### TESTING AND DEMONSTRATION

    threshold = 3
    print 'THRESHOLD = %s' % (threshold)
    log   = Logger(threshold,   preprefix = 'TEST  ')

    print " Lets log a few things!"
    for i in range(-2, 10): log(i, 'log priority %s' % (i))

    print "\n Now make it print the time for each log..."
    import time
    def printtime():
        return time.strftime('%m/%d/%y %H:%M:%S ',time.localtime(time.time()))
    log.preprefix = printtime

    print " and log a few more things"
    for i in range(-2, 10): log(i, 'log priority %s' % (i))
 
    print "\n now create another with a different prefix and priority..."
    print " and put them in a container..."
    log2 = Logger(threshold-2, preprefix = 'LOG2 ')
    cont = LogContainer([log, log2], threshold=0)
    cont.test = cont.test_limit_priority
    
    print " and log a bit more"
    for i in range(-2, 10): cont(i, 'log priority %s' % (i))

    print "\n OK, enough of the container... lets play with formatting"

    stuff = 'abcd\nefgh\nijkl'

    print "\n no trailing newline"
    log(stuff)

    print "\n with trailing newline"
    log(stuff + '\n') # should be the same because the log method
                      # takes care of the newline for you

    print "\n two trailing newlines"
    log(stuff + '\n\n') # should create a "blank" line.  If you use two
                        # newlines, it knows you really wanted one :)
    
    print "\n log JUST a newline"
    log('\n') # should create only a single "blank" line

    print "\n use the write method, with a trailing newline"
    log.write(stuff + '\n') # should just write with no prefix crap
                            # it will _NOT_ quietly tack on a newline

    print "\n print some complex object"
    log(1, {'key': 'value'}) # non-strings should be no trouble

    print "\n now set the file object to None (nothing should be printed)"
    log.file_object = None
    log("THIS SHOULD NOT BE PRINTED")
    log.write("THIS SHOULD NOT BE PRINTED")
