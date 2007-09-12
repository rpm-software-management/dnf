#!/usr/bin/python -tt
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

# imports

import logging 

# ProcessTransaction States

PT_DOWNLOAD        = 10    # Start Download
PT_DOWNLOAD_PKGS   = 11    # Packages to download
PT_GPGCHECK        = 20    # Start Checkin Package Signatures
PT_TEST_TRANS      = 30    # Start Test Transaction
PT_TRANSACTION     = 40    # Start Transaction

PT_MESSAGES = { PT_DOWNLOAD    : "Downloading Packages",
                PT_GPGCHECK    : "Check Package Signatures",
                PT_TEST_TRANS  : "Running Test Transaction",
                PT_TRANSACTION : "Running Transaction"}



class ProcessTransBaseCallback:
    
    def __init__(self):
        self.logger = logging.getLogger('yum.verbose.ProcessTrasactionBaseCallback')
        
    def event(self,state,data=None):
        if state in PT_MESSAGES.keys():
            self.logger.info(PT_MESSAGES[state])

class ProcessTransNoOutputCallback:
    def __init__(self):
        pass
         
    def event(self,state,data=None):
        pass
        
