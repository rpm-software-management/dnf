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
# - clean up config and work on man page for docs
# - need to be able to cancel downloads.  requires some work in urlgrabber
# - what to do if we're asked to exit while updates are being applied?
# - what to do with the lock around downloads/updates

# since it takes me time everytime to figure this out again, here's how to
# queue a check with dbus-send.  adjust appropriately for other methods
# $ dbus-send --system --print-reply --type=method_call \
#   --dest=edu.duke.linux.yum /Updatesd edu.duke.linux.yum.CheckNow

import os
import sys
import time
import gzip
import dbus
import dbus.service
import dbus.glib
import gobject
import smtplib
import threading
from optparse import OptionParser
from email.mime.text import MIMEText



import yum
import yum.Errors
import syslog
from yum.config import BaseConfig, Option, IntOption, ListOption, BoolOption
from yum.parser import ConfigPreProcessor
from ConfigParser import ConfigParser, ParsingError
from yum.constants import *
from yum.update_md import UpdateMetadata

# FIXME: is it really sane to use this from here?
sys.path.append('/usr/share/yum-cli')
import callback

config_file = '/etc/yum/yum-updatesd.conf'
initial_directory = os.getcwd()

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
    def checkFailed(self, error):
        """Emitted when checking for updates failed."""
        pass

    def setupFailed(self, error, translation_domain):
        """Emitted when plugin initialization failed."""
        pass
 

class SyslogUpdateEmitter(UpdateEmitter):
    def __init__(self, syslog_facility, ident = "yum-updatesd",
                 level = "WARN"):
        UpdateEmitter.__init__(self)
        syslog.openlog(ident, 0, self._facilityMap(syslog_facility))
        self.level = level
        
    def updatesAvailable(self, updateInfo):
        num = len(updateInfo)
        level = self.level
        if num > 1:
            msg = "%d updates available" %(num,)
        elif num == 1:
            msg = "1 update available"
        else:
            msg = "No updates available"
            level = syslog.LOG_DEBUG

        syslog.syslog(self._levelMap(level), msg)

    def _levelMap(self, lvl):
        level_map = { "EMERG": syslog.LOG_EMERG,
                      "ALERT": syslog.LOG_ALERT,
                      "CRIT": syslog.LOG_CRIT,
                      "ERR": syslog.LOG_ERR,
                      "WARN": syslog.LOG_WARNING,
                      "NOTICE": syslog.LOG_NOTICE,
                      "INFO": syslog.LOG_INFO,
                      "DEBUG": syslog.LOG_DEBUG }
        if type(lvl) == int:
            return lvl
        return level_map.get(lvl.upper(), syslog.LOG_INFO)

    def _facilityMap(self, facility):
        facility_map = { "KERN": syslog.LOG_KERN,
                         "USER": syslog.LOG_USER,
                         "MAIL": syslog.LOG_MAIL,
                         "DAEMON": syslog.LOG_DAEMON,
                         "AUTH": syslog.LOG_AUTH,
                         "LPR": syslog.LOG_LPR,
                         "NEWS": syslog.LOG_NEWS,
                         "UUCP": syslog.LOG_UUCP,
                         "CRON": syslog.LOG_CRON,
                         "LOCAL0": syslog.LOG_LOCAL0,
                         "LOCAL1": syslog.LOG_LOCAL1,
                         "LOCAL2": syslog.LOG_LOCAL2,
                         "LOCAL3": syslog.LOG_LOCAL3,
                         "LOCAL4": syslog.LOG_LOCAL4,
                         "LOCAL5": syslog.LOG_LOCAL5,
                         "LOCAL6": syslog.LOG_LOCAL6,
                         "LOCAL7": syslog.LOG_LOCAL7,}
        if type(facility) == int:
            return facility
        return facility_map.get(facility.upper(), syslog.LOG_DAEMON)


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
        msg['To'] = ",".join(self.rcpt)
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

    def checkFailed(self, error):
        self.dbusintf.CheckFailedSignal(error)

    def setupFailed(self, error, translation_domain):
        self.dbusintf.SetupFailedSignal(error, translation_domain)


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

    @dbus.service.signal('edu.duke.linux.yum')
    def CheckFailedSignal(self, message):
        pass

    @dbus.service.signal('edu.duke.linux.yum')
    def SetupFailedSignal(self, message, translation_domain=""):
        pass


class UDConfig(BaseConfig):
    """Config format for the daemon"""
    run_interval = IntOption(3600)
    nonroot_workdir = Option("/var/tmp/yum-updatesd")
    emit_via = ListOption(['dbus', 'email', 'syslog'])
    email_to = ListOption(["root"])
    email_from = Option("root")
    dbus_listener = BoolOption(True)
    do_update = BoolOption(False)
    do_download = BoolOption(False)
    do_download_deps = BoolOption(False)
    updaterefresh = IntOption(3600)
    syslog_facility = Option("DAEMON")
    syslog_level = Option("WARN")
    syslog_ident = Option("yum-updatesd")
    yum_config = Option("/etc/yum/yum.conf")


class UpdateBuildTransactionThread(threading.Thread):
    def __init__(self, updd, name):
        self.updd = updd
        threading.Thread.__init__(self, name=name)

    def run(self):
        self.updd.tsInfo.makelists()
        try:
            (result, msgs) = self.updd.buildTransaction()
        except yum.Errors.RepoError, errmsg: # error downloading hdrs
            msgs = ["Error downloading headers"]
            self.updd.emitUpdateFailed(msgs)
            return

        dlpkgs = map(lambda x: x.po, filter(lambda txmbr:
                                            txmbr.ts_state in ("i", "u"),
                                            self.updd.tsInfo.getMembers()))
        self.updd.downloadPkgs(dlpkgs)
        self.processPkgs(dlpkgs)


class UpdateDownloadThread(UpdateBuildTransactionThread):
    def __init__(self, updd):
        UpdateBuildTransactionThread.__init__(self, updd,
            name="UpdateDownloadThread")

    def processPkgs(self, dlpkgs):
        self.updd.emitAvailable()
        self.updd.releaseLocks()


class UpdateInstallThread(UpdateBuildTransactionThread):
    def __init__(self, updd):
        UpdateBuildTransactionThread.__init__(self, updd,
            name="UpdateInstallThread")

    def failed(self, msgs):
        self.updd.emitUpdateFailed(msgs)
        self.updd.releaseLocks()

    def success(self):
        self.updd.emitUpdateApplied()
        self.updd.releaseLocks()

        self.updd.updateInfo = None
        self.updd.updateInfoTime = None        
        
    def processPkgs(self, dlpkgs):
        for po in dlpkgs:
            result, err = self.updd.sigCheckPkg(po)
            if result == 0:
                continue
            elif result == 1:
                try:
                    self.updd.getKeyForPackage(po)
                except yum.Errors.YumBaseError, errmsg:
                    self.failed([str(errmsg)])

        del self.updd.ts
        self.updd.initActionTs() # make a new, blank ts to populate
        self.updd.populateTs(keepold=0)
        self.updd.ts.check() #required for ordering
        self.updd.ts.order() # order
        cb = callback.RPMInstallCallback(output = 0)
        cb.filelog = True
            
        cb.tsInfo = self.updd.tsInfo
        try:
            self.updd.runTransaction(cb=cb)
        except yum.Errors.YumBaseError, err:
            self.failed([str(err)])

        self.success()

class UpdatesDaemon(yum.YumBase):
    def __init__(self, opts):
        yum.YumBase.__init__(self)
        self.opts = opts
        self.didSetup = False

        self.emitters = []
        if 'dbus' in self.opts.emit_via:
            self.emitters.append(DbusUpdateEmitter())
        if 'email' in self.opts.emit_via:
            self.emitters.append(EmailUpdateEmitter(self.opts.email_from,
                                                    self.opts.email_to))
        if 'syslog' in self.opts.emit_via:
            self.emitters.append(SyslogUpdateEmitter(self.opts.syslog_facility,
                                                     self.opts.syslog_ident,
                                                     self.opts.syslog_level))

        self.updateInfo = []
        self.updateInfoTime = None

    def doSetup(self):
        # if we are not root do the special subdir thing
        if os.geteuid() != 0:
            if not os.path.exists(self.opts.nonroot_workdir):
                os.makedirs(self.opts.nonroot_workdir)
            self.repos.setCacheDir(self.opts.nonroot_workdir)

        self.doConfigSetup(fn=self.opts.yum_config)

    def refreshUpdates(self):
        self.doLock()
        try:
            self.doRepoSetup()
            self.doSackSetup()
            self.updateCheckSetup()
        except Exception, e:
            syslog.syslog(syslog.LOG_WARNING,
                          "error getting update info: %s" %(e,))
            self.emitCheckFailed("%s" %(e,))
            self.doUnlock()
            return False
        return True

    def populateUpdateMetadata(self):
        self.updateMetadata = UpdateMetadata()
        repos = []

        for (new, old) in self.up.getUpdatesTuples():
            pkg = self.getPackageObject(new)
            if pkg.repoid not in repos:
                repo = self.repos.getRepo(pkg.repoid)
                repos.append(repo.id)
                try: # grab the updateinfo.xml.gz from the repodata
                    md = repo.retrieveMD('updateinfo')
                except Exception: # can't find any; silently move on
                    continue
                md = gzip.open(md)
                self.updateMetadata.add(md)
                md.close()

    def populateUpdates(self):
        def getDbusPackageDict(pkg):
            """Returns a dictionary corresponding to the package object
            in the form that we can send over the wire for dbus."""
            pkgDict = {
                    "name": pkg.name,
                    "version": pkg.version,
                    "release": pkg.release,
                    "epoch": pkg.epoch,
                    "arch": pkg.arch,
                    "sourcerpm": pkg.sourcerpm,
                    "summary": pkg.summary or "",
            }

            # check if any updateinfo is available
            md = self.updateMetadata.get_notice((pkg.name, pkg.ver, pkg.rel))
            if md:
                # right now we only want to know if it is a security update
                pkgDict['type'] = md['type']

            return pkgDict

        if self.up is None:
            # we're _only_ called after updates are setup
            return

        self.populateUpdateMetadata()

        self.updateInfo = []
        for (new, old) in self.up.getUpdatesTuples():
            n = getDbusPackageDict(self.getPackageObject(new))
            o = getDbusPackageDict(self.rpmdb.searchPkgTuple(old)[0])
            self.updateInfo.append((n, o))

        if self.conf.obsoletes:
            for (obs, inst) in self.up.getObsoletesTuples():
                n = getDbusPackageDict(self.getPackageObject(obs))
                o = getDbusPackageDict(self.rpmdb.searchPkgTuple(inst)[0])
                self.updateInfo.append((n, o))

        self.updateInfoTime = time.time()

    def populateTsInfo(self):
        # figure out the updates
        for (new, old) in self.up.getUpdatesTuples():
            updating = self.getPackageObject(new)
            updated = self.rpmdb.searchPkgTuple(old)[0]
                
            self.tsInfo.addUpdate(updating, updated)

        # and the obsoletes
        if self.conf.obsoletes:
            for (obs, inst) in self.up.getObsoletesTuples():
                obsoleting = self.getPackageObject(obs)
                installed = self.rpmdb.searchPkgTuple(inst)[0]
                
                self.tsInfo.addObsoleting(obsoleting, installed)
                self.tsInfo.addObsoleted(installed, obsoleting)

    def updatesCheck(self):
        if not self.didSetup:
            try:
                self.doSetup()
            except Exception, e:
                syslog.syslog(syslog.LOG_WARNING,
                              "error initializing: %s" % e)

                if isinstance(e, yum.plugins.PluginYumExit):
                    self.emitSetupFailed(e.value, e.translation_domain)
                else:
                    # if we don't know where the string is from, then assume
                    # it's not marked for translation (versus sending 
                    # gettext.textdomain() and assuming it's from the default
                    # domain for this app)
                    self.emitSetupFailed(str(e))
                # Setup failed, let's restart and try again after the update
                # interval
                restart()
            else:
                self.didSetup = True

        try:
            if not self.refreshUpdates():
                return
        except yum.Errors.LockError:
            return True # just pass for now

        try:
            self.populateTsInfo()
            self.populateUpdates()

            if self.opts.do_update:
                uit = UpdateInstallThread(self)
                uit.start()
            elif self.opts.do_download:
                self.emitDownloading()
                dl = UpdateDownloadThread(self)
                dl.start()
            else:
                # just notify about things being available
                self.emitAvailable()
                self.releaseLocks()
        except Exception, e:
            self.emitCheckFailed("%s" %(e,))
            self.doUnlock()

        return True

    def getUpdateInfo(self):
        # if we have a cached copy, use it
        if self.updateInfoTime and (time.time() - self.updateInfoTime <
                                    self.opts.updaterefresh):
            return self.updateInfo
            
        # try to get the lock so we can update the info.  fall back to
        # cached if available or try a few times.
        for i in range(10):
            try:
                self.doLock()
                break
            except yum.Errors.LockError:
                # if we can't get the lock, return what we have if we can
                if self.updateInfo:
                    return self.updateInfo
                time.sleep(1)
        else:
            return []

        try:
            self.updateCheckSetup()

            self.populateUpdates()

            self.releaseLocks()
        except:
            self.doUnlock()

        return self.updateInfo

    def updateCheckSetup(self):
        self.doTsSetup()
        self.doRpmDBSetup()
        self.doUpdateSetup()

    def releaseLocks(self):
        self.closeRpmDB()
        self.doUnlock()

    def emitAvailable(self):
        """method to emit a notice about updates"""
        map(lambda x: x.updatesAvailable(self.updateInfo), self.emitters)

    def emitDownloading(self):
        """method to emit a notice about updates downloading"""
        map(lambda x: x.updatesDownloading(self.updateInfo), self.emitters)

    def emitUpdateApplied(self):
        """method to emit a notice when automatic updates applied"""
        map(lambda x: x.updatesApplied(self.updateInfo), self.emitters)

    def emitUpdateFailed(self, errmsgs):
        """method to emit a notice when automatic updates failed"""
        map(lambda x: x.updatesFailed(errmsgs), self.emitters)

    def emitCheckFailed(self, error):
        """method to emit a notice when checking for updates failed"""
        map(lambda x: x.checkFailed(error), self.emitters)

    def emitSetupFailed(self, error, translation_domain=""):
        """method to emit a notice when checking for updates failed"""
        map(lambda x: x.setupFailed(error, translation_domain), self.emitters)


class YumDbusListener(dbus.service.Object):
    def __init__(self, updd, bus_name, object_path='/Updatesd',
                 allowshutdown = False):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.updd = updd
        self.allowshutdown = allowshutdown

    def doCheck(self):
        self.updd.updatesCheck()
        return False

    @dbus.service.method("edu.duke.linux.yum", in_signature="")
    def CheckNow(self):
        # make updating checking asynchronous since we discover whether
        # or not there are updates via a callback signal anyway
        gobject.idle_add(self.doCheck)
        return "check queued"

    @dbus.service.method("edu.duke.linux.yum", in_signature="")
    def ShutDown(self):
        if not self.allowshutdown:
            return False
        
        # we have to do this in a callback so that it doesn't get
        # sent back to the caller
        gobject.idle_add(shutDown)
        return True

    @dbus.service.method("edu.duke.linux.yum", in_signature="", out_signature="a(a{ss}a{ss})")
    def GetUpdateInfo(self):
        # FIXME: should this be async?
        upds = self.updd.getUpdateInfo()
        return upds
        

def shutDown():
    sys.exit(0)

def restart():
    os.chdir(initial_directory)
    os.execve(sys.argv[0], sys.argv, os.environ)  

def main(options = None):
    # we'll be threading for downloads/updates
    gobject.threads_init()
    dbus.glib.threads_init()

    if options is None:
        parser = OptionParser()
        parser.add_option("-f", "--no-fork", action="store_true", default=False, dest="nofork")
        parser.add_option("-r", "--remote-shutdown", action="store_true", default=False, dest="remoteshutdown")    
        (options, args) = parser.parse_args()

        if not options.nofork:
            if os.fork():
                sys.exit()
            fd = os.open("/dev/null", os.O_RDWR)
            os.dup2(fd, 0)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            os.close(fd)

    confparser = ConfigParser()
    opts = UDConfig()
    
    if os.path.exists(config_file):
        confpp_obj = ConfigPreProcessor(config_file)
        try:
            confparser.readfp(confpp_obj)
        except ParsingError, e:
            print >> sys.stderr, "Error reading config file: %s" % e
            sys.exit(1)

    syslog.openlog("yum-updatesd", 0, syslog.LOG_DAEMON)

    opts.populate(confparser, 'main')
    updd = UpdatesDaemon(opts)

    if opts.dbus_listener:
        bus = dbus.SystemBus()
        name = dbus.service.BusName("edu.duke.linux.yum", bus=bus)
        YumDbusListener(updd, name, allowshutdown = options.remoteshutdown)
    
    run_interval_ms = opts.run_interval * 1000 # needs to be in ms
    gobject.timeout_add(run_interval_ms, updd.updatesCheck)

    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
