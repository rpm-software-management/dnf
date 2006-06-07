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

# (c)2006 Duke University, Red Hat, Inc.
# Seth Vidal <skvidal@linux.duke.edu>
# Jeremy Katz <katzj@redhat.com>

#TODO:
# - add logs and errorlogs below a certain number to send out to syslog
# - clean up config and work on man page for docs
# - need to be able to cancel downloads.  requires some work in urlgrabber
# - what to do if we're asked to exit while updates are being applied?
# - what to do with the lock around downloads/updates
# - need to not hold the rpmdb open.  probably via the changes in yum to
#   handle the rpmdb lazily

import os
import sys
import time
import dbus
import dbus.service
import dbus.glib
import gobject
import smtplib
import string
import time
import threading
from optparse import OptionParser
from email.MIMEText import MIMEText



import yum
import yum.Errors
from yum.logger import Logger, SysLogger, LogContainer
from yum.config import BaseConfig, Option, IntOption, ListOption, BoolOption, \
                       IncludingConfigParser
from yum.constants import *
from yum.packages import YumInstalledPackage

# FIXME: is it really sane to use this from here?
import callback

YUM_PID_FILE = '/var/run/yum.pid'
config_file = '/etc/yum/yum-updatesd.conf'


# FIXME: this is kind of gross -- hopefully the rpmdb as a sack stuff will
# make this not really be needed
def pkgFromInstalledTuple(pkgtup, rpmdb):
    return YumInstalledPackage(rpmdb.returnHeaderByTuple(pkgtup)[0])


class UpdateEmitter(object):
    """Abstract object for implementing different types of emitters."""
    def __init__(self):
        pass
    def updatesAvailable(self, updateInfo):
        """Emitted when there are updates available to be installed.
        If not doing the download here, then called immediately on finding
        new updates.  If we do the download here, then called after the
        updates have been downloaded."""
        pass
    def updatesDownloading(self, updateInfo):
        """Emitted to give feedback of update download starting."""
        pass
    def updatesApplied(self, updateInfo):
        """Emitted on successful installation of updates."""
        pass
    def updatesFailed(self, errmsgs):
        """Emitted when an update has failed to install."""
        pass

class SyslogUpdateEmitter(UpdateEmitter):
    def __init__(self, syslog_facility, ident = "yum-updatesd"):
        UpdateEmitter.__init__(self)
        syslog_object = SysLogger(threshold = 10, 
                                      facility=syslog_facility,
                                      ident='yum-updatesd')
        self.syslog = LogContainer([syslog_object])
        
    def updatesAvailable(self, updateInfo):
        num = len(updateInfo)
        if num > 1:
            msg = "%d updates available" %(num,)
        elif num == 1:
            msg = "1 update available"
        else:
            msg = "No updates available"

        self.syslog(0, msg)

class EmailUpdateEmitter(UpdateEmitter):
    def __init__(self, sender, rcpt):
        UpdateEmitter.__init__(self)        
        self.sender = sender
        self.rcpt = rcpt

    def updatesAvailable(self, updateInfo):
        num = len(updateInfo)
        if num < 1:
            return

        output = """
        Hi,
        There are %d package updates available. Please run the system
        updater.
        
        Thank You,
        Your Computer
        """ % num
                
        msg = MIMEText(output)
        msg['Subject'] = "%d Updates Available" %(num,)
        msg['From'] = self.sender
        msg['To'] = string.join(self.rcpt, ",")
        s = smtplib.SMTP()
        s.connect()
        s.sendmail(self.sender, self.rcpt, msg.as_string())
        s.close()

class DbusUpdateEmitter(UpdateEmitter):
    def __init__(self):
        UpdateEmitter.__init__(self)        
        bus = dbus.SystemBus()
        name = dbus.service.BusName('edu.duke.linux.yum', bus = bus)
        yum_dbus = YumDbusInterface(name)
        self.dbusintf = yum_dbus

    def updatesAvailable(self, updateInfo):
        num = len(updateInfo)
        msg = "%d" %(num,)
        if num > 0:
            self.dbusintf.UpdatesAvailableSignal(msg)
        else:
            self.dbusintf.NoUpdatesAvailableSignal(msg)

    def updatesFailed(self, errmsgs):
        self.dbusintf.UpdatesFailedSignal(errmsgs)

    def updatesApplied(self, updinfo):
        self.dbusintf.UpdatesAppliedSignal(updinfo)

class YumDbusInterface(dbus.service.Object):
    def __init__(self, bus_name, object_path='/UpdatesAvail'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal('edu.duke.linux.yum')
    def UpdatesAvailableSignal(self, message):
        pass

    @dbus.service.signal('edu.duke.linux.yum')
    def NoUpdatesAvailableSignal(self, message):
        pass
        
    @dbus.service.signal('edu.duke.linux.yum')
    def UpdatesFailedSignal(self, errmsgs):
        pass

    @dbus.service.signal('edu.duke.linux.yum')
    def UpdatesAppliedSignal(self, updinfo):
        pass


class UDConfig(yum.config.BaseConfig):
    """Config format for the daemon"""
    run_interval = IntOption(3600)
    nonroot_workdir = Option("/var/tmp/yum-updatesd")
    emit_via = ListOption(['dbus', 'email', 'syslog'])
    email_to = ListOption(["root@localhost"])
    email_from = Option("yum-updatesd@localhost")
    dbus_listener = BoolOption(True)
    do_update = BoolOption(False)
    do_download = BoolOption(False)
    do_download_deps = BoolOption(False)
    updaterefresh = IntOption(3600)
    syslog_facility = Option("DAEMON")
    syslog_level = Option("WARN")
    yum_config = Option("/etc/yum.conf")

class UpdateDownloadThread(threading.Thread):
    def __init__(self, updd, dlpkgs):
        self.updd = updd
        self.dlpkgs = dlpkgs
        threading.Thread.__init__(self, name="UpdateDownloadThread")

    def run(self):
        self.updd.downloadPkgs(self.dlpkgs)
        self.updd.emitAvailable()
        self.updd.closeRpmDB()
        self.updd.doUnlock(YUM_PID_FILE)

class UpdateInstallThread(threading.Thread):
    def __init__(self, updd, dlpkgs):
        self.updd = updd
        self.dlpkgs = dlpkgs
        threading.Thread.__init__(self, name="UpdateInstallThread")

    def failed(self, msgs):
        self.updd.emitUpdateFailed(msgs)
        self.updd.closeRpmDB()
        self.updd.doUnlock(YUM_PID_FILE)

    def success(self):
        self.updd.emitUpdateApplied()
        self.updd.closeRpmDB()
        self.updd.doUnlock(YUM_PID_FILE)

        self.updd.updateInfo = None
        self.updd.updateInfoTime = None        
        
    def run(self):
        self.updd.downloadPkgs(dlpkgs)
        for po in dlpkgs:
            rc, err = self.updd.sigCheckPkg(po)
            if result == 0:
                continue
            elif result == 1:
                try:
                    self.updd.getKeyForPackage(po)
                except yum.Errors.YumBaseError, errmsg:
                    self.failed([errmsg])

        del self.updd.ts
        self.updd.initActionTs() # make a new, blank ts to populate
        self.updd.populateTs(keepold=0)
        self.updd.ts.check() #required for ordering
        self.updd.ts.order() # order
        cb = callback.RPMInstallCallback(output = 0)
            
        # FIXME: need to do filelog
        cb.tsInfo = self.updd.tsInfo
        try:
            tserrors = self.updd.runTransaction(cb=cb)
        except yum.Errors.YumBaseError, err:
            self.failed([err])

        self.success()

class UpdatesDaemon(yum.YumBase):
    def __init__(self, opts):
        yum.YumBase.__init__(self)
        self.opts = opts
        self.doSetup()

        self.emitters = []
        if 'dbus' in self.opts.emit_via:
            self.emitters.append(DbusUpdateEmitter())
        if 'email' in self.opts.emit_via:
            self.emitters.append(EmailUpdateEmitter(self.opts.email_from,
                                                    self.opts.email_to))
        if 'syslog' in self.opts.emit_via:
            self.emitters.append(SyslogUpdateEmitter(self.conf.syslog_facility))

        self.updateInfo = []
        self.updateInfoTime = None

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

        self.doStartupConfig(fn=self.opts.yum_config)
        self.doConfigSetup()

    def refreshUpdates(self):
        self.doLock(YUM_PID_FILE)
        self.doRepoSetup()
        self.doSackSetup()
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()

    def populateUpdates(self):
        def getDbusPackageDict(pkg):
            """Returns a dictionary corresponding to the package object
            in the form that we can send over the wire for dbus."""
            return { "name": pkg.returnSimple("name"),
                     "version": pkg.returnSimple("version"),
                     "release": pkg.returnSimple("release"),
                     "epoch": pkg.returnSimple("epoch"),
                     "arch": pkg.returnSimple("arch"),
                     "sourcerpm": pkg.returnSimple("sourcerpm"),
                     "summary": pkg.returnSimple("summary") or "",
                     }            
        
        if not hasattr(self, 'up'):
            # we're _only_ called after updates are setup
            return

        self.updateInfo = []
        for (new, old) in self.up.getUpdatesTuples():
            n = getDbusPackageDict(self.getPackageObject(new))
            o = getDbusPackageDict(pkgFromInstalledTuple(old, self.rpmdb))
            self.updateInfo.append((n, o))

        if self.conf.obsoletes:
            for (obs, inst) in self.up.getObsoletesTuples():
                n = getDbusPackageDict(self.getPackageObject(obs))
                o = getDbusPackageDict(pkgFromInstalledTuple(inst, self.rpmdb))
                self.updateInfo.append((n, o))

        self.updateInfoTime = time.time()

    def populateTsInfo(self):
        # figure out the updates
        for (new, old) in self.up.getUpdatesTuples():
            updating = self.getPackageObject(new)
            updated = pkgFromInstalledTuple(old, self.rpmdb)
                
            self.tsInfo.addUpdate(updating, updated)

        # and the obsoletes
        if self.conf.obsoletes:
            for (obs, inst) in self.up.getObsoletesTuples():
                obsoleting = self.getPackageObject(obs)
                installed = pkgFromInstalledTuple(inst, self.rpmdb)
                
                self.tsInfo.addObsoleting(obsoleting, installed)
                self.tsInfo.addObsoleted(installed, obsoleting)

    def updatesCheck(self):
        try:
            self.refreshUpdates()
        except yum.Errors.LockError:
            return True # just pass for now

        self.populateTsInfo()
        self.populateUpdates()

        # FIXME: this needs to be done in the download/install threads
        if self.opts.do_update or self.opts.do_download_deps:
            self.tsInfo.makelists()
            try:
                (result, msgs) = self.buildTransaction()
            except yum.Errors.RepoError, errmsg: # error downloading hdrs
                (result, msgs) = (1, ["Error downloading headers"])

        dlpkgs = map(lambda x: x.po, filter(lambda txmbr:
                                            txmbr.ts_state in ("i", "u"),
                                            self.tsInfo.getMembers()))

        close = True
        if self.opts.do_update:
            # we already resolved deps above
            if result == 1: 
                self.emitUpdateFailed(msgs)
            else:
                uit = UpdateInstallThread(self, dlpkgs)
                uit.start()
                close = False
        elif self.opts.do_download:
            self.emitDownloading()
            dl = UpdateDownloadThread(self, dlpkgs)
            dl.start()
            close = False
        else:
            # just notify about things being available
            self.emitAvailable()

        # FIXME: this is kind of ugly in that I want to do it sometimes
        # and yet not others and it's from threads that it matters.  aiyee!
        if close:
            self.closeRpmDB()
            self.doUnlock(YUM_PID_FILE)

        return True

    def getUpdateInfo(self):
        # if we have a cached copy, use it
        if self.updateInfoTime and (time.time() - self.updateInfoTime <
                                    self.opts.updaterefresh):
            print "returning cached"
            return self.updateInfo
            
        # try to get the lock so we can update the info.  fall back to
        # cached if available or try a few times.
        tries = 0
        while tries < 10:
            try:
                self.doLock(YUM_PID_FILE)
                break
            except yum.Errors.LockError:
                pass
            # if we can't get the lock, return what we have if we can
            if self.updateInfo: return self.updateInfo
            time.sleep(1)
        if tries == 10:
            return []
        
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()

        self.populateUpdates()

        self.closeRpmDB()        
        self.doUnlock(YUM_PID_FILE)

        return self.updateInfo

    def emitAvailable(self):
        """method to emit a notice about updates"""
        map(lambda x: x.updatesAvailable(self.updateInfo), self.emitters)

    def emitDownloading(self):
        """method to emit a notice about updates downloading"""
        print "downloading some updates"
        map(lambda x: x.updatesDownloading(self.updateInfo), self.emitters)

    def emitUpdateApplied(self):
        """method to emit a notice when automatic updates applied"""
        map(lambda x: x.updatesApplied(self.updateInfo), self.emitters)

    def emitUpdateFailed(self, errmsgs):
        """method to emit a notice when automatic updates failed"""
        map(lambda x: x.updatesFailed(errmsgs), self.emitters)

class YumDbusListener(dbus.service.Object):
    def __init__(self, updd, bus_name, object_path='/Updatesd',
                 allowshutdown = False):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.updd = updd
        self.allowshutdown = allowshutdown

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
        print "GetUpdateInfo"
        # FIXME: should this be async?
        upds = self.updd.getUpdateInfo()
        return upds
        

def quit(*args):
    sys.exit(0)

def main():
    # we'll be threading for downloads/updates
    gobject.threads_init()
    dbus.glib.threads_init()
    
    parser = OptionParser()
    parser.add_option("-f", "--no-fork", action="store_true", default=False, dest="nofork")
    parser.add_option("-r", "--remote-shutdown", action="store_true", default=False, dest="remoteshutdown")    
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
    updd = UpdatesDaemon(opts)

    if opts.dbus_listener:
        bus = dbus.SystemBus()
        name = dbus.service.BusName("edu.duke.linux.yum", bus=bus)
        object = YumDbusListener(updd, name,
                                 allowshutdown = options.remoteshutdown)
    
    run_interval_ms = opts.run_interval * 1000 # needs to be in ms
    gobject.timeout_add(run_interval_ms, updd.updatesCheck)

    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
