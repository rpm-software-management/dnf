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

"""This module implements the feature steps."""


from __future__ import absolute_import
from __future__ import unicode_literals

import os
import subprocess

import behave
import copr


def _run_ci(args, cwd=None):
    """Run stackci.py from command line.

    The "git", "python", "rpmbuild", "sh", "tito" and "xz" executables
    must be available.

    :param args: additional command line arguments
    :type args: list[unicode]
    :param cwd: a name of the desired working directory
    :type cwd: unicode | None
    :raises exceptions.OSError: if an executable cannot be executed
    :raises subprocess.CalledProcessError: if the script fails

    """
    subprocess.check_call(
        ['python', os.path.abspath('stackci.py')] + args, cwd=cwd)


def _run_setup(name, chroots, repos=()):
    """Run the setup command of stackci.py from command line.

    The "git", "python", "rpmbuild", "sh", "tito" and "xz" executables
    must be available.

    :param name: a name of the project
    :type name: unicode
    :param chroots: names of the chroots to be used in the project
    :type chroots: collections.Iterable[unicode]
    :param repos: the URL of each additional repository that is required
    :type repos: collections.Iterable[unicode]
    :raises exceptions.OSError: if an executable cannot be executed
    :raises subprocess.CalledProcessError: if the command fails

    """
    args = ['setup'] + list(chroots) + [name]
    for url in repos:
        args.insert(1, url)
        args.insert(1, '--add-repository')
    _run_ci(args)


@behave.given('a Copr project {name} exists')  # pylint: disable=no-member
def _prepare_copr(context, name):
    """Prepare a Copr project.

    The "git", "python", "rpmbuild", "sh", "tito" and "xz" executables
    must be available.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param name: a name of the project
    :type name: unicode
    :raises exceptions.OSError: if an executable cannot be executed
    :raises subprocess.CalledProcessError: if the creation fails

    """
    _run_setup(name, ['rawhide'])
    context.temp_coprs.add(name)


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.given(  # pylint: disable=no-member
    'following options are configured as follows')
def _configure_options(context):
    """Configure the user-defined options.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :raises exceptions.ValueError: if the context has no table

    """
    if not context.table:
        raise ValueError('table not found')
    expected = [
        ['Option'], ['Option', 'Value'], ['Option', 'Value #1', 'Value #2']]
    if context.table.headings not in expected:
        raise NotImplementedError('configuration format not supported')
    for row in context.table:
        try:
            option, value = row
        except ValueError:
            raise NotImplementedError('configuration not supported')
        if option == 'CHROOT':
            context.chr_option.append(value)
        elif option == 'PROJECT':
            context.proj_option = value
        elif option == '--add-repository':
            context.repo_option.append(value)
        elif option == '--release':
            context.rel_option = value
        else:
            raise NotImplementedError('configuration not supported')


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.when('I create a Copr project')  # pylint: disable=no-member
def _create_copr(context):
    """Create a Copr project.

    The "git", "python", "rpmbuild", "sh", "tito" and "xz" executables
    must be available.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :raises exceptions.OSError: if an executable cannot be executed
    :raises subprocess.CalledProcessError: if the creation fails

    """
    _run_setup(
        context.proj_option, context.chr_option, reversed(context.repo_option))
    context.temp_coprs.add(context.proj_option)


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.when('I build RPMs of the {project}')  # pylint: disable=no-member
def _build_rpms(context, project):
    """Build RPMs of a project.

    The "git", "python", "rpmbuild", "sh", "tito" and "xz" executables
    must be available.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param project: a description of the project
    :type project: unicode
    :raises exceptions.OSError: if the executable cannot be executed
    :raises subprocess.CalledProcessError: if the build fails

    """
    args = ['build', context.proj_option]
    if project == 'tito-enabled project':
        args.insert(2, 'tito')
        cwd = context.titodn
    elif project == 'librepo project fork':
        args.insert(2, '38f323b94ea6ba3352827518e011d818202167a3')
        if context.rel_option:
            args.insert(2, context.rel_option)
            args.insert(2, '--release')
        args.insert(2, 'librepo')
        cwd = context.librepodn
    elif project == 'libcomps project fork':
        if context.rel_option:
            args.insert(2, context.rel_option)
            args.insert(2, '--release')
        args.insert(2, 'libcomps')
        cwd = context.libcompsdn
    else:
        raise NotImplementedError('project not supported')
    _run_ci(args, cwd)


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.then(  # pylint: disable=no-member
    'I should have a Copr project called {name} with chroots {chroots}')
def _test_copr_project(context, name, chroots):  # pylint: disable=W0613
    """Test whether a Copr project exists.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param name: the name of the project
    :type name: unicode
    :param chroots: names of the chroots to be used in the project
    :type chroots: unicode
    :raises exceptions.ValueError: if the details of the project cannot
       be retrieved

    """
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
    try:
        client = copr.client.CoprClient.create_from_file_config()
        client.get_project_details(name)
    except Exception as err:
        raise ValueError('Copr failed: {}'.format(err))
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259608


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.then(  # pylint: disable=no-member
    'I should have the {repository} repository added to the Copr project '
    'called {name}')
def _test_copr_repo(context, repository, name):  # pylint: disable=W0613
    """Test whether a repository has been added to a Copr project.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param repository: the URL of the repository
    :type repository: unicode
    :param name: the name of the project
    :type name: unicode
    :raises exceptions.AssertionError: if the test fails

    """
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
    try:
        client = copr.client.CoprClient.create_from_file_config()
        details = client.get_project_details(name)
    except Exception as err:
        raise ValueError('Copr failed: {}'.format(err))
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259683
    repos = details.data['detail']['additional_repos'].split(' ')
    assert repository in repos, 'repository not added'


@behave.then('the build should have succeeded')  # pylint: disable=no-member
def _test_success(context):  # pylint: disable=unused-argument
    """Test whether the preceding build have succeeded.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context

    """
    # Behave would fail otherwise so the build must have succeeded if we
    # are here.
    pass


# FIXME: https://bitbucket.org/logilab/pylint/issue/535
@behave.then(  # pylint: disable=no-member
    'the release number of the resulting RPMs of the {project} fork should be '
    '99.2.20150102git3a45678901b23c456d78ef90g1234hijk56789lm')
def _test_release(context, project):  # pylint: disable=unused-argument
    """Test whether the result is affected by RPM macro definitions.

    :param context: the context as described in the environment file
    :type context: behave.runner.Context
    :param project: a description of the project
    :type project: unicode

    """
    # FIXME: https://bugzilla.redhat.com/show_bug.cgi?id=1259293
    # There is no documented way how to obtain the RPMs.
    pass
