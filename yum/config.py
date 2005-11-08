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

#TODO: docstrings

import os
import rpm
import copy
import urlparse
from parser import IncludingConfigParser, IncludedDirConfigParser
from ConfigParser import NoSectionError, NoOptionError
import rpmUtils.transaction
import rpmUtils.arch
import Errors
from repos import Repository

class OptionData(object):
    def __init__(self, parser, section, name):
        self.parser = parser
        self.section = section
        self.name = name
        self.value = None

class Option(object):

    def __init__(self, default=None):
        self._setattrname()
        self.inherit = False
        self.default = default

    def _setattrname(self):
        self._attrname = '__opt%X' % id(self)

    def __get__(self, obj, objtype):
        if obj is None:
            return self
        optdata = getattr(obj, self._attrname, None)
        if optdata != None and optdata.value != None:
            return optdata.value
        else:
            return self.default

    def __set__(self, obj, value):
        optdata = getattr(obj, self._attrname)

        # Only try to parse if its a string
        if isinstance(value, basestring):
            try:
                value = self.parse(value)
            except ValueError, e:
                # Add the field name onto the error
                raise ValueError('Error parsing %r: %s' % (optdata.name, str(e)))
    
        optdata.value = value

        # Write string value back to parser instance
        strvalue = self.tostring(value)
        optdata.parser.set(optdata.section, optdata.name, strvalue)

    def setup(self, obj, parser, section, name):
        '''Initialise the option for a config instance. 
        This must be called before the option can be set or retrieved. 

        @param obj: BaseConfig (or subclass) instance.
        @param parser: ConfigParser (or subclass) where the option is read from.
        @param section: config file section where the option is from.
        @param name: Name of the option.
        @return: None
        '''
        setattr(obj, self._attrname, OptionData(parser, section, name))

    def clone(self):
        '''Return a safe copy of this Option instance
        '''
        new = copy.copy(self)
        new._setattrname()
        return new

    def parse(self, s):
        '''Parse the string value to the Option's native value.

        Will raise ValueError if there was a problem parsing the string.
        Subclasses should override this.
        '''
        return s

    def tostring(self, value):
        '''Convert the Option's native value to a string value.

        This does the opposite fo the parse() method above.
        Subclasses should override this.
        '''
        return str(value)

def Inherit(option_obj):
    new_option = option_obj.clone()
    new_option.inherit = True
    return new_option

class ListOption(Option):

    def __init__(self, default=None):
        if default is None:
            default = []
        super(ListOption, self).__init__(default)

    def parse(self, s):
        """Converts a string from the config file to a workable list

        Commas and spaces are used as separators for the list
        """
        # we need to allow for the '\n[whitespace]' continuation - easier
        # to sub the \n with a space and then read the lines
        s = s.replace('\n', ' ')
        s = s.replace(',', ' ')
        return s.split()

    def tostring(self, value):
        return '\n '.join(value)

class UrlOption(Option):
    '''
    This option handles lists of URLs with validation of the URL scheme.
    '''

    def __init__(self, default=None, schemes=('http', 'ftp', 'file', 'https'), 
            allow_none=False):
        super(UrlOption, self).__init__(default)
        self.schemes = schemes
        self.allow_none = allow_none

    def parse(self, url):
        url = url.strip()

        # Handle the "_none_" special case
        if url.lower() == '_none_':
            if self.allow_none:
                return None
            else:
                raise ValueError('"_none_" is not a valid value')

        # Check that scheme is valid
        (s,b,p,q,f,o) = urlparse.urlparse(url)
        if s not in self.schemes:
            raise ValueError('URL must be %s not "%s"' % (self._schemelist(), s))

        return url

    def _schemelist(self):
        '''Return a user friendly list of the allowed schemes
        '''
        if len(self.schemes) < 1:
            return 'empty'
        elif len(self.schemes) == 1:
            return self.schemes[0]
        else:
            return '%s or %s' % (', '.join(self.schemes[:-1]), self.schemes[-1])

class UrlListOption(ListOption):
    '''
    Option for handling lists of URLs with validation of the URL scheme.
    '''

    def __init__(self, default=None, schemes=('http', 'ftp', 'file', 'https')):
        super(UrlListOption, self).__init__(default)

        # Hold a UrlOption instance to assist with parsing
        self._urloption = UrlOption(schemes=schemes)
        
    def parse(self, s):
        out = []
        for url in super(UrlListOption, self).parse(s):
            out.append(self._urloption.parse(url))
        return out


class IntOption(Option):
    def parse(self, s):
        try:
            return int(s)
        except (ValueError, TypeError), e:
            raise ValueError('invalid integer value')

class BoolOption(Option):
    def parse(self, s):
        s = s.lower()
        if s in ('0', 'no', 'false'):
            return False
        elif s in ('1', 'yes', 'true'):
            return True
        else:
            raise ValueError('invalid boolean value')

    def tostring(self, value):
        if value:
            return "yes"
        else:
            return "no"

class FloatOption(Option):
    def parse(self, s):
        try:
            return float(s.strip())
        except (ValueError, TypeError):
            raise ValueError('invalid float value')

class SelectionOption(Option):
    '''Handles string values where only specific values are allowed
    '''
    def __init__(self, default=None, allowed=()):
        super(SelectionOption, self).__init__(default)
        self._allowed = allowed
        
    def parse(self, s):
        if s not in self._allowed:
            raise ValueError('"%s" is not an allowed value' % s)
        return s

class BytesOption(Option):

    # Multipliers for unit symbols
    MULTS = {
        'k': 1024,
        'm': 1024*1024,
        'g': 1024*1024*1024,
    }

    def parse(self, s):
        """Parse a friendly bandwidth option to bytes

        The input should be a string containing a (possibly floating point)
        number followed by an optional single character unit. Valid units are
        'k', 'M', 'G'. Case is ignored.
       
        Valid inputs: 100, 123M, 45.6k, 12.4G, 100K, 786.3, 0
        Invalid inputs: -10, -0.1, 45.6L, 123Mb

        Return value will always be an integer

        1k = 1024 bytes.

        ValueError will be raised if the option couldn't be parsed.
        """
        if len(s) < 1:
            raise ValueError("no value specified")

        if s[-1].isalpha():
            n = s[:-1]
            unit = s[-1].lower()
            mult = self.MULTS.get(unit, None)
            if not mult:
                raise ValueError("unknown unit '%s'" % unit)
        else:
            n = s
            mult = 1
             
        try:
            n = float(n)
        except ValueError:
            raise ValueError("couldn't convert '%s' to number" % n)

        if n < 0:
            raise ValueError("bytes value may not be negative")

        return int(n * mult)

class ThrottleOption(BytesOption):

    def parse(self, s):
        """Get a throttle option. 

        Input may either be a percentage or a "friendly bandwidth value" as
        accepted by the BytesOption.

        Valid inputs: 100, 50%, 80.5%, 123M, 45.6k, 12.4G, 100K, 786.0, 0
        Invalid inputs: 100.1%, -4%, -500

        Return value will be a int if a bandwidth value was specified or a
        float if a percentage was given.

        ValueError will be raised if input couldn't be parsed.
        """
        if len(s) < 1:
            raise ValueError("no value specified")

        if s[-1] == '%':
            n = s[:-1]
            try:
                n = float(n)
            except ValueError:
                raise ValueError("couldn't convert '%s' to number" % n)
            if n < 0 or n > 100:
                raise ValueError("percentage is out of range")
            return n / 100.0
        else:
            return BytesOption.parse(self, optval)


class BaseConfig(object):
    #XXX: document

    def __init__(self):
        self._section = None

    def __str__(self):
        out = []
        out.append('[%s]' % self._section)
        for name, value in self.iteritems():
            out.append('%s: %r' % (name, value))
        return '\n'.join(out)

    def populate(self, parser, section, parent=None):
        self._section = section
        self.cfg = parser           # Keep a reference to the parser

        for name in self.iterkeys():
            option = self.optionobj(name)
            value = None
            try:
                value = parser.get(section, name)
            except (NoSectionError, NoOptionError):
                # No matching option in this section, try inheriting
                if parent and option.inherit:
                    value = getattr(parent, name)
               
            option.setup(self, parser, section, name)
            if value is not None:
                setattr(self, name, value)

    def optionobj(cls, name):
        '''Return the Option instance for the given name
        '''
        return cls.__dict__[name]
    optionobj = classmethod(optionobj)

    def iterkeys(self):
        for name, item in  self.__class__.__dict__.iteritems():
            if isinstance(item, Option):
                yield name

    def iteritems(self):
        for name in self.iterkeys():
            yield (name, getattr(self, name))

class EarlyConf(BaseConfig):

    distroverpkg = Option('fedora-release')
    installroot = Option()

class YumConf(EarlyConf):

    debuglevel = IntOption(2)
    errorlevel = IntOption(2)
    retries = IntOption(10)
    recent = IntOption(7)

    cachedir = Option('/var/cache/yum')
    logfile = Option('/var/log/yum.log')
    reposdir = ListOption(['/etc/yum/repos.d', '/etc/yum.repos.d'])
    syslog_ident = Option()
    syslog_facility = Option()

    commands = ListOption()
    exclude = ListOption()
    failovermethod = Option('roundrobin')
    yumversion = Option('unversioned')
    proxy = UrlOption(schemes=('http', 'ftp', 'https'), allow_none=True)
    proxy_username = Option()
    proxy_password = Option()
    pluginpath = ListOption(['/usr/lib/yum-plugins'])
    installonlypkgs = ListOption(['kernel', 'kernel-bigmem',
            'kernel-enterprise','kernel-smp', 'kernel-modules', 'kernel-debug',
            'kernel-unsupported', 'kernel-source', 'kernel-devel'])
    kernelpkgnames = ListOption(['kernel','kernel-smp', 'kernel-enterprise',
            'kernel-bigmem', 'kernel-BOOT'])
    exactarchlist = ListOption(['kernel', 'kernel-smp', 'glibc',
            'kernel-hugemem', 'kernel-enterprise', 'kernel-bigmem'])
    tsflags = ListOption()

    assumeyes = BoolOption(False)
    alwaysprompt = BoolOption(True)
    exactarch = BoolOption(True)
    tolerant = BoolOption(True)
    diskspacecheck = BoolOption(True)
    overwrite_groups = BoolOption(False)
    keepalive = BoolOption(True)
    gpgcheck = BoolOption(False)
    obsoletes = BoolOption(False)
    showdupesfromrepos = BoolOption(False)
    enabled = BoolOption(True)
    plugins = BoolOption(False)
    enablegroups = BoolOption(True)

    timeout = FloatOption(30.0)

    bandwidth = BytesOption(0)
    throttle = ThrottleOption(0)

    http_caching = SelectionOption('all', ('none', 'packages', 'all'))
    metadata_expire = IntOption(28800)   # time in seconds

class RepoConf(BaseConfig):
   
    name = Option()         #XXX: error out if no name set
    enabled = BoolOption(True)
    baseurl = UrlListOption()
    mirrorlist = UrlOption()
    gpgkey = UrlListOption()
    exclude = ListOption() 
    includepkgs = ListOption() 

    proxy = Inherit(YumConf.proxy)
    proxy_username = Inherit(YumConf.proxy_username)
    proxy_password = Inherit(YumConf.proxy_password)
    retries = Inherit(YumConf.retries)
    failovermethod = Inherit(YumConf.failovermethod)

    gpgcheck = Inherit(YumConf.gpgcheck)
    keepalive = Inherit(YumConf.keepalive)
    enablegroups = Inherit(YumConf.enablegroups)

    bandwidth = Inherit(YumConf.bandwidth)
    throttle = Inherit(YumConf.throttle)
    timeout = Inherit(YumConf.timeout)
    http_caching = Inherit(YumConf.http_caching)
    metadata_expire = Inherit(YumConf.metadata_expire)

def readMainConfig(configfile, root):
    #XXX: document

    # Read up config variables that are needed early to calculate substitution
    # variables
    EarlyConf.installroot.default = root
    earlyconf = EarlyConf()
    confparser = IncludingConfigParser()
    confparser.read(configfile)
    earlyconf.populate(confparser, 'main')

    # Set up substitution vars
    vars = _getEnvVar()
    vars['basearch'] = rpmUtils.arch.getBaseArch()          # FIXME make this configurable??
    vars['arch'] = rpmUtils.arch.getCanonArch()             # FIXME make this configurable??
    vars['releasever'] = _getsysver(earlyconf.installroot, earlyconf.distroverpkg)

    # Read [main] section
    yumconf = YumConf()
    confparser = IncludingConfigParser(vars=vars)
    confparser.read(configfile)
    yumconf.populate(confparser, 'main')

    # Apply the installroot to directory options
    for option in ('cachedir', 'logfile'):
        path = getattr(yumconf, option)
        setattr(yumconf, option, yumconf.installroot + path)
    
    # Check that plugin paths are all absolute
    for path in yumconf.pluginpath:
        if not path.startswith('/'):
            raise Errors.ConfigError("All plugin search paths must be absolute")

    # Add in some extra attributes which aren't actually configuration values 
    yumconf.yumvar = vars
    yumconf.uid = 0
    yumconf.cache = 0
    yumconf.progess_obj = None

    return yumconf

def readRepoConfig(parser, section, mainconf):
    #XXX: document

    conf = RepoConf()
    conf.populate(parser, section, mainconf)

    thisrepo = Repository(section)

    # Transfer attributes across
    #TODO: merge RepoConf and Repository 
    for k, v in conf.iteritems():
        thisrepo.set(k, v)

    # Set attributes not from the config file
    thisrepo.basecachedir = mainconf.cachedir
    thisrepo.yumvar.update(mainconf.yumvar)
    thisrepo.cfg = parser

    return thisrepo

def getOption(conf, section, name, default, option):
    '''Convenience function to retrieve a parsed and converted value from a
    ConfigParser.

    @param conf: ConfigParser instance or similar
    @param section: Section name
    @param name: Option name
    @param default: Value to use if option is missing
    @param option: Option instance to use for conversion.
    @return: The parsed value or default if value was not present.

    Will raise ValueError if the option could not be parsed.
    '''
    try: 
        val = conf.get(section, name)
    except (NoSectionError, NoOptionError):
        return default
    return option.parse(val)


def _getEnvVar():
    '''Return variable replacements from the environment variables YUM0 to YUM9

    The result is intended to be used with parser.varReplace()
    '''
    yumvar = {}
    for num in range(0, 10):
        env = 'YUM%d' % num
        val = os.environ.get(env, '')
        if val:
            yumvar[env.lower()] = val
    return yumvar

def _getsysver(installroot, distroverpkg):
    ts = rpmUtils.transaction.initReadOnlyTransaction(root=installroot)
    ts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    idx = ts.dbMatch('provides', distroverpkg)
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

