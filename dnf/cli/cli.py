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
#
# Written by Seth Vidal

"""
Command line interface yum class and related.
"""

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from . import output
from dnf.cli import CliError
from dnf.i18n import ucd, _

import collections
import dnf
import dnf.cli.commands
import dnf.cli.commands.autoremove
import dnf.cli.commands.check
import dnf.cli.commands.clean
import dnf.cli.commands.deplist
import dnf.cli.commands.distrosync
import dnf.cli.commands.downgrade
import dnf.cli.commands.remove
import dnf.cli.commands.group
import dnf.cli.commands.install
import dnf.cli.commands.makecache
import dnf.cli.commands.mark
import dnf.cli.commands.reinstall
import dnf.cli.commands.repolist
import dnf.cli.commands.repoquery
import dnf.cli.commands.search
import dnf.cli.commands.shell
import dnf.cli.commands.swap
import dnf.cli.commands.updateinfo
import dnf.cli.commands.upgrade
import dnf.cli.commands.upgrademinimal
import dnf.cli.demand
import dnf.cli.option_parser
import dnf.conf
import dnf.conf.substitutions
import dnf.const
import dnf.exceptions
import dnf.cli.format
import dnf.logging
import dnf.plugin
import dnf.persistor
import dnf.rpm
import dnf.sack
import dnf.util
import dnf.yum.misc
import hawkey
import logging
import operator
import os
import random
import sys
import time

logger = logging.getLogger('dnf')


def _add_pkg_simple_list_lens(data, pkg, indent=''):
    """ Get the length of each pkg's column. Add that to data.
        This "knows" about simpleList and printVer. """
    na = len(pkg.name) + 1 + len(pkg.arch) + len(indent)
    ver = len(pkg.evr)
    rid = len(pkg._from_repo)
    for (d, v) in (('na', na), ('ver', ver), ('rid', rid)):
        data[d].setdefault(v, 0)
        data[d][v] += 1


def _list_cmd_calc_columns(output, ypl):
    """ Work out the dynamic size of the columns to pass to fmtColumns. """
    data = {'na' : {}, 'ver' : {}, 'rid' : {}}
    for lst in (ypl.installed, ypl.available, ypl.extras, ypl.autoremove,
                ypl.updates, ypl.recent):
        for pkg in lst:
            _add_pkg_simple_list_lens(data, pkg)
    if len(ypl.obsoletes) > 0:
        for (npkg, opkg) in ypl.obsoletesTuples:
            _add_pkg_simple_list_lens(data, npkg)
            _add_pkg_simple_list_lens(data, opkg, indent=" " * 4)

    data = [data['na'], data['ver'], data['rid']]
    columns = output.calcColumns(data, remainder_column=1)
    return (-columns[0], -columns[1], -columns[2])


def print_versions(pkgs, base, output):
    def sm_ui_time(x):
        return time.strftime("%c", time.gmtime(x))

    rpmdb_sack = dnf.sack._rpmdb_sack(base)
    done = False
    for pkg in rpmdb_sack.query().installed().filterm(name=pkgs):
        if done:
            print("")
        done = True
        if pkg.epoch == '0':
            ver = '%s-%s.%s' % (pkg.version, pkg.release, pkg.arch)
        else:
            ver = '%s:%s-%s.%s' % (pkg.epoch,
                                   pkg.version, pkg.release, pkg.arch)
        name = output.term.bold(pkg.name)
        print(_("  Installed: %s-%s at %s") %(name, ver,
                                              sm_ui_time(pkg.installtime)))
        print(_("  Built    : %s at %s") % (pkg.packager if pkg.packager else "",
                                            sm_ui_time(pkg.buildtime)))
        # :hawkey, no changelist information yet
        # print(_("  Committed: %s at %s") % (pkg.committer,
        #                                    sm_ui_date(pkg.committime)))


class BaseCli(dnf.Base):
    """This is the base class for yum cli."""

    def __init__(self, conf=None):
        conf = conf or dnf.conf.Conf()
        super(BaseCli, self).__init__(conf=conf)
        self.output = output.Output(self, self.conf)

    def do_transaction(self, display=()):
        """Take care of package downloading, checking, user
        confirmation and actually running the transaction.

        :param display: `rpm.callback.TransactionProgress` object(s)
        :return: a numeric return code, and optionally a list of
           errors.  A negative return code indicates that errors
           occurred in the pre-transaction checks
        """

        # Reports about excludes and includes (but not from plugins)
        if self.conf.excludepkgs:
            logger.debug(_('Excludes in dnf.conf: ') +
                         ", ".join(sorted(set(self.conf.excludepkgs))))
        if self.conf.includepkgs:
            logger.debug(_('Includes in dnf.conf: ') +
                         ", ".join(sorted(set(self.conf.includepkgs))))
        for repo in self.repos.iter_enabled():
            if repo.excludepkgs:
                logger.debug(_('Excludes in repo ') + repo.id + ": " +
                             ", ".join(sorted(set(repo.excludepkgs))))
            if repo.includepkgs:
                logger.debug(_('Includes in repo ') + repo.id + ": " +
                             ", ".join(sorted(set(repo.includepkgs))))

        trans = self.transaction
        pkg_str = self.output.list_transaction(trans)
        if pkg_str:
            logger.info(pkg_str)

        if trans:
            # Check which packages have to be downloaded
            install_pkgs = []
            rmpkgs = []
            install_only = True
            for tsi in trans:
                installed = tsi.installed
                if installed is not None:
                    install_pkgs.append(installed)
                erased = tsi.erased
                if erased is not None:
                    install_only = False
                    rmpkgs.append(erased)

            # Close the connection to the rpmdb so that rpm doesn't hold the
            # SIGINT handler during the downloads.
            del self._ts

            # report the total download size to the user
            if not install_pkgs:
                self.output.reportRemoveSize(rmpkgs)
            else:
                self.output.reportDownloadSize(install_pkgs, install_only)

        if trans:
            # confirm with user
            if self.conf.downloadonly:
                logger.info(_("DNF will only download packages for the transaction."))
            elif 'test' in self.conf.tsflags:
                logger.info(_("DNF will only download packages, install gpg keys, and check the "
                              "transaction."))
            if self._promptWanted():
                if self.conf.assumeno or not self.output.userconfirm():
                    raise CliError(_("Operation aborted."))
        else:
            logger.info(_('Nothing to do.'))
            return

        if trans:
            if install_pkgs:
                logger.info(_('Downloading Packages:'))
                try:
                    total_cb = self.output.download_callback_total_cb
                    self.download_packages(install_pkgs, self.output.progress, total_cb)
                except dnf.exceptions.DownloadError as e:
                    specific = dnf.cli.format.indent_block(ucd(e))
                    errstr = _('Error downloading packages:') + '\n%s' % specific
                    # setting the new line to prevent next chars being eaten up
                    # by carriage returns
                    print()
                    raise dnf.exceptions.Error(errstr)
            # Check GPG signatures
            self.gpgsigcheck(install_pkgs)

        if self.conf.downloadonly:
            return

        if not isinstance(display, collections.Sequence):
            display = [display]
        display = [output.CliTransactionDisplay()] + list(display)
        super(BaseCli, self).do_transaction(display)
        if trans:
            msg = self.output.post_transaction_output(trans)
            logger.info(msg)
            for tsi in trans:
                if tsi.op_type == dnf.transaction.FAIL:
                    raise dnf.exceptions.Error(_('Transaction failed'))

    def gpgsigcheck(self, pkgs):
        """Perform GPG signature verification on the given packages,
        installing keys if possible.

        :param pkgs: a list of package objects to verify the GPG
           signatures of
        :raises: Will raise :class:`Error` if there's a problem
        """
        error_messages = []
        for po in pkgs:
            result, errmsg = self._sig_check_pkg(po)

            if result == 0:
                # Verified ok, or verify not req'd
                continue

            elif result == 1:
                ay = self.conf.assumeyes and not self.conf.assumeno
                if (not sys.stdin or not sys.stdin.isatty()) and not ay:
                    raise dnf.exceptions.Error(_('Refusing to automatically import keys when running ' \
                            'unattended.\nUse "-y" to override.'))

                # the callback here expects to be able to take options which
                # userconfirm really doesn't... so fake it
                fn = lambda x, y, z: self.output.userconfirm()
                try:
                    self._get_key_for_package(po, fn)
                except dnf.exceptions.Error as e:
                    error_messages.append(str(e))

            else:
                # Fatal error
                error_messages.append(errmsg)

        if error_messages:
            for msg in error_messages:
                logger.critical(msg)
            raise dnf.exceptions.Error(_("GPG check FAILED"))

    def check_updates(self, patterns=(), reponame=None, print_=True):
        """Check updates matching given *patterns* in selected repository."""
        ypl = self.returnPkgLists('upgrades', patterns, reponame=reponame)
        if self.conf.obsoletes or self.conf.verbose:
            typl = self.returnPkgLists('obsoletes', patterns, reponame=reponame)
            ypl.obsoletes = typl.obsoletes
            ypl.obsoletesTuples = typl.obsoletesTuples

        if print_:
            columns = _list_cmd_calc_columns(self.output, ypl)
            if len(ypl.updates) > 0:
                local_pkgs = {}
                highlight = self.output.term.MODE['bold']
                if highlight:
                    # Do the local/remote split we get in "yum updates"
                    for po in sorted(ypl.updates):
                        local = po.localPkg()
                        if os.path.exists(local) and po.verifyLocalPkg():
                            local_pkgs[(po.name, po.arch)] = po

                cul = self.conf.color_update_local
                cur = self.conf.color_update_remote
                self.output.listPkgs(ypl.updates, '', outputType='list',
                              highlight_na=local_pkgs, columns=columns,
                              highlight_modes={'=' : cul, 'not in' : cur})
            if len(ypl.obsoletes) > 0:
                print(_('Obsoleting Packages'))
                # The tuple is (newPkg, oldPkg) ... so sort by new
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    self.output.updatesObsoletesList(obtup, 'obsoletes',
                                                     columns=columns)

        return ypl.updates or ypl.obsoletes

    def distro_sync_userlist(self, userlist):
        """ Upgrade or downgrade packages to match the latest versions available
            in the enabled repositories.

            :return: (exit_code, [ errors ])

            exit_code is::
                0 = we're done, exit
                1 = we've errored, exit with error string
                2 = we've got work yet to do, onto the next stage
        """
        oldcount = self._goal.req_length()
        if len(userlist) == 0:
            self.distro_sync()
        else:
            for pkg_spec in userlist:
                self.distro_sync(pkg_spec)

        cnt = self._goal.req_length() - oldcount
        if cnt <= 0 and not self._goal.req_has_distupgrade_all():
            msg = _('No packages marked for distribution synchronization.')
            raise dnf.exceptions.Error(msg)

    def downgradePkgs(self, specs=[], file_pkgs=[], strict=False):
        """Attempt to take the user specified list of packages or
        wildcards and downgrade them. If a complete version number is
        specified, attempt to downgrade them to the specified version

        :param specs: a list of names or wildcards specifying packages to downgrade
        :param file_pkgs: a list of pkg objects from local files
        """

        oldcount = self._goal.req_length()
        for pkg in file_pkgs:
            try:
                self.package_downgrade(pkg, strict=strict)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos
            except dnf.exceptions.MarkingError as e:
                logger.info(_('No match for argument: %s'),
                            self.output.term.bold(pkg.location))
                # it was something on disk and it ended in rpm
                # no matter what we don't go looking at repos

        for arg in specs:
            try:
                self.downgrade_to(arg, strict=strict)
            except dnf.exceptions.PackageNotFoundError as err:
                msg = _('No package %s available.')
                logger.info(msg, self.output.term.bold(arg))
                self._report_icase_hint(arg)
            except dnf.exceptions.PackagesNotInstalledError as err:
                logger.info(_('Packages for argument %s available, but not installed.'),
                            self.output.term.bold(err.pkg_spec))
            except dnf.exceptions.MarkingError:
                assert False
        cnt = self._goal.req_length() - oldcount
        if cnt <= 0:
            raise dnf.exceptions.Error(_('No packages marked for downgrade.'))

    def output_packages(self, basecmd, pkgnarrow='all', patterns=(), reponame=None):
        """Output selection *pkgnarrow* of packages matching *patterns* and *repoid*."""
        try:
            highlight = self.output.term.MODE['bold']
            ypl = self.returnPkgLists(
                pkgnarrow, patterns, installed_available=highlight, reponame=reponame)
        except dnf.exceptions.Error as e:
            return 1, [str(e)]
        else:
            update_pkgs = {}
            inst_pkgs = {}
            local_pkgs = {}

            columns = None
            if basecmd == 'list':
                # Dynamically size the columns
                columns = _list_cmd_calc_columns(self.output, ypl)

            if highlight and ypl.installed:
                #  If we have installed and available lists, then do the
                # highlighting for the installed packages so you can see what's
                # available to update, an extra, or newer than what we have.
                for pkg in (ypl.hidden_available +
                            ypl.reinstall_available +
                            ypl.old_available):
                    key = (pkg.name, pkg.arch)
                    if key not in update_pkgs or pkg > update_pkgs[key]:
                        update_pkgs[key] = pkg

            if highlight and ypl.available:
                #  If we have installed and available lists, then do the
                # highlighting for the available packages so you can see what's
                # available to install vs. update vs. old.
                for pkg in ypl.hidden_installed:
                    key = (pkg.name, pkg.arch)
                    if key not in inst_pkgs or pkg > inst_pkgs[key]:
                        inst_pkgs[key] = pkg

            if highlight and ypl.updates:
                # Do the local/remote split we get in "yum updates"
                for po in sorted(ypl.updates):
                    if po.reponame != hawkey.SYSTEM_REPO_NAME:
                        local_pkgs[(po.name, po.arch)] = po

            # Output the packages:
            clio = self.conf.color_list_installed_older
            clin = self.conf.color_list_installed_newer
            clir = self.conf.color_list_installed_reinstall
            clie = self.conf.color_list_installed_extra
            rip = self.output.listPkgs(ypl.installed, _('Installed Packages'), basecmd,
                                highlight_na=update_pkgs, columns=columns,
                                highlight_modes={'>' : clio, '<' : clin,
                                                 '=' : clir, 'not in' : clie})
            clau = self.conf.color_list_available_upgrade
            clad = self.conf.color_list_available_downgrade
            clar = self.conf.color_list_available_reinstall
            clai = self.conf.color_list_available_install
            rap = self.output.listPkgs(ypl.available, _('Available Packages'), basecmd,
                                highlight_na=inst_pkgs, columns=columns,
                                highlight_modes={'<' : clau, '>' : clad,
                                                 '=' : clar, 'not in' : clai})
            raep = self.output.listPkgs(ypl.autoremove, _('Autoremove Packages'),
                                basecmd, columns=columns)
            rep = self.output.listPkgs(ypl.extras, _('Extra Packages'), basecmd,
                                columns=columns)
            cul = self.conf.color_update_local
            cur = self.conf.color_update_remote
            rup = self.output.listPkgs(ypl.updates, _('Available Upgrades'), basecmd,
                                highlight_na=local_pkgs, columns=columns,
                                highlight_modes={'=' : cul, 'not in' : cur})

            # XXX put this into the ListCommand at some point
            if len(ypl.obsoletes) > 0 and basecmd == 'list':
            # if we've looked up obsolete lists and it's a list request
                rop = [0, '']
                print(_('Obsoleting Packages'))
                for obtup in sorted(ypl.obsoletesTuples,
                                    key=operator.itemgetter(0)):
                    self.output.updatesObsoletesList(obtup, 'obsoletes',
                                                     columns=columns)
            else:
                rop = self.output.listPkgs(ypl.obsoletes, _('Obsoleting Packages'),
                                    basecmd, columns=columns)
            rrap = self.output.listPkgs(ypl.recent, _('Recently Added Packages'),
                                 basecmd, columns=columns)
            if len(patterns) and \
                rrap[0] and rop[0] and rup[0] and rep[0] and rap[0] and \
                raep[0] and rip[0]:
                raise dnf.exceptions.Error(_('No matching Packages to list'))

    def returnPkgLists(self, pkgnarrow='all', patterns=None,
                       installed_available=False, reponame=None):
        """Return a :class:`dnf.yum.misc.GenericHolder` object containing
        lists of package objects that match the given names or wildcards.

        :param pkgnarrow: a string specifying which types of packages
           lists to produce, such as updates, installed, available, etc.
        :param patterns: a list of names or wildcards specifying
           packages to list
        :param installed_available: whether the available package list
           is present as .hidden_available when doing all, available,
           or installed
        :param reponame: limit packages list to the given repository

        :return: a :class:`dnf.yum.misc.GenericHolder` instance with the
           following lists defined::

             available = list of packageObjects
             installed = list of packageObjects
             upgrades = tuples of packageObjects (updating, installed)
             extras = list of packageObjects
             obsoletes = tuples of packageObjects (obsoleting, installed)
             recent = list of packageObjects
        """

        done_hidden_available = False
        done_hidden_installed = False
        if installed_available and pkgnarrow == 'installed':
            done_hidden_available = True
            pkgnarrow = 'all'
        elif installed_available and pkgnarrow == 'available':
            done_hidden_installed = True
            pkgnarrow = 'all'

        ypl = self._do_package_lists(
            pkgnarrow, patterns, ignore_case=True, reponame=reponame)
        if self.conf.showdupesfromrepos:
            ypl.available += ypl.reinstall_available

        if installed_available:
            ypl.hidden_available = ypl.available
            ypl.hidden_installed = ypl.installed
        if done_hidden_available:
            ypl.available = []
        if done_hidden_installed:
            ypl.installed = []
        return ypl

    def provides(self, args):
        """Print out a list of packages that provide the given file or
        feature.  This a cli wrapper to the provides methods in the
        rpmdb and pkgsack.

        :param args: the name of a file or feature to search for
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # always in showdups mode
        old_sdup = self.conf.showdupesfromrepos
        self.conf.showdupesfromrepos = True

        matches = []
        used_search_strings = []
        for spec in args:
            query, used_search_string = super(BaseCli, self).provides(spec)
            matches.extend(query)
            used_search_strings.extend(used_search_string)
        for pkg in matches:
            self.output.matchcallback_verbose(pkg, used_search_strings, args)
        self.conf.showdupesfromrepos = old_sdup

        if not matches:
            raise dnf.exceptions.Error(_('No Matches found'))

    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes and not self.conf.assumeno:
            return False
        return True

    def _history_get_transactions(self, extcmds):
        if not extcmds:
            logger.critical(_('No transaction ID given'))
            return None

        old = self.history.old(extcmds)
        if not old:
            logger.critical(_('Not found given transaction ID'))
            return None
        return old

    def history_get_transaction(self, extcmds):
        old = self._history_get_transactions(extcmds)
        if old is None:
            return None
        if len(old) > 1:
            logger.critical(_('Found more than one transaction ID!'))
        return old[0]

    def history_rollback_transaction(self, extcmd):
        """Rollback given transaction."""
        old = self.history_get_transaction((extcmd,))
        if old is None:
            return 1, ['Failed history rollback, no transaction']
        last = self.history.last()
        if last is None:
            return 1, ['Failed history rollback, no last?']
        if old.tid == last.tid:
            return 0, ['Rollback to current, nothing to do']

        mobj = None
        for trans in self.history.old(list(range(old.tid + 1, last.tid + 1))):
            if trans.altered_lt_rpmdb:
                logger.warning(_('Transaction history is incomplete, before %u.'), trans.tid)
            elif trans.altered_gt_rpmdb:
                logger.warning(_('Transaction history is incomplete, after %u.'), trans.tid)

            if mobj is None:
                mobj = trans
            else:
                mobj.merge(trans)

        tm = dnf.util.normalize_time(old.beg_timestamp)
        print("Rollback to transaction %u, from %s" % (old.tid, tm))
        print(self.output.fmtKeyValFill("  Undoing the following transactions: ",
                                        ", ".join((str(x) for x in mobj.tids()))))
        self.output.historyInfoCmdPkgsAltered(mobj)  # :todo

        history = dnf.history.open_history(self.history)  # :todo
        operations = dnf.history.NEVRAOperations()
        for id_ in range(old.tid + 1, last.tid + 1):
            operations += history.transaction_nevra_ops(id_)

        try:
            self._history_undo_operations(operations, old.tid + 1, True)
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s installed.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['A transaction cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s available.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['A transaction cannot be undone']
        except dnf.exceptions.MarkingError:
            assert False
        else:
            return 2, ["Rollback to transaction %u" % (old.tid,)]

    def history_undo_transaction(self, extcmd):
        """Undo given transaction."""
        old = self.history_get_transaction((extcmd,))
        if old is None:
            return 1, ['Failed history undo']

        tm = dnf.util.normalize_time(old.beg_timestamp)
        msg = _("Undoing transaction {}, from {}").format(old.tid, ucd(tm))
        logger.info(msg)
        self.output.historyInfoCmdPkgsAltered(old)  # :todo

        history = dnf.history.open_history(self.history)  # :todo

        try:
            self._history_undo_operations(
                history.transaction_nevra_ops(old.tid),
                old.tid)
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s installed.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s available.'),
                        self.output.term.bold(ucd(err.pkg_spec)))
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.MarkingError:
            assert False
        else:
            return 2, ["Undoing transaction %u" % (old.tid,)]

class Cli(object):
    def __init__(self, base):
        self.base = base
        self.cli_commands = {}
        self.command = None
        self.demands = dnf.cli.demand.DemandSheet() #:cli

        self.register_command(dnf.cli.commands.autoremove.AutoremoveCommand)
        self.register_command(dnf.cli.commands.check.CheckCommand)
        self.register_command(dnf.cli.commands.clean.CleanCommand)
        self.register_command(dnf.cli.commands.distrosync.DistroSyncCommand)
        self.register_command(dnf.cli.commands.deplist.DeplistCommand)
        self.register_command(dnf.cli.commands.downgrade.DowngradeCommand)
        self.register_command(dnf.cli.commands.group.GroupCommand)
        self.register_command(dnf.cli.commands.install.InstallCommand)
        self.register_command(dnf.cli.commands.makecache.MakeCacheCommand)
        self.register_command(dnf.cli.commands.mark.MarkCommand)
        self.register_command(dnf.cli.commands.reinstall.ReinstallCommand)
        self.register_command(dnf.cli.commands.remove.RemoveCommand)
        self.register_command(dnf.cli.commands.repolist.RepoListCommand)
        self.register_command(dnf.cli.commands.repoquery.RepoQueryCommand)
        self.register_command(dnf.cli.commands.search.SearchCommand)
        self.register_command(dnf.cli.commands.shell.ShellCommand)
        self.register_command(dnf.cli.commands.swap.SwapCommand)
        self.register_command(dnf.cli.commands.updateinfo.UpdateInfoCommand)
        self.register_command(dnf.cli.commands.upgrade.UpgradeCommand)
        self.register_command(dnf.cli.commands.upgrademinimal.UpgradeMinimalCommand)
        self.register_command(dnf.cli.commands.InfoCommand)
        self.register_command(dnf.cli.commands.ListCommand)
        self.register_command(dnf.cli.commands.ProvidesCommand)
        self.register_command(dnf.cli.commands.CheckUpdateCommand)
        self.register_command(dnf.cli.commands.RepoPkgsCommand)
        self.register_command(dnf.cli.commands.HelpCommand)
        self.register_command(dnf.cli.commands.HistoryCommand)

    def _configure_repos(self, opts):
        self.base.read_all_repos(opts)
        if opts.repofrompath:
            for label, path in opts.repofrompath.items():
                self.base.repos.add_new_repo(label, self.base.conf, baseurl=[path])
                # do not let this repo to be disabled
                opts.repos_ed.append((label, "enable"))

        if opts.repo:
            opts.repos_ed.insert(0, ("*", "disable"))
            opts.repos_ed.extend([(r, "enable") for r in opts.repo])

        notmatch = set()

        # Process repo enables and disables in order
        try:
            for (repo, operation) in opts.repos_ed:
                repolist = self.base.repos.get_matching(repo)
                if not repolist:
                    if self.base.conf.strict and operation == "enable":
                        msg = _("Unknown repo: '%s'")
                        raise dnf.exceptions.RepoError(msg % repo)
                    notmatch.add(repo)

                if operation == "enable":
                    repolist.enable()
                else:
                    repolist.disable()
        except dnf.exceptions.ConfigError as e:
            logger.critical(e)
            self.optparser.print_help()
            sys.exit(1)

        for repo in notmatch:
            logger.warning(_("No repository match: %s"), repo)

        for rid in self.base._repo_persistor.get_expired_repos():
            repo = self.base.repos.get(rid)
            if repo:
                repo._md_expire_cache()

        # setup the progress bars/callbacks
        (bar, self.base._ds_callback) = self.base.output.setup_progress_callbacks()
        self.base.repos.all().set_progress_bar(bar)
        key_import = output.CliKeyImport(self.base, self.base.output)
        self.base.repos.all()._set_key_import(key_import)

    def _log_essentials(self):
        logger.debug('DNF version: %s', dnf.const.VERSION)
        logger.log(dnf.logging.DDEBUG,
                        'Command: %s', self.cmdstring)
        logger.log(dnf.logging.DDEBUG,
                        'Installroot: %s', self.base.conf.installroot)
        logger.log(dnf.logging.DDEBUG, 'Releasever: %s',
                        self.base.conf.releasever)
        logger.debug("cachedir: %s", self.base.conf.cachedir)

    def _process_demands(self):
        demands = self.demands
        repos = self.base.repos

        if demands.root_user:
            if not dnf.util.am_i_root():
                raise dnf.exceptions.Error(_('This command has to be run under the root user.'))

        if demands.cacheonly or self.base.conf.cacheonly:
            self.base.conf.cacheonly = True
            repos.all()._md_only_cached = True
        else:
            if demands.freshest_metadata:
                for repo in repos.iter_enabled():
                    repo._md_expire_cache()
            elif not demands.fresh_metadata:
                for repo in repos.values():
                    repo._md_lazy = True

        if demands.sack_activation:
            self.base.fill_sack(load_system_repo='auto',
                                load_available_repos=self.demands.available_repos)

    def _parse_commands(self, opts, args):
        """Check that the requested CLI command exists."""

        basecmd = opts.command
        command_cls = self.cli_commands.get(basecmd)
        if command_cls is None:
            logger.critical(_('No such command: %s. Please use %s --help'),
                            basecmd, sys.argv[0])
            if self.base.conf.plugins:
                logger.critical(_("It could be a DNF plugin command, "
                            "try: \"dnf install 'dnf-command(%s)'\""), basecmd)
            else:
                logger.critical(_("It could be a DNF plugin command, "
                            "but loading of plugins is currently disabled."))
            raise CliError
        self.command = command_cls(self)

        logger.log(dnf.logging.DDEBUG, 'Base command: %s', basecmd)
        logger.log(dnf.logging.DDEBUG, 'Extra commands: %s', args)

    def configure(self, args, option_parser=None):
        """Parse command line arguments, and set up :attr:`self.base.conf` and
        :attr:`self.cmds`, as well as logger objects in base instance.

        :param args: a list of command line arguments
        :param option_parser: a class for parsing cli options
        """
        self.optparser = dnf.cli.option_parser.OptionParser() \
            if option_parser is None else option_parser
        opts = self.optparser.parse_main_args(args)

        # Just print out the version if that's what the user wanted
        if opts.version:
            print(dnf.const.VERSION)
            print_versions(self.base.conf.history_record_packages, self.base,
                           self.base.output)
            sys.exit(0)

        if opts.quiet:
            opts.debuglevel = 0
            opts.errorlevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = dnf.const.VERBOSE_LEVEL

        # Read up configuration options and initialize plugins
        try:
            self.base.conf._configure_from_options(opts)
            if opts.cacheonly:
                self.base.conf.cachedir = self.base.conf.system_cachedir
                self.demands.cacheonly = True
            self._read_conf_file(opts.releasever)
            if 'arch' in opts:
                self.base.conf.arch = opts.arch
            self.base.conf._adjust_conf_options()
        except (dnf.exceptions.ConfigError, ValueError) as e:
            logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        except IOError as e:
            e = '%s: %s' % (ucd(e.args[1]), repr(e.filename))
            logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        if opts.destdir is not None:
            self.base.conf.destdir = opts.destdir
            if not self.base.conf.downloadonly and opts.command not in (
                    'download', 'system-upgrade'):
                logger.critical(
                    _('--destdir must be used with --downloadonly or download command.')
                )
                sys.exit(1)

        if opts.sleeptime is not None:
            time.sleep(random.randrange(opts.sleeptime * 60))

        # store the main commands & summaries, before plugins are loaded
        self.optparser.add_commands(self.cli_commands, 'main')
        # store the plugin commands & summaries
        self.base.init_plugins(opts.disableplugin, opts.enableplugin, self)
        self.optparser.add_commands(self.cli_commands,'plugin')

        # show help if no command specified
        # this is done here, because we first have the full
        # usage info after the plugins are loaded.
        if not opts.command:
            self.optparser.print_help()
            sys.exit(0)

        # save our original args out
        self.base.args = args
        # save out as a nice command string
        self.cmdstring = dnf.const.PROGRAM_NAME + ' '
        for arg in self.base.args:
            self.cmdstring += '%s ' % arg

        self._log_essentials()
        try:
            self._parse_commands(opts, args)
        except CliError:
            sys.exit(1)

        # show help for dnf <command> --help / --help-cmd
        if opts.help:
            self.optparser.print_help(self.command)
            sys.exit(0)

        opts = self.optparser.parse_command_args(self.command, args)

        if opts.allowerasing:
            self.demands.allow_erasing = opts.allowerasing
            self.base._allow_erasing = True
        if opts.freshest_metadata:
            self.demands.freshest_metadata = opts.freshest_metadata
        if opts.debugsolver:
            self.base.conf.debug_solver = True
        if opts.obsoletes:
            self.base.conf.obsoletes = True
        self.command.pre_configure()
        self.base.pre_configure_plugins()

        # with cachedir in place we can configure stuff depending on it:
        self.base._activate_persistor()

        self._configure_repos(opts)

        self.base.configure_plugins()

        self.base.conf._configure_from_options(opts)

        self.command.configure()

        if self.base.conf.destdir:
            dnf.util.ensure_dir(self.base.conf.destdir)
            self.base.repos.all().pkgdir = self.base.conf.destdir

        if self.base.conf.color != 'auto':
            self.base.output.term.reinit(color=self.base.conf.color)

    def _read_conf_file(self, releasever=None):
        timer = dnf.logging.Timer('config')
        conf = self.base.conf

        # search config file inside the installroot first
        conf._search_inside_installroot('config_file_path')

        # read config
        conf.read(priority=dnf.conf.PRIO_MAINCONFIG)

        # search reposdir file inside the installroot first
        conf._search_inside_installroot('reposdir')

        # cachedir, logs, releasever, and gpgkey are taken from or stored in installroot
        subst = conf.substitutions
        subst.update_from_etc(conf.installroot)
        if releasever is None and conf.releasever is None:
            releasever = dnf.rpm.detect_releasever(conf.installroot)
        elif releasever == '/':
            releasever = dnf.rpm.detect_releasever(releasever)
        if releasever is not None:
            conf.releasever = releasever
        if conf.releasever is None:
            logger.warning(_("Unable to detect release version (use '--releasever' to specify "
                             "release version)"))

        for opt in ('cachedir', 'logdir', 'persistdir'):
            conf.prepend_installroot(opt)

        self.base._logging._setup_from_dnf_conf(conf)

        timer()
        return conf

    def _populate_update_security_filter(self, opts, query, cmp_type='eq', all=None):
        """

        :param opts:
        :param query: base package set for filters
        :param cmp_type: string like "eq", "gt", "gte", "lt", "lte"
        :param all:
        :return:
        """
        if (opts is None) and (all is None):
            return
        filters = []
        if opts.bugfix or all:
            key = {'advisory_type__' + cmp_type: 'bugfix'}
            filters.append(query.filter(**key))
        if opts.enhancement or all:
            key = {'advisory_type__' + cmp_type: 'enhancement'}
            filters.append(query.filter(**key))
        if opts.newpackage or all:
            key = {'advisory_type__' + cmp_type: 'newpackage'}
            filters.append(query.filter(**key))
        if opts.security or all:
            key = {'advisory_type__' + cmp_type: 'security'}
            filters.append(query.filter(**key))
        if opts.advisory:
            key = {'advisory__' + cmp_type: opts.advisory}
            filters.append(query.filter(**key))
        if opts.bugzilla:
            key = {'advisory_bug__' + cmp_type: opts.bugzilla}
            filters.append(query.filter(**key))
        if opts.cves:
            key = {'advisory_cve__' + cmp_type: opts.cves}
            filters.append(query.filter(**key))
        if opts.severity:
            key = {'advisory_severity__' + cmp_type: opts.severity}
            filters.append(query.filter(**key))
        self.base._update_security_filters = filters

    def redirect_logger(self, stdout=None, stderr=None):
        """
        Change minimal logger level for terminal output to stdout and stderr according to specific
        command requirements
        @param stdout: logging.INFO, logging.WARNING, ...
        @param stderr:logging.INFO, logging.WARNING, ...
        """
        if stdout is not None:
            self.base._logging.stdout_handler.setLevel(stdout)
        if stderr is not None:
            self.base._logging.stderr_handler.setLevel(stderr)

    def _check_running_kernel(self):
        kernel = self.base.sack.get_running_kernel()
        if kernel is None:
            return

        q = self.base.sack.query().filterm(provides=kernel.name)
        q = q.installed()
        q.filterm(advisory_type='security')

        ikpkg = kernel
        for pkg in q:
            if pkg > ikpkg:
                ikpkg = pkg

        if ikpkg > kernel:
            print('Security: %s is an installed security update' % ikpkg)
            print('Security: %s is the currently running version' % kernel)

    def _option_conflict(self, option_string_1, option_string_2):
        print(self.optparser.print_usage())
        raise dnf.exceptions.Error(_("argument {}: not allowed with argument {}".format(
            option_string_1, option_string_2)))

    def register_command(self, command_cls):
        """Register a Command. :api"""
        for name in command_cls.aliases:
            if name in self.cli_commands:
                raise dnf.exceptions.ConfigError(_('Command "%s" already defined') % name)
            self.cli_commands[name] = command_cls

    def run(self):
        """Call the base command, and pass it the extended commands or
           arguments.

        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        self._process_demands()
        return self.command.run()
