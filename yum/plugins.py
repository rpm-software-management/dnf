
import os
import glob
import imp
import atexit
from constants import *

# TODO: API version checking
#   - multiversion plugin support?

# TODO: prefix for slot methods ("yum_"?) so that yum knows if plugin is trying
# to hook into something that it doesn't support (eg. new plugin with older yum
# version)

# TODO: move all config hooks to within yum pacakge (not cli.py). This may
# require some minor refactoring of various yum bits.

# TODO: better documentation of how the whole thing works (esp. addition of
# config options)

# TODO: use exception in plugins to signal that yum should abort instead of
# return codes

# TODO: fix log() during yum init: early calls to log() (before Logger instance
# is created) mean that all output goes to stdout regardless of the log settings.

# TODO: reposetup slot: plugin must be able to enable and disable repos

# TODO: make it that plugins need to be expicity enabled so that software using
#   yum as a library doesn't get expected plugin interference?

# TODO: cmd line options to disable plugins (all or specific)

# TODO: cmdline/config option to specify additional plugin directories (plugin path)

# TODO: config vars marked as PLUG_OPT_WHERE_ALL should inherit defaults from
#   the [main] setting if the user doesn't specify them

# TODO: handling of plugins that define options which collide with other
# plugins or builtin yum options

# TODO: plugins should be able to specify convertor functions for config vars

# TODO: investigate potential issues with plugins doing user output during
#   their close handlers, esp wrt GUI apps

# TODO "log" slot? To allow plugins to do customised logging/history (say to a
# SQL db)

# TODO: require an explicit call to load plugins so that software using yum as
# a # library doesn't get nasty suprises

SLOTS = ('config', 'init', 'exclude', 'pretrans', 'posttrans', 'close')

class YumPlugins:

    def __init__(self, base, dir):
        self.dir = dir
        self.base = base
        self._importplugins()
        self.opts = []

        # Call close handlers when yum exit's
        atexit.register(self.run, 'close')

        # Let plugins register custom config file options
        self.run('config')

    def run(self, slotname):
        '''Run all plugin functions for the given slot.
        Returns true if yum needs to quit, false otherwise.
        '''
       
        # Determine handler class to use
        if slotname in ('config'):
            gwcls = ConfigPluginConduit
        elif slotname == 'init':
            gwcls = InitPluginConduit
        elif slotname == 'close':
            gwcls = PluginConduit
        elif slotname in ('pretrans', 'posttrans', 'exclude'):
            gwcls = MainPluginConduit
        else:
            raise ValueError('unknown slot name "%s"' % slotname)

        gw = gwcls(self, self.base)

        for modname, func in self._pluginfuncs[slotname]:
            self.base.log(4, 'Running %s handler for %s plugin' % (
                slotname, modname))
            result = func(gw)
            if result:
                # Plugin said we need to terminate
                self.base.log(2, "Exiting due to '%s' plugin." % modname)
                return result
        return 0

    def _importplugins(self):

        # Initialise plugin dict
        self._plugins = {}
        self._pluginfuncs = {}
        for slot in SLOTS:
            self._pluginfuncs[slot] = []

        # Import plugins and collect plugin calls for each slot
        for module in glob.glob('%s/*.py' % self.dir):
            modname = os.path.basename(module).split('.py')[0]

            self.base.log(2, 'Loading %s plugin' % modname)

            fp, pathname, description = imp.find_module(modname, [self.dir])
            module = imp.load_module(modname, fp, pathname, description)

            #TODO: check API version here?

            self._plugins[modname] = module 
            
            for slot in SLOTS:
                if hasattr(module, slot):
                    self._pluginfuncs[slot].append(
                            (modname, getattr(module, slot))
                            )

    def registeropt(self, name, valuetype, where, default):
        '''Called from plugins to register a new config file option.

        name: Name of the new option.
        valuetype: Option type (PLUG_OPT_BOOL, PLUG_OPT_STRING ...)
        where: Where the option should be available in the config file.
            (PLUG_OPT_WHERE_GLOBAL, PLUG_OPT_WHERE_REPO, ...)
        default: Default value for the option if not set by the user.
        '''
        #TODO: duplicate detection
        self.opts.append((name, valuetype, where, default))

    def getopts(self, targetwhere):
        '''Retrieve plugin defined options for the given part of the
        configuration file. 

        targetwhere: the type of option wanted. Should be
            PLUG_OPT_WHERE_GLOBAL, PLUG_OPT_WHERE_REPO or PLUG_OPT_WHERE_ALL
        return: A list of (name, value_type, default) tuples.
        '''
        out = []
        for name, valuetype, where, default in self.opts:
            if where == targetwhere or where == PLUG_OPT_WHERE_ALL:
                out.append((name, valuetype, default))
        return out

class PluginConduit:
    def __init__(self, parent, base):
        self._parent = parent
        self._base = base

    def info(self, level, msg):
        self._base.log(level, msg)

    def error(self, level, msg):
        self._base.errorlog(level, msg)

    def promptyn(self, msg):
        self.info(2, msg)
        if self._base.conf.getConfigOption('assumeyes'):
            return 1
        else:
            return self._base.userconfirm()

class ConfigPluginConduit(PluginConduit):

    def registeropt(self, *args, **kwargs):
        self._parent.registeropt(*args, **kwargs)

class InitPluginConduit(PluginConduit):

    def getConf(self):
        return self._base.conf

class MainPluginConduit(InitPluginConduit):

    def getRepos(self):
        return self._base.repos.listEnabled()

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




