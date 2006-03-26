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

import os
import warnings
import rpm
import copy
import urlparse
import sys
from parser import IncludingConfigParser, IncludedDirConfigParser
from ConfigParser import NoSectionError, NoOptionError
import rpmUtils.transaction
import rpmUtils.arch
import Errors
from repos import Repository

class OptionData(object):
    '''
    Simple class to track state for a single option instance.
    '''
    def __init__(self, name, initial_value):
        self.name = name
        self.value = initial_value
        self.parser = None
        self.section = None

class Option(object):
    '''
    This class handles a single Yum configuration file option. Create
    subclasses for each type of supported configuration option.
    
    Python descriptor foo (__get__ and __set__) is used to make option
    definition easy and consise.
    '''

    def __init__(self, default=None):
        self._setattrname()
        self.inherit = False
        self.default = default

    def _setattrname(self):
        '''Calculate the internal attribute name used to store option state in
        configuration instances.
        '''
        self._attrname = '__opt%d' % id(self)

    def __get__(self, obj, objtype):
        '''Called when the option is read (via the descriptor protocol). 

        @param obj: The configuration instance to modify.
        @param objtype: The type of the config instance (not used).
        @return: The parsed option value or the default value if the value
            wasn't set in the configuration file.
        '''
        if obj is None:
            return self
        optdata = getattr(obj, self._attrname, None)
        if optdata == None:
            return None
        else:
            return optdata.value

    def __set__(self, obj, value):
        '''Called when the option is set (via the descriptor protocol). 

        @param obj: The configuration instance to modify.
        @param value: The value to set the option to.
        @return: Nothing.
        '''
        optdata = getattr(obj, self._attrname)
       
        # Only try to parse if its a string
        if isinstance(value, basestring):
            try:
                value = self.parse(value)
            except ValueError, e:
                # Add the field name onto the error
                raise ValueError('Error parsing %r: %s' % (optdata.name,
                    str(e)))

        optdata.value = value

        # Write string value back to parser instance if possible
        if optdata.parser != None:
            strvalue = self.tostring(value)
            optdata.parser.set(optdata.section, optdata.name, strvalue)

    def setup(self, obj, name):
        '''Initialise the option for a config instance. 
        This must be called before the option can be set or retrieved. 

        @param obj: BaseConfig (or subclass) instance.
        @param name: Name of the option.
        '''
        setattr(obj, self._attrname, OptionData(name, self.default))

    def setparser(self, obj, parser, section):
        '''Set the configuration parser for this option. This is required so
        that options can be written back to a configuration file.

        @param obj: BaseConfig (or subclass) instance.
        @param parser: ConfigParser (or subclass) where the option is read from.
        @param section: config file section where the option is from.
        '''
        optdata = getattr(obj, self._attrname)
        optdata.parser = parser
        optdata.section = section

    def clone(self):
        '''Return a safe copy of this Option instance
        '''
        new = copy.copy(self)
        new._setattrname()
        return new

    def parse(self, s):
        '''Parse the string value to the Option's native value.

        @param s: Raw string value to parse.
        @return: Validated native value.
    
        Will raise ValueError if there was a problem parsing the string.
        Subclasses should override this.
        '''
        return s

    def tostring(self, value):
        '''Convert the Option's native value to a string value.

        @param value: Native option value.
        @return: String representation of input.

        This does the opposite of the parse() method above.
        Subclasses should override this.
        '''
        return str(value)

def Inherit(option_obj):
    '''Clone an Option instance for the purposes of inheritance. The returned
    instance has all the same properties as the input Option and shares items
    such as the default value. Use this to avoid redefinition of reused
    options.

    @param option_obj: Option instance to inherit.
    @return: New Option instance inherited from the input.
    '''
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
            return BytesOption.parse(self, s)


class BaseConfig(object):
    '''
    Base class for storing configuration definitions. Subclass when creating
    your own definitons.
    '''

    def __init__(self):
        self._section = None

        for name in self.iterkeys():
            option = self.optionobj(name)
            option.setup(self, name)

    def __str__(self):
        out = []
        out.append('[%s]' % self._section)
        for name, value in self.iteritems():
            out.append('%s: %r' % (name, value))
        return '\n'.join(out)

    def populate(self, parser, section, parent=None):
        '''Set option values from a INI file section.

        @param parser: ConfParser instance (or subclass)
        @param section: INI file section to read use.
        @param parent: Optional parent BaseConfig (or subclass) instance to use
            when doing option value inheritance.
        '''
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
               
            option.setparser(self, parser, section)
            if value is not None:
                setattr(self, name, value)

    def optionobj(cls, name):
        '''Return the Option instance for the given name
        '''
        # Look for Option instances in this class and base classes so that
        # option inheritance works
        for klass in (cls,) + cls.__bases__:
            obj = klass.__dict__.get(name, None)
            if obj is not None:
                break

        if obj is not None and isinstance(obj, Option):
            return obj
        else:
            raise KeyError
    optionobj = classmethod(optionobj)

    def isoption(cls, name):
        '''Return True if the given name refers to a defined option 
        '''
        try:
            cls.optionobj(name)
            return True
        except KeyError:
            return False
    isoption = classmethod(isoption)

    def iterkeys(self):
        '''Yield the names of all defined options in the instance.
        '''
        for name, item in self.iteritems():
            yield name

    def iteritems(self):
        '''Yield (name, value) pairs for every option in the instance.

        The value returned is the parsed, validated option value.
        '''
        # Use dir() so that we see inherited options too
        for name in dir(self):
            if self.isoption(name):
                yield (name, getattr(self, name))

    def getConfigOption(self, option, default=None):
        warnings.warn('getConfigOption() will go away in a future version of Yum.\n'
                'Please access option values as attributes or using getattr().',
                DeprecationWarning)
        if hasattr(self, option):
            return getattr(self, option)
        return default

    def setConfigOption(self, option, value):
        warnings.warn('setConfigOption() will go away in a future version of Yum.\n'
                'Please set option values as attributes or using setattr().',
                DeprecationWarning)
        if hasattr(self, option):
            setattr(self, option, value)
        else:
            raise Errors.ConfigError, 'No such option %s' % option

class EarlyConf(BaseConfig):
    '''
    Configuration option definitions for yum.conf's [main] section that are
    required before the other [main] options can be parsed (mainly due to
    variable substitution).
    '''
    distroverpkg = Option('fedora-release')
    installroot = Option('/')

class YumConf(EarlyConf):
    '''
    Configuration option definitions for yum.conf\'s [main] section.

    Note: inherits options from EarlyConf too.
    '''

    debuglevel = IntOption(2)
    errorlevel = IntOption(2)
    retries = IntOption(10)
    recent = IntOption(7)

    cachedir = Option('/var/cache/yum')
    keepcache = BoolOption(True)
    logfile = Option('/var/log/yum.log')
    reposdir = ListOption(['/etc/yum/repos.d', '/etc/yum.repos.d'])
    syslog_ident = Option()
    syslog_facility = Option('LOG_DAEMON')

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
            'kernel-hugemem', 'kernel-enterprise', 'kernel-bigmem',
            'kernel-devel'])
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
    enable_group_conditionals = BoolOption(True)

    timeout = FloatOption(30.0)

    bandwidth = BytesOption(0)
    throttle = ThrottleOption(0)

    http_caching = SelectionOption('all', ('none', 'packages', 'all'))
    metadata_expire = IntOption(1800)   # time in seconds

class RepoConf(BaseConfig):
    '''
    Option definitions for repository INI file sections.
    '''
    name = Option()
    enabled = Inherit(YumConf.enabled)
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
    '''Parse Yum's main configuration file

    @param configfile: Path to the configuration file to parse (typically
        '/etc/yum.conf').
    @param root: The base path to use for installation (typically '/')
    @return: Populated YumConf instance.
    '''

    # Read up config variables that are needed early to calculate substitution
    # variables
    EarlyConf.installroot.default = root
    earlyconf = EarlyConf()
    confparser = IncludingConfigParser()
    if not os.path.exists(configfile):
        raise Errors.ConfigError, 'No such config file %s' % configfile

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
    '''Parse an INI file section for a repository.

    @param parser: ConfParser or similar to read INI file values from.
    @param section: INI file section to read.
    @param mainconf: ConfParser or similar for yum.conf.
    @return: Repository instance.
    '''

    conf = RepoConf()
    conf.populate(parser, section, mainconf)

    # Ensure that the repo name is set
    if not conf.name:
        conf.name = section
        print >> sys.stderr, \
            'Repository %r is missing name in configuration, using id' % section

    thisrepo = Repository(section)

    # Transfer attributes across
    #TODO: merge RepoConf and Repository 
    for k, v in conf.iteritems():
        if v or not hasattr(thisrepo, k):
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
    '''Calculate the release version for the system.

    @param installroot: The value of the installroot option.
    @param distroverpkg: The value of the distroverpkg option.
    @return: The release version as a string (eg. '4' for FC4)
    '''
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


#def main():
#    mainconf = readMainConfig('/etc/yum.conf', '/') 
#    repoconf = readRepoConfig(mainconf.cfg, 'core', mainconf)
#
#    print `repoconf.name`
#
#if __name__ == '__main__':
#    main()
