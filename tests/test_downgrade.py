import base

class Downgrade(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base()
        self.sack = self.yumbase.sack

    def test_downgrade_local(self):
        ret = self.yumbase.downgradeLocal(base.TOUR_PKG_PATH)
        self.assertEqual(len(ret), 2) # quirk of TransactionData.addDowngrade()
        new_pkg = [txmbr.po for txmbr in ret if \
                       txmbr.po.location == base.TOUR_PKG_PATH][0]
        new_set = base.installed_but(self.sack, "tour") + [new_pkg]
        self.assertResult(self.yumbase, new_set)
