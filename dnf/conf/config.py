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
from dnf.pycomp import basestring, urlparse

import fnmatch
import dnf.conf.substitutions
import dnf.const
import dnf.exceptions
import dnf.pycomp
import dnf.util
import hawkey
import logging
import os
import libdnf.conf
import libdnf.repo
import tempfile

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


class BaseConfig(object):
    """Base class for storing configuration definitions.

       Subclass when creating your own definitions.

    """

    def __init__(self, config=None, section=None, parser=None):
        self.__dict__["_config"] = config
        self._section = section

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
        self._set_value(name, value, PRIO_RUNTIME)

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

    def _has_option(self, name):
        method = getattr(self._config, name, None)
        return method is not None

    def _get_value(self, name):
        method = getattr(self._config, name, None)
        if method is None:
            return None
        return method().getValue()

    def _get_priority(self, name):
        method = getattr(self._config, name, None)
        if method is None:
            return None
        return method().getPriority()

    def _set_value(self, name, value, priority=PRIO_RUNTIME):
        """Set option's value if priority is equal or higher
           than current priority."""
        method = getattr(self._config, name, None)
        if method is None:
            raise Exception("Option \"" + name + "\" does not exists")
        option = method()
        if value is None:
            try:
                option.set(priority, value)
            except Exception:
                pass
        else:
            try:
                if isinstance(value, list) or isinstance(value, tuple):
                    option.set(priority, libdnf.conf.VectorString(value))
                elif (isinstance(option, libdnf.conf.OptionBool)
                      or isinstance(option, libdnf.conf.OptionChildBool)
                      ) and isinstance(value, int):
                    option.set(priority, bool(value))
                else:
                    option.set(priority, value)
            except RuntimeError as e:
                raise dnf.exceptions.ConfigError(_("Error parsing '%s': %s")
                                                 % (value, str(e)),
                                                 raw_error=str(e))

    def _populate(self, parser, section, filename, priority=PRIO_DEFAULT):
        """Set option values from an INI file section."""
        if parser.hasSection(section):
            for name in parser.options(section):
                value = parser.getSubstitutedValue(section, name)
                if not value or value == 'None':
                    value = ''
                if hasattr(self._config, name):
                    try:
                        self._config.optBinds().at(name).newString(priority, value)
                    except RuntimeError as e:
                        logger.debug(_('Unknown configuration value: %s=%s in %s; %s'),
                                     ucd(name), ucd(value), ucd(filename), str(e))
                else:
                    if name == 'arch' and hasattr(self, name):
                        setattr(self, name, value)
                    else:
                        logger.debug(
                            _('Unknown configuration option: %s = %s in %s'),
                            ucd(name), ucd(value), ucd(filename))

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

    @staticmethod
    def write_raw_configfile(filename, section_id, substitutions, modify):
        # :api
        """
        filename   - name of config file (.conf or .repo)
        section_id - id of modified section (e.g. main, fedora, updates)
        substitutions - instance of base.conf.substitutions
        modify     - dict of modified options
        """
        parser = libdnf.conf.ConfigParser()
        parser.read(filename)

        # b/c repoids can have $values in them we need to map both ways to figure
        # out which one is which
        if not parser.hasSection(section_id):
            for sect in parser.getData():
                if libdnf.conf.ConfigParser.substitute(sect, substitutions) == section_id:
                    section_id = sect

        for name, value in modify.items():
            if isinstance(value, list):
                value = ' '.join(value)
            parser.setValue(section_id, name, value)

        parser.write(filename, False)


class MainConf(BaseConfig):
    # :api
    """Configuration option definitions for dnf.conf's [main] section."""
    def __init__(self, section='main', parser=None):
        # pylint: disable=R0915
        config = libdnf.conf.ConfigMain()
        super(MainConf, self).__init__(config, section, parser)
        self._set_value('pluginpath', [dnf.const.PLUGINPATH], PRIO_DEFAULT)
        self._set_value('pluginconfpath', [dnf.const.PLUGINCONFPATH], PRIO_DEFAULT)
        self.substitutions = dnf.conf.substitutions.Substitutions()
        self.arch = hawkey.detect_arch()
        self._config.system_cachedir().set(PRIO_DEFAULT, dnf.const.SYSTEM_CACHEDIR)

        # setup different cache and log for non-privileged users
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

        # track list of temporary files created
        self.tempfiles = []

    def __del__(self):
        for file_name in self.tempfiles:
            os.unlink(file_name)

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

    def _check_remote_file(self, optname):
        """
        In case the option value is a remote URL, download it to the temporary location
        and use this temporary file instead.
        """
        prio = self._get_priority(optname)
        val = self._get_value(optname)
        if isinstance(val, basestring):
            location = urlparse.urlparse(val)
            if location[0] in ('file', ''):
                # just strip the file:// prefix
                self._set_value(optname, location.path, prio)
            else:
                downloader = libdnf.repo.Downloader()
                temp_fd, temp_path = tempfile.mkstemp(prefix='dnf-downloaded-config-')
                self.tempfiles.append(temp_path)
                try:
                    downloader.downloadURL(None, val, temp_fd)
                except RuntimeError as e:
                    raise dnf.exceptions.ConfigError(
                        _('Configuration file URL "{}" could not be downloaded:\n'
                          '  {}').format(val, str(e)))
                else:
                    self._set_value(optname, temp_path, prio)
                finally:
                    os.close(temp_fd)

    def _search_inside_installroot(self, optname):
        """
        Return root used as prefix for option (installroot or "/"). When specified from commandline
        it returns value from conf.installroot
        """
        installroot = self._get_value('installroot')
        if installroot == "/":
            return installroot
        prio = self._get_priority(optname)
        # don't modify paths specified on commandline
        if prio >= PRIO_COMMANDLINE:
            return installroot
        val = self._get_value(optname)
        # if it exists inside installroot use it (i.e. adjust configuration)
        # for lists any component counts
        if not isinstance(val, str):
            if any(os.path.exists(os.path.join(installroot, p.lstrip('/'))) for p in val):
                self._set_value(
                    optname,
                    libdnf.conf.VectorString([self._prepend_installroot_path(p) for p in val]),
                    prio
                )
                return installroot
        elif os.path.exists(os.path.join(installroot, val.lstrip('/'))):
            self._set_value(optname, self._prepend_installroot_path(val), prio)
            return installroot
        return "/"

    def prepend_installroot(self, optname):
        # :api
        prio = self._get_priority(optname)
        new_path = self._prepend_installroot_path(self._get_value(optname))
        self._set_value(optname, new_path, prio)

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
                if self._has_option(name):
                    appendValue = False
                    if self._config:
                        try:
                            appendValue = self._config.optBinds().at(name).getAddValue()
                        except RuntimeError:
                            # fails if option with "name" does not exist in _config (libdnf)
                            pass
                    if appendValue:
                        add_priority = dnf.conf.PRIO_COMMANDLINE
                        if add_priority < self._get_priority(name):
                            add_priority = self._get_priority(name)
                        for item in value:
                            if item:
                                self._set_value(name, self._get_value(name) + [item], add_priority)
                            else:
                                self._set_value(name, [], dnf.conf.PRIO_COMMANDLINE)
                    else:
                        self._set_value(name, value, dnf.conf.PRIO_COMMANDLINE)
                elif hasattr(self, name):
                    setattr(self, name, value)
                else:
                    logger.warning(_('Unknown configuration option: %s = %s'),
                                   ucd(name), ucd(value))

        if getattr(opts, 'gpgcheck', None) is False:
            self._set_value("localpkg_gpgcheck", False, dnf.conf.PRIO_COMMANDLINE)

        if hasattr(opts, 'main_setopts'):
            # now set all the non-first-start opts from main from our setopts
            # pylint: disable=W0212
            for name, values in opts.main_setopts.items():
                for val in values:
                    if hasattr(self._config, name):
                        try:
                            # values in main_setopts are strings, try to parse it using newString()
                            self._config.optBinds().at(name).newString(PRIO_COMMANDLINE, val)
                        except RuntimeError as e:
                            raise dnf.exceptions.ConfigError(
                                _("Error parsing --setopt with key '%s', value '%s': %s")
                                % (name, val, str(e)), raw_error=str(e))
                    else:
                        # if config option with "name" doesn't exist in _config, it could be defined
                        # only in Python layer
                        if hasattr(self, name):
                            setattr(self, name, val)
                        else:
                            msg = _("Main config did not have a %s attr. before setopt")
                            logger.warning(msg, name)

    def exclude_pkgs(self, pkgs):
        # :api
        name = "excludepkgs"

        if pkgs is not None and pkgs != []:
            if self._has_option(name):
                self._set_value(name, pkgs, dnf.conf.PRIO_COMMANDLINE)
            else:
                logger.warning(_('Unknown configuration option: %s = %s'),
                               ucd(name), ucd(pkgs))

    def _adjust_conf_options(self):
        """Adjust conf options interactions"""

        skip_broken_val = self._get_value('skip_broken')
        if skip_broken_val:
            self._set_value('strict', not skip_broken_val, self._get_priority('skip_broken'))

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
        parser = libdnf.conf.ConfigParser()
        try:
            parser.read(filename)
        except RuntimeError as e:
            raise dnf.exceptions.ConfigError(_('Parsing file "%s" failed: %s') % (filename, e))
        except IOError as e:
            logger.warning(e)
        self._populate(parser, self._section, filename, priority)

        # update to where we read the file from
        self._set_value('config_file_path', filename, priority)

    @property
    def verbose(self):
        return self._get_value('debuglevel') >= dnf.const.VERBOSE_LEVEL


class RepoConf(BaseConfig):
    """Option definitions for repository INI file sections."""

    def __init__(self, parent, section=None, parser=None):
        masterConfig = parent._config if parent else libdnf.conf.ConfigMain()
        super(RepoConf, self).__init__(libdnf.conf.ConfigRepo(masterConfig), section, parser)
        # Do not remove! Attribute is a reference holder.
        # Prevents premature removal of the masterConfig. The libdnf ConfigRepo points to it.
        self._masterConfigRefHolder = masterConfig
        if section:
            self._config.name().set(PRIO_DEFAULT, section)

    def _configure_from_options(self, opts):
        """Configure repos from the opts. """

        if getattr(opts, 'gpgcheck', None) is False:
            for optname in ['gpgcheck', 'repo_gpgcheck']:
                self._set_value(optname, False, dnf.conf.PRIO_COMMANDLINE)

        repo_setopts = getattr(opts, 'repo_setopts', {})
        for repoid, setopts in repo_setopts.items():
            if not fnmatch.fnmatch(self._section, repoid):
                continue
            for name, values in setopts.items():
                for val in values:
                    if hasattr(self._config, name):
                        try:
                            # values in repo_setopts are strings, try to parse it using newString()
                            self._config.optBinds().at(name).newString(PRIO_COMMANDLINE, val)
                        except RuntimeError as e:
                            raise dnf.exceptions.ConfigError(
                                _("Error parsing --setopt with key '%s.%s', value '%s': %s")
                                % (self._section, name, val, str(e)), raw_error=str(e))
                    else:
                        msg = _("Repo %s did not have a %s attr. before setopt")
                        logger.warning(msg, self._section, name)
