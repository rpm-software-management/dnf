# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import contextlib
import logging
import os
import re
import unittest
from functools import reduce

import hawkey
import hawkey.test
from hawkey import SwdbReason, SwdbPkgData

import dnf
import dnf.conf
import dnf.cli.cli
import dnf.cli.demand
import dnf.cli.option_parser
import dnf.comps
import dnf.exceptions
import dnf.goal
import dnf.i18n
import dnf.package
import dnf.persistor
import dnf.pycomp
import dnf.repo
import dnf.sack


if dnf.pycomp.PY3:
    from unittest import mock
    from unittest.mock import MagicMock, mock_open
else:
    from tests import mock
    from tests.mock import MagicMock

    def mock_open(mock=None, data=None):
        if mock is None:
            mock = MagicMock(spec=file)

        handle = MagicMock(spec=file)
        handle.write.return_value = None
        if data is None:
            handle.__enter__.return_value = handle
        else:
            handle.__enter__.return_value = data
        mock.return_value = handle
        return mock


logger = logging.getLogger('dnf')
skip = unittest.skip

TRACEBACK_RE = re.compile(
    r'(Traceback \(most recent call last\):\n'
    r'(?:  File "[^"\n]+", line \d+, in \w+\n'
    r'(?:    .+\n)?)+'
    r'\S.*\n)')
REASONS = {
    'hole': 'group',
    'pepper': 'group',
    'right': 'dep',
    'tour': 'group',
    'trampoline': 'group',
}
RPMDB_CHECKSUM = '47655615e9eae2d339443fa00065d41900f99baf'
TOTAL_RPMDB_COUNT = 10
SYSTEM_NSOLVABLES = TOTAL_RPMDB_COUNT
MAIN_NSOLVABLES = 9
UPDATES_NSOLVABLES = 4
AVAILABLE_NSOLVABLES = MAIN_NSOLVABLES + UPDATES_NSOLVABLES
TOTAL_GROUPS = 4
TOTAL_NSOLVABLES = SYSTEM_NSOLVABLES + AVAILABLE_NSOLVABLES


# testing infrastructure


def dnf_toplevel():
    return os.path.normpath(os.path.join(__file__, '../../'))


def repo(reponame):
    return os.path.join(REPO_DIR, reponame)


def resource_path(path):
    this_dir = os.path.dirname(__file__)
    return os.path.join(this_dir, path)


REPO_DIR = resource_path('repos')
COMPS_PATH = os.path.join(REPO_DIR, 'main_comps.xml')
NONEXISTENT_FILE = resource_path('does-not/exist')
TOUR_44_PKG_PATH = resource_path('repos/rpm/tour-4-4.noarch.rpm')
TOUR_50_PKG_PATH = resource_path('repos/rpm/tour-5-0.noarch.rpm')
TOUR_51_PKG_PATH = resource_path('repos/rpm/tour-5-1.noarch.rpm')
USER_RUNDIR = '/tmp/dnf-user-rundir'


# often used query


def installed_but(sack, *args):
    q = sack.query().filter(reponame__eq=hawkey.SYSTEM_REPO_NAME)
    return reduce(lambda query, name: query.filter(name__neq=name), args, q)


# patching the stdout


@contextlib.contextmanager
def patch_std_streams():
    with mock.patch('sys.stdout', new_callable=dnf.pycomp.StringIO) as stdout, \
            mock.patch('sys.stderr', new_callable=dnf.pycomp.StringIO) as stderr:
        yield (stdout, stderr)


@contextlib.contextmanager
def wiretap_logs(logger_name, level, stream):
    """Record *logger_name* logs of at least *level* into the *stream*."""
    logger = logging.getLogger(logger_name)

    orig_level = logger.level
    logger.setLevel(level)

    handler = logging.StreamHandler(stream)
    orig_handlers = logger.handlers
    logger.handlers = []
    logger.addHandler(handler)

    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(orig_level)
        logger.handlers = orig_handlers


def command_configure(cmd, args):
    parser = dnf.cli.option_parser.OptionParser()
    args = [cmd._basecmd] + args
    parser.parse_main_args(args)
    parser.parse_command_args(cmd, args)
    return cmd.configure()


def command_run(cmd, args):
    command_configure(cmd, args)
    return cmd.run()


def mockSwdbPkg(history, pkg, state="Installed", repo="unknown", reason=SwdbReason.USER):
    """ Add DnfPackage into database """
    hpkg = history.ipkg_to_pkg(pkg)
    pid = history.add_package(hpkg)
    pkg_data = SwdbPkgData()
    history.swdb.trans_data_beg(0, pid, reason, state, False)
    history.update_package_data(pid, 0, pkg_data)
    history.set_repo(hpkg, repo)


class Base(dnf.Base):
    def __init__(self, *args, **kwargs):
        with mock.patch('dnf.rpm.detect_releasever', return_value=69):
            super(Base, self).__init__(*args, **kwargs)

# mock objects


def mock_comps(history, seed_persistor):
    comps = dnf.comps.Comps()
    comps._add_from_xml_filename(COMPS_PATH)

    persistor = history.group
    if seed_persistor:
        name = 'Peppers'
        pkg_types = dnf.comps.MANDATORY
        p_pep = persistor.new_group(name, name, name, False, pkg_types)
        persistor.add_group(p_pep)
        p_pep.add_package(['hole', 'lotus'])

        name = 'somerset'
        pkg_types = dnf.comps.MANDATORY
        p_som = persistor.new_group(name, name, name, False, pkg_types)
        persistor.add_group(p_som)
        p_som.add_package(['pepper', 'trampoline', 'lotus'])

        name = 'sugar-desktop-environment'
        grp_types = dnf.comps.ALL_TYPES
        pkg_types = dnf.comps.ALL_TYPES
        p_env = persistor.new_env(name, name, name, pkg_types, grp_types)
        persistor.add_env(p_env)
        p_env.add_group(['Peppers', 'somerset'])
    return comps


def mock_logger():
    return mock.create_autospec(logger)


class _BaseStubMixin(object):
    """A reusable class for creating `dnf.Base` stubs.

    See also: hawkey/test/python/__init__.py.

    Note that currently the used TestSack has always architecture set to
    "x86_64". This is to get the same behavior when running unit tests on
    different arches.

    """
    def __init__(self, *extra_repos):
        super(_BaseStubMixin, self).__init__(FakeConf())
        for r in extra_repos:
            repo = MockRepo(r, self.conf)
            repo.enable()
            self._repos.add(repo)

        self._repo_persistor = FakePersistor()
        self._ds_callback = mock.Mock()
        self._history = None
        self._closing = False

    def add_test_dir_repo(self, id_, cachedir):
        """Add a repository located in a directory in the tests."""
        repo = dnf.repo.Repo(id_, cachedir)
        repo.baseurl = ['file://%s/%s' % (REPO_DIR, repo.id)]
        self.repos.add(repo)
        return repo

    def close(self):
        self._closing = True
        super(_BaseStubMixin, self).close()

    @property
    def history(self):
        if self._history:
            return self._history
        else:
            self._history = super(_BaseStubMixin, self).history
            if not self._closing:
                # don't reset db on close, it causes several tests to fail
                self._history.reset_db()
            return self._history

    @property
    def sack(self):
        if self._sack:
            return self._sack
        return self.init_sack()

    def _build_comps_solver(self):
        return dnf.comps.Solver(self.history.group, self._comps,
                                REASONS.get)

    def _activate_persistor(self):
        pass

    def init_sack(self):
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a Base reference.
        self._sack = TestSack(REPO_DIR, self)
        self._sack.load_system_repo()
        for repo in self.repos.iter_enabled():
            if repo.__class__ is dnf.repo.Repo:
                self._add_repo_to_sack(repo)
            else:
                fn = "%s.repo" % repo.id
                self._sack.load_test_repo(repo.id, fn)

        self._sack._configure(self.conf.installonlypkgs)
        self._goal = dnf.goal.Goal(self._sack)
        return self._sack

    def mock_cli(self):
        stream = dnf.pycomp.StringIO()
        logger = logging.getLogger('test')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler(stream))
        return mock.Mock(base=self, log_stream=stream, logger=logger,
                         demands=dnf.cli.demand.DemandSheet())

    def read_mock_comps(self, seed_persistor=True):
        self._comps = mock_comps(self.history, seed_persistor)
        return self._comps

    def read_all_repos(self, opts=None):
        for repo in self.repos.values():
            repo._configure_from_options(opts)

    def set_debuglevel(self, level):
        self.conf._set_value('debuglevel', level, dnf.conf.PRIO_RUNTIME)


class BaseCliStub(_BaseStubMixin, dnf.cli.cli.BaseCli):
    """A class mocking `dnf.cli.cli.BaseCli`."""

    def __init__(self, *extra_repos):
        """Initialize the base."""
        super(BaseCliStub, self).__init__(*extra_repos)
        self.output.term = MockTerminal()


class DemandsStub(object):
    pass


class CliStub(object):
    """A class mocking `dnf.cli.Cli`."""

    def __init__(self, base):
        """Initialize the CLI."""
        self.base = base
        self.cli_commands = {}
        self.demands = DemandsStub()
        self.logger = logging.getLogger()
        self.register_command(dnf.cli.commands.HelpCommand)

    def redirect_logger(self, stdout=None, stderr=None):
        return

    def register_command(self, command):
        """Register given *command*."""
        self.cli_commands.update({alias: command for alias in command.aliases})


class MockOutput(object):
    def __init__(self):
        self.term = MockTerminal()

    def setup_progress_callbacks(self):
        return (None, None)


class MockPackage(object):
    def __init__(self, nevra, repo=None):
        self.baseurl = None
        self._chksum = (None, None)
        self.downloadsize = None
        self._header = None
        self.location = '%s.rpm' % nevra
        self.repo = repo
        self.reponame = None if repo is None else repo.id
        self.str = nevra
        self.buildtime = 0
        nevra = hawkey.split_nevra(nevra)
        self.name = nevra.name
        self.epoch = nevra.epoch
        self.version = nevra.version
        self.release = nevra.release
        self.arch = nevra.arch
        self.evr = '%(epoch)d:%(version)s-%(release)s' % vars(self)
        self.pkgtup = (self.name, self.arch, str(self.epoch), self.version,
                       self.release)

    def __str__(self):
        return self.str

    def localPkg(self):
        return os.path.join(self.repo.pkgdir, os.path.basename(self.location))

    def returnIdSum(self):
        return self._chksum


class MockRepo(dnf.repo.Repo):
    def _valid(self):
        return None


class MockQuery(dnf.query.Query):
    def __init__(self, query):
        self.pkgs = [MockPackage(str(p)) for p in query.run()]
        self.i = 0
        self.n = len(self.pkgs)

    def __getitem__(self, key):
        if key < self.n:
            return self.pkgs[key]
        else:
            raise KeyError()

    def __iter__(self):
        return self

    def __len__(self):
        return self.n

    def filter(self, pkg):
        self.pkgs = []
        self.pkgs.extend(pkg)
        self.n = len(self.pkgs)
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.i < self.n:
            i = self.i
            self.i += 1
            return self.pkgs[i]
        else:
            raise StopIteration()

    def run(self):
        return self.pkgs


class MockTerminal(object):
    def __init__(self):
        self.MODE = {'bold': '', 'normal': ''}
        self.columns = 80
        self.real_columns = 80
        self.reinit = mock.Mock()

    def bold(self, s):
        return s


class TestSack(hawkey.test.TestSackMixin, dnf.sack.Sack):
    def __init__(self, repo_dir, base):
        hawkey.test.TestSackMixin.__init__(self, repo_dir)
        dnf.sack.Sack.__init__(self,
                               arch=hawkey.test.FIXED_ARCH,
                               pkgcls=dnf.package.Package,
                               pkginitval=base,
                               make_cache_dir=True)


class MockBase(_BaseStubMixin, Base):
    """A class mocking `dnf.Base`."""


def mock_sack(*extra_repos):
    return MockBase(*extra_repos).sack


class FakeConf(dnf.conf.Conf):
    def __init__(self, **kwargs):
        super(FakeConf, self).__init__()
        self.substitutions['releasever'] = 'Fedora69'
        options = [
            ('assumeyes', None),
            ('best', False),
            ('cachedir', dnf.const.TMPDIR),
            ('clean_requirements_on_remove', False),
            ('color', 'never'),
            ('color_update_installed', 'normal'),
            ('color_update_remote', 'normal'),
            ('color_list_available_downgrade', 'dim'),
            ('color_list_available_install', 'normal'),
            ('color_list_available_reinstall', 'bold'),
            ('color_list_available_upgrade', 'bold'),
            ('color_list_installed_extra', 'bold'),
            ('color_list_installed_newer', 'bold'),
            ('color_list_installed_older', 'bold'),
            ('color_list_installed_reinstall', 'normal'),
            ('color_update_local', 'bold'),
            ('debug_solver', False),
            ('debuglevel', 2),
            ('defaultyes', False),
            ('disable_excludes', []),
            ('diskspacecheck', True),
            ('exclude', []),
            ('include', []),
            ('install_weak_deps', True),
            ('history_record', False),
            ('installonly_limit', 0),
            ('installonlypkgs', ['kernel']),
            ('installroot', '/'),
            ('ip_resolve', None),
            ('multilib_policy', 'best'),
            ('obsoletes', True),
            ('persistdir', '/tmp/swdb/'),
            ('transformdb', False),
            ('protected_packages', ["dnf"]),
            ('plugins', False),
            ('showdupesfromrepos', False),
            ('tsflags', []),
            ('strict', True),
        ] + list(kwargs.items())

        for optname, val in options:
            setattr(self, optname, dnf.conf.Value(val, dnf.conf.PRIO_DEFAULT))

    @property
    def releasever(self):
        return self.substitutions['releasever']


class FakePersistor(object):
    reset_last_makecache = False
    expired_to_add = set()

    def get_expired_repos(self):
        return set()

    def since_last_makecache(self):
        return None

    def save(self):
        pass


# object matchers for asserts


class ObjectMatcher(object):
    """Class allowing partial matching of objects."""

    def __init__(self, type_=None, attrs=None):
        """Initialize a matcher instance."""
        self._type = type_
        self._attrs = attrs

    def __eq__(self, other):
        """Test whether this object is equal to the *other* one."""
        if self._type is not None:
            if type(other) is not self._type:
                return False

        if self._attrs:
            for attr, value in self._attrs.items():
                if value != getattr(other, attr):
                    return False
        return True

    def __ne__(self, other):
        """Test whether this object is not equal to the *other* one."""
        return not self == other

    def __repr__(self):
        """Compute the "official" string representation of this object."""
        args_strs = []

        if self._type is not None:
            args_strs.append('type_=%s' % repr(self._type))

        if self._attrs:
            attrs_str = ', '.join('%s: %s' % (dnf.i18n.ucd(attr), repr(value))
                                  for attr, value in self._attrs.items())
            args_strs.append('attrs={%s}' % attrs_str)

        return '%s(%s)' % (type(self).__name__, ", ".join(args_strs))


# test cases:


class TestCase(unittest.TestCase):

    if not dnf.pycomp.PY3:
        assertCountEqual = unittest.TestCase.assertItemsEqual

    def assertEmpty(self, collection):
        return self.assertEqual(len(collection), 0)

    def assertFile(self, path):
        """Assert the given path is a file."""
        return self.assertTrue(os.path.isfile(path))

    def assertLength(self, collection, length):
        return self.assertEqual(len(collection), length)

    def assertPathDoesNotExist(self, path):
        return self.assertFalse(os.access(path, os.F_OK))

    def assertStartsWith(self, string, what):
        return self.assertTrue(string.startswith(what))

    def assertTracebackIn(self, end, string):
        """Test that a traceback ending with line *end* is in the *string*."""
        traces = (match.group() for match in TRACEBACK_RE.finditer(string))
        self.assertTrue(any(trace.endswith(end) for trace in traces))

    def assertTransEqual(self, trans_pkgs, list):
        return self.assertCountEqual([pkg.name for pkg in trans_pkgs], list)


class DnfBaseTestCase(TestCase):

    # create base with specified test repos
    REPOS = []

    # initialize mock sack
    INIT_SACK = False

    # initialize self.base._transaction
    INIT_TRANSACTION = False

    # False: self.base = MockBase()
    # True: self.base = BaseCliStub()
    BASE_CLI = False

    # None: self.cli = None
    # "init": self.cli = dnf.cli.cli.Cli(self.base)
    # "mock": self.cli = self.base.mock_cli()
    # "stub": self.cli = StubCli(self.base)
    CLI = None

    # read test comps data
    COMPS = False

    # pass as seed_persistor option to reading test comps data
    COMPS_SEED_PERSISTOR = False

    # initialize self.solver = dnf.comps.Solver()
    COMPS_SOLVER = False

    def setUp(self):
        if self.BASE_CLI:
            self.base = BaseCliStub(*self.REPOS)
        else:
            self.base = MockBase(*self.REPOS)

        if self.CLI is None:
            self.cli = None
        elif self.CLI == "init":
            self.cli = dnf.cli.cli.Cli(self.base)
        elif self.CLI == "mock":
            self.cli = self.base.mock_cli()
        elif self.CLI == "stub":
            self.cli = CliStub(self.base)
        else:
            raise ValueError("Invalid CLI value: {}".format(self.CLI))

        if self.COMPS:
            self.base.read_mock_comps(seed_persistor=self.COMPS_SEED_PERSISTOR)

        if self.INIT_SACK:
            self.base.init_sack()

        if self.INIT_TRANSACTION:
            self.base._transaction = dnf.transaction.Transaction()

        if self.COMPS_SOLVER:
            self.solver = dnf.comps.Solver(self.persistor, self.comps, REASONS.get)
        else:
            self.solver = None

    def tearDown(self):
        self.base.close()

    @property
    def comps(self):
        return self.base.comps

    @property
    def goal(self):
        return self.base._goal

    @property
    def history(self):
        return self.base.history

    @property
    def persistor(self):
        return self.base.history.group

    @property
    def sack(self):
        return self.base.sack


class ResultTestCase(DnfBaseTestCase):

    allow_erasing = False

    def _get_installed(self, base):
        try:
            base.resolve(self.allow_erasing)
        except dnf.exceptions.DepsolveError:
            self.fail()

        installed = set(base.sack.query().installed())
        for r in base._transaction.remove_set:
            installed.remove(r)
        installed.update(base._transaction.install_set)
        return installed

    def assertResult(self, base, pkgs):
        """Check whether the system contains the given pkgs.

        pkgs must be present. Any other pkgs result in an error. Pkgs are
        present if they are in the rpmdb and are not REMOVEd or they are
        INSTALLed.
        """

        self.assertCountEqual(self._get_installed(base), pkgs)

    def installed_removed(self, base):
        try:
            base.resolve(self.allow_erasing)
        except dnf.exceptions.DepsolveError:
            self.fail()

        installed = base._transaction.install_set
        removed = base._transaction.remove_set
        return installed, removed
