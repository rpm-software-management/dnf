#!/usr/bin/python -t
#
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

# Copyright 2002-2003 Michael D. Stenner, Ryan D. Tomayko

import unittest

from unittest import TestCase, TestSuite

import grabber
from grabber import URLGrabber, urlgrab, urlopen, urlread
from progress import text_progress_meter

def suite():
    return TestSuite((
        unittest.makeSuite(URLGrabberModuleTestCase,'test'),
        unittest.makeSuite(URLGrabberTestCase,'test') 
        ))

class URLGrabberModuleTestCase(TestCase):
    """Test module level functions defined in grabber.py"""
    def setUp(self):
        pass
        
    def tearDown(self):
        pass
    
    def test_urlopen(self):
        """grabber.urlopen()"""
        fo = grabber.urlopen('http://www.python.org')
        fo.close()
    
    def test_urlgrab(self):
        """grabber.urlgrab()"""
        filename = grabber.urlgrab('http://www.python.org', 
                                    filename='www.python.org')
    
    def test_urlread(self):
        """grabber.urlread()"""
        s = grabber.urlread('http://www.python.org')
       
class URLGrabberTestCase(TestCase):
    """Test grabber.URLGrabber class"""
    
    def setUp(self):
        self.meter = text_progress_meter( fo=open('/dev/null', 'w') )
        pass
    
    def tearDown(self):
        pass
    
    def testKeywordArgs(self):
        """grabber.URLGrabber.__init__() **kwargs handling.
        
        This is a simple test that just passes some arbitrary
        values into the URLGrabber constructor and checks that
        they've been set properly.
        """
        
        g = URLGrabber( progress_obj=self.meter,
                        throttle=0.9,
                        bandwidth=20,
                        retry=20,
                        retrycodes=[5,6,7],
                        copy_local=1,
                        close_connection=1,
                        user_agent='test ua/1.0',
                        proxies={'http' : 'http://www.proxy.com:9090'} )
        opts = g.opts
        
        self.assertEquals( opts.progress_obj, self.meter )
        self.assertEquals( opts.throttle, 0.9 )
        self.assertEquals( opts.bandwidth, 20 )
        self.assertEquals( opts.retry, 20 )
        self.assertEquals( opts.retrycodes, [5,6,7] )
        self.assertEquals( opts.copy_local, 1 )
        self.assertEquals( opts.close_connection, 1 )
        self.assertEquals( opts.user_agent, 'test ua/1.0' )
        self.assertEquals( opts.proxies, {'http' : 'http://www.proxy.com:9090'} )
        
    def test_parse_url(self):
        """grabber.URLGrabber._parse_url()"""
        
        g = URLGrabber()
        (url, parts) = g._parse_url('http://user:pass@host.com/path/part/basename.ext?arg1=val1&arg2=val2#hash')
        (scheme, host, path, parm, query, frag) = parts
        
        self.assertEquals('http://host.com/path/part/basename.ext?arg1=val1&arg2=val2#hash',url)
        self.assertEquals('http', scheme)
        self.assertEquals('host.com', host)
        self.assertEquals('/path/part/basename.ext', path)
        self.assertEquals('arg1=val1&arg2=val2', query)
        self.assertEquals('hash', frag)
        
    def test_parse_url_local_filename(self):
        """grabber.URLGrabber._parse_url('/local/file/path') """
        
        g = URLGrabber()
        (url, parts) = g._parse_url('/etc/redhat-release')
        (scheme, host, path, parm, query, frag) = parts
        
        self.assertEquals('file:///etc/redhat-release',url)
        self.assertEquals('file', scheme)
        self.assertEquals('', host)
        self.assertEquals('/etc/redhat-release', path)
        self.assertEquals('', query)
        self.assertEquals('', frag)
    
if __name__ == '__main__':
    grabber.DEBUG = 1
    runner = unittest.TextTestRunner(descriptions=1,verbosity=2)
    runner.run(suite())
     
