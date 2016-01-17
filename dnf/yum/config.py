# Copyright 2002 Duke University
# Copyright (C) 2012-2013  Red Hat, Inc.
#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Configuration parser and default values for yum.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from . import misc
from .misc import read_in_items_from_dot_dir
from dnf.pycomp import basestring
from iniparse.compat import ParsingError, RawConfigParser as ConfigParser

import copy
import dnf.conf.parser
import dnf.conf.substitutions
import dnf.const
import dnf.exceptions
import dnf.pycomp
import dnf.util
import os
import shlex
import types


class Option(object):
    """
    This class handles a single Yum configuration file option. Create
    subclasses for each type of supported configuration option.
    Python descriptor foo (__get__ and __set__) is used to make option
    definition easy and concise.
    """

    def __init__(self, default=None, parse_default=False):
        self._setattrname()
        self.inherit = False
        if parse_default:
            default = self.parse(default)
        self.default = default

    def _setattrname(self):
        """Calculate the internal attribute name used to store option state in
        configuration instances.
        """
        self._attrname = '__opt%d' % id(self)
        self._attrname_deleted = '__opt%d_deleted' % id(self)

    def __get__(self, obj, objtype):
        """Called when the option is read (via the descriptor protocol).

        :param obj: The configuration instance to modify.
        :param objtype: The type of the config instance (not used).
        :return: The parsed option value or the default value if the value
           wasn't set in the configuration file.
        """
        if getattr(obj, self._attrname_deleted, None) is True:
            raise RuntimeError("Option is no longer a part of the conf.")
        if obj is None:
            return self

        return getattr(obj, self._attrname, None)

    def __set__(self, obj, value):
        """Called when the option is set (via the descriptor protocol).

        :param obj: The configuration instance to modify.
        :param value: The value to set the option to.
        """
        # Only try to parse if it's a string
        if isinstance(value, basestring):
            try:
                value = self.parse(value)
            except ValueError as e:
                raise ValueError('Error parsing "%s = %r": %s' % (self._optname,
                                                                 value, str(e)))
        elif isinstance(value, int):
            try:
                value = self.parse_int(value)
            except ValueError as e:
                raise ValueError('Error parsing "%s = %r": %s' % (self._optname,
                                                                 value, str(e)))

        setattr(obj, self._attrname, value)

    def __delete__(self, obj):
        setattr(obj, self._attrname_deleted, True)

    def setup(self, obj, name):
        """Initialise the option for a config instance.
        This must be called before the option can be set or retrieved.

        :param obj: :class:`BaseConfig` (or subclass) instance.
        :param name: Name of the option.
        """
        self._optname = name
        setattr(obj, self._attrname, copy.copy(self.default))

    def clone(self):
        """Return a safe copy of this :class:`Option` instance.

        :return: a safe copy of this :class:`Option` instance
        """
        new = copy.copy(self)
        new._setattrname()
        return new

    def parse(self, val):
        """Parse the string value to the :class:`Option`'s native value.

        :param s: raw string value to parse
        :return: validated native value
        :raise: ValueError if there was a problem parsing the string.
           Subclasses should override this
        """
        return val

    def parse_int(self, val):
        """Parse `n`, ensuring it is a suitable integer value.

        Return parsed value or raise ValueError if it is not suitable.

        """

        return val

    def tostring(self, value):
        """Convert the :class:`Option`'s native value to a string value.  This
        does the opposite of the :func:`parse` method above.
        Subclasses should override this.

        :param value: native option value
        :return: string representation of input
        """
        return str(value)

def Inherit(option_obj):
    """Clone an Option` instance for the purposes of inheritance.

    The returned instance has all the same properties as the input Option and
    shares items such as the default value. Use this to avoid redefinition of
    reused options.

    """
    new_option = option_obj.clone()
    new_option.inherit = True
    return new_option

class ListOption(Option):
    """An option containing a list of strings."""

    def __init__(self, default=None, parse_default=False):
        if default is None:
            default = []
        super(ListOption, self).__init__(default, parse_default)

    def parse(self, s):
        """Convert a string from the config file to a workable list, parses
        globdir: paths as foo.d-style dirs.

        :param s: The string to be converted to a list. Commas and
           whitespace are used as separators for the list
        :return: *s* converted to a list
        """
        # we need to allow for the '\n[whitespace]' continuation - easier
        # to sub the \n with a space and then read the lines
        s = s.replace('\n', ' ')
        s = s.replace(',', ' ')
        results = []
        for item in s.split():
            if item.startswith('glob:'):
                thisglob = item.replace('glob:', '')
                results.extend(read_in_items_from_dot_dir(thisglob))
                continue
            results.append(item)

        return results

    def tostring(self, value):
        """Convert a list of to a string value.  This does the
        opposite of the :func:`parse` method above.

        :param value: a list of values
        :return: string representation of input
        """
        return '\n '.join(value)

class UrlOption(Option):
    """This option handles lists of URLs with validation of the URL
    scheme.
    """

    def __init__(self, default=None, schemes=('http', 'ftp', 'file', 'https'),
            allow_none=False):
        super(UrlOption, self).__init__(default)
        self.schemes = schemes
        self.allow_none = allow_none

    def parse(self, url):
        """Parse a url to make sure that it is valid, and in a scheme
        that can be used.

        :param url: a string containing the url to parse
        :return: *url* if it is valid
        :raises: :class:`ValueError` if there is an error parsing the url
        """
        url = url.strip()

        # Handle the "_none_" special case
        if url.lower() == '_none_':
            if self.allow_none:
                return None
            else:
                raise ValueError('"_none_" is not a valid value')

        # Check that scheme is valid
        s = dnf.pycomp.urlparse.urlparse(url)[0]
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
    """Option for handling lists of URLs with validation of the URL
    scheme.
    """
    def __init__(self, default=None, schemes=('http', 'ftp', 'file', 'https'),
                 parse_default=False):
        super(UrlListOption, self).__init__(default, parse_default)

        # Hold a UrlOption instance to assist with parsing
        self._urloption = UrlOption(schemes=schemes)

    def parse(self, s):
        """Parse a string containing multiple urls into a list, and
        ensure that they are in a scheme that can be used.

        :param s: the string to parse
        :return: a list of strings containing the urls in *s*
        :raises: :class:`ValueError` if there is an error parsing the urls
        """
        out = []
        s = s.replace('\n', ' ')
        s = s.replace(',', ' ')
        items = [item.replace(' ', '%20') for item in shlex.split(s)]
        tmp = []
        for item in items:
            if item.startswith('glob:'):
                thisglob = item.replace('glob:', '')
                tmp.extend(read_in_items_from_dot_dir(thisglob))
                continue
            tmp.append(item)

        for url in super(UrlListOption, self).parse(' '.join(tmp)):
            out.append(self._urloption.parse(url))
        return out


class IntOption(Option):
    """An option representing an integer value."""

    def __init__(self, default=None, range_min=None, range_max=None):
        super(IntOption, self).__init__(default)
        self._range_min = range_min
        self._range_max = range_max

    def parse(self, s):
        """Parse a string containing an integer.

        :param s: the string to parse
        :return: the integer in *s*
        :raises: :class:`ValueError` if there is an error parsing the
           integer
        """
        try:
            val = int(s)
        except (ValueError, TypeError):
            raise ValueError('invalid integer value')
        return self.parse_int(val)

    def parse_int(self, n):
        if self._range_max is not None and n > self._range_max:
            raise ValueError('Out of range integer value.')
        if self._range_min is not None and n < self._range_min:
            raise ValueError('Out of range integer value.')
        return n

class PositiveIntOption(IntOption):
    """An option representing a positive integer value, where 0 can
    have a special representation.
    """
    def __init__(self, default=None, range_min=0, range_max=None,
                 names_of_0=None):
        super(PositiveIntOption, self).__init__(default, range_min, range_max)
        self._names0 = names_of_0

    def parse(self, s):
        """Parse a string containing a positive integer, where 0 can
           have a special representation.

        :param s: the string to parse
        :return: the integer in *s*
        :raises: :class:`ValueError` if there is an error parsing the
           integer
        """
        if s in self._names0:
            return 0
        return super(PositiveIntOption, self).parse(s)

class SecondsOption(Option):
    """An option representing an integer value of seconds, or a human
    readable variation specifying days, hours, minutes or seconds
    until something happens. Works like :class:`BytesOption`.  Note
    that due to historical president -1 means "never", so this accepts
    that and allows the word never, too.

    Valid inputs: 100, 1.5m, 90s, 1.2d, 1d, 0xF, 0.1, -1, never.
    Invalid inputs: -10, -0.1, 45.6Z, 1d6h, 1day, 1y.

    Return value will always be an integer
    """
    MULTS = {'d': 60 * 60 * 24, 'h' : 60 * 60, 'm' : 60, 's': 1}

    def parse(self, s):
        """Parse a string containing an integer value of seconds, or a human
        readable variation specifying days, hours, minutes or seconds
        until something happens. Works like :class:`BytesOption`.  Note
        that due to historical president -1 means "never", so this accepts
        that and allows the word never, too.

        Valid inputs: 100, 1.5m, 90s, 1.2d, 1d, 0xF, 0.1, -1, never.
        Invalid inputs: -10, -0.1, 45.6Z, 1d6h, 1day, 1y.

        :param s: the string to parse
        :return: an integer representing the number of seconds
           specified by *s*
        :raises: :class:`ValueError` if there is an error parsing the string
        """
        if len(s) < 1:
            raise ValueError("no value specified")

        if s == "-1" or s == "never": # Special cache timeout, meaning never
            return -1
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
        except (ValueError, TypeError):
            raise ValueError('invalid value')

        if n < 0:
            raise ValueError("seconds value may not be negative")

        return int(n * mult)

class BoolOption(Option):
    """An option representing a boolean value.  The value can be one
    of 0, 1, yes, no, true, or false.
    """

    def parse(self, s):
        """Parse a string containing a boolean value.  1, yes, and
        true will evaluate to True; and 0, no, and false will evaluate
        to False.  Case is ignored.

        :param s: the string containing the boolean value
        :return: the boolean value contained in *s*
        :raises: :class:`ValueError` if there is an error in parsing
           the boolean value
        """
        s = s.lower()
        if s in ('0', 'no', 'false'):
            return False
        elif s in ('1', 'yes', 'true'):
            return True
        else:
            raise ValueError('invalid boolean value')

    def tostring(self, value):
        """Convert a boolean value to a string value.  This does the
        opposite of the :func:`parse` method above.

        :param value: the boolean value to convert
        :return: a string representation of *value*
        """
        if value:
            return "1"
        else:
            return "0"

class FloatOption(Option):
    """An option representing a numeric float value."""

    def parse(self, s):
        """Parse a string containing a numeric float value.

        :param s: a string containing a numeric float value to parse
        :return: the numeric float value contained in *s*
        :raises: :class:`ValueError` if there is an error parsing
           float value
        """
        try:
            return float(s.strip())
        except (ValueError, TypeError):
            raise ValueError('invalid float value')

class SelectionOption(Option):
    """Handles string values where only specific values are
    allowed.
    """
    def __init__(self, default=None, allowed=(), mapper={}):
        super(SelectionOption, self).__init__(default)
        self._allowed = allowed
        self._mapper = mapper

    def parse(self, s):
        """Parse a string for specific values.

        :param s: the string to parse
        :return: *s* if it contains a valid value
        :raises: :class:`ValueError` if there is an error parsing the values
        """
        if s in self._mapper:
            s = self._mapper[s]
        if s not in self._allowed:
            raise ValueError('"%s" is not an allowed value' % s)
        return s

class CaselessSelectionOption(SelectionOption):
    """Mainly for compatibility with :class:`BoolOption`, works like
    :class:`SelectionOption` but lowers input case.
    """
    def parse(self, s):
        """Parse a string for specific values.

        :param s: the string to parse
        :return: *s* if it contains a valid value
        :raises: :class:`ValueError` if there is an error parsing the values
        """
        return super(CaselessSelectionOption, self).parse(s.lower())

class BytesOption(Option):
    """An option representing a value in bytes. The value may be given
    in bytes, kilobytes, megabytes, or gigabytes.
    """
    # Multipliers for unit symbols
    MULTS = {
        'k': 1024,
        'm': 1024*1024,
        'g': 1024*1024*1024,
    }

    def parse(self, s):
        """Parse a friendly bandwidth option to bytes.  The input
        should be a string containing a (possibly floating point)
        number followed by an optional single character unit. Valid
        units are 'k', 'M', 'G'. Case is ignored. The convention that
        1k = 1024 bytes is used.

        Valid inputs: 100, 123M, 45.6k, 12.4G, 100K, 786.3, 0.
        Invalid inputs: -10, -0.1, 45.6L, 123Mb.

        :param s: the string to parse
        :return: the number of bytes represented by *s*
        :raises: :class:`ValueError` if the option can't be parsed
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
    """An option representing a bandwidth throttle value. See
    :func:`parse` for acceptable input values.
    """

    def parse(self, s):
        """Get a throttle option. Input may either be a percentage or
        a "friendly bandwidth value" as accepted by the
        :class:`BytesOption`.

        Valid inputs: 100, 50%, 80.5%, 123M, 45.6k, 12.4G, 100K, 786.0, 0.
        Invalid inputs: 100.1%, -4%, -500.

        :param s: the string to parse
        :return: the bandwidth represented by *s*. The return value
           will be an int if a bandwidth value was specified, and a
           float if a percentage was given
        :raises: :class:`ValueError` if input can't be parsed
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
    """Base class for storing configuration definitions.

    Subclass when creating your own definitions.

    """

    def __init__(self):
        self._section = None
        self.cfg = None

        for name in self.iterkeys():
            option = self.optionobj(name)
            option.setup(self, name)

    def __str__(self):
        out = []
        out.append('[%s]' % self._section)
        for name, value in self.iteritems():
            out.append('%s: %r' % (name, value))
        return '\n'.join(out)

    def override(self, ovr_dict):
        """Override config values with those from ovr_dict.

        Do nothing about the keys that are not options.
        """
        for (ovr_opt, ovr_val) in ovr_dict.items():
            opt = self.optionobj(ovr_opt, exceptions=False)
            if opt is not None:
                setattr(self, ovr_opt, ovr_val)

    def populate(self, parser, section, parent=None):
        """Set option values from an INI file section.

        :param parser: :class:`ConfigParser` instance (or subclass)
        :param section: INI file section to read use
        :param parent: Optional parent :class:`BaseConfig` (or
            subclass) instance to use when doing option value
            inheritance
        """
        self.cfg = parser
        self._section = section

        if parser.has_section(section):
            opts = set(parser.options(section))
        else:
            opts = set()
        for name in self.iterkeys():
            option = self.optionobj(name)
            value = None
            if name in opts:
                value = parser.get(section, name)
            else:
                # No matching option in this section, try inheriting
                if parent and option.inherit:
                    value = getattr(parent, name)

            if value is not None:
                setattr(self, name, value)

    @classmethod
    def optionobj(cls, name, exceptions=True):
        """Return the :class:`Option` instance for the given name.

        :param cls: the class to return the :class:`Option` instance from
        :param name: the name of the :class:`Option` instance to return
        :param exceptions: defines what action to take if the
           specified :class:`Option` instance does not exist. If *exceptions* is
           True, a :class:`KeyError` will be raised. If *exceptions*
           is False, None will be returned
        :return: the :class:`Option` instance specified by *name*, or None if
           it does not exist and *exceptions* is False
        :raises: :class:`KeyError` if the specified :class:`Option` does not
           exist, and *exceptions* is True
        """
        obj = getattr(cls, name, None)
        if isinstance(obj, Option):
            return obj
        elif exceptions:
            raise KeyError
        else:
            return None

    @classmethod
    def isoption(cls, name):
        """Return True if the given name refers to a defined option.

        :param cls: the class to find the option in
        :param name: the name of the option to search for
        :return: whether *name* specifies a defined option
        """
        return cls.optionobj(name, exceptions=False) is not None

    def iterkeys(self):
        """Yield the names of all defined options in the instance."""

        for name in dir(self):
            if self.isoption(name):
                yield name

    def iteritems(self):
        """Yield (name, value) pairs for every option in the
        instance. The value returned is the parsed, validated option
        value.
        """
        # Use dir() so that we see inherited options too
        for name in self.iterkeys():
            yield (name, getattr(self, name))

    def write(self, fileobj, section=None, always=()):
        """Write out the configuration to a file-like object.

        :param fileobj: File-like object to write to
        :param section: Section name to use. If not specified, the section name
            used during parsing will be used
        :param always: A sequence of option names to always write out.
            Options not listed here will only be written out if they are at
            non-default values. Set to None to dump out all options
        """
        # Write section heading
        if section is None:
            if self._section is None:
                raise ValueError("not populated, don't know section")
            section = self._section

        # Updated the ConfigParser with the changed values
        cfg_options = self.cfg.options(section)
        for name, value in self.iteritems():
            option = self.optionobj(name)
            if always is None or name in always or option.default != value \
               or name in cfg_options:
                self.cfg.set(section, name, option.tostring(value))
        # write the updated ConfigParser to the fileobj.
        self.cfg.write(fileobj)

class YumConf(BaseConfig):
    """Configuration option definitions for yum.conf's [main] section."""

    debuglevel = IntOption(2, 0, 10) # :api
    errorlevel = IntOption(2, 0, 10)

    installroot = Option('/') # :api
    config_file_path = Option(dnf.const.CONF_FILENAME) # :api
    plugins = BoolOption(True)
    pluginpath = ListOption([dnf.const.PLUGINPATH]) # :api
    pluginconfpath = ListOption([dnf.const.PLUGINCONFPATH])  # :api
    persistdir = Option(dnf.const.PERSISTDIR) # :api

    def __init__(self):
        super(YumConf, self).__init__()
        self.substitutions = dnf.conf.substitutions.Substitutions()

    def _var_replace(self, option):
        path = getattr(self, option)
        new_path = dnf.conf.parser.substitute(path, self.substitutions)
        setattr(self, option, new_path)

    def prepend_installroot(self, option):
        # :api
        path = getattr(self, option)
        path = path.lstrip('/')
        setattr(self, option, os.path.join(self.installroot, path))

    @property
    def releasever(self):
        # :api
        return self.substitutions.get('releasever')

    @releasever.setter
    def releasever(self, val):
        # :api
        if val is None:
            self.substitutions.pop('releasever', None)
            return
        self.substitutions['releasever'] = val

    recent = IntOption(7, range_min=0)
    reset_nice = BoolOption(True)

    cachedir = Option(dnf.const.SYSTEM_CACHEDIR) # :api

    keepcache = BoolOption(False)
    logdir = Option('/var/log') # :api
    reposdir = ListOption(['/etc/yum/repos.d', '/etc/yum.repos.d']) # :api

    debug_solver = BoolOption(False)

    exclude = ListOption()
    include = ListOption()
    fastestmirror = BoolOption(False)
    proxy = UrlOption(schemes=('http', 'ftp', 'https', 'socks5', 'socks5h', 'socks4', 'socks4a'), allow_none=True) #:api
    proxy_username = Option() #:api
    proxy_password = Option() #:api
    username = Option() #:api
    password = Option() #:api
    installonlypkgs = ListOption(dnf.const.INSTALLONLYPKGS)
    # NOTE: If you set this to 2, then because it keeps the current kernel it
    # means if you ever install an "old" kernel it'll get rid of the newest one
    # so you probably want to use 3 as a minimum ... if you turn it on.
    installonly_limit = PositiveIntOption(0, range_min=2, # :api
                                          names_of_0=["0", "<off>"])
    tsflags = ListOption() # :api

    assumeyes = BoolOption(False)  # :api
    assumeno = BoolOption(False)
    defaultyes = BoolOption(False)
    alwaysprompt = BoolOption(True)
    diskspacecheck = BoolOption(True)
    gpgcheck = BoolOption(False)
    repo_gpgcheck = BoolOption(False)
    localpkg_gpgcheck = BoolOption(False)
    obsoletes = BoolOption(True)
    showdupesfromrepos = BoolOption(False)
    enabled = BoolOption(True)
    enablegroups = BoolOption(True)

    bandwidth = BytesOption(0)
    minrate = BytesOption(1000)
    ip_resolve = CaselessSelectionOption(
            allowed=('ipv4', 'ipv6', 'whatever'),
            mapper={'4': 'ipv4', '6': 'ipv6'})
    throttle = ThrottleOption(0)
    timeout = SecondsOption(120)
    max_parallel_downloads = IntOption(None, range_min=1)

    metadata_expire = SecondsOption(60 * 60 * 48)    # 48 hours
    metadata_timer_sync = SecondsOption(60 * 60 * 3) #  3 hours
    disable_excludes = ListOption()
    multilib_policy = SelectionOption('best', ('best', 'all')) # :api
    best = BoolOption(False) # :api
    install_weak_deps = BoolOption(True)
    bugtracker_url = Option(dnf.const.BUGTRACKER)

    color = SelectionOption('auto', ('auto', 'never', 'always'),
                            mapper={'on' : 'always', 'yes' : 'always',
                                    '1' : 'always', 'true' : 'always',
                                    'off' : 'never', 'no' : 'never',
                                    '0' : 'never', 'false' : 'never',
                                    'tty' : 'auto', 'if-tty' : 'auto'})
    color_list_installed_older = Option('bold')
    color_list_installed_newer = Option('bold,yellow')
    color_list_installed_reinstall = Option('normal')
    color_list_installed_extra = Option('bold,red')
    color_list_available_upgrade = Option('bold,blue')
    color_list_available_downgrade = Option('dim,cyan')
    color_list_available_reinstall = Option('bold,underline,green')
    color_list_available_install = Option('normal')
    color_update_installed = Option('normal')
    color_update_local = Option('bold')
    color_update_remote = Option('normal')
    color_search_match = Option('bold')

    sslcacert = Option() # :api
    sslverify = BoolOption(True) # :api
    sslclientcert = Option() # :api
    sslclientkey = Option() # :api
    deltarpm = BoolOption(True)

    history_record = BoolOption(True)
    history_record_packages = ListOption(['dnf', 'rpm'])

    rpmverbosity = Option('info')
    strict = BoolOption(True)  # :api
    clean_requirements_on_remove = BoolOption(True)
    history_list_view = SelectionOption('commands',
                                        ('single-user-commands', 'users',
                                         'commands'),
                                        mapper={'cmds': 'commands',
                                                'default': 'commands'})

    def dump(self):
        """Return a string representing the values of all the
        configuration options.

        :return: a string representing the values of all the
           configuration options
        """
        output = '[main]\n'
        # we exclude all vars which start with _ or are in this list:
        excluded_vars = ('cfg',
                         'config_file_path',
                         'disable_excludes',
                         'substitutions')
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            if attr in excluded_vars:
                continue
            try:
                res = getattr(self, attr)
            except RuntimeError:
                output += "(%s deleted)\n" % attr
                continue
            if isinstance(res, types.MethodType):
                continue
            if not res and type(res) not in (type(False), type(0)):
                res = ''
            if isinstance(res, list):
                res = ',\n   '.join(res)
            output = output + '%s = %s\n' % (attr, res)

        return output

    def read(self, filename=None):
        # :api
        if filename is None:
            filename = self.config_file_path
        parser = ConfigParser()
        config_pp = dnf.conf.parser.ConfigPreProcessor(filename)
        try:
            parser.readfp(config_pp)
        except ParsingError as e:
            raise dnf.exceptions.ConfigError("Parsing file failed: %s" % e)
        self.populate(parser, 'main')

        # update to where we read the file from
        self.config_file_path = filename

    @property
    def verbose(self):
        return self.debuglevel >= dnf.const.VERBOSE_LEVEL

class RepoConf(BaseConfig):
    """Option definitions for repository INI file sections."""

    __cached_keys = set()
    def iterkeys(self):
        """Yield the names of all defined options in the instance."""

        ck = self.__cached_keys
        if not isinstance(self, RepoConf):
            ck = set()
        if not ck:
            ck.update(list(BaseConfig.iterkeys(self)))

        for name in self.__cached_keys:
            yield name

    name = Option() # :api
    enabled = Inherit(YumConf.enabled)
    baseurl = UrlListOption() # :api
    mirrorlist = UrlOption() # :api
    metalink = UrlOption() # :api
    mediaid = Option()
    gpgkey = UrlListOption()
    exclude = ListOption()
    include = ListOption()

    fastestmirror = Inherit(YumConf.fastestmirror)
    proxy = Inherit(YumConf.proxy) #:api
    proxy_username = Inherit(YumConf.proxy_username) #:api
    proxy_password = Inherit(YumConf.proxy_password) #:api
    username = Inherit(YumConf.username) #:api
    password = Inherit(YumConf.password) #:api

    gpgcheck = Inherit(YumConf.gpgcheck)
    repo_gpgcheck = Inherit(YumConf.repo_gpgcheck)
    enablegroups = Inherit(YumConf.enablegroups)

    bandwidth = Inherit(YumConf.bandwidth)
    minrate = Inherit(YumConf.minrate)
    ip_resolve = Inherit(YumConf.ip_resolve)
    throttle = Inherit(YumConf.throttle)
    timeout = Inherit(YumConf.timeout)
    max_parallel_downloads = Inherit(YumConf.max_parallel_downloads)

    metadata_expire = Inherit(YumConf.metadata_expire)
    cost = IntOption(1000)
    priority = IntOption(99)

    sslcacert = Inherit(YumConf.sslcacert) # :api
    sslverify = Inherit(YumConf.sslverify) # :api
    sslclientcert = Inherit(YumConf.sslclientcert) # :api
    sslclientkey = Inherit(YumConf.sslclientkey)   # :api
    deltarpm = Inherit(YumConf.deltarpm)

    skip_if_unavailable = BoolOption(True)  # :api


def logdir_fit(current_logdir):
    return current_logdir if dnf.util.am_i_root() else misc.getCacheDir()
