import os
import re
import time
import types
import urlparse

import Errors
from urlgrabber.grabber import URLGrabber
import urlgrabber.mirror
from urlgrabber.grabber import URLGrabError
import repoMDObject
import packageSack
from repos import Repository
import parser
import storagefactory
from yum import config
from yum import misc

class YumPackageSack(packageSack.PackageSack):
    """imports/handles package objects from an mdcache dict object"""
    def __init__(self, packageClass):
        packageSack.PackageSack.__init__(self)
        self.pc = packageClass
        self.added = {}

    def addDict(self, repo, datatype, dataobj, callback=None):
        if self.added.has_key(repo):
            if datatype in self.added[repo]:
                return

        total = len(dataobj.keys())
        if datatype == 'metadata':
            current = 0
            for pkgid in dataobj.keys():
                current += 1
                if callback: callback.progressbar(current, total, repo)
                pkgdict = dataobj[pkgid]
                po = self.pc(repo, pkgdict)
                po.simple['id'] = pkgid
                self._addToDictAsList(self.pkgsByID, pkgid, po)
                self.addPackage(po)

            if not self.added.has_key(repo):
                self.added[repo] = []
            self.added[repo].append('metadata')
            # indexes will need to be rebuilt
            self.indexesBuilt = 0

        elif datatype in ['filelists', 'otherdata']:
            if self.added.has_key(repo):
                if 'metadata' not in self.added[repo]:
                    raise Errors.RepoError, '%s md for %s imported before primary' \
                           % (datatype, repo.id)
            current = 0
            for pkgid in dataobj.keys():
                current += 1
                if callback: callback.progressbar(current, total, repo)
                pkgdict = dataobj[pkgid]
                if self.pkgsByID.has_key(pkgid):
                    for po in self.pkgsByID[pkgid]:
                        po.importFromDict(pkgdict)

            self.added[repo].append(datatype)
            # indexes will need to be rebuilt
            self.indexesBuilt = 0
        else:
            # umm, wtf?
            pass

    def populate(self, repo, with='metadata', callback=None, cacheonly=0):
        if with == 'all':
            data = ['metadata', 'filelists', 'otherdata']
        else:
            data = [ with ]

        if not hasattr(repo, 'cacheHandler'):
            repo.cacheHandler = repo.storage.GetCacheHandler(
                storedir=repo.cachedir,
                repoid=repo.id,
                callback=callback,
                )
        for item in data:
            if self.added.has_key(repo):
                if item in self.added[repo]:
                    continue

            if item == 'metadata':
                xml = repo.getPrimaryXML()
                xmldata = repo.repoXML.getData('primary')
                (ctype, csum) = xmldata.checksum
                dobj = repo.cacheHandler.getPrimary(xml, csum)
                if not cacheonly:
                    self.addDict(repo, item, dobj, callback)
                del dobj

            elif item == 'filelists':
                xml = repo.getFileListsXML()
                xmldata = repo.repoXML.getData('filelists')
                (ctype, csum) = xmldata.checksum
                dobj = repo.cacheHandler.getFilelists(xml, csum)
                if not cacheonly:
                    self.addDict(repo, item, dobj, callback)
                del dobj


            elif item == 'otherdata':
                xml = repo.getOtherXML()
                xmldata = repo.repoXML.getData('other')
                (ctype, csum) = xmldata.checksum
                dobj = repo.cacheHandler.getOtherdata(xml, csum)
                if not cacheonly:
                    self.addDict(repo, item, dobj, callback)
                del dobj

            else:
                # how odd, just move along
                continue
        # get rid of all this stuff we don't need now
        del repo.cacheHandler

class YumRepository(Repository, config.RepoConf):
    """
    This is an actual repository object
   
    Configuration attributes are pulled in from config.RepoConf.
    """
                
    def __init__(self, repoid):
        config.RepoConf.__init__(self)
        Repository.__init__(self, repoid)

        self.urls = []
        self.enablegroups = 0 
        self.groupsfilename = 'yumgroups.xml' # something some freaks might
                                              # eventually want
        self.repoMDFile = 'repodata/repomd.xml'
        self.repoXML = None
        self.cache = 0
        self.mirrorlistparsed = 0
        self.yumvar = {} # empty dict of yumvariables for $string replacement
        self._proxy_dict = {}
        self.metadata_cookie_fn = 'cachecookie'
        self.groups_added = False
        self.http_headers = {}
        
        # throw in some stubs for things that will be set by the config class
        self.basecachedir = ""
        self.cachedir = ""
        self.pkgdir = ""
        self.hdrdir = ""
        
        # holder for stuff we've grabbed
        self.retrieved = { 'primary':0, 'filelists':0, 'other':0, 'groups':0 }

        # callbacks
        self.callback = None  # for the grabber
        self.failure_obj = None
        self.mirror_failure_obj = None
        self.interrupt_callback = None
        
        self.storage = storagefactory.GetStorage()
        self.sack = self.storage.GetPackageSack()

    def __getProxyDict(self):
        self.doProxyDict()
        if self._proxy_dict:
            return self._proxy_dict
        return None

    # consistent access to how proxy information should look (and ensuring
    # that it's actually determined for the repo)
    proxy_dict = property(__getProxyDict)

    def getPackageSack(self):
        """Returns the instance of this repository's package sack."""
        return self.sack


    def ready(self):
        """Returns true if this repository is setup and ready for use."""
        return self.repoXML is not None


    def getGroupLocation(self):
        """Returns the location of the group."""
        thisdata = self.repoXML.getData('group')
        return thisdata.location


    def __cmp__(self, other):
        if self.id > other.id:
            return 1
        elif self.id < other.id:
            return -1
        else:
            return 0

    def __str__(self):
        return self.id

    def _checksum(self, sumtype, file, CHUNK=2**16):
        """takes filename, hand back Checksum of it
           sumtype = md5 or sha
           filename = /path/to/file
           CHUNK=65536 by default"""
        try:
            return misc.checksum(sumtype, file, CHUNK)
        except (Errors.MiscError, EnvironmentError), e:
            raise Errors.RepoError, 'Error opening file for checksum: %s' % e

    def dump(self):
        output = '[%s]\n' % self.id
        vars = ['name', 'bandwidth', 'enabled', 'enablegroups',
                 'gpgcheck', 'includepkgs', 'keepalive', 'proxy',
                 'proxy_password', 'proxy_username', 'exclude',
                 'retries', 'throttle', 'timeout', 'mirrorlist',
                 'cachedir', 'gpgkey', 'pkgdir', 'hdrdir']
        vars.sort()
        for attr in vars:
            output = output + '%s = %s\n' % (attr, getattr(self, attr))
        output = output + 'baseurl ='
        for url in self.urls:
            output = output + ' %s\n' % url

        return output

    def enable(self):
        self.baseurlSetup()
        Repository.enable(self)

    def check(self):
        """self-check the repo information  - if we don't have enough to move
           on then raise a repo error"""
        if len(self.urls) < 1:
            raise Errors.RepoError, \
             'Cannot find a valid baseurl for repo: %s' % self.id

    def doProxyDict(self):
        if self._proxy_dict:
            return

        self._proxy_dict = {} # zap it
        proxy_string = None
        if self.proxy not in [None, '_none_']:
            proxy_string = '%s' % self.proxy
            if self.proxy_username is not None:
                proxy_parsed = urlparse.urlsplit(self.proxy, allow_fragments=0)
                proxy_proto = proxy_parsed[0]
                proxy_host = proxy_parsed[1]
                proxy_rest = proxy_parsed[2] + '?' + proxy_parsed[3]
                proxy_string = '%s://%s@%s%s' % (proxy_proto,
                        self.proxy_username, proxy_host, proxy_rest)

                if self.proxy_password is not None:
                    proxy_string = '%s://%s:%s@%s%s' % (proxy_proto,
                              self.proxy_username, self.proxy_password,
                              proxy_host, proxy_rest)

        if proxy_string is not None:
            self._proxy_dict['http'] = proxy_string
            self._proxy_dict['https'] = proxy_string
            self._proxy_dict['ftp'] = proxy_string

    def __headersListFromDict(self):
        """Convert our dict of headers to a list of 2-tuples for urlgrabber."""
        headers = []

        keys = self.http_headers.keys()
        for key in keys:
            headers.append((key, self.http_headers[key]))

        return headers

    def setupGrab(self):
        """sets up the grabber functions with the already stocked in urls for
           the mirror groups"""

        if self.failovermethod == 'roundrobin':
            mgclass = urlgrabber.mirror.MGRandomOrder
        else:
            mgclass = urlgrabber.mirror.MirrorGroup

        headers = tuple(self.__headersListFromDict())

        self.grabfunc = URLGrabber(keepalive=self.keepalive,
                                   bandwidth=self.bandwidth,
                                   retry=self.retries,
                                   throttle=self.throttle,
                                   progress_obj=self.callback,
                                   proxies = self.proxy_dict,
                                   failure_callback=self.failure_obj,
                                   interrupt_callback=self.interrupt_callback,
                                   timeout=self.timeout,
                                   http_headers=headers,
                                   reget='simple')


        self.grab = mgclass(self.grabfunc, self.urls,
                            failure_callback=self.mirror_failure_obj)

    def dirSetup(self):
        """make the necessary dirs, if possible, raise on failure"""

        cachedir = os.path.join(self.basecachedir, self.id)
        pkgdir = os.path.join(cachedir, 'packages')
        hdrdir = os.path.join(cachedir, 'headers')
        self.setAttribute('cachedir', cachedir)
        self.setAttribute('pkgdir', pkgdir)
        self.setAttribute('hdrdir', hdrdir)

        cookie = self.cachedir + '/' + self.metadata_cookie_fn
        self.setAttribute('metadata_cookie', cookie)

        for dir in [self.cachedir, self.hdrdir, self.pkgdir]:
            if self.cache == 0:
                if os.path.exists(dir) and os.path.isdir(dir):
                    continue
                else:
                    try:
                        os.makedirs(dir, mode=0755)
                    except OSError, e:
                        raise Errors.RepoError, \
                            "Error making cache directory: %s error was: %s" % (dir, e)
            else:
                if not os.path.exists(dir):
                    raise Errors.RepoError, \
                        "Cannot access repository dir %s" % dir

    def baseurlSetup(self):
        """go through the baseurls and mirrorlists and populate self.urls
           with valid ones, run  self.check() at the end to make sure it worked"""

        goodurls = []
        if self.mirrorlist and not self.mirrorlistparsed:
            mirrorurls = getMirrorList(self.mirrorlist, self.proxy_dict)
            self.mirrorlistparsed = 1
            for url in mirrorurls:
                url = parser.varReplace(url, self.yumvar)
                self.baseurl.append(url)

        for url in self.baseurl:
            url = parser.varReplace(url, self.yumvar)
            (s,b,p,q,f,o) = urlparse.urlparse(url)
            if s not in ['http', 'ftp', 'file', 'https']:
                print 'not using ftp, http[s], or file for repos, skipping - %s' % (url)
                continue
            else:
                goodurls.append(url)
    
        self.setAttribute('urls', goodurls)
        self.check()
        self.setupGrab() # update the grabber for the urls

    def __get(self, url=None, relative=None, local=None, start=None, end=None,
            copy_local=0, checkfunc=None, text=None, reget='simple', cache=True):
        """retrieve file from the mirrorgroup for the repo
           relative to local, optionally get range from
           start to end, also optionally retrieve from a specific baseurl"""

        # if local or relative is None: raise an exception b/c that shouldn't happen
        # if url is not None - then do a grab from the complete url - not through
        # the mirror, raise errors as need be
        # if url is None do a grab via the mirror group/grab for the repo
        # return the path to the local file

        # Turn our dict into a list of 2-tuples
        headers = self.__headersListFromDict()

        # We will always prefer to send no-cache.
        if not (cache or self.http_headers.has_key('Pragma')):
            headers.append(('Pragma', 'no-cache'))

        headers = tuple(headers)

        if local is None or relative is None:
            raise Errors.RepoError, \
                  "get request for Repo %s, gave no source or dest" % self.id

        if self.failure_obj:
            (f_func, f_args, f_kwargs) = self.failure_obj
            self.failure_obj = (f_func, f_args, f_kwargs)

        if self.cache == 1:
            if os.path.exists(local): # FIXME - we should figure out a way
                return local          # to run the checkfunc from here

            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)

        if url is not None:
            ug = URLGrabber(keepalive = self.keepalive,
                            bandwidth = self.bandwidth,
                            retry = self.retries,
                            throttle = self.throttle,
                            progress_obj = self.callback,
                            copy_local = copy_local,
                            reget = reget,
                            proxies = self.proxy_dict,
                            failure_callback = self.failure_obj,
                            interrupt_callback=self.interrupt_callback,
                            timeout=self.timeout,
                            checkfunc=checkfunc,
                            http_headers=headers,
                            )

            remote = url + '/' + relative

            try:
                result = ug.urlgrab(remote, local,
                                    text=text,
                                    range=(start, end),
                                    )
            except URLGrabError, e:
                raise Errors.RepoError, \
                    "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)

        else:
            try:
                result = self.grab.urlgrab(relative, local,
                                           text = text,
                                           range = (start, end),
                                           copy_local=copy_local,
                                           reget = reget,
                                           checkfunc=checkfunc,
                                           http_headers=headers,
                                           )
            except URLGrabError, e:
                raise Errors.RepoError, "failure: %s from %s: %s" % (relative, self.id, e)

        return result

    def getPackage(self, package, checkfunc = None, text = None, cache = True):
        remote = package.returnSimple('relativepath')
        local = package.localPkg()
        basepath = package.returnSimple('basepath')
            
        return self.__get(url=basepath,
                        relative=remote,
                        local=local,
                        checkfunc=checkfunc,
                        text=text,
                        cache=cache
                        )
        
    def getHeader(self, package, checkfunc = None, reget = 'simple',
            cache = True):
        
        remote = package.returnSimple('relativepath')
        local =  package.localHdr()
        start = package.returnSimple('hdrstart')
        end = package.returnSimple('hdrend')
        basepath = package.returnSimple('basepath')

        return self.__get(url=basepath, relative=remote, local=local, start=start,
                        reget=None, end=end, checkfunc=checkfunc, copy_local=1,
                        cache=cache,
                        )
 


    def metadataCurrent(self):
        """Check if there is a metadata_cookie and check its age. If the
        age of the cookie is less than metadata_expire time then return true
        else return False"""

        val = False
        if os.path.exists(self.metadata_cookie):
            cookie_info = os.stat(self.metadata_cookie)
            if cookie_info[8] + self.metadata_expire > time.time():
                val = True
            # WE ARE FROM THE FUTURE!!!!
            elif cookie_info[8] > time.time():
                val = False
        return val

    def setMetadataCookie(self):
        """if possible, set touch the metadata_cookie file"""

        check = self.metadata_cookie
        if not os.path.exists(self.metadata_cookie):
            check = self.cachedir

        if os.access(check, os.W_OK):
            fo = open(self.metadata_cookie, 'w+')
            fo.close()
            del fo


    def setup(self, cache):
        try:
            self.cache = cache
            self.baseurlSetup()
            self.dirSetup()
        except Errors.RepoError, e:
            raise

        try:
            self._loadRepoXML(text=self)
        except Errors.RepoError, e:
            raise Errors.RepoError, ('Cannot open/read repomd.xml file for repository: %s' % self)


    def _loadRepoXML(self, text=None):
        """retrieve/check/read in repomd.xml from the repository"""

        remote = self.repoMDFile
        local = self.cachedir + '/repomd.xml'
        if self.repoXML is not None:
            return
    
        if self.cache or self.metadataCurrent():
            if not os.path.exists(local):
                raise Errors.RepoError, 'Cannot find repomd.xml file for %s' % (self)
            else:
                result = local
        else:
            checkfunc = (self._checkRepoXML, (), {})
            try:
                result = self.__get(relative=remote,
                                  local=local,
                                  copy_local=1,
                                  text=text,
                                  reget=None,
                                  checkfunc=checkfunc,
                                  cache=self.http_caching == 'all')


            except URLGrabError, e:
                raise Errors.RepoError, 'Error downloading file %s: %s' % (local, e)
            # if we have a 'fresh' repomd.xml then update the cookie
            self.setMetadataCookie()

        try:
            self.repoXML = repoMDObject.RepoMD(self.id, result)
        except Errors.RepoMDError, e:
            raise Errors.RepoError, 'Error importing repomd.xml from %s: %s' % (self, e)

    def _checkRepoXML(self, fo):
        if type(fo) is types.InstanceType:
            filepath = fo.filename
        else:
            filepath = fo

        try:
            repoMDObject.RepoMD(self.id, filepath)
        except Errors.RepoMDError, e:
            raise URLGrabError(-1, 'Error importing repomd.xml for %s: %s' % (self, e))


    def checkMD(self, fn, mdtype):
        """check the metadata type against its checksum"""
        
        thisdata = self.repoXML.getData(mdtype)
        
        (r_ctype, r_csum) = thisdata.checksum # get the remote checksum

        if type(fn) == types.InstanceType: # this is an urlgrabber check
            file = fn.filename
        else:
            file = fn

        try:
            l_csum = self._checksum(r_ctype, file) # get the local checksum
        except Errors.RepoError, e:
            raise URLGrabError(-3, 'Error performing checksum')

        if l_csum == r_csum:
            return 1
        else:
            raise URLGrabError(-1, 'Metadata file does not match checksum')



    def retrieveMD(self, mdtype):
        """base function to retrieve metadata files from the remote url
           returns the path to the local metadata file of a 'mdtype'
           mdtype can be 'primary', 'filelists', 'other' or 'group'."""
        
        thisdata = self.repoXML.getData(mdtype)
        
        (r_base, remote) = thisdata.location
        fname = os.path.basename(remote)
        local = self.cachedir + '/' + fname

        if self.retrieved.has_key(mdtype):
            if self.retrieved[mdtype]: # got it, move along
                return local

        if self.cache == 1:
            if os.path.exists(local):
                try:
                    self.checkMD(local, mdtype)
                except URLGrabError, e:
                    raise Errors.RepoError, \
                        "Caching enabled and local cache: %s does not match checksum" % local
                else:
                    return local

            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)

        if os.path.exists(local):
            try:
                self.checkMD(local, mdtype)
            except URLGrabError, e:
                pass
            else:
                self.retrieved[mdtype] = 1
                return local # it's the same return the local one

        try:
            checkfunc = (self.checkMD, (mdtype,), {})
            local = self.__get(relative=remote, local=local, copy_local=1,
                             checkfunc=checkfunc, reget=None,
                             cache=self.http_caching == 'all')
        except URLGrabError, e:
            raise Errors.RepoError, \
                "Could not retrieve %s matching remote checksum from %s" % (local, self)
        else:
            self.retrieved[mdtype] = 1
            return local


    def getPrimaryXML(self):
        """this gets you the path to the primary.xml file, retrieving it if we
           need a new one"""

        return self.retrieveMD('primary')


    def getFileListsXML(self):
        """this gets you the path to the filelists.xml file, retrieving it if we 
           need a new one"""

        return self.retrieveMD('filelists')

    def getOtherXML(self):
        return self.retrieveMD('other')

    def getGroups(self):
        """gets groups and returns group file path for the repository, if there
           is none it returns None"""
        try:
            file = self.retrieveMD('group')
        except URLGrabError:
            file = None

        return file

    def setCallback(self, callback):
        self.callback = callback
        self.setupGrab()

    def setFailureObj(self, failure_obj):
        self.failure_obj = failure_obj
        self.setupGrab()

    def setMirrorFailureObj(self, failure_obj):
        self.mirror_failure_obj = failure_obj
        self.setupGrab()

    def setInterruptCallback(self, callback):
        self.interrupt_callback = callback
        self.setupGrab()

def getMirrorList(mirrorlist, pdict = None):
    """retrieve an up2date-style mirrorlist file from a url,
       we also s/$ARCH/$BASEARCH/ and move along
       returns a list of the urls from that file"""

    returnlist = []
    if hasattr(urlgrabber.grabber, 'urlopen'):
        urlresolver = urlgrabber.grabber
    else:
        import urllib
        urlresolver = urllib

    scheme = urlparse.urlparse(mirrorlist)[0]
    if scheme == '':
        url = 'file://' + mirrorlist
    else:
        url = mirrorlist

    try:
        fo = urlresolver.urlopen(url, proxies=pdict)
    except urlgrabber.grabber.URLGrabError, e:
        print "Could not retrieve mirrorlist %s error was\n%s" % (url, e)
        fo = None

    if fo is not None:
        content = fo.readlines()
        for line in content:
            if re.match('^\s*\#.*', line) or re.match('^\s*$', line):
                continue
            mirror = re.sub('\n$', '', line) # no more trailing \n's
            (mirror, count) = re.subn('\$ARCH', '$BASEARCH', mirror)
            returnlist.append(mirror)

    return returnlist

