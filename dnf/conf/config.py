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
import iniparse
import logging
import os

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
        Each option remembers its default value and can inherit from a parent
        option (e.g. repo.gpgcheck inherits from main.gpgcheck).
        Some options can may be runtimeonly which means they are not read from or
        written to config file.
    """
    def __init__(self, default=None, parent=None, runtimeonly=False):
        self._parent = parent
        self._runtimeonly = runtimeonly
        self._actual = None
        self._default = self._make_value(default, PRIO_DEFAULT)

    def _make_value(self, value, priority):
        if isinstance(value, basestring):
            # try to parse a string (from config file)
            try:
                value = self._parse(value)
            except (ValueError, NotImplementedError) as e:
                raise dnf.exceptions.ConfigError(_("Error parsing '%s': %s")
                                                 % (value, str(e)),
                                                 raw_error=str(e))
        if not isinstance(value, Value):
            value = Value(value, priority)
        return value

    def _get(self):
        """Get option's value, if not set return parent's value."""
        if self._actual:
            return self._actual.value
        if self._parent:
            return self._parent._get()
        return self._default.value

    def _get_priority(self):
        """Get option's priority, if not set return parent's priority."""
        if self._actual:
            return self._actual.priority
        if self._parent:
            return self._parent._get_priority()
        return self._default.priority

    def _set(self, value, priority=PRIO_RUNTIME):
        """Set option's value if priority is equal or higher
           than curent priority."""
        value = self._make_value(value, priority)
        if self._is_default() or self._actual.priority <= value.priority:
            self._actual = value

    def _is_default(self):
        """Was value changed from default?"""
        return self._actual is None

    def _is_runtimeonly(self):
        """Was value changed from default?"""
        return self._runtimeonly

    def _parse(self, strval):
        """Parse the string value to the option's native value."""
        # pylint: disable=R0201
        return strval

    def _tostring(self):
        """Convert the option's native actual value to a string."""
        val = ('' if self._is_default() or self._actual.value is None
               else self._actual.value)
        return str(val)


def inherit(option):
    """Clone an option instance for the purposes of inheritance.
       inherited instance has the same properties and parent set to
       the input option."""
    clone = copy.copy(option)
    clone._parent = option
    clone._actual = None
    return clone


class ListOption(Option):
    """An option containing a list of strings."""

    def __init__(self, default=None, parent=None, runtimeonly=False):
        if default is None:
            default = []
        super(ListOption, self).__init__(default, parent, runtimeonly)

    def _parse(self, strval):
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

    def _tostring(self):
        val = ('' if self._is_default()
               else '\n '.join(self._actual.value))
        return val


class ListAppendOption(ListOption):
    """A list option which appends not sets values."""

    def _set(self, value, priority=PRIO_RUNTIME):
        """Set option's value if priority is equal or higher
           than curent priority."""
        if self._is_default():
            super(ListAppendOption, self)._set(value, priority)
        else:
            # append
            new = self._make_value(value, priority)
            self._actual = Value(self._actual.value + new.value, priority)


class UrlOption(Option):
    """An option handles an URL with validation of the URL scheme."""

    def __init__(self, default=None, parent=None, runtimeonly=False,
                 schemes=('http', 'ftp', 'file', 'https'), allow_none=False):
        self._schemes = schemes
        self._allow_none = allow_none
        super(UrlOption, self).__init__(default, parent, runtimeonly)

    def _parse(self, url):
        """Parse a url to make sure that it is valid, and in a scheme
        that can be used."""
        url = url.strip()

        # Handle the "_none_" special case
        if url.lower() == '_none_':
            if self._allow_none:
                return None
            else:
                raise ValueError(_('"_none_" is not a valid value'))

        # Check that scheme is valid
        s = dnf.pycomp.urlparse.urlparse(url)[0]
        if s not in self._schemes:
            raise ValueError(_("URL must be %s not '%s'")
                             % (self._schemelist(), s))

        return url

    def _schemelist(self):
        """Return a user friendly list of the allowed schemes."""
        if len(self._schemes) < 1:
            return 'empty'
        elif len(self._schemes) == 1:
            return self._schemes[0]
        else:
            return '%s or %s' % (', '.join(self._schemes[:-1]), self._schemes[-1])


class UrlListOption(ListOption, UrlOption):
    """Option for handling lists of URLs with validation of the URL scheme."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 schemes=('http', 'ftp', 'file', 'https'), allow_none=False):
        UrlOption.__init__(self, default, parent, runtimeonly,
                           schemes, allow_none)
        ListOption.__init__(self, default, parent, runtimeonly)

    def _parse(self, val):
        """Parse a string containing multiple urls into a list, and
           ensure that they are in a scheme that can be used."""
        strlist = ListOption._parse(self, val)
        return [UrlOption._parse(self, s) for s in strlist]


class PathOption(Option):
    """Option for file path which can validate path existence."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 exists=False, abspath=False):
        self._exists = exists
        self._abspath = abspath
        super(PathOption, self).__init__(default, parent, runtimeonly)

    def _parse(self, val):
        if val.startswith('file://'):
            val = val[7:]
        if self._abspath and val[0] != '/':
            raise ValueError(_("given path '%s' is not absolute.") % val)
        if self._exists and not os.path.exists(val):
            raise ValueError(_("given path '%s' does not exist.") % val)
        return val


class IntOption(Option):
    """An option representing an integer value."""

    def __init__(self, default=None, parent=None, runtimeonly=False,
                 range_min=None, range_max=None):
        self._range_min = range_min
        self._range_max = range_max
        super(IntOption, self).__init__(default, parent, runtimeonly)

    def _parse(self, s):
        try:
            n = int(s)
        except (ValueError, TypeError):
            raise ValueError(_('invalid integer value'))

        if self._range_max is not None and n > self._range_max:
            raise ValueError(_('given value [%d] should be less than '
                               'allowed value [%d].') % (n, self._range_max))
        if self._range_min is not None and n < self._range_min:
            raise ValueError(_('given value [%d] should be greater than '
                               'allowed value [%d].') % (n, self._range_min))
        return n


class PositiveIntOption(IntOption):
    """An option representing a positive integer value, where 0 can
    have a special representation.
    """
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 range_min=0, range_max=None, names_of_0=None):
        self._names0 = [] if names_of_0 is None else names_of_0
        super(PositiveIntOption, self).__init__(default, parent, runtimeonly,
                                                range_min, range_max)

    def _parse(self, s):
        if s in self._names0:
            return 0
        return super(PositiveIntOption, self)._parse(s)


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

    def _parse(self, s):
        if len(s) < 1:
            raise ValueError(_("no value specified"))

        if s == "-1" or s == "never": # Special cache timeout, meaning never
            return -1
        if s[-1].isalpha():
            n = s[:-1]
            unit = s[-1].lower()
            mult = self.MULTS.get(unit, None)
            if not mult:
                raise ValueError(_("unknown unit '%s'") % unit)
        else:
            n = s
            mult = 1

        try:
            n = float(n)
        except (ValueError, TypeError):
            raise ValueError(_("invalid value '%s'") % s)

        if n < 0:
            raise ValueError(_("seconds value '%s' must not be negative") % s)

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

    def _parse(self, s):
        s = s.lower()
        if s in self._false_names:
            return False
        elif s in self._true_names:
            return True
        else:
            raise ValueError(_("invalid boolean value '%s'") % s)

    def _tostring(self):
        val = ('' if self._is_default()
               else (self._true_names[0] if self._actual.value
                     else self._false_names[0]))
        return val


class FloatOption(Option):
    """An option representing a numeric float value."""

    def _parse(self, s):
        try:
            return float(s.strip())
        except (ValueError, TypeError):
            raise ValueError(_("invalid float value '%s'") % s)


class SelectionOption(Option):
    """Handles string values where only specific values are allowed."""
    def __init__(self, default=None, parent=None, runtimeonly=False,
                 choices=(), mapper={}, notimplemented=()):
        # pylint: disable=W0102
        self._choices = choices
        self._mapper = mapper
        self._notimplemented = notimplemented
        super(SelectionOption, self).__init__(default, parent, runtimeonly)

    def _parse(self, s):
        if s in self._mapper:
            s = self._mapper[s]
        if s in self._notimplemented:
            raise NotImplementedError(_("'%s' value is not implemented") % s)
        if s not in self._choices:
            raise ValueError(_("'%s' is not an allowed value") % s)
        return s


class CaselessSelectionOption(SelectionOption):
    """Mainly for compatibility with :class:`BoolOption`, works like
    :class:`SelectionOption` but lowers input case.
    """
    def _parse(self, s):
        return super(CaselessSelectionOption, self)._parse(s.lower())


class BytesOption(Option):
    """An option representing a value in bytes. The value may be given
    in bytes, kilobytes, megabytes, or gigabytes."""
    # Multipliers for unit symbols
    MULTS = {
        'k': 1024,
        'm': 1024*1024,
        'g': 1024*1024*1024,
    }

    def _parse(self, s):
        """Parse a friendly bandwidth option to bytes.  The input
        should be a string containing a (possibly floating point)
        number followed by an optional single character unit. Valid
        units are 'k', 'M', 'G'. Case is ignored. The convention that
        1k = 1024 bytes is used.

        Valid inputs: 100, 123M, 45.6k, 12.4G, 100K, 786.3, 0.
        Invalid inputs: -10, -0.1, 45.6L, 123Mb.
        """
        if len(s) < 1:
            raise ValueError(_("no value specified"))

        if s[-1].isalpha():
            n = s[:-1]
            unit = s[-1].lower()
            mult = self.MULTS.get(unit, None)
            if not mult:
                raise ValueError(_("unknown unit '%s'") % unit)
        else:
            n = s
            mult = 1

        try:
            n = float(n)
        except ValueError:
            raise ValueError(_("couldn't convert '%s' to number") % s)

        if n < 0:
            raise ValueError(_("bytes value '%s' must not be negative") % s)

        return int(n * mult)


class ThrottleOption(BytesOption):
    """An option representing a bandwidth throttle value. See
    :func:`_parse` for acceptable input values.
    """

    def _parse(self, s):
        """Get a throttle option. Input may either be a percentage or
        a "friendly bandwidth value" as accepted by the
        :class:`BytesOption`.

        Valid inputs: 100, 50%, 80.5%, 123M, 45.6k, 12.4G, 100K, 786.0, 0.
        Invalid inputs: 100.1%, -4%, -500.
        """
        if len(s) < 1:
            raise ValueError(_("no value specified"))

        if s[-1] == '%':
            n = s[:-1]
            try:
                n = float(n)
            except ValueError:
                raise ValueError(_("couldn't convert '%s' to number") % s)
            if n < 0 or n > 100:
                raise ValueError(_("percentage '%s' is out of range") % s)
            return n / 100.0
        else:
            return BytesOption._parse(self, s)


class BaseConfig(object):
    """Base class for storing configuration definitions.

       Subclass when creating your own definitions.

    """

    def __init__(self, section=None, parser=None):
        self._option = {}
        self._section = section
        self._parser = parser

    def __str__(self):
        out = []
        out.append('[%s]' % self._section)
        for name, value in self._option.items():
            out.append('%s: %s' % (name, value))
        return '\n'.join(out)

    def _add_option(self, name, optionobj):
        self._option[name] = optionobj
        # pylint: disable=W0212
        def prop_get(obj):
            return obj._option[name]._get()
        def prop_set(obj, val):
            obj._option[name]._set(val)
        setattr(type(self), name, property(prop_get, prop_set))

    def _get_option(self, name):
        return self._option.get(name, None)

    def _get_value(self, name):
        return self._option[name]._get()

    def _set_value(self, name, value, priority=PRIO_RUNTIME):
        return self._option[name]._set(value, priority)

    def _populate(self, parser, section, priority=PRIO_DEFAULT):
        """Set option values from an INI file section."""
        if parser.has_section(section):
            for name in parser.options(section):
                value = parser.get(section, name)
                opt = self._get_option(name)
                if opt and not opt._is_runtimeonly():
                    try:
                        opt._set(value, priority)
                    except dnf.exceptions.ConfigError as e:
                        logger.warning(_('Unknown configuration value: '
                                         '%s=%s; %s'),
                                       ucd(name), ucd(value), e.raw_error)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'),
                                   ucd(name), ucd(value))

    def _config_items(self):
        """Yield (name, value) pairs for every option in the instance."""
        return self._option.items()

    def dump(self):
        # :api
        """Return a string representing the values of all the
           configuration options.
        """
        output = ['[%s]' % self._section]
        for name, opt in sorted(self._config_items()):
            if not opt._is_runtimeonly():
                val = str(opt._get())
                output.append('%s = %s' % (name, val))

        return '\n'.join(output) + '\n'

    def _write(self, fileobj, section=None, always=()):
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
        cfg_options = self._parser.options(section)
        for name, option in self._config_items():
            if (not option._is_runtimeonly() and
                    (always is None or name in always or not option._is_default()
                     or name in cfg_options)):
                self._parser.set(section, name, option._tostring())
        # write the updated ConfigParser to the fileobj.
        self._parser.write(fileobj)

    @staticmethod
    def write_raw_configfile(filename, section_id, substitutions, modify):
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
        # pylint: disable=R0915
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

        self._add_option('debuglevel',
                         IntOption(2, range_min=0, range_max=10)) # :api
        self._add_option('errorlevel', IntOption(2, range_min=0, range_max=10))

        self._add_option('installroot', PathOption('/', abspath=True)) # :api
        self._add_option('config_file_path',
                         PathOption(dnf.const.CONF_FILENAME)) # :api
        self._add_option('plugins', BoolOption(True))
        self._add_option('pluginpath', ListOption([dnf.const.PLUGINPATH])) # :api
        self._add_option('pluginconfpath',
                         ListOption([dnf.const.PLUGINCONFPATH])) # :api
        self._add_option('persistdir', PathOption(dnf.const.PERSISTDIR)) # :api
        self._add_option('recent', IntOption(7, range_min=0))
        self._add_option('reset_nice', BoolOption(True))

        self._add_option('cachedir', PathOption(cachedir)) # :api
        self._add_option('system_cachedir',
                         PathOption(dnf.const.SYSTEM_CACHEDIR)) # :api

        self._add_option('keepcache', BoolOption(False))
        self._add_option('logdir', Option(logdir)) # :api
        self._add_option('reposdir', ListOption(['/etc/yum.repos.d',
                                                 '/etc/yum/repos.d',
                                                 '/etc/distro.repos.d'])) # :api

        self._add_option('debug_solver', BoolOption(False))

        self._add_option('excludepkgs', ListAppendOption())
        self._add_option('includepkgs', ListAppendOption())
        self._add_option('exclude', self._get_option('excludepkgs'))
            # ^ compatibility with yum
        self._add_option('fastestmirror', BoolOption(False))
        self._add_option('proxy', UrlOption(schemes=('http', 'ftp', 'https',
                                                     'socks5', 'socks5h',
                                                     'socks4', 'socks4a'),
                                            allow_none=True)) # :api
        self._add_option('proxy_username', Option()) # :api
        self._add_option('proxy_password', Option()) # :api
        self._add_option('protected_packages',
                         ListOption("dnf glob:/etc/yum/protected.d/*.conf " \
                                    "glob:/etc/dnf/protected.d/*.conf")) #:api
        self._add_option('username', Option()) # :api
        self._add_option('password', Option()) # :api
        self._add_option('installonlypkgs', ListOption(dnf.const.INSTALLONLYPKGS))
            # NOTE: If you set this to 2, then because it keeps the current
            # kernel it means if you ever install an "old" kernel it'll get rid
            # of the newest one so you probably want to use 3 as a minimum
            # ... if you turn it on.
        self._add_option('installonly_limit',
                         PositiveIntOption(0, range_min=2,
                                           names_of_0=["0", "<off>"])) # :api
        self._add_option('tsflags', ListOption()) # :api

        self._add_option('assumeyes', BoolOption(False)) # :api
        self._add_option('assumeno', BoolOption(False))
        self._add_option('defaultyes', BoolOption(False))
        self._add_option('alwaysprompt', BoolOption(True))
        self._add_option('diskspacecheck', BoolOption(True))
        self._add_option('gpgcheck', BoolOption(False))
        self._add_option('repo_gpgcheck', BoolOption(False))
        self._add_option('localpkg_gpgcheck', BoolOption(False))
        self._add_option('obsoletes', BoolOption(True))
        self._add_option('showdupesfromrepos', BoolOption(False))
        self._add_option('enabled', BoolOption(True))
        self._add_option('enablegroups', BoolOption(True))

        self._add_option('bandwidth', BytesOption(0))
        self._add_option('minrate', BytesOption(1000))
        self._add_option('ip_resolve',
                         CaselessSelectionOption(choices=('ipv4', 'ipv6',
                                                          'whatever'),
                                                 mapper={'4': 'ipv4',
                                                         '6': 'ipv6'}))
        self._add_option('throttle', ThrottleOption(0))
        self._add_option('timeout', SecondsOption(120))
        self._add_option('max_parallel_downloads', IntOption(None, range_min=1))

        self._add_option('metadata_expire',
                         SecondsOption(60 * 60 * 48))    # 48 hours
        self._add_option('metadata_timer_sync',
                         SecondsOption(60 * 60 * 3)) #  3 hours
        self._add_option('disable_excludes', ListOption())
        self._add_option('multilib_policy',
                         SelectionOption('best', choices=('best', 'all'))) # :api
        self._add_option('best', BoolOption(False)) # :api
        self._add_option('install_weak_deps', BoolOption(True))
        self._add_option('bugtracker_url', Option(dnf.const.BUGTRACKER))

        self._add_option('color',
                         SelectionOption('auto',
                                         choices=('auto', 'never', 'always'),
                                         mapper={'on': 'always', 'yes' : 'always',
                                                 '1' : 'always', 'true': 'always',
                                                 'off': 'never', 'no':   'never',
                                                 '0':   'never', 'false': 'never',
                                                 'tty': 'auto', 'if-tty': 'auto'})
                        )
        self._add_option('color_list_installed_older', Option('bold'))
        self._add_option('color_list_installed_newer', Option('bold,yellow'))
        self._add_option('color_list_installed_reinstall', Option('normal'))
        self._add_option('color_list_installed_extra', Option('bold,red'))
        self._add_option('color_list_available_upgrade', Option('bold,blue'))
        self._add_option('color_list_available_downgrade', Option('dim,cyan'))
        self._add_option('color_list_available_reinstall',
                         Option('bold,underline,green'))
        self._add_option('color_list_available_install', Option('normal'))
        self._add_option('color_update_installed', Option('normal'))
        self._add_option('color_update_local', Option('bold'))
        self._add_option('color_update_remote', Option('normal'))
        self._add_option('color_search_match', Option('bold'))

        self._add_option('sslcacert', PathOption()) # :api
        self._add_option('sslverify', BoolOption(True)) # :api
        self._add_option('sslclientcert', Option()) # :api
        self._add_option('sslclientkey', Option()) # :api
        self._add_option('deltarpm', BoolOption(True))

        self._add_option('history_record', BoolOption(True))
        self._add_option('history_record_packages', ListOption(['dnf', 'rpm']))

        self._add_option('rpmverbosity', Option('info'))
        self._add_option('strict', BoolOption(True)) # :api
        self._add_option('clean_requirements_on_remove', BoolOption(True))
        self._add_option('history_list_view',
                         SelectionOption('commands',
                                         choices=('single-user-commands',
                                                  'users', 'commands'),
                                         mapper={'cmds': 'commands',
                                                 'default': 'commands'}))

        # runtime only options
        self._add_option('downloadonly', BoolOption(False, runtimeonly=True))

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

    def _search_inside_installroot(self, optname):
        opt = self._get_option(optname)
        prio = opt._get_priority()
        # dont modify paths specified on commandline
        if prio >= PRIO_COMMANDLINE:
            return
        val = opt._get()
        # if it exists inside installroot use it (i.e. adjust configuration)
        # for lists any component counts
        if isinstance(val, list):
            if any(os.path.exists(os.path.join(self._get_value('installroot'),
                                               p.lstrip('/')))
                   for p in val):
                opt._set(Value([self._prepend_installroot_path(p) for p in val],
                               prio))
        elif os.path.exists(os.path.join(self._get_value('installroot'),
                                         val.lstrip('/'))):
            self.prepend_installroot(optname)
            opt._set(Value(self._prepend_installroot_path(val), prio))

    def prepend_installroot(self, optname):
        # :api
        opt = self._get_option(optname)
        prio = opt._get_priority()
        new_path = self._prepend_installroot_path(opt._get())
        opt._set(Value(new_path, prio))

    def _prepend_installroot_path(self, path):
        root_path = os.path.join(self._get_value('installroot'), path.lstrip('/'))
        return dnf.conf.parser.substitute(root_path, self.substitutions)

    def _configure_from_options(self, opts):
        """Configure parts of CLI from the opts. """

        config_args = ['plugins', 'version', 'config_file_path',
                       'debuglevel', 'errorlevel', 'installroot',
                       'best', 'assumeyes', 'assumeno', 'gpgcheck',
                       'showdupesfromrepos', 'plugins', 'ip_resolve',
                       'rpmverbosity', 'disable_excludes',
                       'color', 'downloadonly', 'exclude', 'excludepkgs']

        for name in config_args:
            value = getattr(opts, name, None)
            if value is not None and value != []:
                confopt = self._get_option(name)
                if confopt:
                    confopt._set(value, dnf.conf.PRIO_COMMANDLINE)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'),
                                   ucd(name), ucd(value))

        if hasattr(opts, 'main_setopts'):
            # now set all the non-first-start opts from main from our setopts
            # pylint: disable=W0212
            for name, val in opts.main_setopts._get_kwargs():
                opt = self._get_option(name)
                if opt:
                    opt._set(val, dnf.conf.PRIO_COMMANDLINE)
                else:
                    msg = "Main config did not have a %s attr. before setopt"
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
            filename = self._get_value('config_file_path')
        self._parser = ConfigParser()
        config_pp = dnf.conf.parser.ConfigPreProcessor(filename)
        try:
            self._parser.readfp(config_pp)
        except ParsingError as e:
            raise dnf.exceptions.ConfigError("Parsing file failed: %s" % e)
        self._populate(self._parser, self._section, priority)

        # update to where we read the file from
        self._set_value('config_file_path', filename, priority)

    @property
    def verbose(self):
        return self._get_value('debuglevel') >= dnf.const.VERBOSE_LEVEL


class RepoConf(BaseConfig):
    """Option definitions for repository INI file sections."""

    def __init__(self, parent, section=None, parser=None):
        super(RepoConf, self).__init__(section, parser)
        self._add_option('name', Option()) # :api
        self._add_option('enabled', inherit(parent._get_option('enabled')))
        self._add_option('basecachedir', inherit(parent._get_option('cachedir')))
        self._add_option('baseurl', UrlListOption()) # :api
        self._add_option('mirrorlist', UrlOption()) # :api
        self._add_option('metalink', UrlOption()) # :api
        self._add_option('mediaid', Option())
        self._add_option('gpgkey', UrlListOption())
        self._add_option('excludepkgs', ListAppendOption())
        self._add_option('includepkgs', ListAppendOption())
        self._add_option('exclude', self._get_option('excludepkgs'))
            # ^ compatibility with yum

        self._add_option('fastestmirror',
                         inherit(parent._get_option('fastestmirror')))
        self._add_option('proxy', inherit(parent._get_option('proxy'))) # :api
        self._add_option('proxy_username',
                         inherit(parent._get_option('proxy_username'))) # :api
        self._add_option('proxy_password',
                         inherit(parent._get_option('proxy_password'))) # :api
        self._add_option('username',
                         inherit(parent._get_option('username'))) # :api
        self._add_option('password',
                         inherit(parent._get_option('password'))) # :api
        self._add_option('protected_packages',
                         inherit(parent._get_option('protected_packages'))) # :api

        self._add_option('gpgcheck', inherit(parent._get_option('gpgcheck')))
        self._add_option('repo_gpgcheck',
                         inherit(parent._get_option('repo_gpgcheck')))
        self._add_option('enablegroups',
                         inherit(parent._get_option('enablegroups')))

        self._add_option('bandwidth', inherit(parent._get_option('bandwidth')))
        self._add_option('minrate', inherit(parent._get_option('minrate')))
        self._add_option('ip_resolve', inherit(parent._get_option('ip_resolve')))
        self._add_option('throttle', inherit(parent._get_option('throttle')))
        self._add_option('timeout', inherit(parent._get_option('timeout')))
        self._add_option('max_parallel_downloads',
                         inherit(parent._get_option('max_parallel_downloads')))

        self._add_option('metadata_expire',
                         inherit(parent._get_option('metadata_expire')))
        self._add_option('cost', IntOption(1000))
        self._add_option('priority', IntOption(99))

        self._add_option('sslcacert',
                         inherit(parent._get_option('sslcacert'))) # :api
        self._add_option('sslverify',
                         inherit(parent._get_option('sslverify'))) # :api
        self._add_option('sslclientcert',
                         inherit(parent._get_option('sslclientcert'))) # :api
        self._add_option('sslclientkey',
                         inherit(parent._get_option('sslclientkey'))) # :api
        self._add_option('deltarpm', inherit(parent._get_option('deltarpm')))

        self._add_option('skip_if_unavailable', BoolOption(True)) # :api

        # yum compatibility options
        self._add_option('failovermethod',
                         SelectionOption('priority', choices=('priority',),
                                         notimplemented=('roundrobin',)))

    def _configure_from_options(self, opts):
        """Configure repos from the opts. """

        if getattr(opts, 'nogpgcheck', None):
            for optname in ['gpgcheck', 'repo_gpgcheck']:
                opt = self._get_option(optname)
                opt._set(False, dnf.conf.PRIO_COMMANDLINE)

        repo_setopts = getattr(opts, 'repo_setopts', {})
        if self._section in repo_setopts:
            # pylint: disable=W0212
            setopts = repo_setopts[self._section]._get_kwargs()
            for name, val in setopts:
                opt = self._get_option(name)
                if opt:
                    opt._set(val, dnf.conf.PRIO_COMMANDLINE)
                else:
                    msg = "Repo %s did not have a %s attr. before setopt"
                    logger.warning(msg, self._section, name)
