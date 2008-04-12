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

"""
Entrance point for the yum command line interface.
"""

import os
import sys
import locale
import logging
import time # test purposes only

from yum import Errors
from yum import plugins
from yum import logginglevels
import yum.i18n
import cli


def main(args):
    """This does all the real work"""
    if True: # not sys.stdout.isatty():
        import codecs
        sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

    def exUserCancel():
        logger.critical(_('\n\nExiting on user cancel'))
        if unlock(): return 200
        return 1

    def exIOError(e):
        if e.errno == 32:
            logger.critical(_('\n\nExiting on Broken Pipe'))
        if unlock(): return 200
        return 1

    def exPluginExit(e):
        '''Called when a plugin raises PluginYumExit.

        Log the plugin's exit message if one was supplied.
        '''
        exitmsg = str(e)
        if exitmsg:
            logger.warn('\n\n%s', exitmsg)
        if unlock(): return 200
        return 1

    def exFatal(e):
        logger.critical('\n\n%s', str(e))
        if unlock(): return 200
        return 1

    def unlock():
        try:
            base.closeRpmDB()
            base.doUnlock()
        except Errors.LockError, e:
            return 200
        return 0

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
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        return exFatal(e)

    lockerr = ""
    while True:
        try:
            base.doLock()
        except Errors.LockError, e:
            if "%s" %(e.msg,) != lockerr:
                lockerr = "%s" %(e.msg,)
                logger.critical(lockerr)
            logger.critical(_("Another app is currently holding the yum lock; waiting for it to exit..."))
            time.sleep(2)
        else:
            break

    try:
        result, resultmsgs = base.doCommands()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [unicode(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    # Act on the command/shell result
    if result == 0:
        # Normal exit 
        for msg in resultmsgs:
            verbose_logger.log(logginglevels.INFO_2, '%s', msg)
        if unlock(): return 200
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical(_('Error: %s'), msg)
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    elif result == 100:
        if unlock(): return 200
        return 100
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3
            
    # Depsolve stage
    verbose_logger.log(logginglevels.INFO_2, _('Resolving Dependencies'))

    try:
        (result, resultmsgs) = base.buildTransaction() 
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [unicode(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)
   
    # Act on the depsolve result
    if result == 0:
        # Normal exit
        if unlock(): return 200
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical(_('Error: %s'), msg)
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3

    verbose_logger.log(logginglevels.INFO_2, _('\nDependencies Resolved'))

    # Run the transaction
    try:
        base.doTransaction()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        return exFatal(e)
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    verbose_logger.log(logginglevels.INFO_2, _('Complete!'))
    if unlock(): return 200
    return 0

def hotshot(func, *args, **kwargs):
    import hotshot.stats, os.path
    fn = os.path.expanduser("~/yum.prof")
    prof = hotshot.Profile(fn)
    rc = prof.runcall(func, *args, **kwargs)
    prof.close()
    print_stats(hotshot.stats.load(fn))
    return rc

def cprof(func, *args, **kwargs):
    import cProfile, pstats, os.path
    fn = os.path.expanduser("~/yum.prof")
    prof = cProfile.Profile()
    rc = prof.runcall(func, *args, **kwargs)
    prof.dump_stats(fn)
    print_stats(pstats.Stats(fn))
    return rc

def print_stats(stats):
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)
    stats.sort_stats('cumulative')
    stats.print_stats(40)

def user_main(args, exit_code=False):
    """ This calls one of the multiple main() functions based on env. vars """
    errcode = None
    if 'YUM_PROF' in os.environ:
        if os.environ['YUM_PROF'] == 'cprof':
            errcode = cprof(main, args)
        if os.environ['YUM_PROF'] == 'hotshot':
            errcode = hotshot(main, args)
    if errcode is None:
        errcode = main(args)
    if exit_code:
        sys.exit(errcode)
    return errcode

if __name__ == "__main__":
    try:
        user_main(sys.argv[1:], exit_code=True)
    except KeyboardInterrupt, e:
        print >> sys.stderr, _("\n\nExiting on user cancel.")
        sys.exit(1)
