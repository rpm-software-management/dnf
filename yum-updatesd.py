#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# in its own dir download metadata and create updates list
# sleep for a configured time and do it all again

#TODO:
# read in config from a file
# make it emit more involved answers than a simple yes or nor on updates
#  being available
# add logs and errorlogs below a certain number to send out to syslog
# maybe provide for configurable emit mechanisms:
#   - dbus
#   - email
#   - syslog


import os
import sys
import time

import yum
import yum.Errors
from yum.config import BaseConfig, Option, IntOption, ListOption, BoolOption, \
                       IncludingConfigParser
from yum.constants import *
YUM_PID_FILE = '/var/run/yum.pid'

class UDConfig(yum.config.BaseConfig):
    """Config format for the daemon"""
    run_interval = IntOption(3600)
    nonroot_workdir = Option("/var/tmp/yum-updatesd")
    emit_via = ListOption(['dbus', 'email', 'syslog'])
    email_to = Option("root@localhost")
    email_from = Option("yum-updatesd@localhost")
    do_update = BoolOption(False)
    syslog_facility = Option("DAEMON")
    syslog_level = Option("WARN")
    yum_config = Option("/etc/yum.conf")
    

class UpdatesDaemon(yum.YumBase):
    def __init__(self, opts):
        yum.YumBase.__init__(self)
        self.opts = opts
        
    def log(self, num, msg):
    #TODO - this should probably syslog
        pass
    
    def errorlog(self, num, msg):
    #TODO - this should probably syslog
        pass

    def doSetup(self):
        # if we are not root do the special subdir thing
        if os.geteuid() != 0:
            if not os.path.exists(self.opts.nonroot_workdir):
                os.makedirs(self.opts.nonroot_workdir)
            self.repos.setCacheDir(self.opts.nonroot_workdir)
        else:
            self.doLock(YUM_PID_FILE)

        self.doConfigSetup(fn=self.opts.yum_config)
        self.doRepoSetup()
        self.doSackSetup()
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()
    
    def updatesCheck(self):
        
        if len(self.up.getUpdatesList()) > 0 or len(self.up.getObsoletesTuples()) > 0:
            return True
        else:
            return False

    def doShutdown(self):
        if os.geteuid() == 0:
            self.doUnlock(YUM_PID_FILE)

        # close the rpmdb
        self.closeRpmDB()
        # delete the updates object
        if hasattr(self, 'up'):
            del self.up
        # delete the package sacks/repos
        if hasattr(self, 'pkgSack'):
            del self.pkgSack
        if hasattr(self, 'repos'):
            del self.repos
    
    def emit(self, what):
        """method to emit a notice about updates"""
        print what
    
    def emit_email(self, what):
        """method to send email for notice of updates"""
        pass
    
    def emit_syslog(self, what):
        """method to write to syslog for notice of updates"""
        pass
        
    def emit_dbus(self, what):
        """method to emit a dbus event for notice of updates"""
        pass
        
    
def main():
    
    if os.fork():
        sys.exit()
    
    config_file = '/etc/yum/yum-updatesd.conf'
    confparser = IncludingConfigParser()
    opts = UDConfig()
    
    if os.path.exists(config_file):
        confparser.read(config_file)
    
    opts.populate(confparser, 'main')
    
    
    while True:
        try:
            my = UpdatesDaemon(opts)
            my.doSetup()
            if my.updatesCheck():
                my.emit('updates exist, time to run the updater')
            
            my.doShutdown()
            del my
        except yum.Errors.YumBaseError, e:
            print >> sys.stderr, 'Error: %s' % e
        
        time.sleep(opts.sleeptime)

    
    
if __name__ == "__main__":
    main()
