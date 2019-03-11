# __init__.py
# dnf.automatic CLI
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
from __future__ import print_function
from __future__ import unicode_literals
from dnf.i18n import _, ucd
import dnf
import dnf.automatic.emitter
import dnf.cli
import dnf.cli.cli
import dnf.cli.output
import dnf.conf
import libdnf.conf
import dnf.const
import dnf.exceptions
import dnf.util
import dnf.logging
import hawkey
import logging
import socket
import argparse
import random
import time

logger = logging.getLogger('dnf')


def build_emitters(conf):
    emitters = dnf.util.MultiCallList([])
    system_name = conf.emitters.system_name
    emit_via = conf.emitters.emit_via
    if emit_via:
        for name in emit_via:
            if name == 'email':
                emitter = dnf.automatic.emitter.EmailEmitter(system_name, conf.email)
                emitters.append(emitter)
            elif name == 'stdio':
                emitter = dnf.automatic.emitter.StdIoEmitter(system_name)
                emitters.append(emitter)
            elif name == 'motd':
                emitter = dnf.automatic.emitter.MotdEmitter(system_name)
                emitters.append(emitter)
            elif name == 'command_email':
                emitter = dnf.automatic.emitter.CommandEmailEmitter(system_name, conf.command_email)
                emitters.append(emitter)
            else:
                raise dnf.exceptions.ConfigError("Unknowr emitter option: %s" % name)
    return emitters


def parse_arguments(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('conf_path', nargs='?', default=dnf.const.CONF_AUTOMATIC_FILENAME)
    parser.add_argument('--timer', action='store_true')
    parser.add_argument('--installupdates', dest='installupdates', action='store_true')
    parser.add_argument('--downloadupdates', dest='downloadupdates', action='store_true')
    parser.add_argument('--no-installupdates', dest='installupdates', action='store_false')
    parser.add_argument('--no-downloadupdates', dest='downloadupdates', action='store_false')
    parser.set_defaults(installupdates=None)
    parser.set_defaults(downloadupdates=None)

    return parser.parse_args(args), parser


class AutomaticConfig(object):
    def __init__(self, filename=None, downloadupdates=None,
                 installupdates=None):
        if not filename:
            filename = dnf.const.CONF_AUTOMATIC_FILENAME
        self.commands = CommandsConfig()
        self.email = EmailConfig()
        self.emitters = EmittersConfig()
        self.command_email = CommandEmailConfig()
        self._parser = None
        self._load(filename)

        if downloadupdates:
            self.commands.download_updates = True
        elif downloadupdates is False:
            self.commands.download_updates = False
        if installupdates:
            self.commands.apply_updates = True
        elif installupdates is False:
            self.commands.apply_updates = False

        self.commands.imply()
        self.filename = filename

    def _load(self, filename):
        parser = libdnf.conf.ConfigParser()
        try:
            parser.read(filename)
        except RuntimeError as e:
            raise dnf.exceptions.ConfigError('Parsing file "%s" failed: %s' % (filename, e))
        except IOError as e:
            logger.warning(e)

        self.commands.populate(parser, 'commands', filename,
                               libdnf.conf.Option.Priority_AUTOMATICCONFIG)
        self.email.populate(parser, 'email', filename, libdnf.conf.Option.Priority_AUTOMATICCONFIG)
        self.emitters.populate(parser, 'emitters', filename,
                               libdnf.conf.Option.Priority_AUTOMATICCONFIG)
        self.command_email.populate(parser, 'command_email', filename,
                                    libdnf.conf.Option.Priority_AUTOMATICCONFIG)
        self._parser = parser

    def update_baseconf(self, baseconf):
        baseconf._populate(self._parser, 'base', self.filename, dnf.conf.PRIO_AUTOMATICCONFIG)


class Config(object):
    def __init__(self):
        self._options = {}

    def add_option(self, name, optionobj):
        self._options[name] = optionobj

        def prop_get(obj):
            return obj._options[name].getValue()

        def prop_set(obj, val):
            obj._options[name].set(libdnf.conf.Option.Priority_RUNTIME, val)

        setattr(type(self), name, property(prop_get, prop_set))

    def populate(self, parser, section, filename, priority):
        """Set option values from an INI file section."""
        if parser.hasSection(section):
            for name in parser.options(section):
                value = parser.getValue(section, name)
                if not value or value == 'None':
                    value = ''
                opt = self._options.get(name, None)
                if opt:
                    try:
                        opt.set(priority, value)
                    except RuntimeError as e:
                        logger.debug(_('Unknown configuration value: %s=%s in %s; %s'),
                                     ucd(name), ucd(value), ucd(filename), str(e))
                else:
                    logger.debug(
                        _('Unknown configuration option: %s = %s in %s'),
                        ucd(name), ucd(value), ucd(filename))


class CommandsConfig(Config):
    def __init__(self):
        super(CommandsConfig, self).__init__()
        self.add_option('apply_updates', libdnf.conf.OptionBool(False))
        self.add_option('base_config_file', libdnf.conf.OptionString('/etc/dnf/dnf.conf'))
        self.add_option('download_updates', libdnf.conf.OptionBool(False))
        self.add_option('upgrade_type', libdnf.conf.OptionEnumString('default',
                        libdnf.conf.VectorString(['default', 'security'])))
        self.add_option('random_sleep', libdnf.conf.OptionNumberInt32(300))

    def imply(self):
        if self.apply_updates:
            self.download_updates = True


class EmailConfig(Config):
    def __init__(self):
        super(EmailConfig, self).__init__()
        self.add_option('email_to',
                        libdnf.conf.OptionStringList(libdnf.conf.VectorString(["root"])))
        self.add_option('email_from', libdnf.conf.OptionString("root"))
        self.add_option('email_host', libdnf.conf.OptionString("localhost"))
        self.add_option('email_port', libdnf.conf.OptionNumberInt32(25))


class CommandConfig(Config):
    _default_command_format = "cat"
    _default_stdin_format = "{body}"

    def __init__(self):
        super(CommandConfig, self).__init__()
        self.add_option('command_format',
                        libdnf.conf.OptionString(self._default_command_format))
        self.add_option('stdin_format',
                        libdnf.conf.OptionString(self._default_stdin_format))


class CommandEmailConfig(CommandConfig):
    _default_command_format = "mail -s {subject} -r {email_from} {email_to}"

    def __init__(self):
        super(CommandEmailConfig, self).__init__()
        self.add_option('email_to',
                        libdnf.conf.OptionStringList(libdnf.conf.VectorString(["root"])))
        self.add_option('email_from', libdnf.conf.OptionString("root"))


class EmittersConfig(Config):
    def __init__(self):
        super(EmittersConfig, self).__init__()
        self.add_option('emit_via', libdnf.conf.OptionStringList(
            libdnf.conf.VectorString(['email', 'stdio'])))
        self.add_option('output_width', libdnf.conf.OptionNumberInt32(80))
        self.add_option('system_name', libdnf.conf.OptionString(socket.gethostname()))


def main(args):
    (opts, parser) = parse_arguments(args)

    try:
        conf = AutomaticConfig(opts.conf_path, opts.downloadupdates,
                               opts.installupdates)
        with dnf.Base() as base:
            cli = dnf.cli.Cli(base)
            cli._read_conf_file()
            conf.update_baseconf(base.conf)
            base.init_plugins(cli=cli)
            logger.debug(_('Started dnf-automatic.'))

            if opts.timer:
                sleeper = random.randint(0, conf.commands.random_sleep)
                logger.debug(_('Sleep for %s seconds'), sleeper)
                time.sleep(sleeper)

            base.pre_configure_plugins()
            base.read_all_repos()
            base.configure_plugins()
            base.fill_sack()
            upgrade(base, conf.commands.upgrade_type)
            base.resolve()
            output = dnf.cli.output.Output(base, base.conf)
            trans = base.transaction
            if not trans:
                return 0

            lst = output.list_transaction(trans)
            emitters = build_emitters(conf)
            emitters.notify_available(lst)
            if not conf.commands.download_updates:
                emitters.commit()
                return 0

            base.download_packages(trans.install_set)
            emitters.notify_downloaded()
            if not conf.commands.apply_updates:
                emitters.commit()
                return 0

            base.do_transaction()
            emitters.notify_applied()
            emitters.commit()
    except dnf.exceptions.Error as exc:
        logger.error(_('Error: %s'), ucd(exc))
        return 1
    return 0


def upgrade(base, upgrade_type):
    if upgrade_type == 'security':
        base._update_security_filters.append(base.sack.query().upgrades().filterm(
            advisory_type='security'))
        base.upgrade_all()
    elif upgrade_type == 'default':
        base.upgrade_all()
    else:
        raise dnf.exceptions.Error(
            'Unsupported upgrade_type "{}", only "default" and "security" supported'.format(
                upgrade_type))
