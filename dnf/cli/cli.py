# Copyright 2005 Duke University
# Copyright (C) 2012-2014  Red Hat, Inc.
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
from dnf.cli import CliError
from dnf.i18n import ucd, _, P_

import dnf
import dnf.cli.commands
import dnf.cli.commands.downgrade
import dnf.cli.commands.group
import dnf.cli.commands.install
import dnf.cli.commands.reinstall
import dnf.cli.commands.upgrade
import dnf.cli.commands.distrosync
import dnf.cli.demand
import dnf.cli.option_parser
import dnf.conf
import dnf.const
import dnf.exceptions
import dnf.cli.format
import dnf.logging
import dnf.match_counter
import dnf.plugin
import dnf.persistor
import dnf.sack
import dnf.util
import dnf.yum.config
import dnf.yum.misc
import dnf.yum.parser
import hawkey
import logging
import operator
import os
from . import output
import random
import re
import signal
import sys
import time
from functools import reduce
from dnf.pycomp import unicode

def _add_pkg_simple_list_lens(data, pkg, indent=''):
    """ Get the length of each pkg's column. Add that to data.
        This "knows" about simpleList and printVer. """
    na = len(pkg.name) + 1 + len(pkg.arch) + len(indent)
    ver = len(pkg.evr)
    rid = len(pkg.reponame)
    for (d, v) in (('na', na), ('ver', ver), ('rid', rid)):
        data[d].setdefault(v, 0)
        data[d][v] += 1

def _list_cmd_calc_columns(output, ypl):
    """ Work out the dynamic size of the columns to pass to fmtColumns. """
    data = {'na' : {}, 'ver' : {}, 'rid' : {}}
    for lst in (ypl.installed, ypl.available, ypl.extras,
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

def sigquit(signum, frame):
    """SIGQUIT handler for the yum cli.  This function will print an
    error message and exit the program.

    :param signum: unused
    :param frame: unused
    """
    print("Quit signal sent - exiting immediately", file=sys.stderr)
    sys.exit(1)

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

    def __init__(self):
        # handle sigquit early on
        signal.signal(signal.SIGQUIT, sigquit)
        dnf.Base.__init__(self)
        self.output = output.Output(self, self.conf)
        self.logger = logging.getLogger("dnf")

    def errorSummary(self, errstring):
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
            summary += _('Disk Requirements:\n')
            for k in disk:
                summary += P_('  At least %dMB more space needed on the %s filesystem.\n', '  At least %dMB more space needed on the %s filesystem.\n', disk[k]) % (disk[k], k)

        # TODO: simplify the dependency errors?

        # Fixup the summary
        summary = _('Error Summary\n-------------\n') + summary

        return summary

    def do_transaction(self):
        """Take care of package downloading, checking, user
        confirmation and actually running the transaction.

        :return: a numeric return code, and optionally a list of
           errors.  A negative return code indicates that errors
           occurred in the pre-transaction checks
        """
        # make sure there's something to do
        if len(self._transaction) == 0:
            msg = _('Trying to run the transaction but nothing to do. Exiting.')
            self.logger.info(msg)
            return -1, None

        lsts = self.output.list_transaction(self.transaction)
        self.logger.info(lsts)
        # Check which packages have to be downloaded
        downloadpkgs = []
        rmpkgs = []
        stuff_to_download = False
        install_only = True
        for tsi in self._transaction:
            installed = tsi.installed
            if installed is not None:
                stuff_to_download = True
                downloadpkgs.append(installed)
            erased = tsi.erased
            if erased is not None:
                install_only = False
                rmpkgs.append(erased)

        # Close the connection to the rpmdb so that rpm doesn't hold the SIGINT
        # handler during the downloads.
        del self.ts

        # report the total download size to the user
        if not stuff_to_download:
            self.output.reportRemoveSize(rmpkgs)
        else:
            self.output.reportDownloadSize(downloadpkgs, install_only)

        # confirm with user
        if self._promptWanted():
            if self.conf.assumeno or not self.output.userconfirm():
                self.logger.info(_('Exiting on user Command'))
                return -1, None


        if downloadpkgs:
            self.logger.info(_('Downloading Packages:'))
        try:
            total_cb = self.output.download_callback_total_cb
            self.download_packages(downloadpkgs, self.output.progress, total_cb)
        except dnf.exceptions.DownloadError as e:
            specific = dnf.cli.format.indent_block(str(e))
            errstring = _('Error downloading packages:\n%s') % specific
            raise dnf.exceptions.Error(errstring)

        # Check GPG signatures
        if self.gpgsigcheck(downloadpkgs) != 0:
            return -1, None

        display = output.CliTransactionDisplay()
        return_code, resultmsgs = super(BaseCli, self).do_transaction(display)
        if return_code == 0:
            msg = self.output.post_transaction_output(self.transaction)
            self.logger.info(msg)
        return return_code, resultmsgs

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
                if not sys.stdin.isatty() and not ay:
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

    def _maybeYouMeant(self, arg):
        """ If install argument doesn't match with case, tell the user. """
        matches = self.doPackageLists(patterns=[arg], ignore_case=True)
        matches = matches.installed + matches.available
        matches = set(map(lambda x: x.name, matches))
        if matches:
            msg = self.output.fmtKeyValFill(_('  * Maybe you meant: '),
                                            ", ".join(matches))
            self.logger.info(unicode(msg))

    def _checkMaybeYouMeant(self, arg, always_output=True, rpmdb_only=False):
        """ If the update/remove argument doesn't match with case, or due
            to not being installed, tell the user. """
        # always_output is a wart due to update/remove not producing the
        # same output.
        # if it is a grouppattern then none of this is going to make any sense
        # skip it.
        return False # :hawkey
        if not arg or arg[0] == '@':
            return

        pkgnarrow='all'
        if rpmdb_only:
            pkgnarrow='installed'

        matches = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=[arg], ignore_case=False)
        if (matches.installed or (not matches.available and
                                  self.returnInstalledPackagesByDep(arg))):
            return # Found a match so ignore
        hibeg = self.term.MODE['bold']
        hiend = self.term.MODE['normal']
        if matches.available:
            self.logger.info(
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return

        # No package name, so do the maybeYouMeant thing here too
        matches = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=[arg], ignore_case=True)
        if not matches.installed and matches.available:
            self.logger.info(
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return
        matches = set(map(lambda x: x.name, matches.installed))
        if always_output or matches:
            self.logger.info(
                                    _('No package %s%s%s available.'),
                                    hibeg, arg, hiend)
        if matches:
            msg = self.output.fmtKeyValFill(_('  * Maybe you meant: '),
                                            ", ".join(matches))
            self.logger.info(msg)

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
            if arg.endswith('.rpm'):
                pkg = self.add_remote_rpm(arg)
                self.package_downgrade(pkg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.downgrade(arg)
            except dnf.exceptions.PackageNotFoundError as err:
                msg = _('No package %s%s%s available.')
                self.logger.info(msg, self.output.term.MODE['bold'], arg,
                                 self.output.term.MODE['normal'])
                self._maybeYouMeant(arg)
            except dnf.exceptions.PackagesNotInstalledError as err:
                for pkg in err.packages:
                    self.logger.info(_('No match for available package: %s'), pkg)
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
               rrap[0] and rop[0] and rup[0] and rep[0] and rap[0] and rip[0]:
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

    def deplist(self, args):
        """Print out a formatted list of dependencies for a list of
        packages.  This is a cli wrapper method for
        :class:`dnf.yum.base.Base.findDeps`.

        :param args: a list of names or wildcards specifying packages
           that should have their dependenices printed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # :dead
        pkgs = []
        for arg in args:
            if arg.endswith('.rpm'):
                # :hawkey
                # thispkg = dnf.yum.packages.YumUrlPackage(self, self.ts, arg)
                thispkg = None
                pkgs.append(thispkg)
            elif self.conf.showdupesfromrepos:
                pkgs.extend(self.pkgSack.returnPackages(patterns=[arg]))
            else:
                try:
                    pkgs.extend(self.pkgSack.returnNewestByName(patterns=[arg]))
                except dnf.exceptions.Error:
                    pass

        results = self.findDeps(pkgs)
        self.output.depListOutput(results)

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

    def cleanCli(self, userlist):
        """Remove data from the yum cache directory.  What data is
        removed depends on the options supplied by the user.

        :param userlist: a list of options.  The following are valid
           options::

             expire-cache = Eliminate the local data saying when the
               metadata and mirror lists were downloaded for each
               repository.
             packages = Eliminate any cached packages
             metadata = Eliminate all of the files which yum uses to
               determine the remote availability of packages
             dbcache = Eliminate the sqlite cache used for faster
               access to metadata
             rpmdb = Eliminate any cached datat from the local rpmdb
             all = do all of the above
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        pkgcode = xmlcode = dbcode = expccode = 0
        pkgresults = xmlresults = dbresults = expcresults = []
        msg = self.output.fmtKeyValFill(_('Cleaning repos: '),
                        ' '.join([ x.id for x in self.repos.iter_enabled()]))
        self.logger.info(msg)
        if 'all' in userlist:
            self.logger.info(_('Cleaning up Everything'))
            pkgcode, pkgresults = self.cleanPackages()
            xmlcode, xmlresults = self.cleanMetadata()
            dbcode, dbresults = self.clean_binary_cache()
            rpmcode, rpmresults = self.cleanRpmDB()

            code = pkgcode + xmlcode + dbcode + rpmcode
            results = (pkgresults + xmlresults + dbresults +
                       rpmresults)
            for msg in results:
                self.logger.debug(msg)
            return code, []

        if 'packages' in userlist:
            self.logger.debug(_('Cleaning up Packages'))
            pkgcode, pkgresults = self.cleanPackages()
        if 'metadata' in userlist:
            self.logger.debug(_('Cleaning up xml metadata'))
            xmlcode, xmlresults = self.cleanMetadata()
        if 'dbcache' in userlist or 'metadata' in userlist:
            self.logger.debug(_('Cleaning up database cache'))
            dbcode, dbresults =  self.clean_binary_cache()
        if 'expire-cache' in userlist or 'metadata' in userlist:
            self.logger.debug(_('Cleaning up expire-cache metadata'))
            expccode, expcresults = self.cleanExpireCache()
        if 'rpmdb' in userlist:
            self.logger.debug(_('Cleaning up cached rpmdb data'))
            expccode, expcresults = self.cleanRpmDB()

        results = pkgresults + xmlresults + dbresults + expcresults
        for msg in results:
            self.logger.info( msg)
        code = pkgcode + xmlcode + dbcode + expccode
        if code:
            raise dnf.exceptions.Error('Error cleaning up.')

    def returnGroupLists(self, userlist):
        """Print out a list of groups that match the given names or
        wildcards.

        :param extcmds: a list of names or wildcards specifying
           groups to list
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        uservisible=1

        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0
                userlist.pop(0)
        if not userlist:
            userlist = None # Match everything...

        env_inst, env_avail = self._environment_list(userlist)
        installed, available = self._group_lists(uservisible, userlist)

        if not any([env_inst ,env_avail, installed, available]):
            self.logger.error(_('Warning: No groups match: %s'),
                              ", ".join(userlist))
            return 0, []

        def _out_grp(sect, group):
            if not done:
                self.logger.info(sect)
            msg = '   %s' % group.ui_name
            if self.conf.verbose:
                msg += ' (%s)' % group.id
            if group.lang_only:
                msg += ' [%s]' % group.lang_only
            self.logger.info('%s', msg)

        def _out_env(sect, envs):
            if envs:
                self.logger.info(sect)
            for e in envs:
                    msg = '   %s' % e.ui_name
                    if self.conf.verbose:
                        msg += ' (%s)' % e.id
                    self.logger.info(msg)

        _out_env(_('Available environment groups:'), env_avail)
        _out_env(_('Installed environment groups:'), env_inst)

        done = False
        for group in installed:
            if group.lang_only: continue
            _out_grp(_('Installed groups:'), group)
            done = True

        done = False
        for group in installed:
            if not group.lang_only: continue
            _out_grp(_('Installed language groups:'), group)
            done = True

        done = False
        for group in available:
            if group.lang_only: continue
            _out_grp(_('Available groups:'), group)
            done = True

        done = False
        for group in available:
            if not group.lang_only: continue
            _out_grp(_('Available language groups:'), group)
            done = True

        return 0, []

    def returnGroupSummary(self, userlist):
        """Print a summary of the groups that match the given names or
        wildcards.

        :param userlist: a list of names or wildcards specifying the
           groups to summarise. If *userlist* is an empty list, all
           installed and available packages will be summarised
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        uservisible=1

        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0
                userlist.pop(0)
        if not userlist:
            userlist = None # Match everything...

        installed, available = self._group_lists(uservisible, userlist)

        def _out_grp(sect, num):
            if not num:
                return
            self.logger.info('%s %u', sect,num)
        done = 0
        for group in installed:
            if group.lang_only: continue
            done += 1
        _out_grp(_('Installed Groups:'), done)

        done = 0
        for group in installed:
            if not group.lang_only: continue
            done += 1
        _out_grp(_('Installed Language Groups:'), done)

        done = False
        for group in available:
            if group.lang_only: continue
            done += 1
        _out_grp(_('Available Groups:'), done)

        done = False
        for group in available:
            if not group.lang_only: continue
            done += 1
        _out_grp(_('Available Language Groups:'), done)

        return 0, []

    def returnGroupInfo(self, userlist):
        """Print complete information about the groups that match the
        given names or wildcards.

        :param userlist: a list of names or wildcards specifying the
           groups to print information about
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        for strng in userlist:
            group_matched = False
            for group in self.comps.groups_by_pattern(strng):
                self.output.displayPkgsInGroups(group)
                group_matched = True

            if not group_matched:
                self.logger.error(_('Warning: Group %s does not exist.'), strng)

        return 0, []

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
            self.logger.critical(_('No transaction ID given'))
            return None

        tids = []
        last = None
        for extcmd in extcmds:
            try:
                id_or_offset = self.transaction_id_or_offset(extcmd)
            except ValueError:
                self.logger.critical(_('Bad transaction ID given'))
                return None

            if id_or_offset < 0:
                if last is None:
                    cto = False
                    last = self.history.last(complete_transactions_only=cto)
                    if last is None:
                        self.logger.critical(_('Bad transaction ID given'))
                        return None
                tids.append(str(last.tid + id_or_offset + 1))
            else:
                tids.append(str(id_or_offset))

        old = self.history.old(tids)
        if not old:
            self.logger.critical(_('Not found given transaction ID'))
            return None
        return old

    def history_get_transaction(self, extcmds):
        old = self._history_get_transactions(extcmds)
        if old is None:
            return None
        if len(old) > 1:
            self.logger.critical(_('Found more than one transaction ID!'))
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
                self.logger.warning(_('Transaction history is incomplete, before %u.'), tid.tid)
            elif tid.altered_gt_rpmdb:
                self.logger.warning(_('Transaction history is incomplete, after %u.'), tid.tid)

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
            self.logger.info(_('No package %s%s%s installed.'),
                             hibeg, unicode(err.pkg_spec), hiend)
            return 1, ['A transaction cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            self.logger.info(_('No package %s%s%s available.'),
                             hibeg, unicode(err.pkg_spec), hiend)
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
            self.logger.info(_('No package %s%s%s installed.'),
                             hibeg, unicode(err.pkg_spec), hiend)
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.PackagesNotAvailableError as err:
            self.logger.info(_('No package %s%s%s available.'),
                             hibeg, unicode(err.pkg_spec), hiend)
            return 1, ['An operation cannot be undone']
        except dnf.exceptions.MarkingError:
            assert False
        else:
            return 2, ["Undoing transaction %u" % (old.tid,)]

class Cli(object):
    def __init__(self, base):
        self._system_cachedir = None
        self.demands = dnf.cli.demand.DemandSheet() #:cli
        self.logger = logging.getLogger("dnf")
        self.command = None
        self.base = base
        self.cli_commands = {}
        self.nogpgcheck = False

        self.register_command(dnf.cli.commands.install.InstallCommand)
        self.register_command(dnf.cli.commands.upgrade.UpgradeCommand)
        self.register_command(dnf.cli.commands.UpgradeToCommand)
        self.register_command(dnf.cli.commands.InfoCommand)
        self.register_command(dnf.cli.commands.ListCommand)
        self.register_command(dnf.cli.commands.EraseCommand)
        self.register_command(dnf.cli.commands.group.GroupCommand)
        self.register_command(dnf.cli.commands.MakeCacheCommand)
        self.register_command(dnf.cli.commands.CleanCommand)
        self.register_command(dnf.cli.commands.ProvidesCommand)
        self.register_command(dnf.cli.commands.CheckUpdateCommand)
        self.register_command(dnf.cli.commands.SearchCommand)
        self.register_command(dnf.cli.commands.RepoListCommand)
        self.register_command(dnf.cli.commands.RepoPkgsCommand)
        self.register_command(dnf.cli.commands.HelpCommand)
        self.register_command(dnf.cli.commands.reinstall.ReinstallCommand)
        self.register_command(dnf.cli.commands.downgrade.DowngradeCommand)
        self.register_command(dnf.cli.commands.HistoryCommand)
        self.register_command(dnf.cli.commands.distrosync.DistroSyncCommand)

    def _configure_cachedir(self):
        # perform the CLI-specific cachedir tricks
        conf = self.base.conf
        suffix = dnf.yum.parser.varReplace(dnf.const.CACHEDIR_SUFFIX, conf.yumvar)
        cli_cache = dnf.conf.CliCache(conf.cachedir, suffix)
        conf.cachedir = cli_cache.cachedir
        self._system_cachedir = cli_cache.system_cachedir
        self.logger.debug("cachedir: %s", conf.cachedir)

    def _configure_repos(self, opts):
        self.base.read_all_repos()
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
            self.logger.critical(e)
            self.print_usage()
            sys.exit(1)

        if self.nogpgcheck:
            for repo in self.base.repos.values():
                repo.gpgcheck = False
                repo.repo_gpgcheck = False

        for rid in self.base._persistor.get_expired_repos():
            repo = self.base.repos.get(rid)
            if repo:
                repo.md_expire_cache()

        if opts.cacheonly:
            for repo in self.base.repos.values():
                repo.basecachedir = self._system_cachedir
                repo.md_only_cached = True

        # setup the progress bars/callbacks
        (bar, self.base.ds_callback) = self.base.output.setup_progress_callbacks()
        self.base.repos.all().set_progress_bar(bar)
        confirm_func = self.base.output._cli_confirm_gpg_key_import
        self.base.repos.all().confirm_func = confirm_func

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
        """Read :attr:`self.cmds` and parse them out to make sure that
        the requested base command and argument makes any sense at
        all.  This function will also set :attr:`self.base.basecmd` and
        :attr:`self.extcmds`.
        """
        self.logger.debug('dnf version: %s', dnf.const.VERSION)
        self.logger.log(dnf.logging.SUBDEBUG,
                        'Command: %s', self.cmdstring)
        self.logger.log(dnf.logging.SUBDEBUG,
                        'Installroot: %s', self.base.conf.installroot)
        if len(self.base.conf.commands) == 0 and len(self.base.cmds) < 1:
            self.base.cmds = self.base.conf.commands
        else:
            self.base.conf.commands = self.base.cmds
        if len(self.base.cmds) < 1:
            self.logger.critical(_('You need to give some command'))
            self.print_usage()
            raise CliError

        basecmd = self.base.cmds[0] # our base command
        command_cls = self.cli_commands.get(basecmd)
        if command_cls is None:
            self.logger.critical(_('No such command: %s. Please use %s --help'),
                                  basecmd, sys.argv[0])
            raise CliError
        self.command = command_cls(self)

        (base, ext) = self.command.canonical(self.base.cmds)
        self.base.basecmd, self.base.extcmds = (base, ext)
        self.logger.log(dnf.logging.SUBDEBUG, 'Base command: %s', base)
        self.logger.log(dnf.logging.SUBDEBUG, 'Extra commands: %s', ext)

    def _parse_setopts(self, setopts):
        """parse the setopts list handed to us and saves the results as
           repo_setopts and main_setopts in the base object"""

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
        self.base.repo_setopts = repoopts

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
                        self.logger.warning(msg % opt)
                    setattr(self.base.conf, opt, getattr(self.main_setopts, opt))

        except (dnf.exceptions.ConfigError, ValueError) as e:
            self.logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        except IOError as e:
            e = '%s: %s' % (unicode(e.args[1]), repr(e.filename))
            self.logger.critical(_('Config error: %s'), e)
            sys.exit(1)
        for item in bad_setopt_tm:
            msg = "Setopt argument has multiple values: %s"
            self.logger.warning(msg % item)
        for item in bad_setopt_ne:
            msg = "Setopt argument has no value: %s"
            self.logger.warning(msg % item)

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

        if opts.sleeptime is not None:
            sleeptime = random.randrange(opts.sleeptime*60)
        else:
            sleeptime = 0

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

        try:
            self._parse_commands() # before we return check over the base command
                                  # + args make sure they match/make sense
        except CliError:
            sys.exit(1)
        self.command.configure(self.base.extcmds)

        if opts.debugrepodata:
            self.write_out_metadata()
        if opts.debugsolver:
            self.base.conf.debug_solver = True

        self.base.plugins.run_config()
        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)

    def check(self):
        """Make sure the command line and options make sense."""
        self.command.doCheck(self.base.basecmd, self.base.extcmds)

    def read_conf_file(self, path=None, root="/", releasever=None,
                       overrides=None):
        conf_st = time.time()
        conf = self.base.conf
        conf.installroot = root
        conf.read(path)
        conf.releasever = releasever
        conf.yumvar_update_from_etc()

        if overrides is not None:
            conf.override(overrides)

        conf.logdir = dnf.yum.config.logdir_fit(conf.logdir)
        for opt in ('cachedir', 'logdir', 'persistdir'):
            conf.prepend_installroot(opt)
            conf._var_replace(opt)

        self.base.logging.setup_from_dnf_conf(conf)

        # repos are ver/arch specific so add $basearch/$releasever
        yumvar = conf.yumvar
        conf._repos_persistdir = os.path.normpath(
            '%s/repos/%s/%s/' % (conf.persistdir,
                                 yumvar.get('basearch', '$basearch'),
                                 yumvar.get('releasever', '$releasever')))
        self.logger.debug('Config time: %0.3f' % (time.time() - conf_st))
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
        if self.demands.sack_activation:
            lar = self.demands.available_repos
            self.base.fill_sack(load_system_repo='auto',
                                load_available_repos=lar)
            self.base.plugins.run_sack()
        return self.command.run(self.base.extcmds)

    def print_usage(self):
        return self.optparser.print_usage()

    def search(self, args):
        """Search for simple text tags in a package object.

        :param args: list of names or wildcards to search for.
           Normally this method will begin by searching the package
           names and summaries, and will only search urls and
           descriptions if that fails.  However, if the first string
           in *args* is "all", this method will always search
           everything
        :return: a tuple where the first item is an exit code, and
           the second item is a generator if the search is a
           successful, and a list of error messages otherwise

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        def _print_match_section(text, keys):
            # Print them in the order they were passed
            used_keys = [arg for arg in args if arg in keys]
            formatted = self.base.output.fmtSection(text % ", ".join(used_keys))
            print(ucd(formatted))

        # prepare the input
        dups = self.base.conf.showdupesfromrepos
        search_all = False
        if len(args) > 1 and args[0] == 'all':
            args.pop(0)
            search_all = True

        counter = dnf.match_counter.MatchCounter()
        for arg in args:
            self.base.search_counted(counter, 'name', arg)
            self.base.search_counted(counter, 'summary', arg)

        section_text = _('N/S Matched: %s')
        ns_only = True
        if search_all or counter.total() == 0:
            section_text = _('Matched: %s')
            ns_only = False
            for arg in args:
                self.base.search_counted(counter, 'description', arg)
                self.base.search_counted(counter, 'url', arg)

        matched_needles = None
        limit = None
        if not self.base.conf.showdupesfromrepos:
            limit = self.base.sack.query().filter(pkg=counter.keys()).latest()
        for pkg in counter.sorted(reverse=True, limit_to=limit):
            if matched_needles != counter.matched_needles(pkg):
                matched_needles = counter.matched_needles(pkg)
                _print_match_section(section_text, matched_needles)
            self.base.output.matchcallback(pkg, counter.matched_haystacks(pkg),
                                           args)

        if len(counter) == 0:
            self.logger.warning(_('Warning: No matches found for: %s'), arg)
            raise dnf.exceptions.Error(_('No Matches found'))

    def write_out_metadata(self):
        print(_("Writing out repository metadata for debugging."))
        rids = [r.id for r in self.base.repos.enabled()]
        rids.append(hawkey.SYSTEM_REPO_NAME)
        for rid in rids:
            with open("%s.repo" % rid, 'w') as outfile:
                self.base.sack.susetags_for_repo(outfile, rid)
