import unittest
import logging
import sys
from testbase import *

class SkipBrokenTests(DepsolveTests):
    ''' Test cases to test skip-broken'''
    
    def setUp(self):
        DepsolveTests.setUp(self)
        self.xrepo = FakeRepo("TestRepository", self.xsack)
        setup_logging()

    def repoPackage(self, name, version='1', release='0', epoch='0', arch='noarch'):
        po = FakePackage(name, version, release, epoch, arch, repo=self.xrepo)
        self.xsack.addPackage(po)
        return po
    
    def instPackage(self, name, version='1', release='0', epoch='0', arch='noarch'):
        po = FakePackage(name, version, release, epoch, arch, repo=self.repo)
        self.rpmdb.addPackage(po)
        return po
           
    def testMissingReqNoSkip(self):
        ''' install fails,  because of missing req.
        bar fails because foobar is not provided '''
        po = self.repoPackage('foo', '1')
        po.addRequires('bar', None, (None,None,None))
        self.tsInfo.addInstall(po)

        xpo = self.repoPackage('bar', '1')
        xpo.addRequires('foobar', None, (None,None,None))
        
        self.assertEquals('err', *self.resolveCode(skip=False))
        self.assertResult((po,xpo))

    def testMissingReqSkip(self):
        ''' install is skipped, because of missing req.
        foo + bar is skipped, because foobar is not provided '''
        po = self.repoPackage('foo', '1')
        po.addRequires('bar', None, (None,None,None))
        self.tsInfo.addInstall(po)

        xpo = self.repoPackage('bar', '1')
        xpo.addRequires('foobar', None, (None,None,None))

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([])

    def testDepWithMissingReqSkip(self):
        ''' install is skipped, beacuse dep is missing req.  
        foo + foobar is skipped because barfoo is not provided
        bar stays in the transaction
        '''
        po1 = self.repoPackage('foo', '1')
        po1.addRequires('foobar', None, (None,None,None))
        self.tsInfo.addInstall(po1)

        po2 = self.repoPackage('bar', '1')
        self.tsInfo.addInstall(po2)

        xpo1 = self.repoPackage('foobar', '1')
        xpo1.addRequires('barfoo', None, (None,None,None))

        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([po2])

    def testUpdateOldRequired(self):
        ''' update breaking req. of installed package is skipped
        foo-1.0 -> foo-2.0 breaks the installed foo-tools needing foo-1.0
        so skip the update and we have and empty transaction 
        '''
        # FIXME: The right solution is to skip the update from the transaction 
        
        po1 = self.instPackage('foo', '1')
        po2 = self.repoPackage('foo', '2')

        ipo = self.instPackage('foo-tools', '2.5')
        ipo.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testUpdateRequireOld(self):
        '''update with missing req. is skipped
        The foo-1.0 -> foo-2.0 update fails, because foo-tools-2.0 need by foo-2.0
        is not provided, the update should be skipped and result in a empty transaction
        '''
        po1 = self.instPackage('foo', '1')
        po1.addRequires('foo-tools', 'EQ', ('0', '1', '0'))
        po2 = self.repoPackage('foo', '2')
        po2.addRequires('foo-tools', 'EQ', ('0', '2', '0'))

        ipo = self.instPackage('foo-tools', '1')

        self.tsInfo.addUpdate(po2, oldpo=po1)

        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testUpdateRequireBoth(self):
        ''' install + update skipped, because of missing req.
        foo-1.0 -> foo-2.0 update, fails because foo-tools-2.0, needed by foo-2.0 is not provided.
        foo-2.0 update get skip, and the foo-gui install will get skipped too, because it need foo-2.0
        there is not longer provided.
        '''
        po1 = self.instPackage('foo', '1')
        po1.addRequires('foo-tools', 'EQ', ('0', '1', '0'))
        po2 = self.repoPackage('foo', '2')
        po2.addRequires('foo-tools', 'EQ', ('0', '2', '0'))

        ipo = self.instPackage('foo-tools', '1')
        por =  self.repoPackage('foo-gui', '1')
        por.addRequires('foo', 'EQ', ('0', '2', '0'))

        self.tsInfo.addUpdate(po2, oldpo=po1)
        self.tsInfo.addInstall(por)

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testEraseDep(self):
        ''' remove a package that someone depends on
        foo is removed, and foo-tools get removed too, because it 
        depends on foo  
        '''
        ipo = self.instPackage('foo', '1')
        ipo2 = self.instPackage('foo-tools', '1')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addErase(ipo)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([])

    def testEraseReqByUpdateNoSkip(self):
        ''' update fails, because a req is erased.
        Update foo-tools-1.0 -> foo-tools-2.0, should fail because the require foo is removed
        '''
        ipo = self.instPackage('foo', '1')
        ipo2 = self.instPackage('foo-tools', '1')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        upo2 = self.repoPackage('foo-tools', '2')
        upo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addErase(ipo)
        self.tsInfo.addUpdate(upo2, oldpo=ipo2)
        
        self.assertEquals('err', *self.resolveCode(skip=False))

    def testEraseReqByUpdateSkip(self):
        ''' update is skipped, because a req is erased.
        Update foo-tools-1.0 -> foo-tools-2.0, should fail because the require foo is removed
        the update is skipped and foo-tools-1.0 is removed too, because it requires foo. 
        '''
        ipo = self.instPackage('foo', '1')
        ipo2 = self.instPackage('foo-tools', '1')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        upo2 = self.repoPackage('foo-tools', '2')
        upo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addUpdate(upo2, oldpo=ipo2)
        self.tsInfo.addErase(ipo)
        
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([])

    def testConflictWithInstalled(self):
        ''' update fails, because it conflicts with installed
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        the update get skipped and the transaction is now empty
        '''
        po1 = self.instPackage('foo', '1')
        po2 = self.repoPackage('foo', '2')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = self.instPackage('bar', '1')

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testConflictWithInstalledButUpdateExist(self):
        ''' update fails, because conflict cant be fixed. (req. loop)
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        bar-1.0 is update to bar-2.0, to solve the conflict but bar-2.0 need foo-1.0
        so the foo & bar updates get skipped and the transaction is empty
        '''
        po1 = self.instPackage('foo', '1')
        po2 = self.repoPackage('foo', '2')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = self.instPackage('bar', '1')


        xpo = self.repoPackage('bar', '2')
        xpo.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([po1,ipo])

    def testConflictWithInstalledButUpdateExist2(self):
        '''update fails, because conflict cant be fixed. (missing req.)
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        bar-1.0 is update to bar-2.0, to solve the conflict but bar-2.0 need poo-1.0
        there is not provided
        So the foo & bar updates get skipped and the transaction is empty
        '''
        po1 = self.instPackage('foo', '1')
        po2 = self.repoPackage('foo', '2')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = self.instPackage('bar', '1')


        xpo = self.repoPackage('bar', '2')
        xpo.addRequires('poo', 'EQ', ('0', '1', '0'))

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([po1,ipo])

    def testAlternativePackageAvailable(self):
        ipo = self.repoPackage('foo')
        ipo.addRequires('bar')
        provides1 = self.repoPackage('bar')
        provides1.addRequires('baz')
        provides2 = self.repoPackage('bar-ng')
        provides2.addProvides('bar')
        #provides2.addRequires('baz')

        self.tsInfo.addInstall(ipo)

        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([ipo, provides2])

    def testOnlyOneRequirementAvailable(self):
        ipo = self.repoPackage('foo')
        ipo.addRequires('bar')
        ipo.addRequires('baz')

        ppo = self.repoPackage('baz')

        self.tsInfo.addInstall(ipo)

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([])

    def test2PkgReqSameDep(self):
        po1 = self.repoPackage('foo')
        po1.addRequires('bar')
        po1.addRequires('foobar')
        po2 = self.repoPackage('bar')
        po2.addRequires('zzzz')
        po3 = self.repoPackage('barfoo')
        po3.addRequires('foobar')
        po4 = self.repoPackage('foobar')
        self.tsInfo.addInstall(po1)
        self.tsInfo.addInstall(po3)

        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([po3,po4])

    def testProvidesAndDepsGetRemoved(self):
        po1 = self.repoPackage('Spaceman')
        po1.addProvides('money')
        po2 = self.repoPackage('GutlessGibbon')
        po2.addRequires('money')
        po2.addRequires('nice')
        po2.addRequires('features')
        self.tsInfo.addInstall(po2)
        self.assertEquals('empty', *self.resolveCode(skip=True))

    def testSecondStepRequiresUpdate(self):
        po1 = self.repoPackage('foo')
        po1.addRequires('xxx')
        po1.addRequires('bar')
        self.tsInfo.addInstall(po1)

        po2 = self.repoPackage('bar')
        po2.addRequires('baz', 'EQ', (None, '2', '1'))

        ipo = self.instPackage('baz')
        upo = self.repoPackage('baz', '2', '1')

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo])


    def testDepCycle1(self):
        po0 = self.repoPackage('leaf')

        po1 = self.repoPackage('foo')
        po1.addRequires('bar')
        po1.addRequires('xxx')
        po2 = self.repoPackage('bar')
        po2.addRequires('baz')
        po3 = self.repoPackage('baz')
        po3.addRequires('foo')
        po3.addRequires('leaf')

        self.tsInfo.addInstall(po1)

        self.assertEquals('empty', *self.resolveCode(skip=True))

    def testDepCycle2(self):
        po0 = self.repoPackage('leaf')

        po1 = self.repoPackage('foo')
        po1.addRequires('bar')
        po2 = self.repoPackage('bar')
        po2.addRequires('baz')
        po2.addRequires('xxx')
        po3 = self.repoPackage('baz')
        po3.addRequires('foo')
        po3.addRequires('leaf')

        self.tsInfo.addInstall(po1)

        self.assertEquals('empty', *self.resolveCode(skip=True))

    def testDepCycle3(self):
        po0 = self.repoPackage('leaf')

        po1 = self.repoPackage('foo')
        po1.addRequires('bar')
        po2 = self.repoPackage('bar')
        po2.addRequires('baz')
        po3 = self.repoPackage('baz')
        po3.addRequires('foo')
        po3.addRequires('leaf')
        po3.addRequires('xxx')

        self.tsInfo.addInstall(po1)

        self.assertEquals('empty', *self.resolveCode(skip=True))

    def testMultiLibUpdate(self):
        '''
        foo-1.i386 & foo-1.xf86_64 is updated by foo-2.i386 & foo-2.xf86_64
        foo-2.xf86_64 has a missing req, and get skipped, foo-2.i386 has to be skipped to
        or it will fail in the rpm test transaction
        '''
        ipo1 = self.instPackage('foo', '1',arch='i386')
        ipo2 = self.instPackage('foo', '1',arch='x86_64')
        po1 = self.repoPackage('foo', '2',arch='i386')
        po2 = self.repoPackage('foo', '2',arch='x86_64')
        po2.addRequires('notfound', 'EQ', ('0', '1', '0'))
        self.tsInfo.addUpdate(po1, oldpo=ipo1)
        self.tsInfo.addUpdate(po2, oldpo=ipo2)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo1,ipo2])

    def testInstReqOldVer1(self):
    	""" 
    	zap-2.0 updates zap-1.0, but zap-2.0 needs barlib-2.0 provided by
    	bar-2.0, but the installed foo, needs barlib-1.0,  so it need to be updated to
    	foo-2.0, that requires barlib-2.0
    	But it only work if foo-1.0 -> foo-2.0 is added as an update, it is not 
    	pulled in by it self.
    	"""
        ipo1 = self.instPackage('foo', '1')
        ipo1.addRequires('barlib', 'EQ', ('0', '1', '0'))
        ipo2 = self.instPackage('bar', '1')
        ipo2.addProvides('barlib', 'EQ', ('0', '1', '0'))
        ipo3 = self.instPackage('zap', '1')
        po1 = self.repoPackage('foo', '2')
        po1.addRequires('barlib', 'EQ', ('0', '2', '0'))
        po2 = self.repoPackage('bar', '2')
        po2.addProvides('barlib', 'EQ', ('0', '2', '0'))
        po3 = self.repoPackage('zap', '2')
        po3.addRequires('barlib', 'EQ', ('0', '2', '0'))
        #FIXME: Find out why this line is needed, it should be auto updated by the solver.
        self.tsInfo.addUpdate(po1, oldpo=ipo1) # why is this needed, it should work without ?
        self.tsInfo.addUpdate(po3, oldpo=ipo3)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([po1,po2,po3])               


    def testBumpedSoName1(self):
        """
        """
        a1 = self.instPackage('a', '1', arch='x86_64')
        a1.addProvides("liba.so.1()(64bit)")
        a2 = self.repoPackage('a', '2', arch='x86_64')
        a2.addProvides("liba.so.2()(64bit)")
        
        b1 = self.instPackage('b', '1', arch='x86_64')
        b1.addProvides("libb.so.1()(64bit)")
        b2 = self.repoPackage('b', '2', arch='x86_64')
        b2.addProvides("libb.so.2()(64bit)")
        
        c1 = self.instPackage('c', '1', arch='x86_64')
        c1.addRequires("liba.so.1()(64bit)")
        c2 = self.repoPackage('c', '2', arch='x86_64')
        c2.addRequires("liba.so.2()(64bit)")

        d1 = self.instPackage('d', '1', arch='x86_64')
        d1.addRequires("libb.so.1()(64bit)")
        d2 = self.repoPackage('d', '2', arch='x86_64')
        d2.addRequires("libb.so.1()(64bit)")

        e1 = self.instPackage('e', '1', arch='x86_64')
        e2 = self.repoPackage('e', '2', arch='x86_64')

        f1 = self.instPackage('f', '1', arch='x86_64')
        f2 = self.repoPackage('f', '2', arch='x86_64')

        self.tsInfo.addUpdate(a2, oldpo=a1)
        self.tsInfo.addUpdate(b2, oldpo=b1)
        self.tsInfo.addUpdate(c2, oldpo=c1)
        self.tsInfo.addUpdate(d2, oldpo=d1)
        self.tsInfo.addUpdate(e2, oldpo=e1)
        self.tsInfo.addUpdate(f2, oldpo=f1)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([a2,b1,c2,d1,e2,f2])
    
    def resolveCode(self,skip = False):
        solver = YumBase()
        solver.conf = FakeConf()
        solver.conf.skip_broken = skip
        solver.tsInfo = solver._tsInfo = self.tsInfo
        solver.rpmdb = self.rpmdb
        solver.pkgSack = self.xsack
        solver.dsCallback = DepSolveProgressCallBack()
        
        for po in self.rpmdb:
            po.repoid = po.repo.id = "installed"
        for po in self.xsack:
            po.repoid = po.repo.id = "TestRepository"
        for txmbr in solver.tsInfo:
            if txmbr.ts_state in ('u', 'i'):
                txmbr.po.repoid = txmbr.po.repo.id = "TestRepository"
            else:
                txmbr.po.repoid = txmbr.po.repo.id = "installed"

        res, msg = solver.buildTransaction()
        return self.res[res], msg

def setup_logging():
    logging.basicConfig()    
    plainformatter = logging.Formatter("%(message)s")    
    console_stdout = logging.StreamHandler(sys.stdout)
    console_stdout.setFormatter(plainformatter)
    verbose = logging.getLogger("yum.verbose")
    verbose.propagate = False
    verbose.addHandler(console_stdout)
    verbose.setLevel(2)
