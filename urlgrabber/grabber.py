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

# Copyright 2002-2003 Michael D. Stenner

"""A high-level cross-protocol url-grabber.



GENERAL ARGUMENTS (kwargs)

copy_local is ignored except for file:// urls, in which case it
specifies whether urlgrab should still make a copy of the file, or
simply point to the existing copy. The module level default for this
option is 0. 

close_connection tells URLGrabber to close the connection after a
file has been transfered. This is ignored unless the download 
happens with the http keepalive handler (keepalive=1).  Otherwise, 
the connection is left open for further use. The module level 
default for this option is 0 (keepalive connections will not be 
closed).

keepalive specifies whether keepalive should be used for HTTP/1.1 
servers that support it. The module level default for this option is
1 (keepalive is enabled).

progress_obj is a class instance that supports the following methods:
po.start(filename, url, basename, length)
# length will be None if unknown
po.update(read) # read == bytes read so far
po.end()

throttle is a number - if it's an int, it's the bytes/second throttle
limit.  If it's a float, it is first multiplied by bandwidth.  If
throttle == 0, throttling is disabled.  If None, the module-level
default (which can be set on default_grabber.throttle) is used. 
See BANDWIDTH THROTTLING for more information.

bandwidth is the nominal max bandwidth in bytes/second.  If throttle
is a float and bandwidth == 0, throttling is disabled.  If None,
the module-level default (which can be set on default_grabber.bandwidth) 
is used. See BANDWIDTH THROTTLING for more information.

range is a tuple of the form (first_byte, last_byte) describing a 
byte range to retrieve. Either or both of the values may be specified. 
If first_byte is None, byte offset 0 is assumed. If last_byte is None,
the last byte available is assumed. Note that both first and last_byte 
values are inclusive so a range of (10,11) would return the 10th and 11th
byte of the resource.

user_agent is a string, usually of the form 'AGENT/VERSION' that is 
provided to HTTP servers in the User-agent header. The module level
default for this option is "urlgrabber/VERSION".

proxies is a dictionary mapping protocol schemes to proxy hosts. For
example, to use a proxy server on host "foo" port 3128 for http and
https URLs:
  proxies={ 'http' : 'http://foo:3128', 'https' : 'http://foo:3128' }
note that proxy authentication information may be provided using normal
URL constructs:
  proxies={ 'http' : 'http://user:host@foo:3128' }
Lastly, if proxies is None, the default environment settings will be 
used.

RETRY RELATED ARGUMENTS

retry is the number of times to retry the grab before bailing.  If 
this is zero, it will retry forever. This was intentional... really,
it was :). If this value is not supplied or is supplied but is None
retrying does not occur.

retrycodes is a sequence of errorcodes (values of e.errno) for which 
it should retry. See the doc on URLGrabError for more details on this. 
retrycodes defaults to [-1,2,4,5,6,7] if not specified explicitly.

checkfunc is a function to do additional checks. This defaults to None,
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


BANDWIDTH THROTTLING

urlgrabber supports throttling via two values: throttle and bandwidth
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

THROTTLING EXAMPLES:

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


SUGGESTED AUTHOR IMPLEMENTATION (THROTTLING)

While this is flexible, it's not extremely obvious to the user.  I
suggest you implement a float throttle as a percent to make the
distinction between absolute and relative throttling very explicit.

Also, you may want to convert the units to something more convenient
than bytes/second, such as kbps or kB/s, etc.

"""

import os
import os.path
import urlparse
import rfc822
import time
import string

DEBUG=1
VERSION='0.2'

try:
    from i18n import _
except ImportError, msg:
    def _(st): return st

try:
    from httplib import HTTPException
except ImportError, msg:
    HTTPException = None

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

try:
    # This is a convenient way to make keepalive optional.
    # Just rename the module so it can't be imported.
    from keepalive import HTTPHandler
except ImportError, msg:
    keepalive_handler = None
else:
    keepalive_handler = HTTPHandler()

# add in range support conditionally too
try:
    from byterange import HTTPRangeHandler,FileRangeHandler,FTPRangeHandler
    from byterange import range_tuple_normalize, range_tuple_to_header
except ImportError, msg:
    range_handlers = ()
    have_range = 0
else:
    range_handlers = (HTTPRangeHandler(), FileRangeHandler(), FTPRangeHandler())
    have_range = 1


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
      8  - Exceeded read limit (for urlread)
 
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

def urlgrab(url, filename=None, **kwargs):
    """grab the file at <url> and make a local copy at <filename>
    If filename is none, the basename of the url is used.
    urlgrab returns the filename of the local file, which may be different
    from the passed-in filename if the copy_local kwarg == 0.
    
    See module documentation for a description of possible kwargs.
    """
    return default_grabber.urlgrab(url, filename, **kwargs)

def urlopen(url, **kwargs):
    """open the url and return a file object
    If a progress object or throttle specifications exist, then
    a special file object will be returned that supports them.
    The file object can be treated like any other file object.
    
    See module documentation for a description of possible kwargs.
    """
    return default_grabber.urlopen(url, **kwargs)

def urlread(url, limit=None, **kwargs):
    """read the url into a string, up to 'limit' bytes
    If the limit is exceeded, an exception will be thrown.  Note that urlread
    is NOT intended to be used as a way of saying "I want the first N bytes"
    but rather 'read the whole file into memory, but don't use too much'
    
    See module documentation for a description of possible kwargs.
    """
    return default_grabber.urlread(url, limit, **kwargs)


class URLGrabberOptions:
    """Class to ease kwargs handling."""

    def __init__(self, **kwargs):
        """Initialize URLGrabberOptions object.
        Set default values for all options and then update options specified
        in kwargs.
        """
        # ensure defaults are present
        self.progress_obj = None
        self.throttle = 1.0
        self.bandwidth = 0
        self.retry = None
        self.retrycodes = [-1,2,4,5,6,7]
        self.checkfunc = None
        self.copy_local = 0
        self.close_connection = 0
        self.range = None
        self.user_agent = 'urlgrabber/%s' % VERSION
        self.keepalive = 1
        self.proxies = None
        # update all attributes with supplied kwargs
        self._set_attributes(**kwargs)
        
    def raw_throttle(self):
        """Calculate raw throttle value from throttle and bandwidth 
        values.
        """
        if self.throttle <= 0:  
            return 0
        elif type(self.throttle) == type(0): 
            return float(self.throttle)
        else: # throttle is a float
            return self.bandwidth * self.throttle
        
    def derive(self, **kwargs):
        """Copy this object and then override the specified options.
        This method does *not* return a copy if no kwargs are supplied.
        """
        if len(kwargs) > 0:
            from copy import copy
            clone = copy(self)
            clone._set_attributes(**kwargs)
            return clone
        else:
            return self
        
    def _set_attributes(self, **kwargs):
        """Update object attributes with those provided in kwargs."""
        self.__dict__.update(kwargs)
        if have_range and kwargs.has_key('range'):
            # normalize the supplied range value
            self.range = range_tuple_normalize(self.range)


class URLGrabber:
    """Provides easy opening of URLs with a variety of options.
    
    All options are specified as kwargs. Options may be specified when
    the class is created and may be overridden on a per request basis.
    
    New objects inherit default values from default_grabber.
    """
    
    def __init__(self, **kwargs):
        self.opts = URLGrabberOptions(**kwargs)
    
    def _retry(self, opts, func, *args):
        tries = 0
        while 1:
            tries = tries + 1
            try:
                return apply(func, (opts,) + args, {})
            except URLGrabError, e:
                if DEBUG: print 'EXCEPTION: %s' % e
                if (opts.retry is None) \
                    or (tries == opts.retry) \
                    or (e.errno not in opts.retrycodes): raise
    
    def urlopen(self, url, **kwargs):
        """open the url and return a file object

        If a progress object or throttle value specified when this 
        object was created, then  a special file object will be 
        returned that supports them. The file object can be treated 
        like any other file object.
        """
        opts = self.opts.derive(**kwargs)
        (url,parts) = self._parse_url(url) 
        def retryfunc(opts, url):
            return URLGrabberFileObject(url, filename=None, opts=opts)
        return self._retry(opts, retryfunc, url)
    
    def urlgrab(self, url, filename=None, **kwargs):
        """grab the file at <url> and make a local copy at <filename>

        If filename is none, the basename of the url is used.
    
        urlgrab returns the filename of the local file, which may be 
        different from the passed-in filename if copy_local == 0.
        
        """
        opts = self.opts.derive(**kwargs)
        (url, parts) = self._parse_url(url)
        (scheme, host, path, parm, query, frag) = parts
        
        if filename is None:
            filename = os.path.basename( path )
        
        if scheme == 'file' and not opts.copy_local:
            # just return the name of the local file - don't make a 
            # copy currently
            if not os.path.exists(path):
                raise URLGrabError(2, 
                      _('Local file does not exist: %s') % (path, ))
            elif not os.path.isfile(path):
                raise URLGrabError(3, 
                              _('Not a normal file: %s') % (path, ))
            else:
                return path
        
        def retryfunc(opts, url, filename):
            fo = URLGrabberFileObject(url, filename, opts)
            try:
                fo._do_grab()
                if not opts.checkfunc is None:
                    if callable(opts.checkfunc):
                        func, args, kwargs = opts.checkfunc, (), {}
                    else:
                        func, args, kwargs = opts.checkfunc
                    apply(func, (filename, )+args, kwargs)
            finally:
                fo.close()
            return filename
        
        return self._retry(opts, retryfunc, url, filename)
    
        
    def urlread(self, url, limit=None, **kwargs):
        """read the url into a string, up to 'limit' bytes

        If the limit is exceeded, an exception will be thrown.  Note
        that urlread is NOT intended to be used as a way of saying 
        "I want the first N bytes" but rather 'read the whole file 
        into memory, but don't use too much'
        
        """
        opts = self.opts.derive(**kwargs)
        (url, parts) = self._parse_url(url)
        if limit is not None:
            limit = limit + 1
            
        def retryfunc(opts, url, limit):
            fo = URLGrabberFileObject(url, filename=None, opts=opts)
            s = fo.read(limit)
            fo.close()
            return s
            
        s = self._retry(opts, retryfunc, url, limit)
        if limit and len(s) > limit:
            raise URLGrabError(8, 
                        _('Exceeded limit (%i): %s') % (limit, url))
        return s
        
    def _parse_url(self,url):
        """break up the url into its component parts

        This function disassembles a url and
        1) "normalizes" it, tidying it up a bit
        2) does any authentication stuff it needs to do

        it returns the (cleaned) url and a tuple of component parts
        """
        (scheme, host, path, parm, query, frag) = \
                                             urlparse.urlparse(url)
        if not scheme:
            url = 'file:' + url
            (scheme, host, path, parm, query, frag) = \
                                             urlparse.urlparse(url)
        path = os.path.normpath(path)
        
        if '@' in host and auth_handler and scheme in ['http', 'https']:
            try:
                # should we be using urllib.splituser and 
                # splitpasswd instead?
                user_password, host = string.split(host, '@', 1)
                user, password = string.split(user_password, ':', 1)
            except ValueError, e:
                raise URLGrabError(1, _('Bad URL: %s') % url)
            if DEBUG: print 'adding HTTP auth: %s, %s' % (user, password)
            auth_handler.add_password(None, host, user, password)
        
        parts = (scheme, host, path, parm, query, frag)
        url = urlparse.urlunparse(parts)
        return url, parts
        
# create the default URLGrabber used by urlXXX functions.
# NOTE: actual defaults are set in URLGrabberOptions
default_grabber = URLGrabber()
                            
class URLGrabberFileObject:
    """This is a file-object wrapper that supports progress objects 
    and throttling.

    This exists to solve the following problem: lets say you want to
    drop-in replace a normal open with urlopen.  You want to use a
    progress meter and/or throttling, but how do you do that without
    rewriting your code?  Answer: urlopen will return a wrapped file
    object that does the progress meter and-or throttling internally.
    """

    def __init__(self, url, filename, opts):
        self.url = url
        self.filename = filename
        self.opts = opts
        self.fo = None
        self._rbuf = ''
        self._rbufsize = 1024*8
        self._ttime = time.time()
        self._tsize = 0
        self._amount_read = 0
        self._opener = None
        self._do_open()
        
    def __getattr__(self, name):
        """This effectively allows us to wrap at the instance level.
        Any attribute not found in _this_ object will be searched for
        in self.fo.  This includes methods."""
        if hasattr(self.fo, name):
            return getattr(self.fo, name)
        raise AttributeError, name
    
    def _get_opener(self):
        """Build a urllib2 OpenerDirector based on request options."""
        if self._opener is None:
            handlers = []
            # if you specify a ProxyHandler when creating the opener
            # it _must_ come before all other handlers in the list or urllib2
            # chokes.
            if self.opts.proxies:
                handlers.append( urllib2.ProxyHandler( self.opts.proxies ) )
            if keepalive_handler and self.opts.keepalive:
                handlers.append( keepalive_handler )
            if range_handlers and self.opts.range:
                handlers.extend( range_handlers )
            if auth_handler:
                handlers.append( auth_handler )
            self._opener = urllib2.build_opener( *handlers )
        return self._opener
        
    def _do_open(self):
        # build request object if any options require setting headers.
        if have_urllib2:
            req = urllib2.Request(self.url)
            if have_range and self.opts.range:
                req.add_header('Range', range_tuple_to_header(self.opts.range))
            if self.opts.user_agent:
                req.add_header('User-agent', self.opts.user_agent)
        else:
            req = self.url
        opener = self._get_opener()
        (scheme, host, path, parm, query, frag) = urlparse.urlparse(self.url)
        
        try:
            fo = opener.open(req)
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
        
        if self.opts.progress_obj:
            try:    length = int(hdr['Content-Length'])
            except: length = None
            self.opts.progress_obj.start(self.filename, self.url, 
                                         os.path.basename(path), 
                                         length)
            self.opts.progress_obj.update(0)
        (self.fo, self.hdr) = (fo, hdr)
    
    def _do_grab(self):
        """dump the file to self.filename."""
        assert self.filename is not None
        new_fo = open(self.filename, 'wb')
        bs = 1024*8
        size = 0

        block = self.read(bs)
        size = size + len(block)
        while block:
            new_fo.write(block)
            block = self.read(bs)
            size = size + len(block)

        new_fo.close()
        try:
            modified_tuple  = self.hdr.getdate_tz('last-modified')
            modified_stamp  = rfc822.mktime_tz(modified_tuple)
            os.utime(self.filename, (modified_stamp, modified_stamp))
        except (TypeError,), e: pass

        return size
    
    def _fill_buffer(self, amt=None):
        """fill the buffer to contain at least 'amt' bytes by reading
        from the underlying file object.  If amt is None, then it will
        read until it gets nothing more.  It updates the progress meter
        and throttles after every self._rbufsize bytes."""
        # the _rbuf test is only in this first 'if' for speed.  It's not
        # logically necessary
        if self._rbuf and not amt is None:
            L = len(self._rbuf)
            if amt > L:
                amt = amt - L
            else:
                return

        # if we've made it here, then we don't have enough in the buffer
        # and we need to read more.

        buf = [self._rbuf]
        bufsize = len(self._rbuf)
        while amt is None or amt:
            # first, delay if necessary for throttling reasons
            if self.opts.raw_throttle():
                diff = self._tsize/self.opts.raw_throttle() - \
                       (time.time() - self._ttime)
                if diff > 0: time.sleep(diff)
                self._ttime = time.time()
                
            # now read some data, up to self._rbufsize
            if amt is None: readamount = self._rbufsize
            else:           readamount = min(amt, self._rbufsize)
            new = self.fo.read(readamount)
            newsize = len(new)
            if not newsize: break # no more to read

            if amt: amt = amt - newsize
            buf.append(new)
            bufsize = bufsize + newsize
            self._tsize = newsize
            self._amount_read = self._amount_read + newsize
            if self.opts.progress_obj:
                self.opts.progress_obj.update(self._amount_read)

        self._rbuf = string.join(buf, '')
        return

    def read(self, amt=None):
        self._fill_buffer(amt)
        if amt is None:
            s, self._rbuf = self._rbuf, ''
        else:
            s, self._rbuf = self._rbuf[:amt], self._rbuf[amt:]
        return s

    def readline(self, limit=-1):
        i = string.find(self._rbuf, '\n')
        while i < 0 and not (0 < limit <= len(self._rbuf)):
            L = len(self._rbuf)
            self._fill_buffer(L + self._rbufsize)
            if not len(self._rbuf) > L: break
            i = string.find(self._rbuf, '\n', L)

        if i < 0: i = len(self._rbuf)
        else: i = i+1
        if 0 <= limit < len(self._rbuf): i = limit

        s, self._rbuf = self._rbuf[:i], self._rbuf[i:]
        return s

    def close(self):
        if self.opts.progress_obj:
            self.opts.progress_obj.end()
        self.fo.close()
        if self.opts.close_connection:
            try: self.fo.close_connection()
            except: pass


#####################################################################
# DEPRECATED FUNCTIONS
def set_throttle(new_throttle):
    """Deprecated. Use: default_grabber.throttle = new_throttle"""
    default_grabber.throttle = new_throttle

def set_bandwidth(new_bandwidth):
    """Deprecated. Use: default_grabber.bandwidth = new_bandwidth"""
    default_grabber.bandwidth = new_bandwidth

def set_progress_obj(new_progress_obj):
    """Deprecated. Use: default_grabber.progress_obj = new_progress_obj"""
    default_grabber.progress_obj = new_progress_obj

def set_user_agent(new_user_agent):
    """Deprecated. Use: default_grabber.user_agent = new_user_agent"""
    default_grabber.user_agent = new_user_agent
    
def retrygrab(url, filename=None, copy_local=0, close_connection=0,
              progress_obj=None, throttle=None, bandwidth=None,
              numtries=3, retrycodes=[-1,2,4,5,6,7], checkfunc=None):
    """Deprecated. Use: urlgrab() with the retry arg instead"""
    kwargs = {'copy_local' :  copy_local, 
              'close_connection' : close_connection,
              'progress_obj' : progress_obj, 
              'throttle' : throttle, 
              'bandwidth' : bandwidth,
              'retry' : numtries,
              'retrycodes' : retrycodes,
              'checkfunc' : checkfunc 
              }
    return urlgrab(url, filename, **kwargs)

        
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
    print "throttle: %s,  throttle bandwidth: %s B/s" % (default_grabber.throttle, 
                                                        default_grabber.bandwidth)

    try: from progress import text_progress_meter
    except ImportError, e: pass
    else: kwargs['progress_obj'] = text_progress_meter()

    try: name = apply(urlgrab, (url, filename), kwargs)
    except URLGrabError, e: print e
    else: print 'LOCAL FILE:', name


def _speed_test():
    #### speed test --- see comment below
    import sys
    
    full_times = []
    raw_times = []
    set_throttle(2**40) # throttle to 1 TB/s   :)

    try:
        from progress import text_progress_meter
    except ImportError, e:
        tpm = None
        print 'not using progress meter'
    else:
        tpm = text_progress_meter(fo=open('/dev/null', 'w'))

    # to address concerns that the overhead from the progress meter
    # and throttling slow things down, we do this little test.  Make
    # sure /tmp/test holds a sanely-sized file (like .2 MB)
    #
    # using this test, you get the FULL overhead of the progress
    # meter and throttling, without the benefit: the meter is directed
    # to /dev/null and the throttle bandwidth is set EXTREMELY high.
    #
    # note: it _is_ even slower to direct the progress meter to a real
    # tty or file, but I'm just interested in the overhead from _this_
    # module.
    
    # get it nicely cached before we start comparing
    print 'pre-caching'
    for i in range(100):
        urlgrab('file:///tmp/test', '/tmp/test2',
                copy_local=1)

    reps = 1000
    for i in range(reps):
        print '\r%4i/%-4i' % (i, reps),
        sys.stdout.flush()
        t = time.time()
        urlgrab('file:///tmp/test', '/tmp/test2',
                copy_local=1, progress_obj=tpm)
        full_times.append(1000 * (time.time() - t))

        t = time.time()
        urlgrab('file:///tmp/test', '/tmp/test2',
                copy_local=1, progress_obj=None)
        raw_times.append(1000* (time.time() - t))
    print '\r'
    
    full_times.sort()
    full_mean = 0.0
    for i in full_times: full_mean = full_mean + i
    full_mean = full_mean/len(full_times)
    print '[full] mean: %.3f ms, median: %.3f ms, min: %.3f ms, max: %.3f ms' % \
          (full_mean, full_times[int(len(full_times)/2)], min(full_times),
           max(full_times))

    raw_times.sort()
    raw_mean = 0.0
    for i in raw_times: raw_mean = raw_mean + i
    raw_mean = raw_mean/len(raw_times)
    print '[raw]  mean: %.3f ms, median: %.3f ms, min: %.3f ms, max: %.3f ms' % \
          (raw_mean, raw_times[int(len(raw_times)/2)], min(raw_times),
           max(raw_times))

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

    try: from progress import text_progress_meter
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

def _file_object_test(filename=None):
    import random, cStringIO, sys
    if filename is None:
        filename = __file__
    print 'using file "%s" for comparisons' % filename
    fo = open(filename)
    s_input = fo.read()
    fo.close()

    for testfunc in [_test_file_object_smallread,
                     _test_file_object_readall,
                     _test_file_object_readline,
                     _test_file_object_readlines]:
        fo_input = cStringIO.StringIO(s_input)
        fo_output = cStringIO.StringIO()
        wrapper = URLGrabberFileObject(fo_input, None, 0)
        print 'testing %-30s ' % testfunc.__name__,
        testfunc(wrapper, fo_output)
        s_output = fo_output.getvalue()
        if s_output == s_input: print 'passed'
        else: print 'FAILED'
            
def _test_file_object_smallread(wrapper, fo_output):
    while 1:
        s = wrapper.read(23)
        fo_output.write(s)
        if not s: return

def _test_file_object_readall(wrapper, fo_output):
    s = wrapper.read()
    fo_output.write(s)

def _test_file_object_readline(wrapper, fo_output):
    while 1:
        s = wrapper.readline()
        fo_output.write(s)
        if not s: return

def _test_file_object_readlines(wrapper, fo_output):
    li = wrapper.readlines()
    fo_output.write(string.join(li, ''))

if __name__ == '__main__':
    _main_test()
    _speed_test()
    _retry_test()
    _file_object_test('test')
    
