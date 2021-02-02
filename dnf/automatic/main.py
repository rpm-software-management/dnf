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

import argparse
import logging
import random
import socket
import time

from dnf.i18n import _, ucd, P_
import dnf
import dnf.automatic.emitter
import dnf.cli
import dnf.cli.cli
import dnf.cli.output
import dnf.conf
import dnf.const
import dnf.exceptions
import dnf.util
import dnf.logging
import dnf.pycomp
import libdnf.conf

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
            elif name == 'command':
                emitter = dnf.automatic.emitter.CommandEmitter(system_name, conf.command)
                emitters.append(emitter)
            elif name == 'command_email':
                emitter = dnf.automatic.emitter.CommandEmailEmitter(system_name, conf.command_email)
                emitters.append(emitter)
            else:
                raise dnf.exceptions.ConfigError("Unknown emitter option: %s" % name)
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
        self.command = CommandConfig()
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
        self.command.populate(parser, 'command', filename,
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
        self.add_option('network_online_timeout', libdnf.conf.OptionNumberInt32(60))

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
    _default_command_format = "mail -Ssendwait -s {subject} -r {email_from} {email_to}"

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


def gpgsigcheck(base, pkgs):
    ok = True
    for po in pkgs:
        result, errmsg = base.package_signature_check(po)
        if result != 0:
            ok = False
            logger.critical(errmsg)
    if not ok:
        raise dnf.exceptions.Error(_("GPG check FAILED"))


def wait_for_network(repos, timeout):
    '''
    Wait up to <timeout> seconds for network connection to be available.
    if <timeout> is 0 the network availability detection will be skipped.
    Returns True if any remote repository is accessible or remote repositories are not enabled.
    Returns False if none of remote repositories is accessible.
    '''
    if timeout <= 0:
        return True

    remote_schemes = {
        'http': 80,
        'https': 443,
        'ftp': 21,
    }

    def remote_address(url_list):
        for url in url_list:
            parsed_url = dnf.pycomp.urlparse.urlparse(url)
            if parsed_url.hostname and parsed_url.scheme in remote_schemes:
                yield (parsed_url.hostname,
                       parsed_url.port or remote_schemes[parsed_url.scheme])

    # collect possible remote repositories urls
    addresses = set()
    for repo in repos.iter_enabled():
        addresses.update(remote_address(repo.baseurl))
        addresses.update(remote_address([repo.mirrorlist]))
        addresses.update(remote_address([repo.metalink]))

    if not addresses:
        # there is no remote repository enabled so network connection should not be needed
        return True

    logger.debug(_('Waiting for internet connection...'))
    time_0 = time.time()
    while time.time() - time_0 < timeout:
        for host, port in addresses:
            try:
                s = socket.create_connection((host, port), 1)
                s.close()
                return True
            except socket.error:
                pass
        time.sleep(1)
    return False


def main(args):
    (opts, parser) = parse_arguments(args)

    try:
        conf = AutomaticConfig(opts.conf_path, opts.downloadupdates,
                               opts.installupdates)
        with dnf.Base() as base:
            cli = dnf.cli.Cli(base)
            cli._read_conf_file()
            # Although dnf-automatic does not use demands, the versionlock
            # plugin uses this demand do decide whether it's rules should
            # be applied.
            # https://bugzilla.redhat.com/show_bug.cgi?id=1746562
            cli.demands.resolving = True
            conf.update_baseconf(base.conf)
            base.init_plugins(cli=cli)
            logger.debug(_('Started dnf-automatic.'))

            if opts.timer:
                sleeper = random.randint(0, conf.commands.random_sleep)
                logger.debug(P_('Sleep for {} second', 'Sleep for {} seconds', sleeper).format(sleeper))
                time.sleep(sleeper)

            base.pre_configure_plugins()
            base.read_all_repos()

            if not wait_for_network(base.repos, conf.commands.network_online_timeout):
                logger.warning(_('System is off-line.'))

            base.configure_plugins()
            base.fill_sack()
            upgrade(base, conf.commands.upgrade_type)
            base.resolve()
            output = dnf.cli.output.Output(base, base.conf)
            trans = base.transaction
            if not trans:
                return 0

            lst = output.list_transaction(trans, total_width=80)
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

            gpgsigcheck(base, trans.install_set)
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
