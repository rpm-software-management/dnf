# dnf configuration classes.
#
# Copyright (C) 2016-2017 Red Hat, Inc.
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

import copy
import dnf.conf.substitutions
import dnf.const
import dnf.exceptions
import dnf.pycomp
import dnf.util
import hawkey
import iniparse
import logging
import os
import libdnf.conf

PRIO_EMPTY = libdnf.conf.Option.Priority_EMPTY
PRIO_DEFAULT = libdnf.conf.Option.Priority_DEFAULT
PRIO_MAINCONFIG = libdnf.conf.Option.Priority_MAINCONFIG
PRIO_AUTOMATICCONFIG = libdnf.conf.Option.Priority_AUTOMATICCONFIG
PRIO_REPOCONFIG = libdnf.conf.Option.Priority_REPOCONFIG
PRIO_PLUGINDEFAULT = libdnf.conf.Option.Priority_PLUGINDEFAULT
PRIO_PLUGINCONFIG = libdnf.conf.Option.Priority_PLUGINCONFIG
PRIO_COMMANDLINE = libdnf.conf.Option.Priority_COMMANDLINE
PRIO_RUNTIME = libdnf.conf.Option.Priority_RUNTIME

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
    def __init__(self, option):
        if isinstance(option, libdnf.conf.Option):
            self._option = option
        else:
            self._option = libdnf.conf.OptionString(option)

    def _get(self):
        """Get option's value."""
        return self._option.getValue()

    def _get_priority(self):
        """Get option's priority."""
        return self._option.getPriority()

    def _set(self, value, priority=PRIO_RUNTIME):
        """Set option's value if priority is equal or higher
           than curent priority."""
        if value is None:
            try:
                self._option.set(priority, value)
            except Exception:
                pass
        else:
            try:
                if isinstance(value, list) or isinstance(value, tuple):
                    self._option.set(priority, libdnf.conf.VectorString(value))
                elif (isinstance(self._option, libdnf.conf.OptionBool) or
                      isinstance(self._option, libdnf.conf.OptionChildBool)) and \
                        isinstance(value, int):
                    self._option.set(priority, bool(value))
                else:
                    self._option.set(priority, value)
            except RuntimeError as e:
                raise dnf.exceptions.ConfigError(_("Error parsing '%s': %s")
                                                 % (value, str(e)),
                                                 raw_error=str(e))

    def _is_default(self):
        """Was value changed from default?"""
        return self._option.getPriority() == PRIO_DEFAULT

    # def _is_runtimeonly(self):
        """Was value changed from default?"""
        # return self._runtimeonly

    def _parse(self, strval):
        """Parse the string value to the option's native value."""
        # pylint: disable=R0201
        return self._option.fromString(strval)

    def _tostring(self):
        """Convert the option's native actual value to a string."""
        val = ('' if self._is_default() or
               self._option.getPriority() == PRIO_EMPTY
               else self._option.getValueString())
        return str(val)


class IntOption(Option):
    def __init__(self, default=0):
        option = libdnf.conf.OptionNumberInt32(default)
        super(IntOption, self).__init__(option)


class LongOption(Option):
    def __init__(self, default=0):
        option = libdnf.conf.OptionNumberInt64(default)
        super(LongOption, self).__init__(option)


class BoolOption(Option):
    def __init__(self, default=False):
        option = libdnf.conf.OptionBool(default)
        super(BoolOption, self).__init__(option)


class SelectionOption(Option):
    """Handles string values where only specific values are allowed."""
    def __init__(self, default=None, choices=()):
        option = libdnf.conf.OptionEnumString(default, libdnf.conf.VectorString(choices))
        super(SelectionOption, self).__init__(option)


class ListOption(Option):
    """Handles string values where only specific values are allowed."""
    def __init__(self, default=None):
        option = libdnf.conf.OptionStringList(libdnf.conf.VectorString(default))
        super(ListOption, self).__init__(option)


class SecondsOption(Option):
    def __init__(self, default=0):
        option = libdnf.conf.OptionSeconds(default)
        super(SecondsOption, self).__init__(option)


class StringOption(Option):
    def __init__(self, default=""):
        option = libdnf.conf.OptionString(default)
        super(StringOption, self).__init__(option)


class PathOption(Option):
    def __init__(self, default="", exists=False, absPath=False):
        option = libdnf.conf.OptionPath(default, exists, absPath)
        super(PathOption, self).__init__(option)


class BaseConfig(object):
    """Base class for storing configuration definitions.

       Subclass when creating your own definitions.

    """

    def __init__(self, config=None, section=None, parser=None):
        self.__dict__["_config"] = config
        self._option = {}
        self._section = section
        self._parser = parser

    # is used in the "automatic" and in the test, remove in future
    def _add_option(self, name, optionobj):
        self._option[name] = optionobj

        def prop_get(obj):
            return obj._option[name]._get()

        def prop_set(obj, val):
            obj._option[name]._set(val)

        setattr(type(self), name, property(prop_get, prop_set))

    def __getattr__(self, name):
        if "_config" not in self.__dict__:
            raise AttributeError("'{}' object has no attribute '{}'".format(self.__class__, name))
        option = getattr(self._config, name)
        if option is None:
            return None
        try:
            value = option().getValue()
        except Exception as ex:
            return None
        if isinstance(value, str):
            return ucd(value)
        return value

    def __setattr__(self, name, value):
        option = getattr(self._config, name, None)
        if option is None:
            # unknown config option, store to BaseConfig only
            return super(BaseConfig, self).__setattr__(name, value)
        if isinstance(value, Value):
            priority = value.priority
            value = value.value
        else:
            priority = PRIO_RUNTIME
        if value is None:
            try:
                option().set(priority, value)
            except Exception:
                pass
        else:
            try:
                if isinstance(value, list) or isinstance(value, tuple):
                    option().set(priority, libdnf.conf.VectorString(value))
                elif (isinstance(option(), libdnf.conf.OptionBool) or
                      isinstance(option(), libdnf.conf.OptionChildBool)) and isinstance(value, int):
                    option().set(priority, bool(value))
                else:
                    option().set(priority, value)
            except RuntimeError as e:
                raise dnf.exceptions.ConfigError(_("Error parsing '%s': %s")
                                                 % (value, str(e)),
                                                 raw_error=str(e))

    def __str__(self):
        out = []
        out.append('[%s]' % self._section)
        if self._config:
            for optBind in self._config.optBinds():
                try:
                    value = optBind.second.getValueString()
                except RuntimeError:
                    value = ""
                out.append('%s: %s' % (optBind.first, value))
        return '\n'.join(out)

    def _get_option(self, name):
        method = getattr(self._config, name, None)
        if method is None:
            return self._option.get(name, None)
        return Option(method())

    def _get_value(self, name):
        opt = self._get_option(name)
        if opt is None:
            return None
        return opt._get()

    def _set_value(self, name, value, priority=PRIO_RUNTIME):
        opt = self._get_option(name)
        if opt is None:
            raise Exception("Option " + name + "does not exists")
        return opt._set(value, priority)

    def _populate(self, parser, section, filename, priority=PRIO_DEFAULT):
        """Set option values from an INI file section."""
        if parser.hasSection(section):
            for name in parser.getData()[section]:
                value = parser.getSubstitutedValue(section, name)
                if not value or value == 'None':
                    value = ''

                try:
                    if not self._config:
                        raise RuntimeError()
                    self._config.optBinds().at(name).newString(priority, value)
                except RuntimeError:
                    opt = self._get_option(name)
                    if opt:  # and not opt._is_runtimeonly():
                        try:
                            if value is not None:
                                opt._set(value, priority)
                        except dnf.exceptions.ConfigError as e:
                            logger.debug(_('Unknown configuration value: '
                                           '%s=%s in %s; %s'), ucd(name),
                                         ucd(value), ucd(filename), e.raw_error)
                    else:
                        if name == 'arch' and hasattr(self, name):
                            setattr(self, name, value)
                        else:
                            logger.debug(
                                _('Unknown configuration option: %s = %s in %s'),
                                ucd(name), ucd(value), ucd(filename))

#    def _config_items(self):
        """Yield (name, value) pairs for every option in the instance."""
#        return self._option.items()

    def dump(self):
        # :api
        """Return a string representing the values of all the
           configuration options.
        """
        output = ['[%s]' % self._section]

        if self._config:
            for optBind in self._config.optBinds():
                # if not opt._is_runtimeonly():
                try:
                    output.append('%s = %s' % (optBind.first, optBind.second.getValueString()))
                except RuntimeError:
                    pass

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

        if self._config:
            for optBind in self._config.optBinds():
                # if (not option._is_runtimeonly() and
                if (always is None or optBind.first in always or
                        optBind.second.getPriority() >= PRIO_DEFAULT or
                        optBind.first in cfg_options):
                    self._parser.set(section, optBind.first, optBind.second.getValueString())

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
        with open(filename) as fp:
            ini = iniparse.INIConfig(fp)

        # b/c repoids can have $values in them we need to map both ways to figure
        # out which one is which
        if section_id not in ini:
            for sect in ini:
                if libdnf.conf.ConfigParser.substitute(sect, substitutions) == section_id:
                    section_id = sect

        for name, value in modify.items():
            if isinstance(value, list):
                value = ' '.join(value)
            ini[section_id][name] = value

        with open(filename, "w") as fp:
            fp.write(str(ini))


class MainConf(BaseConfig):
    # :api
    """Configuration option definitions for dnf.conf's [main] section."""
    def __init__(self, section='main', parser=None):
        # pylint: disable=R0915
        config = libdnf.conf.ConfigMain()
        super(MainConf, self).__init__(config, section, parser)
        self._get_option('pluginpath')._set([dnf.const.PLUGINPATH], PRIO_DEFAULT)
        self._get_option('pluginconfpath')._set([dnf.const.PLUGINCONFPATH], PRIO_DEFAULT)
        self.substitutions = dnf.conf.substitutions.Substitutions()
        self.arch = hawkey.detect_arch()
        self._config.system_cachedir().set(PRIO_DEFAULT, dnf.const.SYSTEM_CACHEDIR)

        # setup different cache and log for non-priviledged users
        if dnf.util.am_i_root():
            cachedir = dnf.const.SYSTEM_CACHEDIR
            logdir = '/var/log'
        else:
            try:
                cachedir = logdir = misc.getCacheDir()
            except (IOError, OSError) as e:
                msg = _('Could not set cachedir: {}').format(ucd(e))
                raise dnf.exceptions.Error(msg)

        self._config.cachedir().set(PRIO_DEFAULT, cachedir)
        self._config.logdir().set(PRIO_DEFAULT, logdir)
        # TODO move to libdnf
        self.modulesdir = PathOption('/etc/dnf/modules.d', absPath=True)
        # TODO move to libdnf
        self.moduledefaultsdir = PathOption('/etc/dnf/modules.defaults.d', absPath=True)

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
        if not isinstance(val, str):
            if any(os.path.exists(os.path.join(self._get_value('installroot'),
                                               p.lstrip('/'))) for p in val):
                opt._set(libdnf.conf.VectorString([self._prepend_installroot_path(p) for p in val]),
                         prio)
        elif os.path.exists(os.path.join(self._get_value('installroot'),
                                         val.lstrip('/'))):
            opt._set(self._prepend_installroot_path(val), prio)

    def prepend_installroot(self, optname):
        # :api
        opt = self._get_option(optname)
        prio = opt._get_priority()
        new_path = self._prepend_installroot_path(opt._get())
        opt._set(new_path, prio)

    def _prepend_installroot_path(self, path):
        root_path = os.path.join(self._get_value('installroot'), path.lstrip('/'))
        return libdnf.conf.ConfigParser.substitute(root_path, self.substitutions)

    def _configure_from_options(self, opts):
        """Configure parts of CLI from the opts """
        config_args = ['plugins', 'version', 'config_file_path',
                       'debuglevel', 'errorlevel', 'installroot',
                       'best', 'assumeyes', 'assumeno', 'clean_requirements_on_remove', 'gpgcheck',
                       'showdupesfromrepos', 'plugins', 'ip_resolve',
                       'rpmverbosity', 'disable_excludes', 'color',
                       'downloadonly', 'exclude', 'excludepkgs', 'skip_broken',
                       'tsflags', 'arch', 'basearch', 'ignorearch', 'cacheonly', 'comment']

        for name in config_args:
            value = getattr(opts, name, None)
            if value is not None and value != []:
                opt = self._get_option(name)
                if opt is not None:
                    appendValue = False
                    if self._config:
                        try:
                            appendValue = self._config.optBinds().at(name).getAddValue()
                        except RuntimeError:
                            # fails if option with "name" does not exist in _config (libdnf)
                            pass
                    if appendValue:
                        add_priority = dnf.conf.PRIO_COMMANDLINE
                        if add_priority < opt._get_priority():
                            add_priority = opt._get_priority()
                        for item in value:
                            if item:
                                opt._set(opt._get() + [item], add_priority)
                            else:
                                opt._set([], dnf.conf.PRIO_COMMANDLINE)
                    else:
                        opt._set(value, dnf.conf.PRIO_COMMANDLINE)
                elif hasattr(self, name):
                    setattr(self, name, value)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'),
                                   ucd(name), ucd(value))

        if getattr(opts, 'gpgcheck', None) is False:
            opt = self._get_option("localpkg_gpgcheck")
            opt._set(False, dnf.conf.PRIO_COMMANDLINE)

        if hasattr(opts, 'main_setopts'):
            # now set all the non-first-start opts from main from our setopts
            # pylint: disable=W0212
            for name, values in opts.main_setopts.items():
                for val in values:
                    try:
                        # values in main_setopts are strings, we try to parse it using newString()
                        self._config.optBinds().at(name).newString(dnf.conf.PRIO_COMMANDLINE, val)
                    except RuntimeError:
                        # if config option with "name" doesn't exist in _config, it could be defined
                        # only in Python layer
                        option = self._option.get(name, None)
                        if option:
                            option._set(val, dnf.conf.PRIO_COMMANDLINE)
                        elif hasattr(self, name):
                            setattr(self, name, val)
                        else:
                            msg = _("Main config did not have a %s attr. before setopt")
                            logger.warning(msg, name)

    def exclude_pkgs(self, pkgs):
        # :api
        name = "excludepkgs"

        if pkgs is not None and pkgs != []:
            confopt = self._get_option(name)
            if confopt:
                confopt._set(pkgs, dnf.conf.PRIO_COMMANDLINE)
            else:
                logger.warning(_('Unknown configuration option: %s = %s'),
                               ucd(name), ucd(pkgs))

    def _adjust_conf_options(self):
        """Adjust conf options interactions"""

        skip_broken = self._get_option('skip_broken')
        skip_broken_val = skip_broken._get()
        if skip_broken_val:
            strict = self._get_option('strict')
            strict._set(not skip_broken_val, skip_broken._get_priority())

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
        self.substitutions['releasever'] = str(val)

    @property
    def arch(self):
        # :api
        return self.substitutions.get('arch')

    @arch.setter
    def arch(self, val):
        # :api

        if val is None:
            self.substitutions.pop('arch', None)
            return
        if val not in dnf.rpm._BASEARCH_MAP.keys():
            msg = _('Incorrect or unknown "{}": {}')
            raise dnf.exceptions.Error(msg.format("arch", val))
        self.substitutions['arch'] = val
        self.basearch = dnf.rpm.basearch(val)

    @property
    def basearch(self):
        # :api
        return self.substitutions.get('basearch')

    @basearch.setter
    def basearch(self, val):
        # :api

        if val is None:
            self.substitutions.pop('basearch', None)
            return
        if val not in dnf.rpm._BASEARCH_MAP.values():
            msg = _('Incorrect or unknown "{}": {}')
            raise dnf.exceptions.Error(msg.format("basearch", val))
        self.substitutions['basearch'] = val

    def read(self, filename=None, priority=PRIO_DEFAULT):
        # :api
        if filename is None:
            filename = self._get_value('config_file_path')
        self._parser = libdnf.conf.ConfigParser()
        try:
            self._parser.read(filename)
        except RuntimeError as e:
            raise dnf.exceptions.ConfigError(_('Parsing file "%s" failed: %s') % (filename, e))
        except IOError as e:
            logger.warning(e)
        self._populate(self._parser, self._section, filename, priority)

        # update to where we read the file from
        self._set_value('config_file_path', filename, priority)

    @property
    def verbose(self):
        return self._get_value('debuglevel') >= dnf.const.VERBOSE_LEVEL


class RepoConf(BaseConfig):
    """Option definitions for repository INI file sections."""

    def __init__(self, parent, section=None, parser=None):
        super(RepoConf, self).__init__(libdnf.conf.ConfigRepo(
            parent._config if parent else libdnf.conf.ConfigMain()), section, parser)
        self._masterConfig = parent._config if parent else libdnf.conf.ConfigMain()

    def _configure_from_options(self, opts):
        """Configure repos from the opts. """

        if getattr(opts, 'gpgcheck', None) is False:
            for optname in ['gpgcheck', 'repo_gpgcheck']:
                opt = self._get_option(optname)
                opt._set(False, dnf.conf.PRIO_COMMANDLINE)

        repo_setopts = getattr(opts, 'repo_setopts', {})
        if self._section in repo_setopts:
            # pylint: disable=W0212
            setopts = repo_setopts[self._section].items()
            for name, values in setopts:
                for val in values:
                    try:
                        # values in repo_setopts are strings, we try to parse it using newString()
                        self._config.optBinds().at(name).newString(dnf.conf.PRIO_COMMANDLINE, val)
                    except RuntimeError:
                        # if config option with "name" doesn't exist in _config, it could be defined
                        # only in Python layer
                        option = self._option.get(name, None)
                        if option:
                            option._set(val, dnf.conf.PRIO_COMMANDLINE)
                        else:
                            msg = _("Repo %s did not have a %s attr. before setopt")
                            logger.warning(msg, self._section, name)

# TODO move to libdnf
class ModuleConf(BaseConfig):
    """Option definitions for module INI file sections."""

    def __init__(self, section=None, parser=None):
        config = None
        super(ModuleConf, self).__init__(config, section, parser)
        # module name, stream and installed version
        self.name = StringOption(section)
        self.stream = StringOption("")
        # installed profiles
        self.profiles = ListOption([])
        # enable/disable a module
        self.enabled = BoolOption(False)
        self.state = StringOption("")

    def _write(self, fileobj):
        if self.state._get() == "" and self.enabled._get():
            self.state._set("enabled")

        output = "[{}]\n".format(self._section)
        output += "name = {}\n".format(self.name._get())
        output += "stream = {}\n".format(self.stream._get())
        output += "profiles = {}\n".format(",".join(self.profiles._get()))
        output += "state = {}\n".format(self.state._get())
        fileobj.write(output)
