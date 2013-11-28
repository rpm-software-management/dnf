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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# Copyright 2005 Duke University

from __future__ import absolute_import
import dnf.logging
import os
import glob
import imp
import atexit
import gettext
import logging
from . import config
from .config import ParsingError, ConfigParser
import dnf.exceptions
from .parser import ConfigPreProcessor

from textwrap import fill
import fnmatch

from .i18n import _, utf8_width

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
    """A simple int subclass that is used to check when a deprecated
    constant is used.
    """

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
    """Exception that can be raised by plugins to signal that yum should stop."""

    def __init__(self, value="", translation_domain=""):
        self.value = value
        self.translation_domain = translation_domain
    def __str__(self):
        if self.translation_domain:
            return gettext.dgettext(self.translation_domain, self.value)
        else:
            return self.value

class YumPlugins:
    """Manager class for Yum plugins."""

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
        self.base = base
        self.optparser = optparser
        self.cmdline = (None, None)
        self.logger = logging.getLogger("dnf")
        self.disabledPlugins = disabled
        self.enabledPlugins  = enabled
        if types is None:
            types = ALL_TYPES
        if not isinstance(types, (list, tuple)):
            types = (types,)

        if id(TYPE_INTERFACE) in [id(t) for t in types]:
            self.logger.info(
                    'Deprecated constant TYPE_INTERFACE during plugin '
                    'initialization.\nPlease use TYPE_INTERACTIVE instead.')

        self._importplugins(types)

        self.cmdlines = {}

        # Call close handlers when yum exit's
        atexit.register(self.run, 'close')

        # Let plugins register custom config file options
        self.run('config')

    def run(self, slotname, **kwargs):
        """Run all plugin functions for the given slot.

        :param slotname: a string representing the name of the slot to
           run the plugins for
        :param kwargs: keyword arguments that will be simply passed on
           to the plugins
        """
        # Determine handler class to use
        conduitcls = SLOT_TO_CONDUIT.get(slotname, None)
        if conduitcls is None:
            raise ValueError('unknown slot name "%s"' % slotname)
        conduitcls = eval(conduitcls)       # Convert name to class object

        for modname, func in self._pluginfuncs[slotname]:
            self.logger.log(dnf.logging.SUBDEBUG,
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
        if self._plugins and not self.base.conf.verbose:
            # Mostly copied from Output._outKeyValFill()
            key = _("Loaded plugins: ")
            val = ", ".join(sorted(self._plugins))
            nxt = ' ' * (utf8_width(key) - 2) + ': '
            width = 80
            if hasattr(self.base, 'term'):
                width = self.base.term.columns
            self.logger.info(
                                    fill(val, width=width, initial_indent=key,
                                         subsequent_indent=nxt))

        if self.disabledPlugins:
            for wc in self.disabledPlugins:
                if wc not in self._used_disable_plugin:
                    self.logger.info(
                                            _("No plugin match for: %s") % wc)
        del self._used_disable_plugin
        if self.enabledPlugins:
            for wc in self.enabledPlugins:
                if wc not in self._used_enable_plugin:
                    self.logger.info(
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
            self.logger.debug(_('Not loading "%s" plugin, as it is disabled'), modname)
            return

        try:
            fp, pathname, description = imp.find_module(modname, [dir])
            try:
                module = imp.load_module(modname, fp, pathname, description)
            finally:
                fp.close()
        except:
            if self.base.conf.verbose:
                raise # Give full backtrace:
            self.logger.error(_('Plugin "%s" can\'t be imported') %
                                      modname)
            return

        # Check API version required by the plugin
        if not hasattr(module, 'requires_api_version'):
            self.logger.error(
                _('Plugin "%s" doesn\'t specify required API version') %
                modname)
            return
        if not apiverok(API_VERSION, module.requires_api_version):
            self.logger.error(
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
                self.logger.info(
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

        self.logger.log(dnf.logging.SUBDEBUG, _('Loading "%s" plugin'),
                                modname)

        # Store the plugin module and its configuration file
        if modname not in self._plugins:
            self._plugins[modname] = (module, conf)
        else:
            raise dnf.exceptions.ConfigError(_('Two or more plugins with the name "%s" ' \
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
            self.logger.info(_("Configuration file %s not found") % conffilename)
        else: # for
            # Configuration files for the plugin not found
            self.logger.info(_("Unable to find configuration file for plugin %s")
                % modname)
            return None
        parser = ConfigParser()
        confpp_obj = ConfigPreProcessor(conffilename)
        try:
            parser.readfp(confpp_obj)
        except ParsingError as e:
            raise dnf.exceptions.ConfigError("Couldn't parse %s: %s" % (conffilename,
                str(e)))
        return parser

    def setCmdLine(self, opts, commands):
        """Set the parsed command line options so that plugins can
        access them.

        :param opts: a dictionary containing the values of the command
           line options
        :param commands: a list of command line arguments passed to yum
        """
        self.cmdline = (opts, commands)


class DummyYumPlugins:
    """This class provides basic emulation of the :class:`YumPlugins`
    class. It exists so that calls to plugins.run() don't fail if
    plugins aren't in use.
    """
    def run(self, *args, **kwargs):
        """Do nothing.  All arguments are unused."""

        pass

    def setCmdLine(self, *args, **kwargs):
        """Do nothing.  All arguments are unused."""

        pass

class PluginConduit:
    """A conduit class to transfer information between yum and the
    plugin.
    """
    def __init__(self, parent, base, conf):
        self._parent = parent
        self._base = base
        self._conf = conf

        self.logger = logging.getLogger("dnf")

    def info(self, level, msg):
        """Send an info message to the logger.

        :param level: the level of the message to send
        :param msg: the message to send
        """
        self.logger.info(msg)

    def error(self, level, msg):
        """Send an error message to the logger.

        :param level: the level of the message to send
        :param msg: the message to send
        """
        self.logger.error(msg)

    def promptYN(self, msg):
        """Return a yes or no response, either from assumeyes already
        being set, or from prompting the user.

        :param msg: the message to prompt the user with
        :return: 1 if the response is yes, and 0 if the response is no
        """
        self.info(2, msg)
        if self._base.conf.assumeyes:
            return 1
        else:
            return self._base.userconfirm()

    def getYumVersion(self):
        """Return a string representing the current version of yum."""

        from dnf import __version__
        return __version__

    def getOptParser(self):
        """Return the :class:`optparse.OptionParser` instance for this
        execution of Yum.  In the "config" and "init" slots a plugin
        may add extra options to this instance to extend the command
        line options that Yum exposes.  In all other slots a plugin
        may only read the :class:`OptionParser` instance.  Any
        modification of the instance at this point will have no
        effect.  See the
        :func:`PreRepoSetupPluginConduit.getCmdLine` method for
        details on how to retrieve the parsed values of command line
        options.

        :return: the global :class:`optparse.OptionParser` instance used by
           Yum. May be None if an OptionParser isn't in use
        """
        return self._parent.optparser

    def confString(self, section, opt, default=None):
        """Read a string value from the plugin's own configuration file.

        :param section: configuration file section to read
        :param opt: option name to read
        :param default: value to read if the option is missing
        :return: string option value read, or default if option was missing
        """
        return config.getOption(self._conf, section, opt, config.Option(default))

    def confInt(self, section, opt, default=None):
        """Read an integer value from the plugin's own configuration file.

        :param section: configuration file section to read
        :param opt: option name to read
        :param default: value to read if the option is missing

        :return: the integer option value read, or *default* if the
            option was missing or could not be parsed
        """
        return config.getOption(self._conf, section, opt, config.IntOption(default))

    def confFloat(self, section, opt, default=None):
        """Read a float value from the plugin's own configuration file.

        :param section: configuration file section to read
        :param opt: option name to read
        :param default: value to read if the option is missing
        :return: float option value read, or *default* if the option was
            missing or could not be parsed
        """
        return config.getOption(self._conf, section, opt, config.FloatOption(default))

    def confBool(self, section, opt, default=None):
        """Read a boolean value from the plugin's own configuration file

        :param section: configuration file section to read
        :param opt: option name to read
        :param default: value to read if the option is missing
        :return: boolean option value read, or *default* if the option
            was missing or could not be parsed
        """
        return config.getOption(self._conf, section, opt, config.BoolOption(default))

    def registerPackageName(self, name):
        """Register the name of a package to use.

        :param name: the name of the package to register
        """
        self._base.conf.history_record_packages.insert(0, name)


class ConfigPluginConduit(PluginConduit):
    """A conduit for use in the config slot."""

    def registerCommand(self, command):
        """Register a new command.

        :param command: the command to register
        :raises: :class:`dnf.exceptions.ConfigError` if the registration
           of commands is not supported
        """
        if hasattr(self._base, 'registerCommand'):
            self._base.registerCommand(command)
        else:
            raise dnf.exceptions.ConfigError(_('registration of commands not supported'))

class PostConfigPluginConduit(ConfigPluginConduit):
    """Conduit for use in the postconfig slot."""

    def getConf(self):
        """Return a dictionary containing the values of the
        configuration options.

        :return: a dictionary containing the values of the
           configuration options
        """
        return self._base.conf

class InitPluginConduit(PluginConduit):
    """Conduit for use in the init slot."""

    def getConf(self):
        """Return a dictionary containing the values of the
        configuration options.

        :return: a dictionary containing the values of the
           configuration options
        """
        return self._base.conf

    def getRepos(self):
        """Return Yum's container object for all configured repositories.

        :return: Yum's :class:`repos.RepoStorage` instance
        """
        return self._base.repos

class ArgsPluginConduit(InitPluginConduit):
    """Conduit for dealing with command line arguments."""

    def __init__(self, parent, base, conf, args):
        InitPluginConduit.__init__(self, parent, base, conf)
        self._args = args

    def getArgs(self):
        """Return a list of the command line arguments passed to yum.

        :return: a list of the command line arguments passed to yum
        """
        return self._args

class PreRepoSetupPluginConduit(InitPluginConduit):
    """Conduit for use in the prererosetup slot."""


    def getCmdLine(self):
        """Return parsed command line options.

        :return: (options, commands) as returned by :class:`OptionParser.parse_args()`
        """
        return self._parent.cmdline

    def getRpmDB(self):
        """Return a representation of the local RPM database. This
        allows querying of installed packages.

        :return: a :class:`dnf.rpmUtils.RpmDBHolder` instance
        """
        return self._base.rpmdb

class PostRepoSetupPluginConduit(PreRepoSetupPluginConduit):
    """Conduit for use in the postreposetup slot."""

    def getGroups(self):
        """Return group information.

        :return: :class:`comps.Comps` instance
        """
        return self._base.comps

class DownloadPluginConduit(PostRepoSetupPluginConduit):
    """Conduit for use in the download slots."""

    def __init__(self, parent, base, conf, pkglist, errors=None):
        PostRepoSetupPluginConduit.__init__(self, parent, base, conf)
        self._pkglist = pkglist
        self._errors = errors

    def getDownloadPackages(self):
        """Return a list of package objects representing packages to be
        downloaded.

        :return: a list of package object representing packages to be
           downloaded
        """
        return self._pkglist

    def getErrors(self):
        """Return a dictionary of download errors.

        :return: a dictionary of download errors. This dictionary is
           indexed by package object. Each element is a list of
           strings describing the error
        """
        if not self._errors:
            return {}
        return self._errors

class MainPluginConduit(PostRepoSetupPluginConduit):
    """Main conduit class for plugins.  Many other conduit classes
    will inherit from this class.
    """
    def getPackages(self, repo=None):
        """Return a list of packages.

        :param repo: the repo to return a packages from
        :return: a list of package objects
        """
        if repo:
            arg = repo.id
        else:
            arg = None
        return self._base.pkgSack.returnPackages(arg)

    def getPackageByNevra(self, nevra):
        """Retrieve a package object from the packages loaded by Yum using
        nevra information.

        :param nevra: a tuple holding (name, epoch, version, release, arch)
            for a package
        :return: a package object
        """
        return self._base.getPackageObject(nevra)

    def delPackage(self, po):
        """Delete the given package from the package sack.

        :param po: the package object to delete
        """
        po.repo.sack.delPackage(po)

    def getTsInfo(self):
        """Return transaction set.

        :return: the transaction set
        """
        return self._base.tsInfo

class DepsolvePluginConduit(MainPluginConduit):
    """Conduit for use in solving dependencies."""

    def __init__(self, parent, base, conf, rescode=None, restring=[]):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.resultcode = rescode
        self.resultstring = restring

class CompareProvidersPluginConduit(MainPluginConduit):
    """Conduit to compare different providers of packages."""

    def __init__(self, parent, base, conf, providers_dict={}, reqpo=None):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.packages = providers_dict
        self.reqpo = reqpo

class HistoryPluginConduit(MainPluginConduit):
    """Conduit to access information about the yum history."""

    def __init__(self, parent, base, conf, rescode=None, restring=[]):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.history = self._base.history

class VerifyPluginConduit(MainPluginConduit):
    """Conduit to verify packages."""

    def __init__(self, parent, base, conf, verify_package):
        MainPluginConduit.__init__(self, parent, base, conf)
        self.verify_package = verify_package

def parsever(apiver):
    """Parse a string representing an api version.

    :param apiver: a string representing an api version
    :return: a tuple containing the major and minor version numbers
    """
    maj, min = apiver.split('.')
    return int(maj), int(min)

def apiverok(a, b):
    """Return true if API version "a" supports API version "b"

    :param a: a string representing an api version
    :param b: a string representing an api version

    :return: whether version *a* supports version *b*
    """
    a = parsever(a)
    b = parsever(b)

    if a[0] != b[0]:
        return 0

    if a[1] >= b[1]:
        return 1

    return 0
