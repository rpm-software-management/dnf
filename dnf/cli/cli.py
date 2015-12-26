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
import datetime
import dnf
import dnf.cli.commands
import dnf.cli.commands.autoremove
import dnf.cli.commands.clean
import dnf.cli.commands.distrosync
import dnf.cli.commands.downgrade
import dnf.cli.commands.remove
import dnf.cli.commands.group
import dnf.cli.commands.install
import dnf.cli.commands.makecache
import dnf.cli.commands.mark
import dnf.cli.commands.reinstall
import dnf.cli.commands.repolist
import dnf.cli.commands.search
import dnf.cli.commands.updateinfo
import dnf.cli.commands.upgrade
import dnf.cli.commands.upgradeto
import dnf.cli.demand
import dnf.cli.option_parser
import dnf.conf
import dnf.conf.parser
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
import dnf.yum.config
import dnf.yum.misc
import hawkey
import logging
import operator
import os
import re
import sys
import time

logger = logging.getLogger('dnf')


def _add_pkg_simple_list_lens(data, pkg, indent=''):
    """ Get the length of each pkg's column. Add that to data.
        This "knows" about simpleList and printVer. """
    na = len(pkg.name) + 1 + len(pkg.arch) + len(indent)
    ver = len(pkg.evr)
    rid = len(pkg.from_repo)
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


def cachedir_fit(conf):
    cli_cache = dnf.conf.CliCache(conf.cachedir)
    return cli_cache.cachedir, cli_cache.system_cachedir


def print_versions(pkgs, base, output):
    def sm_ui_time(x):
        return time.strftime("%Y-%m-%d %H:%M", time.gmtime(x))
    def sm_ui_date(x): # For changelogs, there is no time
        return time.strftime("%Y-%m-%d", time.gmtime(x))

    rpmdb_sack = dnf.sack.rpmdb_sack(base)
    done = False
    for pkg in rpmdb_sack.query().installed().filter(name=pkgs):
        if done:
            print("")
        done = True
        if pkg.epoch == '0':
            ver = '%s-%s.%s' % (pkg.version, pkg.release, pkg.arch)
        else:
            ver = '%s:%s-%s.%s' % (pkg.epoch,
                                   pkg.version, pkg.release, pkg.arch)
        name = "%s%s%s" % (output.term.MODE['bold'], pkg.name,
                           output.term.MODE['normal'])
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
        self.cmd_conf = CmdConf()
        conf = conf or dnf.conf.Conf()
        super(BaseCli, self).__init__(conf=conf)
        self.output = output.Output(self, self.conf)

    def _groups_diff(self):
        if not self.group_persistor:
            return None
        return self.group_persistor.diff()

    def do_transaction(self, display=()):
        """Take care of package downloading, checking, user
        confirmation and actually running the transaction.

        :param display: `rpm.callback.TransactionProgress` object(s)
        :return: a numeric return code, and optionally a list of
           errors.  A negative return code indicates that errors
           occurred in the pre-transaction checks
        """

        grp_diff = self._groups_diff()
        grp_str = self.output.list_group_transaction(self.comps, self.group_persistor, grp_diff)
        if grp_str:
            logger.info(grp_str)
        trans = self.transaction
        pkg_str = self.output.list_transaction(trans)
        if pkg_str:
            logger.info(pkg_str)

        if trans:
            # Check which packages have to be downloaded
            downloadpkgs = []
            rmpkgs = []
            stuff_to_download = False
            install_only = True
            for tsi in trans:
                installed = tsi.installed
                if installed is not None:
                    stuff_to_download = True
                    downloadpkgs.append(installed)
                erased = tsi.erased
                if erased is not None:
                    install_only = False
                    rmpkgs.append(erased)

            # Close the connection to the rpmdb so that rpm doesn't hold the
            # SIGINT handler during the downloads.
            del self.ts

            # report the total download size to the user
            if not stuff_to_download:
                self.output.reportRemoveSize(rmpkgs)
            else:
                self.output.reportDownloadSize(downloadpkgs, install_only)

        if trans or (grp_diff and not grp_diff.empty()):
            # confirm with user
            if self._promptWanted():
                if self.conf.assumeno or not self.output.userconfirm():
                    raise CliError(_("Operation aborted."))
        else:
            logger.info(_('Nothing to do.'))
            return

        if trans:
            if downloadpkgs:
                logger.info(_('Downloading Packages:'))
            try:
                total_cb = self.output.download_callback_total_cb
                self.download_packages(downloadpkgs, self.output.progress,
                                       total_cb)
            except dnf.exceptions.DownloadError as e:
                specific = dnf.cli.format.indent_block(ucd(e))
                errstring = _('Error downloading packages:\n%s') % specific
                # setting the new line to prevent next chars being eaten up by carriage returns
                print()
                raise dnf.exceptions.Error(errstring)
            # Check GPG signatures
            self.gpgsigcheck(downloadpkgs)

        if self.cmd_conf.downloadonly:
            return

        if not isinstance(display, collections.Sequence):
            display = [display]
        display = [output.CliTransactionDisplay()] + list(display)
        super(BaseCli, self).do_transaction(display)
        if trans:
            msg = self.output.post_transaction_output(trans)
            logger.info(msg)

    def gpgsigcheck(self, pkgs):
        """Perform GPG signature verification on the given packages,
        installing keys if possible.

        :param pkgs: a list of package objects to verify the GPG
           signatures of
        :return: non-zero if execution should stop due to an error
        :raises: Will raise :class:`Error` if there's a problem
        """
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)

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
                self.getKeyForPackage(po, fn)

            else:
                # Fatal error
                raise dnf.exceptions.Error(errmsg)

        return 0

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

    def upgrade_userlist_to(self, userlist, reponame=None):
        oldcount = self._goal.req_length()
        for l in userlist:
            self.upgrade_to(l, reponame)
        cnt = self._goal.req_length() - oldcount
        if cnt <= 0:
            raise dnf.exceptions.Error(_('No packages marked for upgrade.'))

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

    def downgradePkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and downgrade them. If a complete version number if
        specified, attempt to downgrade them to the specified version

        :param userlist: a list of names or wildcards specifying
           packages to downgrade
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        oldcount = self._goal.req_length()

        for arg in userlist:
            wildcard = True if dnf.util.is_glob_pattern(arg) else False
            if arg.endswith('.rpm'):
                pkg = self.add_remote_rpm(arg)
                self.package_downgrade(pkg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.downgrade_to(arg)
            except dnf.exceptions.PackageNotFoundError as err:
                msg = _('No package %s%s%s available.')
                logger.info(msg, self.output.term.MODE['bold'], arg,
                                 self.output.term.MODE['normal'])
            except dnf.exceptions.PackagesNotInstalledError as err:
                if not wildcard:
                # glob pattern should not match not installed packages -> ignore error
                    for pkg in err.packages:
                        logger.info(_('No match for available package: %s'), pkg)
            except dnf.exceptions.MarkingError:
                assert False
        cnt = self._goal.req_length() - oldcount
        if cnt <= 0:
            raise dnf.exceptions.Error(_('Nothing to do.'))

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
            rup = self.output.listPkgs(ypl.updates, _('Upgraded Packages'), basecmd,
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

        ypl = self.doPackageLists(
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
        for spec in args:
            matches.extend(super(BaseCli, self). provides(spec))
        for pkg in matches:
            self.output.matchcallback_verbose(pkg, [], args)
        self.conf.showdupesfromrepos = old_sdup

        if not matches:
            raise dnf.exceptions.Error(_('No Matches found'))

    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes and not self.conf.assumeno:
            return False
        if self.conf.alwaysprompt:
            return True

        # prompt if:
        #  package was added to fill a dependency
        #  package is being removed
        #  package wasn't explicitly given on the command line
        for txmbr in self.tsInfo.getMembers():
            if txmbr.isDep or \
                   txmbr.name not in self.extcmds:
                return True

        # otherwise, don't prompt
        return False

    @staticmethod
    def transaction_id_or_offset(extcmd):
        """Convert user input to a transaction ID or an offset from the end."""
        try:
            offset_str, = re.match('^last(-\d+)?$', extcmd).groups()
        except AttributeError:  # extcmd does not match the regex.
            id_ = int(extcmd)
            if id_ < 0:
                # Negative return values are reserved for offsets.
                raise ValueError('bad transaction ID given: %s' % extcmd)
            return id_
        else:
            # Was extcmd 'last-N' or just 'last'?
            offset = int(offset_str) if offset_str else 0
            # Return offsets as negative numbers, where -1 means the last
            # transaction as when indexing sequences.
            return offset - 1

    def _history_get_transactions(self, extcmds):
        if not extcmds:
            logger.critical(_('No transaction ID given'))
            return None

        tids = []
        last = None
        for extcmd in extcmds:
            try:
                id_or_offset = self.transaction_id_or_offset(extcmd)
            except ValueError:
                logger.critical(_('Bad transaction ID given'))
                return None

            if id_or_offset < 0:
                if last is None:
                    cto = False
                    last = self.history.last(complete_transactions_only=cto)
                    if last is None:
                        logger.critical(_('Bad transaction ID given'))
                        return None
                tids.append(str(last.tid + id_or_offset + 1))
            else:
                tids.append(str(id_or_offset))

        old = self.history.old(tids)
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
        for tid in self.history.old(list(range(old.tid + 1, last.tid + 1))):
            if tid.altered_lt_rpmdb:
                logger.warning(_('Transaction history is incomplete, before %u.'), tid.tid)
            elif tid.altered_gt_rpmdb:
                logger.warning(_('Transaction history is incomplete, after %u.'), tid.tid)

            if mobj is None:
                mobj = dnf.yum.history.YumMergedHistoryTransaction(tid)
            else:
                mobj.merge(tid)

        tm = time.ctime(old.beg_timestamp)
        print("Rollback to transaction %u, from %s" % (old.tid, tm))
        print(self.output.fmtKeyValFill("  Undoing the following transactions: ",
                                      ", ".join((str(x) for x in mobj.tid))))
        self.output.historyInfoCmdPkgsAltered(mobj)  # :todo

        history = dnf.history.open_history(self.history)  # :todo
        operations = dnf.history.NEVRAOperations()
        for id_ in range(old.tid + 1, last.tid + 1):
            operations += history.transaction_nevra_ops(id_)

        hibeg = self.output.term.MODE['bold']
        hiend = self.output.term.MODE['normal']
        try:
            self.history_undo_operations(operations)
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s%s%s installed.'),
                             hibeg, ucd(err.pkg_spec), hiend)
            return 1, ['A transaction cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s%s%s available.'),
                             hibeg, ucd(err.pkg_spec), hiend)
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

        tm = time.ctime(old.beg_timestamp)
        print("Undoing transaction %u, from %s" % (old.tid, tm))
        self.output.historyInfoCmdPkgsAltered(old)  # :todo

        history = dnf.history.open_history(self.history)  # :todo

        hibeg = self.output.term.MODE['bold']
        hiend = self.output.term.MODE['normal']
        try:
            self.history_undo_operations(history.transaction_nevra_ops(old.tid))
        except dnf.exceptions.PackagesNotInstalledError as err:
            logger.info(_('No package %s%s%s installed.'),
                             hibeg, ucd(err.pkg_spec), hiend)
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            logger.info(_('No package %s%s%s available.'),
                             hibeg, ucd(err.pkg_spec), hiend)
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.MarkingError:
            assert False
        else:
            return 2, ["Undoing transaction %u" % (old.tid,)]

class Cli(object):
    def __init__(self, base):
        self._system_cachedir = None
        self.base = base
        self.cli_commands = {}
        self.command = None
        self.demands = dnf.cli.demand.DemandSheet() #:cli
        self.main_setopts = {}
        self.nogpgcheck = False
        self.repo_setopts = {}

        self.register_command(dnf.cli.commands.autoremove.AutoremoveCommand)
        self.register_command(dnf.cli.commands.clean.CleanCommand)
        self.register_command(dnf.cli.commands.distrosync.DistroSyncCommand)
        self.register_command(dnf.cli.commands.downgrade.DowngradeCommand)
        self.register_command(dnf.cli.commands.group.GroupCommand)
        self.register_command(dnf.cli.commands.install.InstallCommand)
        self.register_command(dnf.cli.commands.makecache.MakeCacheCommand)
        self.register_command(dnf.cli.commands.mark.MarkCommand)
        self.register_command(dnf.cli.commands.reinstall.ReinstallCommand)
        self.register_command(dnf.cli.commands.remove.RemoveCommand)
        self.register_command(dnf.cli.commands.repolist.RepoListCommand)
        self.register_command(dnf.cli.commands.search.SearchCommand)
        self.register_command(dnf.cli.commands.updateinfo.UpdateInfoCommand)
        self.register_command(dnf.cli.commands.upgrade.UpgradeCommand)
        self.register_command(dnf.cli.commands.upgradeto.UpgradeToCommand)
        self.register_command(dnf.cli.commands.InfoCommand)
        self.register_command(dnf.cli.commands.ListCommand)
        self.register_command(dnf.cli.commands.ProvidesCommand)
        self.register_command(dnf.cli.commands.CheckUpdateCommand)
        self.register_command(dnf.cli.commands.RepoPkgsCommand)
        self.register_command(dnf.cli.commands.HelpCommand)
        self.register_command(dnf.cli.commands.HistoryCommand)

    def _configure_cachedir(self):
        """Set CLI-specific cachedir and its alternative."""
        conf = self.base.conf
        conf.cachedir, self._system_cachedir = cachedir_fit(conf)
        logger.debug("cachedir: %s", conf.cachedir)

    def _configure_repos(self, opts):
        self.base.read_all_repos(self.repo_setopts)
        if opts.repofrompath:
            for label, path in opts.repofrompath.items():
                if path[0] == '/':
                    path = 'file://' + path
                repofp = dnf.repo.Repo(label, self.base.conf.cachedir)
                repofp.baseurl = path
                self.base.repos.add(repofp)
                logger.info(_("Added %s repo from %s"), label, path)

        # Process repo enables and disables in order
        try:
            for (repo, operation) in opts.repos_ed:
                repolist = self.base.repos.get_matching(repo)
                if not repolist:
                    msg = _("Unknown repo: '%s'")
                    raise dnf.exceptions.RepoError(msg % repo)
                if operation == "enable":
                    repolist.enable()
                else:
                    repolist.disable()
        except dnf.exceptions.ConfigError as e:
            logger.critical(e)
            self.print_usage()
            sys.exit(1)

        if self.nogpgcheck:
            for repo in self.base.repos.values():
                repo.gpgcheck = False
                repo.repo_gpgcheck = False

        for rid in self.base.repo_persistor.get_expired_repos():
            repo = self.base.repos.get(rid)
            if repo:
                repo.md_expire_cache()

        if opts.cacheonly:
            self.demands.cacheonly = True
            for repo in self.base.repos.values():
                repo.basecachedir = self._system_cachedir
                repo.md_only_cached = True

        # setup the progress bars/callbacks
        (bar, self.base.ds_callback) = self.base.output.setup_progress_callbacks()
        self.base.repos.all().set_progress_bar(bar)
        key_import = output.CliKeyImport(self.base, self.base.output)
        self.base.repos.all().set_key_import(key_import)

    def _log_essentials(self):
        logger.debug('DNF version: %s', dnf.const.VERSION)
        logger.log(dnf.logging.DDEBUG,
                        'Command: %s', self.cmdstring)
        logger.log(dnf.logging.DDEBUG,
                        'Installroot: %s', self.base.conf.installroot)
        logger.log(dnf.logging.DDEBUG, 'Releasever: %s',
                        self.base.conf.releasever)

    def _process_demands(self):
        demands = self.demands
        repos = self.base.repos

        if not demands.cacheonly:
            if demands.freshest_metadata:
                for repo in repos.iter_enabled():
                    repo.md_expire_cache()
            elif not demands.fresh_metadata:
                for repo in repos.values():
                    repo.md_lazy = True

        if demands.sack_activation:
            lar = self.demands.available_repos
            self.base.fill_sack(load_system_repo='auto',
                                load_available_repos=lar)
            if lar:
                repos = list(self.base.repos.iter_enabled())
                if repos:
                    mts = max(repo.metadata.timestamp for repo in repos)
                    # do not bother users with fractions of seconds
                    age = int(min(repo.metadata.age for repo in repos))
                    for repo in repos:
                        logger.debug(_("%s: using metadata from %s."),
                                     repo.id,
                                     time.ctime(repo.metadata.md_timestamp))
                    logger.info(_("Last metadata expiration check performed "
                                  "%s ago on %s."),
                                datetime.timedelta(seconds=age),
                                time.ctime(mts))
            self.base.plugins.run_sack()

    def _root_and_conffile(self, installroot, conffile):
        """After the first parse of the cmdline options, find initial values for
        installroot and conffile.

        :return: installroot and conffile strings
        """
        # If the conf file is inside the  installroot - use that.
        # otherwise look for it in the normal root
        if installroot and conffile:
            abs_fn = os.path.join(installroot, conffile)
            if os.access(abs_fn, os.R_OK):
                conffile = abs_fn
        elif installroot:
            conffile = dnf.const.CONF_FILENAME
            abs_fn = os.path.join(installroot, conffile[1:])
            if os.access(abs_fn, os.R_OK):
                conffile = abs_fn
        if installroot is None:
            installroot = '/'
        if conffile is None:
            conffile = dnf.const.CONF_FILENAME
        return installroot, conffile

    def _parse_commands(self):
        """Check that the requested CLI command exists."""

        if len(self.base.cmds) < 1:
            logger.critical(_('You need to give some command'))
            self.print_usage()
            raise CliError

        basecmd = self.base.cmds[0] # our base command
        command_cls = self.cli_commands.get(basecmd)
        if command_cls is None:
            logger.critical(_('No such command: %s. Please use %s --help'),
                            basecmd, sys.argv[0])
            if self.base.conf.plugins:
                logger.info(_("It could be a DNF plugin command, "
                            "try: \"dnf install 'dnf-command(%s)'\""), basecmd)
            else:
                logger.info(_("It could be a DNF plugin command, "
                            "but loading of plugins is currently disabled."))
            raise CliError
        self.command = command_cls(self)

        (base, ext) = self.command.canonical(self.base.cmds)
        self.base.basecmd, self.base.extcmds = (base, ext)
        logger.log(dnf.logging.DDEBUG, 'Base command: %s', base)
        logger.log(dnf.logging.DDEBUG, 'Extra commands: %s', ext)

    def _parse_setopts(self, setopts):
        """Parse setopts and repo_setopts."""

        repoopts = {}
        mainopts = dnf.yum.misc.GenericHolder()
        mainopts.items = []

        bad_setopt_tm = []
        bad_setopt_ne = []

        for item in setopts:
            vals = item.split('=')
            if len(vals) > 2:
                bad_setopt_tm.append(item)
                continue
            if len(vals) < 2:
                bad_setopt_ne.append(item)
                continue
            k,v = vals
            period = k.find('.')
            if period != -1:
                repo = k[:period]
                k = k[period+1:]
                if repo not in repoopts:
                    repoopts[repo] = dnf.yum.misc.GenericHolder()
                    repoopts[repo].items = []
                setattr(repoopts[repo], k, v)
                repoopts[repo].items.append(k)
            else:
                setattr(mainopts, k, v)
                mainopts.items.append(k)

        self.main_setopts = mainopts
        self.repo_setopts = repoopts

        return bad_setopt_tm, bad_setopt_ne

    def _get_first_config(self, opts):
        config_args = ['noplugins', 'version', "quiet", "verbose", 'conffile',
                       'debuglevel', 'errorlevel', 'installroot', 'releasever',
                       'setopt']
        in_dict = opts.__dict__
        return {k: in_dict[k] for k in in_dict if k in config_args}

    def configure(self, args):
        """Parse command line arguments, and set up :attr:`self.base.conf` and
        :attr:`self.cmds`, as well as logger objects in base instance.

        :param args: a list of command line arguments
        """
        self.optparser = dnf.cli.option_parser.OptionParser()
        opts, cmds = self.optparser.parse_known_args(args)

        # Just print out the version if that's what the user wanted
        if opts.version:
            print(dnf.const.VERSION)
            opts.quiet = True
            opts.verbose = False

        # go through all the setopts and set the global ones
        bad_setopt_tm, bad_setopt_ne = self._parse_setopts(opts.setopts)

        if self.main_setopts:
            for opt in self.main_setopts.items:
                setattr(opts, opt, getattr(self.main_setopts, opt))

        # get the install root to use
        self.optparser._checkAbsInstallRoot(opts.installroot)
        (root, opts.conffile) = self._root_and_conffile(opts.installroot,
                                                        opts.conffile)
        # the conffile is solid now
        assert(opts.conffile is not None)
        if opts.quiet:
            opts.debuglevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = dnf.const.VERBOSE_LEVEL

        # Read up configuration options and initialize plugins
        overrides = self.optparser._non_nones2dict(self._get_first_config(opts))
        releasever = opts.releasever
        try:
            self.read_conf_file(opts.conffile, root, releasever, overrides)

            # now set all the non-first-start opts from main from our setopts
            if self.main_setopts:
                for opt in self.main_setopts.items:
                    if not hasattr(self.base.conf, opt):
                        msg ="Main config did not have a %s attr. before setopt"
                        logger.warning(msg, opt)
                    setattr(self.base.conf, opt, getattr(self.main_setopts, opt))

        except (dnf.exceptions.ConfigError, ValueError) as e:
            logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        except IOError as e:
            e = '%s: %s' % (ucd(e.args[1]), repr(e.filename))
            logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        for item in bad_setopt_tm:
            msg = "Setopt argument has multiple values: %s"
            logger.warning(msg, item)
        for item in bad_setopt_ne:
            msg = "Setopt argument has no value: %s"
            logger.warning(msg, item)

        self.optparser.configure_from_options(opts, self.base.conf, self.demands,
                                              self.base.output)
        self.base.cmds = cmds

        if opts.version:
            opts.quiet = True
            opts.verbose = False
        if opts.quiet:
            opts.debuglevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = dnf.const.VERBOSE_LEVEL
        self.nogpgcheck = opts.nogpgcheck

        # the configuration reading phase is now concluded, finish the init
        self._configure_cachedir()
        # with cachedir in place we can configure stuff depending on it:
        self.base.activate_persistor()
        self._configure_repos(opts)

        if opts.version:
            print_versions(self.base.conf.history_record_packages, self.base,
                           self.base.output)
            sys.exit(0)

        # store the main commands & summaries, before plugins are loaded
        self.optparser.add_commands(self.cli_commands, 'main')
        if self.base.conf.plugins:
            self.base.plugins.load(self.base.conf.pluginpath, opts.disableplugins)
        self.base.plugins.run_init(self.base, self)
        # store the plugin commands & summaries
        self.optparser.add_commands(self.cli_commands,'plugin')

        # build the usage info and put it into the optparser.
        self.optparser.usage = self.optparser.get_usage()

        # show help if the user requests it
        # this is done here, because we first have the full
        # usage info after the plugins are loaded.
        if opts.help:
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
            self._parse_commands() # before we return check over the base command
                                  # + args make sure they match/make sense
        except CliError:
            sys.exit(1)
        self.command.configure(self.base.extcmds)

        if opts.debugsolver:
            self.base.conf.debug_solver = True

        self.base.cmd_conf.downloadonly = opts.downloadonly

        self.base.plugins.run_config()

    def check(self):
        """Make sure the command line and options make sense."""
        self.command.doCheck(self.base.basecmd, self.base.extcmds)

    def read_conf_file(self, path=None, root="/", releasever=None,
                       overrides=None):
        timer = dnf.logging.Timer('config')
        conf = self.base.conf
        conf.installroot = root
        conf.read(path)
        if releasever is None:
            releasever = dnf.rpm.detect_releasever(root)
        conf.releasever = releasever
        subst = conf.substitutions
        subst.update_from_etc(root)

        if overrides is not None:
            conf.override(overrides)

        conf.logdir = dnf.yum.config.logdir_fit(conf.logdir)
        for opt in ('cachedir', 'logdir', 'persistdir'):
            conf.prepend_installroot(opt)
            conf._var_replace(opt)

        self.base.logging.setup_from_dnf_conf(conf)

        timer()
        return conf

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
        return self.command.run(self.base.extcmds)

    def print_usage(self):
        return self.optparser.print_usage()


class CmdConf(object):
    """Class for storing nonpersistent configuration"""
    downloadonly = False
