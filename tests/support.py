# Copyright (C) 2012-2013  Red Hat, Inc.
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
from sys import version_info as python_version
try:
    from unittest import mock
except ImportError:
    from tests import mock
import io
import contextlib
import dnf
import dnf.comps
import dnf.exceptions
import dnf.package
import dnf.repo
import dnf.sack
import dnf.yum.constants
import gettext
import hawkey
import hawkey.test
import itertools
import os
import unittest
from functools import reduce

skip = unittest.skip

RPMDB_CHECKSUM = 'b3fa9f5ed659fa881ac901606be5e8f99ca55cc3'
TOTAL_RPMDB_COUNT = 5
SYSTEM_NSOLVABLES = TOTAL_RPMDB_COUNT
MAIN_NSOLVABLES = 9
UPDATES_NSOLVABLES = 4
AVAILABLE_NSOLVABLES = MAIN_NSOLVABLES + UPDATES_NSOLVABLES
TOTAL_GROUPS = 3
TOTAL_NSOLVABLES = SYSTEM_NSOLVABLES + AVAILABLE_NSOLVABLES

# testing infrastructure

def dnf_toplevel():
    return os.path.normpath(os.path.join(__file__, "../../"))

def repo(reponame):
    return os.path.join(repo_dir(), reponame)

def repo_dir():
    this_dir=os.path.dirname(__file__)
    return os.path.join(this_dir, "repos")

COMPS_PATH = os.path.join(repo_dir(), "main_comps.xml")
NONEXISTENT_FILE = os.path.join(dnf_toplevel(), "does-not/exist")
TOUR_44_PKG_PATH = os.path.join(repo_dir(), "rpm/tour-4-4.noarch.rpm")
TOUR_50_PKG_PATH = os.path.join(repo_dir(), "rpm/tour-5-0.noarch.rpm")
TOUR_51_PKG_PATH = os.path.join(repo_dir(), "rpm/tour-5-1.noarch.rpm")
USER_RUNDIR = '/tmp/dnf-user-rundir'

# often used query

def installed_but(sack, *args):
    q = sack.query().filter(reponame__eq=hawkey.SYSTEM_REPO_NAME)
    return reduce(lambda query, name: query.filter(name__neq=name), args, q)

# patching objects

@contextlib.contextmanager
def patch_std_streams():
    with mock.patch('sys.stdout', new_callable=io.StringIO) as stdout, \
            mock.patch('sys.stderr', new_callable=io.StringIO) as stderr:
        yield (stdout, stderr)

def patch_translation(gettexts=(), ngettexts=(), translation=None):
    """Return function wrapper patching the translating functions."""
    translation = translation or dnf.pycomp.NullTranslations()
    try:
        gettext = translation.ugettext
        ngettext = translation.ungettext
    except AttributeError:
        gettext = lambda message: translation.get(message, message)
        ngettext = (lambda msgid1, msgid2, n:
                    translation.get((msgid1, int(n != 1)),
                                    msgid1 if n == 1 else msgid2))

    def wrap(function):
        """Wrap the function patching the translating functions."""
        for target in gettexts:
            function = mock.patch(target, gettext)(function)
        for target in ngettexts:
            function = mock.patch(target, ngettext)(function)
        return function

    return wrap

# mock objects

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
    _cli_confirm_gpg_key_import = None

    def __init__(self):
        self.term = MockTerminal()

    def setup_progress_callbacks(self):
        return (None, None)

class MockPackage(object):
    def __init__(self, nevra, repo=None):
        self.header = None
        self.location = '%s.rpm' % nevra
        self.baseurl = None
        self.repo = repo
        self.reponame = None if repo is None else repo.id
        self.str = nevra
        (self.name, self.epoch, self.version, self.release, self.arch) = \
            hawkey.split_nevra(nevra)
        self.evr = '%(epoch)d:%(version)s-%(release)s' % vars(self)
        self.pkgtup = (self.name, self.arch, str(self.epoch), self.version,
                       self.release)

    def __str__(self):
        return self.str

    def localPkg(self):
        return os.path.join(self.repo.pkgdir, os.path.basename(self.location))

class MockRepo(dnf.repo.Repo):
    def valid(self):
        return None

class MockTerminal(object):
    def __init__(self):
        self.MODE = {'bold'   : '', 'normal' : ''}
        self.columns = 80
        self.reinit = mock.Mock()

class TestSack(hawkey.test.TestSackMixin, dnf.sack.Sack):
    def __init__(self, repo_dir, yumbase):
        hawkey.test.TestSackMixin.__init__(self, repo_dir)
        dnf.sack.Sack.__init__(self,
                               arch=hawkey.test.FIXED_ARCH,
                               pkgcls=dnf.package.Package,
                               pkginitval=yumbase,
                               make_cache_dir=True)

class MockBase(dnf.Base):
    """ See also: hawkey/test/python/__init__.py.

        Note that currently the used TestSack has always architecture set to
        "x86_64". This is to get the same behavior when running unit tests on
        different arches.
    """
    def __init__(self, *extra_repos):
        super(MockBase, self).__init__()
        for r in extra_repos:
            repo = MockRepo(r, None)
            repo.enable()
            self._repos.add(repo)

        self._conf = FakeConf()
        self._persistor = FakePersistor()
        self._yumdb = MockYumDB()
        self.ds_callback = mock.Mock()

    @property
    def sack(self):
        if self._sack:
            return self._sack
        return self.init_sack()

    def activate_persistor(self):
        pass

    def init_sack(self):
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a Base reference.
        self._sack = TestSack(repo_dir(), self)
        self._sack.load_system_repo()
        for repo in self.repos.iter_enabled():
            fn = "%s.repo" % repo.id
            self._sack.load_test_repo(repo.id, fn)

        self._sack.configure(self.conf.installonlypkgs)
        self._goal = hawkey.Goal(self._sack)
        return self._sack

    def close(self):
        pass

    def mock_cli(self):
        return mock.Mock('base', base=self)

    def read_mock_comps(self, fn):
        comps = dnf.comps.Comps()
        comps.add_from_xml_filename(fn)
        comps.compile(self.sack.query().installed())
        self._comps = comps
        return comps

    def read_all_repos(self):
        pass

def mock_sack(*extra_repos):
    return MockBase(*extra_repos).sack

class MockYumDB(mock.Mock):
    def __init__(self):
        super(mock.Mock, self).__init__()
        self.db = {}

    def get_package(self, po):
        return self.db.setdefault(str(po), mock.Mock())

    def assertLength(self, length):
        assert(len(self.db) == length)

# mock object taken from testbase.py in yum/test:
class FakeConf(object):
    def __init__(self):
        self.assumeyes = None
        self.best = False
        self.cachedir = dnf.const.TMPDIR
        self.clean_requirements_on_remove = False
        self.color = 'never'
        self.color_update_installed = 'normal'
        self.color_update_remote = 'normal'
        self.color_list_available_install = 'normal'
        self.commands = []
        self.debug_solver = False
        self.debuglevel = 8
        self.defaultyes = False
        self.disable_excludes = []
        self.exclude = []
        self.groupremove_leaf_only = False
        self.history_record = False
        self.installonly_limit = 0
        self.installonlypkgs = ['kernel']
        self.installroot = '/'
        self.multilib_policy = 'best'
        self.obsoletes = True
        self.persistdir = '/should-not-exist-bad-test/persist'
        self.protected_multilib = False
        self.protected_packages = []
        self.showdupesfromrepos = False
        self.tsflags = []
        self.verbose = False
        self.yumvar = {'releasever' : 'Fedora69'}

class FakePersistor(object):
    def get_expired_repos(self):
        return set()

    def reset_last_makecache(self):
        pass

    def since_last_makecache(self):
        return None

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
            attrs_str = ', '.join('%s: %s' % (str(attr), repr(value))
                                  for attr, value in self._attrs.items())
            args_strs.append('attrs={%s}' % attrs_str)

        return '%s(%s)' % (type(self).__name__, ", ".join(args_strs))

# test cases

if python_version.major < 3:
    class PycompTestCase(unittest.TestCase):
        pass
else:
    class PycompTestCase(unittest.TestCase):
        def assertItemsEqual(self, item1, item2):
            super().assertCountEqual(item1, item2)

class TestCase(PycompTestCase):
    def assertFile(self, path):
        """Assert the given path is a file."""
        return self.assertTrue(os.path.isfile(path))

    def assertLength(self, collection, length):
        return self.assertEqual(len(collection), length)

    def assertPathDoesNotExist(self, path):
        return self.assertFalse(os.access(path, os.F_OK))

    def assertStartsWith(self, string, what):
        return self.assertTrue(string.startswith(what))

class ResultTestCase(TestCase):
    def _get_installed(self, base):
        try:
            base.resolve()
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

        self.assertItemsEqual(self._get_installed(base), pkgs)

    def installed_removed(self, base):
        try:
            base.resolve()
        except dnf.exceptions.DepsolveError:
            self.fail()

        installed = base._transaction.install_set
        removed = base._transaction.remove_set
        return installed, removed
