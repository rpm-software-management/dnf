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

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ComplicatedTests))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")

