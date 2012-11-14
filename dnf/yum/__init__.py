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

"""
The Yum RPM software updater.
"""

import os
import os.path
import rpm

def _rpm_ver_atleast(vertup):
    """ Check if rpm is at least the current vertup. Can return False/True/None
        as rpm hasn't had version info for a long time. """
    if not hasattr(rpm, '__version_info__'):
        return None
    try:
        # 4.8.x rpm used strings for the tuple members, so convert.
        vi = tuple([ int(num) for num in rpm.__version_info__])
        return vi >= vertup
    except:
        return None # Something went wrong...

import re
import types
import errno
import time
import glob
import fnmatch
import logging
import logging.config
import operator
import tempfile

import i18n
_ = i18n._
P_ = i18n.P_

import config
from config import ParsingError, ConfigParser
import Errors
import rpmsack
from dnf.rpmUtils.arch import archDifference, canCoinstall, ArchStorage, isMultiLibArch
from dnf.rpmUtils.miscutils import compareEVR
import dnf.rpmUtils.transaction
import comps
from repos import RepoStorage
import misc
from parser import ConfigPreProcessor, varReplace
import transactioninfo
import urlgrabber
from urlgrabber.grabber import URLGrabber, URLGrabError
from urlgrabber.progress import format_number
import plugins
import logginglevels
import yumRepo
import callbacks
import history

import warnings
warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)

from packages import parsePackages, comparePoEVR
from packages import YumAvailablePackage, YumLocalPackage
from packages import YumUrlPackage, YumNotFoundPackage
from constants import *
from rpmtrans import RPMTransaction,SimpleCliCallBack
from i18n import to_unicode, to_str, exception2msg

import string
import StringIO

from weakref import proxy as weakref

from urlgrabber.grabber import default_grabber

import hawkey
import dnf.conf
import dnf.package
import dnf.util
import dnf.rpmUtils.connection
from dnf import const, queries, sack, selector

__version__ = '3.4.3'
__version_info__ = tuple([ int(num) for num in __version__.split('.')])

#  Setup a default_grabber UA here that says we are yum, done using the global
# so that other API users can easily add to it if they want.
#  Don't do it at init time, or we'll get multiple additions if you create
# multiple YumBase() objects.
default_grabber.opts.user_agent += " yum/" + __version__


class _YumPreBaseConf:
    """This is the configuration interface for the :class:`YumBase`
    configuration.  To change configuration settings such as whether
    plugins are on or off, or the value of debuglevel, change the
    values here. Later, when :func:`YumBase.conf` is first called, all
    of the options will be automatically configured.
    """
    def __init__(self):
        self.fn = const.CONF_FILENAME
        self.root = '/'
        self.init_plugins = True
        self.plugin_types = (plugins.TYPE_CORE,)
        self.optparser = None
        self.debuglevel = None
        self.errorlevel = None
        self.disabled_plugins = None
        self.enabled_plugins = None
        self.syslog_ident = None
        self.syslog_facility = None
        self.syslog_device = None
        self.arch = None
        self.releasever = None
        self.uuid = None


class _YumPreRepoConf:
    """This is the configuration interface for the repos configuration
    configuration.  To change configuration settings such what
    callbacks are used, change the values here. Later, when
    :func:`YumBase.repos` is first called, all of the options will be
    automatically configured.
    """
    def __init__(self):
        self.progressbar = None
        self.callback = None
        self.failure_callback = None
        self.interrupt_callback = None
        self.confirm_func = None
        self.gpg_import_func = None
        self.gpgca_import_func = None
        self.cachedir = None
        self.cache = None


class _YumCostExclude:
    """ This excludes packages that are in repos. of lower cost than the passed
        repo. """

    def __init__(self, repo, repos):
        self.repo   = weakref(repo)
        self._repos = weakref(repos)

    def __contains__(self, pkgtup):
        # (n, a, e, v, r) = pkgtup
        for repo in self._repos.listEnabled():
            if repo.cost >= self.repo.cost:
                break
            #  searchNevra is a bit slower, although more generic for repos.
            # that don't use sqlitesack as the backend ... although they are
            # probably screwed anyway.
            #
            # if repo.sack.searchNevra(n, e, v, r, a):
            if pkgtup in repo.sack._pkgtup2pkgs:
                return True
        return False

class YumBase(object):
    """This is a primary structure and base class. It houses the
    objects and methods needed to perform most things in yum. It is
    almost an abstract class in that you will need to add your own
    class above it for most real use.
    """
    def __init__(self):
        self._conf = None
        self._ts = None
        self._tsInfo = None
        self._comps = None
        self._history = None
        self._pkgSack = None
        self._lockfile = None
        self._tags = None
        self._ts_save_file = None
        self._not_found_a = {}
        self._not_found_i = {}
        self.logger = logging.getLogger("yum.YumBase")
        self.verbose_logger = logging.getLogger("yum.verbose.YumBase")
        self._override_sigchecks = False
        self._repos = RepoStorage(self)
        self.repo_setopts = {} # since we have to use repo_setopts in base and
                               # not in cli - set it up as empty so no one
                               # trips over it later

        # Start with plugins disabled
        self.disablePlugins()

        self.localPackages = [] # for local package handling

        self.mediagrabber = None
        self.arch = ArchStorage()
        self.preconf = _YumPreBaseConf()
        self.prerepoconf = _YumPreRepoConf()

        self.run_with_package_names = set()
        self._cleanup = []
        self._sack = None
        self.cache_c = dnf.conf.Cache()

    def __del__(self):
        self.close()
        self.closeRpmDB()
        self.doUnlock()
        # call cleanup callbacks
        for cb in self._cleanup: cb()

    def _add_repo_to_hawkey(self, name):
        repo = hawkey.Repo(name)
        yum_repo = self.repos.repos[name]
        repo.repomd_fn = yum_repo.repoXML.srcfile
        repo.primary_fn = yum_repo.getPrimaryXML()
        repo.filelists_fn = yum_repo.getFileListsXML()
        try:
            repo.presto_fn = yum_repo.getPrestoXML()
        except Errors.RepoMDError, e:
            self.verbose_logger.debug("not found deltainfo for: %s" %
                                      yum_repo.name)
        yum_repo.hawkey_repo = repo
        self._sack.load_yum_repo(repo, build_cache=True, load_filelists=True)

    @property
    @dnf.util.lazyattr("_rpm")
    def rpm(self):
        return dnf.rpmUtils.connection.RpmConnection(self.conf.installroot)

    @property
    def sack(self):
        if self._sack:
            return self._sack
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a YumBase reference.
        start = time.time()
        self._sack = sack.build_sack(self)
        self._sack.load_system_repo(build_cache=True)
        for r in self.repos.listEnabled():
            self._add_repo_to_hawkey(r.id)
        self._sack.installonly = self.conf.installonlypkgs
        self.verbose_logger.debug('hawkey sack setup time: %0.3f' %
                                  (time.time() - start))
        return self._sack

    @property
    @dnf.util.lazyattr("_yumdb")
    def yumdb(self):
        db_path = os.path.normpath(self.conf.persistdir + '/yumdb')
        return rpmsack.RPMDBAdditionalData(db_path)

    def close(self):
        """Close the history and repo objects."""

        # We don't want to create the object, so we test if it's been created
        if self._history is not None:
            self.history.close()

        if self._repos:
            self._repos.close()

    def doGenericSetup(self, cache=0):
        """Do a default setup for all the normal or necessary yum
        components.  This function is really just a shorthand for
        testing purposes.

        :param cache: whether to run in cache only mode, which will
           run only from the system cache
        """
        self.preconf.init_plugins = False
        self.conf.cache = cache

    def _getConfig(self):
        '''
        Parse and load Yum's configuration files and call hooks initialise
        plugins and logging. Uses self.preconf for pre-configuration,
        configuration. '''

        if self._conf:
            return self._conf
        conf_st = time.time()

        fn = self.preconf.fn
        root = self.preconf.root
        init_plugins = self.preconf.init_plugins
        plugin_types = self.preconf.plugin_types
        optparser = self.preconf.optparser
        debuglevel = self.preconf.debuglevel
        errorlevel = self.preconf.errorlevel
        disabled_plugins = self.preconf.disabled_plugins
        enabled_plugins = self.preconf.enabled_plugins
        syslog_ident    = self.preconf.syslog_ident
        syslog_facility = self.preconf.syslog_facility
        syslog_device   = self.preconf.syslog_device
        releasever = self.preconf.releasever
        arch = self.preconf.arch
        uuid = self.preconf.uuid

        if arch: # if preconf is setting an arch we need to pass that up
            self.arch.setup_arch(arch)
        else:
            arch = self.arch.canonarch

        startupconf = config.readStartupConfig(fn, root, releasever)
        startupconf.arch = arch
        startupconf.basearch = self.arch.basearch
        if uuid:
            startupconf.uuid = uuid

        if startupconf.gaftonmode:
            global _
            _ = i18n.dummy_wrapper

        if debuglevel != None:
            startupconf.debuglevel = debuglevel
        if errorlevel != None:
            startupconf.errorlevel = errorlevel
        if syslog_ident != None:
            startupconf.syslog_ident = syslog_ident
        if syslog_facility != None:
            startupconf.syslog_facility = syslog_facility
        if syslog_device != None:
            startupconf.syslog_device = syslog_device
        if releasever == '/':
            if startupconf.installroot == '/':
                releasever = None
            else:
                releasever = config._getsysver("/",startupconf.distroverpkg)
        if releasever != None:
            startupconf.releasever = releasever

        self.doLoggingSetup(startupconf.debuglevel, startupconf.errorlevel,
                            startupconf.syslog_ident,
                            startupconf.syslog_facility,
                            startupconf.syslog_device)

        if init_plugins and startupconf.plugins:
            self.doPluginSetup(optparser, plugin_types, startupconf.pluginpath,
                    startupconf.pluginconfpath,disabled_plugins,enabled_plugins)

        self._conf = config.readMainConfig(startupconf)

        #  We don't want people accessing/altering preconf after it becomes
        # worthless. So we delete it, and thus. it'll raise AttributeError
        del self.preconf

        # Packages used to run yum...
        for pkgname in self.conf.history_record_packages:
            self.run_with_package_names.add(pkgname)

        # run the postconfig plugin hook
        self.plugins.run('postconfig')
        #  Note that Pungi has historically replaced _getConfig(), and it sets
        # up self.conf.yumvar but not self.yumvar ... and AFAIK nothing needs
        # to use YumBase.yumvar, so it's probably easier to just semi-deprecate
        # this (core now only uses YumBase.conf.yumvar).
        self.yumvar = self.conf.yumvar

        # who are we:
        self.conf.uid = os.geteuid()
        # repos are ver/arch specific so add $basearch/$releasever
        self.conf._repos_persistdir = os.path.normpath('%s/repos/%s/%s/'
               % (self.conf.persistdir,  self.yumvar.get('basearch', '$basearch'),
                  self.yumvar.get('releasever', '$releasever')))
        logginglevels.setFileLogs(self.conf.logdir, self._cleanup)
        self.verbose_logger.debug('Config time: %0.3f' % (time.time() - conf_st))
        self.plugins.run('init')
        return self._conf

    def doLoggingSetup(self, debuglevel, errorlevel,
                       syslog_ident=None, syslog_facility=None,
                       syslog_device='/dev/log'):
        """Perform logging related setup.

        :param debuglevel: the minimum debug logging level to output
           messages from
        :param errorlevel: the minimum error logging level to output
           messages from
        :param syslog_ident: the ident of the syslog to use
        :param syslog_facility: the name of the syslog facility to use
        :param syslog_device: the syslog device to use
        """
        logginglevels.doLoggingSetup(debuglevel, errorlevel,
                                     syslog_ident, syslog_facility,
                                     syslog_device)

    def getReposFromConfigFile(self, repofn, repo_age=None, validate=None):
        """Read in repositories from a config .repo file.

        :param repofn: a string specifying the path of the .repo file
           to read
        :param repo_age: the last time that the .repo file was
           modified, in seconds since the epoch
        """
        if repo_age is None:
            repo_age = os.stat(repofn)[8]

        confpp_obj = ConfigPreProcessor(repofn, vars=self.conf.yumvar)
        parser = ConfigParser()
        try:
            parser.readfp(confpp_obj)
        except ParsingError, e:
            msg = str(e)
            raise Errors.ConfigError, msg

        # Check sections in the .repo file that was just slurped up
        for section in parser.sections():

            if section in ['main', 'installed']:
                continue

            # Check the repo.id against the valid chars
            bad = None
            for byte in section:
                if byte in string.ascii_letters:
                    continue
                if byte in string.digits:
                    continue
                if byte in "-_.:":
                    continue

                bad = byte
                break

            if bad:
                self.logger.warning("Bad id for repo: %s, byte = %s %d" %
                                    (section, bad, section.find(bad)))
                continue

            try:
                thisrepo = self.readRepoConfig(parser, section)
            except (Errors.RepoError, Errors.ConfigError), e:
                self.logger.warning(e)
                continue
            else:
                thisrepo.repo_config_age = repo_age
                thisrepo.repofile = repofn

                thisrepo.base_persistdir = self.conf._repos_persistdir


            if thisrepo.id in self.repo_setopts:
                for opt in self.repo_setopts[thisrepo.id].items:
                    if not hasattr(thisrepo, opt):
                        msg = "Repo %s did not have a %s attr. before setopt"
                        self.logger.warning(msg % (thisrepo.id, opt))
                    setattr(thisrepo, opt, getattr(self.repo_setopts[thisrepo.id], opt))

            if validate and not validate(thisrepo):
                continue

            # Got our list of repo objects, add them to the repos
            # collection
            try:
                self._repos.add(thisrepo)
            except Errors.RepoError, e:
                self.logger.warning(e)

    def getReposFromConfig(self):
        """Read in repositories from the main yum conf file, and from
        .repo files.  The location of the main yum conf file is given
        by self.conf.config_file_path, and the location of the
        directory of .repo files is given by self.conf.reposdir.
        """
        # Read .repo files from directories specified by the reposdir option
        # (typically /etc/yum/repos.d)
        repo_config_age = self.conf.config_file_age

        # Get the repos from the main yum.conf file
        self.getReposFromConfigFile(self.conf.config_file_path, repo_config_age)

        for reposdir in self.conf.reposdir:
            # this check makes sure that our dirs exist properly.
            # if they aren't in the installroot then don't prepend the installroot path
            # if we don't do this then anaconda likes to not  work.
            if os.path.exists(self.conf.installroot+'/'+reposdir):
                reposdir = self.conf.installroot + '/' + reposdir

            if os.path.isdir(reposdir):
                for repofn in sorted(glob.glob('%s/*.repo' % reposdir)):
                    thisrepo_age = os.stat(repofn)[8]
                    if thisrepo_age < repo_config_age:
                        thisrepo_age = repo_config_age
                    self.getReposFromConfigFile(repofn, repo_age=thisrepo_age)

    def readRepoConfig(self, parser, section):
        """Parse an INI file section for a repository.

        :param parser: :class:`ConfigParser` or similar object to read
           INI file values from
        :param section: INI file section to read
        :return: :class:`yumRepo.YumRepository` instance
        """
        repo = yumRepo.YumRepository(section)
        try:
            repo.populate(parser, section, self.conf)
        except ValueError, e:
            msg = _('Repository %r: Error parsing config: %s' % (section,e))
            raise Errors.ConfigError, msg

        # Ensure that the repo name is set
        if not repo.name:
            repo.name = section
            self.logger.error(_('Repository %r is missing name in configuration, '
                    'using id') % section)
        repo.name = to_unicode(repo.name)

        repo.basecachedir = self.cache_c.cachedir
        repo.fallback_basecachedir = self.cache_c.fallback_cachedir

        repo.yumvar.update(self.conf.yumvar)
        repo.cfg = parser

        return repo

    def disablePlugins(self):
        """Disable yum plugins."""

        self.plugins = plugins.DummyYumPlugins()

    def doPluginSetup(self, optparser=None, plugin_types=None, searchpath=None,
            confpath=None,disabled_plugins=None,enabled_plugins=None):
        """Initialise and enable yum plugins.
        Note: _getConfig() will also initialise plugins if instructed
        to. Only call this method directly if not calling _getConfig()
        or calling doConfigSetup(init_plugins=False).

        :param optparser: the :class:`OptionParser` instance to use
           for this run
        :param plugin_types: a sequence specifying the types of plugins to load.
           This should be a sequence containing one or more of the
           plugins.TYPE_*  constants. If None (the default), all plugins
           will be loaded
        :param searchpath: a list of directories to look in for plugins. A
           default will be used if no value is specified
        :param confpath: a list of directories to look in for plugin
           configuration files. A default will be used if no value is
           specified
        :param disabled_plugins: a list of plugins to be disabled
        :param enabled_plugins: a list plugins to be enabled
        """
        if isinstance(self.plugins, plugins.YumPlugins):
            raise RuntimeError(_("plugins already initialised"))

        self.plugins = plugins.YumPlugins(self, searchpath, optparser,
                plugin_types, confpath, disabled_plugins, enabled_plugins)

    def closeRpmDB(self):
        """Closes down the instances of rpmdb that could be open."""
        self._ts = None
        self._tsInfo = None
        self.comps = None

    def _getTsInfo(self, remove_only=False):
        """ remove_only param. says if we are going to do _only_ remove(s) in
            the transaction. If so we don't need to setup the remote repos. """
        if self._tsInfo is None:
            self._tsInfo = transactioninfo.TransactionData()
            self._tsInfo.installonlypkgs = self.conf.installonlypkgs
        return self._tsInfo

    def _setTsInfo(self, value):
        self._tsInfo = value

    def _delTsInfo(self):
        self._tsInfo = None

    def _getActionTs(self):
        if not self._ts:
            self.initActionTs()
        return self._ts

    def initActionTs(self):
        """Set up the transaction set that will be used for all the work."""
        self._ts = dnf.rpmUtils.transaction.TransactionWrapper(self.conf.installroot)
        ts_flags_to_rpm = { 'noscripts': rpm.RPMTRANS_FLAG_NOSCRIPTS,
                            'notriggers': rpm.RPMTRANS_FLAG_NOTRIGGERS,
                            'nodocs': rpm.RPMTRANS_FLAG_NODOCS,
                            'test': rpm.RPMTRANS_FLAG_TEST,
                            'justdb': rpm.RPMTRANS_FLAG_JUSTDB,
                            'repackage': rpm.RPMTRANS_FLAG_REPACKAGE}
        # This is only in newer rpm.org releases
        if hasattr(rpm, 'RPMTRANS_FLAG_NOCONTEXTS'):
            ts_flags_to_rpm['nocontexts'] = rpm.RPMTRANS_FLAG_NOCONTEXTS

        self._ts.setFlags(0) # reset everything.

        for flag in self.conf.tsflags:
            if flag in ts_flags_to_rpm:
                self._ts.addTsFlag(ts_flags_to_rpm[flag])
            else:
                self.logger.critical(_('Invalid tsflag in config file: %s'), flag)

        probfilter = 0
        for flag in self.tsInfo.probFilterFlags:
            probfilter |= flag
        self._ts.setProbFilter(probfilter)

    def _deleteTs(self):
        del self._ts
        self._ts = None

    def _getRepos(self, thisrepo=None, doSetup = False):
        """ For each enabled repository set up the basics of the repository. """
        if hasattr(self, 'prerepoconf'):
            self.conf # touch the config class first

            self.getReposFromConfig()

        #  For rhnplugin, and in theory other stuff, calling
        # .getReposFromConfig() recurses back into this function but only once.
        # This means that we have two points on the stack leaving the above call
        # but only one of them can do the repos setup. BZ 678043.
        if hasattr(self, 'prerepoconf'):
            # Recursion
            prerepoconf = self.prerepoconf
            del self.prerepoconf

            self.repos.setProgressBar(prerepoconf.progressbar)
            self.repos.callback = prerepoconf.callback
            self.repos.setFailureCallback(prerepoconf.failure_callback)
            self.repos.setInterruptCallback(prerepoconf.interrupt_callback)
            self.repos.confirm_func = prerepoconf.confirm_func
            self.repos.gpg_import_func = prerepoconf.gpg_import_func
            self.repos.gpgca_import_func = prerepoconf.gpgca_import_func
            if prerepoconf.cache is not None:
                self.repos.setCache(prerepoconf.cache)


        if doSetup:
            if (hasattr(urlgrabber, 'grabber') and
                hasattr(urlgrabber.grabber, 'pycurl')):
                # Must do basename checking, on cert. files...
                cert_basenames = {}
                for repo in self._repos.listEnabled():
                    if not repo.sslclientcert:
                        continue
                    bn = os.path.basename(repo.sslclientcert)
                    if bn not in cert_basenames:
                        cert_basenames[bn] = repo
                        continue
                    if repo.sslclientcert == cert_basenames[bn].sslclientcert:
                        # Exactly the same path is fine too
                        continue

                    msg = 'sslclientcert basename shared between %s and %s'
                    raise Errors.ConfigError, msg % (repo, cert_basenames[bn])

            repo_st = time.time()
            self._repos.doSetup(thisrepo)
            self.verbose_logger.debug('repo time: %0.3f' % (time.time() - repo_st))
        return self._repos

    def _delRepos(self):
        del self._repos
        self._repos = RepoStorage(self)

    def _setGroups(self, val):
        if val is None:
            # if we unset the comps object, we need to undo which repos have
            # been added to the group file as well
            if self._repos:
                for repo in self._repos.listGroupsEnabled():
                    repo.groups_added = False
        self._comps = val

    def _getGroups(self):
        """create the groups object that will store the comps metadata
           finds the repos with groups, gets their comps data and merge it
           into the group object"""

        if self._comps:
            return self._comps

        group_st = time.time()
        self.verbose_logger.log(logginglevels.DEBUG_4,
                                _('Getting group metadata'))
        reposWithGroups = []
        #  Need to make sure the groups data is ready to read. Really we'd want
        # to add groups to the mdpolicy list of the repo. but we don't atm.
        self.pkgSack
        for repo in self.repos.listGroupsEnabled():
            if repo.groups_added: # already added the groups from this repo
                reposWithGroups.append(repo)
                continue

            if not repo.ready():
                raise Errors.RepoError, "Repository '%s' not yet setup" % repo
            try:
                groupremote = repo.getGroupLocation()
            except Errors.RepoMDError, e:
                pass
            else:
                reposWithGroups.append(repo)

        # now we know which repos actually have groups files.
        overwrite = self.conf.overwrite_groups
        self._comps = comps.Comps(overwrite_groups = overwrite)

        for repo in reposWithGroups:
            if repo.groups_added: # already added the groups from this repo
                continue

            self.verbose_logger.log(logginglevels.DEBUG_4,
                _('Adding group file from repository: %s'), repo)
            groupfile = repo.getGroups()
            # open it up as a file object so iterparse can cope with our compressed file
            if groupfile:
                groupfile = misc.repo_gen_decompress(groupfile, 'groups.xml',
                                                     cached=repo.cache)
                # Do we want a RepoError here?

            try:
                self._comps.add(groupfile)
            except (Errors.GroupsError,Errors.CompsException), e:
                msg = _('Failed to add groups file for repository: %s - %s') % (repo, str(e))
                self.logger.critical(msg)
            else:
                repo.groups_added = True

        if self._comps.compscount == 0:
            raise Errors.GroupsError, _('No Groups Available in any repository')

        self._comps.compile(self.rpmdb.simplePkgList())
        self.verbose_logger.debug('group time: %0.3f' % (time.time() - group_st))
        return self._comps

    def _getHistory(self):
        """auto create the history object that to access/append the transaction
           history information. """
        if self._history is None:
            db_path = self.conf.persistdir + "/history"
            releasever = self.conf.yumvar['releasever']
            self._history = history.YumHistory(db_path, self.yumdb,
                                               root=self.conf.installroot,
                                               releasever=releasever)
        return self._history

    # properties so they auto-create themselves with defaults
    repos = property(fget=lambda self: self._getRepos(),
                     fset=lambda self, value: setattr(self, "_repos", value),
                     fdel=lambda self: self._delRepos(),
                     doc="Repo Storage object - object of yum repositories")
    conf = property(fget=lambda self: self._getConfig(),
                    fset=lambda self, value: setattr(self, "_conf", value),
                    fdel=lambda self: setattr(self, "_conf", None),
                    doc="Yum Config Object")
    tsInfo = property(fget=lambda self: self._getTsInfo(),
                      fset=lambda self,value: self._setTsInfo(value),
                      fdel=lambda self: self._delTsInfo(),
                      doc="Transaction Set information object")
    ts = property(fget=lambda self: self._getActionTs(),
                  fdel=lambda self: self._deleteTs(),
                  doc="TransactionSet object")
    comps = property(fget=lambda self: self._getGroups(),
                     fset=lambda self, value: self._setGroups(value),
                     fdel=lambda self: setattr(self, "_comps", None),
                     doc="Yum Component/groups object")
    history = property(fget=lambda self: self._getHistory(),
                       fset=lambda self, value: setattr(self, "_history",value),
                       fdel=lambda self: setattr(self, "_history", None),
                       doc="Yum History Object")

    def yumUtilsMsg(self, func, prog):
        """Output a message that the given tool requires the yum-utils
        package, if it not installed.

        :param func: the function to output the message
        :param prog: the name of the tool that requires yum-utils
        """
        if self.rpmdb.contains(name="yum-utils"):
            return

        hibeg, hiend = "", ""
        if hasattr(self, 'term'):
            hibeg, hiend = self.term.MODE['bold'], self.term.MODE['normal']

        func(_("The program %s%s%s is found in the yum-utils package.") %
             (hibeg, prog, hiend))

    def _push_userinstalled(self, goal):
        msg =  _('--> Finding unneeded leftover dependencies')
        self.verbose_logger.log(logginglevels.INFO_2, msg)
        for pkg in queries.installed(self.sack):
            yumdb_info = self.yumdb.get_package(pkg)
            reason = 'user'
            try:
                reason = yumdb_info.reason
            except AttributeError:
                pass
            if reason == 'user':
                goal.userinstalled(pkg)

    def build_hawkey_goal(self, tsInfo):
        goal = hawkey.Goal(self.sack)
        push_userinstalled = False
        for txmbr in tsInfo:
            pkg = txmbr.po
            if txmbr.ts_state == 'i':
                goal.install(pkg)
            elif txmbr.ts_state == 'u':
                goal.upgrade_to(pkg, check_installed=False)
            elif txmbr.ts_state == 'e':
                push_userinstalled = self.conf.clean_requirements_on_remove
                goal.erase(pkg, clean_deps=self.conf.clean_requirements_on_remove)
            else:
                raise NotImplementedError("hawkey can't handle ts_state '%s'."
                                          % txmbr.ts_state)
        for sltr in tsInfo.selector_installs:
            goal.install(select=sltr)
        if tsInfo.upgrade_all:
            goal.upgrade_all()
        if push_userinstalled:
            self._push_userinstalled(goal)
        return goal

    def buildTransaction(self, unfinished_transactions_check=True):
        """Go through the packages in the transaction set, find them
        in the packageSack or rpmdb, and pack up the transaction set
        accordingly.

        :param unfinished_transactions_check: whether to check for
           unfinished transactions before building the new transaction
        """
        # FIXME: This is horrible, see below and yummain. Maybe create a real
        #        rescode object? :(
        self._depsolving_failed = False

        if (unfinished_transactions_check and
            misc.find_unfinished_transactions(yumlibpath=self.conf.persistdir)):
            msg = _('There are unfinished transactions remaining. You might ' \
                    'consider running yum-complete-transaction first to finish them.' )
            self.logger.critical(msg)
            self.yumUtilsMsg(self.logger.critical, "yum-complete-transaction")
            time.sleep(3)

        # XXX - we could add a conditional here to avoid running the plugins and
        # limit_installonly_pkgs, etc - if we're being run from yum-complete-transaction
        # and don't want it to happen. - skv

        self.plugins.run('preresolve')
        ds_st = time.time()
        self.dsCallback.start()
        goal = self.build_hawkey_goal(self.tsInfo)
        if not goal.run(allow_uninstall=True):
            if self.conf.debuglevel >= 6:
                goal.log_decisions()
            (rescode, restring) =  (1, goal.problems)
        else:
            cnt = 0
            # reset tsInfo, some packages might have gone during resolving
            self.tsInfo = transactioninfo.TransactionData(
                prob_filter_flags=self.tsInfo.probFilterFlags)
            for pkg in goal.list_downgrades():
                cnt += 1
                downgraded = goal.package_obsoletes(pkg)
                self.dsCallback.pkgAdded(downgraded, 'dd')
                self.dsCallback.pkgAdded(pkg, 'd')
                self.tsInfo.addDowngrade(pkg, downgraded)
            for pkg in goal.list_reinstalls():
                cnt += 1
                self.dsCallback.pkgAdded(pkg, 'r')
                txmbr = self.tsInfo.addInstall(pkg)
                reinstalled = goal.package_obsoletes(pkg)
                txmbr = self.tsInfo.addErase(reinstalled)
            for pkg in goal.list_installs():
                cnt += 1
                self.dsCallback.pkgAdded(pkg, 'i')
                txmbr = self.tsInfo.addInstall(pkg)
                txmbr.reason = dnf.util.reason_name(goal.get_reason(pkg))
            for pkg in goal.list_upgrades():
                cnt += 1
                updated = goal.package_obsoletes(pkg)
                self.dsCallback.pkgAdded(updated, 'ud')
                self.dsCallback.pkgAdded(pkg, 'u')
                self.tsInfo.addUpdate(pkg, updated)
            for pkg in goal.list_erasures():
                cnt += 1
                self.dsCallback.pkgAdded(pkg, 'e')
                self.tsInfo.addErase(pkg)
            if cnt > 0:
                (rescode, restring) = (2, [_('Success - deps resolved')])
            else:
                (rescode, restring) = (0, [_('Nothing to do')])
        self.dsCallback.end()
        self.plugins.run('postresolve', rescode=rescode, restring=restring)
        self.verbose_logger.debug('Depsolve time: %0.3f' % (time.time() - ds_st))
        return (rescode, restring)

    def _add_not_found(self, pkgs, nevra_dict):
        if pkgs:
            return None

        pkgtup = (nevra_dict['name'], nevra_dict['arch'],
                  nevra_dict['epoch'], nevra_dict['version'],
                  nevra_dict['release'])
        if None in pkgtup:
            return None
        return pkgtup
    def _add_not_found_a(self, pkgs, nevra_dict={}, pkgtup=None):
        if pkgtup is None and nevra_dict:
            pkgtup = self._add_not_found(pkgs, nevra_dict)
        if pkgtup is None:
            return
        self._not_found_a[pkgtup] = YumNotFoundPackage(pkgtup)
    def _add_not_found_i(self, pkgs, nevra_dict={}, pkgtup=None):
        if pkgtup is None and nevra_dict:
            pkgtup = self._add_not_found(pkgs, nevra_dict)
        if pkgtup is None:
            return
        self._not_found_i[pkgtup] = YumNotFoundPackage(pkgtup)

    def _rpmdb_warn_checks(self, out=None, warn=True, chkcmd=None, header=None,
                           ignore_pkgs=[]):
        if out is None:
            out = self.logger.warning
        if chkcmd is None:
            chkcmd = ['dependencies', 'duplicates']
        if header is None:
            # FIXME: _N()
            msg = _("** Found %d pre-existing rpmdb problem(s),"
                    " 'yum check' output follows:")
            header = lambda problems: not problems or out(msg % problems)
        if warn:
            out(_('Warning: RPMDB altered outside of yum.'))

        if type(chkcmd) in (type([]), type(set())):
            chkcmd = set(chkcmd)
        else:
            chkcmd = set([chkcmd])

        ignore_pkgtups = set((pkg.pkgtup for pkg in ignore_pkgs))

        rc = 0
        probs = []
        if chkcmd.intersection(set(('all', 'dependencies'))):
            prob2ui = {'requires' : _('missing requires'),
                       'conflicts' : _('installed conflict')}
            for prob in self.rpmdb.check_dependencies():
                if prob.pkg.pkgtup in ignore_pkgtups:
                    continue
                if prob.problem == 'conflicts':
                    found = True # all the conflicting pkgs have to be ignored
                    for res in prob.conflicts:
                        if res.pkgtup not in ignore_pkgtups:
                            found = False
                            break
                    if found:
                        continue
                probs.append(prob)

        if chkcmd.intersection(set(('all', 'duplicates'))):
            iopkgs = set(self.conf.installonlypkgs)
            for prob in self.rpmdb.check_duplicates(iopkgs):
                if prob.pkg.pkgtup in ignore_pkgtups:
                    continue
                if prob.duplicate.pkgtup in ignore_pkgtups:
                    continue
                probs.append(prob)

        if chkcmd.intersection(set(('all', 'obsoleted'))):
            for prob in self.rpmdb.check_obsoleted():
                if prob.pkg.pkgtup in ignore_pkgtups:
                    continue
                if prob.obsoleter.pkgtup in ignore_pkgtups:
                    continue
                probs.append(prob)

        if chkcmd.intersection(set(('all', 'provides'))):
            for prob in self.rpmdb.check_provides():
                if prob.pkg.pkgtup in ignore_pkgtups:
                    continue
                probs.append(prob)

        header(len(probs))
        for prob in sorted(probs):
            out(prob)

        return probs

    def _record_history(self):
        return self.conf.history_record and \
            not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)

    def runTransaction(self, cb):
        """Perform the transaction.

        :param cb: an rpm callback object to use in the transaction
        :return: a :class:`misc.GenericHolder` containing
           information about the results of the transaction
        :raises: :class:`Errors.YumRPMTransError` if there is a
           transaction cannot be completed
        """
        self.plugins.run('pretrans')

        #  We may want to put this other places, eventually, but for now it's
        # good as long as we get it right for history.
        for repo in self.repos.listEnabled():
            if repo._xml2sqlite_local:
                self.run_with_package_names.add('yum-metadata-parser')
                break

        if self._record_history():
            using_pkgs_pats = list(self.run_with_package_names)
            using_pkgs = queries.installed_by_name(self.sack, using_pkgs_pats)
            rpmdbv  = self.sack.rpmdb_version(self.yumdb)
            lastdbv = self.history.last()
            if lastdbv is not None:
                lastdbv = lastdbv.end_rpmdbversion

            if lastdbv is None or rpmdbv != lastdbv:
                self.verbose_logger.info("RPMDB altered outside of DNF.")

            cmdline = None
            if hasattr(self, 'args') and self.args:
                cmdline = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                cmdline = ' '.join(self.cmds)

            self.history.beg(rpmdbv, using_pkgs, list(self.tsInfo),
                             [], [], cmdline)
            # write out our config and repo data to additional history info
            self._store_config_in_history()

            self.plugins.run('historybegin')

        # transaction has started - all bets are off on our saved ts file
        if self._ts_save_file is not None:
            # write the saved transaction data to the addon location in history
            # so we can pull it back later if we need to
            savetx_msg = open(self._ts_save_file, 'r').read()
            self.history.write_addon_data('saved_tx', savetx_msg)

            try:
                os.unlink(self._ts_save_file)
            except (IOError, OSError), e:
                pass
        self._ts_save_file = None

        if self.conf.reset_nice:
            onice = os.nice(0)
            if onice:
                try:
                    os.nice(-onice)
                except:
                    onice = 0

        errors = self.ts.run(cb.callback, '')
        # ts.run() exit codes are, hmm, "creative": None means all ok, empty
        # list means some errors happened in the transaction and non-empty
        # list that there were errors preventing the ts from starting...
        if self.conf.reset_nice:
            try:
                os.nice(onice)
            except:
                pass

        # make resultobject - just a plain yumgenericholder object
        resultobject = misc.GenericHolder()
        resultobject.return_code = 0
        if errors is None:
            pass
        elif len(errors) == 0:
            # this is a particularly tricky case happening also when rpm failed
            # to obtain the transaction lock. We can only try to see if a
            # particular element failed and if not, decide that is the
            # case.
            if len(filter(lambda el: el.Failed(), self.ts)) > 0:
                errstring = _('Warning: scriptlet or other non-fatal errors occurred during transaction.')
                self.verbose_logger.debug(errstring)
                resultobject.return_code = 1
            else:
                self.logger.critical(_("Transaction couldn't start (no root?)"))
                raise Errors.YumRPMTransError(msg=_("Could not run transaction."),
                                              errors=[])
        else:
            if self._record_history():
                herrors = [to_unicode(to_str(x)) for x in errors]
                self.plugins.run('historyend')
                self.history.end(rpmdbv, 2, errors=herrors)


            self.logger.critical(_("Transaction couldn't start:"))
            for e in errors:
                self.logger.critical(e[0]) # should this be 'to_unicoded'?
            raise Errors.YumRPMTransError(msg=_("Could not run transaction."),
                                          errors=errors)


        if (not self.conf.keepcache and
            not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)):
            self.cleanUsedHeadersPackages()

        for i in ('ts_all_fn', 'ts_done_fn'):
            if hasattr(cb, i):
                fn = getattr(cb, i)
                try:
                    misc.unlink_f(fn)
                except (IOError, OSError), e:
                    self.logger.critical(_('Failed to remove transaction file %s') % fn)


        self.plugins.run('posttrans')
        # sync up what just happened versus what is in the rpmdb
        if not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST):
            vTcb = None
            if hasattr(cb, 'verify_txmbr'):
                vTcb = cb.verify_txmbr
            self.verifyTransaction(resultobject, vTcb)
        return resultobject

    def verifyTransaction(self, resultobject=None, txmbr_cb=None):
        """Check that the transaction did what was expected, and
        propagate external yumdb information.  Output error messages
        if the transaction did not do what was expected.

        :param resultobject: the :class:`misc.GenericHolder`
           object returned from the :func:`runTransaction` call that
           ran the transaction
        :param txmbr_cb: the callback for the rpm transaction members
        """
        # check to see that the rpmdb and the tsInfo roughly matches
        # push package object metadata outside of rpmdb into yumdb
        # delete old yumdb metadata entries

        # for each pkg in the tsInfo
        # if it is an install - see that the pkg is installed
        # if it is a remove - see that the pkg is no longer installed, provided
        #    that there is not also an install of this pkg in the tsInfo (reinstall)
        # for any kind of install add from_repo to the yumdb, and the cmdline
        # and the install reason

        def _call_txmbr_cb(txmbr, count):
            if txmbr_cb is not None:
                count += 1
                txmbr_cb(txmbr, count)
            return count

        vt_st = time.time()
        self.plugins.run('preverifytrans')
        count = 0
        # the rpmdb has changed by now. hawkey doesn't support dropping a repo
        # yet we have to check what packages are in now: build a transient sack
        # with only rpmdb in it. In the future when RPM Python bindings can tell
        # us if a particular transaction element failed or not we can skip this
        # completely.
        rpmdb_sack = sack.build_sack(self)
        rpmdb_sack.load_system_repo()

        # Process new packages before the old ones so we can copy values.
        for txmbr in self.tsInfo:
            if txmbr.output_state not in TS_INSTALL_STATES:
                continue

            rpo = txmbr.po
            installed = queries.installed_exact(rpmdb_sack, rpo.name,
                                                rpo.evr, rpo.arch)
            if len(installed) < 1:
                self.logger.critical(_('%s was supposed to be installed' \
                                           ' but is not!' % txmbr.po))
                txmbr.output_state = TS_FAILED
                count = _call_txmbr_cb(txmbr, count)
                continue
            po = installed[0]
            count = _call_txmbr_cb(txmbr, count)
            yumdb_info = self.yumdb.get_package(po)
            yumdb_info.from_repo = rpo.repoid
            yumdb_info.reason = txmbr.propagated_reason(self.yumdb)
            yumdb_info.releasever = self.conf.yumvar['releasever']
            if hasattr(self, 'args') and self.args:
                yumdb_info.command_line = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                yumdb_info.command_line = ' '.join(self.cmds)
            csum = rpo.returnIdSum()
            if csum is not None:
                yumdb_info.checksum_type = str(csum[0])
                yumdb_info.checksum_data = str(csum[1])

            if rpo.from_cmdline:
                try:
                    st = os.stat(rpo.localPkg())
                    lp_ctime = str(int(st.st_ctime))
                    lp_mtime = str(int(st.st_mtime))
                    yumdb_info.from_repo_revision  = lp_ctime
                    yumdb_info.from_repo_timestamp = lp_mtime
                except Exception:
                    pass
            elif hasattr(rpo.repo, 'repoXML'):
                md = rpo.repo.repoXML
                if md and md.revision is not None:
                    yumdb_info.from_repo_revision  = str(md.revision)
                if md:
                    yumdb_info.from_repo_timestamp = str(md.timestamp)

            loginuid = misc.getloginuid()
            if txmbr.updates or txmbr.downgrades or txmbr.reinstall:
                if txmbr.updates:
                    opo = txmbr.updates[0]
                elif txmbr.downgrades:
                    opo = txmbr.downgrades[0]
                else:
                    opo = po
                opo_yumdb_info = self.yumdb.get_package(opo)
                if 'installed_by' in opo_yumdb_info:
                    yumdb_info.installed_by = opo_yumdb_info.installed_by
                if loginuid is not None:
                    yumdb_info.changed_by = str(loginuid)
            elif loginuid is not None:
                yumdb_info.installed_by = str(loginuid)

            if self.conf.history_record:
                self.history.sync_alldb(po)

        for txmbr in self.tsInfo:
            if txmbr.output_state not in TS_REMOVE_STATES:
                continue
            rpo = txmbr.po
            installed = queries.installed_exact(rpmdb_sack, rpo.name,
                                                rpo.evr, rpo.arch)
            if len(installed) > 0:
                if not self.tsInfo.getMembersWithState(pkgtup=txmbr.pkgtup,
                            output_states=TS_INSTALL_STATES):
                    # maybe a file log here, too
                    # but raising an exception is not going to do any good
                    # Note: This actually triggers atm. because we can't
                    #       always find the erased txmbr to set it when
                    #       we should.
                    self.logger.critical(_('%s was supposed to be removed' \
                                           ' but is not!' % txmbr.po))
                    # Note: Get Panu to do te.Failed() so we don't have to
                    txmbr.output_state = TS_FAILED
                    count = _call_txmbr_cb(txmbr, count)
                    continue
            count = _call_txmbr_cb(txmbr, count)
            yumdb_item = self.yumdb.get_package(po=txmbr.po)
            yumdb_item.clean()

        for txmbr in self.tsInfo:
            if txmbr.output_state not in TS_INSTALL_STATES + TS_REMOVE_STATES:
                count = _call_txmbr_cb(txmbr, count)
                self.verbose_logger.log(logginglevels.DEBUG_2, 'What is this? %s' % txmbr.po)

        self.plugins.run('postverifytrans')
        if self._record_history():
            ret = -1
            if resultobject is not None:
                ret = resultobject.return_code
            rpmdbv = rpmdb_sack.rpmdb_version(self.yumdb)
            self.plugins.run('historyend')
            self.history.end(rpmdbv, ret)
        self.verbose_logger.debug('VerifyTransaction time: %0.3f' % (time.time() - vt_st))

    def costExcludePackages(self):
        """Create an excluder for repositories with higher costs. For
        example, if repo-A:cost=1 and repo-B:cost=2, this function
        will set up an excluder on repo-B that looks for packages in
        repo-B.
        """
        # if all the repo.costs are equal then don't bother running things
        costs = {}
        for r in self.repos.listEnabled():
            costs.setdefault(r.cost, []).append(r)

        if len(costs) <= 1:
            return

        done = False
        exid = "yum.costexcludes"
        orepos = []
        for cost in sorted(costs):
            if done: # Skip the first one, as they have lowest cost so are good.
                for repo in costs[cost]:
                    yce = _YumCostExclude(repo, self.repos)
                    repo.sack.addPackageExcluder(repo.id, exid,
                                                 'exclude.pkgtup.in', yce)
            orepos.extend(costs[cost])
            done = True

    def excludePackages(self, repo=None):
        """Remove packages from packageSacks based on global exclude
        lists, command line excludes and per-repository excludes.

        :param repo: a repo object to use.  If not given, all
           repositories are used
        """
        if "all" in self.conf.disable_excludes:
            return

        # if not repo: then assume global excludes, only
        # if repo: then do only that repos' packages and excludes

        if not repo: # global only
            if "main" in self.conf.disable_excludes:
                return
            excludelist = self.conf.exclude
            repoid = None
            exid_beg = 'yum.excludepkgs'
        else:
            if repo.id in self.conf.disable_excludes:
                return
            excludelist = repo.getExcludePkgList()
            repoid = repo.id
            exid_beg = 'yum.excludepkgs.' + repoid

        count = 0
        for match in excludelist:
            count += 1
            exid = "%s.%u" % (exid_beg, count)
            self.pkgSack.addPackageExcluder(repoid, exid,'exclude.match', match)

    def includePackages(self, repo):
        """Remove packages from packageSacks based on list of
        packages to include.

        :param repo: the repository to use
        """
        includelist = repo.getIncludePkgList()

        if len(includelist) == 0:
            return

        # includepkgs actually means "exclude everything that doesn't match".
        #  So we mark everything, then wash those we want to keep and then
        # exclude everything that is marked.
        exid = "yum.includepkgs.1"
        self.pkgSack.addPackageExcluder(repo.id, exid, 'mark.washed')
        count = 0
        for match in includelist:
            count += 1
            exid = "%s.%u" % ("yum.includepkgs.2", count)
            self.pkgSack.addPackageExcluder(repo.id, exid, 'wash.match', match)
        exid = "yum.includepkgs.3"
        self.pkgSack.addPackageExcluder(repo.id, exid, 'exclude.marked')

    def doLock(self):
        """Acquire the yum lock.

        :param lockfile: the file to use for the lock
        :raises: :class:`Errors.LockError`
        """
        lockfile = const.PID_FILENAME

        if self.conf.uid != 0:
            #  If we are a user, assume we are using the root cache ... so don't
            # bother locking.
            if self.conf.cache:
                return
            root = self.cache_c.cachedir
            # Don't want <cachedir>/var/run/yum.pid ... just: <cachedir>/yum.pid
            lockfile = os.path.basename(lockfile)
        else:
            root = self.conf.installroot
        lockfile = root + '/' + lockfile # lock in the chroot
        lockfile = os.path.normpath(lockfile) # get rid of silly preceding extra /

        mypid=str(os.getpid())
        while not self._lock(lockfile, mypid, 0644):
            oldpid = self._get_locker(lockfile)
            if not oldpid:
                # Invalid locker: unlink lockfile and retry
                self._unlock(lockfile)
                continue
            if oldpid == os.getpid(): # if we own the lock, we're fine
                break
            # Another copy seems to be running.
            msg = _('Existing lock %s: another copy is running as pid %s.') % (lockfile, oldpid)
            raise Errors.LockError(0, msg, oldpid)
        # We've got the lock, store it so we can auto-unlock on __del__...
        self._lockfile = lockfile

    def doUnlock(self, lockfile=None):
        """Release the yum lock.

        :param lockfile: the lock file to use.  If not given, the file
           that was given as a parameter to the :func:`doLock` call
           that closed the lock is used
        """
        # if we're not root then we don't lock - just return nicely
        #  Note that we can get here from __del__, so if we haven't created
        # YumBase.conf we don't want to do so here as creating stuff inside
        # __del__ is bad.
        if hasattr(self, 'preconf'):
            return

        #  Obviously, we can't lock random places as non-root, but we still want
        # to get rid of our lock file. Given we now have _lockfile I'm pretty
        # sure nothing should ever pass lockfile in here anyway.
        if self.conf.uid != 0:
            lockfile = None

        if lockfile is not None:
            root = self.conf.installroot
            lockfile = root + '/' + lockfile # lock in the chroot
        elif self._lockfile is None:
            return # Don't delete other people's lock files on __del__
        else:
            lockfile = self._lockfile # Get the value we locked with

        self._unlock(lockfile)
        self._lockfile = None

    @staticmethod
    def _lock(filename, contents='', mode=0777):
        lockdir = os.path.dirname(filename)
        try:
            if not os.path.exists(lockdir):
                os.makedirs(lockdir, mode=0755)
            fd = os.open(filename, os.O_EXCL|os.O_CREAT|os.O_WRONLY, mode)
            os.write(fd, contents)
            os.close(fd)
            return 1
        except OSError, msg:
            if not msg.errno == errno.EEXIST:
                # Whoa. What the heck happened?
                errmsg = _('Could not create lock at %s: %s ') % (filename, str(msg))
                raise Errors.LockError(msg.errno, errmsg, int(contents))
            return 0

    @staticmethod
    def _unlock(filename):
        misc.unlink_f(filename)

    @staticmethod
    def _get_locker(lockfile):
        try: fd = open(lockfile, 'r')
        except (IOError, OSError), e:
            msg = _("Could not open lock %s: %s") % (lockfile, e)
            raise Errors.LockError(errno.EPERM, msg)
        try: oldpid = int(fd.readline())
        except ValueError:
            return None # Bogus pid

        try:
            stat = open("/proc/%d/stat" % oldpid).readline()
            if stat.split()[2] == 'Z':
                return None # The pid is a zombie
        except IOError:
            # process dead or /proc not mounted
            try: os.kill(oldpid, 0)
            except OSError, e:
                if e[0] == errno.ESRCH:
                    return None # The pid doesn't exist
                # Whoa. What the heck happened?
                msg = _('Unable to check if PID %s is active') % oldpid
                raise Errors.LockError(errno.EPERM, msg, oldpid)
        return oldpid

    def verifyPkg(self, fo, po, raiseError):
        """Check that the checksum of a remote package matches what we
        expect it to be.  If the checksum of the package file is
        wrong, and the file is also larger than expected, it cannot be
        redeemed, so delete it.

        :param fo: the file object of the package
        :param po: the package object to verify
        :param raiseError: if *raiseError* is 1, and the package
           does not check out, a :class:`URLGrabError` will be raised.
           Defaults to 0
        :return: True if the package is verified successfully.
           Otherwise, False will be returned, unless *raiseError* is
           1, in which case a :class:`URLGrabError` will be raised
        :raises: :class:`URLGrabError` if verification fails, and
           *raiseError* is 1
        """
        if type(fo) is types.InstanceType:
            fo = fo.filename

        if fo != po.localPkg():
            po.localpath = fo

        if not po.verifyLocalPkg():
            # if the file is wrong AND it is >= what we expected then it
            # can't be redeemed. If we can, kill it and start over fresh
            cursize = os.stat(fo)[6]
            totsize = long(po.size)
            if cursize >= totsize and not po.repo.cache:
                # if the path to the file is NOT inside the cachedir then don't
                # unlink it b/c it is probably a file:// url and possibly
                # unlinkable
                if fo.startswith(po.repo.cachedir):
                    os.unlink(fo)

            if raiseError:
                msg = _('Package does not match intended download. Suggestion: run yum --enablerepo=%s clean metadata') %  po.repo.id
                raise URLGrabError(-1, msg)
            else:
                return False


        return True


    def verifyChecksum(self, fo, checksumType, csum):
        """Verify that the checksum of the given file matches the
        given checksum.

        :param fo: the file object to verify the checksum of
        :param checksumType: the type of checksum to use
        :parm csum: the checksum to check against
        :return: 0 if the checksums match
        :raises: :class:`URLGrabError` if there is an error performing
           the checksums, or the checksums do not match
        """
        try:
            filesum = misc.checksum(checksumType, fo)
        except Errors.MiscError, e:
            raise URLGrabError(-3, _('Could not perform checksum'))

        if filesum != csum:
            raise URLGrabError(-1, _('Package does not match checksum'))

        return 0

    def downloadPkgs(self, pkglist, callback=None, callback_total=None):
        """Download the packages specified by the given list of
        package objects.

        :param pkglist: a list of package objects specifying the
           packages to download
        :param callback: unused
        :param callback_total: a callback to output messages about the
           download operation
        :return: a dictionary containing errors from the downloading process
        :raises: :class:`URLGrabError`
        """
        def mediasort(apo, bpo):
            # FIXME: we should probably also use the mediaid; else we
            # could conceivably ping-pong between different disc1's
            a = apo.getDiscNum()
            b = bpo.getDiscNum()
            if a is None and b is None:
                return cmp(apo, bpo)
            if a is None:
                return -1
            if b is None:
                return 1
            if a < b:
                return -1
            elif a > b:
                return 1
            return 0

        """download list of package objects handed to you, output based on
           callback, raise Errors.YumBaseError on problems"""

        errors = {}
        def adderror(po, msg):
            errors.setdefault(po, []).append(msg)

        #  We close the history DB here because some plugins (presto) use
        # threads. And sqlite really doesn't like threads. And while I don't
        # think it should matter, we've had some reports of history DB
        # corruption, and it was implied that it happened just after C-c
        # at download time and this is a safe thing to do.
        #  Note that manual testing shows that history is not connected by
        # this point, from the cli with no plugins. So this really does
        # nothing *sigh*.
        self.history.close()

        self.plugins.run('predownload', pkglist=pkglist)
        repo_cached = False
        remote_pkgs = []
        remote_size = 0
        for po in pkglist:
            if po.from_cmdline:
                continue
            local = po.localPkg()
            if os.path.exists(local):
                if not self.verifyPkg(local, po, False):
                    if po.repo.cache:
                        repo_cached = True
                        adderror(po, _('package fails checksum but caching is '
                            'enabled for %s') % po.repo.id)
                else:
                    self.verbose_logger.debug(_("using local copy of %s") %(po,))
                    continue

            remote_pkgs.append(po)
            remote_size += po.size

            # caching is enabled and the package
            # just failed to check out there's no
            # way to save this, report the error and return
            if (self.conf.cache or repo_cached) and errors:
                return errors


        remote_pkgs.sort(mediasort)
        #  This is kind of a hack and does nothing in non-Fedora versions,
        # we'll fix it one way or anther soon.
        if (hasattr(urlgrabber.progress, 'text_meter_total_size') and
            len(remote_pkgs) > 1):
            urlgrabber.progress.text_meter_total_size(remote_size)
        beg_download = time.time()
        i = 0
        local_size = 0
        done_repos = set()
        for po in remote_pkgs:
            #  Recheck if the file is there, works around a couple of weird
            # edge cases.
            local = po.localPkg()
            i += 1
            if os.path.exists(local):
                if self.verifyPkg(local, po, False):
                    self.verbose_logger.debug(_("using local copy of %s") %(po,))
                    remote_size -= po.size
                    if hasattr(urlgrabber.progress, 'text_meter_total_size'):
                        urlgrabber.progress.text_meter_total_size(remote_size,
                                                                  local_size)
                    continue
                if os.path.getsize(local) >= po.size:
                    os.unlink(local)

            checkfunc = (self.verifyPkg, (po, 1), {})
            try:
                if i == 1 and not local_size and remote_size == po.size:
                    text = os.path.basename(po.relativepath)
                else:
                    text = '(%s/%s): %s' % (i, len(remote_pkgs),
                                            os.path.basename(po.relativepath))
                mylocal = po.repo.getPackage(po,
                                   checkfunc=checkfunc,
                                   text=text,
                                   cache=po.repo.http_caching != 'none',
                                   )
                local_size += po.size
                if hasattr(urlgrabber.progress, 'text_meter_total_size'):
                    urlgrabber.progress.text_meter_total_size(remote_size,
                                                              local_size)
                if po.repoid not in done_repos:
                    #  Check a single package per. repo. ... to give a hint to
                    # the user on big downloads.
                    result, errmsg = self.sigCheckPkg(po)
                    if result != 0:
                        self.verbose_logger.warn("%s", errmsg)
                done_repos.add(po.repoid)

            except Errors.RepoError, e:
                adderror(po, exception2msg(e))
            else:
                po.localpath = mylocal
                if po in errors:
                    del errors[po]

        if hasattr(urlgrabber.progress, 'text_meter_total_size'):
            urlgrabber.progress.text_meter_total_size(0)
        if callback_total is not None and not errors:
            callback_total(remote_pkgs, remote_size, beg_download)

        self.plugins.run('postdownload', pkglist=pkglist, errors=errors)

        # Close curl object after we've downloaded everything.
        if hasattr(urlgrabber.grabber, 'reset_curl_obj'):
            urlgrabber.grabber.reset_curl_obj()

        return errors

    def sigCheckPkg(self, po):
        """Verify the GPG signature of the given package object.

        :param po: the package object to verify the signature of
        :return: (result, error_string)
           where result is::

              0 = GPG signature verifies ok or verification is not required.
              1 = GPG verification failed but installation of the right GPG key
                    might help.
              2 = Fatal GPG verification error, give up.
        """
        if self._override_sigchecks:
            check = False
            hasgpgkey = 0
        elif po.from_cmdline:
            check = self.conf.localpkg_gpgcheck
            hasgpgkey = 0
        else:
            repo = self.repos.getRepo(po.repoid)
            check = repo.gpgcheck
            hasgpgkey = not not repo.gpgkey

        if check:
            ts = self.rpm.readonly_ts
            sigresult = dnf.rpmUtils.miscutils.checkSig(ts, po.localPkg())
            localfn = os.path.basename(po.localPkg())

            if sigresult == 0:
                result = 0
                msg = ''

            elif sigresult == 1:
                if hasgpgkey:
                    result = 1
                else:
                    result = 2
                msg = _('Public key for %s is not installed') % localfn

            elif sigresult == 2:
                result = 2
                msg = _('Problem opening package %s') % localfn

            elif sigresult == 3:
                if hasgpgkey:
                    result = 1
                else:
                    result = 2
                result = 1
                msg = _('Public key for %s is not trusted') % localfn

            elif sigresult == 4:
                result = 2
                msg = _('Package %s is not signed') % localfn

        else:
            result =0
            msg = ''

        return result, msg

    def cleanUsedHeadersPackages(self):
        """Delete the header and package files used in the
        transaction from the yum cache.
        """
        filelist = []
        for txmbr in self.tsInfo:
            if txmbr.po.state not in TS_INSTALL_STATES:
                continue
            if txmbr.po.from_system:
                continue
            if txmbr.po.from_cmdline:
                continue

            # make sure it's not a local file
            repo = self.repos.repos[txmbr.po.repoid]
            local = False
            for u in repo.baseurl:
                if u.startswith("file:"):
                    local = True
                    break

            if local:
                filelist.extend([txmbr.po.localHdr()])
            else:
                filelist.append(txmbr.po.localPkg())

        # now remove them
        for fn in filelist:
            if not os.path.exists(fn):
                continue
            try:
                misc.unlink_f(fn)
            except OSError, e:
                self.logger.warning(_('Cannot remove %s'), fn)
                continue
            else:
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _('%s removed'), fn)

    def cleanPackages(self):
        """Delete the package files from the yum cache."""

        exts = ['rpm']
        return self._cleanFiles(exts, 'pkgdir', 'package')

    def clean_binary_cache(self):
        """ Delete the binary cache files from the DNF cache.

            IOW, clean up the .solv and .solvx hawkey cache files.
        """
        files = [os.path.join(self.cache_c.cachedir,
                              hawkey.SYSTEM_REPO_NAME + ".solv")]
        for repo in self.repos.listEnabled():
            basename = os.path.join(self.cache_c.cachedir, repo.id)
            files.append(basename + ".solv")
            files.append(basename + "-filenames.solvx")
        files = filter(lambda f: os.access(f, os.F_OK), files)

        return self._cleanFilelist('dbcache', files)

    def cleanMetadata(self):
        """Delete the metadata files from the yum cache."""

        exts = ['xml.gz', 'xml', 'cachecookie', 'mirrorlist.txt', 'asc',
                'xml.bz2', 'xml.xz']
        # Metalink is also here, but is a *.xml file
        return self._cleanFiles(exts, 'cachedir', 'metadata')

    def cleanExpireCache(self):
        """Delete the local data saying when the metadata and mirror
           lists were downloaded for each repository."""

        exts = ['cachecookie', 'mirrorlist.txt']
        return self._cleanFiles(exts, 'cachedir', 'metadata')

    def cleanRpmDB(self):
        """Delete any cached data from the local rpmdb."""

        cachedir = self.conf.persistdir + "/rpmdb-indexes/"
        if not os.path.exists(cachedir):
            filelist = []
        else:
            filelist = misc.getFileList(cachedir, '', [])
        return self._cleanFilelist('rpmdb', filelist)

    def _cleanFiles(self, exts, pathattr, filetype):
        filelist = []
        for ext in exts:
            for repo in self.repos.listEnabled():
                path = getattr(repo, pathattr)
                if os.path.exists(path) and os.path.isdir(path):
                    filelist = misc.getFileList(path, ext, filelist)
        return self._cleanFilelist(filetype, filelist)

    def _cleanFilelist(self, filetype, filelist):
        removed = 0
        for item in filelist:
            try:
                misc.unlink_f(item)
            except OSError, e:
                self.logger.critical(_('Cannot remove %s file %s'), filetype, item)
                continue
            else:
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _('%s file %s removed'), filetype, item)
                removed+=1
        msg = P_('%d %s file removed', '%d %s files removed', removed) % (removed, filetype)
        return 0, [msg]

    def doPackageLists(self, pkgnarrow='all', patterns=None, showdups=None,
                       ignore_case=False):
        """Return a :class:`misc.GenericHolder` containing
        lists of package objects.  The contents of the lists are
        specified in various ways by the arguments.

        :param pkgnarrow: a string specifying which types of packages
           lists to produces, such as updates, installed, available,
           etc.
        :param patterns: a list of names or wildcards specifying
           packages to list
        :param showdups: whether to include duplicate packages in the
           lists
        :param ignore_case: whether to ignore case when searching by
           package names
        :return: a :class:`misc.GenericHolder` instance with the
           following lists defined::

             available = list of packageObjects
             installed = list of packageObjects
             updates = tuples of packageObjects (updating, installed)
             extras = list of packageObjects
             obsoletes = tuples of packageObjects (obsoleting, installed)
             recent = list of packageObjects
        """
        if showdups is None:
            showdups = self.conf.showdupesfromrepos
        ygh = misc.GenericHolder(iter=pkgnarrow)

        installed = []
        available = []
        reinstall_available = []
        old_available = []
        updates = []
        obsoletes = []
        obsoletesTuples = []
        recent = []
        extras = []

        ic = ignore_case
        # list all packages - those installed and available, don't 'think about it'
        if pkgnarrow == 'all':
            dinst = {}
            ndinst = {} # Newest versions by name.arch
            for po in queries.installed_by_name(self.sack, patterns=patterns,
                                                       ignore_case=ic):
                dinst[po.pkgtup] = po
                if showdups:
                    continue
                key = (po.name, po.arch)
                if key not in ndinst or po > ndinst[key]:
                    ndinst[key] = po
            installed = dinst.values()

            if showdups:
                avail = queries.by_name(self.sack, patterns=patterns,
                                               ignore_case=ic)
            else:
                avail = queries.latest_per_arch(self.sack,
                                                       patterns=patterns,
                                                       ignore_case=ic).values()

            for pkg in avail:
                if showdups:
                    if pkg.pkgtup in dinst:
                        reinstall_available.append(pkg)
                    else:
                        available.append(pkg)
                else:
                    key = (pkg.name, pkg.arch)
                    if pkg.pkgtup in dinst:
                        reinstall_available.append(pkg)
                    elif key not in ndinst or pkg.evr_gt(ndinst[key]):
                        available.append(pkg)
                    else:
                        old_available.append(pkg)

        # produce the updates list of tuples
        elif pkgnarrow == 'updates':
            updates = queries.updates_by_name(self.sack,
                                                     patterns=patterns,
                                                     ignore_case=ic)

        # installed only
        elif pkgnarrow == 'installed':
            installed = queries.installed_by_name(self.sack,
                                                         patterns=patterns,
                                                         ignore_case=ic)

        # available in a repository
        elif pkgnarrow == 'available':
            if showdups:
                avail = queries.available_by_name(
                    self.sack, patterns=patterns, ignore_case=ic)
                inst_pkgs = queries.installed_by_name(
                    self.sack, patterns=patterns, ignore_case=ic)
                installed_dict = queries.per_arch_dict(inst_pkgs)
                for avail_pkg in avail:
                    key = (avail_pkg.name, avail_pkg.arch)
                    installed_pkgs = installed_dict.get(key, [])
                    same_ver = filter(lambda pkg: pkg.evr == avail_pkg.evr,
                                      installed_pkgs)
                    if len(same_ver) > 0:
                        reinstall_available.append(avail_pkg)
                    else:
                        available.append(avail_pkg)
            else:
                # we will only look at the latest versions of packages:
                available_dict = queries.latest_available_per_arch(
                    self.sack, patterns=patterns, ignore_case=ic)
                installed_dict = queries.latest_installed_per_arch(
                    self.sack, patterns=patterns, ignore_case=ic)
                for (name, arch) in available_dict:
                    avail_pkg = available_dict[(name, arch)]
                    inst_pkg = installed_dict.get((name, arch), None)
                    if not inst_pkg or avail_pkg.evr_gt(inst_pkg):
                        available.append(avail_pkg)
                    elif avail_pkg.evr_eq(inst_pkg):
                        reinstall_available.append(avail_pkg)
                    else:
                        old_available.append(avail_pkg)

        # not in a repo but installed
        elif pkgnarrow == 'extras':
            # anything installed but not in a repo is an extra
            avail = queries.available_by_name(
                self.sack, patterns=patterns, ignore_case=ic)
            avail_dict = queries.per_pkgtup_dict(avail)
            inst = queries.installed_by_name(
                self.sack, patterns=patterns, ignore_case=ic)
            inst_dict = queries.per_pkgtup_dict(inst)

            for pkgtup in inst_dict:
                if pkgtup not in avail_dict:
                    extras.extend(inst_dict[pkgtup])

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            self.conf.obsoletes = 1
            inst = queries.installed(self.sack, get_query=True)
            if patterns:
                inst = queries.installed_by_name(self.sack, patterns=patterns,
                                                 ignore_case=ic, get_query=True)
            obsoletes = hawkey.Query(self.sack).filter(obsoletes=inst)
            obsoletesTuples = []
            for new in obsoletes:
                obsoleted_reldeps = new.obsoletes
                obsoletesTuples.extend([(new, old) for old in
                                        inst.filter(provides=obsoleted_reldeps)])

        # packages recently added to the repositories
        elif pkgnarrow == 'recent':
            now = time.time()
            recentlimit = now-(self.conf.recent*86400)
            if showdups:
                avail = self.pkgSack.returnPackages(patterns=patterns,
                                                    ignore_case=ic)
            else:
                try:
                    avail = self.pkgSack.returnNewestByNameArch(patterns=patterns,
                                                              ignore_case=ic)
                except Errors.PackageSackError:
                    avail = []

            for po in avail:
                if int(po.filetime) > recentlimit:
                    recent.append(po)


        ygh.installed = installed
        ygh.available = available
        ygh.reinstall_available = reinstall_available
        ygh.old_available = old_available
        ygh.updates = updates
        ygh.obsoletes = obsoletes
        ygh.obsoletesTuples = obsoletesTuples
        ygh.recent = recent
        ygh.extras = extras

        return ygh

    def findDeps(self, pkgs):
        """Return the dependencies for a given package object list, as well
        as possible solutions for those dependencies.

        :param pkgs: a list of package objects
        :return: the dependencies as a dictionary of dictionaries:
           packageobject = [reqs] = [list of satisfying pkgs]
        """
        results = {}

        for pkg in pkgs:
            results[pkg] = {}
            reqs = pkg.requires
            reqs.sort()
            pkgresults = results[pkg] # shorthand so we don't have to do the
                                      # double bracket thing

            for req in reqs:
                (r,f,v) = req
                if r.startswith('rpmlib('):
                    continue

                satisfiers = []

                for po in self.whatProvides(r, f, v):
                    satisfiers.append(po)

                pkgresults[req] = satisfiers

        return results

    def search_counted(self, counter, attr, needle):
        fdict = {'%s__substr' % attr : needle}
        if queries.is_glob_pattern(needle):
            fdict = {'%s__glob' % attr : needle}
        q = hawkey.Query(self.sack).filter(**fdict)
        map(lambda pkg: counter.add(pkg, attr, needle), q.run())
        return counter

    def doGroupLists(self, uservisible=0, patterns=None, ignore_case=True):
        """Return two lists of groups: installed groups and available
        groups.

        :param uservisible: If True, only groups marked as uservisible
           will be returned. Otherwise, all groups will be returned
        :param patterns: a list of stings.  If given, only groups
           with names that match the patterns will be included in the
           lists.  If not given, all groups will be included
        :param ignore_case: whether to ignore case when determining
           whether group names match the strings in *patterns*
        """
        installed = []
        available = []

        if self.comps.compscount == 0:
            raise Errors.GroupsError, _('No group data available for configured repositories')

        if patterns is None:
            grps = self.comps.groups
        else:
            grps = self.comps.return_groups(",".join(patterns),
                                            case_sensitive=not ignore_case)
        for grp in grps:
            if grp.installed:
                if uservisible:
                    if grp.user_visible:
                        installed.append(grp)
                else:
                    installed.append(grp)
            else:
                if uservisible:
                    if grp.user_visible:
                        available.append(grp)
                else:
                    available.append(grp)

        return sorted(installed), sorted(available)


    def groupRemove(self, grpid):
        """Mark all the packages in the given group to be removed.

        :param grpid: the name of the group containing the packages to
           mark for removal
        :return: a list of transaction members added to the
           transaction set by this function
        """
        txmbrs_used = []

        thesegroups = self.comps.return_groups(grpid)
        if not thesegroups:
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        for thisgroup in thesegroups:
            thisgroup.toremove = True
            pkgs = thisgroup.packages
            for pkg in thisgroup.packages:
                txmbrs = self.remove(name=pkg, silence_warnings=True)
                txmbrs_used.extend(txmbrs)
                for txmbr in txmbrs:
                    txmbr.groups.append(thisgroup.groupid)

        return txmbrs_used

    def groupUnremove(self, grpid):
        """Unmark any packages in the given group from being removed.

        :param grpid: the name of the group to unmark the packages of
        """
        thesegroups = self.comps.return_groups(grpid)
        if not thesegroups:
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        for thisgroup in thesegroups:
            thisgroup.toremove = False
            pkgs = thisgroup.packages
            for pkg in thisgroup.packages:
                for txmbr in self.tsInfo:
                    if txmbr.po.name == pkg and txmbr.po.state in TS_INSTALL_STATES:
                        try:
                            txmbr.groups.remove(grpid)
                        except ValueError:
                            self.verbose_logger.log(logginglevels.DEBUG_1,
                               _("package %s was not marked in group %s"), txmbr.po,
                                grpid)
                            continue

                        # if there aren't any other groups mentioned then remove the pkg
                        if len(txmbr.groups) == 0:
                            self.tsInfo.remove(txmbr.po.pkgtup)


    def selectGroup(self, grpid, group_package_types=[], enable_group_conditionals=None):
        """Mark all the packages in the given group to be installed.

        :param grpid: the name of the group containing the packages to
           mark for installation
        :param group_package_types: a list of the types of groups to
           work with.  This overrides self.conf.group_package_types
        :param enable_group_conditionals: overrides
           self.conf.enable_group_conditionals
        :return: a list of transaction members added to the
           transaction set by this function
        """
        raise NotImplementedError, "not implemented in hawkey" # :hawkey
        if not self.comps.has_group(grpid):
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        txmbrs_used = []
        thesegroups = self.comps.return_groups(grpid)

        if not thesegroups:
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        package_types = self.conf.group_package_types
        if group_package_types:
            package_types = group_package_types

        for thisgroup in thesegroups:
            if thisgroup.selected:
                continue

            thisgroup.selected = True

            pkgs = []
            if 'mandatory' in package_types:
                pkgs.extend(thisgroup.mandatory_packages)
            if 'default' in package_types:
                pkgs.extend(thisgroup.default_packages)
            if 'optional' in package_types:
                pkgs.extend(thisgroup.optional_packages)

            old_txmbrs = len(txmbrs_used)
            for pkg in pkgs:
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    _('Adding package %s from group %s'), pkg, thisgroup.groupid)
                try:
                    txmbrs = self.install(name=pkg, pkg_warning_level='debug2')
                except Errors.InstallError, e:
                    self.verbose_logger.debug(_('No package named %s available to be installed'),
                        pkg)
                else:
                    txmbrs_used.extend(txmbrs)
                    for txmbr in txmbrs:
                        txmbr.groups.append(thisgroup.groupid)

            group_conditionals = self.conf.enable_group_conditionals
            if enable_group_conditionals is not None: # has to be this way so we can set it to False
                group_conditionals = enable_group_conditionals

            count_cond_test = 0
            if group_conditionals:
                for condreq, cond in thisgroup.conditional_packages.iteritems():
                    if self.isPackageInstalled(cond):
                        try:
                            txmbrs = self.install(name = condreq)
                        except Errors.InstallError:
                            # we don't care if the package doesn't exist
                            continue
                        else:
                            if cond not in self.tsInfo.conditionals:
                                self.tsInfo.conditionals[cond]=[]

                        txmbrs_used.extend(txmbrs)
                        for txmbr in txmbrs:
                            txmbr.groups.append(thisgroup.groupid)
                            self.tsInfo.conditionals[cond].append(txmbr.po)
                        continue
                    # Otherwise we hook into tsInfo.add to make sure
                    # we'll catch it if it's added later in this transaction
                    pkgs = self.pkgSack.searchNevra(name=condreq)
                    if pkgs:
                        if self.arch.multilib:
                            if self.conf.multilib_policy == 'best':
                                use = []
                                best = self.arch.legit_multi_arches
                                best.append('noarch')
                                for pkg in pkgs:
                                    if pkg.arch in best:
                                        use.append(pkg)
                                pkgs = use

                        pkgs = packagesNewestByName(pkgs)
                        count_cond_test += len(pkgs)

                        if cond not in self.tsInfo.conditionals:
                            self.tsInfo.conditionals[cond] = []
                        self.tsInfo.conditionals[cond].extend(pkgs)
            if len(txmbrs_used) == old_txmbrs:
                self.logger.critical(_('Warning: Group %s does not have any packages.'), thisgroup.groupid)
                if count_cond_test:
                    self.logger.critical(_('Group %s does have %u conditional packages, which may get installed.'), count_cond_test)
        return txmbrs_used

    def deselectGroup(self, grpid, force=False):
        """Unmark the packages in the given group from being
        installed.

        :param grpid: the name of the group containing the packages to
           unmark from installation
        :param force: if True, force remove all the packages in the
           given group from the transaction
        """

        if not self.comps.has_group(grpid):
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        thesegroups = self.comps.return_groups(grpid)
        if not thesegroups:
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)

        for thisgroup in thesegroups:
            thisgroup.selected = False

            for pkgname in thisgroup.packages:
                txmbrs = self.tsInfo.getMembersWithState(None,TS_INSTALL_STATES)
                for txmbr in txmbrs:
                    if txmbr.po.name != pkgname:
                        continue

                    if not force:
                        try:
                            txmbr.groups.remove(grpid)
                        except ValueError:
                            self.verbose_logger.log(logginglevels.DEBUG_1,
                               _("package %s was not marked in group %s"), txmbr.po,
                                grpid)
                            continue

                    # If the pkg isn't part of any group, or the group is
                    # being forced out ... then remove the pkg
                    if force or len(txmbr.groups) == 0:
                        self.tsInfo.remove(txmbr.po.pkgtup)
                        for pkg in self.tsInfo.conditionals.get(txmbr.name, []):
                            self.tsInfo.remove(pkg.pkgtup)

    def getPackageObject(self, pkgtup, allow_missing=False):
        """Return a package object that corresponds to the given
        package tuple.

        :param pkgtup: the package tuple specifying the package object
           to return

        :param allow_missing: If no package corresponding to the given
           package tuple can be found, None is returned if
           *allow_missing* is True, and a :class:`Errors.DepError` is
           raised if *allow_missing* is False.
        :return: a package object corresponding to the given package tuple
        :raises: a :class:`Errors.DepError` if no package
           corresponding to the given package tuple can be found, and
           *allow_missing* is False
        """
        raise NotImplementedError, "not implemented in hawkey" # :hawkey
        # look it up in the self.localPackages first:
        for po in self.localPackages:
            if po.pkgtup == pkgtup:
                return po

        pkgs = self.pkgSack.searchPkgTuple(pkgtup)

        if len(pkgs) == 0:
            self._add_not_found_a(pkgs, pkgtup=pkgtup)
            if allow_missing: #  This can happen due to excludes after .up has
                return None   # happened.
            raise Errors.DepError, _('Package tuple %s could not be found in packagesack') % str(pkgtup)

        if len(pkgs) > 1: # boy it'd be nice to do something smarter here FIXME
            result = pkgs[0]
        else:
            result = pkgs[0] # which should be the only

            # this is where we could do something to figure out which repository
            # is the best one to pull from

        return result

    def getInstalledPackageObject(self, pkgtup):
        """Return a :class:`packages.YumInstalledPackage` object that
        corresponds to the given package tuple.  This function should
        be used instead of :func:`searchPkgTuple` if you are assuming
        that the package object exists.

        :param pkgtup: the package tuple specifying the package object
           to return
        :return: a :class:`packages.YumInstalledPackage` object corresponding
           to the given package tuple
        :raises: a :class:`Errors.RpmDBError` if the specified package
           object cannot be found
        """
        pkgs = self.rpmdb.searchPkgTuple(pkgtup)
        if len(pkgs) == 0:
            self._add_not_found_i(pkgs, pkgtup=pkgtup)
            raise Errors.RpmDBError, _('Package tuple %s could not be found in rpmdb') % str(pkgtup)

        # Dito. FIXME from getPackageObject() for len() > 1 ... :)
        po = pkgs[0] # take the first one
        return po

    def gpgKeyCheck(self):
        """Checks for the presence of GPG keys in the rpmdb.

        :return: 0 if there are no GPG keys in the rpmdb, and 1 if
           there are keys
        """
        gpgkeyschecked = self.cache_c.cachedir + '/.gpgkeyschecked.yum'
        if os.path.exists(gpgkeyschecked):
            return 1

        myts = dnf.rpmUtils.transaction.initReadOnlyTransaction(root=self.conf.installroot)
        myts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
        idx = myts.dbMatch('name', 'gpg-pubkey')
        keys = idx.count()
        del idx
        del myts

        if keys == 0:
            return 0
        else:
            mydir = os.path.dirname(gpgkeyschecked)
            if not os.path.exists(mydir):
                os.makedirs(mydir)

            fo = open(gpgkeyschecked, 'w')
            fo.close()
            del fo
            return 1

    def returnPackagesByDep(self, depstring):
        """Return a list of package objects that provide the given
        dependencies.

        :param depstring: a string specifying the dependency to return
           the packages that fulfil
        :return: a list of packages that fulfil the given dependency
        """
        if not depstring:
            return []

        # parse the string out
        #  either it is 'dep (some operator) e:v-r'
        #  or /file/dep
        #  or packagename
        if type(depstring) == types.TupleType:
            (depname, depflags, depver) = depstring
        else:
            depname = depstring
            depflags = None
            depver = None

            if depstring[0] != '/':
                # not a file dep - look at it for being versioned
                dep_split = depstring.split()
                if len(dep_split) == 3:
                    depname, flagsymbol, depver = dep_split
                    if not flagsymbol in SYMBOLFLAGS:
                        raise Errors.YumBaseError, _('Invalid version flag from: %s') % str(depstring)
                    depflags = SYMBOLFLAGS[flagsymbol]

        return self.pkgSack.getProvides(depname, depflags, depver).keys()

    def returnPackageByDep(self, depstring):
        """Return the best, or first, package object that provides the
        given dependencies.

        :param depstring: a string specifying the dependency to return
           the package that fulfils
        :return: the best, or first, package that fulfils the given
           dependency
        :raises: a :class:`Errors.YumBaseError` if no packages that
           fulfil the given dependency can be found
        """
        # we get all sorts of randomness here
        raise NotImplementedError, "not implemented in hawkey" # :hawkey
        errstring = depstring
        if type(depstring) not in types.StringTypes:
            errstring = str(depstring)

        try:
            pkglist = self.returnPackagesByDep(depstring)
        except Errors.YumBaseError:
            raise Errors.YumBaseError, _('No Package found for %s') % errstring

        ps = ListPackageSack(pkglist)
        result = self._bestPackageFromList(ps.returnNewestByNameArch())
        if result is None:
            raise Errors.YumBaseError, _('No Package found for %s') % errstring

        return result

    def returnInstalledPackagesByDep(self, depstring):
        """Return a list of installed package objects that provide the
        given dependencies.

        :param depstring: a string specifying the dependency to return
           the packages that fulfil
        :return: a list of installed packages that fulfil the given
           dependency
        """
        if not depstring:
            return []

        # parse the string out
        #  either it is 'dep (some operator) e:v-r'
        #  or /file/dep
        #  or packagename
        if type(depstring) == types.TupleType:
            (depname, depflags, depver) = depstring
        else:
            depname = depstring
            depflags = None
            depver = None

            if depstring[0] != '/':
                # not a file dep - look at it for being versioned
                dep_split = depstring.split()
                if len(dep_split) == 3:
                    depname, flagsymbol, depver = dep_split
                    if not flagsymbol in SYMBOLFLAGS:
                        raise Errors.YumBaseError, _('Invalid version flag from: %s') % str(depstring)
                    depflags = SYMBOLFLAGS[flagsymbol]

        return self.rpmdb.getProvides(depname, depflags, depver).keys()

    def returnInstalledPackageByDep(self, depstring):
        """Return the best, or first, installed package object that provides the
        given dependencies.

        :param depstring: a string specifying the dependency to return
           the package that fulfils
        :return: the best, or first, installed package that fulfils the given
           dependency
        :raises: a :class:`Errors.YumBaseError` if no packages that
           fulfil the given dependency can be found
        """
        # we get all sorts of randomness here
        raise NotImplementedError, "not implemented in hawkey" # :hawkey
        errstring = depstring
        if type(depstring) not in types.StringTypes:
            errstring = str(depstring)

        try:
            pkglist = self.returnInstalledPackagesByDep(depstring)
        except Errors.YumBaseError:
            raise Errors.YumBaseError, _('No Package found for %s') % errstring

        ps = ListPackageSack(pkglist)
        result = self._bestPackageFromList(ps.returnNewestByNameArch())
        if result is None:
            raise Errors.YumBaseError, _('No Package found for %s') % errstring

        return result

    def _bestPackageFromList(self, pkglist):
        """take list of package objects and return the best package object.
           If the list is empty, return None.

           Note: this is not aware of multilib so make sure you're only
           passing it packages of a single arch group."""


        if len(pkglist) == 0:
            return None

        if len(pkglist) == 1:
            return pkglist[0]

        bestlist = self._compare_providers(pkglist, None)
        return bestlist[0][0]

    def bestPackagesFromList(self, pkglist, arch=None, single_name=False):
        """Return the best packages from a list of packages.  This
        function is multilib aware, so that it will not compare
        multilib to singlelib packages.

        :param pkglist: the list of packages to return the best
           packages from
        :param arch: packages will be selected that are compatible
           with the architecture specified by *arch*
        :param single_name: whether to return a single package name
        :return: a list of the best packages from *pkglist*
        """
        returnlist = []
        compatArchList = self.arch.get_arch_list(arch)
        multiLib = []
        singleLib = []
        noarch = []
        for po in pkglist:
            if po.arch not in compatArchList:
                continue
            elif po.arch in ("noarch"):
                noarch.append(po)
            elif isMultiLibArch(arch=po.arch):
                multiLib.append(po)
            else:
                singleLib.append(po)

        # we now have three lists.  find the best package(s) of each
        multi = self._bestPackageFromList(multiLib)
        single = self._bestPackageFromList(singleLib)
        no = self._bestPackageFromList(noarch)

        if single_name and multi and single and multi.name != single.name:
            # Sinlge _must_ match multi, if we want a single package name
            single = None

        # now, to figure out which arches we actually want
        # if there aren't noarch packages, it's easy. multi + single
        if no is None:
            if multi: returnlist.append(multi)
            if single: returnlist.append(single)
        # if there's a noarch and it's newer than the multilib, we want
        # just the noarch.  otherwise, we want multi + single
        elif multi:
            best = self._bestPackageFromList([multi,no])
            if best.arch == "noarch":
                returnlist.append(no)
            else:
                if multi: returnlist.append(multi)
                if single: returnlist.append(single)
        # similar for the non-multilib case
        elif single:
            best = self._bestPackageFromList([single,no])
            if best.arch == "noarch":
                returnlist.append(no)
            else:
                returnlist.append(single)
        # if there's not a multi or single lib, then we want the noarch
        else:
            returnlist.append(no)

        return returnlist

    def _at_groupinstall(self, pattern):
        " Do groupinstall via. leading @ on the cmd line, for install/update."
        assert pattern[0] == '@'
        group_string = pattern[1:]
        tx_return = []
        for group in self.comps.return_groups(group_string):
            try:
                txmbrs = self.selectGroup(group.groupid)
                tx_return.extend(txmbrs)
            except Errors.GroupsError:
                self.logger.critical(_('Warning: Group %s does not exist.'), group_string)
                continue
        return tx_return

    def _at_groupremove(self, pattern):
        " Do groupremove via. leading @ on the cmd line, for remove."
        assert pattern[0] == '@'
        group_string = pattern[1:]
        tx_return = []
        try:
            txmbrs = self.groupRemove(group_string)
        except Errors.GroupsError:
            self.logger.critical(_('No group named %s exists'), group_string)
        else:
            tx_return.extend(txmbrs)
        return tx_return

    #  Note that this returns available pkgs, and not txmbrs like the other
    # _at_group* functions.
    def _at_groupdowngrade(self, pattern):
        " Do downgrade of a group via. leading @ on the cmd line."
        assert pattern[0] == '@'
        grpid = pattern[1:]

        thesegroups = self.comps.return_groups(grpid)
        if not thesegroups:
            raise Errors.GroupsError, _("No Group named %s exists") % to_unicode(grpid)
        pkgnames = set()
        for thisgroup in thesegroups:
            pkgnames.update(thisgroup.packages)
        return self.pkgSack.searchNames(pkgnames)

    def _minus_deselect(self, pattern):
        """ Remove things from the transaction, like kickstart. """
        assert pattern[0] == '-'
        pat = pattern[1:].strip()

        if pat and pat[0] == '@':
            pat = pat[1:]
            return self.deselectGroup(pat)

        return self.tsInfo.deselect(pat)

    def _add_prob_flags(self, *flags):
        """ Add all of the passed flags to the tsInfo.probFilterFlags array. """
        for flag in flags:
            if flag not in self.tsInfo.probFilterFlags:
                self.tsInfo.probFilterFlags.append(flag)

    def install(self, po=None, **kwargs):
        """Mark the specified item for installation.  If a package
        object is given, mark it for installation.  Otherwise, mark
        the best package specified by the key word arguments for
        installation.

        :param po: a package object to install
        :param kwargs: if *po* is not specified, these keyword
           arguments will be used to find the best package to install
        :return: a list of the transaction members added to the
           transaction set by this function
        :raises: :class:`Errors.InstallError` if there is a problem
           installing the package
        """


        #  This is kind of hacky, we really need a better way to do errors than
        # doing them directly from .install/etc. ... but this is easy. *sigh*.
        #  We are only using this in "groupinstall" atm. ... so we don't have
        # a long list of "blah already installed." messages when people run
        # "groupinstall mygroup" in yum-cron etc.
        pkg_warn = kwargs.get('pkg_warning_level', 'flibble')
        def _dbg2(*args, **kwargs):
            self.verbose_logger.log(logginglevels.DEBUG_2, *args, **kwargs)
        level2func = {'debug2' : _dbg2,
                      'warning' : self.verbose_logger.warning}
        if pkg_warn not in level2func:
            pkg_warn = 'warning'
        pkg_warn = level2func[pkg_warn]

        tx_return = []
        pkgs = []
        was_pattern = False
        if po:
            if not isinstance(po, hawkey.Package):
                raise Errors.InstallError, _('Package Object was not a package object instance')
            txmbr = self.tsInfo.addInstall(po)
            tx_return.append(txmbr)
            return tx_return

        if not kwargs:
            raise Errors.InstallError, _('Nothing specified to install')

        pat = kwargs['pattern']
        if queries.is_nevra(pat):
            availpkgs = queries.available_by_nevra(self.sack, pat)
        elif self.conf.multilib_policy == "best":
            sltr = selector.Selector(self.sack).set_autoglob(name=pat)
            self.tsInfo.add_selector_install(sltr)
            return self.tsInfo
        else:
            availpkgs = queries.available_by_name(self.sack, pat,
                                                  latest_only=True)
        for pkg in availpkgs:
            self.tsInfo.addInstall(pkg)

        return self.tsInfo

    def update(self, po=None, requiringPo=None, update_to=False, **kwargs):
        """Mark the specified items to be updated.  If a package
        object is given, mark it.  Else, if a package is specified by
        the keyword arguments, mark it.  Finally, if nothing is given,
        mark all installed packages to be updated.


        :param po: the package object to be marked for updating
        :param requiringPo: the package object that requires the
           upgrade
        :param update_to: if *update_to* is True, the update will only
           be run if it will update the given package to the given
           version.  For example, if the package foo-1-2 is installed,::

             updatePkgs(["foo-1-2], update_to=False)

           will work identically to::

             updatePkgs(["foo"])

           but::

             updatePkgs(["foo-1-2"], update_to=True)

           will do nothing
        :param kwargs: if *po* is not given, the names or wildcards in
           *kwargs* will be used to find the packages to update
        :return: a list of transaction members added to the
           transaction set by this function
        """
        # check for args - if no po nor kwargs, do them all
        # if po, do it, ignore all else
        # if no po do kwargs
        # uninstalled pkgs called for update get returned with errors in a list, maybe?

        tx_return = []
        instpkgs = []
        availpkgs = []
        if po: # just a po
            if po.from_system:
                instpkgs.append(po)
            else:
                installed = sorted(queries.installed_by_name(self.sack, po.name))
                if len(installed) > 0 and installed[-1] < po:
                    txmbr = self.tsInfo.addUpdate(po)
                    tx_return.append(txmbr)
        elif 'pattern' in kwargs:
            pats = kwargs['pattern']
            availpkgs = queries.updates_by_name(self.sack, pats, latest_only=True)
            for pkg in availpkgs:
                txmbr = self.tsInfo.addUpdate(pkg)
                tx_return.append(txmbr)
        elif not kwargs: # update everything updatable
            self.tsInfo.upgrade_all = True
        else: # we have kwargs, sort them out.
            raise NotImplementedError("not in DNF yet")
        return tx_return

    def remove(self, po=None, **kwargs):
        """Mark the specified packages for removal. If a package
        object is given, mark it for removal.  Otherwise, mark the
        package specified by the keyword arguments.

        :param po: the package object to mark for installation
        :param kwargs: If *po* is not given, the keyword arguments
           will be used to specify a package to mark for installation
        :return: a list of the transaction members that were added to
           the transaction set by this method
        :raises: :class:`Errors.RemoveError` if nothing is specified
           to mark for removal
        """
        if not po and not kwargs:
            raise Errors.RemoveError, 'Nothing specified to remove'

        tx_return = []
        pkgs = []

        if po:
            pkgs = [po]
        else:
            pattern = kwargs['pattern']
            installed = queries.installed_by_name(self.sack, pattern)
            if not installed:
                installed = queries.installed_by_nevra(self.sack, pattern)
            for pkg in installed:
                txmbr = self.tsInfo.addErase(pkg)
                tx_return.append(txmbr)
        return tx_return

    def _local_common(self, path):
        self.sack.create_cmdline_repo()
        try:
            po = self.sack.add_cmdline_package(path)
        except IOError:
            self.logger.critical(_('Cannot open: %s. Skipping.'), path)
            return None
        return po

    def downgrade_local(self, path):
        """Mark a package on the local filesystem (i.e. not from a
        repository) to be downgraded.

        :param pkg: a string specifying the path to an rpm file in the
           local filesystem to be marked to be downgraded
        :param po: a :class:`packages.YumLocalPackage`
        :return: a list of the transaction members added to the
           transaction set by this method
        """
        po = self._local_common(path)
        if not po:
            return []
        return self.downgrade(po)

    def install_local(self, path):
        """Mark a package on the local filesystem (i.e. not from a
        repository) for installation.

        :param pkg: a string specifying the path to an rpm file in the
           local filesystem to be marked for installation
        :param po: a :class:`packages.YumLocalPackage`
        :param updateonly: if True, the given package will only be
           marked for installation if it is an upgrade for a package
           that is already installed.  If False, this restriction is
           not enforced
        :return: a list of the transaction members added to the
           transaction set by this method
        """
        po = self._local_common(path)
        if not po:
            return []
        return self.install(po)

    def update_local(self, path):
        po = self._local_common(path)
        if not po:
            return []
        return self.update(po)

    def reinstall_local(self, path):
        """Mark a package on the local filesystem (i.e. not from a
        repository) for reinstallation.

        :param pkg: a string specifying the path to an rpm file in the
           local filesystem to be marked for reinstallation
        :param po: a :class:`packages.YumLocalPackage`
        :return: a list of the transaction members added to the
           transaction set by this method
        """
        po = self._local_common(path)
        if not po:
            return []
        return self.reinstall(po)

    def reinstall(self, po=None, **kwargs):
        """Mark the given package for reinstallation.  This is
        accomplished by setting problem filters to allow a reinstall
        take place, then calling :func:`install`.

        :param po: the package object to mark for reinstallation
        :param kwargs: if po is not given, the keyword will be used to
           specify a package for reinstallation
        :return: a list of the transaction members added to the
           transaction set by this method
        :raises: :class:`Errors.ReinstallRemoveError` or
           :class:`Errors.ReinstallInstallError` depending the nature
           of the error that is encountered
        """
        self._add_prob_flags(rpm.RPMPROB_FILTER_REPLACEPKG,
                             rpm.RPMPROB_FILTER_REPLACENEWFILES,
                             rpm.RPMPROB_FILTER_REPLACEOLDFILES)

        tx_return = []
        if po:
            installed = queries.installed_exact(self.sack,
                                                po.name, po.evr, po.arch)
            available = [po]
        else:
            pat = kwargs['pattern']
            installed = queries.installed_by_name(self.sack, pat)
            available = queries.available_by_name(self.sack, pat)
        if not installed:
            raise Errors.ReinstallRemoveError(
                _("Problem in reinstall: no package matched to remove"))

        installed = queries.per_nevra_dict(installed)
        available = queries.per_nevra_dict(available)
        for nevra in installed:
            if not nevra in available:
                msg = _("Problem in reinstall: no package %s matched to install")
                msg %= nevra
                failed_pkgs = [installed[nevra]]
                raise Errors.ReinstallInstallError(msg, failed_pkgs=failed_pkgs)

            txmbr = self.tsInfo.addInstall(available[nevra])
            tx_return.append(txmbr)

        return tx_return

    def _is_local_exclude(self, po, pkglist):
        """returns True if the local pkg should be excluded"""

        if "all" in self.conf.disable_excludes or \
           "main" in self.conf.disable_excludes:
            return False

        toexc = []
        if len(self.conf.exclude) > 0:
            exactmatch, matched, unmatched = \
                   parsePackages(pkglist, self.conf.exclude, casematch=1)
            toexc = exactmatch + matched

        if po in toexc:
            return True

        return False

    def downgrade(self, po=None, pattern=None, **kwargs):
        """Mark a package to be downgraded.  This is equivalent to
        first removing the currently installed package, and then
        installing the older version.

        :param po: the package object to be marked to be downgraded
        :param kwargs: if a package object is not given, the keyword
           arguments will be used to specify a package to be marked to
           be downgraded
        :return: a list of the transaction members added to the
           transaction set by this method
        :raises: :class:`Errors.DowngradeError` if no packages are
           specified or available for downgrade
        """
        tx_return = []
        if po:
            installed = sorted(queries.installed_by_name(self.sack, po.name))
            if len(installed) > 0 and installed[0] > po:
                txmbrs = self.tsInfo.addDowngrade(po, installed[0])
                tx_return.append(txmbrs)
        elif pattern:
            for pkg in queries.downgrades_by_name(self.sack, pattern):
                txmbr = self.tsInfo.addDowngrade(pkg)
                tx_return.append(txmbr)
        elif kwargs:
            raise NotImplementedError, "yumbase.downgrade() kwargs not implemented"
        else:
            raise Errors.DowngradeError, 'Nothing specified to downgrade'

        if len(tx_return) > 0:
            self._add_prob_flags(rpm.RPMPROB_FILTER_OLDPACKAGE)
        return tx_return

    def history_redo(self, transaction,
                     force_reinstall=False, force_changed_removal=False):
        """Repeat the transaction represented by the given
        :class:`history.YumHistoryTransaction` object.

        :param transaction: a
           :class:`history.YumHistoryTransaction` object
           representing the transaction to be repeated
        :param force_reinstall: bool - do we want to reinstall anything that was
           installed/updated/downgraded/etc.
        :param force_changed_removal: bool - do we want to force remove anything
           that was downgraded or upgraded.
        :return: whether the transaction was repeated successfully
        """
        # NOTE: This is somewhat basic atm. ... see comment in undo.
        #  Also note that redo doesn't force install Dep-Install packages,
        # which is probably what is wanted the majority of the time.

        old_conf_obs = self.conf.obsoletes
        self.conf.obsoletes = False
        done = False
        for pkg in transaction.trans_data:
            if pkg.state == 'Reinstall':
                if self.reinstall(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Downgrade':
                if force_reinstall and self.rpmdb.searchPkgTuple(pkg.pkgtup):
                    if self.reinstall(pkgtup=pkg.pkgtup):
                        done = True
                    continue

                try:
                    if self.downgrade(pkgtup=pkg.pkgtup):
                        done = True
                except Errors.DowngradeError:
                    self.logger.critical(_('Failed to downgrade: %s'), pkg)
        for pkg in transaction.trans_data:
            if force_changed_removal and pkg.state == 'Downgraded':
                if self.tsInfo.getMembers(pkg.pkgtup):
                    continue
                if self.remove(pkgtup=pkg.pkgtup, silence_warnings=True):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Update':
                if force_reinstall and self.rpmdb.searchPkgTuple(pkg.pkgtup):
                    if self.reinstall(pkgtup=pkg.pkgtup):
                        done = True
                    continue

                if self.update(pkgtup=pkg.pkgtup):
                    done = True
                else:
                    self.logger.critical(_('Failed to upgrade: %s'), pkg)
        for pkg in transaction.trans_data:
            if force_changed_removal and pkg.state == 'Updated':
                if self.tsInfo.getMembers(pkg.pkgtup):
                    continue
                if self.remove(pkgtup=pkg.pkgtup, silence_warnings=True):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state in ('Install', 'True-Install', 'Obsoleting'):
                if force_reinstall and self.rpmdb.searchPkgTuple(pkg.pkgtup):
                    if self.reinstall(pkgtup=pkg.pkgtup):
                        done = True
                    continue

                if self.install(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Erase':
                if self.remove(pkgtup=pkg.pkgtup):
                    done = True
        self.conf.obsoletes = old_conf_obs
        return done

    def history_undo(self, transaction):
        """Undo the transaction represented by the given
        :class:`history.YumHistoryTransaction` object.

        :param transaction: a
           :class:`history.YumHistoryTransaction` object
           representing the transaction to be undone
        :return: whether the transaction was undone successfully
        """
        # NOTE: This is somewhat basic atm. ... for instance we don't check
        #       that we are going from the old new version. However it's still
        #       better than the RHN rollback code, and people pay for that :).
        #  We turn obsoletes off because we want the specific versions of stuff
        # from history ... even if they've been obsoleted since then.
        old_conf_obs = self.conf.obsoletes
        self.conf.obsoletes = False
        done = False
        for pkg in transaction.trans_data:
            if pkg.state == 'Reinstall':
                if self.reinstall(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Updated':
                try:
                    if self.downgrade(pkgtup=pkg.pkgtup):
                        done = True
                except Errors.DowngradeError:
                    self.logger.critical(_('Failed to downgrade: %s'), pkg)
        for pkg in transaction.trans_data:
            if pkg.state == 'Downgraded':
                if self.update(pkgtup=pkg.pkgtup):
                    done = True
                else:
                    self.logger.critical(_('Failed to upgrade: %s'), pkg)
        for pkg in transaction.trans_data:
            if pkg.state == 'Obsoleting':
                #  Note that obsoleting can mean anything, so if this is part of
                # something else, it should be done by now (so do nothing).
                if self.tsInfo.getMembers(pkg.pkgtup):
                    continue
                #  If not it should be an install/obsolete ... so remove it.
                if self.remove(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state in ('Dep-Install', 'Install', 'True-Install'):
                if self.remove(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Obsoleted':
                if self.install(pkgtup=pkg.pkgtup):
                    done = True
        for pkg in transaction.trans_data:
            if pkg.state == 'Erase':
                if self.install(pkgtup=pkg.pkgtup):
                    done = True
        self.conf.obsoletes = old_conf_obs
        return done

    def _retrievePublicKey(self, keyurl, repo=None, getSig=True):
        """
        Retrieve a key file
        @param keyurl: url to the key to retrieve
        Returns a list of dicts with all the keyinfo
        """
        key_installed = False

        msg = _('Retrieving key from %s') % keyurl
        self.verbose_logger.log(logginglevels.INFO_2, msg)

        # Go get the GPG key from the given URL
        try:
            url = misc.to_utf8(keyurl)
            if repo is None:
                opts = {'limit':9999}
                text = 'global/gpgkey'
            else:
                #  If we have a repo. use the proxy etc. configuration for it.
                # In theory we have a global proxy config. too, but meh...
                # external callers should just update.
                opts = repo._default_grabopts()
                text = repo.id + '/gpgkey'
            rawkey = urlgrabber.urlread(url, **opts)

        except urlgrabber.grabber.URLGrabError, e:
            raise Errors.YumBaseError(_('GPG key retrieval failed: ') +
                                      to_unicode(str(e)))

        # check for a .asc file accompanying it - that's our gpg sig on the key
        # suck it down and do the check
        sigfile = None
        valid_sig = False
        if getSig and repo and repo.gpgcakey:
            self.getCAKeyForRepo(repo, callback=repo.confirm_func)
            try:
                url = misc.to_utf8(keyurl + '.asc')
                opts = repo._default_grabopts()
                text = repo.id + '/gpgkeysig'
                sigfile = urlgrabber.urlopen(url, **opts)

            except urlgrabber.grabber.URLGrabError, e:
                sigfile = None

            if sigfile:
                if not misc.valid_detached_sig(sigfile,
                                    StringIO.StringIO(rawkey), repo.gpgcadir):
                    #if we decide we want to check, even though the sig failed
                    # here is where we would do that
                    raise Errors.YumBaseError(_('GPG key signature on key %s does not match CA Key for repo: %s') % (url, repo.id))
                else:
                    msg = _('GPG key signature verified against CA Key(s)')
                    self.verbose_logger.log(logginglevels.INFO_2, msg)
                    valid_sig = True

        # Parse the key
        try:
            keys_info = misc.getgpgkeyinfo(rawkey, multiple=True)
        except ValueError, e:
            raise Errors.YumBaseError(_('Invalid GPG Key from %s: %s') %
                                      (url, to_unicode(str(e))))
        keys = []
        for keyinfo in keys_info:
            thiskey = {}
            for info in ('keyid', 'timestamp', 'userid',
                         'fingerprint', 'raw_key'):
                if info not in keyinfo:
                    raise Errors.YumBaseError, \
                      _('GPG key parsing failed: key does not have value %s') + info
                thiskey[info] = keyinfo[info]
            thiskey['hexkeyid'] = misc.keyIdToRPMVer(keyinfo['keyid']).upper()
            thiskey['valid_sig'] = valid_sig
            thiskey['has_sig'] = bool(sigfile)
            keys.append(thiskey)

        return keys

    def _log_key_import(self, info, keyurl, keytype='GPG'):
        msg = None
        fname = dnf.util.strip_prefix(keyurl, "file://")
        if fname:
            pkgs = queries.by_file(self.sack, fname)
            if pkgs:
                pkg = pkgs[0]
                msg = (_('Importing %s key 0x%s:\n'
                         ' Userid     : "%s"\n'
                         ' Fingerprint: %s\n'
                         ' Package    : %s (%s)\n'
                         ' From       : %s') %
                       (keytype, info['hexkeyid'], to_unicode(info['userid']),
                        misc.gpgkey_fingerprint_ascii(info),
                        pkg, pkg.reponame, fname))
        if msg is None:
            msg = (_('Importing %s key 0x%s:\n'
                     ' Userid     : "%s"\n'
                     ' Fingerprint: %s\n'
                     ' From       : %s') %
                   (keytype, info['hexkeyid'], to_unicode(info['userid']),
                    misc.gpgkey_fingerprint_ascii(info),
                    keyurl.replace("file://","")))
        self.logger.critical("%s", msg)

    def getKeyForPackage(self, po, askcb = None, fullaskcb = None):
        """Retrieve a key for a package. If needed, use the given
        callback to prompt whether the key should be imported.

        :param po: the package object to retrieve the key of
        :param askcb: Callback function to use to ask permission to
           import a key.  The arguments *askck* should take are the
           package object, the userid of the key, and the keyid
        :param fullaskcb: Callback function to use to ask permission to
           import a key.  This differs from *askcb* in that it gets
           passed a dictionary so that we can expand the values passed.
        :raises: :class:`Errors.YumBaseError` if there are errors
           retrieving the keys
        """
        repo = self.repos.getRepo(po.repoid)
        keyurls = repo.gpgkey
        key_installed = False

        def _prov_key_data(msg):
            msg += _('\n\n\n'
                     ' Failing package is: %s\n'
                     ' GPG Keys are configured as: %s\n'
                     ) % (po, ", ".join(repo.gpgkey))
            return msg

        user_cb_fail = False
        for keyurl in keyurls:
            keys = self._retrievePublicKey(keyurl, repo)

            for info in keys:
                ts = self.rpm.readonly_ts
                # Check if key is already installed
                if misc.keyInstalled(ts, info['keyid'], info['timestamp']) >= 0:
                    self.logger.info(_('GPG key at %s (0x%s) is already installed') % (
                        keyurl, info['hexkeyid']))
                    continue

                if repo.gpgcakey and info['has_sig'] and info['valid_sig']:
                    key_installed = True
                else:
                    # Try installing/updating GPG key
                    self._log_key_import(info, keyurl)
                    rc = False
                    if self.conf.assumeno:
                        rc = False
                    elif self.conf.assumeyes:
                        rc = True

                    # grab the .sig/.asc for the keyurl, if it exists
                    # if it does check the signature on the key
                    # if it is signed by one of our ca-keys for this repo or the global one
                    # then rc = True
                    # else ask as normal.

                    elif fullaskcb:
                        rc = fullaskcb({"po": po, "userid": info['userid'],
                                        "hexkeyid": info['hexkeyid'],
                                        "keyurl": keyurl,
                                        "fingerprint": info['fingerprint'],
                                        "timestamp": info['timestamp']})
                    elif askcb:
                        rc = askcb(po, info['userid'], info['hexkeyid'])

                    if not rc:
                        user_cb_fail = True
                        continue

                # Import the key
                result = ts.pgpImportPubkey(misc.procgpgkey(info['raw_key']))
                if result != 0:
                    msg = _('Key import failed (code %d)') % result
                    raise Errors.YumBaseError, _prov_key_data(msg)
                self.logger.info(_('Key imported successfully'))
                key_installed = True

        if not key_installed and user_cb_fail:
            raise Errors.YumBaseError, _("Didn't install any keys")

        if not key_installed:
            msg = _('The GPG keys listed for the "%s" repository are ' \
                  'already installed but they are not correct for this ' \
                  'package.\n' \
                  'Check that the correct key URLs are configured for ' \
                  'this repository.') % repo.name
            raise Errors.YumBaseError, _prov_key_data(msg)

        # Check if the newly installed keys helped
        result, errmsg = self.sigCheckPkg(po)
        if result != 0:
            msg = _("Import of key(s) didn't help, wrong key(s)?")
            self.logger.info(msg)
            errmsg = to_unicode(errmsg)
            raise Errors.YumBaseError, _prov_key_data(errmsg)

    def _getAnyKeyForRepo(self, repo, destdir, keyurl_list, is_cakey=False, callback=None):
        """
        Retrieve a key for a repository If needed, prompt for if the key should
        be imported using callback

        @param repo: Repository object to retrieve the key of.
        @param destdir: destination of the gpg pub ring
        @param keyurl_list: list of urls for gpg keys
        @param is_cakey: bool - are we pulling in a ca key or not
        @param callback: Callback function to use for asking for permission to
                         import a key. This is verification, but also "choice".
                         Takes a dictionary of key info.
        """

        key_installed = False

        def _prov_key_data(msg):
            cakeytxt = _("No")
            if is_cakey:
                cakeytxt = _("Yes")
            msg += _('\n\n\n'
                     ' CA Key: %s\n'
                     ' Failing repo is: %s\n'
                     ' GPG Keys are configured as: %s\n'
                     ) % (cakeytxt, repo, ", ".join(keyurl_list))
            return msg

        user_cb_fail = False
        for keyurl in keyurl_list:
            keys = self._retrievePublicKey(keyurl, repo, getSig=not is_cakey)
            for info in keys:
                # Check if key is already installed
                if hex(int(info['keyid']))[2:-1].upper() in misc.return_keyids_from_pubring(destdir):
                    self.logger.info(_('GPG key at %s (0x%s) is already imported') % (
                        keyurl, info['hexkeyid']))
                    key_installed = True
                    continue
                # Try installing/updating GPG key
                if is_cakey:
                    # know where the 'imported_cakeys' file is
                    ikf = repo.base_persistdir + '/imported_cakeys'
                    keytype = 'CA'
                    cakeys  = []
                    try:
                        cakeys_d = open(ikf, 'r').read()
                        cakeys = cakeys_d.split('\n')
                    except (IOError, OSError):
                        pass
                    if str(info['hexkeyid']) in cakeys:
                        key_installed = True
                else:
                    keytype = 'GPG'
                    if repo.gpgcakey and info['has_sig'] and info['valid_sig']:
                        key_installed = True

                if not key_installed:
                    self._log_key_import(info, keyurl, keytype)
                    rc = False
                    if self.conf.assumeno:
                        rc = False
                    elif self.conf.assumeyes:
                        rc = True

                    elif callback:
                        rc = callback({"repo": repo, "userid": info['userid'],
                                        "hexkeyid": info['hexkeyid'], "keyurl": keyurl,
                                        "fingerprint": info['fingerprint'],
                                        "timestamp": info['timestamp']})


                    if not rc:
                        user_cb_fail = True
                        continue

                # Import the key
                result = misc.import_key_to_pubring(info['raw_key'], info['hexkeyid'], gpgdir=destdir)
                if not result:
                    msg = _('Key %s import failed') % info['hexkeyid']
                    raise Errors.YumBaseError, _prov_key_data(msg)
                self.logger.info(_('Key imported successfully'))
                key_installed = True
                # write out the key id to imported_cakeys in the repos basedir
                if is_cakey and key_installed:
                    if info['hexkeyid'] not in cakeys:
                        ikfo = open(ikf, 'a')
                        try:
                            ikfo.write(info['hexkeyid']+'\n')
                            ikfo.flush()
                            ikfo.close()
                        except (IOError, OSError):
                            # maybe a warning - but in general this is not-critical, just annoying to the user
                            pass

        if not key_installed and user_cb_fail:
            msg = _("Didn't install any keys for repo %s") % repo
            raise Errors.YumBaseError, _prov_key_data(msg)

        if not key_installed:
            msg = \
                  _('The GPG keys listed for the "%s" repository are ' \
                  'already installed but they are not correct.\n' \
                  'Check that the correct key URLs are configured for ' \
                  'this repository.') % (repo.name)
            raise Errors.YumBaseError, _prov_key_data(msg)

    def getKeyForRepo(self, repo, callback=None):
        """Retrieve a key for a repository.  If needed, use the given
        callback to prompt whether the key should be imported.

        :param repo: repository object to retrieve the key of
        :param callback: callback function to use for asking for
           verification of key information
        """
        self._getAnyKeyForRepo(repo, repo.gpgdir, repo.gpgkey, is_cakey=False, callback=callback)

    def getCAKeyForRepo(self, repo, callback=None):
        """Retrieve a key for a repository.  If needed, use the given
        callback to prompt whether the key should be imported.

        :param repo: repository object to retrieve the key of
        :param callback: callback function to use for asking for
           verification of key information
        """
        self._getAnyKeyForRepo(repo, repo.gpgcadir, repo.gpgcakey, is_cakey=True, callback=callback)

    def _limit_installonly_pkgs(self):
        """ Limit packages based on conf.installonly_limit, if any of the
            packages being installed have a provide in conf.installonlypkgs.
            New in 3.2.24: Obey yumdb_info.installonly data. """

        def _sort_and_filter_installonly(pkgs):
            """ Allow the admin to specify some overrides fo installonly pkgs.
                using the yumdb. """
            ret_beg = []
            ret_mid = []
            ret_end = []
            for pkg in sorted(pkgs):
                if 'installonly' not in pkg.yumdb_info:
                    ret_mid.append(pkg)
                    continue

                if pkg.yumdb_info.installonly == 'keep':
                    continue

                if True: # Don't to magic sorting, yet
                    ret_mid.append(pkg)
                    continue

                if pkg.yumdb_info.installonly == 'remove-first':
                    ret_beg.append(pkg)
                elif pkg.yumdb_info.installonly == 'remove-last':
                    ret_end.append(pkg)
                else:
                    ret_mid.append(pkg)

            return ret_beg + ret_mid + ret_end

        if self.conf.installonly_limit < 1 :
            return

        toremove = []
        #  We "probably" want to use either self.ts or self.rpmdb.ts if either
        # is available. However each ts takes a ref. on signals generally, and
        # SIGINT specifically, so we _must_ have got rid of all of the used tses
        # before we try downloading. This is called from buildTransaction()
        # so self.rpmdb.ts should be valid.
        ts = self.rpm.readonly_ts
        (cur_kernel_v, cur_kernel_r) = misc.get_running_kernel_version_release(ts)
        install_only_names = set(self.conf.installonlypkgs)
        for m in self.tsInfo.getMembers():
            if m.ts_state not in ('i', 'u'):
                continue
            if m.reinstall:
                continue

            po_names = set([m.name] + m.po.provides_names)
            if not po_names.intersection(install_only_names):
                continue

            installed = self.rpmdb.searchNevra(name=m.name)
            installed = _sort_and_filter_installonly(installed)
            if len(installed) < self.conf.installonly_limit - 1:
                continue # we're adding one

            numleft = len(installed) - self.conf.installonly_limit + 1
            for po in installed:
                if (po.version, po.release) == (cur_kernel_v, cur_kernel_r):
                    # don't remove running
                    continue
                if numleft == 0:
                    break
                toremove.append((po,m))
                numleft -= 1

        for po,rel in toremove:
            txmbr = self.tsInfo.addErase(po)
            # Add a dep relation to the new version of the package, causing this one to be erased
            # this way skipbroken, should clean out the old one, if the new one is skipped
            txmbr.depends_on.append(rel)

    def _downloadPackages(self,callback):
        ''' Download the need packages in the Transaction '''
        # This can be overloaded by a subclass.
        dlpkgs = map(lambda x: x.po, filter(lambda txmbr:
                                            txmbr.ts_state in ("i", "u"),
                                            self.tsInfo.getMembers()))
        # Check if there is something to do
        if len(dlpkgs) == 0:
            return None
        # make callback with packages to download
        callback.event(callbacks.PT_DOWNLOAD_PKGS,dlpkgs)
        try:
            probs = self.downloadPkgs(dlpkgs)

        except IndexError:
            raise Errors.YumBaseError, [_("Unable to find a suitable mirror.")]
        if len(probs) > 0:
            errstr = [_("Errors were encountered while downloading packages.")]
            for key in probs:
                errors = misc.unique(probs[key])
                for error in errors:
                    errstr.append("%s: %s" % (key, error))

            raise Errors.YumDownloadError, errstr
        return dlpkgs

    def _checkSignatures(self,pkgs,callback):
        ''' The the signatures of the downloaded packages '''
        # This can be overloaded by a subclass.
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)
            if result == 0:
                # Verified ok, or verify not req'd
                continue
            elif result == 1:
                self.getKeyForPackage(po, self._askForGPGKeyImport)
            else:
                raise Errors.YumGPGCheckError, errmsg

        return 0

    def _askForGPGKeyImport(self, po, userid, hexkeyid):
        '''
        Ask for GPGKeyImport
        This need to be overloaded in a subclass to make GPG Key import work
        '''
        return False

    def _run_rpm_check(self):
        results = []
        self.ts.check()
        for prob in self.ts.problems():
            #  Newer rpm (4.8.0+) has problem objects, older have just strings.
            #  Should probably move to using the new objects, when we can. For
            # now just be compatible.
            results.append(to_str(prob))

        return results

    def allowedMultipleInstalls(self, po):
        """Return whether the given package object can be installed
        multiple times with different versions.  For example, this
        would be true of kernels and kernel modules.

        :param po: the package object that this function will
           determine whether can be install multiple times
        :return: a boolean specifying whether *po* can be installed
           multiple times
        """
        iopkgs = set(self.conf.installonlypkgs)
        if po.name in iopkgs:
            return True
        return False # :hawkey

    def add_enable_repo(self, repoid, baseurls=[], mirrorlist=None, **kwargs):
        """Add and enable a repository.

        Never used in yum/:hawkey (only plugins).

        :param repoid: a string specifying the name of the repository
        :param baseurls: a list of strings specifying the urls for
           the repository.  At least one base url, or one mirror, must
           be given
        :param mirrorlist: a list of strings specifying a list of
           mirrors for the repository.  At least one base url, or one
           mirror must be given
        :param kwargs: key word arguments to set any normal repository
           attribute
        :return: the new repository that has been added and enabled
        """
        # out of place fixme - maybe we should make this the default repo addition
        # routine and use it from getReposFromConfigFile(), etc.
        newrepo = yumRepo.YumRepository(repoid)
        newrepo.name = repoid

        var_convert = kwargs.get('variable_convert', True)

        if baseurls:
            replaced = []
            if var_convert:
                for baseurl in baseurls:
                    if baseurl:
                        replaced.append(varReplace(baseurl, self.conf.yumvar))
            else:
                replaced = baseurls
            newrepo.baseurl = replaced

        if mirrorlist:
            if var_convert:
                mirrorlist = varReplace(mirrorlist, self.conf.yumvar)
            newrepo.mirrorlist = mirrorlist

        # setup the repo
        newrepo.setup(cache=self.conf.cache)

        # some reasonable defaults, (imo)
        newrepo.enablegroups = True
        newrepo.metadata_expire = 0
        newrepo.gpgcheck = self.conf.gpgcheck
        newrepo.repo_gpgcheck = self.conf.repo_gpgcheck
        newrepo.basecachedir = self.cache_c.cachedir
        newrepo.fallback_basecachedir = self.cache_c.fallback_cachedir
        newrepo.base_persistdir = self.conf._repos_persistdir

        for key in kwargs.keys():
            if not hasattr(newrepo, key): continue # skip the ones which aren't vars
            setattr(newrepo, key, kwargs[key])

        # add the new repo
        self.repos.add(newrepo)
        # enable the main repo
        self.repos.enableRepo(newrepo.id)
        return newrepo

    def populate_ts(self):
        """Populate the RPM transaction set. """
        if self.dsCallback:
            self.dsCallback.transactionPopulation()

        if self.ts.ts is None:
            self.initActionTs()

        for txmbr in self.tsInfo.getMembers():
            self.verbose_logger.log(logginglevels.DEBUG_3, _('Member: %s'), txmbr)
            if txmbr.ts_state in ['u', 'i']:
                rpmfile = txmbr.po.localPkg()
                if not os.path.exists(rpmfile):
                    raise RuntimeError("rpm file does not exist %s", rpmfile)
                hdr = dnf.rpmUtils.miscutils.headerFromFilename(rpmfile)

                if txmbr.ts_state == 'u':
                    if self.allowedMultipleInstalls(txmbr.po):
                        self.verbose_logger.log(logginglevels.DEBUG_2,
                            _('%s converted to install'), txmbr.po)
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

                self.ts.addInstall(hdr, txmbr, txmbr.ts_state)
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Adding Package %s in mode %s'), txmbr.po, txmbr.ts_state)
                if self.dsCallback:
                    dscb_ts_state = txmbr.ts_state
                    if dscb_ts_state == 'u' and txmbr.downgrades:
                        dscb_ts_state = 'd'
                    self.dsCallback.pkgAdded(txmbr.pkgtup, dscb_ts_state)

            elif txmbr.ts_state in ['e']:
                self.ts.addErase(txmbr.po.idx)
                if self.dsCallback:
                    if txmbr.downgraded_by:
                        continue
                    self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Removing Package %s'), txmbr.po)

    def _does_this_update(self, pkg1, pkg2):
        """returns True if pkg1 can update pkg2, False if not.
           This only checks if it can be an update it does not check if
           it is obsoleting or anything else."""

        if pkg1.name != pkg2.name:
            return False
        if pkg1.verLE(pkg2):
            return False
        if pkg1.arch not in self.arch.archlist:
            return False
        if dnf.rpmUtils.arch.canCoinstall(pkg1.arch, pkg2.arch):
            return False
        if self.allowedMultipleInstalls(pkg1):
            return False

        return True

    def _store_config_in_history(self):
        self.history.write_addon_data('config-main', self.conf.dump())
        myrepos = ''
        for repo in self.repos.listEnabled():
            myrepos += repo.dump()
            myrepos += '\n'
        self.history.write_addon_data('config-repos', myrepos)

    def verify_plugins_cb(self, verify_package):
        """Callback to call a plugin hook for pkg.verify().

        :param verify_package: a conduit for the callback
        :return: *verify_package*
        """
        self.plugins.run('verify_package', verify_package=verify_package)
        return verify_package
