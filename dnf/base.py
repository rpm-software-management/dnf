# Copyright 2005 Duke University
# Copyright (C) 2012-2016 Red Hat, Inc.
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from dnf.comps import CompsQuery
from dnf.i18n import _, P_, ucd
from dnf.module.exceptions import NoModuleException
from dnf.module.persistor import ModulePersistor
from dnf.module.metadata_loader import ModuleMetadataLoader
from dnf.module.repo_module_dict import RepoModuleDict
from dnf.module.repo_module_version import RepoModuleVersion
from dnf.util import first
from dnf.yum import history
from dnf.yum import misc
from dnf.yum import rpmsack
from functools import reduce
import collections
import datetime
import dnf.callback
import dnf.comps
import dnf.conf
import dnf.conf.read
import dnf.crypto
import dnf.drpm
import dnf.exceptions
import dnf.goal
import dnf.history
import dnf.lock
import dnf.logging
import dnf.persistor
import dnf.plugin
import dnf.query
import dnf.repo
import dnf.repodict
import dnf.rpm.connection
import dnf.rpm.miscutils
import dnf.rpm.transaction
import dnf.sack
import dnf.subject
import dnf.transaction
import dnf.util
import dnf.yum.rpmtrans
import functools
import hawkey
import itertools
import logging
import os
import operator
import re
import rpm
import sys
import time
import shutil

logger = logging.getLogger("dnf")


class Base(object):

    def __init__(self, conf=None):
        # :api
        self._closed = False
        self._conf = conf or self._setup_default_conf()
        self._goal = None
        self._repo_persistor = None
        self._sack = None
        self._transaction = None
        self._priv_ts = None
        self._comps = None
        self._comps_trans = dnf.comps.TransactionBunch()
        self._history = None
        self._tempfiles = set()
        self._trans_tempfiles = set()
        self._ds_callback = dnf.callback.Depsolve()
        self._group_persistor = None
        self._module_persistor = None
        self._logging = dnf.logging.Logging()
        self._repos = dnf.repodict.RepoDict()
        self._rpm_probfilter = set([rpm.RPMPROB_FILTER_OLDPACKAGE])
        self._plugins = dnf.plugin.Plugins()
        self._trans_success = False
        self._tempfile_persistor = None
        self._update_security_filters = {}
        self._allow_erasing = False
        self._revert_reason = []
        self._repo_set_imported_gpg_keys = set()
        self.repo_module_dict = RepoModuleDict(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_args):
        self.close()

    def _add_tempfiles(self, files):
        if self._transaction:
            self._trans_tempfiles.update(files)
        elif self.conf.destdir:
            pass
        else:
            self._tempfiles.update(files)

    def _add_repo_to_sack(self, repo):
        repo.load()
        hrepo = repo._hawkey_repo
        hrepo.repomd_fn = repo._repomd_fn
        hrepo.primary_fn = repo._primary_fn
        hrepo.filelists_fn = repo._filelists_fn
        hrepo.cost = repo.cost
        hrepo.priority = repo.priority
        if repo._presto_fn:
            hrepo.presto_fn = repo._presto_fn
        else:
            logger.debug("not found deltainfo for: %s", repo.name)
        if repo._updateinfo_fn:
            hrepo.updateinfo_fn = repo._updateinfo_fn
        else:
            logger.debug("not found updateinfo for: %s", repo.name)
        self._sack.load_repo(hrepo, build_cache=True, load_filelists=True,
                             load_presto=repo.deltarpm,
                             load_updateinfo=True)

    @staticmethod
    def _setup_default_conf():
        conf = dnf.conf.Conf()
        subst = conf.substitutions
        if 'releasever' not in subst:
            subst['releasever'] = \
                dnf.rpm.detect_releasever(conf.installroot)
        return conf

    def _setup_excludes_includes(self):
        disabled = set(self.conf.disable_excludes)
        if 'all' in disabled:
            return
        # first evaluate repo specific includes/excludes
        for r in self.repos.iter_enabled():
            if r.id in disabled:
                continue
            if len(r.includepkgs) > 0:
                for incl in r.includepkgs:
                    subj = dnf.subject.Subject(incl)
                    pkgs = subj.get_best_query(self.sack)
                    self.sack.add_includes(pkgs.filter(reponame=r.id))
                self.sack.set_use_includes(True, r.id)
            for excl in r.excludepkgs:
                subj = dnf.subject.Subject(excl)
                pkgs = subj.get_best_query(self.sack)
                self.sack.add_excludes(pkgs.filter(reponame=r.id))
        # then main (global) includes/excludes because they can mask
        # repo specific settings
        if 'main' not in disabled:
            if len(self.conf.includepkgs) > 0:
                for incl in self.conf.includepkgs:
                    subj = dnf.subject.Subject(incl)
                    pkgs = subj.get_best_query(self.sack)
                    self.sack.add_includes(pkgs)
                self.sack.set_use_includes(True)
            for excl in self.conf.excludepkgs:
                subj = dnf.subject.Subject(excl)
                pkgs = subj.get_best_query(self.sack)
                self.sack.add_excludes(pkgs)

    def _setup_modules(self):
        for repo in self.repos.iter_enabled():
            try:
                module_metadata = ModuleMetadataLoader(repo).load()
                for data in module_metadata:
                    self.repo_module_dict.add(RepoModuleVersion(data, base=self, repo=repo))
            except dnf.exceptions.Error as e:
                logger.debug(e)
                continue

        self.repo_module_dict.read_all_module_confs()
        self.repo_module_dict.read_all_module_defaults()
        self._module_persistor = ModulePersistor()
        self.use_module_includes()

    def use_module_includes(self):
        def update_future_package_set(includes, repos):
            include_repos.update(repos)

            for nevra in includes:
                subj = dnf.subject.Subject(nevra)
                pkgs = subj.get_best_query(self.sack, forms=[hawkey.FORM_NEVRA])
                include_pkgs.add(pkgs)

        self.sack.reset_includes()
        include_repos = set()
        include_pkgs = set()
        for repo_module in self.repo_module_dict.values():
            if repo_module.conf.enabled:
                includes, repos = self.repo_module_dict.get_includes(repo_module.name,
                                                                     repo_module.conf.stream)
                update_future_package_set(includes, repos)
            elif repo_module.defaults.stream:
                includes, repos = self.repo_module_dict.get_includes(repo_module.name,
                                                                     repo_module.defaults.stream)
                update_future_package_set(includes, repos)

        for pkg in include_pkgs:
            self.sack.add_includes(pkg)

        for repo in include_repos:
            self.sack.set_use_includes(True, repo.id)

    def _store_persistent_data(self):
        if self._repo_persistor and not self.conf.cacheonly:
            expired = [r.id for r in self.repos.iter_enabled() if r._md_expired]
            self._repo_persistor.expired_to_add.update(expired)
            self._repo_persistor.save()

        if self._group_persistor:
            self._group_persistor.save()

        if self._tempfile_persistor:
            self._tempfile_persistor.save()

        if self._module_persistor:
            self._module_persistor.save()

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
        # :api
        return self._repos

    @repos.deleter
    def repos(self):
        # :api
        self._repos = None

    @property
    @dnf.util.lazyattr("_priv_rpmconn")
    def _rpmconn(self):
        return dnf.rpm.connection.RpmConnection(self.conf.installroot)

    @property
    def sack(self):
        # :api
        return self._sack

    @property
    def transaction(self):
        # :api
        return self._transaction

    @transaction.setter
    def transaction(self, value):
        # :api
        if self._transaction:
            raise ValueError('transaction already set')
        self._transaction = value

    def _activate_persistor(self):
        self._repo_persistor = dnf.persistor.RepoPersistor(self.conf.cachedir)

    def init_plugins(self, disabled_glob=(), enable_plugins=(), cli=None):
        # :api
        """Load plugins and run their __init__()."""
        if self.conf.plugins:
            self._plugins._load(self.conf, disabled_glob, enable_plugins)
        self._plugins._run_init(self, cli)

    def pre_configure_plugins(self):
        # :api
        """Run plugins pre_configure() method."""
        self._plugins._run_pre_config()

    def configure_plugins(self):
        # :api
        """Run plugins configure() method."""
        self._plugins._run_config()

    def update_cache(self, timer=False):
        # :api

        period = self.conf.metadata_timer_sync
        persistor = self._repo_persistor
        if timer:
            if dnf.util.on_metered_connection():
                msg = _('Metadata timer caching disabled '
                        'when running on metered connection.')
                logger.info(msg)
                return False
            if dnf.util.on_ac_power() is False:
                msg = _('Metadata timer caching disabled '
                        'when running on a battery.')
                logger.info(msg)
                return False
            if period <= 0:
                msg = _('Metadata timer caching disabled.')
                logger.info(msg)
                return False
            since_last_makecache = persistor.since_last_makecache()
            if since_last_makecache is not None and since_last_makecache < period:
                logger.info(_('Metadata cache refreshed recently.'))
                return False
            self.repos.all()._max_mirror_tries = 1

        for r in self.repos.iter_enabled():
            (is_cache, expires_in) = r._metadata_expire_in()
            if expires_in is None:
                logger.info('%s: will never be expired'
                            ' and will not be refreshed.', r.id)
            elif not is_cache or expires_in <= 0:
                logger.debug('%s: has expired and will be refreshed.', r.id)
                r._md_expire_cache()
            elif timer and expires_in < period:
                # expires within the checking period:
                msg = "%s: metadata will expire after %d seconds " \
                      "and will be refreshed now"
                logger.debug(msg, r.id, expires_in)
                r._md_expire_cache()
            else:
                logger.debug('%s: will expire after %d seconds.', r.id,
                             expires_in)

        if timer:
            persistor.reset_last_makecache = True
        self.fill_sack(load_system_repo=False, load_available_repos=True)  # performs the md sync
        logger.info(_('Metadata cache created.'))
        return True

    def fill_sack(self, load_system_repo=True, load_available_repos=True):
        # :api
        """Prepare the Sack and the Goal objects. """
        timer = dnf.logging.Timer('sack setup')
        if self._sack is not None and self._repos is not None:
            for repo in self._repos.values():
                repo._hawkey_repo = repo._init_hawkey_repo()
        self._sack = dnf.sack._build_sack(self)
        lock = dnf.lock.build_metadata_lock(self.conf.cachedir, self.conf.exit_on_lock)
        with lock:
            if load_system_repo is not False:
                try:
                    # FIXME: If build_cache=True, @System.solv is incorrectly updated in install-
                    # remove loops
                    self._sack.load_system_repo(build_cache=False)
                except IOError:
                    if load_system_repo != 'auto':
                        raise
            if load_available_repos:
                errors = []
                mts = 0
                age = time.time()
                for r in self.repos.iter_enabled():
                    try:
                        self._add_repo_to_sack(r)
                        if r.metadata._timestamp > mts:
                            mts = r.metadata._timestamp
                        if r.metadata._age < age:
                            age = r.metadata._age
                        logger.debug(_("%s: using metadata from %s."), r.id,
                                     dnf.util.normalize_time(
                                         r.metadata._md_timestamp))
                    except dnf.exceptions.RepoError as e:
                        r._md_expire_cache()
                        if r.skip_if_unavailable is False:
                            raise
                        errors.append(e)
                        r.disable()
                for e in errors:
                    logger.warning(_("%s, disabling."), e)
                if self.repos._any_enabled():
                    if age != 0 and mts != 0:
                        logger.info(_("Last metadata expiration check: %s ago on %s."),
                                    datetime.timedelta(seconds=int(age)),
                                    dnf.util.normalize_time(mts))
            else:
                self.repos.all().disable()
        conf = self.conf
        self._sack._configure(conf.installonlypkgs, conf.installonly_limit)
        self._setup_excludes_includes()
        self._setup_modules()
        timer()
        self._goal = dnf.goal.Goal(self._sack)
        self._plugins.run_sack()
        return self._sack

    @property
    @dnf.util.lazyattr("_priv_yumdb")
    def _yumdb(self):
        db_path = os.path.normpath(self.conf.persistdir + '/yumdb')
        return rpmsack.AdditionalPkgDB(db_path)

    def close(self):
        # :api
        """Close all potential handles and clean cache.

        Typically the handles are to data sources and sinks.

        """

        if self._closed:
            return
        logger.log(dnf.logging.DDEBUG, 'Cleaning up.')
        self._closed = True
        if not self._trans_success:
            for pkg, reason in self._revert_reason:
                self._yumdb.get_package(pkg).reason = reason
        self._tempfile_persistor = dnf.persistor.TempfilePersistor(
            self.conf.cachedir)

        if not self.conf.keepcache:
            self._clean_packages(self._tempfiles)
            if self._trans_success:
                self._trans_tempfiles.update(
                    self._tempfile_persistor.get_saved_tempfiles())
                self._tempfile_persistor.empty()
                if self._transaction.install_set:
                    self._clean_packages(self._trans_tempfiles)
            else:
                self._tempfile_persistor.tempfiles_to_add.update(
                    self._trans_tempfiles)

        if self._tempfile_persistor.tempfiles_to_add:
            logger.info(_("The downloaded packages were saved in cache "
                          "until the next successful transaction."))
            logger.info(_("You can remove cached packages by executing "
                          "'%s'."), "dnf clean packages")

        # Do not trigger the lazy creation:
        if self._history is not None:
            self.history.close()
        self._store_persistent_data()
        self._closeRpmDB()

    def read_all_repos(self, opts=None):
        # :api
        """Read repositories from the main conf file and from .repo files."""

        reader = dnf.conf.read.RepoReader(self.conf, opts)
        for repo in reader:
            try:
                self.repos.add(repo)
            except dnf.exceptions.ConfigError as e:
                logger.warning(e)

    def reset(self, sack=False, repos=False, goal=False):
        # :api
        """Make the Base object forget about various things."""
        if sack:
            self._sack = None
        if repos:
            self._repos = dnf.repodict.RepoDict()
        if goal:
            self._goal = None
            if self._sack is not None:
                self._goal = dnf.goal.Goal(self._sack)
            if self._group_persistor is not None:
                self._group_persistor = self._activate_group_persistor()
            self._comps_trans = dnf.comps.TransactionBunch()

    def _closeRpmDB(self):
        """Closes down the instances of rpmdb that could be open."""
        del self._ts

    _TS_FLAGS_TO_RPM = {'noscripts': rpm.RPMTRANS_FLAG_NOSCRIPTS,
                        'notriggers': rpm.RPMTRANS_FLAG_NOTRIGGERS,
                        'nodocs': rpm.RPMTRANS_FLAG_NODOCS,
                        'test': rpm.RPMTRANS_FLAG_TEST,
                        'justdb': rpm.RPMTRANS_FLAG_JUSTDB,
                        'nocontexts': rpm.RPMTRANS_FLAG_NOCONTEXTS,
                        'nocrypto': rpm.RPMTRANS_FLAG_NOFILEDIGEST}
    _TS_VSFLAGS_TO_RPM = {'nocrypto': rpm._RPMVSF_NOSIGNATURES |
                          rpm._RPMVSF_NODIGESTS}

    @property
    def _ts(self):
        """Set up the RPM transaction set that will be used
           for all the work."""
        if self._priv_ts is not None:
            return self._priv_ts
        self._priv_ts = dnf.rpm.transaction.TransactionWrapper(
            self.conf.installroot)
        self._priv_ts.setFlags(0)  # reset everything.
        for flag in self.conf.tsflags:
            rpm_flag = self._TS_FLAGS_TO_RPM.get(flag)
            if rpm_flag is None:
                logger.critical(_('Invalid tsflag in config file: %s'), flag)
                continue
            self._priv_ts.addTsFlag(rpm_flag)
            vs_flag = self._TS_VSFLAGS_TO_RPM.get(flag)
            if vs_flag is not None:
                self._priv_ts.pushVSFlags(vs_flag)

        if not self.conf.diskspacecheck:
            self._rpm_probfilter.add(rpm.RPMPROB_FILTER_DISKSPACE)

        if self.conf.ignorearch:
            self._rpm_probfilter.add(rpm.RPMPROB_FILTER_IGNOREARCH)

        probfilter = reduce(operator.or_, self._rpm_probfilter, 0)
        self._priv_ts.setProbFilter(probfilter)
        return self._priv_ts

    @_ts.deleter
    def _ts(self):
        """Releases the RPM transaction set. """
        if self._priv_ts is None:
            return
        self._priv_ts.close()
        del self._priv_ts
        self._priv_ts = None

    def _activate_group_persistor(self):
        return dnf.persistor.GroupPersistor(self.conf.persistdir, self._comps)

    def read_comps(self, arch_filter=False):
        # :api
        """Create the groups object to access the comps metadata."""
        timer = dnf.logging.Timer('loading comps')
        self._comps = dnf.comps.Comps()

        logger.log(dnf.logging.DDEBUG, 'Getting group metadata')
        for repo in self.repos.iter_enabled():
            if not repo.enablegroups:
                continue
            if not repo.metadata:
                continue
            comps_fn = repo.metadata._comps_fn
            if comps_fn is None:
                continue

            logger.log(dnf.logging.DDEBUG,
                       'Adding group file from repository: %s', repo.id)
            if repo._md_only_cached:
                decompressed = misc.calculate_repo_gen_dest(comps_fn,
                                                            'groups.xml')
                if not os.path.exists(decompressed):
                    # root privileges are needed for comps decompression
                    continue
            else:
                decompressed = misc.repo_gen_decompress(comps_fn, 'groups.xml')

            try:
                self._comps._add_from_xml_filename(decompressed)
            except dnf.exceptions.CompsError as e:
                msg = _('Failed to add groups file for repository: %s - %s')
                logger.critical(msg, repo.id, e)

        self._group_persistor = self._activate_group_persistor()
        if arch_filter:
            self._comps._i.arch_filter(
                [self._conf.substitutions['basearch']])
        timer()
        return self._comps

    def _getHistory(self):
        """auto create the history object that to access/append the transaction
           history information. """
        if self._history is None:
            db_path = self.conf.persistdir + "/history"
            releasever = self.conf.releasever
            self._history = history.YumHistory(db_path, self._yumdb,
                                               root=self.conf.installroot,
                                               releasever=releasever)
        return self._history

    history = property(fget=lambda self: self._getHistory(),
                       fset=lambda self, value: setattr(
                           self, "_history", value),
                       fdel=lambda self: setattr(self, "_history", None),
                       doc="Yum History Object")

    def _goal2transaction(self, goal):
        ts = dnf.transaction.Transaction()
        all_obsoleted = set(goal.list_obsoleted())

        for pkg in goal.list_downgrades():
            obs = goal.obsoleted_by_package(pkg)
            downgraded = obs[0]
            self._ds_callback.pkg_added(downgraded, 'dd')
            self._ds_callback.pkg_added(pkg, 'd')
            ts.add_downgrade(pkg, downgraded, obs[1:])
        for pkg in goal.list_reinstalls():
            self._ds_callback.pkg_added(pkg, 'r')
            obs = goal.obsoleted_by_package(pkg)
            reinstalled = obs[0]
            ts.add_reinstall(pkg, reinstalled, obs[1:])
        for pkg in goal.list_installs():
            self._ds_callback.pkg_added(pkg, 'i')
            obs = goal.obsoleted_by_package(pkg)
            ts.add_install(pkg, obs, goal.get_reason(pkg))
            cb = lambda pkg: self._ds_callback.pkg_added(pkg, 'od')
            dnf.util.mapall(cb, obs)
        for pkg in goal.list_upgrades():
            group_fn = functools.partial(operator.contains, all_obsoleted)
            obs, upgraded = dnf.util.group_by_filter(
                group_fn, goal.obsoleted_by_package(pkg))
            cb = lambda pkg: self._ds_callback.pkg_added(pkg, 'od')
            dnf.util.mapall(cb, obs)
            if pkg in self._get_installonly_query():
                ts.add_install(pkg, obs)
            else:
                ts.add_upgrade(pkg, upgraded[0], obs)
                cb = lambda pkg: self._ds_callback.pkg_added(pkg, 'ud')
                dnf.util.mapall(cb, upgraded)
            self._ds_callback.pkg_added(pkg, 'u')
        for pkg in goal.list_erasures():
            self._ds_callback.pkg_added(pkg, 'e')
            ts.add_erase(pkg)
        return ts

    def _query_matches_installed(self, q):
        """ See what packages in the query match packages (also in older
            versions, but always same architecture) that are already installed.

            Unlike in case of _sltr_matches_installed(), it is practical here
            to know even the packages in the original query that can still be
            installed.
        """
        inst = q.installed()
        inst_per_arch = inst._na_dict()
        avail_per_arch = q.available()._na_dict()
        avail_l = []
        inst_l = []
        for na in avail_per_arch:
            if na in inst_per_arch:
                inst_l.append(inst_per_arch[na][0])
            else:
                avail_l.append(avail_per_arch[na])
        return inst_l, avail_l

    def _sltr_matches_installed(self, sltr):
        """ See if sltr matches a patches that is (in older version or different
            architecture perhaps) already installed.
        """
        inst = self.sack.query().installed()
        inst = inst.filter(pkg=sltr.matches())
        return list(inst)

    def _is_userinstalled(self, pkg):
        """Returns true if the package is installed by user."""
        return self._yumdb.get_package(pkg).get('reason') == 'user' and \
            self._yumdb.get_package(pkg).get('from_repo') != 'anakonda'

    def iter_userinstalled(self):
        """Get iterator over the packages installed by the user."""
        return (pkg for pkg in self.sack.query().installed() if self._is_userinstalled(pkg))

    def _run_hawkey_goal(self, goal, allow_erasing):
        ret = goal.run(
            allow_uninstall=allow_erasing, force_best=self.conf.best,
            ignore_weak_deps=(not self.conf.install_weak_deps))
        if self.conf.debug_solver:
            goal.write_debugdata('./debugdata')
        return ret

    def resolve(self, allow_erasing=False):
        # :api
        """Build the transaction set."""
        exc = None
        self._finalize_comps_trans()

        timer = dnf.logging.Timer('depsolve')
        self._ds_callback.start()
        goal = self._goal
        if goal.req_has_erase():
            goal.push_userinstalled(self.sack.query().installed(), self._yumdb)
        elif not self.conf.upgrade_group_objects_upgrade:
            # exclude packages installed from groups
            # these packages will be marked to installation
            # which could prevent them from upgrade, downgrade
            # to prevent "conflicting job" error it's not applied
            # to "remove" and "reinstall" commands

            if not self._group_persistor:
                self._group_persistor = self._activate_group_persistor()
            solver = self._build_comps_solver()
            solver._exclude_packages_from_installed_groups(self)

        goal.add_protected(self.sack.query().filter(
            name=self.conf.protected_packages))
        if not self._run_hawkey_goal(goal, allow_erasing):
            if self.conf.debuglevel >= 6:
                goal.log_decisions()
            msg = dnf.util._format_resolve_problems(goal.problem_rules())
            exc = dnf.exceptions.DepsolveError(msg)
        else:
            self._transaction = self._goal2transaction(goal)

        self._ds_callback.end()
        timer()

        got_transaction = self._transaction is not None and \
            len(self._transaction) > 0
        if got_transaction:
            msg = self._transaction._rpm_limitations()
            if msg:
                exc = dnf.exceptions.Error(msg)

        if exc is not None:
            if self._group_persistor:
                self._group_persistor._rollback()
            raise exc
        if self._group_persistor:
            installed = self.sack.query().installed()
            self._group_persistor.update_group_env_installed(installed, goal)
        self._plugins.run_resolved()
        self.repo_module_dict.enable_based_on_rpms()
        return got_transaction

    def do_transaction(self, display=()):
        # :api
        if not isinstance(display, collections.Sequence):
            display = [display]
        display = \
            [dnf.yum.rpmtrans.LoggingTransactionDisplay()] + list(display)

        if not self.transaction:
            if self._group_persistor:
                self._trans_success = True
                self._group_persistor.commit()
            return

        logger.info(_('Running transaction check'))
        lock = dnf.lock.build_rpmdb_lock(self.conf.persistdir, self.conf.exit_on_lock)
        with lock:
            # save our ds_callback out
            dscb = self._ds_callback
            self._ds_callback = None
            self.transaction._populate_rpm_ts(self._ts)

            msgs = self._run_rpm_check()
            if msgs:
                msg = _('Error: transaction check vs depsolve:')
                logger.error(msg)
                for msg in msgs:
                    logger.error(msg)
                raise dnf.exceptions.TransactionCheckError(msg)

            logger.info(_('Transaction check succeeded.'))

            timer = dnf.logging.Timer('transaction test')
            logger.info(_('Running transaction test'))

            self._ts.order()  # order the transaction
            self._ts.clean()  # release memory not needed beyond this point

            testcb = dnf.yum.rpmtrans.RPMTransaction(self, test=True)
            tserrors = self._ts.test(testcb)
            del testcb

            if len(tserrors) > 0:
                errstring = _('Transaction check error:') + '\n'
                for descr in tserrors:
                    errstring += '  %s\n' % ucd(descr)

                raise dnf.exceptions.Error(errstring + '\n' +
                                        self._trans_error_summary(errstring))

            logger.info(_('Transaction test succeeded.'))
            timer()

            # unset the sigquit handler
            timer = dnf.logging.Timer('transaction')
            # put back our depcheck callback
            self._ds_callback = dscb
            # setup our rpm ts callback
            cb = dnf.yum.rpmtrans.RPMTransaction(self, displays=display)
            if self.conf.debuglevel < 2:
                for display_ in cb.displays:
                    display_.output = False

            self._plugins.run_pre_transaction()

            logger.info(_('Running transaction'))
            self._run_transaction(cb=cb)
        timer()
        self._plugins.unload_removed_plugins(self.transaction)
        self._plugins.run_transaction()
        if self._trans_success:
            if self._group_persistor:
                self._group_persistor.commit()
            if self._module_persistor:
                self._module_persistor.commit()

    def _trans_error_summary(self, errstring):
        """Parse the error string for 'interesting' errors which can
        be grouped, such as disk space issues.

        :param errstring: the error string
        :return: a string containing a summary of the errors
        """
        summary = ''
        # do disk space report first
        p = re.compile(r'needs (\d+)MB on the (\S+) filesystem')
        disk = {}
        for m in p.finditer(errstring):
            if m.group(2) not in disk:
                disk[m.group(2)] = int(m.group(1))
            if disk[m.group(2)] < int(m.group(1)):
                disk[m.group(2)] = int(m.group(1))

        if disk:
            summary += _('Disk Requirements:') + "\n"
            for k in disk:
                summary += "   " + P_(
                    'At least %dMB more space needed on the %s filesystem.',
                    'At least %dMB more space needed on the %s filesystem.',
                    disk[k]) % (disk[k], k) + '\n'

        summary = _('Error Summary') + '\n-------------\n' + summary

        return summary

    def _record_history(self):
        return self.conf.history_record and \
            not self._ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)

    def _run_transaction(self, cb):
        """Perform the RPM transaction."""

        if self._record_history():
            using_pkgs_pats = list(self.conf.history_record_packages)
            installed_query = self.sack.query().installed()
            using_pkgs = installed_query.filter(name=using_pkgs_pats).run()
            rpmdbv = self.sack._rpmdb_version(self._yumdb)
            lastdbv = self.history.last()
            if lastdbv is not None:
                lastdbv = lastdbv.end_rpmdbversion

            if lastdbv is None or rpmdbv != lastdbv:
                logger.debug("RPMDB altered outside of DNF.")

            cmdline = None
            if hasattr(self, 'args') and self.args:
                cmdline = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                cmdline = ' '.join(self.cmds)

            self.history.beg(rpmdbv, using_pkgs, list(self.transaction),
                             [], [], cmdline)
            # write out our config and repo data to additional history info
            self._store_config_in_history()

            if self.conf.comment:
                # write out user provided comment to history info
                self._store_comment_in_history(self.conf.comment)

        if self.conf.reset_nice:
            onice = os.nice(0)
            if onice:
                try:
                    os.nice(-onice)
                except:
                    onice = 0

        logger.log(dnf.logging.DDEBUG, 'RPM transaction start.')
        errors = self._ts.run(cb.callback, '')
        logger.log(dnf.logging.DDEBUG, 'RPM transaction over.')
        # ts.run() exit codes are, hmm, "creative": None means all ok, empty
        # list means some errors happened in the transaction and non-empty
        # list that there were errors preventing the ts from starting...
        if self.conf.reset_nice:
            try:
                os.nice(onice)
            except:
                pass

        if errors is None:
            pass
        elif len(errors) == 0:
            # this is a particularly tricky case happening also when rpm failed
            # to obtain the transaction lock. We can only try to see if a
            # particular element failed and if not, decide that is the
            # case.
            failed = [el for el in self._ts if el.Failed()]
            if len(failed) > 0:
                for te in failed:
                    te_nevra = dnf.util._te_nevra(te)
                    for tsi in self._transaction:
                        if tsi.erased is not None and str(tsi.erased) == te_nevra:
                            tsi.op_type = dnf.transaction.FAIL
                            break
                        if tsi.installed is not None and str(tsi.installed) == te_nevra:
                            tsi.op_type = dnf.transaction.FAIL
                            break
                        for o in tsi.obsoleted:
                            if str(o) == te_nevra:
                                tsi.op_type = dnf.transaction.FAIL
                                break

                errstring = _('Errors occurred during transaction.')
                logger.debug(errstring)
            else:
                login = dnf.util.get_effective_login()
                msg = _("Failed to obtain the transaction lock "
                        "(logged in as: %s).")
                logger.critical(msg, login)
                msg = _('Could not run transaction.')
                raise dnf.exceptions.Error(msg)
        else:
            if self._record_history():
                herrors = [ucd(x) for x in errors]
                self.history.end(rpmdbv, 2, errors=herrors)

            logger.critical(_("Transaction couldn't start:"))
            for e in errors:
                logger.critical(e[0])  # should this be 'to_unicoded'?
            msg = _("Could not run transaction.")
            raise dnf.exceptions.Error(msg)

        for i in ('ts_all_fn', 'ts_done_fn'):
            if hasattr(cb, i):
                fn = getattr(cb, i)
                try:
                    misc.unlink_f(fn)
                except (IOError, OSError):
                    msg = _('Failed to remove transaction file %s')
                    logger.critical(msg, fn)

        # sync up what just happened versus what is in the rpmdb
        if not self._ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST):
            self._verify_transaction(cb.verify_tsi_package)

    def _verify_transaction(self, verify_pkg_cb=None):
        """Check that the transaction did what was expected, and
        propagate external yumdb information.  Output error messages
        if the transaction did not do what was expected.

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

        total = self.transaction._total_package_count()

        def display_banner(pkg, count):
            count += 1
            if verify_pkg_cb is not None:
                verify_pkg_cb(pkg, count, total)
            return count

        timer = dnf.logging.Timer('verify transaction')
        count = 0
        # the rpmdb has changed by now. hawkey doesn't support dropping a repo
        # yet we have to check what packages are in now: build a transient sack
        # with only rpmdb in it. In the future when RPM Python bindings can
        # tell us if a particular transaction element failed or not we can skip
        # this completely.
        rpmdb_sack = dnf.sack._rpmdb_sack(self)

        for tsi in self._transaction:
            rpo = tsi.installed
            if rpo is None:
                continue

            installed = rpmdb_sack.query().installed()._nevra(
                rpo.name, rpo.evr, rpo.arch)
            if len(installed) < 1:
                tsi.op_type = dnf.transaction.FAIL
                logger.critical(_('%s was supposed to be installed'
                                  ' but is not!'), rpo)
                count = display_banner(rpo, count)
                continue
            po = installed[0]
            count = display_banner(rpo, count)
            yumdb_info = self._yumdb.get_package(po)
            yumdb_info.from_repo = rpo.repoid

            yumdb_info.reason = tsi._propagated_reason(self._yumdb, self._get_installonly_query())
            yumdb_info.releasever = self.conf.releasever
            if hasattr(self, 'args') and self.args:
                yumdb_info.command_line = ' '.join(self.args)
            elif hasattr(self, 'cmds') and self.cmds:
                yumdb_info.command_line = ' '.join(self.cmds)
            csum = rpo.returnIdSum()
            if csum is not None:
                yumdb_info.checksum_type = str(csum[0])
                yumdb_info.checksum_data = csum[1]

            if rpo._from_cmdline:
                try:
                    st = os.stat(rpo.localPkg())
                    lp_ctime = str(int(st.st_ctime))
                    lp_mtime = str(int(st.st_mtime))
                    yumdb_info.from_repo_revision = lp_ctime
                    yumdb_info.from_repo_timestamp = lp_mtime
                except Exception:
                    pass
            elif hasattr(rpo.repo, 'repoXML'):
                md = rpo.repo.repoXML
                if md and md._revision is not None:
                    yumdb_info.from_repo_revision = str(md._revision)
                if md:
                    yumdb_info.from_repo_timestamp = str(md._timestamp)

            loginuid = misc.getloginuid()
            if tsi.op_type in (dnf.transaction.DOWNGRADE,
                               dnf.transaction.REINSTALL,
                               dnf.transaction.UPGRADE):
                opo = tsi.erased
                opo_yumdb_info = self._yumdb.get_package(opo)
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
            installed = rpmdb_sack.query().installed()._nevra(
                rpo.name, rpo.evr, rpo.arch)
            if len(installed) > 0:
                if not len(just_installed.filter(arch=rpo.arch, name=rpo.name,
                                                 evr=rpo.evr)):
                    msg = _('%s was supposed to be removed but is not!')
                    logger.critical(msg, rpo)
                    count = display_banner(rpo, count)
                    continue
            else:
                self._yumdb.get_package(rpo).clean()
            count = display_banner(rpo, count)
        if self._record_history():
            rpmdbv = rpmdb_sack._rpmdb_version(self._yumdb)
            self.history.end(rpmdbv, 0)
        timer()
        self._trans_success = True

    def download_packages(self, pkglist, progress=None, callback_total=None):
        # :api
        """Download the packages specified by the given list of packages.

        `pkglist` is a list of packages to download, `progress` is an optional
         DownloadProgress instance, `callback_total` an optional callback to
         output messages about the download operation.

        """

        # select and sort packages to download
        if progress is None:
            progress = dnf.callback.NullDownloadProgress()

        lock = dnf.lock.build_download_lock(self.conf.cachedir, self.conf.exit_on_lock)
        with lock:
            drpm = dnf.drpm.DeltaInfo(self.sack.query().installed(),
                                      progress, self.conf.deltarpm_percentage)
            remote_pkgs, local_repository_pkgs = self._select_remote_pkgs(pkglist)
            self._add_tempfiles([pkg.localPkg() for pkg in remote_pkgs])

            payloads = [dnf.repo._pkg2payload(pkg, progress, drpm.delta_factory,
                                             dnf.repo.RPMPayload)
                        for pkg in remote_pkgs]

            beg_download = time.time()
            est_remote_size = sum(pload.download_size for pload in payloads)
            total_drpm = len(
                [payload for payload in payloads if isinstance(payload, dnf.drpm.DeltaPayload)])
            # compatibility part for tools that do not accept total_drpms keyword
            if progress.start.__code__.co_argcount == 4:
                progress.start(len(payloads), est_remote_size, total_drpms=total_drpm)
            else:
                progress.start(len(payloads), est_remote_size)
            errors = dnf.repo._download_payloads(payloads, drpm)

            if errors._irrecoverable:
                raise dnf.exceptions.DownloadError(errors._irrecoverable)

            remote_size = sum(errors._bandwidth_used(pload)
                              for pload in payloads)
            saving = dnf.repo._update_saving((0, 0), payloads,
                                             errors._recoverable)

            retries = self.conf.retries
            forever = retries == 0
            while errors._recoverable and (forever or retries > 0):
                if retries > 0:
                    retries -= 1

                msg = _("Some packages were not downloaded. Retrying.")
                logger.info(msg)

                remaining_pkgs = [pkg for pkg in errors._recoverable]
                payloads = \
                    [dnf.repo._pkg2payload(pkg, progress, dnf.repo.RPMPayload)
                     for pkg in remaining_pkgs]
                est_remote_size = sum(pload.download_size
                                      for pload in payloads)
                progress.start(len(payloads), est_remote_size)
                errors = dnf.repo._download_payloads(payloads, drpm)

                if errors._irrecoverable:
                    raise dnf.exceptions.DownloadError(errors._irrecoverable)

                remote_size += \
                    sum(errors._bandwidth_used(pload) for pload in payloads)
                saving = dnf.repo._update_saving(saving, payloads, {})

            if errors._recoverable:
                msg = dnf.exceptions.DownloadError.errmap2str(
                    errors._recoverable)
                logger.info(msg)

        if callback_total is not None:
            callback_total(remote_size, beg_download)

        (real, full) = saving
        if real != full:
            if real < full:
                msg = _("Delta RPMs reduced %.1f MB of updates to %.1f MB "
                        "(%d.1%% saved)")
            elif real > full:
                msg = _("Failed Delta RPMs increased %.1f MB of updates to %.1f MB "
                        "(%d.1%% wasted)")
            percent = 100 - real / full * 100
            logger.info(msg, full / 1024 ** 2, real / 1024 ** 2, percent)

        if self.conf.destdir:
            for pkg in local_repository_pkgs:
                location = os.path.join(pkg.repo.pkgdir, os.path.basename(pkg.location))
                shutil.copy(location, self.conf.destdir)

    def add_remote_rpms(self, path_list, strict=True):
        # :api
        pkgs = []
        pkgs_error = []
        for path in path_list:
            if not os.path.exists(path) and '://' in path:
                # download remote rpm to a tempfile
                path = dnf.util._urlopen_progress(path, self.conf)
                self._add_tempfiles([path])
            try:
                pkgs.append(self.sack.add_cmdline_package(path))
            except IOError as e:
                logger.warning(e)
                pkgs_error.append(path)
        self._setup_excludes_includes()
        if pkgs_error and strict:
            raise IOError(_("Could not open: {}").format(' '.join(pkgs_error)))
        return pkgs

    def _sig_check_pkg(self, po):
        """Verify the GPG signature of the given package object.

        :param po: the package object to verify the signature of
        :return: (result, error_string)
           where result is::

              0 = GPG signature verifies ok or verification is not required.
              1 = GPG verification failed but installation of the right GPG key
                    might help.
              2 = Fatal GPG verification error, give up.
        """
        if po._from_cmdline:
            check = self.conf.localpkg_gpgcheck
            hasgpgkey = 0
        else:
            repo = self.repos[po.repoid]
            check = repo.gpgcheck
            hasgpgkey = not not repo.gpgkey

        if check:
            root = self.conf.installroot
            ts = dnf.rpm.transaction.initReadOnlyTransaction(root)
            sigresult = dnf.rpm.miscutils.checkSig(ts, po.localPkg())
            localfn = os.path.basename(po.localPkg())
            del ts
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
            result = 0
            msg = ''

        return result, msg

    def _clean_packages(self, packages):
        for fn in packages:
            if not os.path.exists(fn):
                continue
            try:
                misc.unlink_f(fn)
            except OSError:
                logger.warning(_('Cannot remove %s'), fn)
                continue
            else:
                logger.log(dnf.logging.DDEBUG,
                           _('%s removed'), fn)

    def _do_package_lists(self, pkgnarrow='all', patterns=None, showdups=None,
                       ignore_case=False, reponame=None):
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
        :param reponame: limit packages list to the given repository
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
            return self._list_pattern(
                pkgnarrow, patterns, showdups, ignore_case, reponame)

        assert not dnf.util.is_string_type(patterns)
        list_fn = functools.partial(
            self._list_pattern, pkgnarrow, showdups=showdups,
            ignore_case=ignore_case, reponame=reponame)
        if patterns is None or len(patterns) == 0:
            return list_fn(None)
        yghs = map(list_fn, patterns)
        return reduce(lambda a, b: a.merge_lists(b), yghs)

    def _list_pattern(self, pkgnarrow, pattern, showdups, ignore_case,
                      reponame=None):
        def is_from_repo(package):
            """Test whether given package originates from the repository."""
            if reponame is None:
                return True
            return self._yumdb.get_package(package).get('from_repo') == reponame

        def pkgs_from_repo(packages):
            """Filter out the packages which do not originate from the repo."""
            return (package for package in packages if is_from_repo(package))

        def query_for_repo(query):
            """Filter out the packages which do not originate from the repo."""
            if reponame is None:
                return query
            return query.filter(reponame=reponame)

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
        autoremove = []

        # do the initial pre-selection
        ic = ignore_case
        q = self.sack.query()
        if pattern is not None:
            subj = dnf.subject.Subject(pattern, ignore_case=ic)
            q = subj.get_best_query(self.sack, with_provides=False)

        # list all packages - those installed and available:
        if pkgnarrow == 'all':
            dinst = {}
            ndinst = {}  # Newest versions by name.arch
            for po in q.installed():
                dinst[po.pkgtup] = po
                if showdups:
                    continue
                key = (po.name, po.arch)
                if key not in ndinst or po > ndinst[key]:
                    ndinst[key] = po
            installed = list(pkgs_from_repo(dinst.values()))

            avail = query_for_repo(q)
            if not showdups:
                avail = avail.latest()
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
            updates = query_for_repo(q).upgrades()
            # reduce a query to security upgrades if they are specified
            updates = self._merge_update_filters(updates)
            # reduce a query to latest packages
            updates = updates.latest().run()

        # installed only
        elif pkgnarrow == 'installed':
            installed = list(pkgs_from_repo(q.installed()))

        # available in a repository
        elif pkgnarrow == 'available':
            if showdups:
                avail = query_for_repo(q).available()
                installed_dict = q.installed()._na_dict()
                for avail_pkg in avail:
                    key = (avail_pkg.name, avail_pkg.arch)
                    installed_pkgs = installed_dict.get(key, [])
                    same_ver = [pkg for pkg in installed_pkgs
                                if pkg.evr == avail_pkg.evr]
                    if len(same_ver) > 0:
                        reinstall_available.append(avail_pkg)
                    else:
                        available.append(avail_pkg)
            else:
                # we will only look at the latest versions of packages:
                available_dict = query_for_repo(
                    q).available().latest()._na_dict()
                installed_dict = q.installed().latest()._na_dict()
                for (name, arch) in available_dict:
                    avail_pkg = available_dict[(name, arch)][0]
                    inst_pkg = installed_dict.get((name, arch), [None])[0]
                    if not inst_pkg or avail_pkg.evr_gt(inst_pkg):
                        available.append(avail_pkg)
                    elif avail_pkg.evr_eq(inst_pkg):
                        reinstall_available.append(avail_pkg)
                    else:
                        old_available.append(avail_pkg)

        # packages to be removed by autoremove
        elif pkgnarrow == 'autoremove':
            autoremove_q = query_for_repo(q)._unneeded(self.sack, self._yumdb)
            autoremove = autoremove_q.run()

        # not in a repo but installed
        elif pkgnarrow == 'extras':
            extras = [pkg for pkg in q.extras() if is_from_repo(pkg)]

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            inst = q.installed()
            obsoletes = query_for_repo(
                self.sack.query()).filter(obsoletes=inst)
            # reduce a query to security upgrades if they are specified
            obsoletes = self._merge_update_filters(obsoletes, warning=False)
            obsoletesTuples = []
            for new in obsoletes:
                obsoleted_reldeps = new.obsoletes
                obsoletesTuples.extend(
                    [(new, old) for old in
                     inst.filter(provides=obsoleted_reldeps)])

        # packages recently added to the repositories
        elif pkgnarrow == 'recent':
            avail = q.available()
            if not showdups:
                avail = avail.latest()
            recent = query_for_repo(avail)._recent(self.conf.recent)

        ygh.installed = installed
        ygh.available = available
        ygh.reinstall_available = reinstall_available
        ygh.old_available = old_available
        ygh.updates = updates
        ygh.obsoletes = obsoletes
        ygh.obsoletesTuples = obsoletesTuples
        ygh.recent = recent
        ygh.extras = extras
        ygh.autoremove = autoremove

        return ygh

    def _add_comps_trans(self, trans):
        self._comps_trans += trans
        return len(trans)

    def _remove_if_unneeded(self, query):
        """
        Mark to remove packages that are not required by any user installed package (reason group
        or user)
        :param query: dnf.query.Query() object
        """
        query = query.installed()
        if not query:
            return

        for pkg in query:
            reason = self._yumdb.get_package(pkg).reason
            self._yumdb.get_package(pkg).reason = 'dep'
            self._revert_reason.append((pkg, reason))
        unneeded_pkgs = self.sack.query()._unneeded(self.sack, self._yumdb, debug_solver=False)
        remove_packages = query.intersection(unneeded_pkgs)
        if remove_packages:
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=remove_packages)
            self._goal.erase(select=sltr, clean_deps=self.conf.clean_requirements_on_remove)

    def _finalize_comps_trans(self):
        trans = self._comps_trans
        basearch = self.conf.substitutions['basearch']

        def conditional_pkg_check(pkg):
            """
            If package is conditional it checks if transaction fulfills condition
            :param pkg:
            :return: True if the package should be installed
            """
            if not pkg.requires:
                return True
            installed = self.sack.query().installed().filter(name=pkg.requires).run()
            return len(installed) > 0 or \
                pkg.requires in (pkg.name for pkg in self._goal._installs) or \
                pkg.requires in [pkg.name for pkg in trans.install]

        def trans_upgrade(query, remove_query, pkg):
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=query)
            self._goal.upgrade(select=sltr)
            return remove_query

        def trans_install(query, remove_query, pkg):
            if self.conf.multilib_policy == "all":
                # can provide different suggestion for conditional package in comparison to
                # "best" policy
                if conditional_pkg_check(pkg):
                    self._install_multiarch(query, strict=False)

            else:
                sltr = dnf.selector.Selector(self.sack)
                if pkg.requires:
                    sltr.set(provides="({} if {})".format(pkg.name, pkg.requires))
                else:
                    sltr.set(pkg=query)
                self._goal.install(select=sltr, optional=True)
            return remove_query

        def trans_remove(query, remove_query, pkg):
            remove_query = remove_query.union(query)
            return remove_query

        remove_query = self.sack.query().filter(empty=True)
        attr_fn = ((trans.install, trans_install),
                   (trans.upgrade, trans_upgrade),
                   (trans.remove, trans_remove))

        for (attr, fn) in attr_fn:
            for pkg in attr:
                query_args = {'name': pkg.name}
                if (pkg.basearchonly):
                    query_args.update({'arch': basearch})
                q = self.sack.query().filter(**query_args).apply()
                if not q:
                    package_string = pkg.name
                    if pkg.basearchonly:
                        package_string += '.' + basearch
                    logger.warning(_('No match for group package "{}"').format(package_string))
                    continue
                q = q.filter(arch__neq="src")
                remove_query = fn(q, remove_query, pkg)
                self._goal.group_members.add(pkg.name)

        self._remove_if_unneeded(remove_query)

    def _build_comps_solver(self):
        def reason_fn(pkgname):
            q = self.sack.query().installed().filter(name=pkgname)
            if not q:
                return None
            try:
                return self._yumdb.get_package(q[0]).reason
            except AttributeError:
                return 'unknown'

        return dnf.comps.Solver(self._group_persistor, self._comps, reason_fn)

    def environment_install(self, env_id, types, exclude=None, strict=True):
        solver = self._build_comps_solver()
        types = self._translate_comps_pkg_types(types)
        trans = dnf.comps.install_or_skip(solver._environment_install,
                                          env_id, types, exclude or set(),
                                          strict)
        if not trans:
            return 0
        return self._add_comps_trans(trans)

    def environment_remove(self, env_id):
        solver = self._build_comps_solver()
        trans = solver._environment_remove(env_id)
        return self._add_comps_trans(trans)

    _COMPS_TRANSLATION = {
        'default': dnf.comps.DEFAULT,
        'mandatory': dnf.comps.MANDATORY,
        'optional': dnf.comps.OPTIONAL,
        'conditional': dnf.comps.CONDITIONAL
    }

    @staticmethod
    def _translate_comps_pkg_types(pkg_types):
        ret = 0
        for (name, enum) in Base._COMPS_TRANSLATION.items():
            if name in pkg_types:
                ret |= enum
        return ret

    def group_install(self, grp_id, pkg_types, exclude=None, strict=True):
        # :api
        """Installs packages of selected group
        :param exclude: list of package name glob patterns
            that will be excluded from install set
        """
        def _pattern_to_pkgname(pattern):
            if dnf.util.is_glob_pattern(pattern):
                q = self.sack.query().filter(name__glob=pattern)
                return map(lambda p: p.name, q)
            else:
                return (pattern,)

        exclude_pkgnames = None
        if exclude:
            nested_excludes = [_pattern_to_pkgname(p) for p in exclude]
            exclude_pkgnames = itertools.chain.from_iterable(nested_excludes)

        solver = self._build_comps_solver()
        pkg_types = self._translate_comps_pkg_types(pkg_types)
        trans = dnf.comps.install_or_skip(solver._group_install,
                                          grp_id, pkg_types, exclude_pkgnames,
                                          strict)
        if not trans:
            return 0
        logger.debug("Adding packages from group '%s': %s",
                     grp_id, trans.install)
        return self._add_comps_trans(trans)

    def env_group_install(self, patterns, types, strict=True):
        q = CompsQuery(self.comps, self._group_persistor,
                       CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS,
                       CompsQuery.AVAILABLE | CompsQuery.INSTALLED)
        cnt = 0
        done = True
        for pattern in patterns:
            try:
                res = q.get(pattern)
            except dnf.exceptions.CompsError as err:
                logger.error("Warning: Module or %s", ucd(err))
                done = False
                continue
            for group_id in res.groups:
                cnt += self.group_install(group_id, types, strict=strict)
            for env_id in res.environments:
                cnt += self.environment_install(env_id, types, strict=strict)
        if not done and strict:
            self._group_persistor._rollback()
            raise dnf.exceptions.Error(_('Nothing to do.'))
        return cnt

    def group_remove(self, grp_id):
        solver = self._build_comps_solver()
        trans = solver._group_remove(grp_id)
        return self._add_comps_trans(trans)

    def env_group_remove(self, patterns):
        q = CompsQuery(self.comps, self._group_persistor,
                       CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS,
                       CompsQuery.INSTALLED)
        try:
            res = q.get(*patterns)
        except dnf.exceptions.CompsError as err:
            logger.error("Warning: %s", ucd(err))
            raise dnf.exceptions.Error(_('No groups marked for removal.'))
        cnt = 0
        for env in res.environments:
            cnt += self.environment_remove(env)
        for grp in res.groups:
            cnt += self.group_remove(grp)
        return cnt

    def env_group_upgrade(self, patterns):
        q = CompsQuery(self.comps, self._group_persistor,
                       CompsQuery.GROUPS | CompsQuery.ENVIRONMENTS,
                       CompsQuery.INSTALLED)
        res = q.get(*patterns)
        cnt = 0
        for env in res.environments:
            cnt += self.environment_upgrade(env)
        for grp in res.groups:
            cnt += self.group_upgrade(grp)
        if not cnt:
            msg = _('No group marked for upgrade.')
            raise dnf.cli.CliError(msg)

    def environment_upgrade(self, env_id):
        solver = self._build_comps_solver()
        trans = solver._environment_upgrade(env_id)
        return self._add_comps_trans(trans)

    def group_upgrade(self, grp_id):
        solver = self._build_comps_solver()
        trans = solver._group_upgrade(grp_id)
        return self._add_comps_trans(trans)

    def _gpg_key_check(self):
        """Checks for the presence of GPG keys in the rpmdb.

        :return: 0 if there are no GPG keys in the rpmdb, and 1 if
           there are keys
        """
        gpgkeyschecked = self.conf.cachedir + '/.gpgkeyschecked.yum'
        if os.path.exists(gpgkeyschecked):
            return 1

        installroot = self.conf.installroot
        myts = dnf.rpm.transaction.initReadOnlyTransaction(root=installroot)
        myts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))
        idx = myts.dbMatch('name', 'gpg-pubkey')
        keys = len(idx)
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

    def _install_multiarch(self, query, reponame=None, strict=True):
        already_inst, available = self._query_matches_installed(query)
        for i in already_inst:
            _msg_installed(i)
        for a in available:
            sltr = dnf.selector.Selector(self.sack)
            sltr = sltr.set(pkg=a)
            if reponame is not None:
                sltr = sltr.set(reponame=reponame)
            self._goal.install(select=sltr, optional=(not strict))
        return len(available)

    def install_module(self, specs):
        skipped_specs = specs
        try:
            skipped_specs = self.repo_module_dict.install(specs)
        except NoModuleException:
            self.repo_module_dict.install(specs[1:])

        return skipped_specs

    def install(self, pkg_spec, reponame=None, strict=True, forms=None):
        # :api
        """Mark package(s) given by pkg_spec and reponame for installation."""

        subj = dnf.subject.Subject(pkg_spec)
        solution = subj._get_nevra_solution(self.sack, forms=forms)

        if self.conf.multilib_policy == "all" or subj._is_arch_specified(solution):
            q = solution['query'].filter(arch__neq="src")
            if reponame is not None:
                q = q.filter(reponame=reponame)
            if not q:
                raise dnf.exceptions.PackageNotFoundError(
                    _('no package matched'), pkg_spec)
            return self._install_multiarch(q, reponame=reponame, strict=strict)

        elif self.conf.multilib_policy == "best":
            sltrs = subj._get_best_selectors(self,
                                             forms=forms,
                                             obsoletes=self.conf.obsoletes,
                                             reponame=reponame,
                                             reports=True,
                                             solution=solution)
            if not sltrs:
                raise dnf.exceptions.MarkingError(_('no package matched'), pkg_spec)

            for sltr in sltrs:
                self._goal.install(select=sltr, optional=(not strict))
            return 1
        return 0

    def package_downgrade(self, pkg, strict=False):
        # :api
        if pkg._from_system:
            msg = 'downgrade_package() for an installed package.'
            raise NotImplementedError(msg)

        q = self.sack.query().installed().filter(name=pkg.name, arch=[pkg.arch, "noarch"])
        if not q:
            msg = _("Package %s not installed, cannot downgrade it.")
            logger.warning(msg, pkg.name)
            raise dnf.exceptions.MarkingError(_('No match for argument: %s') % pkg.location, pkg.name)
        elif sorted(q)[0] > pkg:
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=[pkg])
            self._goal.downgrade_to(select=sltr, optional=(not strict))
            return 1
        else:
            msg = _("Package %s of lower version already installed, "
                    "cannot downgrade it.")
            logger.warning(msg, pkg.name)
            return 0

    def package_install(self, pkg, strict=True):
        # :api
        q = self.sack.query()._nevra(pkg.name, pkg.evr, pkg.arch)
        already_inst, available = self._query_matches_installed(q)
        if pkg in already_inst:
            _msg_installed(pkg)
        elif pkg not in itertools.chain.from_iterable(available):
            raise dnf.exceptions.PackageNotFoundError(_('No match for argument: %s'), pkg.location)
        else:
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=[pkg])
            self._goal.install(select=sltr, optional=(not strict))
        return 1

    def package_reinstall(self, pkg):
        if self.sack.query().installed().filter(nevra=str(pkg)):
            self._goal.install(pkg)
            return 1
        msg = _("Package %s not installed, cannot reinstall it.")
        logger.warning(msg, str(pkg))
        raise dnf.exceptions.MarkingError(_('No match for argument: %s') % pkg.location, pkg.name)

    def package_remove(self, pkg):
        self._goal.erase(pkg)
        return 1

    def package_upgrade(self, pkg):
        # :api
        if pkg._from_system:
            msg = 'upgrade_package() for an installed package.'
            raise NotImplementedError(msg)

        if pkg.arch == 'src':
            msg = _("File %s is a source package and cannot be updated, ignoring.")
            logger.info(msg, pkg.location)
            return 0

        q = self.sack.query().installed().filter(name=pkg.name, arch=[pkg.arch, "noarch"])
        if not q:
            msg = _("Package %s not installed, cannot update it.")
            logger.warning(msg, pkg.name)
            raise dnf.exceptions.MarkingError(_('No match for argument: %s') % pkg.location, pkg.name)
        elif sorted(q)[-1] < pkg:
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=[pkg])
            self._goal.upgrade(select=sltr)
            return 1
        else:
            msg = _("Package %s of higher version already installed, "
                    "cannot update it.")
            logger.warning(msg, pkg.name)
            return 0

    def upgrade(self, pkg_spec, reponame=None):
        # :api
        subj = dnf.subject.Subject(pkg_spec)
        solution = subj._get_nevra_solution(self.sack)
        q = solution["query"]
        if q:
            wildcard = dnf.util.is_glob_pattern(pkg_spec)
            # wildcard shouldn't print not installed packages
            # only solution with nevra.name provide packages with same name
            if not wildcard and solution['nevra'] and solution['nevra'].name:
                installed = self.sack.query().installed()
                pkg_name = q[0].name
                installed = installed.filter(name=pkg_name).apply()
                if not installed:
                    msg = _('Package %s available, but not installed.')
                    logger.warning(msg, pkg_name)
                    raise dnf.exceptions.PackagesNotInstalledError(
                        _('No match for argument: %s') % pkg_spec, pkg_spec)
                if solution['nevra'].arch and not dnf.util.is_glob_pattern(solution['nevra'].arch):
                    if not installed.filter(arch=solution['nevra'].arch):
                        msg = _('Package %s available, but installed for different architecture.')
                        logger.warning(msg, "{}.{}".format(pkg_name, solution['nevra'].arch))

            if solution['nevra'] and solution['nevra'].has_just_name() and self.conf.obsoletes:
                obsoletes = self.sack.query().filter(obsoletes=q.installed())
                q = q.upgrades()
                # add obsoletes into transaction
                q = q.union(obsoletes)
            else:
                q = q.upgrades()
            if reponame is not None:
                q = q.filter(reponame=reponame)
            q = self._merge_update_filters(q, pkg_spec=pkg_spec)
            if q:
                sltr = dnf.selector.Selector(self.sack)
                sltr.set(pkg=q)
                self._goal.upgrade(select=sltr)
            return 1

        raise dnf.exceptions.MarkingError(_('No match for argument: %s') % pkg_spec, pkg_spec)

    def upgrade_all(self, reponame=None):
        # :api
        if reponame is None and not self._update_security_filters and \
                not self.repo_module_dict:
            self._goal.upgrade_all()
        else:
            module_query, query_exclude = self.repo_module_dict.upgrade_all()

            q = self.sack.query().upgrades()
            if module_query:
                q = q.union(module_query)
            if query_exclude:
                q = q.difference(query_exclude)

            # add obsoletes into transaction
            if self.conf.obsoletes:
                q = q.union(self.sack.query().filter(obsoletes=self.sack.query().installed()))
            if reponame is not None:
                q = q.filter(reponame=reponame)
            q = self._merge_update_filters(q)
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=q)
            self._goal.upgrade(select=sltr)
        return 1

    def distro_sync(self, pkg_spec=None):
        if pkg_spec is None:
            self._goal.distupgrade_all()
        else:
            sltrs = dnf.subject.Subject(pkg_spec) \
                       ._get_best_selectors(self, obsoletes=self.conf.obsoletes, reports=True)
            if not sltrs:
                logger.info(_('No package %s installed.'), pkg_spec)
                return 0
            for sltr in sltrs:
                self._goal.distupgrade(select=sltr)
        return 1

    def autoremove(self, forms=None, pkg_specs=None, grp_specs=None, filenames=None):
        # :api
        """Removes all 'leaf' packages from the system that were originally
        installed as dependencies of user-installed packages but which are
        no longer required by any such package."""

        if any([grp_specs, pkg_specs, filenames]):
            pkg_specs += filenames
            done = False
            # Remove groups.
            if grp_specs and forms:
                for grp_spec in grp_specs:
                    msg = _('Not a valid form: %s')
                    logger.warning(msg, self.output.term.bold(grp_spec))
            elif grp_specs:
                self.read_comps(arch_filter=True)
                if self.env_group_remove(grp_specs):
                    done = True

            for pkg_spec in pkg_specs:
                try:
                    self.remove(pkg_spec, forms=forms)
                except dnf.exceptions.MarkingError:
                    logger.info(_('No match for argument: %s'),
                                pkg_spec)
                else:
                    done = True

            if not done:
                raise dnf.exceptions.Error(_('No packages marked for removal.'))

        else:
            pkgs = self.sack.query()._unneeded(self.sack, self._yumdb,
                                               debug_solver=self.conf.debug_solver)
            for pkg in pkgs:
                self.package_remove(pkg)

    def remove(self, pkg_spec, reponame=None, forms=None):
        # :api
        """Mark the specified package for removal."""

        matches = dnf.subject.Subject(pkg_spec).get_best_query(self.sack, forms=forms)
        installed = [
            pkg for pkg in matches.installed()
            if reponame is None or
            self._yumdb.get_package(pkg).get('from_repo') == reponame]
        if not installed:
            raise dnf.exceptions.PackagesNotInstalledError(
                'no package matched', pkg_spec)

        clean_deps = self.conf.clean_requirements_on_remove
        for pkg in installed:
            self._goal.erase(pkg, clean_deps=clean_deps)
        return len(installed)

    def reinstall(self, pkg_spec, old_reponame=None, new_reponame=None,
                  new_reponame_neq=None, remove_na=False):
        subj = dnf.subject.Subject(pkg_spec)
        q = subj.get_best_query(self.sack)
        installed_pkgs = [
            pkg for pkg in q.installed()
            if old_reponame is None or
            self._yumdb.get_package(pkg).get('from_repo') == old_reponame]

        available_q = q.available()
        if new_reponame is not None:
            available_q = available_q.filter(reponame=new_reponame)
        if new_reponame_neq is not None:
            available_q = available_q.filter(reponame__neq=new_reponame_neq)
        available_nevra2pkg = dnf.query._per_nevra_dict(available_q)

        if not installed_pkgs:
            raise dnf.exceptions.PackagesNotInstalledError(
                'no package matched', pkg_spec, available_nevra2pkg.values())

        cnt = 0
        clean_deps = self.conf.clean_requirements_on_remove
        for installed_pkg in installed_pkgs:
            try:
                available_pkg = available_nevra2pkg[ucd(installed_pkg)]
            except KeyError:
                if not remove_na:
                    continue
                self._goal.erase(installed_pkg, clean_deps=clean_deps)
            else:
                self._goal.install(available_pkg)
            cnt += 1

        if cnt == 0:
            raise dnf.exceptions.PackagesNotAvailableError(
                'no package matched', pkg_spec, installed_pkgs)

        return cnt

    def downgrade(self, pkg_spec):
        # :api
        """Mark a package to be downgraded.

        This is equivalent to first removing the currently installed package,
        and then installing an older version.

        """
        return self.downgrade_to(pkg_spec)

    def downgrade_to(self, pkg_spec, strict=False):
        """Downgrade to specific version if specified otherwise downgrades
        to one version lower than the package installed.
        """
        subj = dnf.subject.Subject(pkg_spec)
        q = subj.get_best_query(self.sack, with_nevra=True, with_provides=False,
                                with_filenames=False)
        if not q:
            msg = _('No match for argument: %s') % pkg_spec
            raise dnf.exceptions.PackageNotFoundError(msg, pkg_spec)
        done = 0
        available_pkgs = q.available()
        available_pkg_names = list(available_pkgs._name_dict().keys())
        q_installed = self.sack.query().installed().filter(name=available_pkg_names)
        if len(q_installed) == 0:
            msg = _('Packages for argument %s available, but not installed.') % pkg_spec
            raise dnf.exceptions.PackagesNotInstalledError(msg, pkg_spec, available_pkgs)
        for pkg_name in q_installed._name_dict().keys():
            downgrade_pkgs = available_pkgs.downgrades().latest().filter(name=pkg_name)
            if not downgrade_pkgs:
                msg = _("Package %s of lowest version already installed, cannot downgrade it.")
                logger.warning(msg, pkg_name)
                continue
            sltr = dnf.selector.Selector(self.sack)
            sltr.set(pkg=downgrade_pkgs)
            self._goal.downgrade_to(select=sltr, optional=(not strict))
            done = 1
        return done

    def provides(self, provides_spec):
        providers = self.sack.query().filter(file__glob=provides_spec)
        if providers:
            return providers, [provides_spec]
        providers = dnf.query._by_provides(self.sack, provides_spec)
        if providers:
            return providers, [provides_spec]
        binary_provides = [prefix + provides_spec for prefix in ['/usr/bin/', '/usr/sbin/']]
        return self.sack.query().filter(file__glob=binary_provides), binary_provides

    def _history_undo_operations(self, operations, first_trans, rollback=False):
        """Undo the operations on packages by their NEVRAs.

        :param operations: a NEVRAOperations to be undone
        :param first_trans: first transaction id being undone
        :param rollback: True if transaction is performing a rollback
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        def handle_downgrade(new_nevra, old_nevra, obsoleted_nevras):
            """Handle a downgraded package."""
            news = self.sack.query().installed()._nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available()._nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            assert len(news) == 1
            self._transaction.add_upgrade(first(olds), news[0], None)
            for obsoleted_nevra in obsoleted_nevras:
                handle_erase(obsoleted_nevra)

        def handle_erase(old_nevra):
            """Handle an erased package."""
            pkgs = self.sack.query().available()._nevra(old_nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            new_pkg = first(pkgs)
            old_reason = self.history.get_erased_reason(new_pkg, first_trans, rollback)
            self._transaction.add_install(new_pkg, None, old_reason)

        def handle_install(new_nevra, obsoleted_nevras):
            """Handle an installed package."""
            pkgs = self.sack.query().installed()._nevra(new_nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            assert len(pkgs) == 1
            self._transaction.add_erase(pkgs[0])
            for obsoleted_nevra in obsoleted_nevras:
                handle_erase(obsoleted_nevra)

        def handle_reinstall(new_nevra, old_nevra, obsoleted_nevras):
            """Handle a reinstalled package."""
            news = self.sack.query().installed()._nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available()._nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            obsoleteds = []
            for nevra in obsoleted_nevras:
                obsoleteds_ = self.sack.query().installed()._nevra(nevra)
                if obsoleteds_:
                    assert len(obsoleteds_) == 1
                    obsoleteds.append(obsoleteds_[0])
            assert len(news) == 1
            self._transaction.add_reinstall(first(olds), news[0],
                                            obsoleteds)

        def handle_upgrade(new_nevra, old_nevra, obsoleted_nevras):
            """Handle an upgraded package."""
            news = self.sack.query().installed()._nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available()._nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            assert len(news) == 1
            self._transaction.add_downgrade(
                first(olds), news[0], None)
            for obsoleted_nevra in obsoleted_nevras:
                handle_erase(obsoleted_nevra)

        # Build the transaction directly, because the depsolve is not needed.
        self._transaction = dnf.transaction.Transaction()
        for state, nevra, replaced_nevra, obsoleted_nevras in operations:
            if state == 'Install':
                assert not replaced_nevra
                handle_install(nevra, obsoleted_nevras)
            elif state == 'Erase':
                assert not replaced_nevra and not obsoleted_nevras
                handle_erase(nevra)
            elif state == 'Reinstall':
                handle_reinstall(nevra, replaced_nevra, obsoleted_nevras)
            elif state == 'Downgrade':
                handle_downgrade(nevra, replaced_nevra, obsoleted_nevras)
            elif state == 'Update':
                handle_upgrade(nevra, replaced_nevra, obsoleted_nevras)
            else:
                assert False

    def _merge_update_filters(self, q, pkg_spec=None, warning=True):
        """
        Merge Queries in _update_filters and return intersection with q Query
        @param q: Query
        @return: Query
        """
        if not self._update_security_filters or not q:
            return q
        assert len(self._update_security_filters.keys()) == 1
        for key, filters in self._update_security_filters.items():
            assert len(filters) > 0
            t = filters[0]
            for query in filters[1:]:
                t = t.union(query)
            del self._update_security_filters[key]
            self._update_security_filters['minimal'] = [t]
            t = q.intersection(t)
            if len(t) == 0 and warning:
                count = len(q._name_dict().keys())
                if pkg_spec is None:
                    msg1 = _("No security updates needed, but {} update "
                             "available").format(count)
                    msg2 = _("No security updates needed, but {} updates "
                             "available").format(count)
                    logger.warning(P_(msg1, msg2, count))
                else:
                    msg1 = _('No security updates needed for "{}", but {} '
                             'update available').format(pkg_spec, count)
                    msg2 = _('No security updates needed for "{}", but {} '
                             'updates available').format(pkg_spec, count)
                    logger.warning(P_(msg1, msg2, count))
                return t
            if key == 'minimal':
                return t
            else:
                # return all packages with eq or higher version
                latest_pkgs = None
                pkgs_dict = t._name_dict()
                for pkg_list in pkgs_dict.values():
                    pkg_list.sort()
                    pkg = pkg_list[0]
                    if latest_pkgs is None:
                        latest_pkgs = q.filter(name=pkg.name, evr__gte=pkg.evr)
                    else:
                        latest_pkgs = latest_pkgs.union(q.filter(
                            name=pkg.name, evr__gte=pkg.evr))
                return latest_pkgs

    def _get_key_for_package(self, po, askcb=None, fullaskcb=None):
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
        key_installed = repo.id in self._repo_set_imported_gpg_keys
        keyurls = [] if key_installed else repo.gpgkey

        def _prov_key_data(msg):
            msg += _('. Failing package is: %s') % (po) + '\n '
            msg += _('GPG Keys are configured as: %s') % \
                    (', '.join(repo.gpgkey))
            return msg

        user_cb_fail = False
        self._repo_set_imported_gpg_keys.add(repo.id)
        for keyurl in keyurls:
            keys = dnf.crypto.retrieve(keyurl, repo)

            for info in keys:
                # Check if key is already installed
                if misc.keyInstalled(self._ts, info.rpm_id, info.timestamp) >= 0:
                    msg = _('GPG key at %s (0x%s) is already installed')
                    logger.info(msg, keyurl, info.short_id)
                    continue

                # Try installing/updating GPG key
                info.url = keyurl
                dnf.crypto.log_key_import(info)
                rc = False
                if self.conf.assumeno:
                    rc = False
                elif self.conf.assumeyes:
                    rc = True

                # grab the .sig/.asc for the keyurl, if it exists if it
                # does check the signature on the key if it is signed by
                # one of our ca-keys for this repo or the global one then
                # rc = True else ask as normal.

                elif fullaskcb:
                    rc = fullaskcb({"po": po, "userid": info.userid,
                                    "hexkeyid": info.short_id,
                                    "keyurl": keyurl,
                                    "fingerprint": info.fingerprint,
                                    "timestamp": info.timestamp})
                elif askcb:
                    rc = askcb(po, info.userid, info.short_id)

                if not rc:
                    user_cb_fail = True
                    continue

                # Import the key
                # If rpm.RPMTRANS_FLAG_TEST in self._ts, gpg keys cannot be imported successfully
                # therefore the new instance of dnf.rpm.transaction.TransactionWrapper is used'
                ts_import_instance = dnf.rpm.transaction.TransactionWrapper(self.conf.installroot)
                result = ts_import_instance.pgpImportPubkey(misc.procgpgkey(info.raw_key))
                if result != 0:
                    msg = _('Key import failed (code %d)') % result
                    raise dnf.exceptions.Error(_prov_key_data(msg))
                logger.info(_('Key imported successfully'))
                key_installed = True

        if not key_installed and user_cb_fail:
            raise dnf.exceptions.Error(_("Didn't install any keys"))

        if not key_installed:
            msg = _('The GPG keys listed for the "%s" repository are '
                    'already installed but they are not correct for this '
                    'package.\n'
                    'Check that the correct key URLs are configured for '
                    'this repository.') % repo.name
            raise dnf.exceptions.Error(_prov_key_data(msg))

        # Check if the newly installed keys helped
        result, errmsg = self._sig_check_pkg(po)
        if result != 0:
            if keyurls:
                msg = _("Import of key(s) didn't help, wrong key(s)?")
                logger.info(msg)
            errmsg = ucd(errmsg)
            raise dnf.exceptions.Error(_prov_key_data(errmsg))

    def _run_rpm_check(self):
        results = []
        self._ts.check()
        for prob in self._ts.problems():
            #  Newer rpm (4.8.0+) has problem objects, older have just strings.
            #  Should probably move to using the new objects, when we can. For
            # now just be compatible.
            results.append(ucd(prob))

        return results

    def _store_config_in_history(self):
        self.history.write_addon_data('config-main', self.conf.dump())
        myrepos = ''
        for repo in self.repos.iter_enabled():
            myrepos += repo.dump()
            myrepos += '\n'
        self.history.write_addon_data('config-repos', myrepos)

    def _store_comment_in_history(self, comment):
        self.history.write_addon_data('transaction-comment', comment)

    def urlopen(self, url, repo=None, mode='w+b', **kwargs):
        # :api
        """
        Open the specified absolute url, return a file object
        which respects proxy setting even for non-repo downloads
        """
        return dnf.util._urlopen(url, self.conf, repo, mode, **kwargs)

    def _get_installonly_query(self, q=None):
        if q is None:
            q = self._sack.query()
        installonly = q.filter(provides=self.conf.installonlypkgs)
        return installonly

    def _report_icase_hint(self, pkg_spec):
        subj = dnf.subject.Subject(pkg_spec, ignore_case=True)
        solution = subj._get_nevra_solution(self.sack, with_nevra=True, with_provides=False,
                                            with_filenames=False)
        if solution['query'] and solution['nevra'] and solution['nevra'].name:
            logger.info(_("  * Maybe you meant: {}").format(solution['query'][0].name))

    def _select_remote_pkgs(self, install_pkgs):
        """ Check checksum of packages from local repositories and returns list packages from remote
        repositories that will be downloaded. Packages from commandline are skipped.

        :param install_pkgs: list of packages
        :return: list of remote pkgs
        """
        def _verification_of_packages(pkg_list, logger_msg):
            for pkg in pkg_list:
                if not pkg.verifyLocalPkg():
                    logger.critical(logger_msg)
                    return False
            return True

        remote_pkgs = []
        local_repository_pkgs = []
        for pkg in install_pkgs:
            if pkg._is_local_pkg():
                if pkg.reponame != hawkey.CMDLINE_REPO_NAME:
                    local_repository_pkgs.append(pkg)
            else:
                remote_pkgs.append(pkg)
        error = False

        try:
            msg = _('Package "{}" from local repository "{}" has incorrect checksum')
            if not _verification_of_packages(local_repository_pkgs, msg.format(pkg, pkg.reponame)):
                error = True
        except Exception as e:
            logger.critical(str(e))
            error = True

        if error:
            raise dnf.exceptions.Error(
                _("Some packages from local repository have incorrect checksum"))

        if self.conf.cacheonly:
            try:
                msg = _('Package "{}" from repository "{}" has incorrect checksum')
                if not _verification_of_packages(remote_pkgs, msg.format(pkg, pkg.reponame)):
                    error = True
            except Exception as e:
                logger.debug(str(e))
                msg = _('Package "{}" from repository "{}" has invalid cache')
                logger.critical(msg.format(pkg, pkg.reponame))
                error = True

            if error:
                raise dnf.exceptions.Error(
                    _('Some packages have invalid cache, but cannot be downloaded due to '
                      '"--cacheonly" option'))
            remote_pkgs = []

        return remote_pkgs, local_repository_pkgs


def _msg_installed(pkg):
    name = ucd(pkg)
    msg = _('Package %s is already installed, skipping.')
    logger.warning(msg, name)
