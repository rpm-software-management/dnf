#!/usr/bin/python -t
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
# Copyright 2002 Duke University 

import ConfigParser
import sys
import os
import os.path
import urlparse
import types
import urllib
import rpmUtils.transaction
import rpm
import re
import rpmUtils.arch
import Errors
import urlgrabber
import urlgrabber.grabber
import repos


class yumconf:

    def __init__(self, configfile = '/etc/yum.conf'):
        self.cfg = ConfigParser.ConfigParser()
        configh = confpp(configfile)
        try:
            self.cfg.readfp(configh)
        except ConfigParser.MissingSectionHeaderError, e:
            raise Errors.ConfigError,  'Error accessing config file: %s' % configfile
        
        self.repos = repos.RepoStorage() # class of repositories
        
        self.configdata = {} # dict to hold all the data goodies
       
        #defaults -either get them or set them
        
        optionstrings = [('cachedir', '/var/cache/yum'), 
                         ('debuglevel', 2),
                         ('logfile', '/var/log/yum.log'), 
                         ('pkgpolicy', 'newest'),
                         ('errorlevel', 2), 
                         ('syslog_ident', None),
                         ('syslog_facility', 'LOG_USER'),
                         ('distroverpkg', 'fedora-release'),
                         ('bandwidth', None),
                         ('throttle', None),
                         ('retries', 10),
                         ('installroot', '/'),
                         ('commands', []),
                         ('exclude', []),
                         ('yumversion', 'unversioned'),
                         ('installonlypkgs', ['kernel', 'kernel-bigmem', 
                                              'kernel-enterprise','kernel-smp',
                                              'kernel-debug', 'kernel-unsupported', 
                                              'kernel-source']),
                         ('kernelpkgnames', ['kernel','kernel-smp',
                                             'kernel-enterprise', 'kernel-bigmem',
                                             'kernel-BOOT'])]
                         
        optionbools = [('assumeyes', 0),
                       ('exactarch', 1),
                       ('tolerant', 1),
                       ('diskspacecheck', 1),
                       ('overwrite_groups', 0),
                       ('keepalive', 1),
                       ('obsoletes', 0)]

        # not being set from the config file
        # or things that can't be handled like all the rest
        # - but should be in the config class                       
        optionothers = [('uid', 0),
                        ('cache', 0),
                        ('progess_obj', None),
                        ('log' , None),
                        ('filelog', None),
                        ('errorlog', None)]


        # do the strings        
        for (option, default) in optionstrings:
            self.configdata[option] = self._getoption('main', option, default)

        # do the bools
        for (option, default) in optionbools:
            self.configdata[option] = self._getboolean('main', option, default)

        # do the others            
        for (option, default) in optionothers:
            self.configdata[option] = default

       
        # get our variables parsed            
        self.yumvar = self._getEnvVar()
        self.yumvar['basearch'] = rpmUtils.arch.getBaseArch() # FIXME make this configurable??
        self.yumvar['arch'] = rpmUtils.arch.getCanonArch() # FIXME make this configurable??
        # figure out what the releasever really is from the distroverpkg
        self.yumvar['releasever'] = self._getsysver()

        #progress_meter.text_progress_meter(fo=sys.stdout)        
        # weird ones
        for option in ['commands', 'installonlypkgs', 'kernelpkgnames', 'exclude']:
            self.configdata[option] = self._doreplace(self.configdata[option])
            self.configdata[option] = self._parseList(self.configdata[option])

        if len(self.cfg.sections()) > 1:
        
            for section in self.cfg.sections(): # loop through the list of sections
                if section != 'main': # must be a repoid

                    urls = self._getoption(section, 'baseurl', [])
                    name = self._getoption(section, 'name', None)
                    urls = self._doreplace(urls)
                    urls = self._parseList(urls)
                    mirrorlist = self._getoption(section, 'mirrorlist', None)
                    mirrorlist = self._doreplace(mirrorlist) # FIXME it'd be neat if this did something
                    
                    if name is not None and (len(urls) > 0 or mirrorlist is not None):
                        thisrepo = self.repos.add(section)
                        name = self._doreplace(name)
                        thisrepo.set('name', name)

                        # vet the urls
                        goodurls = []
                        for url in urls:
                            (s,b,p,q,f,o) = urlparse.urlparse(url)
                            if s not in ['http', 'ftp', 'file', 'https']:
                                print 'not using ftp, http[s], or file for repos, skipping - %s' % (url)
                                continue
                            else:
                                goodurls.append(url)
                        if len(goodurls) > 0:
                            thisrepo.set('urls', goodurls)                        
                        else:
                            self.repos.delete(section)
                            print 'Error: Cannot find valid baseurl for repo: %s. Skipping' % (section)    
                            continue
                            
                        failmeth = self._getoption(section,'failovermethod')
                        thisrepo.setFailover(failmeth)
                        
                        thisrepo.set('gpgcheck', self._getboolean(section, 'gpgcheck', 0))
                        thisrepo.set('enabled', self._getboolean(section, 'enabled', 1))

                        # get our proxy information if it is there
                        thisrepo.set('proxy', self._getoption(section, 'proxy', None))
                        thisrepo.set('proxy_username', self._getoption(section, 'proxy_username', None))
                        thisrepo.set('proxy_password', self._getoption(section, 'proxy_password', None))
                        thisrepo.set('keepalive', self._getboolean(section, 'keepalive', 1))                        
                        
                        excludelist = self._getoption(section, 'exclude', [])
                        excludelist = self._doreplace(excludelist)
                        excludelist = self._parseList(excludelist)
                        thisrepo.set('excludes', excludelist)

                        includelist = self._getoption(section, 'includepkgs', [])
                        includelist = self._doreplace(includelist)
                        includelist = self._parseList(includelist)
                        thisrepo.set('includepkgs', includelist)

                        thisrepo.set('enablegroups', self._getboolean(section, 'enablegroups', 1))
                        cache = os.path.join(self.getConfigOption('cachedir'), section)
                        pkgdir = os.path.join(cache, 'packages')
                        hdrdir = os.path.join(cache, 'headers')
                        thisrepo.set('cache', cache)
                        thisrepo.set('pkgdir', pkgdir)
                        thisrepo.set('hdrdir', hdrdir)
                    else:
                        print 'Error: Cannot find baseurl or name for repo: %s. Skipping' % (section)    
        else:
            raise Errors.ConfigError, \
                    'Insufficient repository config. No repositories Found/Enabled. Aborting.'


           
    def _getoption(self, section, option, default=None):
        """section  - section of config
           option - option from section
           default - if there is no setting
           """
        try:
            return self.cfg.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError), e:
            return default

    def _getboolean(self, section, option, default=None):
        """section  - section of config
           option - option from section
           default - if there is no setting
           """
        try:
            return self.cfg.getboolean(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError), e:            
            return default
                
    def listConfigOptions(self):
        """return list of options available for global config"""
        return self.configdata.keys()
        
    def setConfigOption(self, option, value):
        """option, value to set for global config options"""
        try:
            self.configdata[option] = value
        except KeyError:
            raise Errors.ConfigError, 'No such option %s' % option

    def getConfigOption(self, option, default=None):
        """gets global config setting, takes optional default value"""
        try:
            return self.configdata[option]
        except KeyError:
            return None


    def _getsysver(self):
        ts = rpmUtils.transaction.initReadOnlyTransaction()
        ts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
        idx = ts.dbMatch('provides', self.getConfigOption('distroverpkg'))
        # we're going to take the first one - if there is more than one of these
        # then the user needs a beating
        if idx.count() == 0:
            releasever = 'Null'
        else:
            hdr = idx.next()
            releasever = hdr['version']
            del hdr
        del idx
        del ts
        return releasever
    
    def _getEnvVar(self):
        yumvar = {}
        for num in range(0, 10):
            env='YUM%s' % num
            var='$%s' % env
            yumvar[num] = os.environ.get(env, var)
        
        return yumvar

    def _parseList(self, value):
        if type(value) is types.ListType:
            return value
            
        listvalue = []
        # we need to allow for the '\n[whitespace]' continuation - easier
        # to sub the \n with a space and then read the lines
        slashnrepl = re.compile('\n')
        commarepl = re.compile(',')
        (value, count) = slashnrepl.subn(' ', value)
        (value, count) = commarepl.subn(' ', value)
        listvalue = value.split()
        return listvalue
        
    def _doreplace(self, thing):
        """ do the replacement of yumvar, release, arch and basearch on any 
            string or list  passed to it - returns whatever you passed"""
        
        if thing is None:
            return thing

        if type(thing) is types.StringType:
            shortlist = []
            shortlist.append(thing)
            
        if type(thing) is types.ListType:
            shortlist = thing
        
        basearch_reg = re.compile('\$basearch')
        arch_reg = re.compile('\$arch')
        releasever_reg = re.compile('\$releasever')
        yumvar_reg = {}

        for num in range(0,10):
            env = '\$YUM%s' % num
            yumvar_reg[num] = re.compile(env)

        returnlist = []        
        for string in shortlist:
            (string, count) = basearch_reg.subn(self.yumvar['basearch'], string)
            (string, count) = arch_reg.subn(self.yumvar['arch'], string)
            (string, count) = releasever_reg.subn(self.yumvar['releasever'], string)
            for num in range(0,10):
                (string, count) = yumvar_reg[num].subn(self.yumvar[num], string)
            returnlist.append(string)
            
        if type(thing) is types.StringType:
            thing = returnlist[0]
        
        if type(thing) is types.ListType:
            thing = returnlist
            
        return thing


class confpp:
    """
    ConfigParser Include Pre-Processor
    
        File-like Object capable of pre-processing include= lines for
        a ConfigParser. 
        
        The readline function expands lines matching include=(url)
        into lines from the url specified. Includes may occur in
        included files as well. 
        
        Suggested Usage:
            cfg = ConfigParser.ConfigParser()
            fileobj = confpp( fileorurl )
            cfg.readfp(fileobj)
    """
    
    
    def __init__(self, configfile):
        # set some file-like object attributes for ConfigParser
        # these just make confpp look more like a real file object.
        self.mode = 'r' 
        
        # establish whether to use urlgrabber or urllib
        # we want to use urlgrabber if it supports urlopen
        if hasattr(urlgrabber.grabber,'urlopen'):   self._urlresolver = urlgrabber.grabber
        else: self._urlresolver = urllib
        
        # first make configfile a url even if it points to 
        # a local file
        scheme = urlparse.urlparse(configfile)[0]
        if scheme == '':
            url = 'file://' + configfile
        else:
            url = configfile
        
        # these are used to maintain the include stack and check
        # for recursive/duplicate includes
        self._incstack = []
        self._alreadyincluded = []
        
        # _pushfile will return None if he couldn't open the file
        fo = self._pushfile( url )
        if fo is None: 
            raise Errors.ConfigError, 'Error accessing file: %s' % url
        
    def readline( self, size=0 ):
        """
        Implementation of File-Like Object readline function. This should be
        the only function called by ConfigParser according to the python docs.
        We maintain a stack of real FLOs and delegate readline calls to the 
        FLO on top of the stack. When EOF occurs on the topmost FLO, it is 
        popped off the stack and the next FLO takes over. include= lines 
        found anywhere cause a new FLO to be opened and pushed onto the top 
        of the stack. Finally, we return EOF when the bottom-most (configfile
        arg to __init__) FLO returns EOF.
        
        Very Technical Pseudo Code:
        
        def confpp.readline() [this is called by ConfigParser]
            open configfile, push on stack
            while stack has some stuff on it
                line = readline from file on top of stack
                pop and continue if line is EOF
                if line starts with 'include=' then
                    error if file is recursive or duplicate
                    otherwise open file, push on stack
                    continue
                else
                    return line
            
            return EOF
        """
        
        # set line to EOF initially. 
        line=''
        while len(self._incstack) > 0:
            # peek at the file like object on top of the stack
            fo = self._incstack[-1]
            line = fo.readline()
            if len(line) > 0:
                m = re.match( r'\s*include\s*=\s*(?P<url>.*)', line )
                if m:
                    url = m.group('url')
                    if len(url) == 0:
                        raise Errors.ConfigError, \
                             'Error parsing config %s: include must specify file to include.' % (self.name)
                    else:
                        # whooohoo a valid include line.. push it on the stack
                        fo = self._pushfile( url )
                else:
                    # line didn't match include=, just return it as is
                    # for the ConfigParser
                    break
            else:
                # the current file returned EOF, pop it off the stack.
                self._popfile()
        
        # at this point we have a line from the topmost file on the stack
        # or EOF if the stack is empty
        return line
    
    
    def _absurl( self, url ):
        """
        Returns an absolute url for the (possibly) relative
        url specified. The base url used to resolve the
        missing bits of url is the url of the file currently
        being included (i.e. the top of the stack).
        """
        
        if len(self._incstack) == 0:
            # it's the initial config file. No base url to resolve against.
            return url
        else:
            return urlparse.urljoin( self.geturl(), url )
    
    
    def _pushfile( self, url ):
        """
        Opens the url specified, pushes it on the stack, and 
        returns a file like object. Returns None if the url 
        has previously been included.
        If the file can not be opened this function exits.
        """
        
        # absolutize this url using the including files url
        # as a base url.
        absurl = self._absurl(url)
        # check if this has previously been included.
        if self._urlalreadyincluded(absurl):
            return None
        try:
            fo = self._urlresolver.urlopen(absurl)
        except urlgrabber.grabber.URLGrabError, e:
            fo = None
        if not fo is None:
            self.name = absurl
            self._incstack.append( fo )
            self._alreadyincluded.append(absurl)
        else:
            raise Errors.ConfigError, \
                  'Error accessing file: Config file %s tried to include %s' % (self.name, absurl)

        return fo
    
    
    def _popfile( self ):
        """
        Pop a file off the stack signaling completion of including that file.
        """
        fo = self._incstack.pop()
        fo.close()
        if len(self._incstack) > 0:
            self.name = self._incstack[-1].geturl()
        else:
            self.name = None
    
    
    def _urlalreadyincluded( self, url ):
        """
        Checks if the url has already been included at all.. this 
        does not necessarily have to be recursive
        """
        for eurl in self._alreadyincluded:
            if eurl == url: return 1
        return 0
    
    
    def geturl(self): return self.name

def main(args):
    file = args[0]
    if len(args) > 1:
        if args[1] == '--dump':
            configh = confpp(file)        
            while 1:
                line = configh.readline()
                if not line: break
                print line,
            sys.exit(0)

    conf = yumconf(configfile = file)                


    for option in conf.listConfigOptions():
        print '%s = %s' % (option, conf.getConfigOption(option))
        
    print '\n\n'
    repositories = conf.repos
    repolist = repositories.sort()
    
    for srvid in repolist:
        repo = repositories.getRepo(srvid)
        print repo
            
        print ''
    
    

if __name__ == "__main__":
        main(sys.argv[1:])
