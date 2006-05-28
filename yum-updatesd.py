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
# - add logs and errorlogs below a certain number to send out to syslog
# - thread it so it can download the updated packages while still answering 
#     dbus calls
# - clean up config and work on man page for docs


import os
import sys
import time
import dbus
import dbus.service
import dbus.glib
import gobject
import smtplib
from optparse import OptionParser
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
    def __init__(self, bus_name, object_path='/UpdatesAvail'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal('edu.duke.linux.yum')
    def UpdatesAvailableSignal(self, message):
        pass

    @dbus.service.signal('edu.duke.linux.yum')
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
    def __init__(self, opts, dbusintf):
        yum.YumBase.__init__(self)
        self.opts = opts
        self.doSetup()

        self.dbusintf = dbusintf
        
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

    def refreshUpdates(self):
        self.doLock(YUM_PID_FILE)
        self.doRepoSetup()
        self.doSackSetup()
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()
        
    def updatesCheck(self):
        try:
            self.refreshUpdates()
        except yum.Errors.LockError:
            return True # just pass for now

        updates = len(self.up.getUpdatesList())
        obsoletes = len(self.up.getObsoletesTuples())

        # this should check to see if opts.do_update is true or false
        # right now just notify something/someone
        if not self.opts.do_update:
            num_updates = updates+obsoletes
            self.emitAvailable(num_updates)

        self.closeRpmDB()
        self.doUnlock(YUM_PID_FILE)

        return True

    def getUpdateInfo(self):
        # try to get the lock up to 10 times to get the explicitly
        # asked for info
        tries = 0
        while tries < 10:
            try:
                self.doLock(YUM_PID_FILE)
                break
            except yum.Errors.LockError:
                pass
            time.sleep(1)
        
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()
        self.doUnlock(YUM_PID_FILE)        
        return self.up.getUpdatesTuples()

    def emitAvailable(self, num_updates):
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
            s.sendmail(self.opts.email_from, [self.opts.email_to], msg.as_string())
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
        if not self.dbusintf:
            # FIXME: assert here ?
            return
        if num_updates > 0:
            msg = "%d updates available" % num_updates
            self.dbusintf.UpdatesAvailableSignal(msg)
        else:
            msg = "No Updates Available"
            self.dbusintf.NoUpdatesAvailableSignal(msg)

class YumDbusListener(dbus.service.Object):
    def __init__(self, updd, bus_name, object_path='/Updatesd'):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.updd = updd
        self.allowshutdown = False

    def doCheck(self):
        self.updd.updatesCheck()
        return False

    @dbus.service.method("edu.duke.linux.yum")
    def CheckNow(self):
        # make updating checking asynchronous since we discover whether
        # or not there are updates via a callback signal anyway
        gobject.idle_add(self.doCheck)
        return "check queued"

    @dbus.service.method("edu.duke.linux.yum")
    def ShutDown(self):
        if not self.allowshutdown:
            return False
        
        # we have to do this in a callback so that it doesn't get
        # sent back to the caller
        gobject.idle_add(quit)
        return True

    @dbus.service.method("edu.duke.linux.yum")
    def GetUpdateInfo(self):
        # FIXME: should this be async?
        upds = self.updd.getUpdateInfo()
        return upds

def quit(*args):
    sys.exit(0)

def main():
    parser = OptionParser()
    parser.add_option("-f", "--no-fork", action="store_true", default=False, dest="nofork")
    (options, args) = parser.parse_args()

    if not options.nofork:
        if os.fork():
            sys.exit()
        fd = os.open("/dev/null", os.O_RDONLY)
        os.dup2(fd, 0)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        os.close(fd)

    confparser = IncludingConfigParser()
    opts = UDConfig()
    
    if os.path.exists(config_file):
        confparser.read(config_file)
    
    opts.populate(confparser, 'main')

    if "dbus" in opts.emit_via:
        # setup the dbus interfaces
        bus = dbus.SystemBus()

        name = dbus.service.BusName('edu.duke.linux.yum', bus=bus)
        yum_dbus = YumDbusInterface(name)

        updd = UpdatesDaemon(opts, yum_dbus)
        
        name = dbus.service.BusName("edu.duke.linux.yum", bus=bus)
        object = YumDbusListener(updd, name)
    else:
        updd = UpdatesDaemon(opts, None)
    
    run_interval_ms = opts.run_interval * 1000 # needs to be in ms
    
    gobject.timeout_add(run_interval_ms, updd.updatesCheck)

    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
