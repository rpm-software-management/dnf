import re
import copy
import glob
import shlex
import string
import os.path
from ConfigParser import ConfigParser, NoSectionError, NoOptionError

#TODO: problem: interpolation tokens are lost when config files are rewritten
#       - workaround is to not set vars, not sure if this is ok
#       - maybe we should do interpolation at the Option level after all?
#TODO: include'ing of URLs (Yum currently supports this)
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
        return self.defaults

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
        #XXX: support multiple filenames
        for filename in shlex.split(filenames):
            self.cwd = os.path.dirname(os.path.realpath(filename))
            ConfigParser.read(self,filename)
            self._readincludes()

    def _add_include(self, section, filename):
        c = IncludingConfigParser(self._defaults)
        if not filename.startswith(os.path.sep):
            filename = os.path.join(self.cwd, filename)
        c.read(filename)
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
            inc = open(fn, 'w')
            self._fns[fn].write(inc)

    _KEYCRE = re.compile(r"\$(\w+)")

    def _interpolate(self, section, option, rawval, vars):
        '''Perform $var subsitution (this overides the default %(..)s subsitution)

        Only the rawval and vars arguments are used. The rest are present for
        compatibility with the parent class.
        '''
        done = []                           # Completed chunks to return

        while rawval:
            m = self._KEYCRE.search(rawval)
            if not m:
                done.append(rawval)
                break

            # Determine replacement value (if unknown variable then preserve original)
            varname = m.group(1).lower()
            replacement = vars.get(varname, m.group())

            start, end = m.span()
            done.append(rawval[:start])     # Keep stuff leading up to token
            done.append(replacement)        # Append replacement value
            rawval = rawval[end:]           # Continue with remainder of string

        return ''.join(done)


class IncludedDirConfigParser(IncludingConfigParser):
    """A conf.d recursive parser - supporting one level of included dirs"""

    def __init__(self, defaults = None, includedir=None, includeglob="*.conf", include="include"):
        self.includeglob = includeglob
        self.includedir = includedir
        IncludingConfigParser.__init__(self,include=include)

    def read(self, filenames):
        for filename in shlex.split(filenames):
            IncludingConfigParser.read(self,filename)
            self._includedir()

    def _includedir(self):
        for section in ConfigParser.sections(self):
            if self.includedir:
                matches = glob.glob("%s/%s" % (self.includedir, self.includeglob))
                # glob dir, open files, include
                for match in matches:
                    if os.path.exists(match):
                        self._add_include(section, match)

    def add_include(self, section, filename):
        """Add a included file to config section"""
        if not self.has_section(section):
            raise NoSectionError(section)
        self._add_include(section, filename)


