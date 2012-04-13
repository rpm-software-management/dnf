#!/usr/bin/python
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
# Copyright 2003 Jack Neely, NC State University

# Here we define a base class for failover methods.  The idea here is that each
# failover method uses a class derived from the base class so yum only has to
# worry about calling get_serverurl() and server_failed() and these classes will 
# figure out which URL to cough up based on the failover method.

"""Classes for handling failovers for server URLs."""

import random

class baseFailOverMethod:
    """A base class to provide a failover to switch to a new server if
    the current one fails.
    """
    def __init__(self, repo):
        self.repo = repo
        self.failures = 0
    
    def get_serverurl(self, i=None):
        """Return a server URL based on this failover method, or None
        if there is a complete failure.  This method should always be
        used to translate an index into a URL, as this object may
        change how indexes map.

        :param i: if given, this is the index of the server URL to
           return, instead of using the failures counter
        :return: the next server URL
        """
        return None
        
    def server_failed(self):
        """Notify the failover method that the current server has
        failed.
        """
        self.failures = self.failures + 1
        
    def reset(self, i=0):
        """Reset the failures counter to the given index.

        :param i: the index to reset the failures counter to
        """
        self.failures = i

    def get_index(self):
        """Return the current number of failures, which is also the
        current index into the list of URLs that this object
        represents.  :fun:`get_serverurl` should always be used to
        translate an index into a URL, as this object may change how
        indexes map.

        :return: the current number of failures, which is also the
           current index   
        """
        return self.failures
   
    def len(self):
        """Return the total number of URLs available to cycle through
        in this object.

        :return: the total number of URLs available
        """
        return len(self.repo.urls)
        
            

class priority(baseFailOverMethod):
    """A class to provide a failover to switch to a new server
    if the current one fails.  This classes chooses the next server
    based on the first success in the list of servers.
    """
    def get_serverurl(self, i=None):
        """Return the next successful server URL in the list, or None
        if there is a complete failure.  This method should always be
        used to translate an index into a URL, as this object may
        change how indexes map.

        :param i: if given, this is the index of the server URL to
           return, instead of using the failures counter
        :return: the next server URL
        """
        if i == None:
            index = self.failures
        else:
            index = i
        
        if index >= len(self.repo.urls):
            return None
        
        return self.repo.urls[index]
        
        
    
class roundRobin(baseFailOverMethod):
    """A class to provide a failover to switch to a new server
    if the current one fails.  When an object of this class is
    created, it selects a random place in the list of URLs to begin
    with, then each time :func:`get_serveurl` is called, the next URL
    in the list is returned, cycling back to the beginning of the list
    after the end is reached.
    """
    def __init__(self, repo):
        baseFailOverMethod.__init__(self, repo)
        random.seed()
        self.offset = random.randint(0, 37)
    
    def get_serverurl(self, i=None):
        """Return the next successful server URL in the list, using
        the round robin scheme, or None if there is a complete
        failure.  This method should always be used to translate an
        index into a URL, as this object may change how indexes map.

        :param i: if given, this is the index of the server URL to
           return, instead of using the failures counter
        :return: the next server URL
        """
        if i == None:
            index = self.failures
        else:
            index = i
        
        if index >= len(self.repo.urls):
            return None
        
        rr = (index + self.offset) % len(self.repo.urls)
        return self.repo.urls[rr]   

# SDG
