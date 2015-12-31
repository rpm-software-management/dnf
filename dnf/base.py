# Copyright 2005 Duke University
# Copyright (C) 2012-2015  Red Hat, Inc.
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
from dnf.util import first
from dnf.yum import history
from dnf.yum import misc
from dnf.yum import rpmsack
from functools import reduce
import collections
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
import dnf.yum.config
import dnf.yum.rpmtrans
import functools
import hawkey
import itertools
import logging
import os
import operator
import re
import rpm
import time

logger = logging.getLogger("dnf")


class Base(object):

    def __init__(self, conf=None):
        # :api
        self._closed = False
        self._conf = conf or self._setup_default_conf()
        self._goal = None
        self.repo_persistor = None
        self._sack = None
        self._transaction = None
        self._ts = None
        self._comps = None
        self._history = None
        self._tempfiles = set()
        self._trans_tempfiles = set()
        self.ds_callback = dnf.callback.Depsolve()
        self._group_persistor = None
        self.logging = dnf.logging.Logging()
        self._repos = dnf.repodict.RepoDict()
        self.rpm_probfilter = set([rpm.RPMPROB_FILTER_OLDPACKAGE])
        self.plugins = dnf.plugin.Plugins()
        self.trans_success = False
        self._tempfile_persistor = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_args):
        self.close()

    def _add_tempfiles(self, files):
        if self._transaction:
            self._trans_tempfiles.update(files)
        else:
            self._tempfiles.update(files)

    def _add_repo_to_sack(self, name):
        repo = self.repos[name]
        try:
            repo.load()
        except dnf.exceptions.RepoError as e:
            repo.md_expire_cache()
            if repo.skip_if_unavailable is False:
                raise
            logger.warning(_("%s, disabling."), e)
            repo.disable()
            return
        hrepo = repo.hawkey_repo
        hrepo.repomd_fn = repo.repomd_fn
        hrepo.primary_fn = repo.primary_fn
        hrepo.filelists_fn = repo.filelists_fn
        hrepo.cost = repo.cost
        if repo.presto_fn:
            hrepo.presto_fn = repo.presto_fn
        else:
            logger.debug("not found deltainfo for: %s", repo.name)
        if repo.updateinfo_fn:
            hrepo.updateinfo_fn = repo.updateinfo_fn
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
        cache_dirs = dnf.conf.CliCache(conf.cachedir)

        conf.cachedir = cache_dirs.cachedir
        return conf

    def _setup_excludes_includes(self):
        disabled = set(self.conf.disable_excludes)
        if 'all' in disabled:
            return
        if 'main' not in disabled:
            for excl in self.conf.exclude:
                subj = dnf.subject.Subject(excl)
                pkgs = subj.get_best_query(self.sack)
                self.sack.add_excludes(pkgs)
            for incl in self.conf.include:
                subj = dnf.subject.Subject(incl)
                pkgs = subj.get_best_query(self.sack)
                self.sack.add_includes(pkgs)
        for r in self.repos.iter_enabled():
            if r.id in disabled:
                continue
            for excl in r.exclude:
                pkgs = self.sack.query().filter(reponame=r.id).\
                    filter_autoglob(name=excl)
                self.sack.add_excludes(pkgs)
            for incl in r.include:
                pkgs = self.sack.query().filter(reponame=r.id).\
                    filter_autoglob(name=incl)
                self.sack.add_includes(pkgs)

    def _store_persistent_data(self):
        def check_expired(repo):
            try:
                exp_remaining = repo.metadata_expire_in()[1]
                return False if exp_remaining is None else exp_remaining <= 0
            except dnf.exceptions.MetadataError:
                return False

        if self.repo_persistor:
            expired = [r.id for r in self.repos.iter_enabled()
                       if check_expired(r)]
            self.repo_persistor.set_expired_repos(expired)

        if self._group_persistor:
            self._group_persistor.save()

        if self._tempfile_persistor:
            self._tempfile_persistor.save()

    @property
    def comps(self):
        # :api
        return self._comps

    @property
    def conf(self):
        # :api
        return self._conf

    @property
    def goal(self):
        return self._goal

    @property
    def group_persistor(self):
        return self._group_persistor

    @property
    def repos(self):
        return self._repos

    @repos.deleter
    def repos(self):
        self._repos = None

    @property
    @dnf.util.lazyattr("_rpmconn")
    def rpmconn(self):
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
        if self._transaction:
            raise ValueError('transaction already set')
        self._transaction = value

    def activate_persistor(self):
        self.repo_persistor = dnf.persistor.RepoPersistor(self.conf.cachedir)

    def fill_sack(self, load_system_repo=True, load_available_repos=True):
        """Prepare the Sack and the Goal objects. :api."""
        timer = dnf.logging.Timer('sack setup')
        self._sack = dnf.sack.build_sack(self)
        lock = dnf.lock.build_metadata_lock(self.conf.cachedir)
        with lock:
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
        self._setup_excludes_includes()
        timer()
        self._goal = dnf.goal.Goal(self._sack)
        return self._sack

    @property
    @dnf.util.lazyattr("_yumdb")
    def yumdb(self):
        db_path = os.path.normpath(self.conf.persistdir + '/yumdb')
        return rpmsack.AdditionalPkgDB(db_path)

    def close(self):
        """Close all potential handles and clean cache. :api

        Typically the handles are to data sources and sinks.

        """

        if self._closed:
            return
        logger.log(dnf.logging.DDEBUG, 'Cleaning up.')
        self._closed = True
        self._tempfile_persistor = dnf.persistor.TempfilePersistor(
            self.conf.cachedir)

        if self._group_persistor and \
                (not self._transaction or self.trans_success):
            self._group_persistor.commit()

        if not self.conf.keepcache:
            self.clean_packages(self._tempfiles)
            if self.trans_success:
                self._trans_tempfiles.update(
                    self._tempfile_persistor.get_saved_tempfiles())
                self._tempfile_persistor.empty()
                if self._transaction.install_set:
                    self.clean_packages(self._trans_tempfiles)
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
        self.closeRpmDB()

    def read_all_repos(self, repo_setopts=None):
        """Read repositories from the main conf file and from .repo files."""
        # :api

        reader = dnf.conf.read.RepoReader(self.conf, repo_setopts or {})
        for repo in reader:
            try:
                self.repos.add(repo)
            except dnf.exceptions.ConfigError as e:
                logger.warning(e)

    def reset(self, sack=False, repos=False, goal=False):
        """Make the Base object forget about various things. :api"""
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
                        'nocrypto': rpm.RPMTRANS_FLAG_NOFILEDIGEST}
    _TS_VSFLAGS_TO_RPM = {'nocrypto': rpm._RPMVSF_NOSIGNATURES |
                          rpm._RPMVSF_NODIGESTS}

    @property
    def ts(self):
        """Set up the RPM transaction set that will be used
           for all the work."""
        if self._ts is not None:
            return self._ts
        self._ts = dnf.rpm.transaction.TransactionWrapper(
            self.conf.installroot)
        self._ts.setFlags(0)  # reset everything.
        for flag in self.conf.tsflags:
            rpm_flag = self._TS_FLAGS_TO_RPM.get(flag)
            if rpm_flag is None:
                logger.critical(_('Invalid tsflag in config file: %s'), flag)
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

    def _activate_group_persistor(self):
        return dnf.persistor.GroupPersistor(self.conf.persistdir, self._comps)

    def read_comps(self):
        """Create the groups object to access the comps metadata. :api"""
        timer = dnf.logging.Timer('loading comps')
        self._comps = dnf.comps.Comps()

        logger.log(dnf.logging.DDEBUG, 'Getting group metadata')
        for repo in self.repos.iter_enabled():
            if not repo.enablegroups:
                continue
            if not repo.metadata:
                continue
            comps_fn = repo.metadata.comps_fn
            if comps_fn is None:
                continue

            logger.log(dnf.logging.DDEBUG,
                       'Adding group file from repository: %s', repo.id)
            if repo.md_only_cached:
                decompressed = misc.calculate_repo_gen_dest(comps_fn,
                                                            'groups.xml')
                if not os.path.exists(decompressed):
                    # root privileges are needed for comps decompression
                    continue
            else:
                decompressed = misc.repo_gen_decompress(comps_fn, 'groups.xml')

            try:
                self._comps.add_from_xml_filename(decompressed)
            except dnf.exceptions.CompsError as e:
                msg = _('Failed to add groups file for repository: %s - %s')
                logger.critical(msg, repo.id, e)

        self._group_persistor = self._activate_group_persistor()
        timer()
        return self._comps

    def _getHistory(self):
        """auto create the history object that to access/append the transaction
           history information. """
        if self._history is None:
            db_path = self.conf.persistdir + "/history"
            releasever = self.conf.releasever
            self._history = history.YumHistory(db_path, self.yumdb,
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
            ts.add_install(pkg, obs, goal.get_reason(pkg))
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

            Unlike in case of _sltr_matches_installed(), it is practical here
            to know even the packages in the original query that can still be
            installed.
        """
        inst = q.installed()
        inst_per_arch = inst.na_dict()
        avail_per_arch = q.latest().available().na_dict()
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

    def iter_userinstalled(self):
        """Get iterator over the packages installed by the user."""
        return (pkg for pkg in self.sack.query().installed()
                if self.yumdb.get_package(pkg).get('reason') == 'user' and
                self.yumdb.get_package(pkg).get('from_repo') != 'anakonda')

    def run_hawkey_goal(self, goal, allow_erasing):
        ret = goal.run(
            allow_uninstall=allow_erasing, force_best=self.conf.best,
            ignore_weak_deps=(not self.conf.install_weak_deps))
        if self.conf.debug_solver:
            goal.write_debugdata('./debugdata')
        return ret

    def resolve(self, allow_erasing=False):
        """Build the transaction set. :api"""
        exc = None

        timer = dnf.logging.Timer('depsolve')
        self.ds_callback.start()
        goal = self._goal
        if goal.req_has_erase():
            goal.push_userinstalled(self.sack.query().installed(), self.yumdb)
        if not self.run_hawkey_goal(goal, allow_erasing):
            if self.conf.debuglevel >= 6:
                goal.log_decisions()
            exc = dnf.exceptions.DepsolveError('.\n'.join(goal.problems))
        else:
            self._transaction = self._goal2transaction(goal)

        self.ds_callback.end()
        timer()

        got_transaction = self._transaction is not None and \
            len(self._transaction) > 0
        if got_transaction:
            msg = self._transaction.rpm_limitations()
            if msg:
                exc = dnf.exceptions.Error(msg)

        if exc is not None:
            raise exc
        return got_transaction

    def do_transaction(self, display=()):
        # :api
        if not isinstance(display, collections.Sequence):
            display = [display]
        display = \
            [dnf.yum.rpmtrans.LoggingTransactionDisplay()] + list(display)

        if not self.transaction:
            return

        logger.info(_('Running transaction check'))
        lock = dnf.lock.build_rpmdb_lock(self.conf.persistdir)
        with lock:
            # save our ds_callback out
            dscb = self.ds_callback
            self.ds_callback = None
            self.transaction.populate_rpm_ts(self.ts)

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
            if not self.conf.diskspacecheck:
                self.rpm_probfilter.add(rpm.RPMPROB_FILTER_DISKSPACE)

            self.ts.order()  # order the transaction
            self.ts.clean()  # release memory not needed beyond this point

            testcb = dnf.yum.rpmtrans.RPMTransaction(self, test=True)
            tserrors = self.ts.test(testcb)
            del testcb

            if len(tserrors) > 0:
                errstring = _('Transaction check error:\n')
                for descr in tserrors:
                    errstring += '  %s\n' % ucd(descr)

                raise dnf.exceptions.Error(errstring + '\n' +
                                        self._trans_error_summary(errstring))

            logger.info(_('Transaction test succeeded.'))
            timer()

            # unset the sigquit handler
            timer = dnf.logging.Timer('transaction')
            # put back our depcheck callback
            self.ds_callback = dscb
            # setup our rpm ts callback
            cb = dnf.yum.rpmtrans.RPMTransaction(self, displays=display)
            if self.conf.debuglevel < 2:
                for display_ in cb.displays:
                    display_.output = False

            logger.info(_('Running transaction'))
            self._run_transaction(cb=cb)
        timer()

    def _trans_error_summary(self, errstring):
        """Parse the error string for 'interesting' errors which can
        be grouped, such as disk space issues.

        :param errstring: the error string
        :return: a string containing a summary of the errors
        """
        summary = ''
        # do disk space report first
        p = re.compile('needs (\d+)MB on the (\S+) filesystem')
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

        summary = _('Error Summary\n-------------\n') + summary

        return summary

    def _record_history(self):
        return self.conf.history_record and \
            not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST)

    def _run_transaction(self, cb):
        """Perform the RPM transaction."""

        if self._record_history():
            using_pkgs_pats = list(self.conf.history_record_packages)
            installed_query = self.sack.query().installed()
            using_pkgs = installed_query.filter(name=using_pkgs_pats).run()
            rpmdbv = self.sack.rpmdb_version(self.yumdb)
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

        if self.conf.reset_nice:
            onice = os.nice(0)
            if onice:
                try:
                    os.nice(-onice)
                except:
                    onice = 0

        logger.log(dnf.logging.DDEBUG, 'RPM transaction start.')
        errors = self.ts.run(cb.callback, '')
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
            if len([el for el in self.ts if el.Failed()]) > 0:
                errstring = _('Warning: scriptlet or other non-fatal errors '
                              'occurred during transaction.')
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
        if not self.ts.isTsFlagSet(rpm.RPMTRANS_FLAG_TEST):
            self.verify_transaction(cb.verify_tsi_package)

    def verify_transaction(self, verify_pkg_cb=None):
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

        total = self.transaction.total_package_count()

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
        rpmdb_sack = dnf.sack.rpmdb_sack(self)

        for tsi in self._transaction:
            rpo = tsi.installed
            if rpo is None:
                continue

            installed = rpmdb_sack.query().installed().nevra(
                rpo.name, rpo.evr, rpo.arch)
            if len(installed) < 1:
                tsi.op_type = dnf.transaction.FAIL
                logger.critical(_('%s was supposed to be installed'
                                  ' but is not!'), rpo)
                count = display_banner(rpo, count)
                continue
            po = installed[0]
            count = display_banner(rpo, count)
            yumdb_info = self.yumdb.get_package(po)
            yumdb_info.from_repo = rpo.repoid

            yumdb_info.reason = tsi.propagated_reason(self.yumdb,
                                                      self.conf.installonlypkgs)
            yumdb_info.releasever = self.conf.releasever
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
                    yumdb_info.from_repo_revision = lp_ctime
                    yumdb_info.from_repo_timestamp = lp_mtime
                except Exception:
                    pass
            elif hasattr(rpo.repo, 'repoXML'):
                md = rpo.repo.repoXML
                if md and md.revision is not None:
                    yumdb_info.from_repo_revision = str(md.revision)
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
                    logger.critical(msg, rpo)
                    count = display_banner(rpo, count)
                    continue
            count = display_banner(rpo, count)
            yumdb_item = self.yumdb.get_package(rpo)
            yumdb_item.clean()

        if self._record_history():
            rpmdbv = rpmdb_sack.rpmdb_version(self.yumdb)
            self.history.end(rpmdbv, 0)
        timer()
        self.trans_success = True

    def download_packages(self, pkglist, progress=None, callback_total=None):
        """Download the packages specified by the given list of packages. :api

        `pkglist` is a list of packages to download, `progress` is an optional
         DownloadProgress instance, `callback_total` an optional callback to
         output messages about the download operation.

        """

        # select and sort packages to download
        if progress is None:
            progress = dnf.callback.NullDownloadProgress()

        lock = dnf.lock.build_download_lock(self.conf.cachedir)
        with lock:
            drpm = dnf.drpm.DeltaInfo(self.sack.query().installed(), progress)
            remote_pkgs = [po for po in pkglist
                           if not (po.from_cmdline or po.repo.local)]
            self._add_tempfiles([pkg.localPkg() for pkg in remote_pkgs])

            payloads = [dnf.repo.pkg2payload(pkg, progress, drpm.delta_factory,
                                             dnf.repo.RPMPayload)
                        for pkg in remote_pkgs]

            beg_download = time.time()
            est_remote_size = sum(pload.download_size for pload in payloads)
            progress.start(len(payloads), est_remote_size)
            errors = dnf.repo.download_payloads(payloads, drpm)

            if errors.irrecoverable:
                raise dnf.exceptions.DownloadError(errors.irrecoverable)

            remote_size = sum(errors.bandwidth_used(pload)
                              for pload in payloads)
            saving = dnf.repo.update_saving((0, 0), payloads,
                                            errors.recoverable)

            if errors.recoverable:
                msg = dnf.exceptions.DownloadError.errmap2str(
                    errors.recoverable)
                logger.info(msg)

                remaining_pkgs = [pkg for pkg in errors.recoverable]
                payloads = \
                    [dnf.repo.pkg2payload(pkg, progress, dnf.repo.RPMPayload)
                     for pkg in remaining_pkgs]
                est_remote_size = sum(pload.download_size
                                      for pload in payloads)
                progress.start(len(payloads), est_remote_size)
                errors = dnf.repo.download_payloads(payloads, drpm)

                assert not errors.recoverable
                if errors.irrecoverable:
                    raise dnf.exceptions.DownloadError(errors.irrecoverable)

                remote_size += \
                    sum(errors.bandwidth_used(pload) for pload in payloads)
                saving = dnf.repo.update_saving(saving, payloads, {})

        if callback_total is not None:
            callback_total(remote_size, beg_download)

        (real, full) = saving
        if real != full:
            msg = _("Delta RPMs reduced %.1f MB of updates to %.1f MB "
                    "(%d.1%% saved)")
            percent = 100 - real / full * 100
            logger.info(msg, full / 1024 ** 2, real / 1024 ** 2, percent)

    def add_remote_rpm(self, path):
        # :api
        if not os.path.exists(path) and '://' in path:
            # download remote rpm to a tempfile
            path = dnf.util.urlopen(path, suffix='.rpm', delete=False).name
            self._add_tempfiles([path])
        return self.sack.add_cmdline_package(path)

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

    def clean_packages(self, packages):
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

    def doPackageLists(self, pkgnarrow='all', patterns=None, showdups=None,
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
            return self.yumdb.get_package(package).get('from_repo') == reponame

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
            updates = query_for_repo(q).upgrades().run()

        # installed only
        elif pkgnarrow == 'installed':
            installed = list(pkgs_from_repo(q.installed()))

        # available in a repository
        elif pkgnarrow == 'available':
            if showdups:
                avail = query_for_repo(q).available()
                installed_dict = q.installed().na_dict()
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
                    q).available().latest().na_dict()
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

        # packages to be removed by autoremove
        elif pkgnarrow == 'autoremove':
            autoremove_q = query_for_repo(q).unneeded(self.sack, self.yumdb)
            autoremove = autoremove_q.run()

        # not in a repo but installed
        elif pkgnarrow == 'extras':
            extras = [pkg for pkg in q.extras() if is_from_repo(pkg)]

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            inst = q.installed()
            obsoletes = query_for_repo(
                self.sack.query()).filter(obsoletes=inst)
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
            recent = query_for_repo(avail).recent(self.conf.recent)

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
        cnt = 0
        clean_deps = self.conf.clean_requirements_on_remove
        attr_fn = ((trans.install, self._goal.install),
                   (trans.install_opt,
                    functools.partial(self._goal.install, optional=True)),
                   (trans.upgrade, self._goal.upgrade),
                   (trans.remove,
                    functools.partial(self._goal.erase, clean_deps=clean_deps)))

        for (attr, fn) in attr_fn:
            for it in attr:
                if not self.sack.query().filter(name=it):
                    # a comps item that doesn't refer to anything real
                    continue
                sltr = dnf.selector.Selector(self.sack)
                sltr.set(name=it)
                fn(select=sltr)
                cnt += 1

        self._goal.group_members.update(trans.install)
        self._goal.group_members.update(trans.install_opt)
        return cnt

    def build_comps_solver(self):
        def reason_fn(pkgname):
            q = self.sack.query().installed().filter(name=pkgname)
            if not q:
                return None
            try:
                return self.yumdb.get_package(q[0]).reason
            except AttributeError:
                return 'unknown'

        return dnf.comps.Solver(self._group_persistor, self._comps, reason_fn)

    def environment_install(self, env_id, types, exclude=None, strict=True):
        solver = self.build_comps_solver()
        types = self._translate_comps_pkg_types(types)
        trans = dnf.comps.install_or_skip(solver.environment_install,
                                          env_id, types, exclude or set(),
                                          strict)
        if not trans:
            return 0
        return self._add_comps_trans(trans)

    def environment_remove(self, env_id):
        solver = self.build_comps_solver()
        trans = solver.environment_remove(env_id)
        return self._add_comps_trans(trans)

    _COMPS_TRANSLATION = {
        'default': dnf.comps.DEFAULT,
        'mandatory': dnf.comps.MANDATORY,
        'optional': dnf.comps.OPTIONAL
    }

    @staticmethod
    def _translate_comps_pkg_types(pkg_types):
        ret = 0
        for (name, enum) in Base._COMPS_TRANSLATION.items():
            if name in pkg_types:
                ret |= enum
        return ret

    def group_install(self, grp_id, pkg_types, exclude=None, strict=True):
        """Installs packages of selected group
        :param exclude: list of package name glob patterns
            that will be excluded from install set
        """
        # :api
        def _pattern_to_pkgname(pattern):
            if dnf.util.is_glob_pattern(pattern):
                q = self.sack.query().filter(name__glob=pattern)
                return map(lambda p: p.name, q)
            else:
                return (pattern,)

        # compat: erase in 2.0.0
        if isinstance(grp_id, dnf.comps.Environment) or \
           isinstance(grp_id, dnf.comps.Group):
                grp_id = grp_id.id
                msg = "group_install() expects group id \
                       instead of Comps object."
                dnf.logging.depr(msg)

        exclude_pkgnames = None
        if exclude:
            nested_excludes = [_pattern_to_pkgname(p) for p in exclude]
            exclude_pkgnames = itertools.chain.from_iterable(nested_excludes)

        solver = self.build_comps_solver()
        pkg_types = self._translate_comps_pkg_types(pkg_types)
        trans = dnf.comps.install_or_skip(solver.group_install,
                                          grp_id, pkg_types, exclude_pkgnames,
                                          strict)
        if not trans:
            return 0
        logger.debug("Adding packages from group '%s': %s",
                     grp_id, trans.install)
        return self._add_comps_trans(trans)

    def env_group_install(self, patterns, types, strict=True):
        q = CompsQuery(self.comps, self.group_persistor,
                       CompsQuery.ENVIRONMENTS | CompsQuery.GROUPS,
                       CompsQuery.AVAILABLE | CompsQuery.INSTALLED)
        cnt = 0
        done = True
        for pattern in patterns:
            try:
                res = q.get(pattern)
            except dnf.exceptions.CompsError as err:
                logger.error("Warning: %s", ucd(err))
                done = False
                continue
            for group_id in res.groups:
                cnt += self.group_install(group_id, types, strict=strict)
            for env_id in res.environments:
                cnt += self.environment_install(env_id, types, strict=strict)
        if not done and strict:
            raise dnf.exceptions.Error(_('Nothing to do.'))
        return cnt

    def group_remove(self, grp_id):
        # :api
        # compat: erase in 2.0.0
        if isinstance(grp_id, dnf.comps.Environment) or \
           isinstance(grp_id, dnf.comps.Group):
                msg = "group_remove() expects group id \
                       instead of Comps object."
                dnf.logging.depr(msg)
                grp_id = grp_id.id

        solver = self.build_comps_solver()
        trans = solver.group_remove(grp_id)
        return self._add_comps_trans(trans)

    def env_group_remove(self, patterns):
        q = CompsQuery(self.comps, self.group_persistor,
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
        q = CompsQuery(self.comps, self.group_persistor,
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
        solver = self.build_comps_solver()
        trans = solver.environment_upgrade(env_id)
        return self._add_comps_trans(trans)

    def group_upgrade(self, grp_id):
        # :api
        # compat: erase in 2.0.0
        if isinstance(grp_id, dnf.comps.Environment) or \
           isinstance(grp_id, dnf.comps.Group):
                msg = "group_upgrade() expects group id \
                       instead of Comps object."
                dnf.logging.depr(msg)
                grp_id = grp_id.id

        solver = self.build_comps_solver()
        trans = solver.group_upgrade(grp_id)
        return self._add_comps_trans(trans)

    def gpgKeyCheck(self):
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

    def install(self, pkg_spec, reponame=None, strict=True):
        """Mark package(s) given by pkg_spec and reponame for installation.:api
        """

        subj = dnf.subject.Subject(pkg_spec)
        if self.conf.multilib_policy == "all" or \
           subj.is_arch_specified(self.sack):
            q = subj.get_best_query(self.sack).filter(arch__neq="src")
            if reponame is not None:
                q = q.filter(reponame=reponame)
            if not q:
                raise dnf.exceptions.PackageNotFoundError(
                    _('no package matched'), pkg_spec)
            already_inst, available = self._query_matches_installed(q)
            for i in already_inst:
                _msg_installed(i)
            for a in available:
                self._goal.install(a, optional=(not strict))
            return len(available)
        elif self.conf.multilib_policy == "best":
            sltrs = subj.get_best_selectors(self.sack)
            match = reduce(lambda x, y: y.matches() or x, sltrs, [])
            if not match:
                raise dnf.exceptions.MarkingError(
                    _('no package matched'), pkg_spec)
            for sltr in sltrs:
                if not sltr.matches():
                    continue
                if reponame is not None:
                    sltr = sltr.set(reponame=reponame)
                already_inst = self._sltr_matches_installed(sltr)
                if already_inst:
                    for package in already_inst:
                        _msg_installed(package)
                self._goal.install(select=sltr, optional=(not strict))
            return 1
        return 0

    def install_groupie(self, pkg_name, inst_set):
        """Installs a group member package by name. """
        forms = [hawkey.FORM_NAME]
        subj = dnf.subject.Subject(pkg_name)
        if self.conf.multilib_policy == "all":
            q = subj.get_best_query(
                self.sack, with_provides=False, forms=forms)
            for pkg in q:
                self._goal.install(pkg)
            return len(q)
        elif self.conf.multilib_policy == "best":
            sltr = subj.get_best_selector(self.sack, forms=forms)
            if sltr.matches():
                self._goal.install(select=sltr)
                return 1
        return 0

    def package_downgrade(self, pkg):
        # :api
        if pkg.from_system:
            msg = 'downgrade_package() for an installed package.'
            raise NotImplementedError(msg)

        q = self.sack.query().installed().filter(name=pkg.name, arch=pkg.arch)
        if not q:
            msg = _("Package %s not installed, cannot downgrade it.")
            logger.warning(msg, pkg.name)
            return 0
        elif sorted(q)[0] > pkg:
            self._goal.downgrade_to(pkg)
            return 1
        else:
            msg = _("Package %s of lower version already installed, "
                    "cannot downgrade it.")
            logger.warning(msg, pkg.name)
            return 0

    def package_install(self, pkg, strict=True):
        # :api
        q = self.sack.query().nevra(pkg.name, pkg.evr, pkg.arch)
        already_inst, _ = self._query_matches_installed(q)
        if pkg in already_inst:
            _msg_installed(pkg)
        else:
            self._goal.install(pkg, optional=(not strict))
        return 1

    def package_reinstall(self, pkg):
        if self.sack.query().installed().filter(nevra=str(pkg)):
            self._goal.install(pkg)
            return 1
        msg = _("Package %s not installed, cannot reinstall it.")
        logger.warning(msg, str(pkg))
        return 0

    def package_remove(self, pkg):
        self._goal.erase(pkg)
        return 1

    def package_upgrade(self, pkg):
        # :api
        if pkg.from_system:
            msg = 'upgrade_package() for an installed package.'
            raise NotImplementedError(msg)

        q = self.sack.query().installed().filter(name=pkg.name, arch=pkg.arch)
        if not q:
            msg = _("Package %s not installed, cannot update it.")
            logger.warning(msg, pkg.name)
            return 0
        elif sorted(q)[-1] < pkg:
            self._goal.upgrade_to(pkg)
            return 1
        else:
            msg = _("Package %s of higher version already installed, "
                    "cannot update it.")
            logger.warning(msg, pkg.name)
            return 0

    def upgrade(self, pkg_spec, reponame=None):
        # :api
        def is_installed_by_name(pkg_name):
            return first(self.sack.query().installed().filter(name=pkg_name))
        wildcard = True if dnf.util.is_glob_pattern(pkg_spec) else False
        sltrs = dnf.subject.Subject(pkg_spec).get_best_selectors(self.sack)
        match = reduce(lambda x, y: y.matches() or x, sltrs, [])
        if match:
            prev_count = self._goal.req_length()
            for sltr in sltrs:
                if not sltr.matches():
                    continue
                pkg_name = sltr.matches()[0].name
                if not is_installed_by_name(pkg_name):
                    if not wildcard: # wildcard shouldn't print not installed packages
                        msg = _("Package %s not installed, cannot update it.")
                        logger.warning(msg, pkg_name)
                    continue
                if reponame is not None:
                    sltr = sltr.set(reponame=reponame)
                self._goal.upgrade(select=sltr)

            if self._goal.req_length() - prev_count:
                return 1

        raise dnf.exceptions.MarkingError('no package matched', pkg_spec)

    def upgrade_all(self, reponame=None):
        # :api
        if reponame is None:
            self._goal.upgrade_all()
        else:
            try:
                self.upgrade('*', reponame)
            except dnf.exceptions.MarkingError:
                pass
        return 1

    def upgrade_to(self, pkg_spec, reponame=None):
        forms = [hawkey.FORM_NEVRA, hawkey.FORM_NEVR]
        sltr = dnf.subject.Subject(pkg_spec).get_best_selector(self.sack,
                                                               forms=forms)
        if sltr.matches():
            if reponame is not None:
                sltr = sltr.set(reponame=reponame)

            prev_count = self._goal.req_length()
            self._goal.upgrade_to(select=sltr)
            if self._goal.req_length() - prev_count:
                return 1

        return 0

    def distro_sync(self, pkg_spec=None):
        if pkg_spec is None:
            self._goal.distupgrade_all()
        else:
            sltrs = dnf.subject.Subject(pkg_spec).get_best_selectors(self.sack)
            match = reduce(lambda x, y: y.matches() or x, sltrs, [])
            if not match:
                logger.info(_('No package %s installed.'), pkg_spec)
                return 0
            for sltr in sltrs:
                if not sltr.matches():
                    continue
                self._goal.distupgrade(select=sltr)
        return 1

    def remove(self, pkg_spec, reponame=None):
        """Mark the specified package for removal. #:api """

        matches = dnf.subject.Subject(pkg_spec).get_best_query(self.sack)
        installed = [
            pkg for pkg in matches.installed()
            if reponame is None or
            self.yumdb.get_package(pkg).get('from_repo') == reponame]
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
            self.yumdb.get_package(pkg).get('from_repo') == old_reponame]

        available_q = q.available()
        if new_reponame is not None:
            available_q = available_q.filter(reponame=new_reponame)
        if new_reponame_neq is not None:
            available_q = available_q.filter(reponame__neq=new_reponame_neq)
        available_nevra2pkg = dnf.query.per_nevra_dict(available_q)

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
        """Mark a package to be downgraded. :api

        This is equivalent to first removing the currently installed package,
        and then installing an older version.

        """
        subj = dnf.subject.Subject(pkg_spec)
        q = subj.get_best_query(self.sack)
        installed = sorted(q.installed())
        installed_pkg = first(installed)
        if installed_pkg is None:
            available_pkgs = q.available()
            if available_pkgs:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', pkg_spec, available_pkgs)
            raise dnf.exceptions.PackageNotFoundError('no package matched',
                                                      pkg_spec)

        arch = installed_pkg.arch
        q = self.sack.query().filter(name=installed_pkg.name, arch=arch)
        avail = [pkg for pkg in q.downgrades() if pkg < installed_pkg]
        avail_pkg = first(sorted(avail, reverse=True))
        if avail_pkg is None:
            return 0

        self._goal.install(avail_pkg)
        return 1

    def downgrade_to(self, pkg_spec):
        """Downgrade to specific version if specified otherwise downgrades
        to one version lower than the package installed.
        """
        subj = dnf.subject.Subject(pkg_spec)
        poss = subj.subj.nevra_possibilities_real(self.sack, allow_globs=True)
        nevra = dnf.util.first(poss)
        if not nevra:
            raise dnf.exceptions.PackageNotFoundError('no package matched',
                                                      pkg_spec)

        q = subj._nevra_to_filters(self.sack.query(), nevra)
        available_pkgs = q.available()
        test_q = dnf.subject.Subject(nevra.name).get_best_query(self.sack)
        if not test_q.installed():
            raise dnf.exceptions.PackagesNotInstalledError(
                'no package matched', pkg_spec, available_pkgs)
        downgrade_pkgs = available_pkgs.downgrades().latest()
        if not downgrade_pkgs:
            msg = _("Package %s of lowest version already installed, "
                    "cannot downgrade it.")
            logger.warning(msg, nevra.name)
            return 0
        dnf.util.mapall(self._goal.downgrade_to, downgrade_pkgs)
        return 1

    def provides(self, provides_spec):
        providers = dnf.query.by_provides(self.sack, provides_spec)
        if providers:
            return providers
        if any(map(dnf.util.is_glob_pattern, provides_spec)):
            return self.sack.query().filter(file__glob=provides_spec)
        return self.sack.query().filter(file=provides_spec)

    def history_undo_operations(self, operations):
        """Undo the operations on packages by their NEVRAs.

        :param operations: a NEVRAOperations to be undone
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        def handle_downgrade(new_nevra, old_nevra, obsoleted_nevras):
            """Handle a downgraded package."""
            news = self.sack.query().installed().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available().nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            assert len(news) == 1
            self._transaction.add_upgrade(first(olds), news[0], None)
            for obsoleted_nevra in obsoleted_nevras:
                handle_erase(obsoleted_nevra)

        def handle_erase(old_nevra):
            """Handle an erased package."""
            pkgs = self.sack.query().available().nevra(old_nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            self._transaction.add_install(
                first(pkgs), None, 'history')

        def handle_install(new_nevra, obsoleted_nevras):
            """Handle an installed package."""
            pkgs = self.sack.query().installed().nevra(new_nevra)
            if not pkgs:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            assert len(pkgs) == 1
            self._transaction.add_erase(pkgs[0])
            for obsoleted_nevra in obsoleted_nevras:
                handle_erase(obsoleted_nevra)

        def handle_reinstall(new_nevra, old_nevra, obsoleted_nevras):
            """Handle a reinstalled package."""
            news = self.sack.query().installed().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available().nevra(old_nevra)
            if not olds:
                raise dnf.exceptions.PackagesNotAvailableError(
                    'no package matched', old_nevra)
            obsoleteds = []
            for nevra in obsoleted_nevras:
                obsoleteds_ = self.sack.query().installed().nevra(nevra)
                if obsoleteds_:
                    assert len(obsoleteds_) == 1
                    obsoleteds.append(obsoleteds_[0])
            assert len(news) == 1
            self._transaction.add_reinstall(first(olds), news[0],
                                            obsoleteds)

        def handle_upgrade(new_nevra, old_nevra, obsoleted_nevras):
            """Handle an upgraded package."""
            news = self.sack.query().installed().nevra(new_nevra)
            if not news:
                raise dnf.exceptions.PackagesNotInstalledError(
                    'no package matched', new_nevra)
            olds = self.sack.query().available().nevra(old_nevra)
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

    def getKeyForPackage(self, po, askcb=None, fullaskcb=None):
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
            msg += _('Failing package is: %s\n'
                     ' GPG Keys are configured as: %s\n'
                     ) % (po, ", ".join(repo.gpgkey))
            return '\n\n\n' + msg

        user_cb_fail = False
        for keyurl in keyurls:
            keys = dnf.crypto.retrieve(keyurl, repo)

            for info in keys:
                ts = self.rpmconn.readonly_ts
                # Check if key is already installed
                if misc.keyInstalled(ts, info.rpm_id, info.timestamp) >= 0:
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
                result = ts.pgpImportPubkey(misc.procgpgkey(info.raw_key))
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
        result, errmsg = self.sigCheckPkg(po)
        if result != 0:
            msg = _("Import of key(s) didn't help, wrong key(s)?")
            logger.info(msg)
            errmsg = ucd(errmsg)
            raise dnf.exceptions.Error(_prov_key_data(errmsg))

    def _run_rpm_check(self):
        results = []
        self.ts.check()
        for prob in self.ts.problems():
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


def _msg_installed(pkg):
    name = ucd(pkg)
    msg = _('Package %s is already installed, skipping.')
    logger.warning(msg, name)
