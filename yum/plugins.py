
import os
import glob
import imp
import atexit
from constants import *
import ConfigParser
import config 
import Errors

# TODO: update yum.conf man page with plugin related opts

# TODO: better documentation of how the whole thing works (esp. addition of
# config options)
#       - document from user perspective in yum man page
#       - PLUGINS.txt for developers

# TODO: test the API by implementing some crack from bugzilla

# TODO: check for *_hook methods that aren't supported

# TODO "log" slot? To allow plugins to do customised logging/history (say to a
# SQL db)

# TODO: multiversion plugin support

# TODO: cmdline options to disable/enable plugins (all or specific)

# TODO: cmdline option to override/specify additional plugin directories

# TODO: config vars marked as PLUG_OPT_WHERE_ALL should inherit defaults from
#   the [main] setting if the user doesn't specify them

# TODO: plugins should be able to specify convertor functions for config vars

# TODO: investigate potential issues with plugins doing user output during
#   their close handlers, esp wrt GUI apps

# TODO: detect conflicts between builtin yum options and registered plugin
# options (will require refactoring of config.py)


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
API_VERSION = '0.2'

SLOTS = ('config', 'init', 'reposetup', 'exclude', 'pretrans', 'posttrans',
        'close')

class PluginYumExit(Errors.YumBaseError):
    '''Used by plugins to signal that yum should stop
    '''

class YumPlugins:

    def __init__(self, base):
        self.enabled = base.conf.plugins
        self.searchpath = base.conf.pluginpath
        self.base = base

        self._importplugins()
        self.opts = {}

        # Call close handlers when yum exit's
        atexit.register(self.run, 'close')

        # Let plugins register custom config file options
        self.run('config')

    def run(self, slotname):
        '''Run all plugin functions for the given slot.
        '''
        if not self.enabled:
            return
       
        # Determine handler class to use
        if slotname in ('config'):
            conduitcls = ConfigPluginConduit
        elif slotname == 'init':
            conduitcls = InitPluginConduit
        elif slotname == 'reposetup':
            conduitcls = RepoSetupPluginConduit
        elif slotname == 'close':
            conduitcls = PluginConduit
        elif slotname in ('pretrans', 'posttrans', 'exclude'):
            conduitcls = MainPluginConduit
        else:
            raise ValueError('unknown slot name "%s"' % slotname)


        for modname, func in self._pluginfuncs[slotname]:
            self.base.log(3, 'Running "%s" handler for "%s" plugin' % (
                slotname, modname))
    
            _, conf = self._plugins[modname]
            func(conduitcls(self, self.base, conf))

    def _importplugins(self):

        if not self.enabled:
            return 0

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
                self._loadplugin(modulefile)

    def _loadplugin(self, modulefile):
        '''Attempt to import a plugin module and register the hook methods it
        uses.
        '''
        dir, modname = os.path.split(modulefile)
        modname = modname.split('.py')[0]

        conf = self._getpluginconf(modname)
        if not conf or not conf._getboolean('main', 'enabled', 0):
            self.base.log(3, '"%s" plugin is disabled' % modname)
            return

        self.base.log(2, 'Loading "%s" plugin' % modname)

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
        '''Parse the plugin specific configuration file and return a CFParser
        instance representing it. Returns None if there was an error reading or
        parsing the configuration file.
        '''
        conffilename = os.path.join('/etc/yum/pluginconf.d', modname+'.conf')

        parser = config.CFParser()
        try:
            fin = open(conffilename, 'rt')
            parser.readfp(fin)
            fin.close()
        except ConfigParser.Error, e:
            raise Errors.ConfigError("Couldn't parse %s: %s" % (conffilename,
                str(e)))
        except IOError, e:
            self.base.log(2, str(e))
            return None

        return parser

    def registeropt(self, name, valuetype, where, default):
        '''Called from plugins to register a new config file option.

        name: Name of the new option.
        valuetype: Option type (PLUG_OPT_BOOL, PLUG_OPT_STRING ...)
        where: Where the option should be available in the config file.
            (PLUG_OPT_WHERE_MAIN, PLUG_OPT_WHERE_REPO, ...)
        default: Default value for the option if not set by the user.
        '''
        if self.opts.has_key(name):
            raise Errors.ConfigError('Plugin option conflict: ' \
                    'an option named "%s" has already been registered' % name
                    )
        self.opts[name] = (valuetype, where, default)

    def parseopts(self, conf, repos):
        '''Parse any configuration options registered by plugins

        conf: the yumconf instance holding Yum's global options
        repos: a list of all repository objects
        '''

        # Process [main] options first
        self._do_opts(conf.cfg, 'main', PLUG_OPT_WHERE_MAIN, 
                conf.setConfigOption)

        # Process repository level options
        for repo in repos:
            self._do_opts(repo.cfgparser, repo.id, PLUG_OPT_WHERE_REPO, 
                repo.set)

    def _do_opts(self, cfgparser, section, targetwhere, setfunc):
        '''Process registered plugin options for one config file section
        '''
        typetofunc =  {
            PLUG_OPT_STRING: cfgparser._getoption,
            PLUG_OPT_INT: cfgparser._getint,
            PLUG_OPT_BOOL: cfgparser._getboolean,
            PLUG_OPT_FLOAT: cfgparser._getfloat,
            }
        for name, (vtype, where, default) in self.opts.iteritems(): 
            if where in (targetwhere, PLUG_OPT_WHERE_ALL):
                setfunc(name, typetofunc[vtype](section, name, default))

class DummyYumPlugins:
    '''
    This class provides basic emulation of the YumPlugins class. It exists so
    that calls to plugins.run() don't fail if plugins aren't in use.
    '''
    def run(self, *args, **kwargs):
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
        if self._base.conf.getConfigOption('assumeyes'):
            return 1
        else:
            return self._base.userconfirm()

    def getYumVersion(self):
        import yum
        return yum.__version__

    def confString(self, section, opt, default=None):
        '''Read a string value from the plugin's own configuration file
        '''
        return self._conf._getoption(section, opt, default)

    def confInt(self, section, opt, default=None):
        '''Read an integer value from the plugin's own configuration file
        '''
        return self._conf._getint(section, opt, default)

    def confFloat(self, section, opt, default=None):
        '''Read a float value from the plugin's own configuration file
        '''
        return self._conf._getfloat(section, opt, default)

    def confBool(self, section, opt, default=None):
        '''Read a boolean value from the plugin's own configuration file
        '''
        return self._conf._getboolean(section, opt, default)

class ConfigPluginConduit(PluginConduit):

    def registerOpt(self, *args, **kwargs):
        self._parent.registeropt(*args, **kwargs)

class InitPluginConduit(PluginConduit):

    def getConf(self):
        return self._base.conf

class RepoSetupPluginConduit(InitPluginConduit):

    def getRepos(self, pattern='*'):
        return self._base.repos.findRepos(pattern)

class MainPluginConduit(RepoSetupPluginConduit):

    def getPackages(self, repo=None):
        if repo:
            arg = repo.id
        else:
            arg = None
        return self._base.pkgSack.returnPackages(arg)

    def delPackage(self, po):
        self._base.pkgSack.delPackage(po)

    def getTsInfo(self):
        return self._base.tsInfo

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



