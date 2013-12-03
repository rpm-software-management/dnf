from tests import support, mock
from dnf.yum.misc import unlink_f
from dnf.util import Bunch
import hawkey

PACKAGE = 'tour-5-1.noarch'

class DrpmTest(support.TestCase):
    def __init__(self, *args):
        support.TestCase.__init__(self, *args)
        self.base = support.MockBase()
        self.sack = self.base.sack

        # load the testing repo
        repo = support.MockRepo('drpm', '/tmp/dnf-cache')
        self.base.repos[repo.id] = repo
        repo.baseurl = ['file://%s/%s' % (support.repo_dir(), repo.id)]
        repo.load()

        # add it to sack
        hrepo = hawkey.Repo(repo.id)
        hrepo.repomd_fn = repo.repomd_fn
        hrepo.primary_fn = repo.primary_fn
        hrepo.filelists_fn = repo.filelists_fn
        hrepo.presto_fn = repo.presto_fn
        self.sack.load_yum_repo(hrepo, load_filelists=True, load_presto=True)

    def setUp(self):
        # find the newest 'tour' package available
        self.pkg = max(self.base.sack.query().available().filter(name='tour'))
        self.assertEqual(str(self.pkg), PACKAGE)

        # pretend it's remote and not cached
        self.pkg.repo.__class__.local = False
        self.pkg.localPkg = lambda: '/tmp/%s.rpm' % PACKAGE
        unlink_f(self.pkg.localPkg())

    def tearDown(self):
        # don't break other tests
        del self.pkg.repo.__class__.local

    def test_delta(self):
        # there should be a delta from 5-0 to 5-1
        self.assertTrue(self.pkg.get_delta_from_evr('5-0'))

    def download(self, errors=None, ret={}):
        # utility function, calls Base.download_packages()
        # and returns the list of relative URLs it used.
        urls = []
        def dlp(targets, failfast):
            target, = targets
            self.assertEqual(target.__class__.__name__, 'PackageTarget')
            self.assertTrue(failfast)
            urls.append(target.relative_url)
            err = errors and errors.pop(0)
            if err:
                # PackageTarget.err is not writable
                targets[0] = Bunch(po=target.po, err=err)
        with mock.patch('librepo.download_packages', dlp):
            self.assertEqual(self.base.download_packages([self.pkg]), ret)
        return urls

    def test_simple_download(self):
        self.assertEquals(self.download(), [PACKAGE +'.rpm'])

    def test_drpm_download(self):
        # the testing drpm is about 150% of the target..
        self.pkg.repo.deltarpm = 1
        with mock.patch('dnf.drpm.MAX_PERCENTAGE', 50):
            self.assertEquals(self.download(), ['tour-5-1.noarch.rpm'])
        with mock.patch('dnf.drpm.MAX_PERCENTAGE', 200):
            self.assertEquals(self.download(), ['drpms/tour-5-1.noarch.drpm'])
