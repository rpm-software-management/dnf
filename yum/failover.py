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

import random

class baseFailOverMethod:

    def __init__(self, repo):
        self.repo = repo
        self.failures = 0
    
    def get_serverurl(self, i=None):
        """Returns a serverurl based on this failover method or None 
           if complete failure.  If i is given it is a direct index
           to pull a server URL from instead of using the failures 
           counter."""
        return None
        
    def server_failed(self):
        "Tells the failover method that the current server is failed."
        self.failures = self.failures + 1
        
    def reset(self, i=0):
        "Reset the failures counter to a given index."
        self.failures = i

    def get_index(self):
        """Returns the current number of failures which is also the
           index into the list this object represents.  ger_serverurl()
           should always be used to translate an index into a URL
           as this object may change how indexs map.  (See RoundRobin)"""

        return self.failures
   
    def len(self):
        """Returns the how many URLs we've got to cycle through."""

        return len(self.repo.urls)
        
            

class priority(baseFailOverMethod):

    """Chooses server based on the first success in the list."""
    
    def get_serverurl(self, i=None):
        "Returns a serverurl based on this failover method or None if complete failure."
        
        if i == None:
            index = self.failures
        else:
            index = i
        
        if index >= len(self.repo.urls):
            return None
        
        return self.repo.urls[index]
        
        
    
class roundRobin(baseFailOverMethod):

    """Chooses server based on a round robin."""
    
    def __init__(self, repo):
        baseFailOverMethod.__init__(self, repo)
        random.seed()
        self.offset = random.randint(0, 37)
    
    def get_serverurl(self, i=None):
        "Returns a serverurl based on this failover method or None if complete failure."

        if i == None:
            index = self.failures
        else:
            index = i
        
        if index >= len(self.repo.urls):
            return None
        
        rr = (index + self.offset) % len(self.repo.urls)
        return self.repo.urls[rr]   

# SDG
