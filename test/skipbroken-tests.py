import unittest
import logging
import sys
from testbase import *

class SkipBrokenTests(DepsolveTests):
    ''' Test cases to test skip-broken'''
    
    def setup_func(self):
        setup_logging()

    def testMissingReqNoSkip(self):
        ''' install fails,  because of missing req.
        bar fails because foobar is not provided '''
        po = FakePackage('foo', '1', '0', '0', 'noarch')
        po.addRequires('bar', None, (None,None,None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('bar', '1', '0', '0', 'noarch')
        xpo.addRequires('foobar', None, (None,None,None))
        self.xsack.addPackage(xpo)
        self.assertEquals('err', *self.resolveCode(skip=False))
        self.assertResult((po,xpo))

    def testMissingReqSkip(self):
        ''' install is skipped, because of missing req.
        foo + bar is skipped, because foobar is not provided '''
        po = FakePackage('foo', '1', '0', '0', 'noarch')
        po.addRequires('bar', None, (None,None,None))
        self.tsInfo.addInstall(po)

        xpo = FakePackage('bar', '1', '0', '0', 'noarch')
        xpo.addRequires('foobar', None, (None,None,None))
        self.xsack.addPackage(xpo)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([])

    def testDepWithMissingReqSkip(self):
        ''' install is skipped, beacuse dep is missing req.  
        foo + foobar is skipped because barfoo is not provided
        bar stays in the transaction
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po1.addRequires('foobar', None, (None,None,None))
        self.tsInfo.addInstall(po1)

        po2 = FakePackage('bar', '1', '0', '0', 'noarch')
        self.tsInfo.addInstall(po2)

        xpo1 = FakePackage('foobar', '1', '0', '0', 'noarch')
        xpo1.addRequires('barfoo', None, (None,None,None))
        self.xsack.addPackage(xpo1)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([po2])

    def testUpdateOldRequired(self):
        ''' update breaking req. of installed package is skipped
        foo-1.0 -> foo-2.0 breaks the installed foo-tools needing foo-1.0
        so skip the update and we have and empty transaction 
        '''
        # FIXME: The right solution is to skip the update from the transaction 
        
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')

        ipo = FakePackage('foo-tools', '2.5', '0', '0', 'noarch')
        ipo.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.rpmdb.addPackage(po1)
        self.tsInfo.addUpdate(po2, oldpo=po1)
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testUpdateRequireOld(self):
        '''update with missing req. is skipped
        The foo-1.0 -> foo-2.0 update fails, because foo-tools-2.0 need by foo-2.0
        is not provided, the update should be skipped and result in a empty transaction
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po1.addRequires('foo-tools', 'EQ', ('0', '1', '0'))
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')
        po2.addRequires('foo-tools', 'EQ', ('0', '2', '0'))

        ipo = FakePackage('foo-tools', '1', '0', '0', 'noarch')

        self.rpmdb.addPackage(po1)
        self.tsInfo.addUpdate(po2, oldpo=po1)
        self.rpmdb.addPackage(ipo)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testUpdateRequireBoth(self):
        ''' install + update skipped, because of missing req.
        foo-1.0 -> foo-2.0 update, fails because foo-tools-2.0, needed by foo-2.0 is not provided.
        foo-2.0 update get skip, and the foo-gui install will get skipped too, because it need foo-2.0
        there is not longer provided.
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po1.addRequires('foo-tools', 'EQ', ('0', '1', '0'))
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')
        po2.addRequires('foo-tools', 'EQ', ('0', '2', '0'))

        ipo = FakePackage('foo-tools', '1', '0', '0', 'noarch')
        por =  FakePackage('foo-gui', '1', '0', '0', 'noarch')
        por.addRequires('foo', 'EQ', ('0', '2', '0'))

        self.rpmdb.addPackage(po1)
        self.tsInfo.addUpdate(po2, oldpo=po1)
        self.rpmdb.addPackage(ipo)
        self.tsInfo.addInstall(por)

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testEraseDep(self):
        ''' remove a package that someone depends on
        foo is removed, and foo-tools get removed too, because it 
        depends on foo  
        '''
        ipo = FakePackage('foo', '1', '0', '0', 'noarch')
        ipo2 = FakePackage('foo-tools', '1', '0', '0', 'noarch')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.rpmdb.addPackage(ipo)
        self.rpmdb.addPackage(ipo2)

        self.tsInfo.addErase(ipo)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([])

    def testEraseReqByUpdateNoSkip(self):
        ''' update fails, because a req is erased.
        Update foo-tools-1.0 -> foo-tools-2.0, should fail because the require foo is removed
        '''
        ipo = FakePackage('foo', '1', '0', '0', 'noarch')
        ipo2 = FakePackage('foo-tools', '1', '0', '0', 'noarch')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        upo2 = FakePackage('foo-tools', '2', '0', '0', 'noarch')
        upo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.rpmdb.addPackage(ipo)
        self.rpmdb.addPackage(ipo2)   
        self.tsInfo.addErase(ipo)
        self.tsInfo.addUpdate(upo2, oldpo=ipo2)
        
        self.assertEquals('err', *self.resolveCode(skip=False))

    def testEraseReqByUpdateSkip(self):
        ''' update is skipped, because a req is erased.
        Update foo-tools-1.0 -> foo-tools-2.0, should fail because the require foo is removed
        the update is skipped and foo-tools-1.0 is removed too, because it requires foo. 
        '''
        ipo = FakePackage('foo', '1', '0', '0', 'noarch')
        ipo2 = FakePackage('foo-tools', '1', '0', '0', 'noarch')
        ipo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        upo2 = FakePackage('foo-tools', '2', '0', '0', 'noarch')
        upo2.addRequires('foo', 'EQ', ('0', '1', '0'))

        self.rpmdb.addPackage(ipo)
        self.rpmdb.addPackage(ipo2)   
        self.tsInfo.addUpdate(upo2, oldpo=ipo2)
        self.tsInfo.addErase(ipo)
        
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult([])

    def testConflictWithInstalled(self):
        ''' update fails, because it conflicts with installed
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        the update get skipped and the transaction is now empty
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = FakePackage('bar', '1', '0', '0', 'noarch')

        self.rpmdb.addPackage(po1)
        self.rpmdb.addPackage(ipo)

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([ipo, po1])

    def testConflictWithInstalledButUpdateExist(self):
        ''' update fails, because conflict cant be fixed. (req. loop)
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        bar-1.0 is update to bar-2.0, to solve the conflict but bar-2.0 need foo-1.0
        so the foo & bar updates get skipped and the transaction is empty
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = FakePackage('bar', '1', '0', '0', 'noarch')

        self.rpmdb.addPackage(po1)
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('bar', '2', '0', '0', 'noarch')
        xpo.addRequires('foo', 'EQ', ('0', '1', '0'))
        self.xsack.addPackage(xpo)

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([po1,ipo])

    def testConflictWithInstalledButUpdateExist(self):
        '''update fails, because conflict cant be fixed. (missing req.)
        foo 1.0 -> 2.0 update fails, because foo-2.0 conflict with bar-1.0
        bar-1.0 is update to bar-2.0, to solve the conflict but bar-2.0 need poo-1.0
        there is not provided
        So the foo & bar updates get skipped and the transaction is empty
        '''
        po1 = FakePackage('foo', '1', '0', '0', 'noarch')
        po2 = FakePackage('foo', '2', '0', '0', 'noarch')
        po2.addConflicts('bar', 'EQ', ('0', '1', '0'))

        ipo = FakePackage('bar', '1', '0', '0', 'noarch')

        self.rpmdb.addPackage(po1)
        self.rpmdb.addPackage(ipo)

        xpo = FakePackage('bar', '2', '0', '0', 'noarch')
        xpo.addRequires('poo', 'EQ', ('0', '1', '0'))
        self.xsack.addPackage(xpo)

        self.tsInfo.addUpdate(po2, oldpo=po1)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([po1,ipo])


    def resolveCode(self,skip = False):
        solver = YumBase()
        solver.conf = FakeConf()
        solver.conf.skip_broken = skip
        solver.tsInfo = solver._tsInfo = self.tsInfo
        solver.rpmdb = self.rpmdb
        solver.pkgSack = self.xsack
        
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

