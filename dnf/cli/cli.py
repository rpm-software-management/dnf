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
#
# Written by Seth Vidal

"""
Command line interface yum class and related.
"""

from __future__ import print_function
from __future__ import absolute_import
from dnf.cli import CliError
from dnf.i18n import ucd
from dnf.yum.i18n import to_unicode, to_utf8, exception2msg, _, P_
from optparse import OptionParser,OptionGroup,SUPPRESS_HELP

import dnf
import dnf.cli.commands
import dnf.conf
import dnf.const
import dnf.exceptions
import dnf.logging
import dnf.match_counter
import dnf.persistor
import dnf.sack
import dnf.util
import dnf.yum.misc
import dnf.yum.parser
import dnf.yum.plugins
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
import rpm
from functools import reduce
from dnf.pycomp import unicode

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
        self.output = output.Output(self)
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
        problems = self.download_packages(downloadpkgs, self.output.progress,
                                          self.output.download_callback_total_cb)

        if len(problems) > 0:
            errstring = ''
            errstring += _('Error Downloading Packages:\n')
            for key in problems:
                errors = dnf.yum.misc.unique(problems[key])
                for error in errors:
                    errstring += '  %s: %s\n' % (key, error)
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
            self.logger.info(to_unicode(msg))

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

    def installPkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and install them, or if they are installed, update
        them to a newer version. If a complete version number is
        specified, attempt to upgrade (or downgrade if they have been
        removed) them to the specified version.

        :param userlist: a list of names or wildcards specifying
           packages to install
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # get the list of available packages
        # iterate over the user's list
        # add packages to Transaction holding class if they match.
        # if we've added any packages to the transaction then return 2 and a string
        # if we've hit a snag, return 1 and the failure explanation
        # if we've got nothing to do, return 0 and a 'nothing available to install' string

        oldcount = self._goal.req_length()

        done = False
        for arg in userlist:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.install_local(arg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos
            try:
                self.install(arg)
            except dnf.exceptions.PackageNotFoundError:
                msg = _('No package %s%s%s available.')
                self.logger.info(msg, self.output.term.MODE['bold'], arg,
                                 self.output.term.MODE['normal'])
            else:
                done = True
        cnt = self._goal.req_length() - oldcount
        if cnt > 0:
            msg = P_('%d package to install', '%d packages to install', cnt)
            return 2, [msg % cnt]

        if not done:
            return 1, [_('Nothing to do')]
        return 0, [_('Nothing to do')]

    def updatePkgs(self, userlist):
        """Take user commands and populate transaction wrapper with
        packages to be updated.

        :param userlist: a list of names or wildcards specifying
           packages to update.  If *userlist* is an empty list, yum
           will perform a global update
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting

        oldcount = self._goal.req_length()
        if len(userlist) == 0: # simple case - do them all
            self.update_all()

        else:
            # go through the userlist - look for items that are local rpms. If we find them
            # pass them off to installLocal() and then move on
            for item in userlist:
                if (item.endswith('.rpm') and (dnf.yum.misc.re_remote_url(item) or
                                               os.path.exists(item))):
                    self.update_local(item)
                    continue

                try:
                    self.update(item)
                except dnf.exceptions.PackageNotFoundError:
                    self.logger.info(_('No match for argument: %s'), unicode(item))
                    self._checkMaybeYouMeant(item)

        cnt = self._goal.req_length() - oldcount
        if cnt > 0:
            msg = P_('%d package marked for upgrade',
                     '%d packages marked for upgrade', cnt)
            return 2, [msg % cnt]
        elif self._goal.req_has_upgrade_all():
            return 2, [_('All packages marked for upgrade')]
        else:
            return 0, [_('No packages marked for upgrade')]

    def upgrade_userlist_to(self, userlist):
        oldcount = self._goal.req_length()
        for l in userlist:
            self.upgrade_to(l)
        cnt = self._goal.req_length() - oldcount
        if cnt > 0:
            msg = P_('%d package marked for upgrade',
                     '%d packages marked for upgrade', cnt)
            return 2, [msg % cnt]
        else:
            return 0, [_('No Packages marked for upgrade')]

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
        assert(len(userlist) == 0)
        self.distro_sync()

        cnt = self._goal.req_length() - oldcount
        if cnt > 0:
            msg = P_('%d package marked for Distribution Synchronization',
                     '%d packages marked for Distribution Synchronization',
                     cnt)
            return 2, [msg % cnt]
        elif self._goal.req_has_distupgrade_all():
            return 2, [_('All packages marked for Distribution Synchronization')]
        else:
            return 0, [_('No Packages marked for Distribution Synchronization')]

    def erasePkgs(self, userlist):
        """Take user commands and populate a transaction wrapper with
        packages to be erased.

        :param userlist: a list of names or wildcards specifying
           packages to erase
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        cnt = 0
        for arg in userlist:
            try:
                current_cnt = self.remove(arg)
            except dnf.exceptions.PackagesNotInstalledError:
                self.logger.info(_('No match for argument: %s'), unicode(arg))
                self._checkMaybeYouMeant(arg, always_output=False, rpmdb_only=True)
            else:
                cnt += current_cnt

        if cnt > 0:
            msg = P_('%d package marked for removal',
                     '%d packages marked for removal', cnt)
            return 2, [msg % cnt]
        else:
            return 0, [_('No Packages marked for removal')]

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
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.downgrade_local(arg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.downgrade(arg)
            except dnf.exceptions.PackagesNotInstalledError as err:
                for pkg in err.packages:
                    self.logger.info(_('No match for available package: %s'), pkg)
                self._maybeYouMeant(arg)
        cnt = self._goal.req_length() - oldcount
        if cnt > 0:
            msg = P_('%d package to downgrade',
                     '%d packages to downgrade', cnt)
            return 2, [msg % cnt]
        return 0, [_('Nothing to do')]

    def reinstallPkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and reinstall them.

        :param userlist: a list of names or wildcards specifying
           packages to reinstall
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        oldcount = self._goal.req_length()

        done = False
        for arg in userlist:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.reinstall_local(arg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.reinstall(arg)
            except dnf.exceptions.PackagesNotInstalledError:
                self.logger.info(_('No match for argument: %s'), unicode(arg))
                self._checkMaybeYouMeant(arg, always_output=False)
            except dnf.exceptions.PackagesNotAvailableError as e:
                for ipkg in e.packages:
                    xmsg = ''
                    yumdb_info = self.yumdb.get_package(ipkg)
                    if 'from_repo' in yumdb_info:
                        xmsg = yumdb_info.from_repo
                        xmsg = _(' (from %s)') % xmsg
                    msg = _('Installed package %s%s%s%s not available.')
                    self.logger.info(msg, self.output.term.MODE['bold'], ipkg,
                                     self.output.term.MODE['normal'], xmsg)
            else:
                done = True

        cnt = self._goal.req_length() - oldcount
        if cnt:
            msg = P_('%d package to reinstall',
                     '%d packages to reinstall', cnt)
            return 2, [msg % cnt]

        if not done:
            return 1, [_('Nothing to do')]
        return 0, [_('Nothing to do')]

    def returnPkgLists(self, extcmds, installed_available=False):
        """Return a :class:`dnf.yum.misc.GenericHolder` object containing
        lists of package objects that match the given names or wildcards.

        :param extcmds: a list of names or wildcards specifying
           packages to list
        :param installed_available: whether the available package list
           is present as .hidden_available when doing all, available,
           or installed

        :return: a :class:`dnf.yum.misc.GenericHolder` instance with the
           following lists defined::

             available = list of packageObjects
             installed = list of packageObjects
             upgrades = tuples of packageObjects (updating, installed)
             extras = list of packageObjects
             obsoletes = tuples of packageObjects (obsoleting, installed)
             recent = list of packageObjects
        """
        special = ['available', 'installed', 'all', 'extras', 'upgrades',
                   'recent', 'obsoletes']

        pkgnarrow = 'all'
        done_hidden_available = False
        done_hidden_installed = False
        if len(extcmds) > 0:
            if installed_available and extcmds[0] == 'installed':
                done_hidden_available = True
                extcmds.pop(0)
            elif installed_available and extcmds[0] == 'available':
                done_hidden_installed = True
                extcmds.pop(0)
            elif extcmds[0] == 'updates':
                pkgnarrow = 'upgrades'
                extcmds.pop(0)
            elif extcmds[0] in special:
                pkgnarrow = extcmds.pop(0)

        ypl = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=extcmds,
                                  ignore_case=True)
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
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
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

        return 0, []

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

        if matches:
            return 0, []
        return 0, ['No Matches found']

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
             plugins = Tell any enabled plugins to eliminate their
               cached data
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
            self.plugins.run('clean')

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
        if 'plugins' in userlist:
            self.logger.debug(_('Cleaning up plugins'))
            self.plugins.run('clean')

        code = pkgcode + xmlcode + dbcode + expccode
        results = pkgresults + xmlresults + dbresults + expcresults
        for msg in results:
            self.logger.info( msg)
        return code, []

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

        envs = self._environment_list(userlist)
        installed, available = self.group_lists(uservisible, userlist)

        if not envs and not installed and not available:
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

        if len(envs):
            self.logger.info(_('Available environment groups:'))
        for e in envs:
            msg = '   %s' % e.ui_name
            if self.conf.verbose:
                msg += ' (%s)' % e.id
            self.logger.info(msg)

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

        installed, available = self.group_lists(uservisible, userlist)

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

    def install_grouplist(self, grouplist):
        """Mark the packages in the given groups for installation.

        :param grouplist: a list of names or wildcards specifying
           groups to be installed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        pkgs_used = []

        groups = []
        for group_string in grouplist:
            matched = self.comps.groups_by_pattern(group_string)
            if len(matched) == 0:
                msg = _('Warning: Group %s does not exist.') % ucd(group_string)
                self.logger.error(msg)
                continue
            groups.extend(matched)
        total_cnt = reduce(operator.add, map(self.select_group, groups), 0)
        if not total_cnt:
            return 0, [_('No packages in any requested group available '\
                             'to install or upgrade')]
        else:
            return 2, [P_('%d package to Install', '%d packages to Install',
                          total_cnt) % total_cnt]

    def removeGroups(self, grouplist):
        """Mark the packages in the given groups for removal.

        :param grouplist: a list of names or wildcards specifying
           groups to be removed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        cnt = 0
        for group_string in grouplist:
            try:
                cnt += self.group_remove(group_string)
            except dnf.exceptions.CompsError as e:
                self.logger.critical(e)
                continue

        if cnt:
            msg = P_('%d package to remove', '%d packages to remove', cnt)
            return 2, [msg % cnt]
        else:
            return 0, [_('No packages to remove from groups')]

    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes and not self.conf.assumeno:
            return False
        if self.conf.alwaysprompt:
            return True

        # prompt if:
        #  package was added to fill a dependency
        #  package is being removed
        #  package wasn't explictly given on the command line
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
        if len(extcmds) < 2:
            self.logger.critical(_('No transaction ID given'))
            return None

        tids = []
        last = None
        for extcmd in extcmds[1:]:
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

class Cli(object):
    def __init__(self, base):
        self._system_cachedir = None
        self.logger = logging.getLogger("dnf")
        self.command = None
        self.base = base
        self.cli_commands = {}
        self.nogpgcheck = False

        # :hawkey -- commented out are not yet supported in dnf
        self._register_command(dnf.cli.commands.InstallCommand)
        self._register_command(dnf.cli.commands.UpgradeCommand)
        self._register_command(dnf.cli.commands.UpgradeToCommand)
        self._register_command(dnf.cli.commands.InfoCommand)
        self._register_command(dnf.cli.commands.ListCommand)
        self._register_command(dnf.cli.commands.EraseCommand)
        self._register_command(dnf.cli.commands.GroupsCommand)
        self._register_command(dnf.cli.commands.MakeCacheCommand)
        self._register_command(dnf.cli.commands.CleanCommand)
        self._register_command(dnf.cli.commands.ProvidesCommand)
        self._register_command(dnf.cli.commands.CheckUpdateCommand)
        self._register_command(dnf.cli.commands.SearchCommand)
        # self._register_command(dnf.cli.commands.DepListCommand)
        self._register_command(dnf.cli.commands.RepoListCommand)
        self._register_command(dnf.cli.commands.HelpCommand)
        self._register_command(dnf.cli.commands.ReInstallCommand)
        self._register_command(dnf.cli.commands.DowngradeCommand)
        # self._register_command(dnf.cli.commands.VersionCommand)
        self._register_command(dnf.cli.commands.HistoryCommand)
        # self._register_command(dnf.cli.commands.CheckRpmdbCommand)
        self._register_command(dnf.cli.commands.DistroSyncCommand)

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
                repolist = self.base.repos.get_multiple(repo)
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

        if opts.cacheonly:
            for repo in self.base.repos.values():
                repo.basecachedir = self._system_cachedir
                repo.md_only_cached = True

        for rid in self.base._persistor.get_expired_repos():
            repo = self.base.repos.get(rid)
            if repo:
                repo.md_expire_cache()

        # setup the progress bars/callbacks
        (bar, self.base.ds_callback) = self.base.output.setup_progress_callbacks()
        self.base.repos.all.set_progress_bar(bar)
        confirm_func = self.base.output._cli_confirm_gpg_key_import
        self.base.repos.all.confirm_func = confirm_func

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

    def _make_usage(self):
        """
        Format an attractive usage string for yum, listing subcommand
        names and summary usages.
        """
        name = dnf.const.PROGRAM_NAME
        usage = '%s [options] COMMAND\n\nList of Commands:\n\n' % name
        commands = dnf.yum.misc.unique([x for x in self.cli_commands.values()
                                    if not (hasattr(x, 'hidden') and x.hidden)])
        commands.sort(key=lambda x: x.aliases[0])
        for command in commands:
            try:
                summary = command.get_summary()
                usage += "%-14s %s\n" % (command.aliases[0], summary)
            except (AttributeError, NotImplementedError):
                usage += "%s\n" % command.aliases[0]

        return usage

    def _register_command(self, command_cls):
        """ Register a :class:`dnf.cli.commands.Command` so that it can be
            called by any of the names returned by its
            :func:`dnf.cli.commands.Command.getNames` method.

            :param command_cls: the :class:`dnf.cli.commands.Command` to register
        """
        for name in command_cls.aliases:
            if name in self.cli_commands:
                raise dnf.exceptions.ConfigError(_('Command "%s" already defined') % name)
            self.cli_commands[name] = command_cls

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
        ext_str = ' '.join(ext)
        self.logger.log(dnf.logging.SUBDEBUG, 'Base command: %s', base)
        self.logger.log(dnf.logging.SUBDEBUG, 'Extra commands: %s', ext)

    def _parse_setopts(self, setopts):
        """parse the setopts list handed to us and saves the results as
           repo_setopts and main_setopts in the yumbase object"""

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

    def configure(self, args):
        """Parse command line arguments, and set up :attr:`self.base.conf` and
        :attr:`self.cmds`, as well as logger objects in base instance.

        :param args: a list of command line arguments
        """
        self.optparser = YumOptionParser(base=self.base, usage=self._make_usage())

        # Parse only command line options that affect basic yum setup
        opts = self.optparser.firstParse(args)

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

        # Read up configuration options and initialise plugins
        overrides = self.optparser._non_nones2dict(opts)
        releasever = opts.releasever
        try:
            self.base.read_conf_file(opts.conffile, root, releasever, overrides)

            # now set all the non-first-start opts from main from our setopts
            if self.main_setopts:
                for opt in self.main_setopts.items:
                    if not hasattr(self.base.conf, opt):
                        msg ="Main config did not have a %s attr. before setopt"
                        self.logger.warning(msg % opt)
                    setattr(self.base.conf, opt, getattr(self.main_setopts, opt))

        except dnf.exceptions.ConfigError as e:
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except IOError as e:
            e = '%s: %s' % (to_unicode(e.args[1]), repr(e.filename))
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except ValueError as e:
            self.logger.critical(_('Options Error: %s'), e)
            sys.exit(1)
        for item in bad_setopt_tm:
            msg = "Setopt argument has multiple values: %s"
            self.logger.warning(msg % item)
        for item in  bad_setopt_ne:
            msg = "Setopt argument has no value: %s"
            self.logger.warning(msg % item)

        # update usage in case plugins have added commands
        self.optparser.set_usage(self._make_usage())

        self.base.plugins.run('args', args=args)
        # Now parse the command line for real and
        # apply some of the options to self.base.conf
        (opts, self.base.cmds) = self.optparser.setupYumConfig(args=args)

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
            print_versions(self.base.run_with_package_names,
                           self.base, self.base.output)
            sys.exit(0)

        if opts.sleeptime is not None:
            sleeptime = random.randrange(opts.sleeptime*60)
        else:
            sleeptime = 0

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
        self.command.configure()

        if opts.debugrepodata:
            self.write_out_metadata()
        if opts.debugsolver:
            self.base.conf.debug_solver = True
        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)

    def check(self):
        """Make sure the command line and options make sense."""
        self.command.doCheck(self.base.basecmd, self.base.extcmds)

    def run(self):
        """Call the base command, and pass it the extended commands or
           arguments.

        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        if self.command.activate_sack:
            lar = self.command.load_available_repos
            self.base.fill_sack(load_system_repo='auto',
                                load_available_repos=lar)
        return self.command.doCommand(self.base.basecmd, self.base.extcmds)

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
            return 0, [_('No Matches found')]
        return 0, []

    def write_out_metadata(self):
        print(_("Writing out repository metadata for debugging."))
        rids = [r.id for r in self.base.repos.enabled()]
        rids.append(hawkey.SYSTEM_REPO_NAME)
        for rid in rids:
            with open("%s.repo" % rid, 'w') as outfile:
                self.base.sack.susetags_for_repo(outfile, rid)

class YumOptionParser(OptionParser):
    """Subclass that makes some minor tweaks to make OptionParser do things the
    "yum way".
    """

    def __init__(self, base, **kwargs):
        # check if this is called with a utils=True/False parameter
        if 'utils' in kwargs:
            self._utils = kwargs['utils']
            del kwargs['utils']
        else:
            self._utils = False
        OptionParser.__init__(self, **kwargs)
        self.logger = logging.getLogger("dnf")
        self.base = base
        # self.plugin_option_group = OptionGroup(self, _("Plugin Options"))
        # self.add_option_group(self.plugin_option_group)

        self._addYumBasicOptions()

    def error(self, msg):
        """Output an error message, and exit the program.  This method
        is overridden so that error output goes to the logger.

        :param msg: the error message to output
        """
        self.print_usage()
        self.logger.critical(_("Command line error: %s"), msg)
        sys.exit(1)

    def firstParse(self, args):
        """Parse only command line options that affect basic yum
        setup.

        :param args: a list of command line options to parse
        :return: a dictionary containing the values of command line
           options
        """
        try:
            args = _filtercmdline(
                        ('--noplugins','--version','-q', '-v', "--quiet", "--verbose"),
                        ('-c', '--config', '-d', '--debuglevel',
                         '-e', '--errorlevel',
                         '--installroot',
                         '--disableplugin', '--enableplugin', '--releasever',
                         '--setopt'),
                        args)
        except ValueError as arg:
            self.print_help()
            print(_("\n\n%s: %s option requires an argument") % \
                      ('Command line error', arg), file=sys.stderr)
            sys.exit(1)
        return self.parse_args(args=args)[0]

    @staticmethod
    def _splitArg(seq):
        """ Split all strings in seq, at "," and whitespace.
            Returns a new list. """
        ret = []
        for arg in seq:
            ret.extend(arg.replace(",", " ").split())
        return ret

    @staticmethod
    def _non_nones2dict(opts):
        in_dct =  opts.__dict__
        dct = {k: in_dct[k] for k in in_dct
               if in_dct[k] is not None
               if in_dct[k] != []}
        for k in ['enableplugins', 'disableplugins']:
            v = dct.get(k, None)
            if v is None:
                continue
            dct[k] = YumOptionParser._splitArg(v)
        return dct

    def setupYumConfig(self, args):
        """Parse command line options.

        :param args: the command line arguments entered by the user
        :return: (opts, cmds)  opts is a dictionary containing
           the values of command line options.  cmds is a list of the
           command line arguments that were not parsed as options.
           For example, if args is ["install", "foo", "--verbose"],
           cmds will be ["install", "foo"].
        """
        (opts, cmds) = self.parse_args(args=args)

        # Let the plugins know what happened on the command line
        self.base.plugins.setCmdLine(opts, cmds)

        try:
            # config file is parsed and moving us forward
            # set some things in it.
            if opts.best:
                self.base.conf.best = opts.best

            # Handle remaining options
            if opts.assumeyes:
                self.base.conf.assumeyes = 1
            if opts.assumeno:
                self.base.conf.assumeno  = 1

            if opts.obsoletes:
                self.base.conf.obsoletes = 1

            if opts.installroot:
                self._checkAbsInstallRoot(opts.installroot)
                self.base.conf.installroot = opts.installroot

            if opts.showdupesfromrepos:
                self.base.conf.showdupesfromrepos = True

            if opts.color not in (None, 'auto', 'always', 'never',
                                  'tty', 'if-tty', 'yes', 'no', 'on', 'off'):
                raise ValueError(_("--color takes one of: auto, always, never"))
            elif opts.color is None:
                if self.base.conf.color != 'auto':
                    self.base.output.term.reinit(color=self.base.conf.color)
            else:
                _remap = {'tty' : 'auto', 'if-tty' : 'auto',
                          '1' : 'always', 'true' : 'always',
                          'yes' : 'always', 'on' : 'always',
                          '0' : 'always', 'false' : 'always',
                          'no' : 'never', 'off' : 'never'}
                opts.color = _remap.get(opts.color, opts.color)
                if opts.color != 'auto':
                    self.base.output.term.reinit(color=opts.color)

            if opts.disableexcludes:
                disable_excludes = self._splitArg(opts.disableexcludes)
            else:
                disable_excludes = []
            self.base.conf.disable_excludes = disable_excludes

            for exclude in self._splitArg(opts.exclude):
                try:
                    excludelist = self.base.conf.exclude
                    excludelist.append(exclude)
                    self.base.conf.exclude = excludelist
                except dnf.exceptions.ConfigError as e:
                    self.logger.critical(e)
                    self.print_help()
                    sys.exit(1)

            if opts.rpmverbosity is not None:
                self.base.conf.rpmverbosity = opts.rpmverbosity

        except ValueError as e:
            self.logger.critical(_('Options Error: %s'), e)
            self.print_help()
            sys.exit(1)

        return opts, cmds

    def _checkAbsInstallRoot(self, installroot):
        if not installroot:
            return
        if installroot[0] == '/':
            return
        # We have a relative installroot ... haha
        self.logger.critical(_('--installroot must be an absolute path: %s'),
                             installroot)
        sys.exit(1)

    def _help_callback(self, opt, value, parser, *args, **kwargs):
        self.print_help()
        self.exit()

    def _repo_callback(self, option, opt_str, value, parser):
        operation = 'disable' if opt_str == '--disablerepo' else 'enable'
        l = getattr(parser.values, option.dest)
        l.append((value, operation))

    def _addYumBasicOptions(self):
        if self._utils:
            group = OptionGroup(self, "Yum Base Options")
            self.add_option_group(group)
        else:
            group = self

        # Note that we can't use the default action="help" because of the
        # fact that print_help() unconditionally does .encode() ... which is
        # bad on unicode input.
        # All defaults need to be a None, so we can always tell whether the user
        # has set something or whether we are getting a default.
        group.conflict_handler = "resolve"
        group.add_option("-h", "--help", action="callback",
                        callback=self._help_callback,
                help=_("show this help message and exit"))
        group.conflict_handler = "error"

        group.add_option("-b", "--best", action="store_true",
                         help=_("try the best available package versions in "
                                "transactions."))
        group.add_option("-C", "--cacheonly", dest="cacheonly",
                action="store_true",
                help=_("run entirely from system cache, don't update cache"))
        group.add_option("-c", "--config", dest="conffile",
                default=None,
                help=_("config file location"), metavar='[config file]')
        group.add_option("-R", "--randomwait", dest="sleeptime", type='int',
                default=None,
                help=_("maximum command wait time"), metavar='[minutes]')
        group.add_option("-d", "--debuglevel", dest="debuglevel", default=None,
                help=_("debugging output level"), type='int',
                metavar='[debug level]')
        group.add_option("--debugrepodata", dest="debugrepodata",
                         action="store_true", default=None,
                         help=_("dumps package metadata into files"))
        group.add_option("--debugsolver",
                         action="store_true", default=None,
                         help=_("dumps detailed solving results into files"))
        group.add_option("--showduplicates", dest="showdupesfromrepos",
                        action="store_true",
                help=_("show duplicates, in repos, in list/search commands"))
        group.add_option("-e", "--errorlevel", dest="errorlevel", default=None,
                help=_("error output level"), type='int',
                metavar='[error level]')
        group.add_option("", "--rpmverbosity", default=None,
                help=_("debugging output level for rpm"),
                metavar='[debug level name]')
        group.add_option("-q", "--quiet", dest="quiet", action="store_true",
                        help=_("quiet operation"))
        group.add_option("-v", "--verbose", dest="verbose", action="store_true",
                        help=_("verbose operation"))
        group.add_option("-y", "--assumeyes", dest="assumeyes",
                action="store_true", help=_("answer yes for all questions"))
        group.add_option("--assumeno", dest="assumeno",
                action="store_true", help=_("answer no for all questions"))
        group.add_option("--version", action="store_true",
                help=_("show Yum version and exit"))
        group.add_option("--installroot", help=_("set install root"),
                metavar='[path]')
        group.add_option("--enablerepo", action='callback',
                type='string', dest='repos_ed', default=[],
                callback=self._repo_callback,
                help=SUPPRESS_HELP,
                metavar='[repo]')
        group.add_option("--disablerepo", action='callback',
                type='string', dest='repos_ed', default=[],
                callback=self._repo_callback,
                help=SUPPRESS_HELP,
                metavar='[repo]')
        group.add_option("-x", "--exclude", default=[], action="append",
                # help=_("exclude package(s) by name or glob"),
                help=SUPPRESS_HELP,
                metavar='[package]')
        group.add_option("", "--disableexcludes", default=[], action="append",
                # help=_("disable exclude from main, for a repo or for everything"),
                help=SUPPRESS_HELP,
                        metavar='[repo]')
        group.add_option("--obsoletes", action="store_true",
                # help=_("enable obsoletes processing during upgrades")
                help=SUPPRESS_HELP)
        group.add_option("--noplugins", action="store_true",
                # help=_("disable Yum plugins")
                help=SUPPRESS_HELP)
        group.add_option("--nogpgcheck", action="store_true",
                # help=_("disable gpg signature checking")
                help=SUPPRESS_HELP)
        group.add_option("", "--disableplugin", dest="disableplugins", default=[],
                action="append",
                # help=_("disable plugins by name"),
                help=SUPPRESS_HELP,
                metavar='[plugin]')
        group.add_option("", "--enableplugin", dest="enableplugins", default=[],
                action="append",
                # help=_("enable plugins by name"),
                help=SUPPRESS_HELP,
                metavar='[plugin]')
        group.add_option("", "--color", dest="color", default=None,
                # help=_("control whether color is used")
                help=SUPPRESS_HELP)
        group.add_option("", "--releasever", dest="releasever", default=None,
                # help=_("set value of $releasever in yum config and repo files")
                help=SUPPRESS_HELP)
        group.add_option("", "--setopt", dest="setopts", default=[],
                action="append",
                # help=_("set arbitrary config and repo options")
                help=SUPPRESS_HELP)

def _filtercmdline(novalopts, valopts, args):
    '''Keep only specific options from the command line argument list

    This function allows us to peek at specific command line options when using
    the optparse module. This is useful when some options affect what other
    options should be available.

    @param novalopts: A sequence of options to keep that don't take an argument.
    @param valopts: A sequence of options to keep that take a single argument.
    @param args: The command line arguments to parse (as per sys.argv[:1]
    @return: A list of strings containing the filtered version of args.

    Will raise ValueError if there was a problem parsing the command line.
    '''
    out = []
    args = list(args)       # Make a copy because this func is destructive

    while len(args) > 0:
        a = args.pop(0)
        if '=' in a:
            opt, _ = a.split('=', 1)
            if opt in valopts:
                out.append(a)

        elif a == '--':
            out.append(a)

        elif a in novalopts:
            out.append(a)

        elif a in valopts:
            if len(args) < 1:
                raise ValueError(a)
            next = args.pop(0)
            if next[0] == '-':
                raise ValueError(a)

            out.extend([a, next])

        else:
            # Check for single letter options that take a value, where the
            # value is right up against the option
            for opt in valopts:
                if len(opt) == 2 and a.startswith(opt):
                    out.append(a)

    return out
