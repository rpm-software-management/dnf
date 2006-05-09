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
# Copyright 2005 Duke University

import os
import glob
import imp
import warnings
import atexit
from constants import *
import ConfigParser
import config 
import Errors

# XXX: break the API for how plugins define config file options
#   - they should just be able to manipulate the YumConf and RepoConf classes
#     directly, adding Option instances as required
#   - cleaner, more flexible and 
#   - update PLUGINS document
#   - will take care of the following existing TODOs:
# TODO: detect conflicts between builtin yum options and registered plugin
# options (will require refactoring of config.py)
# TODO: plugins should be able to specify convertor functions for config vars

# TODO: should plugin searchpath be affected by installroot option?

# TODO: cleaner method to query installed packages rather than exposing RpmDB
# (Panu?)

# TODO: consistent case of YumPlugins methods

# TODO: expose progress bar interface

# TODO: allow plugins to define new repository types

# TODO: check for *_hook methods that aren't supported

# TODO "log" slot? To allow plugins to do customised logging/history (say to a
# SQL db)

# TODO: multiversion plugin support

# TODO: config vars marked as PLUG_OPT_WHERE_ALL should inherit defaults from
#   the [main] setting if the user doesn't specify them

# TODO: allow plugins to extend shell commands

# TODO: allow plugins to extend commands (on the command line)

# TODO: More developer docs:  use epydoc as API begins to stablise


# The API_VERSION constant defines the current plugin API version. It is used
# to decided whether or not plugins can be loaded. It is compared against the
# 'requires_api_version' attribute of each plugin. The version number has the
# format: "major_version.minor_version".
# 
# For a plugin to be loaded the major version required by the plugin must match
# the major version in API_VERSION. Additionally, the minor version in
# API_VERSION must be greater than or equal the minor version required by the
# plugin.
# 
# If a change to yum is made that break backwards compatibility wrt the plugin
# API, the major version number must be incremented and the minor version number
# reset to 0. If a change is made that doesn't break backwards compatibility,
# then the minor number must be incremented.
API_VERSION = '2.3'

class DeprecatedInt(int):
    '''
    A simple int subclass that used to check when a deprecated constant is used.
    '''

# Plugin types
TYPE_CORE = 0
TYPE_INTERACTIVE = 1
TYPE_INTERFACE = DeprecatedInt(1)
ALL_TYPES = (TYPE_CORE, TYPE_INTERACTIVE)

# Mapping of slots to conduit classes
SLOT_TO_CONDUIT = {
    'config': 'ConfigPluginConduit',
    'init': 'InitPluginConduit',
    'predownload': 'DownloadPluginConduit',
    'postdownload': 'DownloadPluginConduit',
    'prereposetup': 'PreRepoSetupPluginConduit',
    'postreposetup': 'PostRepoSetupPluginConduit',
    'close': 'PluginConduit',
    'clean': 'PluginConduit',
    'pretrans': 'MainPluginConduit',
    'posttrans': 'MainPluginConduit',
    'exclude': 'MainPluginConduit',
    'preresolve': 'DepsolvePluginConduit',
    'postresolve': 'DepsolvePluginConduit',
    }

# Enumerate all slot names
SLOTS = SLOT_TO_CONDUIT.keys()

class PluginYumExit(Exception):
    '''Used by plugins to signal that yum should stop
    '''

class YumPlugins:
    '''
    Manager class for Yum plugins.
    '''

    def __init__(self, base, searchpath, optparser=None, types=None):
        '''Initialise the instance.

        @param base: The
        @param searchpath: A list of paths to look for plugin modules.
        @param optparser: The OptionParser instance for this run (optional).
            Use to allow plugins to extend command line options.
        @param types: A sequence specifying the types of plugins to load.
            This should be sequnce containing one or more of the TYPE_...
            constants. If None (the default), all plugins will be loaded.
        '''

        self.searchpath = searchpath
        self.base = base
        self.optparser = optparser
        self.cmdline = (None, None)
        if not types:
            types = ALL_TYPES

        if id(TYPE_INTERFACE) in [id(t) for t in types]:
            self.base.log(2, 'Deprecated constant TYPE_INTERFACE during plugin '
                    'initialization.\nPlease use TYPE_INTERACTIVE instead.')

        self._importplugins(types)

        self.opts = {}
        self.cmdlines = {}

        # Call close handlers when yum exit's
        atexit.register(self.run, 'close')

        # Let plugins register custom config file options
        self.run('config')

    def run(self, slotname, **kwargs):
        '''Run all plugin functions for the given slot.
        '''
        # Determine handler class to use
        conduitcls = SLOT_TO_CONDUIT.get(slotname, None)
        if conduitcls is None:
            raise ValueError('unknown slot name "%s"' % slotname)
        conduitcls = eval(conduitcls)       # Convert name to class object

        for modname, func in self._pluginfuncs[slotname]:
            self.base.log(3, 'Running "%s" handler for "%s" plugin' % (
                slotname, modname))
    
            _, conf = self._plugins[modname]
            func(conduitcls(self, self.base, conf, **kwargs))

    def _importplugins(self, types):
        '''Load plugins matching the given types.
        '''

        # Initialise plugin dict
        self._plugins = {}
        self._pluginfuncs = {}
        for slot in SLOTS:
            self._pluginfuncs[slot] = []

        # Import plugins 
        for dir in self.searchpath:
            if not os.path.isdir(dir):
                continue
            for modulefile in glob.glob('%s/*.py' % dir):
                self._loadplugin(modulefile, types)

    def _loadplugin(self, modulefile, types):
        '''Attempt to import a plugin module and register the hook methods it
        uses.
        '''
        dir, modname = os.path.split(modulefile)
        modname = modname.split('.py')[0]

        conf = self._getpluginconf(modname)
        if not conf or not config.getOption(conf, 'main', 'enabled', False,
                config.BoolOption()):
            self.base.log(3, '"%s" plugin is disabled' % modname)
            return

        fp, pathname, description = imp.find_module(modname, [dir])
        module = imp.load_module(modname, fp, pathname, description)

        # Check API version required by the plugin
        if not hasattr(module, 'requires_api_version'):
             raise Errors.ConfigError(
                'Plugin "%s" doesn\'t specify required API version' % modname
                )
        if not apiverok(API_VERSION, module.requires_api_version):
            raise Errors.ConfigError(
                'Plugin "%s" requires API %s. Supported API is %s.' % (
                    modname,
                    module.requires_api_version,
                    API_VERSION,
                    ))

        # Check plugin type against filter
        plugintypes = getattr(module, 'plugin_type', ALL_TYPES)
        if not isinstance(plugintypes, (list, tuple)):
            plugintypes = (plugintypes,)

        if len(plugintypes) < 1:
            return
        for plugintype in plugintypes:
            if id(plugintype) == id(TYPE_INTERFACE):
                self.base.log(2, 'Plugin "%s" uses deprecated constant '
                        'TYPE_INTERFACE.\nPlease use TYPE_INTERACTIVE '
                        'instead.' % modname)

            if plugintype not in types:
                return

        self.base.log(2, 'Loading "%s" plugin' % modname)

        # Store the plugin module and its configuration file
        if not self._plugins.has_key(modname):
            self._plugins[modname] = (module, conf)
        else:
            raise Errors.ConfigError('Two or more plugins with the name "%s" ' \
                    'exist in the plugin search path' % modname)
        
        for slot in SLOTS:
            funcname = slot+'_hook'
            if hasattr(module, funcname):
                self._pluginfuncs[slot].append(
                        (modname, getattr(module, funcname))
                        )

    def _getpluginconf(self, modname):
        '''Parse the plugin specific configuration file and return a
        IncludingConfigParser instance representing it. Returns None if there
        was an error reading or parsing the configuration file.
        '''
        #XXX: should this use installroot?
        conffilename = os.path.join('/etc/yum/pluginconf.d', modname+'.conf')

        try:
            parser = config.IncludingConfigParser()
            parser.read(conffilename)
        except ConfigParser.Error, e:
            raise Errors.ConfigError("Couldn't parse %s: %s" % (conffilename,
                str(e)))
        except IOError, e:
            self.base.log(2, str(e))
            return None

        return parser

    def registeropt(self, name, valuetype, where, default):
        '''Called from plugins to register a new config file option.

        @param name: Name of the new option.
        @param valuetype: Option type (PLUG_OPT_BOOL, PLUG_OPT_STRING ...)
        @param where: Where the option should be available in the config file.
            (PLUG_OPT_WHERE_MAIN, PLUG_OPT_WHERE_REPO, ...)
        @param default: Default value for the option if not set by the user.
        '''
        if self.opts.has_key(name):
            raise Errors.ConfigError('Plugin option conflict: ' \
                    'an option named "%s" has already been registered' % name
                    )
        self.opts[name] = (valuetype, where, default)

    def parseopts(self, conf, repos):
        '''Parse any configuration options registered by plugins

        @param conf: the yumconf instance holding Yum's global options
        @param repos: a list of all repository objects
        '''
        #XXX: with the new config stuff this is an ugly hack!
        # See first TODO at top of this file

        type2opt =  {
            PLUG_OPT_STRING: config.Option(),
            PLUG_OPT_INT: config.IntOption(),
            PLUG_OPT_BOOL: config.BoolOption(),
            PLUG_OPT_FLOAT: config.FloatOption(),
            }

        # Process [main] options first
        for name, (vtype, where, default) in self.opts.iteritems(): 
            if where in (PLUG_OPT_WHERE_MAIN, PLUG_OPT_WHERE_ALL):
                val = config.getOption(conf.cfg, 'main', name, default,
                        type2opt[vtype])
                setattr(conf, name, val)

        # Process repository level options
        for repo in repos:
            for name, (vtype, where, default) in self.opts.iteritems(): 
                if where in (PLUG_OPT_WHERE_REPO, PLUG_OPT_WHERE_ALL):
                    val = config.getOption(conf.cfg, repo.id, name, default,
                            type2opt[vtype])
                    repo.setAttribute(name, val)

    def setCmdLine(self, opts, commands):
        '''Set the parsed command line options so that plugins can access them
        '''
        self.cmdline = (opts, commands)


class DummyYumPlugins:
    '''
    This class provides basic emulation of the YumPlugins class. It exists so
    that calls to plugins.run() don't fail if plugins aren't in use.
    '''
    def run(self, *args, **kwargs):
        pass

    def setCmdLine(self, *args, **kwargs):
        pass

class PluginConduit:
    def __init__(self, parent, base, conf):
        self._parent = parent
        self._base = base
        self._conf = conf

    def info(self, level, msg):
        self._base.log(level, msg)

    def error(self, level, msg):
        self._base.errorlog(level, msg)

    def promptYN(self, msg):
        self.info(2, msg)
        if self._base.conf.assumeyes:
            return 1
        else:
            return self._base.userconfirm()

    def getYumVersion(self):
        import yum
        return yum.__version__

    def getOptParser(self):
        '''Return the optparse.OptionParser instance for this execution of Yum

        In the "config" and "init" slots a plugin may add extra options to this
        instance to extend the command line options that Yum exposes.

        In all other slots a plugin may only read the OptionParser instance.
        Any modification of the instance at this point will have no effect. 
        
        See the getCmdLine() method for details on how to retrieve the parsed
        values of command line options.

        @return: the global optparse.OptionParser instance used by Yum. May be
            None if an OptionParser isn't in use.
        '''
        return self._parent.optparser

    def confString(self, section, opt, default=None):
        '''Read a string value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: String option value read, or default if option was missing.
        '''
        return config.getOption(self._conf, section, opt, default,
                config.Option())

    def confInt(self, section, opt, default=None):
        '''Read an integer value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Integer option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, default,
                config.IntOption())

    def confFloat(self, section, opt, default=None):
        '''Read a float value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Float option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, default,
                config.FloatOption())

    def confBool(self, section, opt, default=None):
        '''Read a boolean value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Boolean option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, default,
                config.BoolOption())

class ConfigPluginConduit(PluginConduit):

    def registerOpt(self, *args, **kwargs):
        '''Register a yum configuration file option.

        Arguments are as for YumPlugins.registeropt().
        '''
        self._parent.registeropt(*args, **kwargs)


class InitPluginConduit(PluginConduit):

    def getConf(self):
        return self._base.conf

    def getRepos(self):
        '''Return Yum's container object for all configured repositories.

        @return: Yum's RepoStorage instance
        '''
        return self._base.repos

class PreRepoSetupPluginConduit(InitPluginConduit):

    def getCmdLine(self):
        '''Return parsed command line options.

        @return: (options, commands) as returned by OptionParser.parse_args()
        '''
        return self._parent.cmdline

    def getRpmDB(self):
        '''Return a representation of local RPM database. This allows querying
        of installed packages.

        @return: rpmUtils.RpmDBHolder instance
        '''
        self._base.doTsSetup()
        self._base.doRpmDBSetup()
        return self._base.rpmdb

class PostRepoSetupPluginConduit(PreRepoSetupPluginConduit):

    def getGroups(self):
        '''Return group information.

        @return: yum.comps.Comps instance
        '''
        self._base.doGroupSetup()
        return self._base.comps

class DownloadPluginConduit(PostRepoSetupPluginConduit):

    def __init__(self, parent, base, conf, pkglist, errors=None):
        PostRepoSetupPluginConduit.__init__(self, parent, base, conf)
        self._pkglist = pkglist
        self._errors = errors

    def getDownloadPackages(self):
        '''Return a list of package objects representing packages to be
        downloaded.
        '''
        return self._pkglist

    def getErrors(self):
        '''Return a dictionary of download errors. 
        
        The returned dictionary is indexed by package object. Each element is a
        list of strings describing the error.
        '''
        if not self._errors:
            return {}
        return self._errors

class MainPluginConduit(PostRepoSetupPluginConduit):

    def getPackages(self, repo=None):
        if repo:
            arg = repo.id
        else:
            arg = None
        return self._base.pkgSack.returnPackages(arg)

    def getPackageByNevra(self, nevra):
        '''Retrieve a package object from the packages loaded by Yum using
        nevra information 
        
        @param nevra: A tuple holding (name, epoch, version, release, arch)
            for a package
        @return: A PackageObject instance (or subclass)
        '''
        return self._base.getPackageObject(nevra)

    def delPackage(self, po):
        self._base.pkgSack.delPackage(po)

    def getTsInfo(self):
        return self._base.tsInfo

class DepsolvePluginConduit(MainPluginConduit):
    def __init__(self, parent, base, conf, rescode=None, restring=[]):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.resultcode = rescode
        self.resultstring = restring


def parsever(apiver):
    maj, min = apiver.split('.')
    return int(maj), int(min)

def apiverok(a, b):
    '''Return true if API version "a" supports API version "b"
    '''
    a = parsever(a)
    b = parsever(b)

    if a[0] != b[0]:
        return 0

    if a[1] >= b[1]:
        return 1

    return 0
