import os.path
import urlparse
import time
import string

DEBUG=0

try:
    from i18n import _
except ImportError, msg:
    def _(st): return st

try:
    from httplib import HTTPException
except ImportError, msg:
    HTTPException = None

special_handlers = []

try:
    import urllib2
except ImportError, msg:
    import urllib
    urllib._urlopener = urllib.FancyURLopener() # make sure it ready now
    urllib2 = urllib   # this way, we can always just do urllib.urlopen()
    have_urllib2 = 0
    auth_handler = None
else:
    have_urllib2 = 1
    auth_handler = urllib2.HTTPBasicAuthHandler( \
        urllib2.HTTPPasswordMgrWithDefaultRealm())
    special_handlers.append(auth_handler)

try:
    # This is a convenient way to make keepalive optional.
    # Just rename the module so it can't be imported.
    from keepalive import HTTPHandler
except ImportError, msg:
    keepalive_handler = None
else:
    keepalive_handler = HTTPHandler()
    special_handlers.append(keepalive_handler)

if have_urllib2:
    opener = apply(urllib2.build_opener, special_handlers)
    urllib2.install_opener(opener)

def set_user_agent(new_user_agent):
    if have_urllib2: addheaders = opener.addheaders
    else:            addheaders = urllib._urlopener.addheaders

    new_tuple = ('User-agent', new_user_agent)

    for i in range(len(addheaders)):
        if addheaders[i][0] == 'User-agent':
            addheaders[i] = new_tuple
            break
    else:
        addheaders.append(new_tuple)

class URLGrabError(IOError):
    """
    URLGrabError error codes:
      -1 - default retry code for retrygrab check functions
      0  - everything looks good (you should never see this)
      1  - malformed url
      2  - local file doesn't exist
      3  - request for non-file local file (dir, etc)
      4  - IOError on fetch
      5  - OSError on fetch
      6  - no content length header when we expected one
      7  - HTTPException

    Negative codes are reserved for use by functions passed in to
    retrygrab with checkfunc.

    You can use it like this:
      try: urlgrab(url)
      except URLGrabError, e:
         if e.errno == 3: ...
           # or
         print e.strerror
           # or simply
         print e  #### print '[Errno %i] %s' % (e.errno, e.strerror)
    """
    pass

def close_all():
    """close any open keepalive connections"""
    if keepalive_handler: keepalive_handler.close_all()

_throttle = 1.0
_bandwidth = 0
def set_throttle(new_throttle):
    """urlgrab supports throttling via two values: throttle and bandwidth
    Between the two, you can either specify and absolute throttle threshold
    or specify a theshold as a fraction of maximum available bandwidth.
    
    throttle is a number - if it's an int, it's the bytes/second throttle
       limit.  If it's a float, it is first multiplied by bandwidth.  If
       throttle == 0, throttling is disabled.  If None, the module-level
       default (which can be set with set_throttle) is used.

    bandwidth is the nominal max bandwidth in bytes/second.  If throttle
       is a float and bandwidth == 0, throttling is disabled.  If None,
       the module-level default (which can be set with set_bandwidth) is
       used.

    EXAMPLES:

      Lets say you have a 100 Mbps connection.  This is (about) 10^8 bits
      per second, or 12,500,000 Bytes per second.  You have a number of
      throttling options:

      *) set_bandwidth(12500000); set_throttle(0.5) # throttle is a float

         This will limit urlgrab to use half of your available bandwidth.

      *) set_throttle(6250000) # throttle is an int

         This will also limit urlgrab to use half of your available
         bandwidth, regardless of what bandwidth is set to.

      *) set_throttle(6250000); set_throttle(1.0) # float

         Use half your bandwidth

      *) set_throttle(6250000); set_throttle(2.0) # float

         Use up to 12,500,000 Bytes per second (your nominal max bandwidth)

      *) set_throttle(6250000); set_throttle(0) # throttle = 0

         Disable throttling - this is more efficient than a very large
         throttle setting.

      *) set_throttle(0); set_throttle(1.0) # throttle is float, bandwidth = 0

         Disable throttling - this is the default when the module is loaded.


    SUGGESTED AUTHOR IMPLEMENTATION

      While this is flexible, it's not extremely obvious to the user.  I
      suggest you implement a float throttle as a percent to make the
      distinction between absolute and relative throttling very explicit.

      Also, you may want to convert the units to something more convenient
      than bytes/second, such as kbps or kB/s, etc.
    """
    global _throttle
    _throttle = new_throttle

def set_bandwidth(new_bandwidth):
    global _bandwidth
    _bandwidth = new_bandwidth


def retrygrab(url, filename=None, copy_local=0, close_connection=0,
              progress_obj=None, throttle=None, bandwidth=None,
              numtries=3, retrycodes=[-1,2,4,5,6,7], checkfunc=None):
    """a wrapper function for urlgrab that retries downloads

    The args for retrygrab are the same as urlgrab except for numtries,
    retrycodes, and checkfunc.  You should use keyword arguments for
    both in case new args are added to urlgrab later.  If you use keyword
    args (especially for the retrygrab-specific options) then retrygrab
    will continue to be a drop-in replacement for urlgrab.  Otherwise,
    things may break.

    retrygrab exits just like urlgrab in either case.  Either it
    returns the local filename or it raises an exception.  The
    exception raised will be the one raised MOST RECENTLY by urlgrab.

    retrygrab ONLY retries if URLGrabError is raised.  If urlgrab (or
    checkfunc) raise some other exception, it will be passed up
    immediately.

    numtries
       number of times to retry the grab before bailing.  If this is
       zero, it will retry forever.  This was intentional... really,
       it was :)

    retrycodes
       the errorcodes (values of e.errno) for which it should retry.
       See the doc on URLGrabError for more details on this.

    checkfunc
       a function to do additional checks.  This defaults to None,
       which means no additional checking.  The function should simply
       return on a successful check.  It should raise URLGrabError on
       and unsuccessful check.  Raising of any other exception will
       be considered immediate failure and no retries will occur.

       Negative error numbers are reserved for use by these passed in
       functions.  By default, -1 results in a retry, but this can be
       customized with retrycodes.

       If you simply pass in a function, it will be given exactly one
       argument: the local file name as returned by urlgrab.  If you
       need to pass in other arguments,  you can do so like this:

         checkfunc=(function, ('arg1', 2), {'kwarg': 3})

       if the downloaded file as filename /tmp/stuff, then this will
       result in this call:

         function('/tmp/stuff', 'arg1', 2, kwarg=3)

       NOTE: both the "args" tuple and "kwargs" dict must be present
       if you use this syntax, but either (or both) can be empty.
    """

    tries = 0
    if not checkfunc is None:
        if callable(checkfunc):
            func, args, kwargs = checkfunc, (), {}
        else:
            func, args, kwargs = checkfunc
    else:
        func = None

    while 1:
        tries = tries + 1
        if DEBUG: print 'TRY #%i: %s' % (tries, url)
        try:
            fname = urlgrab(url, filename, copy_local, close_connection,
                            progress_obj, throttle, bandwidth)
            if not func is None: apply(func, (fname, )+args, kwargs)
            if DEBUG: print 'RESULT = success (%s)' % fname
            return fname
        except URLGrabError, e:
            if DEBUG: print 'EXCEPTION: %s' % e
            if tries == numtries or (e.errno not in retrycodes): raise

def urlgrab(url, filename=None, copy_local=0, close_connection=0,
            progress_obj=None, throttle=None, bandwidth=None):
    """grab the file at <url> and make a local copy at <filename>

    If filename is none, the basename of the url is used.

    copy_local is ignored except for file:// urls, in which case it
    specifies whether urlgrab should still make a copy of the file, or
    simply point to the existing copy.

    close_connection tells urlgrab to close the connection after
    completion.  This is ignored unless the download happens with the
    http keepalive handler.  Otherwise, the connection is left open
    for further use.

    progress_obj is a class instance that supports the following methods:
       po.start(filename, url, basename, length)
       # length will be None if unknown
       po.update(read) # read == bytes read so far
       po.end()

    throttle is a number - if it's an int, it's the bytes/second throttle
       limit.  If it's a float, it is first multiplied by bandwidth.  If
       throttle == 0, throttling is disabled.  If None, the module-level
       default (which can be set with set_throttle) is used.

    bandwidth is the nominal max bandwidth in bytes/second.  If throttle
       is a float and bandwidth == 0, throttling is disabled.  If None,
       the module-level default (which can be set with set_bandwidth) is
       used.

    urlgrab returns the filename of the local file, which may be different
    from the passed-in filename if copy_local == 0.
    """

    (scheme, host, path, parm, query, frag) = urlparse.urlparse(url)
    path = os.path.normpath(path)
    if '@' in host and auth_handler and scheme in ['http', 'https']:
        try:
            # should we be using urllib.splituser and splitpasswd instead?
            user_password, host = string.split(host, '@', 1)
            user, password = string.split(user_password, ':', 1)
        except ValueError, e:
            raise URLGrabError(1, _('Bad URL: %s') % url)
        if DEBUG: print 'adding HTTP auth: %s, %s' % (user, password)
        auth_handler.add_password(None, host, user, password)

    url = urlparse.urlunparse((scheme, host, path, parm, query, frag))

    if filename == None:
        filename = os.path.basename(path)
    if scheme == 'file' and not copy_local:
        # just return the name of the local file - don't make a copy
        # currently we don't do anything with the progress_cb here
        if not os.path.exists(path):
            raise URLGrabError(2, _('Local file does not exist: %s') % (path, ))
        elif not os.path.isfile(path):
            raise URLGrabError(3, _('Not a normal file: %s') % (path, ))
        else:
            return path

    if throttle == None: throttle = _throttle
    if throttle <= 0: raw_throttle = 0
    elif type(throttle) == type(0): raw_throttle = float(throttle)
    else: # throttle is a float
        if bandwidth == None: bandwidth = _bandwidth
        raw_throttle = bandwidth * throttle

    # initiate the connection & get the headers
    try:
        fo = urllib2.urlopen(url)
        hdr = fo.info()
    except ValueError, e:
        raise URLGrabError(1, _('Bad URL: %s') % (e, ))
    except IOError, e:
        raise URLGrabError(4, _('IOError: %s') % (e, ))
    except OSError, e:
        raise URLGrabError(5, _('OSError: %s') % (e, ))
    except HTTPException, e:
        raise URLGrabError(7, _('HTTP Error (%s): %s') % \
                           (e.__class__.__name__, e))

    # this is a cute little hack - if there isn't a "Content-Length"
    # header then its probably something generated dynamically, such
    # as php, cgi, a directory listing, or an error message.  It is
    # probably not what we want.
    if have_urllib2 or scheme != file:
        # urllib does not provide content-length for local files
        if not hdr is None and not hdr.has_key('Content-Length'):
            raise URLGrabError(6, _('ERROR: Url Return no Content-Length  - something is wrong'))

    # download and store the file
    try:
        if progress_obj is None:
            _do_grab(filename, fo, progress_obj, raw_throttle)
        else:
            try:    length = int(hdr['Content-Length'])
            except: length = None
            progress_obj.start(filename, url, os.path.basename(path), length)
            _do_grab(filename, fo, progress_obj, raw_throttle)
            progress_obj.end()

        fo.close()
        if close_connection:
            # try and close connection
            try: fo.close_connection()
            except AttributeError: pass
    except IOError, e:
        raise URLGrabError(4, _('IOError: %s') % (e, ))
    except OSError, e:
        raise URLGrabError(5, _('OSError: %s') % (e, ))
    except HTTPException, e:
        raise URLGrabError(7, _('HTTP Error (%s): %s') % \
                           (e.__class__.__name__, e))

    return filename

def _do_grab(filename, fo, progress_obj, raw_throttle):
    # note: raw_throttle should be a float if true.  That forces float
    #       division
    new_fo = open(filename, 'wb')
    bs = 1024*8
    size = 0
    if raw_throttle:
        # defining block_time here (and with bs) is a little faster
        # but it doesn't deal well with lots of small files - defining
        # it in the loop only delays each block accoring to its size
        # which is good if you have many files smaller than one bs.
        #block_time = bs/raw_throttle
        ttime = time.time()

    if not progress_obj is None: progress_obj.update(size)
    block = fo.read(bs)
    size = size + len(block)
    if not progress_obj is None: progress_obj.update(size)
    while block:
        if raw_throttle:
            block_time = len(block)/raw_throttle
            now = time.time()
            diff = block_time - (now - ttime)
            if diff > 0: time.sleep(diff)
            ttime = time.time()
        new_fo.write(block)
        block = fo.read(bs)
        size = size + len(block)
        if not progress_obj is None: progress_obj.update(size)
        
    new_fo.close()
    return size


def _do_simple_grab(filename, fo, progress_obj, raw_throttle):
    new_fo = open(filename, 'wb')
    bs = 1024*8
    size = 0

    block = fo.read(bs)
    size = size + len(block)
    while block:
        new_fo.write(block)
        block = fo.read(bs)
        size = size + len(block)
        
    new_fo.close()
    return size

#####################################################################
#  TESTING
def _main_test():
    import sys
    try: url, filename = sys.argv[1:3]
    except ValueError:
        print 'usage:', sys.argv[0], \
              '<url> <filename> [copy_local=0|1] [close_connection=0|1]'
        sys.exit()

    kwargs = {}
    for a in sys.argv[3:]:
        k, v = string.split(a, '=', 1)
        kwargs[k] = int(v)

    set_throttle(1.0)
    set_bandwidth(32 * 1024)
    print "throttle: %s,  throttle bandwidth: %s B/s" % (_throttle, _bandwidth)

    try: from progress_meter import text_progress_meter
    except ImportError, e: pass
    else: kwargs['progress_obj'] = text_progress_meter()

    try: name = apply(urlgrab, (url, filename), kwargs)
    except URLGrabError, e: print e
    else: print 'LOCAL FILE:', name


def _speed_test():
    #### speed test --- see comment below
    
    fancy_times = []
    simple_times = []
    global _do_grab
    _do_fancy_grab = _do_grab
    set_throttle(2**40) # throttle to 1 TB/s   :)

    try: from progress_meter import text_progress_meter
    except ImportError, e: 'not using progress meter'
    else: tpm = text_progress_meter(fo=open('/dev/null', 'w'))

    # to address concerns that the overhead from the progress meter
    # and throttling slow things down, we do this little test.  Make
    # sure /tmp/test holds an sane-sized file (like .2 MB)
    #
    # whith these commented out, you get the FULL overhead of the progress
    # meter and throttling, without the benefit: the meter is directed
    # to /dev/null and the throttle bandwidth is set EXTREMELY high.
    #
    # UN-commenting them actually turns them off, which is a more realistic
    # comparison - this is what it would be like in a real program with the
    # features turned off.  There is still SOME overhead, though (the
    # difference between _do_grab and _do_simple_grab, but it's really
    # just a couple of "if"s per downloaded block.
    
    tpm = None       ######## uncomment to turn off progress meter
    set_throttle(0)  ######## uncomment to turn off throttling
    
    # get it nicely cached before we start comparing
    for i in range(100):
        urlgrab('file:///tmp/test', '/tmp/test2', copy_local=1)

    for i in range(1000):
        _do_grab = _do_fancy_grab
        t = time.time()
        urlgrab('file:///tmp/test', '/tmp/test2', copy_local=1, progress_obj=tpm)
        fancy_times.append(1000 * (time.time() - t))

        _do_grab = _do_simple_grab
        t = time.time()
        urlgrab('file:///tmp/test', '/tmp/test2', copy_local=1, progress_obj=tpm)
        simple_times.append(1000* (time.time() - t))

    
    fancy_times.sort()
    fancy_mean = 0.0
    for i in fancy_times: fancy_mean = fancy_mean + i
    fancy_mean = fancy_mean/len(fancy_times)
    print '[fancy]  mean: %.3f ms, median: %.3f ms, min: %.3f ms, max: %.3f ms' % \
          (fancy_mean, fancy_times[int(len(fancy_times)/2)], min(fancy_times),
           max(fancy_times))

    simple_times.sort()
    simple_mean = 0.0
    for i in simple_times: simple_mean = simple_mean + i
    simple_mean = simple_mean/len(simple_times)
    print '[simple] mean: %.3f ms, median: %.3f ms, min: %.3f ms, max: %.3f ms' % \
          (simple_mean, simple_times[int(len(simple_times)/2)], min(simple_times),
           max(simple_times))

    close_all()

def _retry_test():
    import sys
    try: url, filename = sys.argv[1:3]
    except ValueError:
        print 'usage:', sys.argv[0], \
              '<url> <filename> [copy_local=0|1] [close_connection=0|1]'
        sys.exit()

    kwargs = {}
    for a in sys.argv[3:]:
        k, v = string.split(a, '=', 1)
        kwargs[k] = int(v)

    try: from progress_meter import text_progress_meter
    except ImportError, e: pass
    else: kwargs['progress_obj'] = text_progress_meter()

    global DEBUG
    #DEBUG = 1
    def cfunc(filename, hello, there='foo'):
        print hello, there
        import random
        rnum = random.random()
        if rnum < .5:
            print 'forcing retry'
            raise URLGrabError(-1, 'forcing retry')
        if rnum < .75:
            print 'forcing failure'
            raise URLGrabError(-2, 'forcing immediate failure')
        print 'success'
        return
        
    close_all()
    kwargs['checkfunc'] = (cfunc, ('hello',), {'there':'there'})
    try: name = apply(retrygrab, (url, filename), kwargs)
    except URLGrabError, e: print e
    else: print 'LOCAL FILE:', name

if __name__ == '__main__':
    set_user_agent('URLGrabber')
    _main_test()
    #_speed_test()
    #_retry_test()
