# Copyright 2005 Duke University
# Copyright (C) 2012-2013  Red Hat, Inc.
#
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

"""
Supplies the Base class.
"""

from __future__ import absolute_import
from __future__ import print_function
from dnf import const, query, sack
from dnf.pycomp import unicode, basestring
from dnf.yum import config
from dnf.yum import history
from dnf.yum import i18n
from dnf.yum import misc
from dnf.yum import plugins
from dnf.yum import rpmsack
from dnf.yum.config import ParsingError, ConfigParser
from dnf.yum.constants import *
from dnf.yum.i18n import to_unicode, to_str, exception2msg
from dnf.yum.parser import ConfigPreProcessor
from functools import reduce, cmp_to_key

import io
import dnf.comps
import dnf.conf
import dnf.exceptions
import dnf.history
import dnf.lock
import dnf.logging
import dnf.output
import dnf.persistor
import dnf.repo
import dnf.repodict
import dnf.rpmUtils.arch
import dnf.rpmUtils.connection
import dnf.rpmUtils.transaction
import dnf.subject
import dnf.transaction
import dnf.util
import dnf.yum.rpmtrans
import errno
import functools
import glob
import hawkey
import logging
import os
import operator
import rpm
import signal
import time
import types
import string
import librepo

_ = i18n._
P_ = i18n.P_

class Base(object):
    def __init__(self):
        # :api
        self._closed = False
        self._conf = config.YumConf()
        self._conf.uid = 0
        self._goal = None
        self._persistor = None
        self._sack = None
        self._transaction = None
        self._ts = None
        self._comps = None
        self._history = None
        self._tags = None
        self._ts_save_file = None
        self._tempfiles = []
        self.ds_callback = dnf.output.DepsolveCallback()
        self.logger = logging.getLogger("dnf")
        self.logging = dnf.logging.Logging()
        self._repos = dnf.repodict.RepoDict()
        self.repo_setopts = {} # since we have to use repo_setopts in base and
                               # not in cli - set it up as empty so no one
                               # trips over it later

        # Start with plugins disabled
        self.disablePlugins()
        self.rpm_probfilter = [rpm.RPMPROB_FILTER_OLDPACKAGE,
                               rpm.RPMPROB_FILTER_REPLACEPKG,
                               rpm.RPMPROB_FILTER_REPLACEOLDFILES]

        self.mediagrabber = None
        self.arch = dnf.rpmUtils.arch.Arch()

        self.run_with_package_names = set()
        self.goal_parameters = dnf.conf.GoalParameters()

        self._conf.yumvar['arch'] = self.arch.canonarch
        self._conf.yumvar['basearch'] = self.arch.basearch
        self._conf.yumvar_update_from_env()

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_args):
        self.close()

    def _add_repo_to_sack(self, name):
        hrepo = hawkey.Repo(name)
        repo = self.repos[name]
        try:
            repo.load()
        except dnf.exceptions.RepoError as e:
            if repo.skip_if_unavailable is False:
                raise
            msg = _("%s, disabling.") % str(e)
            self.logger.warning(msg)
            repo.disable()
            return
        hrepo.repomd_fn = repo.repomd_fn
        hrepo.primary_fn = repo.primary_fn
        hrepo.filelists_fn = repo.filelists_fn
        hrepo.cost = repo.cost
        if repo.presto_fn:
            hrepo.presto_fn = repo.presto_fn
        else:
            self.logger.debug("not found deltainfo for: %s" % repo.name)
        repo.hawkey_repo = hrepo
        self._sack.load_yum_repo(hrepo, build_cache=True, load_filelists=True)

    def _setup_excludes(self):
        disabled = set(self.conf.disable_excludes)
        if 'all' in disabled:
            return
        if 'main' not in disabled:
            for excl in self.conf.exclude:
                pkgs = self.sack.query().filter_autoglob(name=excl)
                self.sack.add_excludes(pkgs)
        for r in self.repos.iter_enabled():
            if r.id in disabled:
                continue
            for excl in r.exclude:
                pkgs = self.sack.query().filter(reponame=r.id).\
                    filter_autoglob(name=excl)
                self.sack.add_excludes(pkgs)

    def _store_persistent_data(self):
        def check_expired(repo):
            try:
                return repo.metadata_expire_in()[1] <= 0
            except dnf.exceptions.MetadataError:
                return False

        expired = [r.id for r in self.repos.iter_enabled() if check_expired(r)]
        self._persistor.set_expired_repos(expired)

    @property
    def comps(self):
        # :api
        return self._comps

    @property
    def conf(self):
        # :api
        return self._conf

    @property
    def repos(self):
        return self._repos

    @repos.deleter
    def repos(self):
        self._repos = None

    @property
    @dnf.util.lazyattr("_rpmconn")
    def rpmconn(self):
        return dnf.rpmUtils.connection.RpmConnection(self.conf.installroot)

    @property
    def sack(self):
        # :api
        return self._sack

    @property
    def transaction(self):
        return self._transaction

    def activate_persistor(self):
        self._persistor = dnf.persistor.Persistor(self.conf.cachedir)

    def fill_sack(self, load_system_repo=True, load_available_repos=True):
        """Prepare the Sack and the Goal objects. :api."""
        start = time.time()
        self._sack = sack.build_sack(self)
        with dnf.lock.metadata_cache_lock:
            if load_system_repo is not False:
                try:
                    self._sack.load_system_repo(build_cache=True)
                except IOError:
                    if load_system_repo != 'auto':
                        raise
            if load_available_repos:
                for r in self.repos.iter_enabled():
                    self._add_repo_to_sack(r.id)
        conf = self.conf
        self._sack.configure(conf.installonlypkgs, conf.installonly_limit)
        self.logger.debug('hawkey sack setup time: %0.3f' %
                                  (time.time() - start))
        self._setup_excludes()
        self._goal = hawkey.Goal(self._sack)
        return self._sack

    @property
    @dnf.util.lazyattr("_yumdb")
    def yumdb(self):
        db_path = os.path.normpath(self.conf.persistdir + '/yumdb')
        return rpmsack.AdditionalPkgDB(db_path)

    def close(self):
        """Close the history and repo objects."""

        if self._closed:
            return
        self._closed = True
        # Do not trigger the lazy creation:
        if self._history is not None:
            self.history.close()
        if self._persistor:
            self._store_persistent_data()
        self.closeRpmDB()

    def read_conf_file(self, path=None, root="/", releasever=None,
                       overrides=None):
        conf_st = time.time()
        path = path or const.CONF_FILENAME
        startupconf = config.readStartupConfig(path, root)
        # replace the yumvar
        startupconf.yumvar = self._conf.yumvar
        startupconf.releasever = releasever
        startupconf.yumvar_update_from_etc()

        self._conf = config.readMainConfig(startupconf)
        if overrides is not None:
            self._conf.override(overrides)

        self.logging.setup_from_dnf_conf(self.conf)
        for pkgname in self.conf.history_record_packages:
            self.run_with_package_names.add(pkgname)
        self._conf.uid = os.geteuid()

        # repos are ver/arch specific so add $basearch/$releasever
        yumvar = self._conf.yumvar
        self._conf._repos_persistdir = os.path.normpath(
            '%s/repos/%s/%s/' % (self._conf.persistdir,
                                 yumvar.get('basearch', '$basearch'),
                                 yumvar.get('releasever', '$releasever')))
        self.logger.debug('Config time: %0.3f' % (time.time() - conf_st))
        return self._conf

    def read_repos(self, repofn, repo_age=None):
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
        except ParsingError as e:
            msg = str(e)
            raise dnf.exceptions.ConfigError(msg)

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
            except (dnf.exceptions.RepoError, dnf.exceptions.ConfigError) as e:
                self.logger.warning(e)
                continue
            else:
                thisrepo.repo_config_age = repo_age
                thisrepo.repofile = repofn

            if thisrepo.id in self.repo_setopts:
                for opt in self.repo_setopts[thisrepo.id].items:
                    if not hasattr(thisrepo, opt):
                        msg = "Repo %s did not have a %s attr. before setopt"
                        self.logger.warning(msg % (thisrepo.id, opt))
                    setattr(thisrepo, opt, getattr(self.repo_setopts[thisrepo.id], opt))

            # Got our list of repo objects, add them to the repos
            # collection
            try:
                self.repos.add(thisrepo)
            except dnf.exceptions.ConfigError as e:
                self.logger.warning(e)

    def read_all_repos(self):
        """Read in repositories from the main yum conf file, and from
        .repo files.  The location of the main yum conf file is given
        by self.conf.config_file_path, and the location of the
        directory of .repo files is given by self.conf.reposdir.
        """
        # Read .repo files from directories specified by the reposdir option
        # (typically /etc/yum/repos.d)
        repo_config_age = self.conf.config_file_age

        # Get the repos from the main yum.conf file
        self.read_repos(self.conf.config_file_path, repo_config_age)

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
                    self.read_repos(repofn, repo_age=thisrepo_age)

    def readRepoConfig(self, parser, section):
        """Parse an INI file section for a repository.

        :param parser: :class:`ConfigParser` or similar object to read
           INI file values from
        :param section: INI file section to read
        :return: :class:`dnf.repo.Repo` instance
        """
        repo = dnf.repo.Repo(section, self.conf.cachedir)
        try:
            repo.populate(parser, section, self.conf)
        except ValueError as e:
            msg = _('Repository %r: Error parsing config: %s' % (section,e))
            raise dnf.exceptions.ConfigError(msg)

        # Ensure that the repo name is set
        if not repo.name:
            repo.name = section
            self.logger.error(_('Repository %r is missing name in configuration, '
                    'using id') % section)
        repo.name = to_unicode(repo.name)

        repo.yumvar.update(self.conf.yumvar)
        repo.cfg = parser

        return repo

    def reset(self, sack=False, repos=False, goal=False):
        """Make the Base object forget about various things."""
        if sack:
            self._sack = None
        if repos:
            self._repos = dnf.repodict.RepoDict()
        if goal:
            self._goal = None
            if self._sack is not None:
                self._goal = hawkey.Goal(self._sack)

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
        del self.ts
        self._comps = None

    _TS_FLAGS_TO_RPM = {'noscripts': rpm.RPMTRANS_FLAG_NOSCRIPTS,
                        'notriggers': rpm.RPMTRANS_FLAG_NOTRIGGERS,
                        'nodocs': rpm.RPMTRANS_FLAG_NODOCS,
                        'test': rpm.RPMTRANS_FLAG_TEST,
                        'justdb': rpm.RPMTRANS_FLAG_JUSTDB,
                        'nocontexts': rpm.RPMTRANS_FLAG_NOCONTEXTS,
                        'nocrypto' : rpm.RPMTRANS_FLAG_NOFILEDIGEST}
    _TS_VSFLAGS_TO_RPM = {'nocrypto' : rpm._RPMVSF_NOSIGNATURES |
                          rpm._RPMVSF_NODIGESTS }

    @property
    def ts(self):
        """Set up the RPM transaction set that will be used for all the work."""
        if self._ts is not None:
            return self._ts
        self._ts = dnf.rpmUtils.transaction.TransactionWrapper(
            self.conf.installroot)
        self._ts.setFlags(0) # reset everything.
        for flag in self.conf.tsflags:
            rpm_flag = self._TS_FLAGS_TO_RPM.get(flag)
            if rpm_flag is None:
                self.logger.critical(_('Invalid tsflag in config file: %s'), flag)
                continue
            self._ts.addTsFlag(rpm_flag)
            vs_flag = self._TS_VSFLAGS_TO_RPM.get(flag)
            if vs_flag is not None:
                self._ts.pushVSFlags(vs_flag)

        probfilter = reduce(operator.or_, self.rpm_probfilter, 0)
        self._ts.setProbFilter(probfilter)
        return self._ts

    @ts.deleter
    def ts(self):
        """Releases the RPM transaction set. """
        if self._ts is None:
            return
        self._ts.close()
        del self._ts
        self._ts = None

    def read_comps(self):
        """Create the groups object to access the comps metadata. :api"""
        group_st = time.time()
        self.logger.log(dnf.logging.SUBDEBUG, 'Getting group metadata')
        self._comps = dnf.comps.Comps()

        for repo in self.repos.iter_enabled():
            if not repo.enablegroups:
                continue
            comps_fn = repo.metadata.comps_fn
            if comps_fn is None:
                continue

            self.logger.log(dnf.logging.SUBDEBUG,
                            'Adding group file from repository: %s', repo.id)
            decompressed = misc.repo_gen_decompress(comps_fn, 'groups.xml')

            try:
                self._comps.add_from_xml_filename(decompressed)
            except dnf.exceptions.CompsError as e:
                msg = _('Failed to add groups file for repository: %s - %s')
                self.logger.critical(msg % (repo.id, str(e)))

        if len(self._comps) == 0:
            msg = _('No Groups Available in any repository')
            raise dnf.exceptions.CompsError(msg)

        self._comps.compile(self.sack.query().installed())
        self.logger.debug('group time: %0.3f' % (time.time() - group_st))
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

    history = property(fget=lambda self: self._getHistory(),
                       fset=lambda self, value: setattr(self, "_history",value),
                       fdel=lambda self: setattr(self, "_history", None),
                       doc="Yum History Object")

    def _goal2transaction(self, goal):
        ts = dnf.transaction.Transaction()
        all_obsoleted = set(goal.list_obsoleted())

        for pkg in goal.list_downgrades():
            obs = goal.obsoleted_by_package(pkg)
            downgraded = obs[0]
            self.ds_callback.pkg_added(downgraded, 'dd')
            self.ds_callback.pkg_added(pkg, 'd')
            ts.add_downgrade(pkg, downgraded, obs[1:])
        for pkg in goal.list_reinstalls():
            self.ds_callback.pkg_added(pkg, 'r')
            obs = goal.obsoleted_by_package(pkg)
            reinstalled = obs[0]
            ts.add_reinstall(pkg, reinstalled, obs[1:])
        for pkg in goal.list_installs():
            self.ds_callback.pkg_added(pkg, 'i')
            obs = goal.obsoleted_by_package(pkg)
            reason = dnf.util.reason_name(goal.get_reason(pkg))
            ts.add_install(pkg, obs, reason)
            cb = lambda pkg: self.ds_callback.pkg_added(pkg, 'od')
            dnf.util.mapall(cb, obs)
        for pkg in goal.list_upgrades():
            group_fn = functools.partial(operator.contains, all_obsoleted)
            obs, upgraded = dnf.util.group_by_filter(
                group_fn, goal.obsoleted_by_package(pkg))
            cb = lambda pkg: self.ds_callback.pkg_added(pkg, 'od')
            dnf.util.mapall(cb, obs)
            if pkg.name in self.conf.installonlypkgs:
                ts.add_install(pkg, obs)
            else:
                ts.add_upgrade(pkg, upgraded[0], obs)
                cb = lambda pkg: self.ds_callback.pkg_added(pkg, 'ud')
                dnf.util.mapall(cb, upgraded)
            self.ds_callback.pkg_added(pkg, 'u')
        for pkg in goal.list_erasures():
            self.ds_callback.pkg_added(pkg, 'e')
            ts.add_erase(pkg)
        return ts

    def _query_matches_installed(self, q):
        """ See what packages in the query match packages (also in older
            versions, but always same architecture) that are already installed.

            Unlike in case of _sltr_matches_installed(), it is practical here to
            know even the packages in the original query that can still be
            installed.
        """
        inst = q.installed()
        inst_per_arch = query.per_arch_dict(inst)
        avail = q.latest().available()
        avail_per_arch = query.per_arch_dict(avail)
        avail_l = []
        inst_l = []
        for na in avail_per_arch:
            if na in inst_per_arch:
                inst_l.append(inst_per_arch[na][0])
            else:
                avail_l.extend(avail_per_arch[na])
        return inst_l, avail_l

    def _sltr_matches_installed(self, sltr):
        """ See if sltr matches a patches that is (in older version or different
            architecture perhaps) already installed.
        """
        inst = self.sack.query().installed()
        inst = inst.filter(pkg=sltr.matches())
        return list(inst)

    def _push_userinstalled(self, goal):
        msg =  _('--> Finding unneeded leftover dependencies')
        self.logger.info(msg)
        for pkg in self.sack.query().installed().run():
            yumdb_info = self.yumdb.get_package(pkg)
            reason = 'user'
            try:
                reason = yumdb_info.reason
            except AttributeError:
                pass
            if reason == 'user':
                goal.userinstalled(pkg)

    def run_hawkey_goal(self, goal):
        allow_uninstall = self.goal_parameters.allow_uninstall
        ret = goal.run(allow_uninstall=allow_uninstall,
                       force_best=self.conf.best)
        if self.conf.debug_solver:
            goal.write_debugdata()
        return ret

    def resolve(self):
        """Build the transaction set."""
        self.plugins.run('preresolve')
        exc = None

        ds_st = time.time()
        self.ds_callback.start()
        goal = self._goal
        if goal.req_has_erase():
            self._push_userinstalled(goal)
        if not self.run_hawkey_goal(goal):
            if self.conf.debuglevel >= 6:
                goal.log_decisions()
            exc = dnf.exceptions.DepsolveError('. '.join(goal.problems))
        else:
            self._transaction = self._goal2transaction(goal)

        self.ds_callback.end()
        self.logger.debug('Depsolve time: %0.3f' % (time.time() - ds_st))

        got_transaction = self._transaction is not None and \
                          len(self._transaction) > 0
        if got_transaction:
            msg = self._transaction.rpm_limitations()
            if msg:
                exc = dnf.exceptions.Error(msg)

        self.plugins.run('postresolve', exception=exc,
                         got_transaction=got_transaction)
        if exc is not None:
            raise exc
        return got_transaction

    def do_transaction(self, display=None):
        # :api
        # save our ds_callback out
        dscb = self.ds_callback
        self.ds_callback = None
        self.transaction.populate_rpm_ts(self.ts)

        rcd_st = time.time()
        self.logger.info(_('Running transaction check'))
        msgs = self._run_rpm_check()
        if msgs:
            rpmlib_only = True
            for msg in msgs:
                if msg.startswith('rpmlib('):
                    continue
                rpmlib_only = False
            if rpmlib_only:
                print(_("ERROR You need to upgrade rpm to handle:"))
            else:
                print(_('ERROR with transaction check vs depsolve:'))

            for msg in msgs:
                print(i18n.to_utf8(msg))

            if rpmlib_only:
                return 1, [_('RPM needs to be upgraded')]
            raise dnf.exceptions.TransactionCheckError(
                'transaction not consistent with package database')

        self.logger.info(_('Transaction check succeeded.'))
        self.logger.debug('Transaction check time: %0.3f' %
                          (time.time() - rcd_st))

        tt_st = time.time()
        self.logger.info(_('Running transaction test'))
        if not self.conf.diskspacecheck:
            self.rpm_probfilter.append(rpm.RPMPROB_FILTER_DISKSPACE)

        self.ts.order() # order the transaction
        self.ts.clean() # release memory not needed beyond this point

        testcb = dnf.yum.rpmtrans.RPMTransaction(self, test=True)
        tserrors = self.ts.test(testcb)
        del testcb

        if len(tserrors) > 0:
            errstring = _('Transaction check error:\n')
            for descr in tserrors:
                errstring += '  %s\n' % to_unicode(descr)

            raise dnf.exceptions.Error(errstring + '\n' + \
                 self.errorSummary(errstring))

        self.logger.info(_('Transaction test succeeded.'))
        self.logger.debug('Transaction test time: %0.3f' % (time.time() - tt_st))

        # unset the sigquit handler
        sigquit = signal.signal(signal.SIGQUIT, signal.SIG_DFL)
        ts_st = time.time()

        # put back our depcheck callback
        self.ds_callback = dscb
        # setup our rpm ts callback
        if display is None:
            cb = dnf.yum.rpmtrans.RPMTransaction(self)
        else:
            cb = dnf.yum.rpmtrans.RPMTransaction(self, display=display)
        if self.conf.debuglevel < 2:
            cb.display.output = False

        self.logger.info(_('Running transaction'))
        return_code = self.runTransaction(cb=cb)

        self.logger.debug('Transaction time: %0.3f' % (time.time() - ts_st))
        # put back the sigquit handler
        signal.signal(signal.SIGQUIT, sigquit)

        return return_code, None

    def _record_history(self):
        return self.conf.history_record and \
            not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)

    @dnf.lock.rpmdb_lock.decorator
    def runTransaction(self, cb):
        """Perform the transaction.

        :param cb: an rpm callback object to use in the transaction
        :return: a :class:`misc.GenericHolder` containing
           information about the results of the transaction
        :raises: :class:`dnf.exceptions.YumRPMTransError` if there is a
           transaction cannot be completed
        """
        self.plugins.run('pretrans')

        if self._record_history():
            using_pkgs_pats = list(self.run_with_package_names)
            installed_query = self.sack.query().installed()
            using_pkgs = installed_query.filter(name=using_pkgs_pats).run()
            rpmdbv  = self.sack.rpmdb_version(self.yumdb)
            lastdbv = self.history.last()
            if lastdbv is not None:
                lastdbv = lastdbv.end_rpmdbversion

            if lastdbv is None or rpmdbv != lastdbv:
                self.logger.debug("RPMDB altered outside of DNF.")

            cmdline = None
            if hasattr(self, 'args') and self.args:
                cmdline = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                cmdline = ' '.join(self.cmds)

            self.history.beg(rpmdbv, using_pkgs, list(self.transaction),
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
            except (IOError, OSError) as e:
                pass
        self._ts_save_file = None

        if self.conf.reset_nice:
            onice = os.nice(0)
            if onice:
                try:
                    os.nice(-onice)
                except:
                    onice = 0

        self.logger.debug('runTransaction: rpm transaction start.')
        errors = self.ts.run(cb.callback, '')
        self.logger.debug('runTransaction: rpm transaction over.')
        # ts.run() exit codes are, hmm, "creative": None means all ok, empty
        # list means some errors happened in the transaction and non-empty
        # list that there were errors preventing the ts from starting...
        if self.conf.reset_nice:
            try:
                os.nice(onice)
            except:
                pass

        return_code = 0
        if errors is None:
            pass
        elif len(errors) == 0:
            # this is a particularly tricky case happening also when rpm failed
            # to obtain the transaction lock. We can only try to see if a
            # particular element failed and if not, decide that is the
            # case.
            if len([el for el in self.ts if el.Failed()]) > 0:
                errstring = _('Warning: scriptlet or other non-fatal errors occurred during transaction.')
                self.logger.debug(errstring)
                return_code = 1
            else:
                self.logger.critical(_("Transaction couldn't start (no root?)"))
                raise dnf.exceptions.YumRPMTransError(msg=_("Could not run transaction."),
                                              errors=[])
        else:
            if self._record_history():
                herrors = [to_unicode(to_str(x)) for x in errors]
                self.plugins.run('historyend')
                self.history.end(rpmdbv, 2, errors=herrors)


            self.logger.critical(_("Transaction couldn't start:"))
            for e in errors:
                self.logger.critical(e[0]) # should this be 'to_unicoded'?
            raise dnf.exceptions.YumRPMTransError(msg=_("Could not run transaction."),
                                          errors=errors)

        for i in ('ts_all_fn', 'ts_done_fn'):
            if hasattr(cb, i):
                fn = getattr(cb, i)
                try:
                    misc.unlink_f(fn)
                except (IOError, OSError) as e:
                    self.logger.critical(_('Failed to remove transaction file %s') % fn)


        self.plugins.run('posttrans')
        # sync up what just happened versus what is in the rpmdb
        if not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST):
            self.verify_transaction(return_code, cb.verify_tsi_package)

        if (not self.conf.keepcache and
            not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)):
            self.clean_used_packages()

        return return_code

    def verify_transaction(self, return_code, verify_pkg_cb=None):
        """Check that the transaction did what was expected, and
        propagate external yumdb information.  Output error messages
        if the transaction did not do what was expected.

        :param resultobject: the :class:`misc.GenericHolder`
           object returned from the :func:`runTransaction` call that
           ran the transaction
        :param txmbr_cb: the callback for the rpm transaction members
        """
        # check to see that the rpmdb and the transaction roughly matches
        # push package object metadata outside of rpmdb into yumdb
        # delete old yumdb metadata entries

        # for each pkg in the transaction
        # if it is an install - see that the pkg is installed
        # if it is a remove - see that the pkg is no longer installed, provided
        #    that there is not also an install of this pkg in the transaction
        #    (reinstall)
        # for any kind of install add from_repo to the yumdb, and the cmdline
        # and the install reason

        total = self.transaction.total_package_count()
        def display_banner(pkg, count):
            count += 1
            if verify_pkg_cb is not None:
                verify_pkg_cb(pkg, count, total)
            return count

        vt_st = time.time()
        self.plugins.run('preverifytrans')
        count = 0
        # the rpmdb has changed by now. hawkey doesn't support dropping a repo
        # yet we have to check what packages are in now: build a transient sack
        # with only rpmdb in it. In the future when RPM Python bindings can tell
        # us if a particular transaction element failed or not we can skip this
        # completely.
        rpmdb_sack = sack.rpmdb_sack(self)

        for tsi in self._transaction:
            rpo = tsi.installed
            if rpo is None:
                continue

            installed = rpmdb_sack.query().installed().nevra(
                rpo.name, rpo.evr, rpo.arch)
            if len(installed) < 1:
                self.logger.critical(_('%s was supposed to be installed' \
                                           ' but is not!' % rpo))
                count = display_banner(rpo, count)
                continue
            po = installed[0]
            count = display_banner(rpo, count)
            yumdb_info = self.yumdb.get_package(po)
            yumdb_info.from_repo = rpo.repoid

            yumdb_info.reason = tsi.propagated_reason(self.yumdb)
            yumdb_info.releasever = self.conf.yumvar['releasever']
            if hasattr(self, 'args') and self.args:
                yumdb_info.command_line = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                yumdb_info.command_line = ' '.join(self.cmds)
            csum = rpo.returnIdSum()
            if csum is not None:
                yumdb_info.checksum_type = str(csum[0])
                yumdb_info.checksum_data = csum[1]

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
            if tsi.op_type in (dnf.transaction.DOWNGRADE,
                               dnf.transaction.REINSTALL,
                               dnf.transaction.UPGRADE):
                opo = tsi.erased
                opo_yumdb_info = self.yumdb.get_package(opo)
                if 'installed_by' in opo_yumdb_info:
                    yumdb_info.installed_by = opo_yumdb_info.installed_by
                if loginuid is not None:
                    yumdb_info.changed_by = str(loginuid)
            elif loginuid is not None:
                yumdb_info.installed_by = str(loginuid)

            if self.conf.history_record:
                self.history.sync_alldb(po)

        just_installed = self.sack.query().\
            filter(pkg=self.transaction.install_set)
        for rpo in self.transaction.remove_set:
            installed = rpmdb_sack.query().installed().nevra(
                rpo.name, rpo.evr, rpo.arch)
            if len(installed) > 0:
                if not len(just_installed.filter(arch=rpo.arch, name=rpo.name,
                                                 evr=rpo.evr)):
                    msg = _('%s was supposed to be removed but is not!')
                    self.logger.critical(msg % rpo)
                    count = display_banner(rpo, count)
                    continue
            count = display_banner(rpo, count)
            yumdb_item = self.yumdb.get_package(po=rpo)
            yumdb_item.clean()

        self.plugins.run('postverifytrans')
        if self._record_history():
            rpmdbv = rpmdb_sack.rpmdb_version(self.yumdb)
            self.plugins.run('historyend')
            self.history.end(rpmdbv, return_code)
        self.logger.debug('VerifyTransaction time: %0.3f' % (time.time() - vt_st))

    def download_packages(self, pkglist, progress=None, callback_total=None):
        """Download the packages specified by the given list of packages. :api

        :param pkglist: a list of package objects specifying the
           packages to download
        :param callback_total: a callback to output messages about the
           download operation
        :return: a dictionary containing errors from the downloading process

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
           callback, raise dnf.exceptions.Error on problems"""

        self.plugins.run('predownload', pkglist=pkglist)

        # select and sort packages to download
        remote_pkgs = list(filter(lambda po: not (po.from_cmdline or po.repo.local), pkglist))
        remote_pkgs.sort(key=cmp_to_key(mediasort))
        remote_size = sum(po.size for po in remote_pkgs)

        # run downloads
        beg_download = time.time()
        if progress:
            progress.start(len(remote_pkgs), remote_size)
        targets = [po.repo.get_package_target(po, progress) for po in remote_pkgs]
        try:
            librepo.download_packages(targets, failfast=True)
        except librepo.LibrepoException:
            pass # .err of the failed target is set already
        errors = dict((t.po, [t.err]) for t in targets
                      if t.err not in (None, 'Already downloaded'))

        if callback_total is not None and not errors:
            callback_total(remote_pkgs, remote_size, beg_download)
        self.plugins.run('postdownload', pkglist=pkglist, errors=errors)
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
        if po.from_cmdline:
            check = self.conf.localpkg_gpgcheck
            hasgpgkey = 0
        else:
            repo = self.repos[po.repoid]
            check = repo.gpgcheck
            hasgpgkey = not not repo.gpgkey

        if check:
            ts = self.rpmconn.readonly_ts
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

    def clean_used_packages(self):
        """Delete the header and package files used in the
        transaction from the yum cache.
        """
        filelist = self._tempfiles
        for pkg in self.transaction.install_set:
            if pkg is None:
                continue
            if pkg.from_system or pkg.from_cmdline:
                continue

            # make sure it's not a local file
            repo = self.repos[pkg.repoid]
            for u in repo.baseurl:
                if u.startswith("file:"):
                    break
            else:
                filelist.append(pkg.localPkg())

        # now remove them
        for fn in filelist:
            if not os.path.exists(fn):
                continue
            try:
                misc.unlink_f(fn)
            except OSError as e:
                self.logger.warning(_('Cannot remove %s'), fn)
                continue
            else:
                self.logger.log(dnf.logging.SUBDEBUG,
                    _('%s removed'), fn)

    def cleanPackages(self):
        """Delete the package files from the yum cache."""

        exts = ['rpm']
        return self._cleanFiles(exts, 'pkgdir', 'package')

    def clean_binary_cache(self):
        """ Delete the binary cache files from the DNF cache.

            IOW, clean up the .solv and .solvx hawkey cache files.
        """
        files = [os.path.join(self.conf.cachedir,
                              hawkey.SYSTEM_REPO_NAME + ".solv")]
        for repo in self.repos.iter_enabled():
            basename = os.path.join(self.conf.cachedir, repo.id)
            files.append(basename + ".solv")
            files.append(basename + "-filenames.solvx")
        files = [f for f in files if os.access(f, os.F_OK)]

        return self._cleanFilelist('dbcache', files)

    def cleanMetadata(self):
        """Delete the metadata files from the yum cache."""

        exts = ['xml.gz', 'xml', 'cachecookie', 'mirrorlist', 'asc',
                'xml.bz2', 'xml.xz']
        # Metalink is also here, but is a *.xml file
        return self._cleanFiles(exts, 'cachedir', 'metadata')

    def cleanExpireCache(self):
        """Delete the local data saying when the metadata and mirror
           lists were downloaded for each repository."""

        for repo in self.repos.iter_enabled():
            repo.md_expire_cache()
        return 0, [_('The enabled repos were expired')]

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
            for repo in self.repos.iter_enabled():
                path = getattr(repo, pathattr)
                if os.path.exists(path) and os.path.isdir(path):
                    filelist = misc.getFileList(path, ext, filelist)
        return self._cleanFilelist(filetype, filelist)

    def _cleanFilelist(self, filetype, filelist):
        removed = 0
        for item in filelist:
            try:
                misc.unlink_f(item)
            except OSError as e:
                self.logger.critical(_('Cannot remove %s file %s'), filetype, item)
                continue
            else:
                self.logger.log(dnf.logging.SUBDEBUG,
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
             upgrades = tuples of packageObjects (updating, installed)
             extras = list of packageObjects
             obsoletes = tuples of packageObjects (obsoleting, installed)
             recent = list of packageObjects
        """
        if showdups is None:
            showdups = self.conf.showdupesfromrepos
        if patterns is None:
            return self._list_pattern(pkgnarrow, patterns, showdups, ignore_case)

        assert(not dnf.util.is_string_type(patterns))
        list_fn = functools.partial(self._list_pattern, pkgnarrow,
                                    showdups=showdups, ignore_case=ignore_case)
        if patterns is None or len(patterns) == 0:
            return list_fn(None)
        yghs = map(list_fn, patterns)
        return reduce(lambda a, b: a.merge_lists(b), yghs)

    def _list_pattern(self, pkgnarrow, pattern, showdups, ignore_case):
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

        # do the initial pre-selection
        ic = ignore_case
        q = self.sack.query()
        if pattern is not None:
            subj = dnf.subject.Subject(pattern, ignore_case=ic)
            q = subj.get_best_query(self.sack, with_provides=False)

        # list all packages - those installed and available:
        if pkgnarrow == 'all':
            dinst = {}
            ndinst = {} # Newest versions by name.arch
            for po in q.installed():
                dinst[po.pkgtup] = po
                if showdups:
                    continue
                key = (po.name, po.arch)
                if key not in ndinst or po > ndinst[key]:
                    ndinst[key] = po
            installed = list(dinst.values())

            avail = q
            if not showdups:
                avail = q.latest()
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
        elif pkgnarrow == 'upgrades':
            updates = q.upgrades().run()

        # installed only
        elif pkgnarrow == 'installed':
            installed = q.installed().run()

        # available in a repository
        elif pkgnarrow == 'available':
            if showdups:
                avail = q.available()
                installed_dict = q.installed().na_dict()
                for avail_pkg in avail:
                    key = (avail_pkg.name, avail_pkg.arch)
                    installed_pkgs = installed_dict.get(key, [])
                    same_ver = [pkg for pkg in installed_pkgs if pkg.evr == avail_pkg.evr]
                    if len(same_ver) > 0:
                        reinstall_available.append(avail_pkg)
                    else:
                        available.append(avail_pkg)
            else:
                # we will only look at the latest versions of packages:
                available_dict = q.available().latest().na_dict()
                installed_dict = q.installed().latest().na_dict()
                for (name, arch) in available_dict:
                    avail_pkg = available_dict[(name, arch)][0]
                    inst_pkg = installed_dict.get((name, arch), [None])[0]
                    if not inst_pkg or avail_pkg.evr_gt(inst_pkg):
                        available.append(avail_pkg)
                    elif avail_pkg.evr_eq(inst_pkg):
                        reinstall_available.append(avail_pkg)
                    else:
                        old_available.append(avail_pkg)

        # not in a repo but installed
        elif pkgnarrow == 'extras':
            # anything installed but not in a repo is an extra
            avail_dict = q.available().pkgtup_dict()
            inst_dict = q.installed().pkgtup_dict()
            for pkgtup in inst_dict:
                if pkgtup not in avail_dict:
                    extras.extend(inst_dict[pkgtup])

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            self.conf.obsoletes = 1
            inst = q.installed()
            obsoletes = self.sack.query().filter(obsoletes=inst)
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
                avail = q.available()
            else:
                avail = q.latest()

            for po in avail:
                if int(po.buildtime) > recentlimit:
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
        if dnf.util.is_glob_pattern(needle):
            fdict = {'%s__glob' % attr : needle}
        q = self.sack.query().filter(hawkey.ICASE, **fdict)
        for pkg in q.run():
            counter.add(pkg, attr, needle)
        return counter

    def _assert_comps(self):
        msg = _('No group data available for configured repositories.')
        if not len(self.comps):
            raise dnf.exceptions.CompsError(msg)

    def _environment_list(self, patterns):
        self._assert_comps()

        if patterns is None:
            envs = self.comps.environments
        else:
            envs = self.comps.environments_by_pattern(",".join(patterns))
        return sorted(envs)

    def _group_lists(self, uservisible, patterns):
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

        self._assert_comps()

        if patterns is None:
            grps = self.comps.groups
        else:
            grps = self.comps.groups_by_pattern(",".join(patterns))
        for grp in grps:
            tgt_list = available
            if grp.installed:
                tgt_list = installed
            if not uservisible or grp.uservisible:
                tgt_list.append(grp)

        return sorted(installed), sorted(available)

    def group_remove(self, grp_spec):
        groups = self.comps.groups_by_pattern(grp_spec)
        if not groups:
            raise dnf.exceptions.CompsError(_("No Group named %s exists") % to_unicode(grpid))

        cnt = 0
        for pkg in (pkg for grp in groups for pkg in grp.packages):
            try:
                self.remove(pkg.name)
            except dnf.exceptions.PackagesNotInstalledError:
                continue
            cnt += 1

        return cnt

    def groupUnremove(self, grpid):
        """Unmark any packages in the given group from being removed.

        :param grpid: the name of the group to unmark the packages of
        """
        thesegroups = self.comps.groups_by_pattern(grpid)
        if not thesegroups:
            raise dnf.exceptions.CompsError(_("No Group named %s exists") % to_unicode(grpid))

        for thisgroup in thesegroups:
            thisgroup.toremove = False
            pkgs = thisgroup.packages
            for pkg in thisgroup.packages:
                for txmbr in self.tsInfo:
                    if txmbr.po.name == pkg and txmbr.po.state in TS_INSTALL_STATES:
                        try:
                            txmbr.groups.remove(grpid)
                        except ValueError:
                            self.logger.debug(
                               _("package %s was not marked in group %s"), txmbr.po,
                                grpid)
                            continue

                        # if there aren't any other groups mentioned then remove the pkg
                        if len(txmbr.groups) == 0:
                            self.tsInfo.remove(txmbr.po.pkgtup)

    def select_group(self, group, pkg_types=const.GROUP_PACKAGE_TYPES):
        """Mark all the packages in the given group to be installed. :api

        :param group: the group containing the packages to mark for installation
        :return: number of transaction members added to the transaction set

        """

        txmbrs = []
        if group.selected:
            return 0
        group.selected = True

        pkgs = []
        if 'mandatory' in pkg_types:
            pkgs.extend(group.mandatory_packages)
        if 'default' in pkg_types:
            pkgs.extend(group.default_packages)
        if 'optional' in pkg_types:
            pkgs.extend(group.optional_packages)

        inst_set = set([pkg.name for pkg in self.sack.query().installed()])
        adding_msg = _('Adding package %s from group %s')
        cnt = 0
        for pkg in pkgs:
            self.logger.debug(adding_msg % (pkg.name, group.id))
            if pkg.name in inst_set:
                continue
            inst_set.add(pkg.name)
            current_cnt = self.install_groupie(pkg.name, inst_set)
            cnt += current_cnt

        if cnt == 0:
            msg = _('Warning: Group %s does not have any packages.')
            self.logger.warning(msg % group.id)
        return cnt

    def deselectGroup(self, grpid, force=False):
        """Unmark the packages in the given group from being
        installed.

        :param grpid: the name of the group containing the packages to
           unmark from installation
        :param force: if True, force remove all the packages in the
           given group from the transaction
        """

        if not self.comps.has_group(grpid):
            raise dnf.exceptions.CompsError(_("No Group named %s exists") % to_unicode(grpid))

        thesegroups = self.comps.groups_by_pattern(grpid)
        if not thesegroups:
            raise dnf.exceptions.CompsError(_("No Group named %s exists") % to_unicode(grpid))

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
                            self.logger.debug(
                               _("package %s was not marked in group %s"), txmbr.po,
                                grpid)
                            continue

                    # If the pkg isn't part of any group, or the group is
                    # being forced out ... then remove the pkg
                    if force or len(txmbr.groups) == 0:
                        self.tsInfo.remove(txmbr.po.pkgtup)
                        for pkg in self.tsInfo.conditionals.get(txmbr.name, []):
                            self.tsInfo.remove(pkg.pkgtup)

    def gpgKeyCheck(self):
        """Checks for the presence of GPG keys in the rpmdb.

        :return: 0 if there are no GPG keys in the rpmdb, and 1 if
           there are keys
        """
        gpgkeyschecked = self.conf.cachedir + '/.gpgkeyschecked.yum'
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
        if isinstance(depstring, tuple):
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
                        raise dnf.exceptions.Error(_('Invalid version flag from: %s') % str(depstring))
                    depflags = SYMBOLFLAGS[flagsymbol]

        return list(self.pkgSack.getProvides(depname, depflags, depver).keys())

    def returnPackageByDep(self, depstring):
        """Return the best, or first, package object that provides the
        given dependencies.

        :param depstring: a string specifying the dependency to return
           the package that fulfils
        :return: the best, or first, package that fulfils the given
           dependency
        :raises: a :class:`dnf.exceptions.Error` if no packages that
           fulfil the given dependency can be found
        """
        # we get all sorts of randomness here
        raise NotImplementedError("not implemented in hawkey") # :hawkey
        errstring = depstring
        if isinstance(depstring, basestring):
            errstring = str(depstring)

        try:
            pkglist = self.returnPackagesByDep(depstring)
        except dnf.exceptions.Error:
            raise dnf.exceptions.Error(_('No Package found for %s') % errstring)

        ps = ListPackageSack(pkglist)
        result = self._bestPackageFromList(ps.returnNewestByNameArch())
        if result is None:
            raise dnf.exceptions.Error(_('No Package found for %s') % errstring)

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
        if isinstance(depstring, tuple):
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
                        raise dnf.exceptions.Error(_('Invalid version flag from: %s') % str(depstring))
                    depflags = SYMBOLFLAGS[flagsymbol]

        return list(self.rpmdb.getProvides(depname, depflags, depver).keys())

    def returnInstalledPackageByDep(self, depstring):
        """Return the best, or first, installed package object that provides the
        given dependencies.

        :param depstring: a string specifying the dependency to return
           the package that fulfils
        :return: the best, or first, installed package that fulfils the given
           dependency
        :raises: a :class:`dnf.exceptions.Error` if no packages that
           fulfil the given dependency can be found
        """
        # we get all sorts of randomness here
        raise NotImplementedError("not implemented in hawkey") # :hawkey
        errstring = depstring
        if not isinstance(depstring, basestring):
            errstring = str(depstring)

        try:
            pkglist = self.returnInstalledPackagesByDep(depstring)
        except dnf.exceptions.Error:
            raise dnf.exceptions.Error(_('No Package found for %s') % errstring)

        ps = ListPackageSack(pkglist)
        result = self._bestPackageFromList(ps.returnNewestByNameArch())
        if result is None:
            raise dnf.exceptions.Error(_('No Package found for %s') % errstring)

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

    def install(self, pkg_spec):
        """Mark package(s) specified by pkg_spec for installation. :api"""

        def msg_installed(pkg):
            name = unicode(pkg)
            msg = _('Package %s is already installed, skipping.') % name
            self.logger.warning(msg)

        subj = dnf.subject.Subject(pkg_spec)
        if self.conf.multilib_policy == "all" or subj.filename_pattern:
            q = subj.get_best_query(self.sack)
            already_inst, available = self._query_matches_installed(q)
            for i in already_inst:
                msg_installed(i)
            for a in available:
                self._goal.install(a)
            return len(available)
        elif self.conf.multilib_policy == "best":
            sltr = subj.get_best_selector(self.sack)
            if not sltr:
                raise dnf.exceptions.PackageNotFoundError(
                    _("Problem in install: no package matched to install"))
            already_inst = self._sltr_matches_installed(sltr)
            if already_inst:
                msg_installed(already_inst[0])
            self._goal.install(select=sltr)
            return 1
        return 0

    def install_groupie(self, pkg_name, inst_set):
        """Installs a group member package by name. """
        forms = [hawkey.FORM_NAME]
        subj = dnf.subject.Subject(pkg_name)
        if self.conf.multilib_policy == "all":
            q = subj.get_best_query(self.sack, with_provides=False, forms=forms)
            for pkg in q:
                self._goal.install(pkg)
            return len(q)
        elif self.conf.multilib_policy == "best":
            sltr = subj.get_best_selector(self.sack, forms=forms)
            if sltr:
                self._goal.install(select=sltr)
                return 1
        return 0

    def update(self, pkg_spec):
        sltr = dnf.subject.Subject(pkg_spec).get_best_selector(self.sack)
        if sltr:
            self._goal.upgrade(select=sltr)
            return 1
        raise dnf.exceptions.PackageNotFoundError(
            _("Problem in update: no package matched to update"))

    def update_all(self):
        self._goal.upgrade_all()
        return 1

    def upgrade_to(self, pkg_spec):
        forms = [hawkey.FORM_NEVRA, hawkey.FORM_NEVR]
        sltr = dnf.subject.Subject(pkg_spec).get_best_selector(self.sack, forms=forms)
        if sltr:
            self._goal.upgrade_to(select=sltr)
            return 1
        return 0

    def distro_sync(self, pkg=None):
        if pkg is None:
            self._goal.distupgrade_all()
            return 1
        return 0

    def remove(self, pkg_spec):
        """Mark the specified package for removal.

        :return: a list of the transaction members that were added to
           the transaction set by this method

        """

        matches = dnf.subject.Subject(pkg_spec).get_best_query(self.sack)
        installed = matches.installed().run()
        if not installed:
            raise dnf.exceptions.PackagesNotInstalledError(
                _("Problem in remove: no package matched to remove"))

        clean_deps = self.conf.clean_requirements_on_remove
        for pkg in installed:
            self._goal.erase(pkg, clean_deps=clean_deps)
        return len(installed)

    def _local_common(self, path):
        self.sack.create_cmdline_repo()
        try:
            if not os.path.exists(path) and '://' in path:
                # download remote rpm to a tempfile
                path = dnf.util.urlopen(path, suffix='.rpm', delete=False).name
                self._tempfiles.append(path)
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
            return 0

        installed = sorted(self.sack.query().installed().filter(name=po.name))
        if len(installed) > 0 and installed[0] > po:
            self._goal.install(po)
            self._goal.erase(installed[0])
            return 2
        return 0

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
            return 0
        self._goal.install(po)
        return 1

    def update_local(self, path):
        po = self._local_common(path)
        if not po:
            return 0
        self._goal.upgrade_to(po)
        return 1

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
            return 0
        self._goal.install(po)
        return 1

    def reinstall(self, pkg_spec):
        subj = dnf.subject.Subject(pkg_spec)
        q = subj.get_best_query(self.sack)
        installed_pkgs = q.installed().run()
        available_nevra2pkg = query.per_nevra_dict(q.available())
        if not installed_pkgs:
            raise dnf.exceptions.PackagesNotInstalledError(
                _("Problem in reinstall: no package matched to remove"),
                available_nevra2pkg.values())

        cnt = 0
        for installed_pkg in installed_pkgs:
            try:
                available_pkg = available_nevra2pkg[str(installed_pkg)]
            except KeyError:
                continue

            self._goal.install(available_pkg)
            cnt += 1

        if cnt == 0:
            msg = _("Problem in reinstall: no package %s matched to install")
            msg %= ", ".join(str(pkg) for pkg in installed_pkgs)
            raise dnf.exceptions.PackagesNotAvailableError(msg, installed_pkgs)

        return cnt

    def downgrade(self, pkg_spec):
        """Mark a package to be downgraded.  This is equivalent to
        first removing the currently installed package, and then
        installing an older version.

        :return: a list of the transaction members added to the
           transaction set by this method

        """
        subj = dnf.subject.Subject(pkg_spec)
        q = subj.get_best_query(self.sack)
        installed = sorted(q.installed())
        installed_pkg = dnf.util.first(installed)
        if installed_pkg is None:
            raise dnf.exceptions.PackagesNotInstalledError(
                _("Problem in downgrade: no package matched to downgrade"))

        q = self.sack.query().filter(name=installed_pkg.name, arch=installed_pkg.arch)
        avail = [pkg for pkg in q.downgrades() if pkg < installed_pkg]
        avail_pkg = dnf.util.first(sorted(avail, reverse=True))
        if avail_pkg is None:
            return 0

        self._goal.install(avail_pkg)
        return 1

    def provides(self, provides_spec):
        providers = query.by_provides(self.sack, provides_spec)
        if providers:
            return providers
        if any(map(dnf.util.is_glob_pattern, provides_spec)):
            return self.sack.query().filter(file__glob=provides_spec)
        return self.sack.query().filter(file=provides_spec)

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
                except dnf.exceptions.Error:
                    # :dead
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

    def history_undo(self, id_or_offset):
        """Undo the transaction represented by the given ID or offset from
        the last transaction.

        :param id_or_offset: an ID or offset from the last transaction
           representing the transaction to be undone
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        def add_install(nevra):
            """Add a package to install."""
            pkgs = self.sack.query().available().nevra(nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Problem in undo: package to install not available"))
            assert len(pkgs) == 1
            self._transaction.add_install(pkgs[0], None)

        def add_erase(nevra):
            """Add a package to erase."""
            pkgs = self.sack.query().installed().nevra(nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotInstalledError(
                    _("Problem in undo: package to remove not installed"))
            assert len(pkgs) == 1
            self._transaction.add_erase(pkgs[0])

        def add_reinstall(new_nevra, old_nevra, obsoleted_nevras):
            """Add a package to reinstall."""
            news = self.sack.query().available().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Problem in undo: package to reinstall not available"))
            olds = self.sack.query().installed().nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotInstalledError(
                    _("Problem in undo: package to reinstall not installed"))
            obsoleteds = []
            for nevra in obsoleted_nevras:
                obsoleteds_ = self.sack.query().installed().nevra(nevra)
                if obsoleteds_:
                    assert len(obsoleteds_) == 1
                    obsoleteds.append(obsoleteds_[0])
            assert len(news) == 1 and len(olds) == 1
            self._transaction.add_reinstall(news[0], olds[0], obsoleteds)

        def add_upgrade(new_nevra, old_nevra):
            """Add a package to upgrade."""
            news = self.sack.query().available().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Problem in undo: package to update not available"))
            olds = self.sack.query().installed().nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotInstalledError(
                    _("Problem in undo: package to update not installed"))
            assert len(news) == 1 and len(olds) == 1
            self._transaction.add_upgrade(news[0], olds[0], None)

        def add_downgrade(new_nevra, old_nevra):
            """Add a package to downgrade."""
            news = self.sack.query().available().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotAvailableError(
                    _("Problem in undo: package to downgrade not available"))
            olds = self.sack.query().installed().nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotInstalledError(
                    _("Problem in undo: package to downgrade not installed"))
            assert len(news) == 1 and len(olds) == 1
            self._transaction.add_downgrade(news[0], olds[0], None)

        history = dnf.history.open_history(self.history, self.sack)
        last_id = history.last_transaction_id()
        if not last_id:
            raise ValueError('no transaction in history')
        id_ = last_id + id_or_offset + 1 if id_or_offset < 0 else id_or_offset

        # Build the transaction directly, because the depsolve is not needed.
        self._transaction = dnf.transaction.Transaction()
        for item_ops in history.transaction_items_ops(id_):
            obsoleted_nevras = []
            obsoleting_nevra = None
            replaced_nevra = None

            # It is easier to traverse the item in the reversed order.
            reversed_it = reversed(tuple(item_ops))
            nevra, state = next(reversed_it)

            while state == 'Obsoleted':
                obsoleted_nevras.append(nevra)
                nevra, state = next(reversed_it)
            if obsoleted_nevras:
                assert state == 'Obsoleting'
                obsoleting_nevra = nevra
                nevra, state = next(reversed_it)
            if state in {'Reinstalled', 'Downgraded', 'Updated'}:
                replaced_nevra = nevra
                nevra, state = next(reversed_it)
            assert dnf.util.is_exhausted(reversed_it)

            assert not obsoleting_nevra or obsoleting_nevra == nevra
            if state == 'Install':
                assert not replaced_nevra
                add_erase(nevra)
                for obsoleted_nevra in obsoleted_nevras:
                    add_install(obsoleted_nevra)
            elif state == 'Erase':
                assert not replaced_nevra and not obsoleted_nevras
                add_install(nevra)
            elif state == 'Reinstall':
                add_reinstall(replaced_nevra, nevra, obsoleted_nevras)
            elif state == 'Downgrade':
                add_upgrade(replaced_nevra, nevra)
                for obsoleted_nevra in obsoleted_nevras:
                    add_install(obsoleted_nevra)
            elif state == 'Update':
                add_downgrade(replaced_nevra, nevra)
                for obsoleted_nevra in obsoleted_nevras:
                    add_install(obsoleted_nevra)
            else:
                assert False

    def _retrievePublicKey(self, keyurl, repo=None, getSig=True):
        """
        Retrieve a key file
        @param keyurl: url to the key to retrieve
        Returns a list of dicts with all the keyinfo
        """
        key_installed = False

        msg = _('Retrieving key from %s') % keyurl
        self.logger.info(msg)

        # Go get the GPG key from the given URL
        try:
            # If we have a repo, use the proxy etc. configuration for it.
            rawkey = dnf.util.urlopen(keyurl, repo).read()

        except IOError as e:
            raise dnf.exceptions.Error(_('GPG key retrieval failed: ') +
                                      to_unicode(str(e)))

        # check for a .asc file accompanying it - that's our gpg sig on the key
        # suck it down and do the check
        sigfile = None
        valid_sig = False
        if getSig and repo and repo.gpgcakey:
            self.getCAKeyForRepo(repo, callback=repo.confirm_func)
            try:
                sigfile = dnf.util.urlopen(url + '.asc', repo)

            except IOError as e:
                sigfile = None

            if sigfile:
                if not misc.valid_detached_sig(sigfile,
                                    io.StringIO(rawkey), repo.gpgcadir):
                    #if we decide we want to check, even though the sig failed
                    # here is where we would do that
                    raise dnf.exceptions.Error(_('GPG key signature on key %s does not match CA Key for repo: %s') % (url, repo.id))
                else:
                    msg = _('GPG key signature verified against CA Key(s)')
                    self.logger.info(msg)
                    valid_sig = True

        # Parse the key
        try:
            keys_info = misc.getgpgkeyinfo(rawkey, multiple=True)
        except ValueError as e:
            raise dnf.exceptions.Error(_('Invalid GPG Key from %s: %s') %
                                      (url, to_unicode(str(e))))
        keys = []
        for keyinfo in keys_info:
            thiskey = {}
            for info in ('keyid', 'timestamp', 'userid',
                         'fingerprint', 'raw_key'):
                if info not in keyinfo:
                    raise dnf.exceptions.Error(
                        _('GPG key parsing failed: key does not have value %s') + info
                    )
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
            pkgs = self.sack.query().filter(file=fname)
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
        :raises: :class:`dnf.exceptions.Error` if there are errors
           retrieving the keys
        """
        repo = self.repos[po.repoid]
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
                ts = self.rpmconn.readonly_ts
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
                    raise dnf.exceptions.Error(_prov_key_data(msg))
                self.logger.info(_('Key imported successfully'))
                key_installed = True

        if not key_installed and user_cb_fail:
            raise dnf.exceptions.Error(_("Didn't install any keys"))

        if not key_installed:
            msg = _('The GPG keys listed for the "%s" repository are ' \
                  'already installed but they are not correct for this ' \
                  'package.\n' \
                  'Check that the correct key URLs are configured for ' \
                  'this repository.') % repo.name
            raise dnf.exceptions.Error(_prov_key_data(msg))

        # Check if the newly installed keys helped
        result, errmsg = self.sigCheckPkg(po)
        if result != 0:
            msg = _("Import of key(s) didn't help, wrong key(s)?")
            self.logger.info(msg)
            errmsg = to_unicode(errmsg)
            raise dnf.exceptions.Error(_prov_key_data(errmsg))

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
                    ikf = self.conf._repos_persistdir + '/imported_cakeys'
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
                    raise dnf.exceptions.Error(_prov_key_data(msg))
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
            raise dnf.exceptions.Error(_prov_key_data(msg))

        if not key_installed:
            msg = \
                  _('The GPG keys listed for the "%s" repository are ' \
                  'already installed but they are not correct.\n' \
                  'Check that the correct key URLs are configured for ' \
                  'this repository.') % (repo.name)
            raise dnf.exceptions.Error(_prov_key_data(msg))

    def getCAKeyForRepo(self, repo, callback=None):
        """Retrieve a key for a repository.  If needed, use the given
        callback to prompt whether the key should be imported.

        :param repo: repository object to retrieve the key of
        :param callback: callback function to use for asking for
           verification of key information
        """
        self._getAnyKeyForRepo(repo, repo.gpgcadir, repo.gpgcakey, is_cakey=True, callback=callback)

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

    def _store_config_in_history(self):
        self.history.write_addon_data('config-main', self.conf.dump())
        myrepos = ''
        for repo in self.repos.iter_enabled():
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
