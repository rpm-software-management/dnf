# clean.py
# Clean CLI command.
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals
from .. import commands
from dnf.i18n import _, P_
from dnf.yum import misc

import dnf.cli
import dnf.logging
import hawkey
import logging
import os

logger = logging.getLogger("dnf")

valid_args = ('packages', 'metadata', 'dbcache', 'plugins', 'expire-cache',
              'rpmdb', 'all')


def _check_args(cli, basecmd, extcmds):
    """Verify that extcmds are valid options for clean."""

    if len(extcmds) == 0:
        logger.critical(_('Error: clean requires an option: %s'),
                        ", ".join(valid_args))
        raise dnf.cli.CliError

    for cmd in extcmds:
        if cmd not in valid_args:
            logger.critical(_('Error: invalid clean argument: %r'), cmd)
            commands.err_mini_usage(cli, basecmd)
            raise dnf.cli.CliError


def _clean_binary_cache(repos, cachedir):
    """ Delete the binary cache files from the DNF cache.

        IOW, clean up the .solv and .solvx hawkey cache files.
    """
    files = [os.path.join(cachedir, hawkey.SYSTEM_REPO_NAME + ".solv")]
    for repo in repos.iter_enabled():
        basename = os.path.join(cachedir, repo.id)
        files.append(basename + ".solv")
        files.append(basename + "-filenames.solvx")
        files.append(basename + "-presto.solvx")
        files.append(basename + "-updateinfo.solvx")
    files = [f for f in files if os.access(f, os.F_OK)]

    return _clean_filelist('dbcache', files)


def _clean_filelist(filetype, filelist):
    removed = 0
    for item in filelist:
        try:
            misc.unlink_f(item)
        except OSError:
            logger.critical(_('Cannot remove %s file %s'),
                                 filetype, item)
            continue
        else:
            logger.log(dnf.logging.DDEBUG,
                _('%s file %s removed'), filetype, item)
            removed += 1
    msg = P_('%d %s file removed', '%d %s files removed', removed)
    msg %= (removed, filetype)
    return 0, [msg]


def _clean_files(repos, exts, pathattr, filetype):
    filelist = []
    for ext in exts:
        for repo in repos.iter_enabled():
            if repo.local and filetype != 'metadata':
                continue
            path = getattr(repo, pathattr)
            if os.path.exists(path) and os.path.isdir(path):
                filelist = misc.getFileList(path, ext, filelist)
    return _clean_filelist(filetype, filelist)


def _clean_metadata(repos):
    """Delete the metadata files from the yum cache."""

    exts = ('xml.gz', 'xml', 'cachecookie', 'mirrorlist', 'asc',
            'xml.bz2', 'xml.xz')
    # Metalink is also here, but is a *.xml file
    return _clean_files(repos, exts, 'cachedir', 'metadata')


def _clean_packages(repos):
    """Delete the package files from the yum cache."""

    exts = ('rpm',)
    return _clean_files(repos, exts, 'pkgdir', 'package')


def _clean_rpmdb(persistdir):
    """Delete any cached data from the local rpmdb."""

    cachedir = persistdir + "/rpmdb-indexes/"
    if not os.path.exists(cachedir):
        filelist = []
    else:
        filelist = misc.getFileList(cachedir, '', [])
    return _clean_filelist('rpmdb', filelist)


def clean_expire_cache(repos):
    """Delete the local data saying when the metadata and mirror
       lists were downloaded for each repository."""

    for repo in repos.iter_enabled():
        repo.md_expire_cache()
    return 0, [_('The enabled repos were expired')]


class CleanCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    clean command.
    """

    aliases = ('clean',)
    summary = _("Remove cached data")
    usage = "[%s]" % "|".join(valid_args)


    def clean(self, userlist):
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
        repos = self.base.repos
        msg = self.output.fmtKeyValFill(
            _('Cleaning repos: '),
            ' '.join([x.id for x in repos.iter_enabled()]))
        logger.info(msg)

        persistdir = self.base.conf.persistdir
        cachedir = self.base.conf.cachedir
        if 'all' in userlist:
            logger.info(_('Cleaning up Everything'))
            pkgcode, pkgresults = _clean_packages(repos)
            xmlcode, xmlresults = _clean_metadata(repos)
            dbcode, dbresults = _clean_binary_cache(repos, cachedir)
            rpmcode, rpmresults = _clean_rpmdb(persistdir)

            code = pkgcode + xmlcode + dbcode + rpmcode
            results = (pkgresults + xmlresults + dbresults +
                       rpmresults)
            for msg in results:
                logger.debug(msg)
            return code, []
        if 'packages' in userlist:
            logger.debug(_('Cleaning up Packages'))
            pkgcode, pkgresults = _clean_packages(repos)
        if 'metadata' in userlist:
            logger.debug(_('Cleaning up xml metadata'))
            xmlcode, xmlresults = _clean_metadata(repos)
        if 'dbcache' in userlist or 'metadata' in userlist:
            logger.debug(_('Cleaning up database cache'))
            dbcode, dbresults = _clean_binary_cache(repos, cachedir)
        if 'expire-cache' in userlist or 'metadata' in userlist:
            logger.debug(_('Cleaning up expire-cache metadata'))
            clean_expire_cache(repos)
        if 'rpmdb' in userlist:
            logger.debug(_('Cleaning up cached rpmdb data'))
            expccode, expcresults = _clean_rpmdb(persistdir)

        results = pkgresults + xmlresults + dbresults + expcresults
        for msg in results:
            logger.info(msg)
        code = pkgcode + xmlcode + dbcode + expccode
        if code:
            raise dnf.exceptions.Error('Error cleaning up.')

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that there is at least one enabled repository,
        and that this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        _check_args(self.cli, basecmd, extcmds)
        commands.checkEnabledRepo(self.base)

    def run(self, extcmds):
        return self.clean(extcmds)
