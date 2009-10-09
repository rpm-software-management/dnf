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

import sys
import time
import exceptions

import yum
from cli import *
from yum import Errors
from yum import _
from yum import logginglevels
from optparse import OptionGroup

import yum.plugins as plugins


def suppress_keyboard_interrupt_message():
    old_excepthook = sys.excepthook

    def new_hook(type, value, traceback):
        if type != exceptions.KeyboardInterrupt:
            old_excepthook(type, value, traceback)
        else:
            pass

    sys.excepthook = new_hook

class YumUtilBase(YumBaseCli):
    def __init__(self,name,ver,usage):
        YumBaseCli.__init__(self)
        self._parser = YumOptionParser(base=self,utils=True,usage=usage)
        self._usage = usage
        self._utilName = name
        self._utilVer = ver
        self._option_group = OptionGroup(self._parser, "%s options" % self._utilName,"")
        self._parser.add_option_group(self._option_group)
        suppress_keyboard_interrupt_message()
        
    def getOptionParser(self):
        return self._parser        

    def getOptionGroup(self):
        """ Get an option group to add non inherited options"""
        return self._option_group    
    
    def waitForLock(self):
        lockerr = ""
        while True:
            try:
                self.doLock()
            except Errors.LockError, e:
                if "%s" %(e.msg,) != lockerr:
                    lockerr = "%s" %(e.msg,)
                    self.logger.critical(lockerr)
                self.logger.critical("Another app is currently holding the yum lock; waiting for it to exit...")  
                time.sleep(2)
            else:
                break
        
    def _printUtilVersion(self):
        print "%s - %s (yum - %s)" % (self._utilName,self._utilVer,yum.__version__)
        
    def doUtilConfigSetup(self,args = sys.argv[1:],pluginsTypes=(plugins.TYPE_CORE,)):
        # Parse only command line options that affect basic yum setup
        opts = self._parser.firstParse(args)
        # Just print out the version if that's what the user wanted
        if opts.version:
            self._printUtilVersion()
            sys.exit(0)
        # get the install root to use
        root = self._parser.getRoot(opts)
        if opts.quiet:
            opts.debuglevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = 6
        
        # Read up configuration options and initialise plugins
        try:
            pc = self.preconf
            pc.fn = opts.conffile
            pc.root = root
            pc.init_plugins = not opts.noplugins
            pc.plugin_types = pluginsTypes
            pc.optparser = self._parser
            pc.debuglevel = opts.debuglevel
            pc.errorlevel = opts.errorlevel
            if hasattr(opts, "disableplugins"):
                pc.disabled_plugins =self._parser._splitArg(opts.disableplugins)
            if hasattr(opts, "enableplugins"):
                pc.enabled_plugins = self._parser._splitArg(opts.enableplugins)
            self.conf

        except Errors.ConfigError, e:
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            sys.exit(1)


        # update usage in case plugins have added commands
        self._parser.set_usage(self._usage)
        
        # Now parse the command line for real and 
        # apply some of the options to self.conf
        (opts, self.cmds) = self._parser.setupYumConfig()
        return opts

    def doUtilYumSetup(self):
        """do a default setup for all the normal/necessary yum components,
           really just a shorthand for testing"""
        # FIXME - we need another way to do this, I think.
        try:
            self._getTs()
            self._getRpmDB()
            self._getRepos(doSetup = True)
            self._getSacks()
        except Errors.YumBaseError, msg:
            self.logger.critical(str(msg))
            sys.exit(1)
    
    def doUtilTransaction(self):
        def exUserCancel():
            self.logger.critical(_('\n\nExiting on user cancel'))
            if unlock(): return 200
            return 1

        def exIOError(e):
            if e.errno == 32:
                self.logger.critical(_('\n\nExiting on Broken Pipe'))
            else:
                self.logger.critical(_('\n\n%s') % str(e))
            if unlock(): return 200
            return 1

        def exPluginExit(e):
            '''Called when a plugin raises PluginYumExit.

            Log the plugin's exit message if one was supplied.
            ''' # ' xemacs hack
            exitmsg = str(e)
            if exitmsg:
                self.logger.warn('\n\n%s', exitmsg)
            if unlock(): return 200
            return 1

        def exFatal(e):
            self.logger.critical('\n\n%s', to_unicode(e.value))
            if unlock(): return 200
            return 1

        def unlock():
            try:
                self.closeRpmDB()
                self.doUnlock()
            except Errors.LockError, e:
                return 200
            return 0

        try:
            return_code = self.doTransaction()
        except plugins.PluginYumExit, e:
            return exPluginExit(e)
        except Errors.YumBaseError, e:
            return exFatal(e)
        except KeyboardInterrupt:
            return exUserCancel()
        except IOError, e:
            return exIOError(e)

        self.verbose_logger.log(logginglevels.INFO_2, _('Complete!'))
        if unlock(): return 200
        return return_code
        
def main():
    name = 'testutil'
    ver  = '0.1'
    usage = 'testutil [options] [args]'
    util = YumUtilBase(name,ver,usage)
    parser = util.getOptionParser() 
    parser.add_option("", "--myoption", dest="myoption",
                    action="store_true", default=False, 
                    help="This is an util option")
    util.logger.info("Setup Yum Config")
    opts = util.doUtilConfigSetup()
    util.logger.info("Setup Yum")
    util.doUtilYumSetup()
    print "Command line args: %s" % " ".join(util.cmds)
    print "Command line options :"
    print opts
    
    util.logger.info("%s Completed" % name)
if __name__ == '__main__':
    main()

    
