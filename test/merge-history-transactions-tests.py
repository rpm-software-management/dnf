import unittest

import yum.history as hist

_fake_count = 0
class FakeYumHistoryTransaction(hist.YumHistoryTransaction):
    def __init__(self, pkgs, tid=None, beg_timestamp=None, end_timestamp=None,
                 beg_rpmdbversion=None, end_rpmdbversion=None,
                 loginuid=0, return_code=0, pkgs_with=[],
                 errors=[], output=[]):
        global _fake_count

        if tid is None:
            _fake_count += 1
            tid = _fake_count
        if beg_timestamp is None:
            _fake_count += 1
            beg_timestamp = _fake_count
        if end_timestamp is None:
            _fake_count += 1
            end_timestamp = _fake_count

        if beg_rpmdbversion is None:
            _fake_count += 1
            beg_rpmdbversion = '?:<n/a>,' + str(_fake_count)
        if end_rpmdbversion is None:
            _fake_count += 1
            end_rpmdbversion = '?:<n/a>,' + str(_fake_count)

        self.tid              = tid
        self.beg_timestamp    = beg_timestamp
        self.beg_rpmdbversion = beg_rpmdbversion
        self.end_timestamp    = end_timestamp
        self.end_rpmdbversion = end_rpmdbversion
        self.loginuid         = loginuid
        self.return_code      = return_code

        self._loaded_TW = pkgs_with
        self._loaded_TD = pkgs

        self._loaded_ER = errors
        self._loaded_OT = output

        self.altered_lt_rpmdb = None
        self.altered_gt_rpmdb = None

def _dump_trans_data(pkgs):
    """ For debugging to see WTF is going on with .trans_data. """
    return [(str(pkg), pkg.state) for pkg in pkgs]

class MergeHistTransTests(unittest.TestCase):

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)

    def setUp(self):
        pass
    def tearDown(self):
        pass

    def _merge_new(self, trans):
        merged = hist.YumMergedHistoryTransaction(trans[0])
        for pkg in trans[1:]:
            merged.merge(pkg)
        return merged

    def _trans_new(self, *args, **kwargs):
        return FakeYumHistoryTransaction(*args, **kwargs)

    def _pkg_new(self, name, version='1', release='2',
                 arch='noarch', epoch='0', checksum=None, state='Install'):
        self.assertTrue(state in hist._sttxt2stcode)
        pkg = hist.YumHistoryPackageState(name,arch,epoch,version,release,
                                          state, checksum)
        return pkg

    def assertMergedBeg(self, merged, beg):
        self.assertTrue(beg.tid in merged.tid)
        self.assertEquals(beg.beg_timestamp, merged.beg_timestamp)
        self.assertEquals(beg.beg_rpmdbversion, merged.beg_rpmdbversion)
    def assertMergedEnd(self, merged, end):
        self.assertTrue(end.tid in merged.tid)
        self.assertEquals(end.end_timestamp, merged.end_timestamp)
        self.assertEquals(end.end_rpmdbversion, merged.end_rpmdbversion)
    def assertMergedCodes(self, merged, trans):
        ret = set()
        uid = set()
        for trans in trans:
            ret.add(trans.loginuid)
            uid.add(trans.return_code)
        if len(ret) == 1:
            self.assertEquals(list(ret)[0], merged.return_code)
        else:
            for ret in ret:
                self.assertTrue(ret in merged.return_code)
        if len(uid) == 1:
            self.assertEquals(list(uid)[0], merged.loginuid)
        else:
            for uid in uid:
                self.assertTrue(uid in merged.loginuid)

    def assertMergedMain(self, merged, trans):
        self.assertMergedBeg(merged, trans[0])
        self.assertMergedEnd(merged, trans[-1])
        self.assertMergedCodes(merged, trans)

    def testSimpleInMerge1(self, xstate='Install'):
        pkg1 = self._pkg_new('foo', state=xstate)
        pkg2 = self._pkg_new('xbar', version='4')
        trans = []
        trans.append(self._trans_new([pkg1]))
        trans.append(self._trans_new([pkg2]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(pkgs[0], pkg1)
        self.assertEquals(pkgs[0].state, xstate)
        self.assertEquals(pkgs[1], pkg2)
        self.assertEquals(pkgs[1].state, pkg2.state)

    def testSimpleInMerge2(self, xstate='Install'):
        pkg1 = self._pkg_new('foo', state=xstate)
        pkg2 = self._pkg_new('bar',  version='4')
        pkg3 = self._pkg_new('xbar', version='6')
        pkg4 = self._pkg_new('xfoo', version='3')
        trans = []
        trans.append(self._trans_new([pkg1, pkg3]))
        trans.append(self._trans_new([pkg2, pkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], pkg2)
        self.assertEquals(pkgs[0].state, pkg2.state)
        self.assertEquals(pkgs[1], pkg1)
        self.assertEquals(pkgs[1].state, xstate)
        self.assertEquals(pkgs[2], pkg3)
        self.assertEquals(pkgs[2].state, pkg3.state)
        self.assertEquals(pkgs[3], pkg4)
        self.assertEquals(pkgs[3].state, pkg4.state)

    def testSimpleUpMerge1(self, xstate='Update'):
        opkg1 = self._pkg_new('foo',              state='Updated')
        npkg1 = self._pkg_new('foo', version='3', state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')

        trans = []
        trans.append(self._trans_new([opkg1, npkg1]))
        trans.append(self._trans_new([opkg2, npkg2]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], opkg1)
        self.assertEquals(pkgs[2].state, opkg1.state)
        self.assertEquals(pkgs[3], npkg1)
        self.assertEquals(pkgs[3].state, xstate)

    def testSimpleUpMerge2(self, xstate='Update'):
        opkg1 = self._pkg_new('foo',              state='Updated')
        npkg1 = self._pkg_new('foo', version='3', state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated')
        npkg3 = self._pkg_new('foo', version='5', state='Update')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1, npkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], opkg1)
        self.assertEquals(pkgs[2].state, opkg1.state)
        self.assertEquals(pkgs[3], npkg3)
        self.assertEquals(pkgs[3].state, xstate)

    def testSimpleUpMerge3(self, xstate='Install'):
        opkg1 = self._pkg_new('foo', state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo',              state='Updated')
        npkg3 = self._pkg_new('foo', version='5', state='Update')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], npkg3)
        self.assertEquals(pkgs[2].state, xstate)

    def testSimpleUpMultiMerge1(self, xstate='Install'):
        opkg1 = self._pkg_new('foo', arch='i586',              state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', arch='i586',              state='Updated')
        npkg3 = self._pkg_new('foo', arch='i686', version='5', state='Update')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], npkg3)
        self.assertEquals(pkgs[2].state, xstate)

    def testUpDownMerge1(self, xstate='Update'):
        opkg1 = self._pkg_new('foo', version='0', state='Updated')
        npkg1 = self._pkg_new('foo',              state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo',              state='Updated')
        npkg3 = self._pkg_new('foo', version='7', state='Update')
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='5', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1, npkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[2], opkg1)
        self.assertNotEquals(pkgs[3], opkg3)
        self.assertNotEquals(pkgs[3], npkg3)
        self.assertNotEquals(pkgs[3], opkg4)
        self.assertNotEquals(pkgs[3].state, npkg4.state)
        self.assertEquals(pkgs[3].pkgtup, npkg4.pkgtup)
        self.assertEquals(pkgs[3].state, xstate)

    def testUpDownMerge2(self, xstate='Install'):
        opkg1 = self._pkg_new('foo')
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo',              state='Updated')
        npkg3 = self._pkg_new('foo', version='7', state=xstate)
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='5', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertNotEquals(pkgs[2], opkg1)
        self.assertNotEquals(pkgs[2], opkg3)
        self.assertNotEquals(pkgs[2], npkg3)
        self.assertNotEquals(pkgs[2], opkg4)
        self.assertNotEquals(pkgs[2].state, npkg4.state)
        self.assertEquals(pkgs[2].pkgtup, npkg4.pkgtup)
        self.assertEquals(pkgs[2].state, xstate)

    def testUpDownMerge3(self):
        opkg1 = self._pkg_new('foo')
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated') # rpmdbv
        npkg3 = self._pkg_new('foo', version='7', state='Update')
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='3', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[2], opkg1)
        self.assertEquals(pkgs[2].state, opkg1.state)
        self.assertNotEquals(pkgs[3], opkg1)
        self.assertNotEquals(pkgs[3].state, opkg3.state)
        self.assertNotEquals(pkgs[3], npkg3)
        self.assertNotEquals(pkgs[3], opkg4)
        self.assertNotEquals(pkgs[3].state, npkg4.state)
        self.assertEquals(pkgs[3].pkgtup, npkg4.pkgtup)
        self.assertEquals(pkgs[3].state, 'Reinstall')

    def testUpDownMerge4(self, xstate='Update'):
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated')
        npkg3 = self._pkg_new('foo', version='7', state=xstate)
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='3', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertNotEquals(pkgs[2].state, opkg3.state)
        self.assertNotEquals(pkgs[2], npkg3)
        self.assertNotEquals(pkgs[2], opkg4)
        self.assertNotEquals(pkgs[2].state, npkg4.state)
        self.assertEquals(pkgs[2].pkgtup, opkg3.pkgtup)
        if xstate == 'Obsoleting':
            self.assertEquals(pkgs[2].state, 'Obsoleting')
        else:
            self.assertEquals(pkgs[2].state, 'Reinstall')

    def testUpDownMerge5(self, xstate='Update'):
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated')
        npkg3 = self._pkg_new('foo', version='21', state=xstate)
        opkg4 = self._pkg_new('foo', version='21', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='19', state='Downgrade')
        opkg5 = self._pkg_new('foo', version='19', state='Downgraded')
        npkg5 = self._pkg_new('foo', version='13', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg5, npkg5]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], opkg3)
        self.assertEquals(pkgs[2].state, opkg3.state)
        self.assertEquals(pkgs[3], npkg5)
        self.assertEquals(pkgs[3].state, xstate)

    def testDownUpMerge1(self, xstate='Downgrade'):
        opkg1 = self._pkg_new('foo', version='10', state='Downgraded')
        npkg1 = self._pkg_new('foo', version='9',  state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='7',  state='Updated')
        npkg3 = self._pkg_new('foo', version='8',  state='Update')
        opkg4 = self._pkg_new('foo', version='9',  state='Downgraded')
        npkg4 = self._pkg_new('foo', version='7',  state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1, npkg1]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertNotEquals(pkgs[2], opkg3)
        self.assertNotEquals(pkgs[2].state, npkg3.state)
        self.assertNotEquals(pkgs[2], opkg4)
        self.assertNotEquals(pkgs[2], npkg4)
        self.assertEquals(pkgs[2].pkgtup, npkg3.pkgtup)
        self.assertEquals(pkgs[2].state, xstate)
        self.assertEquals(pkgs[3], opkg1)
        self.assertEquals(pkgs[3].state, opkg1.state)

    def testDownUpMerge2(self, xstate='Install'):
        opkg1 = self._pkg_new('foo', version='7', state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='5', state='Updated')
        npkg3 = self._pkg_new('foo', version='6', state='Update')
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='5', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertNotEquals(pkgs[2], opkg1)
        self.assertNotEquals(pkgs[2], opkg3)
        self.assertNotEquals(pkgs[2], opkg4)
        self.assertNotEquals(pkgs[2], npkg4)
        self.assertNotEquals(pkgs[2].state, npkg3.state)
        self.assertEquals(pkgs[2].pkgtup, npkg3.pkgtup)
        self.assertEquals(pkgs[2].state, xstate)

    def testDownUpMerge3(self):
        opkg1 = self._pkg_new('foo')
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated')
        npkg3 = self._pkg_new('foo', version='7', state='Update')
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded') # rpmdbv
        npkg4 = self._pkg_new('foo', version='3', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2, opkg1]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[2], opkg1)
        self.assertEquals(pkgs[2].state, opkg1.state)
        self.assertNotEquals(pkgs[3], opkg1)
        self.assertNotEquals(pkgs[3], opkg3)
        self.assertNotEquals(pkgs[3].state, npkg3.state)
        self.assertNotEquals(pkgs[3].state, opkg4.state)
        self.assertNotEquals(pkgs[3], npkg4)
        self.assertEquals(pkgs[3].pkgtup, npkg3.pkgtup)
        self.assertEquals(pkgs[3].state, 'Reinstall')

    def testDownUpMerge4(self, xstate='Update'):
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='3', state='Updated')
        npkg3 = self._pkg_new('foo', version='7', state=xstate)
        opkg4 = self._pkg_new('foo', version='7', state='Downgraded')
        npkg4 = self._pkg_new('foo', version='3', state='Downgrade')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg3, npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[1], npkg2)
        self.assertNotEquals(pkgs[2], opkg3)
        self.assertNotEquals(pkgs[2].state, 'Update')
        self.assertNotEquals(pkgs[2].state, opkg4.state)
        self.assertNotEquals(pkgs[2], npkg4)
        self.assertEquals(pkgs[2].pkgtup, npkg3.pkgtup)
        if xstate == 'Obsoleting':
            self.assertEquals(pkgs[2].state, 'Obsoleting')
        else:
            self.assertEquals(pkgs[2].state, 'Reinstall')

    def testDownUpMerge5(self, xstate='Downgrade'):
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        opkg3 = self._pkg_new('foo', version='21', state='Downgraded')
        npkg3 = self._pkg_new('foo', version='3',  state=xstate)
        opkg4 = self._pkg_new('foo', version='3',  state='Updated')
        npkg4 = self._pkg_new('foo', version='7',  state='Update')
        opkg5 = self._pkg_new('foo', version='7',  state='Updated')
        npkg5 = self._pkg_new('foo', version='13', state='Update')

        trans = []
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([opkg4, npkg4]))
        trans.append(self._trans_new([opkg5, npkg5]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 4)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, opkg2.state)
        self.assertEquals(pkgs[1], npkg2)
        self.assertEquals(pkgs[1].state, npkg2.state)
        self.assertEquals(pkgs[2], npkg5)
        self.assertEquals(pkgs[2].state, xstate)
        self.assertEquals(pkgs[3], opkg3)
        self.assertEquals(pkgs[3].state, opkg3.state)

    def testInRmMerge1(self, xstate='Install', estate='Erase'):
        npkg1 = self._pkg_new('foo', state=xstate)
        npkg2 = self._pkg_new('foo', state=estate)
        npkg3 = self._pkg_new('bar', version='6', state='True-Install')

        trans = []
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([npkg2]))
        trans.append(self._trans_new([npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0], npkg3)
        self.assertEquals(pkgs[0].state, npkg3.state)

    def testInRmMerge2(self, xstate='Install'):
        self.testInRmMerge1(xstate, 'Obsoleted')

    def testInRmInonlyMerge1(self, xstate='True-Install', estate='Erase'):
        npkg1 = self._pkg_new('foo', state=xstate)
        npkg2 = self._pkg_new('foo', version='2', state=xstate)
        npkg3 = self._pkg_new('foo', version='3', state=xstate)
        npkg4 = self._pkg_new('foo', state=estate)
        npkg5 = self._pkg_new('foo', version='2', state=estate)
        npkg6 = self._pkg_new('foo', version='3', state=estate)
        npkg9 = self._pkg_new('bar', version='6', state=xstate)

        trans = []
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([npkg2]))
        trans.append(self._trans_new([npkg3]))
        trans.append(self._trans_new([npkg4]))
        trans.append(self._trans_new([npkg5]))
        trans.append(self._trans_new([npkg6]))
        trans.append(self._trans_new([npkg9]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0], npkg9)
        self.assertEquals(pkgs[0].state, npkg9.state)

    def testInRmInonlyMerge2(self, xstate='True-Install'):
        self.testInRmInonlyMerge1(xstate, 'Obsoleted')

    def testUpRmMerge1(self, xstate='Update'):
        npkg1 = self._pkg_new('foo')
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state=xstate)
        npkg3 = self._pkg_new('bar', version='6', state='Erase')

        trans = []
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(pkgs[0], opkg2)
        self.assertEquals(pkgs[0].state, npkg3.state)
        self.assertEquals(pkgs[1], npkg1)
        self.assertEquals(pkgs[1].state, npkg1.state)

    def testUpRmMerge2(self, xstate='True-Install'):
        npkg1 = self._pkg_new('foo')
        npkg4 = self._pkg_new('bar', version='4', state=xstate)
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state='Update')
        npkg3 = self._pkg_new('bar', version='6', state='Erase')

        trans = []
        trans.append(self._trans_new([npkg1, npkg4]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0], npkg1)
        self.assertEquals(pkgs[0].state, npkg1.state)

    def testUpRmMerge3(self, xstate='Update'):
        npkg1 = self._pkg_new('foo')
        npkg4 = self._pkg_new('bar', version='4', state='Dep-Install')
        opkg2 = self._pkg_new('bar', version='4', state='Updated')
        npkg2 = self._pkg_new('bar', version='6', state=xstate)
        npkg3 = self._pkg_new('bar', version='6', state='Erase')

        trans = []
        trans.append(self._trans_new([npkg1, npkg4]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0], npkg1)
        self.assertEquals(pkgs[0].state, npkg1.state)

    def testRmInMerge1(self, xstate='Install', estate='Erase'):
        npkg1 = self._pkg_new('foo', state=xstate)
        npkg2 = self._pkg_new('foo', state=estate)
        npkg3 = self._pkg_new('bar', version='6', state='True-Install')

        trans = []
        trans.append(self._trans_new([npkg2]))
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([npkg3]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(pkgs[0], npkg3)
        self.assertEquals(pkgs[0].state, npkg3.state)
        self.assertEquals(pkgs[1], npkg1)
        if xstate == 'Obsoleting':
            self.assertEquals(pkgs[1].state, 'Obsoleting')
        else:
            self.assertEquals(pkgs[1].state, 'Reinstall')

    def testRmInMerge2(self, xstate='Install'):
        self.testRmInMerge1(xstate, 'Obsoleted')

    def testUpRmInlMerge1(self, xstate='Update', ystate='Install',
                          estate='Erase'):
        npkg1 = self._pkg_new('bar', version='6', state='True-Install')
        opkg2 = self._pkg_new('foo', version='3',  state='Updated')
        npkg2 = self._pkg_new('foo', version='7',  state=xstate)
        npkg3 = self._pkg_new('foo', version='7',  state=estate)
        npkg4 = self._pkg_new('foo',               state=ystate)

        trans = []
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([npkg3]))
        trans.append(self._trans_new([npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], npkg1)
        self.assertEquals(pkgs[0].state, npkg1.state)
        self.assertEquals(pkgs[1].pkgtup, npkg4.pkgtup)
        if ystate == 'Obsoleting':
            self.assertEquals(pkgs[1].state, "Obsoleting")
        else:
            self.assertEquals(pkgs[1].state, "Downgrade")
        self.assertEquals(pkgs[2].pkgtup, opkg2.pkgtup)
        self.assertEquals(pkgs[2].state, "Downgraded")

    def testUpRmInlMerge2(self, xstate='Update', ystate='Install'):
        self.testUpRmInlMerge1(xstate, ystate, 'Obsoleted')

    def testUpRmInuMerge1(self, xstate='Update', ystate='Install',
                          estate='Erase'):
        npkg1 = self._pkg_new('bar', version='6', state='True-Install')
        opkg2 = self._pkg_new('foo', version='3',  state='Updated')
        npkg2 = self._pkg_new('foo', version='7',  state=xstate)
        npkg3 = self._pkg_new('foo', version='7',  state=estate)
        npkg4 = self._pkg_new('foo', version='4',  state=ystate)

        trans = []
        trans.append(self._trans_new([npkg1]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([npkg3]))
        trans.append(self._trans_new([npkg4]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], npkg1)
        self.assertEquals(pkgs[0].state, npkg1.state)
        self.assertEquals(pkgs[1].pkgtup, opkg2.pkgtup)
        self.assertEquals(pkgs[1].state,  "Updated")
        self.assertEquals(pkgs[2].pkgtup, npkg4.pkgtup)
        if ystate == 'Obsoleting':
            self.assertEquals(pkgs[2].state, "Obsoleting")
        else:
            self.assertEquals(pkgs[2].state, "Update")

    def testUpRmInuMerge2(self, xstate='Update', ystate='Install'):
        self.testUpRmInuMerge1(xstate, ystate, 'Obsoleted')

    def testBrokenUpMerge1(self, xstate='Update', estate='Erase'):
        # This is "broken", so as long as we don't die it's all good.
        # The below test basically documents what we do.
        opkg1 = self._pkg_new('foo', version='1',   state='Updated')
        npkg1 = self._pkg_new('foo', version='2',   state=xstate)
        opkg2 = self._pkg_new('foo', version='11',  state='Updated')
        npkg2 = self._pkg_new('foo', version='21',  state=xstate)
        opkg3 = self._pkg_new('foo', version='110', state='Updated')
        npkg3 = self._pkg_new('foo', version='210', state=xstate)
        npkg4 = self._pkg_new('foo', version='2',   state=estate)
        npkg5 = self._pkg_new('foo', version='21',  state=estate)
        npkg6 = self._pkg_new('foo', version='210', state=estate)

        trans = []
        trans.append(self._trans_new([opkg1, npkg1]))
        trans.append(self._trans_new([opkg2, npkg2]))
        trans.append(self._trans_new([opkg3, npkg3]))
        trans.append(self._trans_new([npkg4]))
        trans.append(self._trans_new([npkg5]))
        trans.append(self._trans_new([npkg6]))
        merged = self._merge_new(trans)
        self.assertMergedMain(merged, trans)
        pkgs = merged.trans_data
        self.assertEquals(len(pkgs), 3)
        self.assertEquals(pkgs[0], opkg1)
        self.assertEquals(pkgs[0].state, 'Updated')
        self.assertEquals(pkgs[1], opkg2)
        self.assertEquals(pkgs[1].state, 'Updated')
        self.assertEquals(pkgs[2], opkg3)
        self.assertEquals(pkgs[2].state, estate)

    #  Obsoleting is the _painful_ one because it really should be a state, but
    # an attribute. So "Obsoleting" can be any of:
    #     Install*, Reinstall, Update, Downgrade
    def testObsSIM1(self):
        self.testSimpleInMerge1(xstate='Obsoleting')
    def testObsSIM2(self):
        self.testSimpleInMerge2(xstate='Obsoleting')
    def testObsSUM1(self):
        self.testSimpleUpMerge1(xstate='Obsoleting')
    def testObsSUM2(self):
        self.testSimpleUpMerge2(xstate='Obsoleting')
    def testObsSUM3(self):
        self.testSimpleUpMerge3(xstate='Obsoleting')
    def testObsSUMM1(self):
        self.testSimpleUpMultiMerge1(xstate='Obsoleting')
    def testObsUDM1(self):
        self.testUpDownMerge1(xstate='Obsoleting')
    def testObsUDM2(self):
        self.testUpDownMerge2(xstate='Obsoleting')
    def testObsUDM4(self):
        self.testUpDownMerge4(xstate='Obsoleting')
    def testObsUDM5(self):
        self.testUpDownMerge5(xstate='Obsoleting')
    def testObsDUM1(self):
        self.testDownUpMerge1(xstate='Obsoleting')
    def testObsDUM2(self):
        self.testDownUpMerge2(xstate='Obsoleting')
    def testObsDUM4(self):
        self.testDownUpMerge4(xstate='Obsoleting')
    def testObsDUM5(self):
        self.testDownUpMerge5(xstate='Obsoleting')
    def testObsIRM1(self):
        self.testInRmMerge1(xstate='Obsoleting')
    def testObsIRM2(self):
        self.testInRmMerge2(xstate='Obsoleting')
    def testObsIRMM1(self):
        self.testInRmInonlyMerge1(xstate='Obsoleting')
    def testObsIRMM2(self):
        self.testInRmInonlyMerge1(xstate='Obsoleting')
    def testObsURM1(self):
        self.testUpRmMerge1(xstate='Obsoleting')
    def testObsURM2(self):
        self.testUpRmMerge2(xstate='Obsoleting')
    def testObsURM3(self):
        self.testUpRmMerge3(xstate='Obsoleting')
    def testObsRIM1(self):
        self.testRmInMerge1(xstate='Obsoleting')
    def testObsRIM2(self):
        self.testRmInMerge2(xstate='Obsoleting')
    def testObsURIlM1(self):
        self.testUpRmInlMerge1(xstate='Obsoleting')
        self.testUpRmInlMerge1(ystate='Obsoleting')
        self.testUpRmInlMerge1(xstate='Obsoleting', ystate='Obsoleting')
    def testObsURIlM2(self):
        self.testUpRmInlMerge2(xstate='Obsoleting')
        self.testUpRmInlMerge2(ystate='Obsoleting')
        self.testUpRmInlMerge2(xstate='Obsoleting', ystate='Obsoleting')
    def testObsURIuM1(self):
        self.testUpRmInuMerge1(xstate='Obsoleting')
        self.testUpRmInuMerge1(ystate='Obsoleting')
        self.testUpRmInuMerge1(xstate='Obsoleting', ystate='Obsoleting')
    def testObsURIuM2(self):
        self.testUpRmInuMerge2(xstate='Obsoleting')
        self.testUpRmInuMerge2(ystate='Obsoleting')
        self.testUpRmInuMerge2(xstate='Obsoleting', ystate='Obsoleting')
