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

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    base.getOptionsConfig(args)
    
    try:
        base.doLock('/var/run/yum.pid')
    except Errors.LockError, e:
        base.errorlog(0,'%s' % e.msg)
        sys.exit(200)
    
    # right now we've parsed the config, we've parsed the cli
    # all these things check out
    # the things we will require are dependent on the command invoked.
    try:
        result = base.doCommands()  # this build
    except Errors, e:
        print 'raised error %s from doCommands()' % e
        raise
    
    # the result code from doCommands() determines where we go from here
    # this means we either do the transaction set we have or exit nicely    
    # we're done, unlock, and take us home mr. data.     
    try:
        base.doUnlock('/var/run/yum.pid')
    except Errors.LockError, e:
        base.errorlog(0,'%s' % e.msg)
        sys.exit(200)
    else:
        sys.exit(0)
        
    
if __name__ == "__main__":
        main(sys.argv[1:])
