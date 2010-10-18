from testbase import *

class SimpleRemoveTests(OperationsTests):

    @staticmethod
    def buildPkgs(pkgs, *args):
        pkgs.leaf = FakePackage('foo', '2.5', '1.1', '0', 'noarch')
        pkgs.leaf.addFile('/bin/foo')

        pkgs.requires_leaf = FakePackage('bar', '4')
        pkgs.requires_leaf.addRequires('foo')

        pkgs.requires_file = FakePackage('barkeeper', '0.8')
        pkgs.requires_file.addRequires('/bin/foo')

        pkgs.rr_leaf = FakePackage('baz', '5.3')
        pkgs.rr_leaf.addRequires('bar')

        pkgs.provides_leaf = FakePackage('foo-ng', '2.5')
        pkgs.provides_leaf.addProvides('foo')

    def testRemoveSingle(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf], [])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testRemoveRequired(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf, p.requires_leaf], [])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testRemoveRequiredMissing(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'bar'], [p.requires_leaf], [])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testRemoveRequiredProvided(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf, p.requires_leaf, p.provides_leaf], [])
        self.assert_(res=='ok', msg)
        self.assertResult( (p.requires_leaf, p.provides_leaf) )

    def testRemoveRequiredAvailable(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf, p.requires_leaf], [p.provides_leaf])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testRemoveRequiredChain(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf, p.requires_leaf, p.rr_leaf], [])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testRemoveRequiredFile(self):
        p = self.pkgs
        res, msg = self.runOperation(['remove', 'foo'], [p.leaf, p.requires_file], [])
        self.assert_(res=='ok', msg)
        self.assertResult( () )

    def testShellUpRm1(self):
        """ Do an update for a package, and then rm it. """
        pi1 = FakePackage('foo', '1', '1', '0', 'x86_64')

        pa1 = FakePackage('foo', '2', '1', '0', 'x86_64')

        res, msg = self.runOperation((['update', 'foo'],
                                      ['remove', 'foo'],
                                      ),
                                     [pi1],
                                     [pa1], multi_cmds=True)
        self.assert_(res=='ok', msg)
        self.assertResult(())

    def testShellUpRm2(self):
        """ Do an update for a package, and then rm it. """
        pi1 = FakePackage('foo', '1', '1', '0', 'x86_64')
        pi2 = FakePackage('foo', '1', '1', '0', 'i686')

        pa1 = FakePackage('foo', '2', '1', '0', 'x86_64')
        pa2 = FakePackage('foo', '2', '1', '0', 'i686')

        res, msg = self.runOperation((['update', 'foo'],
                                      ['remove', 'foo.i686'],
                                      ),
                                     [pi1, pi2],
                                     [pa1, pa2], multi_cmds=True)
        self.assert_(res=='ok', msg)
        self.assertResult((pi1, ))

    def testShellUpRm3(self):
        """ Do an update for a package, and then rm it. """
        pi1 = FakePackage('foo', '1', '1', '0', 'x86_64')
        pi2 = FakePackage('foo', '1', '1', '0', 'i686')

        pa1 = FakePackage('foo', '2', '1', '0', 'x86_64')
        pa2 = FakePackage('foo', '2', '1', '0', 'i686')

        res, msg = self.runOperation((['update', 'foo'],
                                      ['remove', 'foo.x86_64'],
                                      ),
                                     [pi1, pi2],
                                     [pa1, pa2], multi_cmds=True)
        self.assert_(res=='ok', msg)
        self.assertResult((pi2, ))

    def testShellUpRm4(self):
        """ Do an update for a package, and then rm it. """
        pi1 = FakePackage('foo', '1', '1', '0', 'x86_64')
        pi2 = FakePackage('foo', '1', '1', '0', 'i686')

        pa1 = FakePackage('foo', '2', '1', '0', 'x86_64')
        pa2 = FakePackage('foo', '2', '1', '0', 'i686')

        res, msg = self.runOperation((['update', 'foo-2-1'],
                                      ['remove', 'foo.i686'],
                                      ),
                                     [pi1, pi2],
                                     [pa1, pa2], multi_cmds=True)
        self.assert_(res=='ok', msg)
        self.assertResult((pi1,))

