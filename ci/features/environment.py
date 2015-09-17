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

"""This module provides the test fixture common to all the features.

Among other things, the fixture contains a tito-enabled project
directory, a librepo fork directory, a testing repository and an
empty working directory which is created before every scenario.
The only RPM of the tito-enabled project appends the value of an
RPM macro %{snapshot} to its release number if set.

The :class:`behave.runner.Context` instance passed to the environmental
controls and to the step implementations is expected to have following
attributes:

:attr:`!titodn` : :class:`str`
    A name of the directory with the tito-enabled project.
:attr:`!librepodn` : :class:`str`
    A name of the directory with the librepo project fork.
:attr:`!libcompsdn` : :class:`str`
    A name of the directory with the libcomps project fork.
:attr:`!repourl` : :data:`types.UnicodeType`
    The URL of the testing repository.
:attr:`!chr_option` : :class:`list[types.UnicodeType]`
    Names the chroots to be used in a Copr project.
:attr:`!proj_option` : :data:`types.UnicodeType` | :data:`None`
    A name of the Copr project to be created.
:attr:`!repo_option` : :class:`list[types.UnicodeType]`
    The URL of each repository that should be added to the Copr project
    or to the Mock's "config_opts['yum.conf']" option.
:attr:`!rel_option` : :data:`types.UnicodeType` | :data:`None`
    A custom release number of the resulting RPMs passed to stack-ci.
:attr:`!temp_coprs` : :class:`set[types.UnicodeType]`
    Names of the Copr projects to be removed after every scenario.

"""


from __future__ import absolute_import
from __future__ import unicode_literals

import os
import shutil
import subprocess
import tempfile

import copr
import pygit2

import stackci


def before_all(context):
    """Do the preparation that can be done at the very beginning.

    The "tito" executable must be available.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :raises exceptions.IOError: if the tito-enabled project cannot be
       created
    :raises exceptions.ValueError: if the tito-enabled project cannot be
       created
    :raises exceptions.OSError: if the executable cannot be executed
    :raises subprocess.CalledProcessError: if the tito-enabled project
       cannot be created

    """
    signature = pygit2.Signature(
        stackci.NAME, '{}@example.com'.format(stackci.NAME))
    context.titodn = tempfile.mkdtemp()
    dst_spec = os.path.join(context.titodn, b'foo.spec')
    shutil.copy(
        os.path.join(os.path.dirname(__file__), b'resources', b'foo.spec'),
        dst_spec)
    try:
        titorepo = pygit2.init_repository(context.titodn)
        titorepo.index.add(os.path.relpath(dst_spec, titorepo.workdir))
        titorepo.index.write()
        titorepo.create_commit(
            'refs/heads/master', signature, signature, 'Add a spec file.',
            titorepo.index.write_tree(), [])
    # FIXME: https://github.com/libgit2/pygit2/issues/531
    except Exception as err:
        raise ValueError('Git repository creation failed: {}'.format(err))
    # FIXME: https://github.com/dgoodwin/tito/issues/171
    subprocess.check_call(['tito', 'init'], cwd=context.titodn)
    context.librepodn = tempfile.mkdtemp()
    try:
        libreporepo = pygit2.clone_repository(
            'https://github.com/rpm-software-management/librepo.git',
            context.librepodn)
        libreporepo.reset(
            'd9bed0d9f96b505fb86a1adc50b3d6f8275fab93', pygit2.GIT_RESET_HARD)
    # FIXME: https://github.com/libgit2/pygit2/issues/531
    except Exception as err:
        raise ValueError('Git repository creation failed: {}'.format(err))
    context.libcompsdn = tempfile.mkdtemp()
    try:
        libcompsrepo = pygit2.clone_repository(
            'https://github.com/rpm-software-management/libcomps.git',
            context.libcompsdn)
        libcompsrepo.reset(
            'eb966bc43097c0d00e154abe7f40f4d1d75fbcd1', pygit2.GIT_RESET_HARD)
    # FIXME: https://github.com/libgit2/pygit2/issues/531
    except Exception as err:
        raise ValueError('Git repository creation failed: {}'.format(err))


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
def before_scenario(context, scenario):  # pylint: disable=unused-argument
    """Do the preparation that must be done before every scenario.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param scenario: the next tested scenario
    :type scenario: behave.model.Scenario

    """
    context.chr_option = []
    context.proj_option = None
    context.repo_option = []
    context.rel_option = None
    context.temp_coprs = set()


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
def after_scenario(context, scenario):  # pylint: disable=unused-argument
    """Do the preparation that must be done after every scenario.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param scenario: the next tested scenario
    :type scenario: behave.model.Scenario
    :raises exceptions.ValueError: if the temporary Copr projects cannot
       be removed

    """
    while True:
        try:
            name = context.temp_coprs.pop()
        except KeyError:
            break
        # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
        try:
            client = copr.client.CoprClient.create_from_file_config()
            client.delete_project(name)
        except Exception as err:
            raise ValueError('Copr failed: {}'.format(err))


def after_all(context):
    """Do the cleanup that can be done at the very end.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :raises exceptions.OSError: if the tito-enabled project cannot be
       removed

    """
    shutil.rmtree(context.librepodn)
    shutil.rmtree(context.titodn)
