from yum.constants import *
import unittest
import settestpath
from testbase import *

from yum.transactioninfo import TransactionData

class TransactionDataTests(unittest.TestCase):
    ''' Test cases for yum.transactioninfo.TransactionData'''
    
    def setUp(self):
        self.tsInfo = TransactionData()
        self.rpmdb  = packageSack.PackageSack()
        self.pkgSack  = packageSack.PackageSack()
        self.tsInfo.setDatabases(self.rpmdb, self.pkgSack)
        self.foo1 = FakePackage('foo', '1', '0', '0', 'noarch')
        self.foo2 = FakePackage('foo', '2', '0', '0', 'i386')
        self.bar1 = FakePackage('bar', '1', '0', '0', 'i386')
        self.bar2 = FakePackage('bar', '2', '0', '0', 'noarch')
        self.foogui1 = FakePackage('foogui', '1', '0', '0', 'x86_64')
        self.foogui2 = FakePackage('foogui', '2', '0', '0', 'noarch')
        
    
    def testLenght(self):
        ''' test __len__ method '''
        self.tsInfo.addInstall(self.foo1)
        self.tsInfo.addUpdate(self.foogui2,self.foogui1)
        self.dumpTsInfo()
        self.assertEqual(len(self.tsInfo),3)

    def testAddTheSameTwice(self):
        ''' test add the same twice '''
        txmbr1 = self.tsInfo.addInstall(self.foo1)
        txmbr2 = self.tsInfo.addInstall(self.foo2)
        txmbr3 = self.tsInfo.addInstall(self.foo1)
        self.dumpTsInfo()
        self.assertEqual(len(self.tsInfo),2) # only 2 members
        # self.assertEquals(txmbr3, txmbr1)    # 1 & 3 should be equal

    def testExists(self):
        ''' test exists method '''
        self.tsInfo.addInstall(self.foo1)
        self.tsInfo.addInstall(self.bar1)
        self.dumpTsInfo()
        self.assertEqual(self.tsInfo.exists(self.foo1.pkgtup),1)
        self.assertEqual(self.tsInfo.exists(self.bar1.pkgtup),1)
        self.assertEqual(self.tsInfo.exists(self.foogui1.pkgtup),0)
        
    def testRemove(self):
        ''' test remove from transaction '''
        txmbr = self.tsInfo.addInstall(self.foo1)
        self.tsInfo.addInstall(self.bar2)
        self.tsInfo.remove(self.bar2.pkgtup)
        self.dumpTsInfo()
        self.assertResult([txmbr])

    def testAddToTransaction(self):
        ''' test adding basic adding to Transaction '''
        txmbr1 = self.tsInfo.addInstall(self.foo1)
        txmbr2 = self.tsInfo.addUpdate(self.foogui2,self.foogui1)
        txmbr3 = self.tsInfo.getMembers(self.foogui1.pkgtup)[0]
        self.dumpTsInfo()
        self.assertResult([txmbr1,txmbr2,txmbr3])

    def testGetFromTransaction(self):
        ''' test getting from Transaction '''
        self.tsInfo.addInstall(self.foo2)
        self.tsInfo.addObsoleting(self.bar2,self.bar1)
        self.tsInfo.addUpdate(self.foogui2,self.foogui1)
        self.tsInfo.addErase(self.foo1)
        self.dumpTsInfo()
        # get install member foo-2.0 - u
        txmbr = self.tsInfo.getMembers(self.foo2.pkgtup)[0]
        self.assertEqual(txmbr.po, self.foo2)
        self.assertEqual(txmbr.current_state, TS_AVAILABLE)
        self.assertEqual(txmbr.output_state, TS_INSTALL)
        self.assertEqual(txmbr.po.state, TS_INSTALL)
        self.assertEqual(txmbr.ts_state, 'u')
        # get erase member foo-1.0 - e
        txmbr = self.tsInfo.getMembers(self.foo1.pkgtup)[0]
        self.assertEqual(txmbr.po, self.foo1)
        self.assertEqual(txmbr.current_state, TS_INSTALL)
        self.assertEqual(txmbr.output_state, TS_ERASE)
        self.assertEqual(txmbr.po.state, TS_INSTALL)
        self.assertEqual(txmbr.ts_state, 'e')
        # get Obsoleting
        txmbr = self.tsInfo.getMembers(self.bar2.pkgtup)[0]
        self.assertEqual(txmbr.po, self.bar2)
        self.assertEqual(txmbr.current_state, TS_AVAILABLE)
        self.assertEqual(txmbr.output_state, TS_OBSOLETING)
        self.assertEqual(txmbr.po.state, TS_OBSOLETING)
        self.assertEqual(txmbr.ts_state, 'u')
        self.assertEqual(txmbr.relatedto, [(self.bar1, 'obsoletes')])
        self.assertEqual(txmbr.obsoletes, [self.bar1])
        # get update member
        txmbr = self.tsInfo.getMembers(self.foogui2.pkgtup)[0]
        self.assertEqual(txmbr.po, self.foogui2)
        self.assertEqual(txmbr.current_state, TS_AVAILABLE)
        self.assertEqual(txmbr.output_state, TS_UPDATE)
        self.assertEqual(txmbr.po.state, TS_UPDATE)
        self.assertEqual(txmbr.ts_state, 'u')
        self.assertEqual(txmbr.relatedto, [(self.foogui1, 'updates')])
        self.assertEqual(txmbr.updates, [self.foogui1])
        

    def testAddUpdatesAndObsoletes(self):
        ''' test addUpdated,addObsoleted'''
        txmbr1 = self.tsInfo.addUpdated(self.foo1,self.foo2)
        txmbr2 = self.tsInfo.addObsoleted(self.bar1,self.bar2)
        self.dumpTsInfo()
        self.assertResult([txmbr1,txmbr2])
        txmbr = self.tsInfo.getMembersWithState(output_states=[TS_UPDATED])[0]
        self.assertEqual(txmbr.po, self.foo1)
        txmbr = self.tsInfo.getMembersWithState(output_states=[TS_OBSOLETED])[0]
        self.assertEqual(txmbr.po, self.bar1)
        

    def testMatchNaevr(self):
        ''' test MatchNaevr '''
        self.tsInfo.addInstall(self.foo1)
        self.tsInfo.addObsoleting(self.bar2,self.bar1)
        self.tsInfo.addUpdate(self.foogui2,self.foogui1)
        self.dumpTsInfo()
        res = self.tsInfo.matchNaevr( name='foogui')
        self.assertEqual(len(res),2) # foogui-1.0, foogui-2.0
        res = self.tsInfo.matchNaevr( arch='noarch')
        self.assertEqual(len(res),3) # foo-1.0, bar-2.0, foogui-2.0
        res = self.tsInfo.matchNaevr( epoch='0',ver='1', rel='0')
        self.assertEqual(len(res),2) # foo-1.0, foogui-1.0

    def testgetMembersWithState(self):
        ''' test getMembersWithState'''
        self.tsInfo.addInstall(self.foo1)
        self.tsInfo.addObsoleting(self.bar2,self.bar1)
        self.tsInfo.addUpdate(self.foogui2,self.foogui1)
        self.dumpTsInfo()
        res = self.tsInfo.getMembersWithState(output_states=[TS_INSTALL,TS_UPDATE])
        self.assertEqual(len(res),2) # foo-1.0, bar-2.0
        res = self.tsInfo.getMembersWithState(output_states=[TS_UPDATED])
        self.assertEqual(len(res),1) # bar-1.0
    
    def assertResult(self, txmbrs):
        """Check if self.tsInfo contains the given txmbr.
        """
        errors = ["Problems with members in txInfo \n\n"]
        txmbrs = set(txmbrs)
        found = set(self.tsInfo.getMembers())

        # Look for needed members
        for txmbr in txmbrs:
            if not self.tsInfo.exists(txmbr.po.pkgtup):
               errors.append(" %s was not found in tsInfo!\n" % txmbr)

        for txmbr in found - txmbrs:
            errors.append("%s should not be in tsInfo\n" % txmbr)

        if len(errors) > 1:
            errors.append("\nTest case was:\n\n")
            errors.extend(inspect.getsource(inspect.stack()[1][0].f_code))
            errors.append("\n")
            self.fail("".join(errors))
            
    def dumpTsInfo(self):
        for txmbr in self.tsInfo:
            print txmbr
