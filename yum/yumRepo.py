# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2005 Duke University 
# Copyright 2007 Red Hat
import os
import re
import time
import types
import urlparse
urlparse.uses_fragment.append("media")

import Errors
from urlgrabber.grabber import URLGrabber
from urlgrabber.grabber import default_grabber
import urlgrabber.mirror
from urlgrabber.grabber import URLGrabError
import repoMDObject
import packageSack
from repos import Repository
import parser
import sqlitecachec
import sqlitesack
from yum import config
from yum import misc
from constants import *

import logging
import logginglevels

import warnings

import glob
import shutil
import stat

warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)

logger = logging.getLogger("yum.Repos")
verbose_logger = logging.getLogger("yum.verbose.Repos")

class YumPackageSack(packageSack.PackageSack):
    """imports/handles package objects from an mdcache dict object"""
    def __init__(self, packageClass):
        packageSack.PackageSack.__init__(self)
        self.pc = packageClass
        self.added = {}

    def __del__(self):
        self.close()

    def close(self):
        self.added = {}

    def addDict(self, repo, datatype, dataobj, callback=None):
        if self.added.has_key(repo):
            if datatype in self.added[repo]:
                return

        total = len(dataobj)
        if datatype == 'metadata':
            current = 0
            for pkgid in dataobj:
                current += 1
                if callback: callback.progressbar(current, total, repo)
                pkgdict = dataobj[pkgid]
                po = self.pc(repo, pkgdict)
                po.id = pkgid
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
            for pkgid in dataobj:
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

    def populate(self, repo, mdtype='metadata', callback=None, cacheonly=0):
        if mdtype == 'all':
            data = ['metadata', 'filelists', 'otherdata']
        else:
            data = [ mdtype ]

        if not hasattr(repo, 'cacheHandler'):
            repo.cacheHandler = sqlitecachec.RepodataParserSqlite(
                storedir=repo.cachedir,
                repoid=repo.id,
                callback=callback,
                )
        for item in data:
            if self.added.has_key(repo):
                if item in self.added[repo]:
                    continue
            
            db_fn = None
            
            if item == 'metadata':
                mydbtype = 'primary_db'
                mymdtype = 'primary'
                repo_get_function = repo.getPrimaryXML
                repo_cache_function = repo.cacheHandler.getPrimary

            elif item == 'filelists':
                mydbtype = 'filelists_db'
                mymdtype = 'filelists'
                repo_get_function = repo.getFileListsXML
                repo_cache_function = repo.cacheHandler.getFilelists
                
            elif item == 'otherdata':
                mydbtype = 'other_db'
                mymdtype = 'other'
                repo_get_function = repo.getOtherXML
                repo_cache_function = repo.cacheHandler.getOtherdata
                
            else:
                continue
                
            if self._check_db_version(repo, mydbtype):
                # see if we have the uncompressed db and check it's checksum vs the openchecksum
                # if not download the bz2 file
                # decompress it
                # unlink it
                
                db_un_fn = self._check_uncompressed_db(repo, mydbtype)
                if not db_un_fn:
                    db_fn = repo._retrieveMD(mydbtype, retrieve_can_fail=True)
                    if db_fn:
                        db_un_fn = db_fn.replace('.bz2', '')
                        if not repo.cache:
                            misc.bunzipFile(db_fn, db_un_fn)
                            os.unlink(db_fn)
                            db_un_fn = self._check_uncompressed_db(repo, mydbtype)

                dobj = repo.cacheHandler.open_database(db_un_fn)

            else:
                xml = repo_get_function()
                xmldata = repo.repoXML.getData(mymdtype)
                (ctype, csum) = xmldata.checksum
                dobj = repo_cache_function(xml, csum)

            if not cacheonly:
                self.addDict(repo, item, dobj, callback)
            del dobj


        # get rid of all this stuff we don't need now
        del repo.cacheHandler

    def _check_uncompressed_db(self, repo, mdtype):
        """return file name of uncompressed db is good, None if not"""
        mydbdata = repo.repoXML.getData(mdtype)
        (r_base, remote) = mydbdata.location
        fname = os.path.basename(remote)
        bz2_fn = repo.cachedir + '/' + fname
        db_un_fn = bz2_fn.replace('.bz2', '')
        
        result = None
        
        if os.path.exists(db_un_fn):
            try:
                repo.checkMD(db_un_fn, mdtype, openchecksum=True)
            except URLGrabError:
                if not repo.cache:
                    os.unlink(db_un_fn)
            else:
                result = db_un_fn

        return result
        
    def _check_db_version(self, repo, mdtype):
        return repo._check_db_version(mdtype)
        
class YumRepository(Repository, config.RepoConf):
    """
    This is an actual repository object
   
    Configuration attributes are pulled in from config.RepoConf.
    """
                
    def __init__(self, repoid):
        config.RepoConf.__init__(self)
        Repository.__init__(self, repoid)

        self.repofile = None
        self._urls = []
        self.enablegroups = 0 
        self.groupsfilename = 'yumgroups.xml' # something some freaks might
                                              # eventually want
        self.repoMDFile = 'repodata/repomd.xml'
        self._repoXML = None
        self._oldRepoMDData = {}
        self.cache = 0
        self.mirrorlistparsed = 0
        self.yumvar = {} # empty dict of yumvariables for $string replacement
        self._proxy_dict = {}
        self.metadata_cookie_fn = 'cachecookie'
        self.groups_added = False
        self.http_headers = {}
        self.repo_config_age = 0 # if we're a repo not from a file then the 
                                 # config is very, very old
        # throw in some stubs for things that will be set by the config class
        self.basecachedir = ""
        self.cachedir = ""
        self.pkgdir = ""
        self.hdrdir = ""
        self.cost = 1000
        self.copy_local = 0        
        # holder for stuff we've grabbed
        self.retrieved = { 'primary':0, 'filelists':0, 'other':0, 'group':0,
                           'updateinfo':0}

        # callbacks
        self.callback = None  # for the grabber
        self.failure_obj = None
        self.mirror_failure_obj = None
        self.interrupt_callback = None
        self._callbacks_changed = False

        # callback function for handling media
        self.mediafunc = None
        
        self.sack = sqlitesack.YumSqlitePackageSack(
                sqlitesack.YumAvailablePackageSqlite)

        self._grabfunc = None
        self._grab = None

    def close(self):
        self.sack.close()
        Repository.close(self)
    
    def _resetSack(self):
        self.sack = sqlitesack.YumSqlitePackageSack(
                sqlitesack.YumAvailablePackageSqlite)

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
        if hasattr(self, 'metadata_cookie'):
            return self.repoXML is not None
        return False


    def getGroupLocation(self):
        """Returns the location of the group."""
        if 'group_gz' in self.repoXML.fileTypes():
            thisdata = self.repoXML.getData('group_gz')
        else:
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

    def _checksum(self, sumtype, file, CHUNK=2**16, checksum_can_fail=False):
        """takes filename, hand back Checksum of it
           sumtype = md5 or sha
           filename = /path/to/file
           CHUNK=65536 by default"""
        try:
            return misc.checksum(sumtype, file, CHUNK)
        except (Errors.MiscError, EnvironmentError), e:
            if checksum_can_fail:
                return None
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

    def enablePersistent(self):
        """Persistently enables this repository."""
        self.enable()
        self.cfg.set(self.id, 'enabled', '1')

        try:
            self.cfg.write(file(self.repofile, 'w'))
        except IOError, e:
            if e.errno == 13:
                self.logger.warning(e)
            else:
                raise IOError, str(e)

    def disablePersistent(self):
        """Persistently disables this repository."""
        self.disable()
        self.cfg.set(self.id, 'enabled', '0')

        try:
            self.cfg.write(file(self.repofile, 'w'))
        except IOError, e:
            if e.errno == 13:
                self.logger.warning(e)
            else:
                raise IOError, str(e)

    def check(self):
        """self-check the repo information  - if we don't have enough to move
           on then raise a repo error"""
        if len(self._urls) < 1 and not self.mediaid:
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
                # http://foo:123 == ('http', 'foo:123', '', '', '')
                # don't turn that into: http://foo:123? - bug#328121
                if proxy_parsed[2] == '':
                    proxy_rest = ''
                else:
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

        for key in self.http_headers:
            headers.append((key, self.http_headers[key]))

        return headers

    def setupGrab(self):
        warnings.warn('setupGrab() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)
        self._setupGrab()

    def _setupGrab(self):
        """sets up the grabber functions with the already stocked in urls for
           the mirror groups"""

        if self.failovermethod == 'roundrobin':
            mgclass = urlgrabber.mirror.MGRandomOrder
        else:
            mgclass = urlgrabber.mirror.MirrorGroup

        headers = tuple(self.__headersListFromDict())

        self._grabfunc = URLGrabber(keepalive=self.keepalive,
                                    bandwidth=self.bandwidth,
                                    retry=self.retries,
                                    throttle=self.throttle,
                                    progress_obj=self.callback,
                                    proxies = self.proxy_dict,
                                    failure_callback=self.failure_obj,
                                    interrupt_callback=self.interrupt_callback,
                                    timeout=self.timeout,
                                    copy_local=self.copy_local,
                                    http_headers=headers,
                                    reget='simple')

        self._grabfunc.opts.user_agent = default_grabber.opts.user_agent

        self._grab = mgclass(self._grabfunc, self.urls,
                             failure_callback=self.mirror_failure_obj)

    def _getgrabfunc(self):
        if not self._grabfunc or self._callbacks_changed:
            self._setupGrab()
            self._callbacks_changed = False
        return self._grabfunc

    def _getgrab(self):
        if not self._grab or self._callbacks_changed:
            self._setupGrab()
            self._callbacks_changed = False
        return self._grab

    grabfunc = property(lambda self: self._getgrabfunc())
    grab = property(lambda self: self._getgrab())

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

        for dir in [self.cachedir, self.pkgdir]:
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
        # if we're using a cachedir that's not the system one, copy over these 
        # basic items from the system one
        self._preload_md_from_system_cache('repomd.xml')
        self._preload_md_from_system_cache('cachecookie')
        self._preload_md_from_system_cache('mirrorlist.txt')        
        
        
    def baseurlSetup(self):
        warnings.warn('baseurlSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)
        self._baseurlSetup()

    def _baseurlSetup(self):
        """go through the baseurls and mirrorlists and populate self.urls
           with valid ones, run  self.check() at the end to make sure it worked"""

        mirrorurls = []
        if self.mirrorlist and not self.mirrorlistparsed:
            mirrorurls.extend(self._getMirrorList())
            self.mirrorlistparsed = True

        self.baseurl = self._replace_and_check_url(self.baseurl)
        self.mirrorurls = self._replace_and_check_url(mirrorurls)
        self._urls = self.baseurl + self.mirrorurls
        # if our mirrorlist is just screwed then make sure we unlink a mirrorlist cache
        if len(self._urls) < 1:
            if hasattr(self, 'mirrorlist_file') and os.path.exists(self.mirrorlist_file):
                if not self.cache:
                    try:
                        os.unlink(self.mirrorlist_file)
                    except (IOError, OSError), e:
                        print 'Could not delete bad mirrorlist file: %s - %s' % (self.mirrorlist_file, e)
                    else:
                        print 'removing mirrorlist with no valid mirrors: %s' % self.mirrorlist_file
        # store them all back in baseurl for compat purposes
        self.baseurl = self._urls
        self.check()
        
    def _replace_and_check_url(self, url_list):
        goodurls = []
        for url in url_list:
            url = parser.varReplace(url, self.yumvar)
            (s,b,p,q,f,o) = urlparse.urlparse(url)
            if s not in ['http', 'ftp', 'file', 'https']:
                print 'YumRepo Warning: not using ftp, http[s], or file for repos, skipping - %s' % (url)
                continue
            else:
                goodurls.append(url)

        return goodurls

    def _geturls(self):
        if not self._urls:
            self._baseurlSetup()
        return self._urls

    urls = property(fget=lambda self: self._geturls(),
                    fset=lambda self, value: setattr(self, "_urls", value),
                    fdel=lambda self: setattr(self, "_urls", None))
                    

    def _getFile(self, url=None, relative=None, local=None, start=None, end=None,
            copy_local=None, checkfunc=None, text=None, reget='simple', cache=True):
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
        
        # if copylocal isn't specified pickup the repo-defined attr
        if copy_local is None:
            copy_local = self.copy_local
            
        if local is None or relative is None:
            raise Errors.RepoError, \
                  "get request for Repo %s, gave no source or dest" % self.id

        if self.cache == 1:
            if os.path.exists(local): # FIXME - we should figure out a way
                return local          # to run the checkfunc from here

            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,

                           self)

        if url:
            (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)

        if self.mediaid and self.mediafunc:
            discnum = 1
            if url:
                if scheme == "media" and fragid:
                    discnum = int(fragid)
            try:
                # FIXME: we need to figure out what really matters to
                # pass to the media grabber function here
                result = self.mediafunc(local = local, checkfunc = checkfunc, relative = relative, text = text, copy_local = copy_local, url = url, mediaid = self.mediaid, name = self.name, discnum = discnum, range = (start, end))
                return result
            except Errors.MediaError, e:
                verbose_logger.log(logginglevels.DEBUG_2, "Error getting package from media; falling back to url %s" %(e,))
        
        if url is not None and scheme != "media":
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

            ug.opts.user_agent = default_grabber.opts.user_agent

            remote = url + '/' + relative

            try:
                result = ug.urlgrab(remote, local,
                                    text=text,
                                    range=(start, end),
                                    )
            except URLGrabError, e:
                errstr = "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)
                if e.errno == 256:
                    raise Errors.NoMoreMirrorsRepoError, errstr
                else:
                    raise Errors.RepoError, errstr
                    

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
                errstr = "failure: %s from %s: %s" % (relative, self.id, e)
                if e.errno == 256:
                    raise Errors.NoMoreMirrorsRepoError, errstr
                else:
                    raise Errors.RepoError, errstr

        return result
    __get = _getFile

    def getPackage(self, package, checkfunc = None, text = None, cache = True):
        remote = package.relativepath
        local = package.localPkg()
        basepath = package.basepath
            
        return self._getFile(url=basepath,
                        relative=remote,
                        local=local,
                        checkfunc=checkfunc,
                        text=text,
                        cache=cache
                        )
        
    def getHeader(self, package, checkfunc = None, reget = 'simple',
            cache = True):

        remote = package.relativepath
        local =  package.localHdr()
        start = package.hdrstart
        end = package.hdrend
        basepath = package.basepath

        return self._getFile(url=basepath, relative=remote, local=local, start=start,
                        reget=None, end=end, checkfunc=checkfunc, copy_local=1,
                        cache=cache,
                        )
 


    def metadataCurrent(self):
        """Check if there is a metadata_cookie and check its age. If the
        age of the cookie is less than metadata_expire time then return true
        else return False"""
        warnings.warn('metadataCurrent() will go away in a future version of Yum.\n \
                       please use withinCacheAge() instead.',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        return self.withinCacheAge(self.metadata_cookie, self.metadata_expire)

    def withinCacheAge(self, myfile, expiration_time):
        """check if any file is older than a certain amount of time. Used for 
           the cachecookie and the mirrorlist
           return True if w/i the expiration time limit
           false if the time limit has expired
           
           Additionally compare the file to age of the newest .repo or yum.conf 
           file. If any of them are newer then invalidate the cache
           """

        # -1 is special and should never get refreshed
        if expiration_time == -1 and os.path.exists(myfile):
            return True
        val = False
        if os.path.exists(myfile):
            cookie_info = os.stat(myfile)
            if cookie_info[8] + expiration_time > time.time():
                val = True
            # WE ARE FROM THE FUTURE!!!!
            elif cookie_info[8] > time.time():
                val = False
            
            # make sure none of our config files for this repo are newer than
            # us
            if cookie_info[8] < int(self.repo_config_age):
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


    def setup(self, cache, mediafunc = None):
        try:
            self.cache = cache
            self.mediafunc = mediafunc
            self.dirSetup()
        except Errors.RepoError, e:
            raise
        if not self.mediafunc and self.mediaid and not self.mirrorlist and not self.baseurl:
            verbose_logger.log(logginglevels.DEBUG_2, "Disabling media repo for non-media-aware frontend")
            self.enabled = False

    def _cachingRepoXML(self, local):
        """ Should we cache the current repomd.xml """
        if self.cache and not os.path.exists(local):
            raise Errors.RepoError, 'Cannot find repomd.xml file for %s' % self
        if self.cache or self.withinCacheAge(self.metadata_cookie,
                                             self.metadata_expire):
            return True
        return False
    
    def _getFileRepoXML(self, local, text=None, grab_can_fail=None):
        """ Call _getFile() for the repomd.xml file. """
        checkfunc = (self._checkRepoXML, (), {})
        try:
            result = self._getFile(relative=self.repoMDFile,
                                   local=local,
                                   copy_local=1,
                                   text=text,
                                   reget=None,
                                   checkfunc=checkfunc,
                                   cache=self.http_caching == 'all')

        except URLGrabError, e:
            if grab_can_fail is None:
                grab_can_fail = 'old_repo_XML' in self._oldRepoMDData
            if grab_can_fail:
                return None
            raise Errors.RepoError, 'Error downloading file %s: %s' % (local, e)
        return result
        
    def _parseRepoXML(self, local, parse_can_fail=None):
        """ Parse the repomd.xml file. """
        try:
            return repoMDObject.RepoMD(self.id, local)
        except Errors.RepoMDError, e:
            if parse_can_fail is None:
                parse_can_fail = 'old_repo_XML' in self._oldRepoMDData
            if parse_can_fail:
                return None
            raise Errors.RepoError, 'Error importing repomd.xml from %s: %s' % (self, e)
        
    def _saveOldRepoXML(self, local):
        """ If we have an older repomd.xml file available, save it out. """
        # Cleanup old trash...
        for fname in glob.glob(self.cachedir + "/*.old.tmp"):
            os.unlink(fname)

        if os.path.exists(local):
            old_local = local + '.old.tmp' # locked, so this is ok
            shutil.copy2(local, old_local)
            xml = self._parseRepoXML(old_local, True)
            self._oldRepoMDData = {'old_repo_XML' : xml, 'local' : local,
                                   'old_local' : old_local, 'new_MD_files' : []}
            return True
        return False
            

    def _revertOldRepoXML(self):
        """ If we have older data available, revert to it. """
        if 'old_repo_XML' not in self._oldRepoMDData:
            self._oldRepoMDData = {}
            return

        # Unique names mean the rename doesn't work anymore.
        for fname in self._oldRepoMDData['new_MD_files']:
            os.unlink(fname)

        old_data = self._oldRepoMDData
        self._oldRepoMDData = {}
        
        if 'old_local' in old_data:
            os.rename(old_data['old_local'], old_data['local'])

        self._repoXML = old_data['old_repo_XML']

        if 'old_MD_files' not in old_data:
            return
        for revert in old_data['old_MD_files']:
            os.rename(revert + '.old.tmp', revert)

    def _doneOldRepoXML(self):
        """ Done with old data, delete it. """
        old_data = self._oldRepoMDData
        self._oldRepoMDData = {}

        if 'old_local' in old_data:
            os.unlink(old_data['old_local'])

        if 'old_MD_files' not in old_data:
            return
        for revert in old_data['old_MD_files']:
            os.unlink(revert + '.old.tmp')
        
    def _get_mdtype_data(self, mdtype, repoXML=None):
        if repoXML is None:
            repoXML = self.repoXML

        if mdtype == 'group' and 'group_gz' in repoXML.fileTypes():
            mdtype = 'group_gz'
        if (mdtype in ['other', 'filelists', 'primary'] and
            self._check_db_version(mdtype + '_db', repoXML=repoXML)):
            mdtype += '_db'

        if repoXML.repoData.has_key(mdtype):
            return (mdtype, repoXML.getData(mdtype))
        return (mdtype, None)

    def _get_mdtype_fname(self, data, compressed=False):
        (r_base, remote) = data.location
        local = self.cachedir + '/' + os.path.basename(remote)

        if compressed: # DB file, we need the uncompressed version
            local = local.replace('.bz2', '')
        return local

    def _groupCheckDataMDNewer(self):
        """ We check the timestamps, if any of the timestamps for the
            "new" data is older than what we have ... we revert. """
        
        if 'old_repo_XML' not in self._oldRepoMDData:
            return True
        old_repo_XML = self._oldRepoMDData['old_repo_XML']
        
        mdtypes = self.retrieved.keys()

        for mdtype in mdtypes:
            (nmdtype, newdata) = self._get_mdtype_data(mdtype)
            (omdtype, olddata) = self._get_mdtype_data(mdtype,
                                                       repoXML=old_repo_XML)
            if olddata is None or newdata is None:
                continue
            if omdtype == nmdtype and olddata.checksum == newdata.checksum:
                continue
            if olddata.timestamp > newdata.timestamp:
                return False
        return True

    def _commonLoadRepoXML(self, text, mdtypes=None):
        """ Common LoadRepoXML for instant and group, returns False if you
            should just return. """
        local  = self.cachedir + '/repomd.xml'
        if self._repoXML is not None:
            return False
    
        if self._cachingRepoXML(local):
            caching = True
            result = local
        else:
            caching = False
            self._saveOldRepoXML(local)
                
            result = self._getFileRepoXML(local, text)
            if result is None:
                # Ignore this as we have a copy
                self._revertOldRepoXML()
                return False
            
            # if we have a 'fresh' repomd.xml then update the cookie
            self.setMetadataCookie()

        self._repoXML = self._parseRepoXML(result)
        if self._repoXML is None:
            self._revertOldRepoXML()
            return False

        if caching:
            return False # Skip any work.

        if not self._groupCheckDataMDNewer():
            self._revertOldRepoXML()
            return False
        return True
        
    def _check_db_version(self, mdtype, repoXML=None):
        if repoXML is None:
            repoXML = self.repoXML
        if repoXML.repoData.has_key(mdtype):
            if DBVERSION == repoXML.repoData[mdtype].dbversion:
                return True
        return False

    def _groupCheckDataMDValid(self, data, dbmdtype, mmdtype, file_check=False):
        """ Check that we already have this data, and that it's valid. Given
            the DB mdtype and the main mdtype (no _db suffix). """

        if data is None:
            return None

        if not file_check:
            compressed = dbmdtype.endswith("_db")
            local = self._get_mdtype_fname(data, compressed)
        else:
            compressed = False
            local = self._get_mdtype_fname(data, False)
            if not os.path.exists(local):
                local = local.replace('.bz2', '')
                compressed = True
        # if we can, make a copy of the system-wide-cache version of this file
        self._preload_md_from_system_cache(os.path.basename(local))
        if not self._checkMD(local, dbmdtype, openchecksum=compressed,
                             data=data, check_can_fail=True):
            return None

        return local

    def _commonRetrieveDataMD(self, mdtypes=None):
        """ Retrieve any listed mdtypes, and revert if there was a failure.
            Also put any of the non-valid mdtype files from the old_repo_XML
            into the delete list, this means metadata can change filename
            without us leaking it. """

        def _mdtype_eq(omdtype, odata, nmdtype, ndata):
            """ Check if two returns from _get_mdtype_data() are equal. """
            if ndata is None:
                return False
            return omdtype == nmdtype and odata.checksum == ndata.checksum

        all_mdtypes = self.retrieved.keys()
        if mdtypes is None:
            mdtypes = all_mdtypes

        reverts = []
        if 'old_repo_XML' not in self._oldRepoMDData:
            old_repo_XML = None
        else:
            old_repo_XML = self._oldRepoMDData['old_repo_XML']
            self._oldRepoMDData['old_MD_files'] = reverts
            
        # Inited twice atm. ... sue me
        self._oldRepoMDData['new_MD_files'] = []
        for mdtype in all_mdtypes:
            (nmdtype, ndata) = self._get_mdtype_data(mdtype)

            if old_repo_XML:
                (omdtype, odata) = self._get_mdtype_data(mdtype,
                                                         repoXML=old_repo_XML)
                local = self._groupCheckDataMDValid(odata, omdtype,mdtype,True)
                if local:
                    if _mdtype_eq(omdtype, odata, nmdtype, ndata):
                        continue # If they are the same do nothing
            
                    # Move this version, we _may_ get a new one.
                    # We delete it on success, revert it back on failure.
                    # We don't copy as we know it's bad due to above test.
                    os.rename(local, local + '.old.tmp')
                    reverts.append(local)

            if ndata is None: # Doesn't exist in this repo
                continue

            if mdtype not in mdtypes:
                continue

            # No old repomd data, but we might still have uncompressed MD
            if self._groupCheckDataMDValid(ndata, nmdtype, mdtype):
                continue
            
            if not self._retrieveMD(nmdtype, retrieve_can_fail=True):
                self._revertOldRepoXML()
                return False

            local = self._get_mdtype_fname(ndata, False)
            if nmdtype.endswith("_db"): # Uncompress any .sqlite.bz2 files
                dl_local = local
                local = local.replace('.bz2', '')
                misc.bunzipFile(dl_local, local)
                os.unlink(dl_local)
            self._oldRepoMDData['new_MD_files'].append(local)

        self._doneOldRepoXML()
        return True

    def _instantLoadRepoXML(self, text=None):
        """ Retrieve the new repomd.xml from the repository, then check it
            and parse it. If it fails revert.
            Mostly traditional behaviour. """
        if self._commonLoadRepoXML(text):
            self._commonRetrieveDataMD([])

    def _groupLoadRepoXML(self, text=None, mdtypes=None):
        """ Retrieve the new repomd.xml from the repository, then check it
            and parse it. If it fails we revert to the old version and pretend
            that is fine. If the new repomd.xml requires new version of files
            that we have, like updateinfo.xml, we download those too and if any
            of those fail, we again revert everything and pretend old data is
            good. """

        if self._commonLoadRepoXML(text):
            self._commonRetrieveDataMD(mdtypes)

    def _loadRepoXML(self, text=None):
        """retrieve/check/read in repomd.xml from the repository"""
        try:
            if self.mdpolicy in ["instant"]:
                return self._instantLoadRepoXML(text)
            if self.mdpolicy in ["group:all"]:
                return self._groupLoadRepoXML(text)
            if self.mdpolicy in ["group:main"]:
                return self._groupLoadRepoXML(text, ["primary", "group",
                                                     "filelists", "updateinfo"])
            if self.mdpolicy in ["group:small"]:
                return self._groupLoadRepoXML(text, ["primary", "updateinfo"])
            if self.mdpolicy in ["group:primary"]:
                return self._groupLoadRepoXML(text, ["primary"])
        except KeyboardInterrupt:
            self._revertOldRepoXML() # Undo metadata cookie?
            raise
        raise Errors.RepoError, 'Bad loadRepoXML policy: %s' % (self.mdpolicy)
        
    def _getRepoXML(self):
        if self._repoXML:
            return self._repoXML
        try:
            self._loadRepoXML(text=self)
        except Errors.RepoError, e:
            msg = ("Cannot retrieve repository metadata (repomd.xml) for repository: %s. " 
                  "Please verify its path and try again" % self )
            raise Errors.RepoError, msg
        return self._repoXML
        

    repoXML = property(fget=lambda self: self._getRepoXML(),
                       fset=lambda self, val: setattr(self, "_repoXML", val),
                       fdel=lambda self: setattr(self, "_repoXML", None))

    def _checkRepoXML(self, fo):
        if type(fo) is types.InstanceType:
            filepath = fo.filename
        else:
            filepath = fo

        try:
            repoMDObject.RepoMD(self.id, filepath)
        except Errors.RepoMDError, e:
            raise URLGrabError(-1, 'Error importing repomd.xml for %s: %s' % (self, e))


    def checkMD(self, fn, mdtype, openchecksum=False):
        """check the metadata type against its checksum"""
        return self._checkMD(fn, mdtype, openchecksum)
    
    def _checkMD(self, fn, mdtype, openchecksum=False,
                 data=None, check_can_fail=False):
        """ Internal function, use .checkMD() from outside yum. """

        thisdata = data # So the argument name is nicer
        if thisdata is None:
            thisdata = self.repoXML.getData(mdtype)

        # Note openchecksum means do it after you've uncompressed the data.
        if openchecksum:
            (r_ctype, r_csum) = thisdata.openchecksum # get the remote checksum
        else:
            (r_ctype, r_csum) = thisdata.checksum # get the remote checksum

        if type(fn) == types.InstanceType: # this is an urlgrabber check
            file = fn.filename
        else:
            file = fn

        try:
            l_csum = self._checksum(r_ctype, file) # get the local checksum
        except Errors.RepoError, e:
            if check_can_fail:
                return None
            raise URLGrabError(-3, 'Error performing checksum')

        if l_csum == r_csum:
            return 1
        else:
            if check_can_fail:
                return None
            raise URLGrabError(-1, 'Metadata file does not match checksum')



    def retrieveMD(self, mdtype):
        """base function to retrieve metadata files from the remote url
           returns the path to the local metadata file of a 'mdtype'
           mdtype can be 'primary', 'filelists', 'other' or 'group'."""
        return self._retrieveMD(mdtype)

    def _retrieveMD(self, mdtype, retrieve_can_fail=False):        
        """ Internal function, use .retrieveMD() from outside yum. """
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
            if self._checkMD(local, mdtype, check_can_fail=True):
                self.retrieved[mdtype] = 1
                return local # it's the same return the local one

        try:
            checkfunc = (self.checkMD, (mdtype,), {})
            local = self._getFile(relative=remote, local=local, copy_local=1,
                             checkfunc=checkfunc, reget=None,
                             cache=self.http_caching == 'all')
        except (Errors.NoMoreMirrorsRepoError, Errors.RepoError):
            if retrieve_can_fail:
                return None
            raise
        except URLGrabError, e:
            if retrieve_can_fail:
                return None
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
        if 'group_gz' in self.repoXML.fileTypes():
            return self._retrieveMD('group_gz', retrieve_can_fail=True)
        return self._retrieveMD('group', retrieve_can_fail=True)

    def setCallback(self, callback):
        self.callback = callback
        self._callbacks_changed = True

    def setFailureObj(self, failure_obj):
        self.failure_obj = failure_obj
        self._callbacks_changed = True

    def setMirrorFailureObj(self, failure_obj):
        self.mirror_failure_obj = failure_obj
        self._callbacks_changed = True

    def setInterruptCallback(self, callback):
        self.interrupt_callback = callback
        self._callbacks_changed = True
    def _getMirrorList(self):
        """retrieve an up2date-style mirrorlist file from our mirrorlist url,
           also save the file to the local repo dir and use that if cache expiry
           not expired

           we also s/$ARCH/$BASEARCH/ and move along
           return the baseurls from the mirrorlist file
           """
        returnlist = []
        
        self.mirrorlist_file = self.cachedir + '/' + 'mirrorlist.txt'
        fo = None
        
        cacheok = False
        if self.withinCacheAge(self.mirrorlist_file, self.mirrorlist_expire):
            cacheok = True
            fo = open(self.mirrorlist_file, 'r')
        else:
            url = self.mirrorlist
            scheme = urlparse.urlparse(url)[0]
            if scheme == '':
                url = 'file://' + url
            try:
                fo = urlgrabber.grabber.urlopen(url, proxies=self.proxy_dict)
            except urlgrabber.grabber.URLGrabError, e:
                print "Could not retrieve mirrorlist %s error was\n%s" % (url, e)
                fo = None
        
        if fo is not None:
            try:
                content = fo.readlines()
            except Exception, e:
                print "Could not read mirrorlist %s error was \n%s" %(url, e)
                content = ""
            for line in content:
                if re.match('^\s*\#.*', line) or re.match('^\s*$', line):
                    continue
                mirror = re.sub('\n$', '', line) # no more trailing \n's
                (mirror, count) = re.subn('\$ARCH', '$BASEARCH', mirror)
                returnlist.append(mirror)

            if not self.cache and not cacheok:
                output = open(self.mirrorlist_file, 'w')
                for line in content:
                    output.write(line)
                output.close()

        return returnlist

    def _preload_md_from_system_cache(self, filename):
        """attempts to download the file from the system-wide cache, if possible"""
        if not hasattr(self, 'old_base_cache_dir'):
            return
        if self.old_base_cache_dir == "":
            return
            
        glob_repo_cache_dir=os.path.join(self.old_base_cache_dir, self.id)
        if not os.path.exists(glob_repo_cache_dir):
            return
        if os.path.normpath(glob_repo_cache_dir) == os.path.normpath(self.cachedir):
            return
            
        # copy repomd.xml, cachecookie and mirrorlist.txt
        fn = glob_repo_cache_dir + '/' + filename
        destfn = self.cachedir + '/' + os.path.basename(filename)
        # don't copy it if the copy in our users dir is newer or equal
        if not os.path.exists(fn): 
            return
        if os.path.exists(destfn):
            if os.stat(fn)[stat.ST_CTIME] <= os.stat(destfn)[stat.ST_CTIME]:
                return
        #print 'copying %s to %s' % (fn, destfn)
        shutil.copy2(fn, destfn)


def getMirrorList(mirrorlist, pdict = None):
    warnings.warn('getMirrorList() will go away in a future version of Yum.\n',
            Errors.YumFutureDeprecationWarning, stacklevel=2)    
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

