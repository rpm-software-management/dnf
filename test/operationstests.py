from testbase import *
from simpleobsoletestests import SimpleObsoletesTests

# Obsolete for conflict
class ComplicatedTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        SimpleObsoletesTests.buildPkgs(pkgs)
        # conflicts
        pkgs.conflicts = FakePackage('super-zippy', '0.3', '1', '0', 'i386')
        pkgs.conflicts.addConflicts('zsh', 'EQ', ('0', '1', '1'))

    def testObsoleteForConflict(self):
        p = self.pkgs
        res, msg = self.runOperation(['install', 'super-zippy'], [p.installed_i386], [p.obsoletes_i386, p.obsoletes_x86_64, p.conflicts])
        if new_behavior:
            self.assert_(res=='ok', msg)
            self.assertResult((p.obsoletes_i386, p.conflicts))

class ComplicatedObsoletesTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.installed = FakePackage('foo', '1.4', '1')
        pkgs.obsoletecircle = FakePackage('foo', '1.4', '1')
        pkgs.obsoletecircle.addObsoletes('baz')
        pkgs.obsoletes = FakePackage('bar', '1.2', '1')
        pkgs.obsoletes.addObsoletes('foo')
        pkgs.obsoletes2 = FakePackage('baz', '1.8', '1')
        pkgs.obsoletes2.addObsoletes('bar')

    def testObsoleteChain(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.installed], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes2,))
        else:
            self.assertResult((p.obsoletes,))
    def testObsoleteChainNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes], [p.obsoletes2])
        self.assert_(res=='ok', msg)
        self.assertResult((p.obsoletes2,))

    def testObsoleteCircle(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletecircle], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletecircle,))
        else:
            self.assertResult((p.obsoletes,))
    def testObsoleteCircleNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes], [p.obsoletecircle, p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes,))
        else:
            self.assertResult((p.obsoletes2,))
    def testObsoleteCircleNextNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletes2], [p.obsoletecircle, p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletes2,))
        else:
            self.assertResult((p.obsoletecircle,))
    def testObsoleteCircleNextNextNext(self):
        p = self.pkgs
        res, msg = self.runOperation(['update'], [p.obsoletecircle], [p.obsoletes, p.obsoletes2])
        self.assert_(res=='ok', msg)
        if new_behavior:
            self.assertResult((p.obsoletecircle,))
        else:
            self.assertResult((p.obsoletes,))
    # continue endlessly

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ComplicatedObsoletesTests))
    suite.addTest(unittest.makeSuite(ComplicatedTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

