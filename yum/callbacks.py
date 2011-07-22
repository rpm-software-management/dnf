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

"""Classes for handling various callbacks."""

# imports

import logging 
from urlgrabber.progress import BaseMeter,format_time,format_number


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
    """A class to handle callbacks from
    :func:`YumBase.processTransaction`.
    """
    def __init__(self):
        self.logger = logging.getLogger('yum.verbose.ProcessTrasactionBaseCallback')
        
    def event(self,state,data=None):
        """Handle an event by logging it.

        :param state: a number indicating the type of callback
        :param data: data associated with the callback
        """
        if state in PT_MESSAGES.keys():
            self.logger.info(PT_MESSAGES[state])

class ProcessTransNoOutputCallback:
    """A class to handle callbacks from
    :func:`YumBase.processTransaction`, without logging them.
    """
    def __init__(self):
        pass
         
    def event(self,state,data=None):
        """Handle an event.

        :param state: a number indicating the type of callback
        :param data: data associated with the callback
        """
        pass
    
class DownloadBaseCallback( BaseMeter ):
    """This is a base class that can be extended to implement a custom
    download progress handler to be used with
    :func:`YumBase.repos.setProgressBar`.
    
    Example::
    
       from yum.callbacks import DownloadBaseCallback
       
       class MyDownloadCallback(  DownloadBaseCallback ):
   
           def updateProgress(self,name,frac,fread,ftime):
               '''
               Update the progressbar
               @param name: filename
               @param frac: Progress fracment (0 -> 1)
               @param fread: formated string containing BytesRead
               @param ftime : formated string containing remaining or elapsed time
               '''
               pct = int( frac*100 )
               print " %s : %s " % (name,pct)
   
   
       if __name__ == '__main__':
           my = YumBase()
           my.doConfigSetup()
           dnlcb = MyDownloadCallback()
           my.repos.setProgressBar( dnlcb )
           for pkg in my.pkgSack:
               print pkg.name
       """
    def __init__(self):
        BaseMeter.__init__( self )
        self.totSize = ""   # Total size to download in a formatted string (Kb, MB etc)
        
    def update( self, amount_read, now=None ):
        """Update the status bar.

        :param amount_read: the amount of data, in bytes, that has been read
        :param now: the current time in seconds since the epoch.  If
           *now* is not given, the output of :func:`time.time()` will
           be used.
        """
        BaseMeter.update( self, amount_read, now )

    def _do_start( self, now=None ):
        name = self._getName()
        self.updateProgress(name,0.0,"","")
        if not self.size is None:
            self.totSize = format_number( self.size )

    def _do_update( self, amount_read, now=None ):
        fread = format_number( amount_read )
        name = self._getName()
        if self.size is None:
            # Elapsed time
            etime = self.re.elapsed_time()
            fetime = format_time( etime )
            frac = 0.0
            self.updateProgress(name,frac,fread,fetime)
        else:
            # Remaining time
            rtime = self.re.remaining_time()
            frtime = format_time( rtime )
            frac = self.re.fraction_read()
            self.updateProgress(name,frac,fread,frtime)


    def _do_end( self, amount_read, now=None ):
        total_time = format_time( self.re.elapsed_time() )
        total_size = format_number( amount_read )
        name = self._getName()
        self.updateProgress(name,1.0,total_size,total_time)

    def _getName(self):
        '''
        Get the name of the package being downloaded
        '''
        if self.text and type( self.text ) == type( "" ):
            name = self.text
        else:
            name = self.basename
        return name

    def updateProgress(self,name,frac,fread,ftime):
        """Update the progressbar.  This method should be overridden
        by subclasses to implement the handler.

        :param name: the name of the filed being downloaded
        :param frac: number between 0 and 1 representing the fraction
            fraction of the file that has been downloaded
        :param fread: formatted string containing the number of bytes read
        :param ftime: formatted string containing remaining or elapsed time

        """
        pass
        
