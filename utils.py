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

import yum
from cli import *
import yum.i18n


import yum.plugins as plugins

class YumUtilBase(YumBaseCli):
    def __init__(self,name,ver,usage):
        YumBaseCli.__init__(self)
        self._parser = YumOptionParser(base=self,usage=usage)
        self._usage = usage
        self._utilName = name
        self._utilVer = ver
        
    def getOptionParser(self):
        return self._parser        
    
    def waitForLock(self):
        lockerr = ""
        while True:
            try:
                self.doLock()
            except yum.Errors.LockError, e:
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
        # Read up configuration options and initialise plugins
        try:
            self._getConfig(opts.conffile, root, 
                    init_plugins=not opts.noplugins,
                    plugin_types= pluginsTypes,
                    optparser=self._parser,
                    debuglevel=opts.debuglevel,
                    errorlevel=opts.errorlevel)
        except yum.Errors.ConfigError, e:
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
            self._getRepos()
            self._getSacks()
        except yum.Errors.YumBaseError, msg:
            self.logger.critical(str(msg))
            sys.exit(1)
            
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

    
