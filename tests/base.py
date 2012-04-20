import dnf.package
import dnf.queries
import dnf.yum
import dnf.yum.constants
import hawkey.test
import os
import unittest

TOTAL_RPMDB_COUNT = 1
SYSTEM_NSOLVABLES = TOTAL_RPMDB_COUNT + 2
TOTAL_NSOLVABLES = 6

def repo(reponame):
    return os.path.join(repo_dir(), reponame)

def repo_dir():
    this_dir=os.path.dirname(__file__)
    return os.path.join(this_dir, "repos")

def mock_yum_base(*extra_repos):
    yumbase = MockYumBase()
    yumbase.conf = FakeConf()
    yumbase.tsInfo = dnf.yum.transactioninfo.TransactionData()

    yumbase.mock_extra_repos = extra_repos
    return yumbase

class MockYumBase(dnf.yum.YumBase):
    """ See also: hawkey/test/python/__init__.py """
    def _init_hawkey_sack(self):
        # Create the Sack, tell it how to build packages, passing in the Package
        # class and a YumBase reference.
        self._sack = hawkey.test.TestSack(repo_dir(), dnf.package.Package, self)
        self._sack.load_rpm_repo()
        for repo in self.mock_extra_repos:
            fn = "%s.repo" % repo
            self._sack.load_test_repo(repo, fn)

        return self._sack

class ResultTestCase(unittest.TestCase):

    # originally from testbase.py
    def assertResult(self, yumbase, pkgs):
        """ Check if "system" contains the given pkgs. pkgs must be present. Any
            other pkgs result in an error. Pkgs are present if they are in the
            rpmdb and are not REMOVEd or they are INSTALLed.
        """
        pkgs = set(pkgs)
        installed = set(dnf.queries.installed_by_name(yumbase.sack, None))

        for txmbr in yumbase.tsInfo.getMembersWithState(
            output_states=dnf.yum.constants.TS_REMOVE_STATES):
            installed.remove(txmbr.po)
        for txmbr in yumbase.tsInfo.getMembersWithState(
            output_states=dnf.yum.constants.TS_INSTALL_STATES):
            installed.add(txmbr.po)
        self.assertEqual(pkgs, installed)

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
        self.clean_requirements_on_remove = True
        self.upgrade_requirements_on_install = False
