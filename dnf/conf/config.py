# dnf configuration classes.
#
# Copyright (C) 2016  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

from dnf.yum import misc
from dnf.i18n import ucd, _
from dnf.pycomp import basestring
from iniparse.compat import ParsingError, RawConfigParser as ConfigParser

import copy
import dnf.conf.parser
import dnf.conf.substitutions
import dnf.const
import dnf.exceptions
import dnf.pycomp
import dnf.util
import logging
import os
import shlex
import types

PRIO_DEFAULT = 10
PRIO_MAINCONFIG = 20
PRIO_AUTOMATICCONFIG = 30
PRIO_REPOCONFIG = 40
PRIO_PLUGINDEFAULT = 50
PRIO_PLUGINCONFIG = 60
PRIO_COMMANDLINE = 70
PRIO_RUNTIME = 80

logger = logging.getLogger('dnf')


class Value(object):
    """Value of an Option consists of an actual value and its priority.
    """
    def __init__(self, value, priority):
        self.value = value
        self.priority = priority

    def __repr__(self):
        return "%s(value=%r, priority=%r)" % (self.__class__.__name__,
                                              self.value, self.priority)


class Option(object):
    """ This class handles a single configuration file option.
        Create subclasses for each type of supported configuration option.
        Each option remembers its default value and can inherit from a parent option
        (e.g. repo.gpgcheck inherits from main.gpgcheck).
        Some options can may be runtimeonly which means they are not read from or
        written to config file.
    """
    def __init__(self, default=None, parent=None, runtimeonly=False):
        self.parent = parent
        self.runtimeonly = runtimeonly
        self.actual = None
        self.default = self._make_value(default, PRIO_DEFAULT)

    def _make_value(self, value, priority):
        if isinstance(value, basestring):
            # try to parse a string (from config file)
            try:
                value = self.parse(value)
            except ValueError as e:
                raise dnf.exceptions.ConfigError('Error parsing "%s": %s' % (value, str(e)))
        if not isinstance(value, Value):
            value = Value(value, priority)
        return value

    def get(self):
        """Get option's value, if not set return parent's value."""
        if self.actual:
            return self.actual.value
        if self.parent:
            return self.parent.get()
        return self.default.value

    def get_priority(self):
        """Get option's priority, if not set return parent's priority."""
        if self.actual:
            return self.actual.priority
        if self.parent:
            return self.parent.get_priority()
        return self.default.priority

    def set(self, value, priority=PRIO_RUNTIME):
        """Set option's value if priority is equal or higher than curent priority."""
        value = self._make_value(value, priority)
        if self.is_default() or self.actual.priority <= value.priority:
            self.actual = value

    def is_default(self):
        """Was value changed from default?"""
        return self.actual is None

    def is_runtimeonly(self):
        """Was value changed from default?"""
        return self.runtimeonly

    def parse(self, strval):
        """Parse the string value to the option's native value."""
        return strval

    def tostring(self):
        """Convert the option's native actual value to a string."""
        val = ('' if self.is_default() or self.actual.value is None
                  else self.actual.value)
        return str(val)


def Inherit(option):
    """Clone an option instance for the purposes of inheritance.
       Inherited instance has the same properties and parent set to
       the input option."""
    clone = copy.copy(option)
    clone.parent = option
    return clone


class ListOption(Option):
    """An option containing a list of strings."""

    def __init__(self, default=None, parent=None, runtimeonly=False):
        if default is None:
            default = []
        super(ListOption, self).__init__(default, parent, runtimeonly)

    def parse(self, strval):
        """Convert a string from the config file to a list, parses
           globdir: paths as foo.d-style dirs.
        """
        # we need to allow for the '\n[whitespace]' continuation - easier
        # to sub the \n with a space and then read the lines
        strval = strval.replace('\n', ' ')
        strval = strval.replace(',', ' ')
        results = []
        for item in strval.split():
            if item.startswith('glob:'):
                thisglob = item.replace('glob:', '')
                results.extend(misc.read_in_items_from_dot_dir(thisglob))
                continue
            results.append(item)

        return results

    def tostring(self):
        val = ('' if self.is_default()
                  else '\n '.join(self.actual.value))
        return val


class UrlOption(Option):
    """An option handles an URL with validation of the URL scheme."""

    def __init__(self, default=None, parent=None, runtimeonly=False,
                 schemes=('http', 'ftp', 'file', 'https'), allow_none=False):
        self.schemes = schemes
        self.allow_none = allow_none
        super(UrlOption, self).__init__(default, parent, runtimeonly)

    def parse(self, url):
        """Parse a url to make sure that it is valid, and in a scheme
        that can be used."""
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
        """Return a user friendly list of the allowed schemes."""
        if len(self.schemes) < 1:
            return 'empty'
        elif len(self.schemes) == 1:
            return self.schemes[0]
        else:
            return '%s or %s' % (', '.join(self.schemes[:-1]), self.schemes[-1])


class UrlListOption(ListOption, UrlOption):
    """Option for handling lists of URLs with validation of the URL scheme."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 schemes=('http', 'ftp', 'file', 'https'), allow_none=False):
        self.schemes = schemes
        self.allow_none = allow_none
        ListOption.__init__(self, default, parent, runtimeonly)

    def parse(self, val):
        """Parse a string containing multiple urls into a list, and
           ensure that they are in a scheme that can be used."""
        strlist = ListOption.parse(self, val)
        return [UrlOption.parse(self, s) for s in strlist]


class PathOption(Option):
    """Option for file path which can validate path existence."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 exists=False, abspath=False):
        self.exists = exists
        self.abspath = abspath
        super(PathOption, self).__init__(default, parent, runtimeonly)

    def parse(self, val):
        """Validate path."""
        if val.startswith('file://'):
            val = val[7:]
        if self.abspath and val[0] != '/':
            raise ValueError("Given path '%s' is not absolute." % val)
        if self.exists and not os.path.exists(va):
            raise ValueError("Given path '%s' does not exist." % val)
        return val


class IntOption(Option):
    """An option representing an integer value."""

    def __init__(self, default=None, parent=None, runtimeonly=False,
                 range_min=None, range_max=None):
        self._range_min = range_min
        self._range_max = range_max
        super(IntOption, self).__init__(default, parent, runtimeonly)

    def parse(self, s):
        """Parse a string containing an integer."""
        try:
            n = int(s)
        except (ValueError, TypeError):
            raise ValueError('invalid integer value')

        if self._range_max is not None and n > self._range_max:
            raise ValueError('Given value [%d] should be less than '
                             'allowed value [%d].' % (n, self._range_max))
        if self._range_min is not None and n < self._range_min:
            raise ValueError('Given value [%d] should be greater than '
                             'allowed value [%d].' % (n, self._range_min))
        return n


class PositiveIntOption(IntOption):
    """An option representing a positive integer value, where 0 can
    have a special representation.
    """
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 range_min=0, range_max=None, names_of_0=[]):
        self._names0 = names_of_0
        super(PositiveIntOption, self).__init__(default, parent, runtimeonly,
                                                range_min, range_max)

    def parse(self, s):
        """Parse a string containing a positive integer, where 0 can
           have a special representation."""
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
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 true_names=('1', 'yes', 'true', 'enabled'),
                 false_names=('0', 'no', 'false', 'disabled')):
        self._true_names = true_names
        self._false_names = false_names
        super(BoolOption, self).__init__(default, parent, runtimeonly)

    def parse(self, s):
        """Parse a string containing a boolean value.  1, yes, and
        true will evaluate to True; and 0, no, and false will evaluate
        to False.  Case is ignored.
        """
        s = s.lower()
        if s in self._false_names:
            return False
        elif s in self._true_names:
            return True
        else:
            raise ValueError('invalid boolean value')

    def tostring(self):
        val = ('' if self.is_default()
                  else (self._true_names[0] if self.actual.value
                                            else self._false_names[0]))
        return val


class FloatOption(Option):
    """An option representing a numeric float value."""

    def parse(self, s):
        """Parse a string containing a numeric float value."""
        try:
            return float(s.strip())
        except (ValueError, TypeError):
            raise ValueError('invalid float value')


class SelectionOption(Option):
    """Handles string values where only specific values are allowed."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 choices=(), mapper={}):
        self._choices = choices
        self._mapper = mapper
        super(SelectionOption, self).__init__(default, parent, runtimeonly)

    def parse(self, s):
        """Parse a string for specific values."""
        if s in self._mapper:
            s = self._mapper[s]
        if s not in self._choices:
            raise ValueError('"%s" is not an allowed value' % s)
        return s


class CaselessSelectionOption(SelectionOption):
    """Mainly for compatibility with :class:`BoolOption`, works like
    :class:`SelectionOption` but lowers input case.
    """
    def parse(self, s):
        """Parse a string for specific values."""
        return super(CaselessSelectionOption, self).parse(s.lower())


class BytesOption(Option):
    """An option representing a value in bytes. The value may be given
    in bytes, kilobytes, megabytes, or gigabytes."""
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

    def __init__(self, section=None, parser=None):
        self._option = {}
        self.section = section
        self.parser = parser

    def __str__(self):
        out = []
        out.append('[%s]' % self.section)
        for name, value in self._options.items():
            out.append('%s: %r' % (name, value))
        return '\n'.join(out)

    def add_option(self, name, optionobj):
        self._option[name] = optionobj
        def prop_get(obj):
            return obj._option[name].get()
        def prop_set(obj, val):
            obj._option[name].set(val)
        setattr(type(self), name, property(prop_get, prop_set))

    def get_option(self, name):
        return self._option.get(name, None)

    def populate(self, parser, section, priority=PRIO_DEFAULT):
        """Set option values from an INI file section."""
        if parser.has_section(section):
            for name in parser.options(section):
                value = parser.get(section, name)
                opt = self.get_option(name)
                if opt and not opt.is_runtimeonly():
                    opt.set(value, priority)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'), ucd(name), ucd(value))

    def config_items(self):
        """Yield (name, value) pairs for every option in the instance."""
        return self._option.items()

    def dump(self):
        """Return a string representing the values of all the
           configuration options.
        """
        output = ['[%s]' % self.section]
        for name, opt in sorted(self.config_items()):
            if not opt.is_runtimeonly():
                val = opt.tostring()
                output.append('%s = %s' % (name, val))

        return '\n'.join(output) + '\n'

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
            if self.section is None:
                raise ValueError("not populated, don't know section")
            section = self.section

        # Updated the ConfigParser with the changed values
        cfg_options = self.parser.options(section)
        for name, option in self.config_items():
            if (not option.is_runtimeonly() and
                        (always is None or name in always or not option.is_default() \
                         or name in cfg_options)):
                self.parser.set(section, name, option.tostring())
        # write the updated ConfigParser to the fileobj.
        self.parser.write(fileobj)

    def write_raw_configfile(self, filename, section_id, substitutions, modify):
        # :api
        """
        filename   - name of config file (.conf or .repo)
        section_id - id of modified section (e.g. main, fedora, updates)
        substitutions - instance of base.conf.substitutions
        modify     - dict of modified options
        """
        ini = iniparse.INIConfig(open(filename))

        # b/c repoids can have $values in them we need to map both ways to figure
        # out which one is which
        if section_id not in ini:
            for sect in ini:
                if dnf.conf.parser.substitute(sect, substitutions) == section_id:
                    section_id = sect

        for name, value in modify.items():
            if isinstance(value, list):
                value = ' '.join(value)
            ini[section_id][name] = value

        fp = open(filename, "w")
        fp.write(str(ini))
        fp.close()


class MainConf(BaseConfig):
    # :api
    """Configuration option definitions for dnf.conf's [main] section."""

    def __init__(self, section='main', parser=None):
        super(MainConf, self).__init__(section, parser)
        self.substitutions = dnf.conf.substitutions.Substitutions()
        # setup different cache and log for non-priviledged users
        if dnf.util.am_i_root():
            cachedir = dnf.const.SYSTEM_CACHEDIR
            logdir = '/var/log'
        else:
            try:
                cachedir = logdir = misc.getCacheDir()
            except (IOError, OSError) as e:
                logger.critical(_('Could not set cachedir: %s'), ucd(e))

        self.add_option('debuglevel',  IntOption(2, range_min=0, range_max=10)) # :api
        self.add_option('errorlevel',  IntOption(2, range_min=0, range_max=10))

        self.add_option('installroot',  PathOption('/', abspath=True)) # :api
        self.add_option('config_file_path',  PathOption(dnf.const.CONF_FILENAME)) # :api
        self.add_option('plugins',  BoolOption(True))
        self.add_option('pluginpath',  ListOption([dnf.const.PLUGINPATH])) # :api
        self.add_option('pluginconfpath',  ListOption([dnf.const.PLUGINCONFPATH])) # :api
        self.add_option('persistdir',  PathOption(dnf.const.PERSISTDIR)) # :api
        self.add_option('recent',  IntOption(7, range_min=0))
        self.add_option('reset_nice',  BoolOption(True))

        self.add_option('cachedir',  PathOption(cachedir)) # :api
        self.add_option('system_cachedir',  PathOption(dnf.const.SYSTEM_CACHEDIR)) # :api

        self.add_option('keepcache',  BoolOption(False))
        self.add_option('logdir',  Option(logdir)) # :api
        self.add_option('reposdir',  ListOption(['/etc/yum.repos.d', '/etc/yum/repos.d', '/etc/distro.repos.d'])) # :api

        self.add_option('debug_solver',  BoolOption(False))

        self.add_option('exclude',  ListOption())
        self.add_option('include',  ListOption())
        self.add_option('fastestmirror',  BoolOption(False))
        self.add_option('proxy',  UrlOption(schemes=('http', 'ftp', 'https', 'socks5', 'socks5h', 'socks4', 'socks4a'), allow_none=True)) # :api
        self.add_option('proxy_username',  Option()) # :api
        self.add_option('proxy_password',  Option()) # :api
        self.add_option('protected_packages', ListOption(
                "dnf glob:/etc/yum/protected.d/*.conf " \
                "glob:/etc/dnf/protected.d/*.conf")) #:api
        self.add_option('username',  Option()) # :api
        self.add_option('password',  Option()) # :api
        self.add_option('installonlypkgs',  ListOption(dnf.const.INSTALLONLYPKGS))
            # NOTE: If you set this to 2, then because it keeps the current kernel it
            # means if you ever install an "old" kernel it'll get rid of the newest one
            # so you probably want to use 3 as a minimum ... if you turn it on.
        self.add_option('installonly_limit',  PositiveIntOption(0, range_min=2, # :api
                                                  names_of_0=["0", "<off>"]))
        self.add_option('tsflags',  ListOption()) # :api

        self.add_option('assumeyes',  BoolOption(False)) # :api
        self.add_option('assumeno',  BoolOption(False))
        self.add_option('defaultyes',  BoolOption(False))
        self.add_option('alwaysprompt',  BoolOption(True))
        self.add_option('diskspacecheck',  BoolOption(True))
        self.add_option('gpgcheck',  BoolOption(False))
        self.add_option('repo_gpgcheck',  BoolOption(False))
        self.add_option('localpkg_gpgcheck',  BoolOption(False))
        self.add_option('obsoletes',  BoolOption(True))
        self.add_option('showdupesfromrepos',  BoolOption(False))
        self.add_option('enabled',  BoolOption(True))
        self.add_option('enablegroups',  BoolOption(True))

        self.add_option('bandwidth',  BytesOption(0))
        self.add_option('minrate',  BytesOption(1000))
        self.add_option('ip_resolve',  CaselessSelectionOption(
                    choices=('ipv4', 'ipv6', 'whatever'),
                    mapper={'4': 'ipv4', '6': 'ipv6'}))
        self.add_option('throttle',  ThrottleOption(0))
        self.add_option('timeout',  SecondsOption(120))
        self.add_option('max_parallel_downloads',  IntOption(None, range_min=1))

        self.add_option('metadata_expire',  SecondsOption(60 * 60 * 48))    # 48 hours
        self.add_option('metadata_timer_sync',  SecondsOption(60 * 60 * 3)) #  3 hours
        self.add_option('disable_excludes',  ListOption())
        self.add_option('multilib_policy',  SelectionOption('best', choices=('best', 'all'))) # :api
        self.add_option('best',  BoolOption(False)) # :api
        self.add_option('install_weak_deps',  BoolOption(True))
        self.add_option('bugtracker_url',  Option(dnf.const.BUGTRACKER))

        self.add_option('color',  SelectionOption('auto', choices=('auto', 'never', 'always'),
                                    mapper={'on' : 'always', 'yes' : 'always',
                                            '1' : 'always', 'true' : 'always',
                                            'off' : 'never', 'no' : 'never',
                                            '0' : 'never', 'false' : 'never',
                                            'tty' : 'auto', 'if-tty' : 'auto'}))
        self.add_option('color_list_installed_older',  Option('bold'))
        self.add_option('color_list_installed_newer',  Option('bold,yellow'))
        self.add_option('color_list_installed_reinstall',  Option('normal'))
        self.add_option('color_list_installed_extra',  Option('bold,red'))
        self.add_option('color_list_available_upgrade',  Option('bold,blue'))
        self.add_option('color_list_available_downgrade',  Option('dim,cyan'))
        self.add_option('color_list_available_reinstall',  Option('bold,underline,green'))
        self.add_option('color_list_available_install',  Option('normal'))
        self.add_option('color_update_installed',  Option('normal'))
        self.add_option('color_update_local',  Option('bold'))
        self.add_option('color_update_remote',  Option('normal'))
        self.add_option('color_search_match',  Option('bold'))

        self.add_option('sslcacert',  PathOption()) # :api
        self.add_option('sslverify',  BoolOption(True)) # :api
        self.add_option('sslclientcert',  Option()) # :api
        self.add_option('sslclientkey',  Option()) # :api
        self.add_option('deltarpm',  BoolOption(True))

        self.add_option('history_record',  BoolOption(True))
        self.add_option('history_record_packages',  ListOption(['dnf', 'rpm']))

        self.add_option('rpmverbosity',  Option('info'))
        self.add_option('strict',  BoolOption(True)) # :api
        self.add_option('clean_requirements_on_remove',  BoolOption(True))
        self.add_option('history_list_view',  SelectionOption('commands',
                             choices=('single-user-commands', 'users', 'commands'),
                             mapper={'cmds': 'commands', 'default': 'commands'}))

        # runtime only options
        self.add_option('downloadonly', BoolOption(False, runtimeonly=True))

    @property
    def get_reposdir(self):
        # :api
        """Returns the value of reposdir"""
        myrepodir = None
        # put repo file into first reposdir which exists or create it
        for rdir in self._get_value('reposdir'):
            if os.path.exists(rdir):
                myrepodir = rdir
                break

        if not myrepodir:
            myrepodir = self._get_value('reposdir')[0]
            dnf.util.ensure_dir(myrepodir)
        return myrepodir

    def search_inside_installroot(self, optname):
        opt = self.get_option(optname)
        prio = opt.get_priority()
        # dont modify paths specified on commandline
        if prio >= PRIO_COMMANDLINE:
            return
        val = opt.get()
        # if it exists inside installroot use it (i.e. adjust configuration)
        # for lists any component counts
        if isinstance(val, list):
            if any(os.path.exists(os.path.join(self.installroot, p.lstrip('/')))
                    for p in val):
                opt.set(Value([self._prepend_installroot_path(p) for p in val], prio))
        elif os.path.exists(os.path.join(self.installroot, val.lstrip('/'))):
            self.prepend_installroot(optname)
            opt.set(Value(self._prepend_installroot_path(val), prio))

    def prepend_installroot(self, optname):
        # :api
        opt = self.get_option(optname)
        prio = opt.get_priority()
        new_path = self._prepend_installroot_path(opt.get())
        opt.set(Value(new_path, prio))

    def _prepend_installroot_path(self, path):
        return dnf.conf.parser.substitute(
                os.path.join(self.installroot, path.lstrip('/')), self.substitutions)

    def configure_from_options(self, opts):
        """Configure parts of CLI from the opts. """

        config_args = ['plugins', 'version', 'config_file_path',
                       'debuglevel', 'errorlevel', 'installroot',
                       'best', 'assumeyes', 'assumeno', 'gpgcheck',
                       'showdupesfromrepos', 'plugins', 'ip_resolve',
                       'rpmverbosity', 'disable_excludes',
                       'color', 'downloadonly']

        for name in config_args:
            value = getattr(opts, name, None)
            if value is not None and value != []:
                confopt = self.get_option(name)
                if confopt:
                    confopt.set(value, dnf.conf.PRIO_COMMANDLINE)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'), ucd(name), ucd(value))

        if hasattr(opts, 'main_setopts'):
            # now set all the non-first-start opts from main from our setopts
            for name, val in opts.main_setopts._get_kwargs():
                opt = self.get_option(name)
                if opt:
                    opt.set(val, dnf.conf.PRIO_COMMANDLINE)
                else:
                    msg ="Main config did not have a %s attr. before setopt"
                    logger.warning(msg, name)

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


    def read(self, filename=None, priority=PRIO_DEFAULT):
        # :api
        if filename is None:
            filename = self.config_file_path
        self.parser = ConfigParser()
        config_pp = dnf.conf.parser.ConfigPreProcessor(filename)
        try:
            self.parser.readfp(config_pp)
        except ParsingError as e:
            raise dnf.exceptions.ConfigError("Parsing file failed: %s" % e)
        self.populate(self.parser, self.section, priority)

        # update to where we read the file from
        self.config_file_path = filename

    @property
    def verbose(self):
        return self.debuglevel >= dnf.const.VERBOSE_LEVEL


class RepoConf(BaseConfig):
    """Option definitions for repository INI file sections."""

    def __init__(self, parent, section=None, parser=None):
        super(RepoConf, self).__init__(section, parser)
        self.add_option('name',  Option()) # :api
        self.add_option('enabled',  Inherit(parent.get_option('enabled')))
        self.add_option('basecachedir',  Inherit(parent.get_option('cachedir')))
        self.add_option('baseurl',  UrlListOption()) # :api
        self.add_option('mirrorlist',  UrlOption()) # :api
        self.add_option('metalink',  UrlOption()) # :api
        self.add_option('mediaid',  Option())
        self.add_option('gpgkey',  UrlListOption())
        self.add_option('exclude',  ListOption())
        self.add_option('include',  ListOption())

        self.add_option('fastestmirror',  Inherit(parent.get_option('fastestmirror')))
        self.add_option('proxy',  Inherit(parent.get_option('proxy'))) # :api
        self.add_option('proxy_username',  Inherit(parent.get_option('proxy_username'))) # :api
        self.add_option('proxy_password',  Inherit(parent.get_option('proxy_password'))) # :api
        self.add_option('username',  Inherit(parent.get_option('username'))) # :api
        self.add_option('password',  Inherit(parent.get_option('password'))) # :api
        self.add_option('protected_packages',
                Inherit(parent.get_option('protected_packages'))) # :api

        self.add_option('gpgcheck',  Inherit(parent.get_option('gpgcheck')))
        self.add_option('repo_gpgcheck',  Inherit(parent.get_option('repo_gpgcheck')))
        self.add_option('enablegroups',  Inherit(parent.get_option('enablegroups')))

        self.add_option('bandwidth',  Inherit(parent.get_option('bandwidth')))
        self.add_option('minrate',  Inherit(parent.get_option('minrate')))
        self.add_option('ip_resolve',  Inherit(parent.get_option('ip_resolve')))
        self.add_option('throttle',  Inherit(parent.get_option('throttle')))
        self.add_option('timeout',  Inherit(parent.get_option('timeout')))
        self.add_option('max_parallel_downloads',  Inherit(parent.get_option('max_parallel_downloads')))

        self.add_option('metadata_expire',  Inherit(parent.get_option('metadata_expire')))
        self.add_option('cost',  IntOption(1000))
        self.add_option('priority',  IntOption(99))

        self.add_option('sslcacert',  Inherit(parent.get_option('sslcacert'))) # :api
        self.add_option('sslverify',  Inherit(parent.get_option('sslverify'))) # :api
        self.add_option('sslclientcert',  Inherit(parent.get_option('sslclientcert'))) # :api
        self.add_option('sslclientkey',  Inherit(parent.get_option('sslclientkey'))) # :api
        self.add_option('deltarpm',  Inherit(parent.get_option('deltarpm')))

        self.add_option('skip_if_unavailable',  BoolOption(True)) # :api

    def configure_from_options(self, opts):
        """Configure repos from the opts. """

        if getattr(opts, 'nogpgcheck', None):
            for optname in ['gpgcheck', 'repo_gpgcheck']:
                opt = self.get_option(optname)
                opt.set(False, dnf.conf.PRIO_RUNTIME)

        if getattr(opts, 'cacheonly', None):
            self.md_only_cached = True

        if self.id in getattr(opts, 'repo_setopts', []):
            for name, val in self.repo_setopts[self.id]._get_kwargs():
                opt = self.get_option(name)
                if opt:
                    opt.set(val, dnf.conf.PRIO_COMMANDLINE)
                else:
                    msg = "Repo %s did not have a %s attr. before setopt"
                    logger.warning(msg, self.id, name)
