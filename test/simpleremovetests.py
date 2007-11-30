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
