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
# Copyright 2004 Duke University


import os
import errno
import Errors

class YumBase:
    """this is a base class that is used to hold things"""
    def __init__(self):
       pass
       

def doLock(lockfile, mypid):
    """perform the yum locking, raise yum-based exceptions, not OSErrors"""
    
    while not lock(lockfile, mypid, 0644):
        fd = open(lockfile, 'r')
        try: oldpid = int(fd.readline())
        except ValueError:
            # bogus data in the pid file. Throw away.
            unlock(lockfile)
        else:
            try: os.kill(oldpid, 0)
            except OSError, e:
                if e[0] == errno.ESRCH:
                    # The pid doesn't exist
                    unlock(lockfile)
                else:
                    # Whoa. What the heck happened?
                    msg = 'Unable to check if PID %s is active' % oldpid
                    raise Errors.LockError(1, msg)
            else:
                # Another copy seems to be running.
                msg = 'Existing lock %s: another copy is running. Aborting.' % lockfile
                raise Errors.LockError(0, msg)


def lock(filename, contents='', mode=0777):
    try:
        fd = os.open(filename, os.O_EXCL|os.O_CREAT|os.O_WRONLY, mode)
    except OSError, msg:
        if not msg.errno == errno.EEXIST: raise msg
        return 0
    else:
        os.write(fd, contents)
        os.close(fd)
        return 1

def unlock(filename):
    try:
        os.unlink(filename)
    except OSError, msg:
        pass
        
