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

"""A high-level cross-protocol url-grabber.

GENERAL ARGUMENTS (kwargs)

  Where possible, the module-level default is indicated, and legal
  values are provided.

  copy_local = 0   [0|1]

    ignored except for file:// urls, in which case it specifies
    whether urlgrab should still make a copy of the file, or simply
    point to the existing copy. The module level default for this
    option is 0.

  close_connection = 0   [0|1]

    tells URLGrabber to close the connection after a file has been
    transfered. This is ignored unless the download happens with the
    http keepalive handler (keepalive=1).  Otherwise, the connection
    is left open for further use. The module level default for this
    option is 0 (keepalive connections will not be closed).

  keepalive = 1   [0|1]

    specifies whether keepalive should be used for HTTP/1.1 servers
    that support it. The module level default for this option is 1
    (keepalive is enabled).

  progress_obj = None

    a class instance that supports the following methods:
      po.start(filename, url, basename, length, text)
      # length will be None if unknown
      po.update(read) # read == bytes read so far
      po.end()

  text = None
  
    specifies an alternativ text item in the beginning of the progress
    bar line. If not given, the basename of the file is used.

  throttle = 1.0

    a number - if it's an int, it's the bytes/second throttle limit.
    If it's a float, it is first multiplied by bandwidth.  If throttle
    == 0, throttling is disabled.  If None, the module-level default
    (which can be set on default_grabber.throttle) is used. See
    BANDWIDTH THROTTLING for more information.

  timeout = None

    a positive float expressing the number of seconds to wait for socket
    operations. If the value is None or 0.0, socket operations will block
    forever. Setting this option causes urlgrabber to call the settimeout
    method on the Socket object used for the request. See the Python
    documentation on settimeout for more information.
    http://www.python.org/doc/current/lib/socket-objects.html

  bandwidth = 0

    the nominal max bandwidth in bytes/second.  If throttle is a float
    and bandwidth == 0, throttling is disabled.  If None, the
    module-level default (which can be set on
    default_grabber.bandwidth) is used. See BANDWIDTH THROTTLING for
    more information.

  range = None

    a tuple of the form (first_byte, last_byte) describing a byte
    range to retrieve. Either or both of the values may set to
    None. If first_byte is None, byte offset 0 is assumed. If
    last_byte is None, the last byte available is assumed. Note that
    the range specification is python-like in that (0,10) will yeild
    the first 10 bytes of the file.

    If set to None, no range will be used.
    
  reget = None   [None|'simple'|'check_timestamp']

    whether to attempt to reget a partially-downloaded file.  Reget
    only applies to .urlgrab and (obviously) only if there is a
    partially downloaded file.  Reget has two modes:

      'simple' -- the local file will always be trusted.  If there
        are 100 bytes in the local file, then the download will always
        begin 100 bytes into the requested file.

      'check_timestamp' -- the timestamp of the server file will be
        compared to the timestamp of the local file.  ONLY if the
        local file is newer than or the same age as the server file
        will reget be used.  If the server file is newer, or the
        timestamp is not returned, the entire file will be fetched.

    NOTE: urlgrabber can do very little to verify that the partial
    file on disk is identical to the beginning of the remote file.
    You may want to either employ a custom "checkfunc" or simply avoid
    using reget in situations where corruption is a concern.

  user_agent = 'urlgrabber/VERSION'

    a string, usually of the form 'AGENT/VERSION' that is provided to
    HTTP servers in the User-agent header. The module level default
    for this option is "urlgrabber/VERSION".

  proxies = None

    a dictionary that maps protocol schemes to proxy hosts. For
    example, to use a proxy server on host "foo" port 3128 for http
    and https URLs:
      proxies={ 'http' : 'http://foo:3128', 'https' : 'http://foo:3128' }
    note that proxy authentication information may be provided using
    normal URL constructs:
      proxies={ 'http' : 'http://user:host@foo:3128' }
    Lastly, if proxies is None, the default environment settings will
    be used.

  prefix = None

    a url prefix that will be prepended to all requested urls.  For
    example:
      g = URLGrabber(prefix='http://foo.com/mirror/')
      g.urlgrab('some/file.txt')
      ## this will fetch 'http://foo.com/mirror/some/file.txt'
    This option exists primarily to allow identical behavior to
    MirrorGroup (and derived) instances.  Note: a '/' will be inserted
    if necessary, so you cannot specify a prefix that ends with a
    partial file or directory name.

  opener = None
  
    Overrides the default urllib2.OpenerDirector provided to urllib2
    when making requests.  This option exists so that the urllib2
    handler chain may be customized.  Note that the range, reget,
    proxy, and keepalive features require that custom handlers be
    provided to urllib2 in order to function properly.  If an opener
    option is provided, no attempt is made by urlgrabber to ensure
    chain integrity.  You are responsible for ensuring that any
    extension handlers are present if said features are required.
    
RETRY RELATED ARGUMENTS

  retry = None

    the number of times to retry the grab before bailing.  If this is
    zero, it will retry forever. This was intentional... really, it
    was :). If this value is not supplied or is supplied but is None
    retrying does not occur.

  retrycodes = [-1,2,4,5,6,7]

    a sequence of errorcodes (values of e.errno) for which it should
    retry. See the doc on URLGrabError for more details on
    this. retrycodes defaults to [-1,2,4,5,6,7] if not specified
    explicitly.

  checkfunc = None

    a function to do additional checks. This defaults to None, which
    means no additional checking.  The function should simply return
    on a successful check.  It should raise URLGrabError on an
    unsuccessful check.  Raising of any other exception will be
    considered immediate failure and no retries will occur.

    If it raises URLGrabError, the error code will determine the retry
    behavior.  Negative error numbers are reserved for use by these
    passed in functions, so you can use many negative numbers for
    different types of failure.  By default, -1 results in a retry,
    but this can be customized with retrycodes.

    If you simply pass in a function, it will be given exactly one
    argument: a CallbackObject instance with the .url attribute
    defined and either .filename (for urlgrab) or .data (for urlread).
    For urlgrab, .filename is the name of the local file.  For
    urlread, .data is the actual string data.  If you need other
    arguments passed to the callback (program state of some sort), you
    can do so like this:

      checkfunc=(function, ('arg1', 2), {'kwarg': 3})

    if the downloaded file has filename /tmp/stuff, then this will
    result in this call (for urlgrab):

      function(obj, 'arg1', 2, kwarg=3)
      # obj.filename = '/tmp/stuff'
      # obj.url = 'http://foo.com/stuff'
      
    NOTE: both the "args" tuple and "kwargs" dict must be present if
    you use this syntax, but either (or both) can be empty.

  failure_callback = None

    The callback that gets called during retries when an attempt to
    fetch a file fails.  The syntax for specifying the callback is
    identical to checkfunc, except for the attributes defined in the
    CallbackObject instance.  In this case, it will have .exception
    and .url defined.  As you might suspect, .exception is the
    exception that was raised.

    The callback is present primarily to inform the calling program of
    the failure, but if it raises an exception (including the one it's
    passed) that exception will NOT be caught and will therefore cause
    future retries to be aborted.

BANDWIDTH THROTTLING

  urlgrabber supports throttling via two values: throttle and
  bandwidth Between the two, you can either specify and absolute
  throttle threshold or specify a theshold as a fraction of maximum
  available bandwidth.

  throttle is a number - if it's an int, it's the bytes/second
  throttle limit.  If it's a float, it is first multiplied by
  bandwidth.  If throttle == 0, throttling is disabled.  If None, the
  module-level default (which can be set with set_throttle) is used.

  bandwidth is the nominal max bandwidth in bytes/second.  If throttle
  is a float and bandwidth == 0, throttling is disabled.  If None, the
  module-level default (which can be set with set_bandwidth) is used.

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

# $Id$

import os
import os.path
import urlparse
import rfc822
import time
import string
import urllib
import urllib2
from stat import *  # S_* and ST_*

try:
    exec('from ' + (__name__.split('.'))[0] + ' import __version__')
except:
    __version__ = '???'

auth_handler = urllib2.HTTPBasicAuthHandler( \
     urllib2.HTTPPasswordMgrWithDefaultRealm())

DEBUG=0

try:
    from i18n import _
except ImportError, msg:
    def _(st): return st

try:
    from httplib import HTTPException
except ImportError, msg:
    HTTPException = None

try:
    # This is a convenient way to make keepalive optional.
    # Just rename the module so it can't be imported.
    from keepalive import HTTPHandler
except ImportError, msg:
    keepalive_handler = None
else:
    keepalive_handler = HTTPHandler()

try:
    # add in range support conditionally too
    from urlgrabber.byterange import HTTPRangeHandler, FileRangeHandler, \
         FTPRangeHandler, range_tuple_normalize, range_tuple_to_header, \
         RangeError
except ImportError, msg:
    range_handlers = ()
    RangeError = None
    have_range = 0
else:
    range_handlers = (HTTPRangeHandler(), FileRangeHandler(), FTPRangeHandler())
    have_range = 1


# check whether socket timeout support is available (Python >= 2.3)
import socket
try:
    TimeoutError = socket.timeout
    have_socket_timeout = True
except AttributeError:
    TimeoutError = None
    have_socket_timeout = False

class URLGrabError(IOError):
    """
    URLGrabError error codes:

      URLGrabber error codes (0 -- 255)
        0    - everything looks good (you should never see this)
        1    - malformed url
        2    - local file doesn't exist
        3    - request for non-file local file (dir, etc)
        4    - IOError on fetch
        5    - OSError on fetch
        6    - no content length header when we expected one
        7    - HTTPException
        8    - Exceeded read limit (for urlread)
        9    - Requested byte range not satisfiable.
        10   - Byte range requested, but range support unavailable
        11   - Illegal reget mode
        12   - Socket timeout.

      MirrorGroup error codes (256 -- 511)
        256  - No more mirrors left to try

      Custom (non-builtin) classes derived from MirrorGroup (512 -- 767)
        [ this range reserved for application-specific error codes ]

      Retry codes (< 0)
        -1   - retry the download, unknown reason

    Note: to test which group a code is in, you can simply do integer
    division by 256: e.errno / 256

    Negative codes are reserved for use by functions passed in to
    retrygrab with checkfunc.  The value -1 is built in as a generic
    retry code and is already included in the retrycodes list.
    Therefore, you can create a custom check function that simply
    returns -1 and the fetch will be re-tried.  For more customized
    retries, you can use other negative number and include them in
    retry-codes.  This is nice for outputting useful messages about
    what failed.

    You can use these error codes like so:
      try: urlgrab(url)
      except URLGrabError, e:
         if e.errno == 3: ...
           # or
         print e.strerror
           # or simply
         print e  #### print '[Errno %i] %s' % (e.errno, e.strerror)
    """
    pass

class CallbackObject:
    """Container for returned callback data.

    This is currently a dummy class into which urlgrabber can stuff
    information for passing to callbacks.  This way, the prototype for
    all callbacks is the same, regardless of the data that will be
    passed back.  Any function that accepts a callback function as an
    argument SHOULD document what it will define in this object.

    It is possible that this class will have some greater
    functionality in the future.
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

    def __init__(self, delegate=None, **kwargs):
        """Initialize URLGrabberOptions object.
        Set default values for all options and then update options specified
        in kwargs.
        """
        self.delegate = delegate
        if delegate is None:
            self._set_defaults()
        self._set_attributes(**kwargs)
    
    def __getattr__(self, name):
        if self.delegate and hasattr(self.delegate, name):
            return getattr(self.delegate, name)
        raise AttributeError, name
    
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
        """Create a derived URLGrabberOptions instance.
        This method creates a new instance and overrides the
        options specified in kwargs.
        """
        return URLGrabberOptions(delegate=self, **kwargs)
        
    def _set_attributes(self, **kwargs):
        """Update object attributes with those provided in kwargs."""
        self.__dict__.update(kwargs)
        if have_range and kwargs.has_key('range'):
            # normalize the supplied range value
            self.range = range_tuple_normalize(self.range)
        if not self.reget in [None, 'simple', 'check_timestamp']:
            raise URLGrabError(11, _('Illegal reget mode: %s') \
                               % (self.reget, ))

    def _set_defaults(self):
        """Set all options to their default values. 
        When adding new options, make sure a default is
        provided here.
        """
        self.progress_obj = None
        self.throttle = 1.0
        self.bandwidth = 0
        self.retry = None
        self.retrycodes = [-1,2,4,5,6,7]
        self.checkfunc = None
        self.copy_local = 0
        self.close_connection = 0
        self.range = None
        self.user_agent = 'urlgrabber/%s' % __version__
        self.keepalive = 1
        self.proxies = None
        self.reget = None
        self.failure_callback = None
        self.prefix = None
        self.opener = None
        self.cache_openers = True
        self.timeout = None
        self.text = None
 
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
                if opts.failure_callback:
                    cb_func, cb_args, cb_kwargs = \
                          self._make_callback(opts.failure_callback)
                    # this is a little icky - for now, the first element
                    # of args is the url.  we might consider a way to tidy
                    # that up, though
                    obj = CallbackObject()
                    obj.exception = e
                    obj.url = args[0]
                    cb_func(obj, *cb_args, **cb_kwargs)
    
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
            if scheme in [ 'http', 'https' ]:
                filename = os.path.basename( urllib.unquote(path) )
            else:
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
            elif not opts.range:
                return path
        
        def retryfunc(opts, url, filename):
            fo = URLGrabberFileObject(url, filename, opts)
            try:
                fo._do_grab()
                if not opts.checkfunc is None:
                    cb_func, cb_args, cb_kwargs = \
                             self._make_callback(opts.checkfunc)
                    obj = CallbackObject()
                    obj.filename = filename
                    obj.url = url
                    apply(cb_func, (obj, )+cb_args, cb_kwargs)
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
            s = ''
            try:
                # this is an unfortunate thing.  Some file-like objects
                # have a default "limit" of None, while the built-in (real)
                # file objects have -1.  They each break the other, so for
                # now, we just force the default if necessary.
                if limit is None: s = fo.read()
                else: s = fo.read(limit)

                if not opts.checkfunc is None:
                    cb_func, cb_args, cb_kwargs = \
                             self._make_callback(opts.checkfunc)
                    obj = CallbackObject()
                    obj.data = s
                    obj.url = url
                    apply(cb_func, (obj, )+cb_args, cb_kwargs)
            finally:
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
        if self.opts.prefix:
            p = self.opts.prefix
            if p[-1] == '/' or url[0] == '/': url = p + url
            else: url = p + '/' + url
            
        (scheme, host, path, parm, query, frag) = \
                                             urlparse.urlparse(url)
        if not scheme:
            if not url[0] == '/': url = os.path.abspath(url)
            url = 'file:' + url
            (scheme, host, path, parm, query, frag) = \
                                             urlparse.urlparse(url)
        path = os.path.normpath(path)
        if scheme in ['http', 'https']: path = urllib.quote(path)
        if '@' in host and auth_handler and scheme in ['http', 'https']:
            try:
                user_pass, host = host.split('@', 1)
                if ':' in user_pass: user, password = user_pass.split(':', 1)
            except ValueError, e:
                raise URLGrabError(1, _('Bad URL: %s') % url)
            if DEBUG: print 'adding HTTP auth: %s, %s' % (user, password)
            auth_handler.add_password(None, host, user, password)
        parts = (scheme, host, path, parm, query, frag)
        url = urlparse.urlunparse(parts)
        return url, parts
        
    def _make_callback(self, callback_obj):
        if callable(callback_obj):
            return callback_obj, (), {}
        else:
            return callback_obj

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
        if self.opts.opener:
            return self.opts.opener
        elif self._opener is None:
            handlers = []
            # if you specify a ProxyHandler when creating the opener
            # it _must_ come before all other handlers in the list or urllib2
            # chokes.
            if self.opts.proxies:
                handlers.append( CachedProxyHandler(self.opts.proxies) )
            if keepalive_handler and self.opts.keepalive:
                handlers.append( keepalive_handler )
            if range_handlers and (self.opts.range or self.opts.reget):
                handlers.extend( range_handlers )
            handlers.append( auth_handler )
            if self.opts.cache_openers:
              self._opener = CachedOpenerDirector(*handlers)
            else:
              self._opener = urllib2.build_opener(*handlers)
            # OK, I don't like to do this, but otherwise, we end up with
            # TWO user-agent headers.
            self._opener.addheaders = []
        return self._opener
        
    def _do_open(self):
        opener = self._get_opener()

        # build request object
        req = urllib2.Request(self.url)
        if self.opts.user_agent:
            req.add_header('User-agent', self.opts.user_agent)

        self._build_range(req) # take care of reget and byterange stuff
        fo, hdr = self._make_request(req, opener)
        if self.reget_time and self.opts.reget == 'check_timestamp':
            fetch_again = 0
            try:
                modified_tuple  = hdr.getdate_tz('last-modified')
                modified_stamp  = rfc822.mktime_tz(modified_tuple)
                if modified_stamp > self.reget_time: fetch_again = 1
            except (TypeError,):
                fetch_again = 1
            
            if fetch_again:
                # the server version is newer than the (incomplete) local
                # version, so we should abandon the version we're getting
                # and fetch the whole thing again.
                fo.close()
                self.opts.reget = None
                del req.headers['Range']
                self._build_range(req)
                fo, hdr = self._make_request(req, opener)

        (scheme, host, path, parm, query, frag) = urlparse.urlparse(self.url)
        if not (self.opts.progress_obj or self.opts.raw_throttle() \
                or self.opts.timeout):
            # if we're not using the progress_obj, throttling, or timeout
            # we can get a performance boost by going directly to
            # the underlying fileobject for reads.
            self.read = fo.read
            if hasattr(fo, 'readline'):
                self.readline = fo.readline
        elif self.opts.progress_obj:
            try:    length = int(hdr['Content-Length'])
            except: length = None
            self.opts.progress_obj.start(str(self.filename), self.url, 
                                         os.path.basename(path), 
                                         length,
                                         text=self.opts.text)
            self.opts.progress_obj.update(0)
        (self.fo, self.hdr) = (fo, hdr)
    
    def _build_range(self, req):
        self.reget_time = None
        self.append = 0
        reget_length = 0
        rt = None
        if have_range and self.opts.reget and type(self.filename) == type(''):
            # we have reget turned on and we're dumping to a file
            try:
                s = os.stat(self.filename)
            except OSError:
                pass
            else:
                self.reget_time = s[ST_MTIME]
                reget_length = s[ST_SIZE]
                rt = reget_length, ''
                self.append = 1
                
        if self.opts.range:
            if not have_range:
                raise URLGrabError(10, _('Byte range requested but range '\
                                         'support unavailable'))
            rt = self.opts.range
            if rt[0]: rt = (rt[0] + reget_length, rt[1])

        if rt:
            header = range_tuple_to_header(rt)
            if header: req.add_header('Range', header)

    def _make_request(self, req, opener):
        try:
            if have_socket_timeout and self.opts.timeout:
                old_to = socket.getdefaulttimeout()
                socket.setdefaulttimeout(self.opts.timeout)
                try:
                    fo = opener.open(req)
                finally:
                    socket.setdefaulttimeout(old_to)
            else:
                fo = opener.open(req)
            hdr = fo.info()
        except ValueError, e:
            raise URLGrabError(1, _('Bad URL: %s') % (e, ))
        except RangeError, e:
            raise URLGrabError(9, _('%s') % (e, ))
        except IOError, e:
            if hasattr(e, 'reason') and have_socket_timeout and \
                   isinstance(e.reason, TimeoutError):
                raise URLGrabError(12, _('Timeout: %s') % (e, ))
            else:
                raise URLGrabError(4, _('IOError: %s') % (e, ))
        except OSError, e:
            raise URLGrabError(5, _('OSError: %s') % (e, ))
        except HTTPException, e:
            raise URLGrabError(7, _('HTTP Error (%s): %s') % \
                            (e.__class__.__name__, e))
        else:
            return (fo, hdr)
        
    def _do_grab(self):
        """dump the file to self.filename."""
        if self.append: new_fo = open(self.filename, 'ab')
        else: new_fo = open(self.filename, 'wb')
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
            try:
                new = self.fo.read(readamount)
            except socket.error, e:
                raise URLGrabError(4, _('Socket Error: %s') % (e, ))
            except TimeoutError, e:
                raise URLGrabError(12, _('Timeout: %s') % (e, ))
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
            self.opts.progress_obj.end(self._amount_read)
        self.fo.close()
        if self.opts.close_connection:
            try: self.fo.close_connection()
            except: pass

_handler_cache = []
def CachedOpenerDirector(*handlers):
    for (cached_handlers, opener) in _handler_cache:
        if cached_handlers == handlers:
            for handler in opener.handlers:
                handler.add_parent(opener)
            return opener
    opener = urllib2.build_opener(*handlers)
    _handler_cache.append( (handlers, opener) )
    return opener

_proxy_cache = []
def CachedProxyHandler(proxies):
    for (pdict, handler) in _proxy_cache:
        if pdict == proxies:
            return handler
    handler = urllib2.ProxyHandler(proxies)
    _proxy_cache.append( (proxies,handler) )


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
    _retry_test()
    _file_object_test('test')
    
