import sys
import unittest

# Adjust path so we can see the src modules running from branch as well
# as test dir:
sys.path.insert(0, '../../')
sys.path.insert(0, '../')
sys.path.insert(0, './')

new_behavior = "--new_behavior" in sys.argv
sys.argv = filter("--new_behavior".__ne__, sys.argv)

from yum import YumBase
from yum import transactioninfo
from yum import packages
from yum import packageSack
from yum.constants import TS_INSTALL_STATES, TS_REMOVE_STATES
from cli import YumBaseCli
import inspect

#############################################################
### Helper classes ##########################################
#############################################################

class FakeConf(object):

    def __init__(self):
        self.installonlypkgs = []
        self.exclude = []
        self.debuglevel = 0
        self.obsoletes = True
        self.exactarch = False
        self.exactarchlist = []
        self.installroot = '/'
        self.tsflags = []
        self.installonly_limit = 0

class FakeRepo(object):

    def __init__(self, id=None):
        self.id = id

class FakePackage(packages.YumAvailablePackage):

    def __init__(self, name, version, release, epoch, arch, repo=None):
        if repo is None:
            repo = FakeRepo()
        packages.YumAvailablePackage.__init__(self, repo)

        self.name = name
        self.version = version
        self.ver = version
        self.release = release
        self.rel = release
        self.epoch = epoch
        self.arch = arch

        self.prco['provides'].append((name, 'EQ', (epoch, version, release)))

        # Just a unique integer
        self.id = self.__hash__()

    def addProvides(self, name, flag=None, evr=(None, None, None)):
        self.prco['provides'].append((name, flag, evr))
    def addRequires(self, name, flag=None, evr=(None, None, None)):
        self.prco['requires'].append((name, flag, evr))
    def addConflicts(self, name, flag=None, evr=(None, None, None)):
        self.prco['conflicts'].append((name, flag, evr))
    def addObsoletes(self, name, flag=None, evr=(None, None, None)):
        self.prco['obsoletes'].append((name, flag, evr))
    def addFile(self, name, ftype='file'):
        self.files[ftype].append(name)


class TestingDepsolve(YumBase):

    def __init__(self, tsInfo, rpmdb, pkgSack):
        YumBase.__init__(self)

        self.conf = FakeConf()
        self.tsInfo = tsInfo
        self._tsInfo = tsInfo
        self.rpmdb = rpmdb
        self.pkgSack = pkgSack

    def getInstalledPackageObject(self, pkgtup):
        return self.rpmdb.searchNevra(pkgtup[0], pkgtup[2], pkgtup[3],
                pkgtup[4], pkgtup[1])[0]


def build_depsolver(tsInfo, rpmdb=None, pkgSack=None):
    if rpmdb is None:
        rpmdb   = packageSack.PackageSack()
    if pkgSack is None:
        pkgSack = packageSack.PackageSack()
    # XXX this side-affect is hacky:
    tsInfo.setDatabases(rpmdb, pkgSack)

    solver = TestingDepsolve(tsInfo, rpmdb, pkgSack)
    return solver

class _Container(object):
    pass


#######################################################################
### Abstract super class for test cases ###############################
#######################################################################

class _DepsolveTestsBase(unittest.TestCase):

    res = {0 : 'empty', 2 : 'ok', 1 : 'err'}

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self.pkgs = _Container()
        self.buildPkgs(self.pkgs)

    @staticmethod
    def buildPkgs(pkgs, *args):
        """Overload this staticmethod to create pkpgs that are used in several
        test cases. It gets called from __init__ with self.pkgs as first parameter.
        It is a staticmethod so you can call .buildPkgs() from other Tests to share
        buildPkg code (inheritance doesn't work here, because we don't want to
        inherit the test cases, too).
        """
        pass

    def assertResult(self, pkgs, optional_pkgs=[]):
        """Check if "system" contains the given pkgs. pkgs must be present,
        optional_pkgs may be. Any other pkgs result in an error. Pkgs are
        present if they are in the rpmdb and are not REMOVEd or they
        are INSTALLed.
        """
        errors = ["Unexpected result after depsolving: \n\n"]
        pkgs = set(pkgs)
        optional_pkgs = set(optional_pkgs)
        installed = set()

        for pkg in self.rpmdb:
            # got removed
            if self.tsInfo.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES):
                if pkg in pkgs:
                    errors.append("Package %s was removed!\n" % pkg)
            else: # still installed
                if pkg not in pkgs and pkg not in optional_pkgs:
                    errors.append("Package %s was not removed!\n" % pkg)
            installed.add(pkg)

        for txmbr in self.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            installed.add(txmbr.po)
            if txmbr.po not in pkgs and txmbr.po not in optional_pkgs:
                errors.append("Package %s was installed!\n" % txmbr.po)
        for pkg in pkgs - installed:
            errors.append("Package %s was not installed!\n" % pkg)

        if len(errors) > 1:
            errors.append("\nTest case was:\n\n")
            errors.extend(inspect.getsource(inspect.stack()[1][0].f_code))
            errors.append("\n")
            self.fail("".join(errors))


#######################################################################
### Derive Tests from these classes or unittest.TestCase ##############
#######################################################################

class DepsolveTests(_DepsolveTestsBase):
    """Run depsolver on an manually  set up transaction.
    You can add pkgs to self.rpmdb or self.tsInfo. See
    yum/transactioninfo.py for details.
    A typical test case looks like:

    def testInstallPackageRequireInstalled(self):
        po = FakePackage('zsh', '1', '1', None, 'i386')
        po.addRequires('zip', 'EQ', (None, '1.3', '2'))
        self.tsInfo.addInstall(po)

        ipo = FakePackage('zip', '1.3', '2', None, 'i386')
        self.rpmdb.addPackage(ipo)

        result, msg = self.resolveCode()
        self.assertEquals('ok', result, msg)
        self.assertResult((po, ipo))
    """

    def setUp(self):
        """ Called at the start of each test. """
        self.tsInfo = transactioninfo.TransactionData()
        self.rpmdb  = packageSack.PackageSack()
        self.xsack  = packageSack.PackageSack()
        self.repo   = FakeRepo("installed")

    def FakeInstPkg(self, name, version, release, epoch, arch):
        return FakePackage(name, version, release, epoch, arch, self.repo)

    def resolveCode(self):
        solver = build_depsolver(self.tsInfo, self.rpmdb, self.xsack)
        result, msg = solver.resolveDeps()
        return (self.res[result], msg)

class OperationsTests(_DepsolveTestsBase):
    """Run a yum command (install, update, remove, ...) in a given set of installed
    and available pkgs. Typical test case looks like:

    def testUpdate(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed], [p.update])
        self.assert_(res=='ok', msg)
        self.assertResult((p.update,))

    To avoid creating the same pkgs over and over again overload the staticmethod
    buildPkgs. It gets called from __init__ with self.pkgs as first parameter.
    As it is a static method you can call .buildPkgs() from other Tests to share
    buildPkg code.
    """

    def runOperation(self, args, installed=[], available=[]):
        """Sets up and runs the depsolver. args[0] must be a valid yum command
        ("install", "update", ...). It might be followed by pkg names as on the
        yum command line. The pkg objects in installed are added to self.rpmdb and
        those in available to self.xsack which is the repository to resolve
        requirements from.
        """
        depsolver = YumBaseCli()
        self.rpmdb = depsolver.rpmdb = packageSack.PackageSack()
        self.xsack = depsolver._pkgSack  = packageSack.PackageSack()
        self.repo = depsolver.repo = FakeRepo("installed")
        depsolver.conf = FakeConf()
        depsolver.doLoggingSetup(-1, -1)
        self.depsolver = depsolver

        for po in installed:
            po.repoid = po.repo.id = "installed"
            self.depsolver.rpmdb.addPackage(po)
        for po in available:
            self.depsolver._pkgSack.addPackage(po)

        self.depsolver.basecmd = args[0]
        self.depsolver.extcmds = args[1:]
        res, msg = self.depsolver.doCommands()
        self.tsInfo = depsolver.tsInfo
        if res!=2:
            return res, msg
        res, msg = self.depsolver.buildTransaction()
        return self.res[res], msg
