import sys
import string

class logger:
    """
    USAGE:
      from logger import logger

      log_obj = logger(VERBOSITY)     # create the instance

      log_obj.log(3, 'message')       # log a message with level 3
      log_obj(3, 'message')           # same thing
      log_obj(3, ['message'])         # same thing

      log_obj.test(3)                 # boolean - would a message of
                                      # this level be printed?

      # a raw write call after the level test, for writing arbitrary text
      log_obj.write(3, 'thing\nto\nwrite')  # (will not be followed by \n)
      
      pr = log_obj.gen_prefix(3)  # generate the prefix used for level 3

      # see the examples in the test section for more

    ATTRIBUTES:
      (all of these are settable as keyword args to __init__)

      ATTRIBUTES   DEFAULT      DESCRIPTION
      ----------------------------------------------------------
      verbosity    = 0          how verbose the program should be
      default      = 1          default level to log at
      file_object  = sys.stderr file object to which output goes
      prefix       = '='        prefix string - repeated for more
                                important logs
      prefix_depth = 5          times prefix is repeated for logs
                                of level 0.  Basically, set this
                                one larger than your highest log
                                level.
      preprefix    = ''         string printed before the prefix
                                if callable, returned string will
                                be used (useful for printing time)
      postprefix   = ' '        string printed after the prefix
      children     = []         list of other logging objects
                                every time the log method is
                                called, the parent will also call
                                it for each child.  Do not make
                                it recursive.  I warned you.
      

    SUGGESTED USE:
      I use the following rules of thumb:

        LOG LEVEL    MEANING
              -1     failure - cannot be ignored
               0     important message - printed in default mode
               1     informational message - printed with -v
               2     debugging information

      You can extend it farther in both directions, but I rarely
      find it useful.

        VERBOSITY    MEANING
              -1     quiet mode (-q) only failures are printed
               0     normal operation
               1     verbose mode (-v)
               2     debug mode (-vv or -d)

      If you don't like the repeated prefix, set it to ''.  You can
      still use preprefix to print your program name, for example.

    """

    AUTHOR  = "Michael D. Stenner <mstenner@phy.duke.edu>"
    VERSION = "0.3"
    DATE    = "2002/05/29"

    def __init__(self,
                 verbosity    = 0,
                 default      = 1,
                 file_object  = sys.stderr,
                 prefix       = '=',
                 prefix_depth = 5,
                 preprefix    = '',
                 postprefix   = ' ',
                 children     = None):
        self.verbosity    = int(verbosity)
        self.default      = default
        self.file_object  = file_object
        self.prefix       = prefix
        self.prefix_depth = prefix_depth
        self.preprefix    = preprefix
        self.postprefix   = postprefix
        if children == None: self.children = []
        else: self.children = children

    def test(self, level):

        """
        Return true if a log of the given level would be printed.
        """

        if self.verbosity >= int(level): return 1
        else: return 0
        
    def gen_prefix(self, level):

        """
        Return the full prefix (including pre and post) for the
        given level
        """
        
        if callable(self.preprefix): prefix = self.preprefix()
        else: prefix = self.preprefix

        if self.prefix:
            depth  = self.prefix_depth - level
            if depth < 1: depth = 1
            for i in range(0, depth):
                prefix = prefix + self.prefix

        prefix = prefix + self.postprefix
        return prefix

    def __call__(self, level, message=None):

        """
        A convenient alternative to the log method.  Basically, I
        like to name the instance "log" to minimize characters :)
        """

        self.log(level, message)

    def log(self, level, message=None):
        """
        Print a log message.  This prepends the prefix to each line.
        """

        if message == None:
            # using default level, and the variable 'level'
            # actually contains the message
            m = level
            l = self.default
        else:
            l = level
            m = message

        if self.test(l):
            if type(m) == type(''): # message is a string
                mlist = string.split(m, '\n')
                if mlist[-1] == '': del mlist[-1] # string ends in \n
            elif type(m) == type([]): # message is a list
                mlist = []
                for line in m: mlist.append(string.rstrip(line))
            else: mlist = [str(m)] # message is other type
            for line in mlist:
                self.file_object.write(self.gen_prefix(l) +
                                       line + '\n')

        for child in self.children: child.log(level, message)

    def write(self, level, message=None):
        """
        Print a log message.  In this case, 'message' must be a string
        as it will be passed directly to the file object's write method.
        """
        
        if message == None:
            # using default level, and the variable 'level'
            # actually contains the message
            m = level
            l = self.default
        else:
            l = level
            m = message

        if self.test(l): self.file_object.write(m)

        for child in self.children: child.write(level, message)


if __name__ == '__main__':
    ###### TESTING AND DEMONSTRATION

    loglevel = 3
    print 'LOGLEVEL = %s' % (loglevel)
    log   = logger(loglevel,   preprefix = 'TEST  ')

    print " Lets log a few things!"
    for i in range(-2, 10): log(i, 'log level %s' % (i))

    print "\n Now make it print the time for each log..."
    import time
    def printtime():
        return time.strftime('%m/%d/%y %H:%M:%S ',time.localtime(time.time()))
    log.preprefix = printtime

    print " and log a few more things"
    for i in range(-2, 10): log(i, 'log level %s' % (i))
 
    print "\n now add a child with a different prefix and level..."
    child = logger(loglevel-2, preprefix = 'CHILD ')
    log.children.append(child)

    print " and log a bit more"
    for i in range(-2, 10): log(i, 'log level %s' % (i))

    print "\n OK, enough of the child... lets play with formatting"
    log.children = []

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

