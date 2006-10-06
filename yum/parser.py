import re
import glob
import shlex
import string
import urlparse
import urlgrabber
import os.path
from ConfigParser import ConfigParser, NoSectionError, NoOptionError

import Errors

#TODO: better handling of recursion
#TODO: ability to handle bare includes (ie. before first [section])
#TODO: avoid include line reordering on write

# The above 3 items are probably handled best by more separation between
# include functionality and ConfigParser. Delegate instead of subclass. See how
# this was done in the previous implementation.

#TODO: problem: interpolation tokens are lost when config files are rewritten
#       - workaround is to not set vars, not sure if this is ok
#       - maybe we should do interpolation at the Option level after all?
#       - preserve original uninterpolated value?
#TODO: separate $var interpolation into YumParser?

class IncludingConfigParser(ConfigParser):

    def __init__(self, vars=None, include="include"):
        """
        @param vars: A dictionary of subsitution variables.
        @param include: Name of option that lists files for inclusion
        """
        self.include = include

        # Dictionary of filenames -> included configparser objects
        self._fns = {}

        # Dictionary of sections -> filenames
        self._included = {}

        self.cwd = None
        ConfigParser.__init__(self, vars)

    def defaults(self):
        """Return a dictionary containing the instance-wide defaults."""
        return self._defaults

    def sections(self):
        """Return a list of the sections available in file and includes."""
        s = self.__sections()
        for included in self._included.keys():
            s.append(included)
        return s

    def has_section(self, section): 
        """Indicates whether the named section is present in 
        the configuration and includes."""
        if section in self.__sections() or section in self._included.keys():
            return True
        else:
            return False

    def has_option(self, section, option):
        if not self.has_section(section):
            raise NoSectionError(section)
        if section in self._included.keys():
            fn = self._included[section]
            return self._fns[fn].has_option(section, option)
        else:
            return ConfigParser.has_option(self,  section, option)
        
    def options(self, section):
        """Return a list of option names for the given section name"""
        if not self.has_section(section):
            raise NoSectionError(section)
        if section in self._included.keys():
            fn = self._included[section]
            return self._fns[fn].options(section)
        else:
            return ConfigParser.options(self,  section)

    def items(self, section):
        if not self.has_section(section):
            raise NoSectionError(section)
        if section in self._included.keys():
            fn = self._included[section]
            return self._fns[fn].items(section)
        else:
            return ConfigParser.items(self, section)

    def remove_section(self, section):
        if not self.has_section(section):
            raise NoSectionError(section)
        if section in self._included.keys():
            fn = self._included[section]
            return self._fns[fn].remove_section(section)
        else:
            return ConfigParser.remove_section(self, section)

    def add_include(self, section, fn):
        """Add a included file to config section"""
        if not self.has_section(section):
            raise NoSectionError(section)
        if not self.has_option(section, self.include):
            raise NoOptionError(self.include, section)
        inc = self.get(section, self.include)
        if fn in shlex.split(inc):
            return
        self._add_include(section, fn)

        
    def remove_include(self, section, fn):
        """Remove an included config parser"""
        if not self.has_section(section):
            raise NoSectionError(section)
        if not self.has_option(section, self.include):
            raise NoOptionError(self.include, section)
        #XXX: raise NoIncludeError???
        if not self._included.has_key(fn):
            return

    def __sections(self):
        return ConfigParser.sections(self) 

    def read(self, filenames):
        for filename in shlex.split(filenames):
            self.cwd = os.path.dirname(os.path.realpath(filename))
            ConfigParser.read(self,filename)
            self._readincludes()

    def readfp(self, fp, filename=None):
        ConfigParser.readfp(self, fp, filename)
        self._readincludes()

    def _add_include(self, section, filename):
        c = IncludingConfigParser(self._defaults)

        # Be aware of URL style includes
        scheme, loc, path, params, qry, frag = urlparse.urlparse(filename,
                'file')

        # Normalise file URLs
        if scheme == 'file':
            filename = path

        # Prepend current directory if absolute path wasn't given
        if scheme == 'file':
            if not filename.startswith(os.path.sep):
                filename = os.path.join(self.cwd, filename)

        c.readfp(urlgrabber.urlopen(filename), filename)

        # Keep track of included sections
        for includesection in c.sections():
            self._included[includesection] = filename
        self._fns[filename] = c

    def _remove_include(self, section, filename):
        inc = self.get(section, self.include)
        filenames = shlex.split(inc)
        if filename in filenames:
            filenames.remove(filename)
        self.set(section, self.include, string.join(filenames, ' '))
        self._included.pop(filename)

    def _readincludes(self):
        for section in ConfigParser.sections(self):
            if self.has_option(section, self.include):
                for filename in shlex.split(self.get(section, self.include)):
                    self._add_include(section, filename)
            
    def get(self, section, option, raw=False, vars=None):
        """Return section from file or included files"""
        if section in self._included:
            fn = self._included[section]
            return self._fns[fn].get(section, option, raw, vars)
        return ConfigParser.get(self, section, option, raw, vars)

    def set(self, section, option, value):
        if section in self._included:
            fn = self._included[section]
            return self._fns[fn].set(section, option, value)
        return ConfigParser.set(self, section, option, value)

    def write(self, fp):
        """Take a file object and write it"""

        # Don't call the parent write() method because it dumps out
        # self._defaults as its own section which isn't desirable here.

        # Write out the items for this file
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key == '__name__':
                    continue
                fp.write("%s = %s\n" % (key, str(value).replace('\n', '\n\t')))
            fp.write("\n")

        # Write out any included files
        for fn in self._fns.keys():
            # Only bother for files since we can't easily write back to much
            # else.
            scheme = urlparse.urlparse(fn, 'file')[0]
            if scheme == 'file':
                inc = open(fn, 'w')
                self._fns[fn].write(inc)

    def _interpolate(self, section, option, rawval, vars):
        '''Perform $var subsitution (this overides the default %(..)s
        subsitution)

        Only the rawval and vars arguments are used. The rest are present for
        compatibility with the parent class.
        '''
        return varReplace(rawval, vars)


class IncludedDirConfigParser(IncludingConfigParser):
    """A conf.d recursive parser - supporting one level of included dirs"""

    def __init__(self, vars=None, includedir=None, includeglob="*.conf",
            include="include"):
        self.includeglob = includeglob
        self.includedir = includedir
        IncludingConfigParser.__init__(self, vars=vars, include=include)

    def read(self, filenames):
        for filename in shlex.split(filenames):
            IncludingConfigParser.read(self,filename)
            self._includedir()

    def _includedir(self):
        for section in ConfigParser.sections(self):
            if self.includedir:
                matches = glob.glob("%s/%s" % (self.includedir,
                    self.includeglob))
                # glob dir, open files, include
                for match in matches:
                    if os.path.exists(match):
                        self._add_include(section, match)

    def add_include(self, section, filename):
        """Add a included file to config section"""
        if not self.has_section(section):
            raise NoSectionError(section)
        self._add_include(section, filename)


_KEYCRE = re.compile(r"\$(\w+)")

def varReplace(raw, vars):
    '''Perform variable replacement

    @param raw: String to perform substitution on.  
    @param vars: Dictionary of variables to replace. Key is variable name
        (without $ prefix). Value is replacement string.
    @return: Input raw string with substituted values.
    '''

    done = []                      # Completed chunks to return

    while raw:
        m = _KEYCRE.search(raw)
        if not m:
            done.append(raw)
            break

        # Determine replacement value (if unknown variable then preserve
        # original)
        varname = m.group(1).lower()
        replacement = vars.get(varname, m.group())

        start, end = m.span()
        done.append(raw[:start])    # Keep stuff leading up to token
        done.append(replacement)    # Append replacement value
        raw = raw[end:]             # Continue with remainder of string

    return ''.join(done)

class ConfigPreProcessor:
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
    
    
    def __init__(self, configfile, vars=None):
        # put the vars away in a helpful place
        self._vars = vars
        
        # set some file-like object attributes for ConfigParser
        # these just make confpp look more like a real file object.
        self.mode = 'r' 
        
        # establish whether to use urlgrabber or urllib
        # we want to use urlgrabber if it supports urlopen
        if hasattr(urlgrabber.grabber, 'urlopen'):
            self._urlresolver = urlgrabber.grabber
        else: 
            self._urlresolver = urllib
        
        
        # first make configfile a url even if it points to 
        # a local file
        scheme = urlparse.urlparse(configfile)[0]
        if scheme == '':
            # check it to make sure it's not a relative file url
            if configfile[0] != '/':
                configfile = os.getcwd() + '/' + configfile
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
        if self._vars:
            return varReplace(line, self._vars)
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
        if fo is not None:
            self.name = absurl
            self._incstack.append( fo )
            self._alreadyincluded.append(absurl)
        else:
            raise Errors.ConfigError, \
                  'Error accessing file for config %s' % (absurl)

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


def _test():
    import sys

    p = IncludingConfigParser()
    p.read(sys.argv[1])

    p.set('one', 'a', '111')
    p.set('three', 'foo', 'bar')

    for section in p.sections():
        print '***', section
        for k, v in p.items(section):
            print '%s = %r' % (k, v)

    p.write(open(sys.argv[1], 'wt'))

if __name__ == '__main__':
    _test()

