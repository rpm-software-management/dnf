# Copyright (C) 2012-2014  Red Hat, Inc.
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
from functools import reduce
import contextlib
import dnf
import dnf.cli.cli
import dnf.cli.demand
import dnf.comps
import dnf.exceptions
import dnf.goal
import dnf.i18n
import dnf.package
import dnf.persistor
import dnf.pycomp
import dnf.repo
import dnf.sack
import dnf.yum.rpmsack
import hawkey
import hawkey.test
import itertools
import logging
import os
import re
import unittest

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
    'hole'      : 'group',
    'pepper'    : 'group',
    'right'     : 'dep',
    'tour'      : 'group',
    'trampoline': 'group',
}
RPMDB_CHECKSUM = '528a64b44871e11dcdc9e1fbcb00b4a6c9ae3421'
TOTAL_RPMDB_COUNT = 8
SYSTEM_NSOLVABLES = TOTAL_RPMDB_COUNT
MAIN_NSOLVABLES = 9
UPDATES_NSOLVABLES = 4
AVAILABLE_NSOLVABLES = MAIN_NSOLVABLES + UPDATES_NSOLVABLES
TOTAL_GROUPS = 3
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
    logger.addHandler(handler)

    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(orig_level)

# mock objects

def mock_comps(seed_persistor):
    comps = dnf.comps.Comps()
    comps.add_from_xml_filename(COMPS_PATH)

    persistor = MockGroupPersistor()
    if seed_persistor:
        p_env = persistor.environment('sugar-desktop-environment')
        p_env.name = 'Sugar Desktop Environment'
        p_env.ui_name = 'Sugar Desktop Environment'
        p_env.grp_types = dnf.comps.ALL_TYPES
        p_env.pkg_types = dnf.comps.ALL_TYPES
        p_env.full_list.extend(('Peppers', 'somerset'))
        p_pep = persistor.group('Peppers')
        p_pep.name = 'Pepper\'s'
        p_pep.ui_name = 'Pepper\'s'
        p_pep.pkg_types = dnf.comps.MANDATORY
        p_pep.full_list.extend(('hole', 'lotus'))
        p_som = persistor.group('somerset')
        p_som.name = 'Solid Ground'
        p_som.ui_name = 'Solid Ground'
        p_som.pkg_types = dnf.comps.MANDATORY
        p_som.full_list.extend(('pepper', 'trampoline', 'lotus'))

    return comps, persistor


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
            repo = MockRepo(r, None)
            repo.enable()
            self._repos.add(repo)

        self._persistor = FakePersistor()
        self._yumdb = MockYumDB()
        self.ds_callback = mock.Mock()

    def add_test_dir_repo(self, id_, cachedir):
        """Add a repository located in a directory in the tests."""
        repo = dnf.repo.Repo(id_, cachedir)
        repo.baseurl = ['file://%s/%s' % (REPO_DIR, repo.id)]
        self.repos.add(repo)
        return repo

    @property
    def sack(self):
        if self._sack:
            return self._sack
        return self.init_sack()

    def _activate_group_persistor(self):
        return MockGroupPersistor()

    def build_comps_solver(self):
        return dnf.comps.Solver(self.group_persistor, REASONS.get)

    def activate_persistor(self):
        pass

    def init_sack(self):
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a Base reference.
        self._sack = TestSack(REPO_DIR, self)
        self._sack.load_system_repo()
        for repo in self.repos.iter_enabled():
            if repo.__class__ is dnf.repo.Repo:
                self._add_repo_to_sack(repo.id)
            else:
                fn = "%s.repo" % repo.id
                self._sack.load_test_repo(repo.id, fn)

        self._sack.configure(self.conf.installonlypkgs)
        self._goal = dnf.goal.Goal(self._sack)
        return self._sack

    def close(self):
        pass

    def mock_cli(self):
        stream = dnf.pycomp.StringIO()
        logger = logging.getLogger('test')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler(stream))
        return mock.Mock(base=self, log_stream=stream, logger=logger,
                         nogpgcheck=True, demands=dnf.cli.demand.DemandSheet())

    def read_mock_comps(self, seed_persistor=True):
        self._comps, self.group_persistor = mock_comps(seed_persistor)
        return self._comps

    def read_all_repos(self, repo_setopts=None):
        pass


class BaseCliStub(_BaseStubMixin, dnf.cli.cli.BaseCli):
    """A class mocking `dnf.cli.cli.BaseCli`."""

    def __init__(self, *extra_repos):
        """Initialize the base."""
        super(BaseCliStub, self).__init__(*extra_repos)
        self.output.term = MockTerminal()

class HistoryStub(dnf.yum.history.YumHistory):
    """Stub of dnf.yum.history.YumHistory for easier testing."""

    def __init__(self):
        """Initialize a stub instance."""
        self.old_data_pkgs = {}

    def _old_data_pkgs(self, tid, sort=True):
        """Get packages of a transaction."""
        if sort:
            raise NotImplementedError('sorting not implemented yet')
        return self.old_data_pkgs.get(tid, ())[:]

    def close(self):
        """Close the history."""
        pass

    def old(self, tids=[], limit=None, *_args, **_kwargs):
        """Get transactions with given IDs."""
        create = lambda tid: dnf.yum.history.YumHistoryTransaction(self,
            (int(tid), 0, '0:685cc4ac4ce31b9190df1604a96a3c62a3100c35',
             1, '1:685cc4ac4ce31b9190df1604a96a3c62a3100c36', 0, 0))

        sorted_all_tids = sorted(self.old_data_pkgs.keys(), reverse=True)

        trxs = (create(tid) for tid in tids or sorted_all_tids
                if tid in self.old_data_pkgs)
        limited = trxs if limit is None else itertools.islice(trxs, limit)
        return tuple(limited)

class MockOutput(object):
    def __init__(self):
        self.term = MockTerminal()

    def setup_progress_callbacks(self):
        return (None, None)

class MockPackage(object):
    def __init__(self, nevra, repo=None):
        self.baseurl = None
        self.chksum = (None, None)
        self.downloadsize = None
        self.header = None
        self.location = '%s.rpm' % nevra
        self.repo = repo
        self.reponame = None if repo is None else repo.id
        self.str = nevra
        self.buildtime = 0
        (self.name, self.epoch, self.version, self.release, self.arch) = \
            hawkey.split_nevra(nevra)
        self.evr = '%(epoch)d:%(version)s-%(release)s' % vars(self)
        self.pkgtup = (self.name, self.arch, str(self.epoch), self.version,
                       self.release)

    def __str__(self):
        return self.str

    def localPkg(self):
        return os.path.join(self.repo.pkgdir, os.path.basename(self.location))

    def returnIdSum(self):
        return self.chksum

class MockRepo(dnf.repo.Repo):
    def valid(self):
        return None

class MockTerminal(object):
    def __init__(self):
        self.MODE = {'bold'   : '', 'normal' : ''}
        self.columns = 80
        self.reinit = mock.Mock()

class TestSack(hawkey.test.TestSackMixin, dnf.sack.Sack):
    def __init__(self, repo_dir, base):
        hawkey.test.TestSackMixin.__init__(self, repo_dir)
        dnf.sack.Sack.__init__(self,
                               arch=hawkey.test.FIXED_ARCH,
                               pkgcls=dnf.package.Package,
                               pkginitval=base,
                               make_cache_dir=True)

class MockBase(_BaseStubMixin, dnf.Base):
    """A class mocking `dnf.Base`."""

def mock_sack(*extra_repos):
    return MockBase(*extra_repos).sack

class MockYumDB(mock.Mock):
    def __init__(self):
        super(mock.Mock, self).__init__()
        self.db = {}

    def get_package(self, pkg):
        return self.db.setdefault(str(pkg), mock.Mock())

    def assertLength(self, length):
        assert len(self.db) == length

class RPMDBAdditionalDataPackageStub(dnf.yum.rpmsack.RPMDBAdditionalDataPackage):

    """A class mocking `dnf.yum.rpmsack.RPMDBAdditionalDataPackage`."""

    def __init__(self):
        """Initialize the data."""
        super(RPMDBAdditionalDataPackageStub, self).__init__(None, None, None)

    def __iter__(self, show_hidden=False):
        """Return a new iterator over the data."""
        for item in self._read_cached_data:
            yield item

    def _attr2fn(self, attribute):
        """Convert given *attribute* to a filename."""
        raise NotImplementedError('the method is not supported')

    def _delete(self, attribute):
        """Delete the *attribute* value."""
        try:
            del self._read_cached_data[attribute]
        except KeyError:
            raise AttributeError("Cannot delete attribute %s on %s " %
                                 (attribute, self))

    def _read(self, attribute):
        """Read the *attribute* value."""
        if attribute in self._read_cached_data:
            return self._read_cached_data[attribute]
        raise AttributeError("%s has no attribute %s" % (self, attribute))

    def _write(self, attribute, value):
        """Write the *attribute* value."""
        self._auto_cache(attribute, value, None)

    def clean(self):
        """Purge out everything."""
        for item in self.__iter__(show_hidden=True):
            self._delete(item)


class FakeConf(object):
    def __init__(self):
        self.assumeyes = None
        self.best = False
        self.cachedir = dnf.const.TMPDIR
        self.clean_requirements_on_remove = False
        self.color = 'never'
        self.color_update_installed = 'normal'
        self.color_update_remote = 'normal'
        self.color_list_available_downgrade = 'dim'
        self.color_list_available_install = 'normal'
        self.color_list_available_reinstall = 'bold'
        self.color_list_available_upgrade = 'bold'
        self.color_list_installed_extra = 'bold'
        self.color_list_installed_newer = 'bold'
        self.color_list_installed_older = 'bold'
        self.color_list_installed_reinstall = 'normal'
        self.color_update_local = 'bold'
        self.commands = []
        self.debug_solver = False
        self.debuglevel = 8
        self.defaultyes = False
        self.disable_excludes = []
        self.exclude = []
        self.include = []
        self.history_record = False
        self.installonly_limit = 0
        self.installonlypkgs = ['kernel']
        self.installroot = '/'
        self.ip_resolve = None
        self.multilib_policy = 'best'
        self.obsoletes = True
        self.persistdir = '/should-not-exist-bad-test/persist'
        self.plugins = False
        self.showdupesfromrepos = False
        self.tsflags = []
        self.verbose = False
        self.substitutions = {'releasever' : 'Fedora69'}

    @property
    def releasever(self):
        return self.substitutions['releasever']

class FakePersistor(object):
    def get_expired_repos(self):
        return set()

    def reset_last_makecache(self):
        pass

    def since_last_makecache(self):
        return None

class MockGroupPersistor(dnf.persistor.GroupPersistor):
    """Empty persistor that doesn't need any I/O."""
    def __init__(self):
        self.db = self._empty_db()


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


class ResultTestCase(TestCase):

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
