import base
import dnf.queries

class Downgrade(base.ResultTestCase):
    def test_downgrade_local(self):
        yumbase = base.mock_yum_base()
        sack = yumbase.sack

        ret = yumbase.downgradeLocal(base.TOUR_PKG_PATH)
        self.assertEqual(len(ret), 2) # quirk of TransactionData.addDowngrade()
        new_pkg = [txmbr.po for txmbr in ret if \
                       txmbr.po.location == base.TOUR_PKG_PATH][0]
        new_set = base.installed_but(sack, "tour") + [new_pkg]
        self.assertResult(yumbase, new_set)

    def test_downgrade(self):
        yumbase = base.mock_yum_base("main")
        sack = yumbase.sack
        ret = yumbase.downgrade(pattern="tour")
        self.assertEqual(len(ret), 1)

        new_pkg = dnf.queries.available_by_name(sack, "tour")[0]
        self.assertEqual(new_pkg.evr, "4.6-1")
        new_set = base.installed_but(sack, "tour") + [new_pkg]
        self.assertResult(yumbase, new_set)
