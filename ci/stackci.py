#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Red Hat, Inc.
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

"""This module represents the continuous integration script.

When the module is run as a script, the command line interface to the
program is started. The interface usage is::

    usage: prog [-h] {setup,build} ...

    Test the DNF stack.

    positional arguments:
      {setup,build}  the action to be performed

    optional arguments:
      -h, --help     show this help message and exit

    If an error occurs the exit status is non-zero.

The usage of the "setup" command is::

    usage: prog setup [-h] [--add-repository URL]
                      CHROOT [CHROOT ...] PROJECT

    Create a new Copr project.

    positional arguments:
      CHROOT                the chroots to be used in the project
                            ("22" adds "fedora-22-i386,
                            fedora-22-x86_64", "23" adds
                            "fedora-23-i386, fedora-23-x86_64",
                            "rawhide" adds "fedora-rawhide-i386,
                            fedora-rawhide-x86_64")
      PROJECT               the name of the project

    optional arguments:
      -h, --help            show this help message and exit
      --add-repository URL  the URL of an additional repository
                            that is required

The usage of the "build" command is::

    usage: prog build [-h] PROJECT {tito,librepo,libcomps} ...

    Build RPMs of a project from the checkout in the current working
    directory in Copr.

    positional arguments:
      PROJECT               the name of the Copr project
      {tito,librepo,libcomps}
                            the type of the project

    optional arguments:
      -h, --help            show this help message and exit

The usage for "tito" projects is::

    usage: prog build PROJECT tito [-h]

    Build a tito-enabled project.

    optional arguments:
      -h, --help  show this help message and exit

    The "tito" executable must be available.

The usage for "librepo" projects is::

    usage: prog build PROJECT librepo [-h] [--release RELEASE] SPEC

    Build a librepo project fork.

    positional arguments:
      SPEC               the ID of the Fedora Git
                         revision of the spec file

    optional arguments:
      -h, --help         show this help message and exit
      --release RELEASE  a custom release number of the resulting RPMs

    The "git", "rpmbuild", "sh" and "xz" executables must be available.

The usage for "libcomps" projects is::

    usage: prog build PROJECT libcomps [-h] [--release RELEASE]

    Build a libcomps project fork.

    optional arguments:
      -h, --help         show this help message and exit
      --release RELEASE  a custom release number of the resulting RPMs

    The "python" and "rpmbuild" executables must be available.

:var NAME: the name of the project
:type NAME: unicode
:var LOGGER: the logger used by this project
:type LOGGER: logging.Logger

"""


from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import errno
import fileinput
import glob
import itertools
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib

import copr
import rpm


NAME = 'stack-ci'

LOGGER = logging.getLogger(NAME)


def decode_path(path):
    """Decode a filesystem path string.

    :param path: the filesystem path
    :type path: str
    :return: the decoded path
    :rtype: unicode

    """
    return path.decode(sys.getfilesystemencoding() or sys.getdefaultencoding())


def _remkdir(name, notexists_ok=False):
    """Re-create a directory.

    :param name: a name of the directory
    :type name: unicode
    :param notexists_ok: create the directory if the path does not exist
       instead of raising an error
    :type notexists_ok: bool
    :raises exceptions.OSError: if the directory cannot be re-created

    """
    try:
        shutil.rmtree(name)
    except OSError as err:
        if not notexists_ok or err.errno != errno.ENOENT:
            raise
    os.mkdir(name)


def _substitute_file(filename, regex, replacement):
    """Replace every occurrence of a regular expression in a file.

    :param filename: a name of the file
    :type filename: unicode
    :param regex: the regular expression
    :type regex: re.RegexObject
    :param replacement: the replacement
    :type replacement: str
    :returns: the number of substituted lines
    :rtype: int
    :raises exceptions.IOError: if the file is not accessible

    """
    count = 0
    for line in fileinput.input([filename], inplace=1):
        if regex.match(line):
            print(replacement)
            count += 1
            continue
        print(line, end=b'')
    return count


def _log_call(executable, status, output, encoding='utf-8'):
    """Log the result of an executable.

    :param executable: a name of the executable
    :type executable: unicode
    :param status: the exit status
    :type status: int
    :param output: the captured output
    :type output: str
    :param encoding: the encoding of the output
    :type encoding: unicode

    """
    LOGGER.log(
        logging.ERROR if status else logging.DEBUG,
        '"%s" have exited with %s:\n  captured output:\n%s',
        executable,
        status,
        re.sub(r'^', '    ', output.decode(encoding, 'replace'), flags=re.M))


def _create_copr(name, chroots, repos=()):
    """Create a Copr project.

    :param name: a name of the project
    :type name: unicode
    :param chroots: names of the chroots to be used in the project
    :type chroots: collections.Iterable[unicode]
    :param repos: the URL of each additional repository that is required
    :type repos: collections.Iterable[unicode]
    :raises exceptions.ValueError: if the project cannot be created

    """
    chroots, repos = list(chroots), list(repos)
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
    try:
        client = copr.client.CoprClient.create_from_file_config()
        client.create_project(name, chroots=chroots, repos=repos)
    except Exception:
        LOGGER.debug('Copr have failed to create a project.', exc_info=True)
        raise ValueError('Copr failed')


def rpm_headers(dirname):
    """Iterate over the headers of the RPMs in a directory.

    :param dirname: a name of the directory
    :type dirname: unicode
    :return: a generator yielding the pairs (file name, RPM header)
    :rtype: generator[tuple[unicode, rpm.hdr]]

    """
    filenames = glob.iglob(os.path.join(dirname, '*.rpm'))
    transaction = rpm.TransactionSet()
    for filename in filenames:
        try:
            with open(filename) as file_:
                header = transaction.hdrFromFdno(file_.fileno())
        except (IOError, rpm.error):
            LOGGER.debug('Failed to read %s', filename, exc_info=True)
            continue
        yield filename, header


def _build_srpm(spec, sources, destdn, release=None):
    """Build a SRPM from a spec file and source archives.

    The "rpmbuild" executable must be available. The source archives and
    SRPMs in ~/rpmbuild/SRPMS will be removed.

    :param spec: a name of the spec file
    :type spec: unicode
    :param sources: a name of the source archives (with shell-style
       wildcards)
    :param sources: str
    :param destdn: the name of a destination directory
    :type destdn: unicode
    :param release: a custom release number of the resulting SRPM
    :type release: str | None
    :returns: a combination of the standard output and standard error of
       the executable
    :rtype: str
    :raises exceptions.IOError: if the build cannot be prepared
    :raises exceptions.OSError: if the build cannot be prepared or if
       the executable cannot be executed
    :raises subprocess.CalledProcessError: if the executable fails to
       build the SRPM

    """
    if release:
        count = _substitute_file(
            spec, re.compile(br'^\s*Release\s*:\s*.+$', re.IGNORECASE),
            b'Release: {}'.format(release))
        assert count == 1, 'unexpected spec file'
    rpmbuilddn = os.path.expanduser(os.path.join('~', 'rpmbuild'))
    for filename in glob.iglob(sources):
        shutil.move(filename, os.path.join(rpmbuilddn, 'SOURCES'))
    srpmdn = os.path.join(rpmbuilddn, 'SRPMS')
    for filename, header in rpm_headers(srpmdn):
        if not header.isSource():
            continue
        os.remove(filename)
    output = subprocess.check_output(
        [b'rpmbuild', b'--quiet', b'-bs', b'--clean', b'--rmsource',
         b'--rmspec', spec],
        stderr=subprocess.STDOUT)
    for filename, header in rpm_headers(srpmdn):
        if not header.isSource():
            continue
        shutil.move(filename, destdn)
    return output


def _build_tito(destdn, last_tag=True):
    """Build a SRPM of a tito-enabled project in the current work. dir.

    The "tito" executable must be available. The destination directory
    will be overwritten.

    :param destdn: the name of a destination directory
    :type destdn: unicode
    :param last_tag: build from the latest tag instead of the current HEAD
    :type last_tag: bool
    :raises exceptions.OSError: if the destination directory cannot be
       created or overwritten or if the executable cannot be executed
    :raises exceptions.ValueError: if the build fails

    """
    # It isn't possible to define custom RPM macros.
    # See https://bugzilla.redhat.com/show_bug.cgi?id=1260098
    LOGGER.info('Building a SRPM from %s...', os.getcwdu())
    _remkdir(destdn, notexists_ok=True)
    # FIXME: https://github.com/dgoodwin/tito/issues/171
    cmd = [
        'tito', 'build', '--srpm', '--output={}'.format(destdn)]
    if not last_tag:
        cmd.insert(3, '--test')
    status = 0
    try:
        # FIXME: https://github.com/dgoodwin/tito/issues/165
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        status, output = err.returncode, err.output
        raise ValueError('"tito" failed')
    finally:
        _log_call(cmd[0], status, output)


def _build_librepo(spec, destdn, release=None):
    """Build a SRPM of a librepo project fork in the current work. dir.

    The "git", "rpmbuild", "sh" and "xz" executables must be available.
    The destination directory will be overwritten.

    :param spec: the ID of the Fedora Git revision of the spec file
    :type spec: unicode
    :param destdn: the name of a destination directory
    :type destdn: unicode
    :param release: a custom release number of the resulting RPMs
    :type release: str | None
    :raises exceptions.IOError: if the spec file of librepo cannot be
       downloaded or if the build cannot be prepared
    :raises urllib.ContentTooShortError: if the spec file of librepo
       cannot be downloaded
    :raises exceptions.OSError: if the build cannot be prepared or if
       an executable cannot be executed or if the destination directory
       cannot be created or overwritten
    :raises exceptions.ValueError: if the build fails

    """
    LOGGER.info('Building a SRPM from %s...', os.getcwdu())
    specurlpat = (
        'http://pkgs.fedoraproject.org/cgit/librepo.git/plain/librepo.spec?'
        'id={}')
    specfn = urllib.urlretrieve(specurlpat.format(spec))[0]
    # FIXME: https://github.com/Tojaj/librepo/issues/69
    try:
        gitrev = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], universal_newlines=True)
    except subprocess.CalledProcessError as err:
        _log_call(err.cmd[0], err.returncode, err.output)
        raise ValueError('"utils/make_tarball.sh" failed')
    gitrev = gitrev.rstrip('\n')
    count = _substitute_file(
        specfn, re.compile(br'^\s*%global\s+gitrev\s+.+$'),
        b'%global gitrev {}'.format(gitrev))
    assert count == 1, 'unexpected spec file'
    try:
        subprocess.check_output(
            [b'sh', os.path.join(b'utils', b'make_tarball.sh'), gitrev],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        _log_call(err.cmd[0], err.returncode, err.output)
        raise ValueError('"utils/make_tarball.sh" failed')
    _remkdir(destdn, notexists_ok=True)
    try:
        output = _build_srpm(
            specfn, b'*-{}.tar.xz'.format(gitrev), destdn, release)
    except subprocess.CalledProcessError as err:
        _log_call('rpmbuild', err.returncode, err.output)
        raise ValueError('"rpmbuild" failed')
    else:
        _log_call('rpmbuild', 0, output)


def _build_libcomps(destdn, release=None):
    """Build a SRPM of a librepo project fork in the current work. dir.

    The "python" and "rpmbuild" executables must be available. The
    destination directory will be overwritten.

    :param destdn: the name of a destination directory
    :type destdn: unicode
    :param release: a custom release number of the resulting SRPM
    :type release: str | None
    :raises exceptions.OSError: if some of the executables cannot be
       executed or if the destination directory cannot be created or
       overwritten
    :raises exceptions.IOError: if the build cannot be prepared
    :raises exceptions.ValueError: if the build fails

    """
    LOGGER.info('Building a SRPM from %s...', os.getcwdu())
    try:
        # FIXME: https://github.com/midnightercz/libcomps/pull/26
        subprocess.check_output(
            ['python', 'build_prep.py'], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        _log_call(err.cmd[0], err.returncode, err.output)
        raise ValueError('sources preparation failed')
    _remkdir(destdn, notexists_ok=True)
    try:
        output = _build_srpm('libcomps.spec', b'*-*.tar.gz', destdn, release)
    except subprocess.CalledProcessError as err:
        _log_call('rpmbuild', err.returncode, err.output)
        raise ValueError('"rpmbuild" failed')
    else:
        _log_call('rpmbuild', 0, output)


def _build_in_copr(dirname, project):
    """Build RPMs from SRPMs in Copr.

    :param dirname: a name of the directory with SRPMs
    :type dirname: unicode
    :param project: a name of the Copr project
    :type project: unicode
    :raises exceptions.ValueError: if the build cannot be requested or
       if the build fails

    """
    srpms = {
        fname: header[rpm.RPMTAG_N] for fname, header in rpm_headers(dirname)
        if header.isSource()}
    pkgs = list(srpms.keys())
    LOGGER.info('Building RPMs from %s...', ', '.join(pkgs))
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
    try:
        client = copr.client.CoprClient.create_from_file_config()
        result = client.create_new_build(project, pkgs=pkgs)
    except OSError:
        LOGGER.debug('Copr have failed to create a project.', exc_info=True)
        raise ValueError('Copr failed')
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1258970
    while True:
        for build in result.builds_list:
            # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
            try:
                status = build.handle.get_build_details().status
            except Exception:
                LOGGER.debug(
                    'Copr have failed to get build details.', exc_info=True)
                raise ValueError('Copr failed')
            if status not in {'skipped', 'failed', 'succeeded'}:
                break
        else:
            break
        time.sleep(10)
    success, urls = True, []
    for build in result.builds_list:
        # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
        try:
            details = build.handle.get_build_details()
        except Exception:
            LOGGER.debug(
                'Copr have failed to get build details.', exc_info=True)
            raise ValueError('Copr failed')
        if details.status == 'failed':
            success = False
        # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259251
        for chroot in details.data['chroots']:
            for package in srpms.values():
                urls.append('{}/{}/{:08}-{}'.format(
                    details.results, chroot, build.build_id, package.decode()))
    LOGGER.info('Results of the build can be found at: %s', ', '.join(urls))
    if not success:
        raise ValueError('build failed')


def _start_commandline():  # pylint: disable=R0912,R0915
    """Start the command line interface to the program.

    The root logger is configured to write DEBUG+ messages into the
    destination directory if not configured otherwise. A handler that
    writes INFO+ messages to :data:`sys.stderr` is added to
    :const:`.LOGGER`.

    The interface usage is::

        usage: prog [-h] {setup,build} ...

        Test the DNF stack.

        positional arguments:
          {setup,build}  the action to be performed

        optional arguments:
          -h, --help     show this help message and exit

        If an error occurs the exit status is non-zero.

    The usage of the "setup" command is::

        usage: prog setup [-h] [--add-repository URL]
                          CHROOT [CHROOT ...] PROJECT

        Create a new Copr project.

        positional arguments:
          CHROOT                the chroots to be used in the project
                                ("22" adds "fedora-22-i386,
                                fedora-22-x86_64", "23" adds
                                "fedora-23-i386, fedora-23-x86_64",
                                "rawhide" adds "fedora-rawhide-i386,
                                fedora-rawhide-x86_64")
          PROJECT               the name of the project

        optional arguments:
          -h, --help            show this help message and exit
          --add-repository URL  the URL of an additional repository
                                that is required

    The usage of the "build" command is::

        usage: prog build [-h] PROJECT {tito,librepo,libcomps} ...

        Build RPMs of a project from the checkout in the current working
        directory in Copr.

        positional arguments:
          PROJECT               the name of the Copr project
          {tito,librepo,libcomps}
                                the type of the project

        optional arguments:
          -h, --help            show this help message and exit

    The usage for "tito" projects is::

        usage: prog build PROJECT tito [-h]

        Build a tito-enabled project.

        optional arguments:
          -h, --help  show this help message and exit

        The "tito" executable must be available.

    The usage for "librepo" projects is::

        usage: prog build PROJECT librepo [-h] [--release RELEASE] SPEC

        Build a librepo project fork.

        positional arguments:
          SPEC               the ID of the Fedora Git
                             revision of the spec file

        optional arguments:
          -h, --help         show this help message and exit
          --release RELEASE  a custom release number of the
                             resulting RPMs

        The "git", "rpmbuild", "sh" and "xz" executables must be
        available.

    The usage for "libcomps" projects is::

        usage: prog build PROJECT libcomps [-h] [--release RELEASE]

        Build a libcomps project fork.

        optional arguments:
          -h, --help         show this help message and exit
          --release RELEASE  a custom release number of the
                             resulting RPMs

        The "python" and "rpmbuild" executables must be available.

    :raises exceptions.SystemExit: with a non-zero exit status if an
       error occurs

    """
    chroot2chroots = {
        '22': {'fedora-22-i386', 'fedora-22-x86_64'},
        '23': {'fedora-23-i386', 'fedora-23-x86_64'},
        'rawhide': {'fedora-rawhide-i386', 'fedora-rawhide-x86_64'}}
    argparser = argparse.ArgumentParser(
        description='Test the DNF stack.',
        epilog='If an error occurs the exit status is non-zero.')
    cmdparser = argparser.add_subparsers(
        dest='command', help='the action to be performed')
    setupparser = cmdparser.add_parser(
        'setup', description='Create a new Copr project.')
    setupparser.add_argument(
        '--add-repository', action='append', default=[], type=unicode,
        help='the URL of an additional repository that is required',
        metavar='URL')
    setupparser.add_argument(
        'chroot', nargs='+', choices=sorted(chroot2chroots), metavar='CHROOT',
        help='the chroots to be used in the project ({})'.format(
            ', '.join('"{}" adds "{}"'.format(key, ', '.join(sorted(value)))
                      for key, value in sorted(chroot2chroots.items()))))
    setupparser.add_argument(
        'project', type=unicode, metavar='PROJECT',
        help='the name of the project')
    buildparser = cmdparser.add_parser(
        'build',
        description='Build RPMs of a project from the checkout in the current '
                    'working directory in Copr.')
    buildparser.add_argument(
        'copr', type=unicode, metavar='PROJECT',
        help='the name of the Copr project')
    projparser = buildparser.add_subparsers(
        dest='project', help='the type of the project')
    projparser.add_parser(
        'tito', description='Build a tito-enabled project.',
        epilog='The "tito" executable must be available.')
    commonparser = argparse.ArgumentParser(add_help=False)
    commonparser.add_argument(
        '--release', help='a custom release number of the resulting RPMs')
    repoparser = projparser.add_parser(
        'librepo', description='Build a librepo project fork.',
        epilog='The "git", "rpmbuild", "sh" and "xz" executables must be '
               'available.',
        parents=[commonparser])
    repoparser.add_argument(
        'fedrev', type=unicode, metavar='SPEC',
        help='the ID of the Fedora Git revision of the spec file')
    projparser.add_parser(
        'libcomps', description='Build a libcomps project fork.',
        epilog='The "python" and "rpmbuild" executables must be available.',
        parents=[commonparser])
    options = argparser.parse_args()
    logfn = os.path.join(os.getcwdu(), '{}.log'.format(NAME))
    try:
        logging.basicConfig(
            filename=logfn,
            filemode='wt',
            format='%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:'
                   '%(message)s',
            datefmt='%Y%m%dT%H%M%S',
            level=logging.DEBUG)
    except IOError:
        sys.exit('A log file ({}) be created or overwritten.'.format(logfn))
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    LOGGER.addHandler(handler)
    if options.command == b'setup':
        chroots = set(itertools.chain.from_iterable(
            chroot2chroots[chroot] for chroot in options.chroot))
        try:
            _create_copr(options.project, chroots, options.add_repository)
        except ValueError:
            LOGGER.debug(
                'An exception have occurred during setup.', exc_info=True)
            sys.exit('Copr have failed to create the project.')
    elif options.command == b'build':
        destdn = decode_path(tempfile.mkdtemp())
        try:
            if options.project == b'tito':
                try:
                    _build_tito(destdn, last_tag=False)
                except ValueError:
                    LOGGER.debug(
                        'An exception have occurred during the tito build.',
                        exc_info=True)
                    sys.exit(
                        'The build have failed. Hopefully the executables '
                        'have created an output in the destination '
                        'directory.')
                except OSError:
                    LOGGER.debug(
                        'An exception have occurred during the tito build.',
                        exc_info=True)
                    sys.exit(
                        'The destination directory cannot be overwritten '
                        'or the executable cannot be executed.')
            elif options.project == b'librepo':
                try:
                    _build_librepo(
                        options.fedrev, destdn, options.release)
                except (IOError, urllib.ContentTooShortError, ValueError):
                    LOGGER.debug(
                        'An exception have occurred during the librepo build.',
                        exc_info=True)
                    sys.exit('The build have failed.')
                except OSError:
                    LOGGER.debug(
                        'An exception have occurred during the librepo build.',
                        exc_info=True)
                    sys.exit(
                        'The destination directory cannot be overwritten '
                        'or some of the executables cannot be executed.')
            elif options.project == b'libcomps':
                try:
                    _build_libcomps(destdn, options.release)
                except (IOError, ValueError):
                    LOGGER.debug(
                        'An exception have occurred during the libcmps build.',
                        exc_info=True)
                    sys.exit(
                        'The build have failed. Hopefully the executables have'
                        ' created an output in the destination directory.')
                except OSError:
                    LOGGER.debug(
                        'An exception have occurred during the libcmps build.',
                        exc_info=True)
                    sys.exit(
                        'The destination directory cannot be overwritten '
                        'or some of the executables cannot be executed.')
            try:
                _build_in_copr(destdn, options.copr)
            except ValueError:
                LOGGER.debug(
                    'Copr have failed to build the RPMs.', exc_info=True)
                sys.exit(
                    'The build could not be requested or the build have '
                    'failed. Hopefully Copr provides some details.')
        finally:
            shutil.rmtree(destdn)


if __name__ == '__main__':
    _start_commandline()
