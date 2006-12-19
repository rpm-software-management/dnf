#!/usr/bin/python -t
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
# Copyright 2005 Duke University 


import sys
import locale
import logging
import time # test purposes only

from yum import Errors
from yum import plugins
from yum import logginglevels
import cli


def main(args):
    """This does all the real work"""

    def exUserCancel():
        logger.critical('\n\nExiting on user cancel')
        unlock()
        sys.exit(1)

    def exIOError(e):
        if e.errno == 32:
            logger.critical('\n\nExiting on Broken Pipe')
        unlock()
        sys.exit(1)

    def exPluginExit(e):
        '''Called when a plugin raises PluginYumExit.

        Log the plugin's exit message if one was supplied.
        '''
        exitmsg = str(e)
        if exitmsg:
            logger.warn('\n\n%s', exitmsg)
        unlock()
        sys.exit(1)

    def exFatal(e):
        logger.critical('\n\n%s', str(e))
        unlock()
        sys.exit(1)

    def unlock():
        try:
            base.closeRpmDB()
            base.doUnlock()
        except Errors.LockError, e:
            sys.exit(200)

    logger = logging.getLogger("yum.main")
    verbose_logger = logging.getLogger("yum.verbose.main")

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error, e:
        # default to C locale if we get a failure.
        print >> sys.stderr, 'Failed to set locale, defaulting to C'
        locale.setlocale(locale.LC_ALL, 'C')
        
    # our core object for the cli
    base = cli.YumBaseCli()

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        base.getOptionsConfig(args)
    except plugins.PluginYumExit, e:
        exPluginExit(e)
    except Errors.YumBaseError, e:
        exFatal(e)
    try:
        base.doLock()
    except Errors.LockError, e:
        logger.critical('%s', e.msg)
        sys.exit(200)

    try:
        result, resultmsgs = base.doCommands()
    except plugins.PluginYumExit, e:
        exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [str(e)]
    except KeyboardInterrupt:
        exUserCancel()
    except IOError, e:
        exIOError(e)

    # Act on the command/shell result
    if result == 0:
        # Normal exit 
        for msg in resultmsgs:
            verbose_logger.log(logginglevels.INFO_2, '%s', msg)
        unlock()
        sys.exit(0)
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical('Error: %s', msg)
        unlock()
        sys.exit(1)
    elif result == 2:
        # Continue on
        pass
    elif result == 100:
        unlock()
        sys.exit(100)
    else:
        logger.critical('Unknown Error(s): Exit Code: %d:', result)
        for msg in resultmsgs:
            logger.critical(msg)
        unlock()
        sys.exit(3)
            
    # Depsolve stage
    verbose_logger.log(logginglevels.INFO_2, 'Resolving Dependencies')
    verbose_logger.debug(time.time())
    try:
        (result, resultmsgs) = base.buildTransaction() 
    except plugins.PluginYumExit, e:
        exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [str(e)]
    except KeyboardInterrupt:
        exUserCancel()
    except IOError, e:
        exIOError(e)
   
    # Act on the depsolve result
    if result == 0:
        # Normal exit
        unlock()
        sys.exit(0)
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical('Error: %s', msg)
        unlock()
        sys.exit(1)
    elif result == 2:
        # Continue on
        pass
    else:
        logger.critical('Unknown Error(s): Exit Code: %d:', result)
        for msg in resultmsgs:
            logger.critical(msg)
        unlock()
        sys.exit(3)

    verbose_logger.log(logginglevels.INFO_2, '\nDependencies Resolved')
    verbose_logger.debug(time.time())

    # Run the transaction
    try:
        base.doTransaction()
    except plugins.PluginYumExit, e:
        exPluginExit(e)
    except Errors.YumBaseError, e:
        exFatal(e)
    except KeyboardInterrupt:
        exUserCancel()
    except IOError, e:
        exIOError(e)

    verbose_logger.log(logginglevels.INFO_2, 'Complete!')
    unlock()
    sys.exit(0)

    
if __name__ == "__main__":
    #import hotshot
    #p = hotshot.Profile(os.path.expanduser("~/yum.prof"))
    #p.run('main(sys.argv[1:])')
    #p.close()    
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, "\n\nExiting on user cancel."
        sys.exit(1)
