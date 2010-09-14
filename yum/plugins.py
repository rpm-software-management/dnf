#! /usr/bin/python -tt
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
import gettext
import logging
import logginglevels
from constants import *
import config 
from config import ParsingError, ConfigParser
import Errors
from parser import ConfigPreProcessor

from textwrap import fill
import fnmatch

from weakref import proxy as weakref

from yum import _

from yum.i18n import utf8_width

# TODO: expose rpm package sack objects to plugins (once finished)
# TODO: allow plugins to use the existing config stuff to define options for
# their own configuration files (would replace confString() etc).
# TODO: expose progress bar interface
# TODO "log" slot? To allow plugins to do customised logging/history (say to a
# SQL db)
# TODO: consistent case of YumPlugins methods
# TODO: allow plugins to extend shell commands
# TODO: allow plugins to define new repository types
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
API_VERSION = '2.6'

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
    'postconfig': 'PostConfigPluginConduit',
    'init': 'InitPluginConduit',
    'args': 'ArgsPluginConduit',
    'predownload': 'DownloadPluginConduit',
    'postdownload': 'DownloadPluginConduit',
    'prereposetup': 'PreRepoSetupPluginConduit',
    'postreposetup': 'PostRepoSetupPluginConduit',
    'close': 'PluginConduit',
    'clean': 'PluginConduit',
    'pretrans': 'MainPluginConduit',
    'posttrans': 'MainPluginConduit',
    'preverifytrans': 'MainPluginConduit',
    'postverifytrans': 'MainPluginConduit',
    'exclude': 'MainPluginConduit',
    'preresolve': 'DepsolvePluginConduit',
    'postresolve': 'DepsolvePluginConduit',
    'historybegin': 'HistoryPluginConduit',
    'historyend': 'HistoryPluginConduit',
    'compare_providers': 'CompareProvidersPluginConduit',
    'verify_package': 'VerifyPluginConduit',
    }

# Enumerate all slot names
SLOTS = sorted(SLOT_TO_CONDUIT.keys())

class PluginYumExit(Exception):
    '''Used by plugins to signal that yum should stop
    '''
    def __init__(self, value="", translation_domain=""):
        self.value = value
        self.translation_domain = translation_domain
    def __str__(self):
        if self.translation_domain:
            return gettext.dgettext(self.translation_domain, self.value)
        else:
            return self.value
    
class YumPlugins:
    '''
    Manager class for Yum plugins.
    '''

    def __init__(self, base, searchpath, optparser=None, types=None, 
            pluginconfpath=None,disabled=None,enabled=None):
        '''Initialise the instance.

        @param base: The
        @param searchpath: A list of paths to look for plugin modules.
        @param optparser: The OptionParser instance for this run (optional).
            Use to allow plugins to extend command line options.
        @param types: A sequence specifying the types of plugins to load.
            This should be sequnce containing one or more of the TYPE_...
            constants. If None (the default), all plugins will be loaded.
        @param pluginconfpath: A list of paths to look for plugin configuration
            files. Defaults to "/etc/yum/pluginconf.d".
        '''
        if not pluginconfpath:
            pluginconfpath = ['/etc/yum/pluginconf.d']

        self.searchpath = searchpath
        self.pluginconfpath = pluginconfpath
        self.base = weakref(base)
        self.optparser = optparser
        self.cmdline = (None, None)
        self.verbose_logger = logging.getLogger("yum.verbose.YumPlugins")
        self.disabledPlugins = disabled
        self.enabledPlugins  = enabled
        if types is None:
            types = ALL_TYPES
        if not isinstance(types, (list, tuple)):
            types = (types,)

        if id(TYPE_INTERFACE) in [id(t) for t in types]:
            self.verbose_logger.log(logginglevels.INFO_2,
                    'Deprecated constant TYPE_INTERFACE during plugin '
                    'initialization.\nPlease use TYPE_INTERACTIVE instead.')

        self._importplugins(types)

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
            self.verbose_logger.log(logginglevels.DEBUG_4,
                                    'Running "%s" handler for "%s" plugin',
                                    slotname, modname)
    
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
        self._used_disable_plugin = set()
        self._used_enable_plugin  = set()
        for dir in self.searchpath:
            if not os.path.isdir(dir):
                continue
            for modulefile in sorted(glob.glob('%s/*.py' % dir)):
                self._loadplugin(modulefile, types)

        # If we are in verbose mode we get the full 'Loading "blah" plugin' lines
        if (self._plugins and
            not self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)):
            # Mostly copied from YumOutput._outKeyValFill()
            key = _("Loaded plugins: ")
            val = ", ".join(sorted(self._plugins))
            nxt = ' ' * (utf8_width(key) - 2) + ': '
            width = 80
            if hasattr(self.base, 'term'):
                width = self.base.term.columns
            self.verbose_logger.log(logginglevels.INFO_2,
                                    fill(val, width=width, initial_indent=key,
                                         subsequent_indent=nxt))

        if self.disabledPlugins:
            for wc in self.disabledPlugins:
                if wc not in self._used_disable_plugin:
                    self.verbose_logger.log(logginglevels.INFO_2,
                                            _("No plugin match for: %s") % wc)
        del self._used_disable_plugin
        if self.enabledPlugins:
            for wc in self.enabledPlugins:
                if wc not in self._used_enable_plugin:
                    self.verbose_logger.log(logginglevels.INFO_2,
                                            _("No plugin match for: %s") % wc)
        del self._used_enable_plugin

    @staticmethod
    def _plugin_cmdline_match(modname, plugins, used):
        """ Check if this plugin has been temporary enabled/disabled. """
        if plugins is None:
            return False

        for wc in plugins:
            if fnmatch.fnmatch(modname, wc):
                used.add(wc)
                return True

        return False


    def _loadplugin(self, modulefile, types):
        '''Attempt to import a plugin module and register the hook methods it
        uses.
        '''
        dir, modname = os.path.split(modulefile)
        modname = modname.split('.py')[0]

        conf = self._getpluginconf(modname)
        if (not conf or
            (not config.getOption(conf, 'main', 'enabled',
                                  config.BoolOption(False)) and
             not self._plugin_cmdline_match(modname, self.enabledPlugins,
                                            self._used_enable_plugin))):
            self.verbose_logger.debug(_('Not loading "%s" plugin, as it is disabled'), modname)
            return

        try:
            fp, pathname, description = imp.find_module(modname, [dir])
            try:
                module = imp.load_module(modname, fp, pathname, description)
            finally:
                fp.close()
        except:
            if self.verbose_logger.isEnabledFor(logginglevels.DEBUG_4):
                raise # Give full backtrace:
            self.verbose_logger.error(_('Plugin "%s" can\'t be imported') %
                                      modname)
            return

        # Check API version required by the plugin
        if not hasattr(module, 'requires_api_version'):
            self.verbose_logger.error(
                _('Plugin "%s" doesn\'t specify required API version') %
                modname)
            return
        if not apiverok(API_VERSION, module.requires_api_version):
            self.verbose_logger.error(
                _('Plugin "%s" requires API %s. Supported API is %s.') % (
                    modname,
                    module.requires_api_version,
                    API_VERSION,
                    ))
            return

        # Check plugin type against filter
        plugintypes = getattr(module, 'plugin_type', ALL_TYPES)
        if not isinstance(plugintypes, (list, tuple)):
            plugintypes = (plugintypes,)

        if len(plugintypes) < 1:
            return
        for plugintype in plugintypes:
            if id(plugintype) == id(TYPE_INTERFACE):
                self.verbose_logger.log(logginglevels.INFO_2,
                        'Plugin "%s" uses deprecated constant '
                        'TYPE_INTERFACE.\nPlease use TYPE_INTERACTIVE '
                        'instead.', modname)

            if plugintype not in types:
                return

        #  This should really work like enable/disable repo. and be based on the
        # cmd line order ... but the API doesn't really allow that easily.
        # FIXME: Fix for 4.*
        if (self._plugin_cmdline_match(modname, self.disabledPlugins,
                                       self._used_disable_plugin) and
            not self._plugin_cmdline_match(modname, self.enabledPlugins,
                                           self._used_enable_plugin)):
            return

        self.verbose_logger.log(logginglevels.DEBUG_3, _('Loading "%s" plugin'),
                                modname)

        # Store the plugin module and its configuration file
        if modname not in self._plugins:
            self._plugins[modname] = (module, conf)
        else:
            raise Errors.ConfigError(_('Two or more plugins with the name "%s" ' \
                    'exist in the plugin search path') % modname)
        
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
        for dir in self.pluginconfpath:
            conffilename = os.path.join(dir, modname + ".conf")
            if os.access(conffilename, os.R_OK):
                # Found configuration file
                break
            self.verbose_logger.log(logginglevels.INFO_2, _("Configuration file %s not found") % conffilename)
        else: # for
            # Configuration files for the plugin not found
            self.verbose_logger.log(logginglevels.INFO_2, _("Unable to find configuration file for plugin %s")
                % modname)
            return None
        parser = ConfigParser()
        confpp_obj = ConfigPreProcessor(conffilename)
        try:
            parser.readfp(confpp_obj)
        except ParsingError, e:
            raise Errors.ConfigError("Couldn't parse %s: %s" % (conffilename,
                str(e)))
        return parser

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

        self.logger = logging.getLogger("yum.plugin")
        self.verbose_logger = logging.getLogger("yum.verbose.plugin")

    def info(self, level, msg):
        converted_level = logginglevels.logLevelFromDebugLevel(level)
        self.verbose_logger.log(converted_level, msg)

    def error(self, level, msg):
        converted_level = logginglevels.logLevelFromErrorLevel(level)
        self.logger.log(converted_level, msg)

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
        # ' xemacs highlighting hack
        # This isn't API compatible :(
        # return self._parent.optparser.plugin_option_group
        return self._parent.optparser

    def confString(self, section, opt, default=None):
        '''Read a string value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: String option value read, or default if option was missing.
        '''
        # ' xemacs highlighting hack
        return config.getOption(self._conf, section, opt, config.Option(default))

    def confInt(self, section, opt, default=None):
        '''Read an integer value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Integer option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, config.IntOption(default))

    def confFloat(self, section, opt, default=None):
        '''Read a float value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Float option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, config.FloatOption(default))

    def confBool(self, section, opt, default=None):
        '''Read a boolean value from the plugin's own configuration file

        @param section: Configuration file section to read.
        @param opt: Option name to read.
        @param default: Value to read if option is missing.
        @return: Boolean option value read, or default if option was missing or
            could not be parsed.
        '''
        return config.getOption(self._conf, section, opt, config.BoolOption(default))

    def registerPackageName(self, name):
        self._base.run_with_package_names.add(name)


class ConfigPluginConduit(PluginConduit):

    def registerOpt(self, name, valuetype, where, default):
        '''Register a yum configuration file option.

        @param name: Name of the new option.
        @param valuetype: Option type (PLUG_OPT_BOOL, PLUG_OPT_STRING ...)
        @param where: Where the option should be available in the config file.
            (PLUG_OPT_WHERE_MAIN, PLUG_OPT_WHERE_REPO, ...)
        @param default: Default value for the option if not set by the user.
        '''
        warnings.warn('registerOpt() will go away in a future version of Yum.\n'
                'Please manipulate config.YumConf and config.RepoConf directly.',
                DeprecationWarning)

        type2opt =  {
            PLUG_OPT_STRING: config.Option,
            PLUG_OPT_INT: config.IntOption,
            PLUG_OPT_BOOL: config.BoolOption,
            PLUG_OPT_FLOAT: config.FloatOption,
            }

        if where == PLUG_OPT_WHERE_MAIN:
            setattr(config.YumConf, name, type2opt[valuetype](default))

        elif where == PLUG_OPT_WHERE_REPO:
            setattr(config.RepoConf, name, type2opt[valuetype](default))

        elif where == PLUG_OPT_WHERE_ALL:
            option = type2opt[valuetype](default)
            setattr(config.YumConf, name, option)
            setattr(config.RepoConf, name, config.Inherit(option))

    def registerCommand(self, command):
        if hasattr(self._base, 'registerCommand'):
            self._base.registerCommand(command)
        else:
            raise Errors.ConfigError(_('registration of commands not supported'))

class PostConfigPluginConduit(ConfigPluginConduit):

    def getConf(self):
        return self._base.conf

class InitPluginConduit(PluginConduit):

    def getConf(self):
        return self._base.conf

    def getRepos(self):
        '''Return Yum's container object for all configured repositories.

        @return: Yum's RepoStorage instance
        '''
        return self._base.repos

class ArgsPluginConduit(InitPluginConduit):

    def __init__(self, parent, base, conf, args):
        InitPluginConduit.__init__(self, parent, base, conf)
        self._args = args

    def getArgs(self):
        return self._args

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
        return self._base.rpmdb

class PostRepoSetupPluginConduit(PreRepoSetupPluginConduit):

    def getGroups(self):
        '''Return group information.

        @return: yum.comps.Comps instance
        '''
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
        po.repo.sack.delPackage(po)

    def getTsInfo(self):
        return self._base.tsInfo

class DepsolvePluginConduit(MainPluginConduit):
    def __init__(self, parent, base, conf, rescode=None, restring=[]):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.resultcode = rescode
        self.resultstring = restring

class CompareProvidersPluginConduit(MainPluginConduit):
    def __init__(self, parent, base, conf, providers_dict={}, reqpo=None):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.packages = providers_dict
        self.reqpo = reqpo

class HistoryPluginConduit(MainPluginConduit):
    def __init__(self, parent, base, conf, rescode=None, restring=[]):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.history = self._base.history

class VerifyPluginConduit(MainPluginConduit):
    def __init__(self, parent, base, conf, verify_package):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.verify_package = verify_package

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
