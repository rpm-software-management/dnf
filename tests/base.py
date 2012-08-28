# Copyright (C) 2012  Red Hat, Inc.
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

import dnf.package
import dnf.queries
import dnf.sack
import dnf.yum
import dnf.yum.constants
import hawkey.test
import mock
import os
import unittest

TOTAL_RPMDB_COUNT = 3
SYSTEM_NSOLVABLES = TOTAL_RPMDB_COUNT
MAIN_NSOLVABLES = 6
UPDATES_NSOLVABLES = 1
AVAILABLE_NSOLVABLES = MAIN_NSOLVABLES + UPDATES_NSOLVABLES
TOTAL_NSOLVABLES = SYSTEM_NSOLVABLES + AVAILABLE_NSOLVABLES

# testing infrastructure

def repo(reponame):
    return os.path.join(repo_dir(), reponame)

def repo_dir():
    this_dir=os.path.dirname(__file__)
    return os.path.join(this_dir, "repos")

TOUR_44_PKG_PATH = os.path.join(repo_dir(), "tour-4-4.noarch.rpm")
TOUR_51_PKG_PATH = os.path.join(repo_dir(), "tour-5-1.noarch.rpm")

# often used query

def installed_but(sack, *args):
    q = hawkey.Query(sack).filter(repo__eq=hawkey.SYSTEM_REPO_NAME)
    return reduce(lambda query, name: query.filter(name__neq=name), args, q)

# mock objects

def create_mock_package(name, major_version):
    pkg = mock.Mock(spec_set=['pkgtup', 'name', 'reponame', 'repoid',
                              'arch', 'evr', 'state', 'reason'])
    pkg.name = name
    pkg.reponame = pkg.repoid = 'main'
    pkg.arch = 'noarch'
    pkg.evr = '%d-1' % major_version
    pkg.pkgtup = (pkg.name, pkg.arch, 0, str(major_version) , '1')
    return pkg

def mock_packages():
    return [create_mock_package("within%s" % chr(i), 2)
            for i in range(ord('A'), ord('I'))]

def mock_yum_base(*extra_repos):
    yumbase = MockYumBase()
    yumbase.conf = FakeConf()
    yumbase.tsInfo = dnf.yum.transactioninfo.TransactionData()
    yumbase.dsCallback = mock.Mock()
    yumbase.mock_extra_repos = extra_repos
    yumbase._yumdb = MockYumDB()
    return yumbase

class TestSack(hawkey.test.TestSackMixin, dnf.sack.Sack):
    def __init__(self, repo_dir, yumbase):
        hawkey.test.TestSackMixin.__init__(self, repo_dir)
        dnf.sack.Sack.__init__(self,
                               pkgcls=dnf.package.Package,
                               pkginitval=yumbase)

class MockYumBase(dnf.yum.YumBase):
    """ See also: hawkey/test/python/__init__.py.

        Note that currently the used TestSack has always architecture set to
        "x86_64". This is to get the same behavior when running unit tests on
        different arches.
    """
    @property
    def sack(self):
        if self._sack:
            return self._sack
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a YumBase reference.
        self._sack = TestSack(repo_dir(), self)
        self._sack.load_system_repo()
        for repo in self.mock_extra_repos:
            fn = "%s.repo" % repo
            self._sack.load_test_repo(repo, fn)

        return self._sack

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
        self.installonlypkgs = ['kernel']
        self.exclude = []
        self.debuglevel = 8
        self.obsoletes = True
        self.exactarch = False
        self.exactarchlist = []
        self.installroot = '/'
        self.tsflags = []
        self.installonly_limit = 0
        self.skip_broken = False
        self.disable_excludes = []
        self.multilib_policy = 'best'
        self.persistdir = '/should-not-exist-bad-test!'
        self.showdupesfromrepos = False
        self.uid = 0
        self.groupremove_leaf_only = False
        self.protected_packages = []
        self.protected_multilib = False
        self.clean_requirements_on_remove = False
        self.upgrade_requirements_on_install = False
        self.yumvar = {'releasever' : 'Fedora69'}
        self.history_record = False

# specialized test cases

class ResultTestCase(unittest.TestCase):

    # originally from testbase.py
    def assertResult(self, yumbase, pkgs):
        """ Check if "system" contains the given pkgs. pkgs must be present. Any
            other pkgs result in an error. Pkgs are present if they are in the
            rpmdb and are not REMOVEd or they are INSTALLed.
        """
        installed = set(dnf.queries.installed_by_name(yumbase.sack, None))

        (rcode, rstring) = yumbase.buildTransaction()
        self.assertNotEqual(rcode, 1)

        for txmbr in yumbase.tsInfo.getMembersWithState(
            output_states=dnf.yum.constants.TS_REMOVE_STATES):
            installed.remove(txmbr.po)
        for txmbr in yumbase.tsInfo.getMembersWithState(
            output_states=dnf.yum.constants.TS_INSTALL_STATES):
            installed.add(txmbr.po)
        self.assertItemsEqual(installed, pkgs)
