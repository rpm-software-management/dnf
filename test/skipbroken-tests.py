import unittest
import logging
import sys
import re
from testbase import *

REGEX_PKG = re.compile(r"(\d*):?(.*)-(.*)-(.*)\.(.*)$")

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

    def _pkgstr_to_nevra(self, pkg_str):
        '''
        Get a nevra from from a epoch:name-version-release.arch string
        @param pkg_str: package string
        '''
        res = REGEX_PKG.search(pkg_str)
        if res:
            (e,n,v,r,a) = res.groups()
            if e == "": 
                e = "0"
            return (n,e,v,r,a)   
        else: 
            raise AttributeError("Illegal package string : %s" % pkg_str)

    def repoString(self, pkg_str):
        ''' 
        Add an available package from a epoch:name-version-release.arch string
        '''
        (n,e,v,r,a) = self._pkgstr_to_nevra(pkg_str)
        return self.repoPackage(n,v,r,e,a)   
                
            
    def instString(self, pkg_str):
        ''' 
        Add an installed package from a epoch:name-version-release.arch string
        '''
        (n,e,v,r,a) = self._pkgstr_to_nevra(pkg_str)
        return self.instPackage(n,v,r,e,a)   

           
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
        foo-1.i386 & foo-1.x86_64 is updated by foo-2.i386 & foo-2.x86_64
        foo-2.x86_64 has a missing req, and gets skipped, foo-2.i386 has to be
        skipped too or it will fail in the rpm test transaction
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
        d2 need a lib from b1, so the update fails.
        d2 and b2 get skipped, but the installed b1 needs a
        lib from a1, but it has been updated to a2, so it is
        no longer there. so a2 needs to be skipped to
        """
        a1 = self.instPackage('a', '1', arch='x86_64')
        a1.addProvides("liba.so.1()(64bit)")
        a2 = self.repoPackage('a', '2', arch='x86_64')
        a2.addProvides("liba.so.2()(64bit)")
        
        b1 = self.instPackage('b', '1', arch='x86_64')
        b1.addProvides("libb.so.1()(64bit)")
        b1.addRequires("liba.so.1()(64bit)")
        b2 = self.repoPackage('b', '2', arch='x86_64')
        b2.addProvides("libb.so.2()(64bit)")
        b2.addRequires("liba.so.2()(64bit)")
        
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
        self.assertResult([a1,b1,c1,d1,e2,f2])

    def testBumpedSoName2(self):
        """ 
        https://bugzilla.redhat.com/show_bug.cgi?id=468785
        """
        c1 = self.instPackage('cyrus-sasl-lib', '2.1.22',"18")
        c1.addRequires("libdb-4.3.so")
        
        d1 = self.instPackage('compat-db', '4.6.21',"4")
        d1.addProvides("libdb-4.3.so")
        od1 = self.repoPackage('compat-db46', '4.6.21',"5")
        od1.addProvides("libdb-4.6.so")
        od1.addObsoletes("compat-db")
        od2 = self.repoPackage('compat-db45', '4.6.21',"5")
        od2.addProvides("libdb-4.5.so")
        od2.addObsoletes("compat-db")
        
        r1 = self.instPackage('rpm', '4.6.0-0','0.rc1.3')
        r1.addRequires("libdb-4.5.so")
        r2 = self.instPackage('rpm-libs', '4.6.0-0','0.rc1.3')
        r2.addRequires("libdb-4.5.so")
        r3 = self.instPackage('rpm-build', '4.6.0-0','0.rc1.3')
        r3.addRequires("libdb-4.5.so")
        r4 = self.instPackage('rpm-python', '4.6.0-0','0.rc1.3')
        r4.addRequires("libdb-4.5.so")

        ur1 = self.repoPackage('rpm', '4.6.0-0','0.rc1.5')
        ur1.addRequires("libdb-4.5.so")
        ur1.addRequires("compat-db45")
        ur2 = self.repoPackage('rpm-libs', '4.6.0-0','0.rc1.5')
        ur2.addRequires("libdb-4.5.so")
        ur2.addRequires("compat-db45")
        ur3 = self.repoPackage('rpm-build', '4.6.0-0','0.rc1.5')
        ur3.addRequires("libdb-4.5.so")
        ur3.addRequires("compat-db45")
        ur4 = self.repoPackage('rpm-python', '4.6.0-0','0.rc1.5')
        ur4.addRequires("libdb-4.5.so")
        ur4.addRequires("compat-db45")

        self.tsInfo.addObsoleting(od2, oldpo=d1)
        self.tsInfo.addObsoleted(d1, od2)
        self.tsInfo.addObsoleting(od1, oldpo=d1)
        self.tsInfo.addObsoleted(d1, od1)
        self.tsInfo.addUpdate(ur1, oldpo=r1)
        self.tsInfo.addUpdate(ur2, oldpo=r2)
        self.tsInfo.addUpdate(ur3, oldpo=r3)
        self.tsInfo.addUpdate(ur4, oldpo=r4)
        
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([c1,d1,r1,r2,r3,r4])

    def testBumpedSoName3(self):
        """ 
        https://bugzilla.redhat.com/show_bug.cgi?id=468785
        yum update compat-db46
        """
        c1 = self.instPackage('cyrus-sasl-lib', '2.1.22',"18")
        c1.addRequires("libdb-4.3.so")
        
        d1 = self.instPackage('compat-db', '4.6.21',"4")
        d1.addProvides("libdb-4.3.so")
        od1 = self.repoPackage('compat-db46', '4.6.21',"5")
        od1.addProvides("libdb-4.6.so")
        od1.addObsoletes("compat-db")
        od2 = self.repoPackage('compat-db45', '4.6.21',"5")
        od2.addProvides("libdb-4.5.so")
        od2.addObsoletes("compat-db")
        
        r1 = self.instPackage('rpm', '4.6.0-0','0.rc1.3')
        r1.addRequires("libdb-4.5.so")
        r2 = self.instPackage('rpm-libs', '4.6.0-0','0.rc1.3')
        r2.addRequires("libdb-4.5.so")
        r3 = self.instPackage('rpm-build', '4.6.0-0','0.rc1.3')
        r3.addRequires("libdb-4.5.so")
        r4 = self.instPackage('rpm-python', '4.6.0-0','0.rc1.3')
        r4.addRequires("libdb-4.5.so")

        ur1 = self.repoPackage('rpm', '4.6.0-0','0.rc1.5')
        ur1.addRequires("libdb-4.5.so")
        ur1.addRequires("compat-db45")
        ur2 = self.repoPackage('rpm-libs', '4.6.0-0','0.rc1.5')
        ur2.addRequires("libdb-4.5.so")
        ur2.addRequires("compat-db45")
        ur3 = self.repoPackage('rpm-build', '4.6.0-0','0.rc1.5')
        ur3.addRequires("libdb-4.5.so")
        ur3.addRequires("compat-db45")
        ur4 = self.repoPackage('rpm-python', '4.6.0-0','0.rc1.5')
        ur4.addRequires("libdb-4.5.so")
        ur4.addRequires("compat-db45")

        self.tsInfo.addObsoleting(od1, oldpo=d1)
        self.tsInfo.addObsoleted(d1, od1)
        self.tsInfo.addUpdate(ur1, oldpo=r1)
        self.tsInfo.addUpdate(ur2, oldpo=r2)
        self.tsInfo.addUpdate(ur3, oldpo=r3)
        self.tsInfo.addUpdate(ur4, oldpo=r4)
        
        self.assertEquals('err', *self.resolveCode(skip=False))
        
    def testBumpedSoNameMultiArch(self):
        """ 
        if compat-db45.x86_64 get skipped, then compat-db45.i386 should not 
        get pulled in instead
        """
        c1 = self.instPackage('cyrus-sasl-lib', '2.1.22',"18", arch='x86_64')
        c1.addRequires("libdb-4.3.so")
        
        d1 = self.instPackage('compat-db', '4.6.21',"4", arch='x86_64')
        d1.addProvides("libdb-4.3.so")
        od1 = self.repoPackage('compat-db46', '4.6.21',"5", arch='x86_64')
        od1.addProvides("libdb-4.6.so")
        od1.addObsoletes("compat-db")
        od2 = self.repoPackage('compat-db45', '4.6.21',"5", arch='x86_64')
        od2.addProvides("libdb-4.5.so")
        od2.addObsoletes("compat-db")
        od3 = self.repoPackage('compat-db45', '4.6.21',"5", arch='i386')
        od3.addProvides("libdb-4.5.so")
        od3.addObsoletes("compat-db")
        
        r1 = self.instPackage('rpm', '4.6.0-0','0.rc1.3', arch='x86_64')
        r1.addRequires("libdb-4.5.so")
        r2 = self.instPackage('rpm-libs', '4.6.0-0','0.rc1.3', arch='x86_64')
        r2.addRequires("libdb-4.5.so")
        r3 = self.instPackage('rpm-build', '4.6.0-0','0.rc1.3', arch='x86_64')
        r3.addRequires("libdb-4.5.so")
        r4 = self.instPackage('rpm-python', '4.6.0-0','0.rc1.3', arch='x86_64')
        r4.addRequires("libdb-4.5.so")

        ur1 = self.repoPackage('rpm', '4.6.0-0','0.rc1.5', arch='x86_64')
        ur1.addRequires("libdb-4.5.so")
        ur1.addRequires("compat-db45")
        ur2 = self.repoPackage('rpm-libs', '4.6.0-0','0.rc1.5', arch='x86_64')
        ur2.addRequires("libdb-4.5.so")
        ur2.addRequires("compat-db45")
        ur3 = self.repoPackage('rpm-build', '4.6.0-0','0.rc1.5', arch='x86_64')
        ur3.addRequires("libdb-4.5.so")
        ur3.addRequires("compat-db45")
        ur4 = self.repoPackage('rpm-python', '4.6.0-0','0.rc1.5', arch='x86_64')
        ur4.addRequires("libdb-4.5.so")
        ur4.addRequires("compat-db45")


        self.tsInfo.addObsoleting(od2, oldpo=d1)
        self.tsInfo.addObsoleted(d1, od2)
        self.tsInfo.addObsoleting(od1, oldpo=d1)
        self.tsInfo.addObsoleted(d1, od1)
        self.tsInfo.addUpdate(ur1, oldpo=r1)
        self.tsInfo.addUpdate(ur2, oldpo=r2)
        self.tsInfo.addUpdate(ur3, oldpo=r3)
        self.tsInfo.addUpdate(ur4, oldpo=r4)

        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([c1,d1,r1,r2,r3,r4])
        
    def testDualPackageUpdate(self):    
        '''
        RHBZ #522112
        two version of the same package installed on the system
        and update will update both, but if it fail some dep only
        One of the updated packages will be removed from the
        transaction.
        '''
        i1 = self.instPackage('xorg-x11-server-Xorg','1.6.99.900')
        i2 = self.instPackage('xorg-x11-server-Xorg','1.6.3')
        u1 = self.repoPackage('xorg-x11-server-Xorg', '1.6.99.901')
        u1.addRequires("notfound")
        self.tsInfo.addUpdate(u1, oldpo=i1)
        self.tsInfo.addUpdate(u1, oldpo=i2)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([i1,i2])
 
    def testDowngrade1(self):
        '''
        bar require foolib=2.0 provided by foo-1.2
        foo-1.2 is downgraded to foo-1.1 there only contains foolib=1.0
        so bar requirement is broken and the downgrade should be removed from
        transaction
        '''
        i1 = self.instPackage('foo', '1.2')
        i1.addProvides('foolib', 'EQ', ('0', '2', '0'))
        i2 = self.instPackage('bar', '1.0')
        i2.addRequires('foolib', 'EQ', ('0', '2', '0'))
        d1 = self.repoPackage('foo', '1.1')
        d1.addProvides('foolib', 'EQ', ('0', '1', '0'))
        self.tsInfo.addDowngrade(d1, oldpo=i1)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([i1, i2])
       

    def testMissingfileReqIptabes(self):    
        '''
        RHBZ #555528
        iptables-0:1.4.5-1.fc12.i686 provides /usr/lib/libxtables.so.2
        is updated to
        iptables-0:1.4.6-1.fc13.i686 provides /usr/lib/libxtables.so.4
        so libguestfs-1:1.0.81-1.fc13.i686 that requires /usr/lib/libxtables.so.2
        breaks because /usr/lib/libxtables.so.2 no longer exists.
        
        It fails in real life but not in the testcase :(
        
        '''
        i1 = self.instPackage('iptables','1.4.5', arch='x86_64')
        i1.addFile("/usr/lib64/libxtables.so.2")
        i2 = self.instPackage('libguestfs','1.0.81', arch='x86_64')
        i2.addRequires("/usr/lib64/libxtables.so.2")
        u1 = self.repoPackage('iptables','1.4.6', arch='x86_64')
        u1.addFile("/usr/lib64/libxtables.so.4")
        self.tsInfo.addUpdate(u1, oldpo=i1)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult([i1,i2])

    def testTransactionOutput(self):
        '''  
        Test that skip-broken transaction dump output dont show the 
        dependon: xxx once.
        '''
        i1 = self.repoPackage('bar1', '1')
        i1.addRequires('foo1', 'EQ', ('0', '1', '0'))
        i1.addRequires('foo2', 'EQ', ('0', '1', '0'))
        i1.addRequires('foo3', 'EQ', ('0', '1', '0'))
        i1.addRequires('foo4', 'EQ', ('0', '1', '0'))
        i1.addRequires('foo5', 'EQ', ('0', '1', '0'))
        i1.addRequires('foo6', 'EQ', ('0', '1', '0'))
        i2 = self.repoPackage('fooA', '1')
        i2.addProvides('foo1', 'EQ', ('0', '1', '0'))
        i3 = self.repoPackage('fooB', '1')
        i3.addProvides('foo2', 'EQ', ('0', '1', '0'))
        i4 = self.repoPackage('fooC', '1')
        i4.addProvides('foo3', 'EQ', ('0', '1', '0'))
        i5 = self.repoPackage('fooD', '1')
        i5.addProvides('foo4', 'EQ', ('0', '1', '0'))
        i6 = self.repoPackage('fooE', '1')
        i6.addProvides('foo5', 'EQ', ('0', '1', '0'))
        i7 = self.instPackage('fooF', '1')
        i7.addProvides('foo6', 'EQ', ('0', '1', '0'))
        u7 = self.instPackage('fooF', '2')
        u7.addProvides('foo6', 'EQ', ('0', '2', '0'))
        self.tsInfo.addInstall(i1)
        self.tsInfo.addUpdate(u7, oldpo=i7)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        # uncomment this line and the test will fail and you can see the output
        # self.assertResult([i1])
        
    def test_conflict_looping(self):
        ''' 
        Skip-broken is looping
        https://bugzilla.redhat.com/show_bug.cgi?id=681806
        '''
        members = [] # the result after the transaction
        # Installed package conflicts with u1
        i0 = self.instString('kde-l10n-4.6.0-3.fc15.1.noarch')
        i0.addConflicts('kdepim', 'GT', ('6', '4.5.9', '0'))
        members.append(i0)
        i1 = self.instString('6:kdepim-4.5.94.1-1.fc14.x86_64')
        u1 = self.repoString('7:kdepim-4.4.10-1.fc15.x86_64')
        self.tsInfo.addUpdate(u1, oldpo=i1)
        # u1 should be removed, because of the conflict
        members.append(i1)
        i2 = self.instString('6:kdepim-libs-4.5.94.1-1.fc14.x86_64')
        u2 = self.repoString('7:kdepim-libs-4.4.10-1.fc15.x86_64')
        self.tsInfo.addUpdate(u2, oldpo=i2)
        members.append(u2)
        i3 = self.instString('kdepim-runtime-libs-4.5.94.1-2.fc14.x86_64')
        u3 = self.repoString('1:kdepim-runtime-libs-4.4.10-2.fc15.x86_64')
        self.tsInfo.addUpdate(u3, oldpo=i3)
        members.append(u3)
        i4 = self.instString('kdepim-runtime-4.5.94.1-2.fc14.x86_64')
        u4 = self.repoString('1:kdepim-runtime-4.4.10-2.fc15.x86_64')
        self.tsInfo.addUpdate(u4, oldpo=i4)
        members.append(u4)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult(members)

    def test_skipbroken_001(self):
        ''' 
        this will pass
        https://bugzilla.redhat.com/show_bug.cgi?id=656057
        '''
        members = []
        # Installed package conflicts with ux1
        ix0 = self.instString('1:libguestfs-1.6.0-1.fc14.1.i686')
        ix0.addRequires('/usr/lib/.libssl.so.1.0.0a.hmac')
        members.append(ix0)
        ix1 = self.instString('openssl-1.0.0a-2.fc14.i686')
        ix1.addFile("/usr/lib/.libssl.so.1.0.0a.hmac")
        ux1 = self.repoString('openssl-1.0.0b-1.fc14.i686')
        ux1.addFile("/usr/lib/.libssl.so.1.0.0b.hmac")
        self.tsInfo.addUpdate(ux1, oldpo=ix1)
        members.append(ix1)
        self.assertEquals('empty', *self.resolveCode(skip=True))
        self.assertResult(members)


    def test_skipbroken_002(self):
        ''' 
        this will pass
        https://bugzilla.redhat.com/show_bug.cgi?id=656057
        '''
        members = []
        # Installed package conflicts with ux1
        ix0 = self.instString('1:libguestfs-1.6.0-1.fc14.1.i686')
        ix0.addRequires('/usr/lib/.libssl.so.1.0.0a.hmac')
        members.append(ix0)
        ix1 = self.instString('openssl-1.0.0a-2.fc14.i686')
        ix1.addFile("/usr/lib/.libssl.so.1.0.0a.hmac")
        ux1 = self.repoString('openssl-1.0.0b-1.fc14.i686')
        ux1.addFile("/usr/lib/.libssl.so.1.0.0b.hmac")
        self.tsInfo.addUpdate(ux1, oldpo=ix1)
        members.append(ix1)
        # this is just junk to make the transaction big
        i1 = self.instString('afoobar-0.4.12-2.fc12.noarch')
        u1 = self.repoString('afoobar-0.4.14-1.fc14.noarch')
        self.tsInfo.addUpdate(u1, oldpo=i1)
        members.append(u1)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult(members)

    def test_skipbroken_003(self):
        ''' 
        this will fail, because of a bug in the skip-broken code.
        it will remove the wrong package (zfoobar) instead of openssl.
        the problem is that self._working_po is not set with the right value
        when checking file requires for installed packages after the transaction
        if resolved. (_resolveRequires)
        if fails because self._working_po contains the last package processed in the transaction
        zfoobar, so it will be removed.
        https://bugzilla.redhat.com/show_bug.cgi?id=656057
        
        This should not fail anymore, after the the self._working_po is reset in depsolver
        '''
        members = []
        # Installed package conflicts with ux1
        ix0 = self.instString('1:libguestfs-1.6.0-1.fc14.1.i686')
        ix0.addRequires('/usr/lib/.libssl.so.1.0.0a.hmac')
        members.append(ix0)
        ix1 = self.instString('openssl-1.0.0a-2.fc14.i686')
        ix1.addFile("/usr/lib/.libssl.so.1.0.0a.hmac")
        ux1 = self.repoString('openssl-1.0.0b-1.fc14.i686')
        ux1.addFile("/usr/lib/.libssl.so.1.0.0b.hmac")
        self.tsInfo.addUpdate(ux1, oldpo=ix1)
        members.append(ix1)
        # this is just junk to make the transaction big
        i1 = self.instString('zfoobar-0.4.12-2.fc12.noarch')
        u1 = self.repoString('zfoobar-0.4.14-1.fc14.noarch')
        self.tsInfo.addUpdate(u1, oldpo=i1)
        members.append(u1)
        self.assertEquals('ok', *self.resolveCode(skip=True))
        self.assertResult(members)
    
    
    def resolveCode(self,skip = False):
        solver = YumBase()
        solver.save_ts  =  save_ts
        solver.arch.setup_arch('x86_64')
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
