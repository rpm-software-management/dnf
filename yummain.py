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
# Copyright 2004 Duke University 


import os
import sys
import locale
import time # test purposes only

import yum
import rpmUtils.updates
import yum.Errors as Errors
import yum.depsolve
import cli
import output


from i18n import _


def main(args):
    """This does all the real work"""

    locale.setlocale(locale.LC_ALL, '')
    # our core object for the cli
    base = cli.YumBaseCli()

    if len(args) < 1:
        base.usage()

    def unlock():
        try:
            base.doUnlock('/var/run/yum.pid')
        except Errors.LockError, e:
            sys.exit(200)

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    base.getOptionsConfig(args)
    
    try:
        base.doLock('/var/run/yum.pid')
    except Errors.LockError, e:
        base.errorlog(0,'%s' % e.msg)
        sys.exit(200)

    # build up an idea of what we're supposed to do
    try:
        result, resultmsgs = base.doCommands()
    except Errors, e:
        result = 1
        resultmsgs = [str(e)]
#    except KeyboardInterrupt, e:
#        base.errorlog(0, 'Exiting on user cancel')
#        unlock()
#        sys.exit(1)
        
    if result not in [0, 1, 2, 100]:
        base.errorlog(0, 'Unknown Error(s): Exit Code: %d:' % result)
        for msg in resultmsgs:
            base.errorlog(0, msg)
        unlock()
        sys.exit(3)
    
    if result == 100:
        unlock()
        sys.exit(100)

    elif result == 0:
        for msg in resultmsgs:
            base.log(2, '%s' % msg)
        unlock()
        sys.exit(0)
            
    elif result == 1:
        for msg in resultmsgs:
            base.errorlog(0, 'Error: %s' % msg)
        unlock()
        sys.exit(1)
            
    # Depsolve stage
    base.log(2, 'Resolving Dependencies')
    base.log(3, time.time())
    try:
        (result, resultmsgs) = base.buildTransaction() 
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [str(e)]
    except KeyboardInterrupt, e:
        base.errorlog(0, 'Exiting on user cancel')
        unlock()
        sys.exit(1)
    
    if result not in [0, 1, 2]:
        base.errorlog(0, 'Unknown Error(s): Exit Code: %d:' % result)
        for msg in resultmsgs:
            base.errorlog(0, msg)
        unlock()
        sys.exit(3)
        
    if result == 0:
        unlock()
        sys.exit(0)
            
    elif result == 1:
        for msg in resultmsgs:
            base.errorlog(0, 'Error: %s' % msg)
        unlock()
        sys.exit(1)

    base.log(2, '\nDependencies Resolved')
    base.log(3, time.time())
    #run post-depresolve script here
    #run  pre-trans script here
    # run the transaction
    try:
        base.doTransaction()
    except Errors.YumBaseError, e:
        base.errorlog(0, '%s' % e)
        unlock()
        sys.exit(1)
    except KeyboardInterrupt, e:
        base.errorlog(0, 'Exiting on user cancel')
        unlock()
        sys.exit(1)

    # run post-trans script here
    # things ran correctly
    # run a report function base.whatwedid() :)
    
    base.log(2, 'Complete!')
    unlock()
    sys.exit(0)
    
    
if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, "\nExiting on user cancel."
        sys.exit(1)
