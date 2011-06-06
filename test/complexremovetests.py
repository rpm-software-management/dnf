from testbase import *

class ComplexRemoveTests(OperationsTests):
    # Three testcases. A -> B means that B requires A. 
    # 1) 0 -> L1 -> (R1 -> R2, L2 -> L3) where everything but L3 was 
    # dep-installed (removing L3 should remove everything);
    # 2) 0 -> L1 -> (R1 -> R2, L2 -> L3) where everything but L3 and R2 was 
    # dep-installed (removing L3 should only remove L3 and L2);
    # 3) C1 <--> C2 -> C3 where C1 and C2 were dep-installed (removing 
    # C3 should remove everything)
    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.node0 = FakePackage('foo', '2.5', '1.1', '0', 'noarch')
        pkgs.node0.addFile('/bin/foo')
        pkgs.node0.yumdb_info.reason = 'dep'
        
        pkgs.lnode1 = FakePackage('bar1', '1.0')
        pkgs.lnode1.addRequires('foo')
        pkgs.lnode1.addRequiresPkg(pkgs.node0)
        pkgs.node0.addRequiringPkg(pkgs.lnode1)
        pkgs.lnode1.yumdb_info.reason = 'dep'
        
        pkgs.lnode2 = FakePackage('bar2', '1.0')
        pkgs.lnode2.addRequires('bar1')
        pkgs.lnode2.addRequiresPkg(pkgs.lnode1)
        pkgs.lnode1.addRequiringPkg(pkgs.lnode2)
        pkgs.lnode2.yumdb_info.reason = 'dep'
        
        pkgs.lnode3 = FakePackage('bar3', '1.0')
        pkgs.lnode3.addRequires('bar2')
        pkgs.lnode3.addRequiresPkg(pkgs.lnode2)
        pkgs.lnode2.addRequiresPkg(pkgs.lnode3)
        pkgs.lnode3.yumdb_info.reason = 'user'

        pkgs.rnode1 = FakePackage('baz1', '1.0')
        pkgs.rnode1.addRequires('bar1')
        pkgs.rnode1.addRequiresPkg(pkgs.lnode1)
        pkgs.lnode1.addRequiringPkg(pkgs.rnode1)
        pkgs.rnode1.yumdb_info.reason = 'dep'
        
        pkgs.rnode2 = FakePackage('baz2', '1.0')
        pkgs.rnode2.addRequires('baz1')
        pkgs.rnode2.addRequiresPkg(pkgs.rnode1)
        pkgs.rnode1.addRequiringPkg(pkgs.rnode2)
        pkgs.rnode2.yumdb_info.reason = 'dep'

        pkgs.cycle1 = FakePackage('cycle1', '1.0')
        pkgs.cycle1.yumdb_info.reason = 'dep'

        pkgs.cycle2 = FakePackage('cycle2', '1.0')
        pkgs.cycle2.yumdb_info.reason = 'dep'

        pkgs.cycle3 = FakePackage('cycle3', '1.0')
        pkgs.cycle3.yumdb_info.reason = 'user'


        pkgs.cycle1.addRequires('cycle2')
        pkgs.cycle1.addRequiresPkg(pkgs.cycle2)
        pkgs.cycle2.addRequiringPkg(pkgs.cycle1)

        pkgs.cycle2.addRequires('cycle1')
        pkgs.cycle2.addRequiringPkg(pkgs.cycle1)
        pkgs.cycle1.addRequiringPkg(pkgs.cycle2)

        pkgs.cycle3.addRequires('cycle2')
        pkgs.cycle3.addRequiresPkg(pkgs.cycle2)
        pkgs.cycle2.addRequiringPkg(pkgs.cycle3)

    def testRemoveCycle(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'cycle3'], [p.cycle1, p.cycle2, p.cycle3], [])
        self.assertResult( () )

    def testRemoveTree(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'bar3'], [p.node0, p.lnode1, p.lnode2, p.lnode3, p.rnode1, p.rnode2], [])
        self.assertResult( () )

    def testRemoveNeededRevdeps(self):
        p = self.pkgs
        p.rnode2.yumdb_info.reason = 'user'
        res, msg = self.runOperation(['remove', 'bar3'], [p.node0, p.lnode1, p.lnode2, p.lnode3, p.rnode1, p.rnode2], [])
        p.rnode2.yumdb_info.reason = 'dep'
        self.assertResult( (p.node0, p.lnode1, p.rnode1, p.rnode2) )

