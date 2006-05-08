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

# (c)2006 Duke University - written by Seth Vidal

#TODO:
# add logs and errorlogs below a certain number to send out to syslog
# fix email notifications so it does _something_ :)


import os
import sys
import time
import dbus
import dbus.service
import dbus.glib
import gobject
import smtplib
from email.MIMEText import MIMEText



import yum
import yum.Errors
from yum.logger import Logger, SysLogger, LogContainer
from yum.config import BaseConfig, Option, IntOption, ListOption, BoolOption, \
                       IncludingConfigParser
from yum.constants import *
YUM_PID_FILE = '/var/run/yum.pid'
config_file = '/etc/yum/yum-updatesd.conf'



class YumDbusInterface(dbus.service.Object):
    def __init__(self, bus_name, object_path='/edu/duke/linux/yum/object'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal('edu.duke.linux.Yum')
    def UpdatesAvailableSignal(self, message):
        pass

    @dbus.service.signal('edu.duke.linux.Yum')
    def NoUpdatesAvailableSignal(self, message):
        pass
        


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
        self.doSetup()
        self.updatesCheck()
        self.doShutdown()
        
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

        self.doConfigSetup(fn=self.opts.yum_config)
        self.doLock(YUM_PID_FILE)        
        self.doRepoSetup()
        self.doSackSetup()
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()
    
    def updatesCheck(self):
        updates = len(self.up.getUpdatesList())
        obsoletes = len(self.up.getObsoletesTuples())

        # this should check to see if opts.do_update is true or false
        # right now just notify something/someone
        num_updates = updates+obsoletes
        self.emit(num_updates)


    def doShutdown(self):
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
    
    def emit(self, num_updates):
        """method to emit a notice about updates"""
        if 'dbus' in self.opts.emit_via:
            self.emit_dbus(num_updates)
        
        if 'syslog' in self.opts.emit_via:
            self.emit_syslog(num_updates)
        
        if 'email' in self.opts.emit_via:
            self.emit_email(num_updates)


    def emit_email(self, num_updates):
        """method to send email for notice of updates"""
        
        if num_updates > 0:
            output = """
               Hi,
                There are %d package updates available. Please run the system
                updater.
                
                Thank You,
                Your Computer
                
                """ % num_updates
                
            msg = MIMEText(output)
            subject = 'Updates Available'
            msg['Subject'] = subject
            msg['From'] = self.opts.email_from
            msg['To'] = self.opts.email_to
            s = smtplib.SMTP()
            s.connect()
            s.sendmail(mail_from, [mail_to], msg.as_string())
            s.close()        
        
    
    def emit_syslog(self, num_updates):
        """method to write to syslog for notice of updates"""
        syslog_object = SysLogger(threshold = 10, 
                                      facility=self.conf.syslog_facility,
                                      ident='yum-updatesd')
        syslog = LogContainer([syslog_object])
        
        if num_updates > 0:
            msg = "%d update(s) available" % num_updates
        else:
            msg = "No Updates Available"
            
        syslog(0, msg)

    def emit_dbus(self, num_updates):
        """method to emit a dbus event for notice of updates"""
        # setup the dbus interface
        my_bus = dbus.SystemBus()
        name = dbus.service.BusName('edu.duke.linux.Yum', bus=my_bus)
        yum_dbus = YumDbusInterface(name)
        if num_updates > 0:
            msg = "%d updates available" % num_updates
            yum_dbus.UpdatesAvailableSignal(msg)
        else:
            msg = "No Updates Available"
            yum_dbus.NoUpdatesAvailableSignal(msg)
        
        del yum_dbus
        del name
        del my_bus
        
class YumDbusListener(dbus.service.Object):
    def __init__(self, bus_name, object_path='/Updatesd'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method("edu.duke.linux.yum.Updatesd")
    def CheckNow(self):
        run_update_check()
        return "check completed"



def run_update_check(opts=None):

    if not opts:
        confparser = IncludingConfigParser()
        opts = UDConfig()
        
        if os.path.exists(config_file):
            confparser.read(config_file)
        
        opts.populate(confparser, 'main')

    try:
        my = UpdatesDaemon(opts)
    except yum.Errors.YumBaseError, e:
        print >> sys.stderr, 'Error: %s' % e
    else:
        del my
    
    return True # has to be true or gobject will stop running it afaict
    

def main():
    
    if os.fork():
        sys.exit()

    confparser = IncludingConfigParser()
    opts = UDConfig()
    
    if os.path.exists(config_file):
        confparser.read(config_file)
    
    opts.populate(confparser, 'main')
    
    bus = dbus.SystemBus()
    name = dbus.service.BusName("edu.duke.linux.yum.Updatesd", bus=bus)
    object = YumDbusListener(name)
    
    run_interval_ms = opts.run_interval * 1000 # get it into milliseconds for gobject
    
    gobject.timeout_add(run_interval_ms, run_update_check)

    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
